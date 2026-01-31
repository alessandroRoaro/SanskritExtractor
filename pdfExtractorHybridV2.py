"""
Hybrid Sanskrit Dictionary Extractor V2
- Uses Surya as base (good Devanagari, structure, roots, subscripts)
- Uses Google Cloud Vision for IAST corrections
- Imports functions from both pdfExtractorSurya and pdfExtractorGoogleVision
"""

from PIL import Image
from surya.foundation import FoundationPredictor
from surya.recognition import RecognitionPredictor
from surya.detection import DetectionPredictor
import os
import re

# Import processing functions from Surya extractor
from pdfExtractorSurya import (
    convert_math_to_unicode,
    clean_page_output,
    fix_root_prefixes,
    add_missing_devanagari
)

# Import Google Vision function
from pdfExtractorGoogleVision import run_ocr_columns as run_google_vision_ocr


def run_surya_ocr(image_path, rec_predictor, det_predictor):
    """Run Surya OCR on an image with column splitting, return processed text."""
    image = Image.open(image_path)
    width, height = image.size
    
    # Split into columns
    left_col = image.crop((0, 0, width // 2, height))
    right_col = image.crop((width // 2, 0, width, height))
    
    # Process both columns with Surya
    predictions = rec_predictor([left_col, right_col], det_predictor=det_predictor, math_mode=False)
    
    # Extract text from left column
    page_text = ""
    for line in predictions[0].text_lines:
        page_text += line.text + "\n"
    
    page_text += "\n"  # Separator between columns
    
    # Extract text from right column
    for line in predictions[1].text_lines:
        page_text += line.text + "\n"
    
    # Apply Surya-specific post-processing
    page_text = convert_math_to_unicode(page_text)
    page_text = fix_root_prefixes(page_text)
    page_text = add_missing_devanagari(page_text)
    page_text = clean_page_output(page_text)
    
    return page_text


def extract_iast_tokens(text):
    """Extract IAST tokens from text."""
    iast_pattern = re.compile(r'[a-zA-ZāĀīĪūŪṛṚṝṜḷḶḹḸṃṂḥḤṅṄñÑṭṬḍḌṇṆśŚṣṢ₀₁₂₃₄₅₆₇₈₉]+')
    return set(iast_pattern.findall(text))


def fix_iast_with_google_vision(surya_text, gv_text):
    """
    Fix IAST in Surya output using Google Vision's accurate IAST.
    
    Strategy: Find IAST words in Surya that differ from Google Vision
    and replace them with the correct version.
    """
    # Get all IAST tokens from Google Vision (the accurate source)
    gv_tokens = extract_iast_tokens(gv_text)
    
    # Build a mapping of normalized forms to correct forms
    def normalize(word):
        return re.sub(r'[₀₁₂₃₄₅₆₇₈₉0-9]', '', word.lower())
    
    gv_lookup = {}
    for token in gv_tokens:
        norm = normalize(token)
        if norm and len(norm) > 2:  # Skip very short words
            gv_lookup[norm] = token
    
    # Find and fix IAST words in Surya text
    iast_pattern = re.compile(r'[a-zA-ZāĀīĪūŪṛṚṝṜḷḶḹḸṃṂḥḤṅṄñÑṭṬḍḌṇṆśŚṣṢ₀₁₂₃₄₅₆₇₈₉]+')
    
    def replace_if_better(match):
        word = match.group(0)
        norm = normalize(word)
        
        # If Google Vision has a version of this word, check if it's different
        if norm in gv_lookup:
            gv_word = gv_lookup[norm]
            # Only replace if the words differ in diacritics (not just case/subscripts)
            if normalize(word) == normalize(gv_word) and word != gv_word:
                # Preserve the subscript from original if GV doesn't have one
                surya_subscript = re.search(r'[₀₁₂₃₄₅₆₇₈₉]', word)
                gv_subscript = re.search(r'[₀₁₂₃₄₅₆₇₈₉]', gv_word)
                
                if surya_subscript and not gv_subscript:
                    return gv_word + surya_subscript.group(0)
                return gv_word
        
        return word
    
    fixed_text = iast_pattern.sub(replace_if_better, surya_text)
    return fixed_text


def process_page_hybrid(image_path, rec_predictor, det_predictor):
    """Process a single page with hybrid approach (Surya + Google Vision)."""
    print(f"  Running Surya OCR...")
    surya_text = run_surya_ocr(image_path, rec_predictor, det_predictor)
    
    print(f"  Running Google Vision OCR...")
    gv_text = run_google_vision_ocr(image_path)
    
    print(f"  Fixing IAST with Google Vision...")
    hybrid_text = fix_iast_with_google_vision(surya_text, gv_text)
    
    return hybrid_text


def extract_text_from_images(page_range, output_path):
    """Extract text from multiple page images using hybrid approach."""
    
    # Check Google Vision credentials
    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        print("WARNING: GOOGLE_APPLICATION_CREDENTIALS not set.")
        print("Google Vision IAST correction will not work.")
        print("Set it with: export GOOGLE_APPLICATION_CREDENTIALS='/path/to/key.json'")
        print()
    
    # Initialize Surya predictors once
    print("Initializing Surya models...")
    foundation_predictor = FoundationPredictor()
    det_predictor = DetectionPredictor()
    rec_predictor = RecognitionPredictor(foundation_predictor)
    
    all_text = []
    page_list = list(page_range)
    total_pages = len(page_list)
    
    for i, page_num in enumerate(page_list):
        image_path = f'pages/page_{page_num}.png'
        print(f"Processing {image_path} ({i+1}/{total_pages})...")
        
        try:
            if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
                # Full hybrid mode
                page_text = process_page_hybrid(image_path, rec_predictor, det_predictor)
            else:
                # Surya only mode (no Google Vision)
                page_text = run_surya_ocr(image_path, rec_predictor, det_predictor)
            
            all_text.append(page_text)
            print(f"  Done.")
            
        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            all_text.append(f"ERROR on page {page_num}: {e}\n")
    
    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_text))
    
    print(f"\nText extracted and saved to {output_path}")
    print(f"Total pages processed: {len(all_text)}")


if __name__ == "__main__":
    import sys
    
    # Default: pages 1-950
    start_page = 1
    end_page = 950
    output_path = "extracted_dictionary_hybrid.txt"
    
    # Allow command line override: python pdfExtractorHybridV2.py [start] [end] [output]
    if len(sys.argv) >= 2:
        start_page = int(sys.argv[1])
    if len(sys.argv) >= 3:
        end_page = int(sys.argv[2])
    if len(sys.argv) >= 4:
        output_path = sys.argv[3]
    
    page_range = range(start_page, end_page + 1)
    print(f"Processing pages {start_page} to {end_page}")
    print(f"Output: {output_path}")
    print()
    
    extract_text_from_images(page_range, output_path)
