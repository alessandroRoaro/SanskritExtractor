"""
Hybrid Sanskrit Dictionary Extractor
- Uses Google Cloud Vision for OCR (fast, perfect IAST)
- Post-processes to add Devanagari transliteration to headwords
"""

from google.cloud import vision
from PIL import Image
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
import cv2
import numpy as np
import io
import os
import re


def preprocess_for_ocr(pil_image, scale=2):
    """
    Preprocess image to improve OCR of subscripts and small diacritics.
    Similar to Tesseract preprocessing but lighter for Google Vision.
    """
    # Convert PIL to OpenCV
    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    
    # Upscale to help small glyphs (subscripts, diacritics)
    enlarged = cv2.resize(cv_image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # Convert to grayscale
    gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)
    
    # Local contrast boost (CLAHE) for faint text
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    
    # Sharpen to make thin strokes more distinct
    blurred = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharpened = cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)
    
    # Convert back to RGB for Google Vision
    result = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(result)


def extract_text_from_columns(image_path, use_preprocessing=True, scale=2):
    """Extract text from an image, processing left and right columns separately."""
    client = vision.ImageAnnotatorClient()
    
    # Open and split image into columns
    image = Image.open(image_path)
    width, height = image.size
    
    left_col = image.crop((0, 0, width // 2, height))
    right_col = image.crop((width // 2, 0, width, height))
    
    # Apply preprocessing if enabled
    if use_preprocessing:
        left_col = preprocess_for_ocr(left_col, scale=scale)
        right_col = preprocess_for_ocr(right_col, scale=scale)
    
    results = []
    
    for col_image in [left_col, right_col]:
        # Convert PIL image to bytes
        img_byte_arr = io.BytesIO()
        col_image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        vision_image = vision.Image(content=img_byte_arr)
        
        # Use document_text_detection for dense text
        response = client.document_text_detection(image=vision_image)
        
        if response.error.message:
            raise Exception(f"API Error: {response.error.message}")
        
        text = response.full_text_annotation.text if response.full_text_annotation.text else ""
        results.append(text)
    
    return results[0], results[1]


def iast_to_devanagari(iast_text):
    """Convert IAST text to Devanagari."""
    return transliterate(iast_text, sanscript.IAST, sanscript.DEVANAGARI)


def fix_subscripts_and_symbols(text):
    """
    Post-process OCR output to fix:
    1. Regular numbers that should be subscripts (₁₂₃ etc.)
    2. Corrupted prefix symbols
    """
    
    # Map regular digits to subscript digits
    subscript_map = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')
    
    # IAST characters for pattern matching
    iast_chars = r"[a-zA-ZāĀīĪūŪṛṚṝṜḷḶḹḸṃṂḥḤṅṄñÑṭṬḍḌṇṆśŚṣṢ]"
    
    # Pattern 1: Numbers at end of IAST words in brackets [dhāv2] → [dhāv₂]
    # Matches: [word + number] or [* word + number]
    def fix_bracket_subscripts(match):
        content = match.group(1)
        # Convert trailing digits to subscripts
        result = re.sub(r'(' + iast_chars + r'+)([0-9]+)(?=\]|$)', 
                       lambda m: m.group(1) + m.group(2).translate(subscript_map),
                       content)
        return '[' + result + ']'
    
    text = re.sub(r'\[([^\]]+)\]', fix_bracket_subscripts, text)
    
    # Pattern 2: Numbers at end of headwords followed by space/bracket
    # dhāvat2 [ppr. → dhāvat₂ [ppr.
    # dhāvana2 [act. → dhāvana₂ [act.
    text = re.sub(
        r'(' + iast_chars + r'+)([0-9]+)(\s+\[)',
        lambda m: m.group(1) + m.group(2).translate(subscript_map) + m.group(3),
        text
    )
    
    # Pattern 3: Numbers at end of headwords before grammar markers
    # dhāv2 v. → dhāv₂ v.
    text = re.sub(
        r'(' + iast_chars + r'+)([0-9]+)(\s+(?:v\.|a\.|m\.|n\.|f\.|ifc\.|ind\.))',
        lambda m: m.group(1) + m.group(2).translate(subscript_map) + m.group(3),
        text
    )
    
    # Pattern 4: Clean up corrupted prefix symbols
    # These appear to be dictionary markers that get mangled
    # fч, fa, fur, Fч → clean prefix markers
    # √ч, √¶¶ → √ (square root for verb roots)
    
    # Fix corrupted √ (verb root marker)
    text = re.sub(r'√[чц¶]+\s*', '√', text)
    text = re.sub(r'V(?=धाव)', '√', text)  # V followed by Devanagari dhāv
    
    # Fix corrupted entry markers (fч, fa, fur, Fч seem to be entry type indicators)
    # These might be intended to be specific symbols - leaving as-is for now
    # but cleaning obvious corruptions
    text = re.sub(r'ч¶\s+', '', text)  # Remove noise before entries
    
    return text


def add_devanagari_to_headwords(text):
    """
    Add Devanagari transliteration to IAST headwords in dictionary entries.
    
    Headwords are identified by:
    - IAST word followed by [etymology] in brackets
    - IAST word followed by grammar markers (a. m. n. f., v., etc.)
    - Verb roots with √ prefix
    """
    
    # IAST characters including diacritics
    iast_chars = r"[a-zA-ZāĀīĪūŪṛṚṝṜḷḶḹḸṃṂḥḤṅṄñÑṭṬḍḌṇṆśŚṣṢ]"
    
    # Pattern 1: Headword followed by [etymology] - most reliable
    # e.g., "dhārāgṛha [gṛha]", "dhārtarāṣṭra [* dhṛtarāṣṭra]"
    pattern_etymology = re.compile(
        r'^'                                    # Start of line
        r'([√¶¯"¿\s]*)'                        # Optional prefix symbols
        r'(' + iast_chars + r'+)'              # IAST headword
        r'([₁₂₃₄₅₆₇₈₉₀]*)'                    # Optional subscript numbers
        r'(\s+\[)',                             # Space then [ bracket
        re.MULTILINE
    )
    
    # Pattern 2: Headword followed by grammar markers (a. m. n. f., v., ifc., ind., etc.)
    # e.g., "dhiṣaṇa a. m. n. f.", "dhik ind."
    pattern_grammar = re.compile(
        r'^'
        r'([√¶¯"¿\s]*)'
        r'(' + iast_chars + r'+)'
        r'([₁₂₃₄₅₆₇₈₉₀]*)'
        r'(\s+(?:a\.\s*m\.\s*n\.\s*f\.|v\.\s*\[|ifc\.\s|ind\.\s|m\.\s|f\.\s|n\.\s))',
        re.MULTILINE
    )
    
    # Common French words to skip (even with diacritics)
    skip_words = {'a', 'à', 'au', 'de', 'du', 'en', 'et', 'f', 'il', 'la', 'le', 'les', 
                  'm', 'n', 'np', 'ou', 'pl', 'pp', 'pr', 'se', 'un', 'une', 'v', 'cf',
                  'mod', 'myth', 'phil', 'pkt', 'soc', 'syn', 'véd', 'lit', 'ifc', 'iic',
                  'abs', 'acc', 'act', 'agt', 'ca', 'dés', 'excl', 'g', 'gr', 'ind',
                  'patr', 'pf', 'pfp', 'ppr', 'r', 'super', 'fч', 'fa', 'fur', 'Fч',
                  'hã', 'SOC'}
    
    def replace_headword(match):
        prefix = match.group(1)
        headword = match.group(2)
        subscript = match.group(3)
        suffix = match.group(4)
        
        if headword.lower() in skip_words:
            return match.group(0)
        
        # Must have IAST diacritics OR be a reasonable length Sanskrit word
        has_diacritics = any(c in headword for c in 'āīūṛṝḷḹṃḥṅñṭḍṇśṣĀĪŪṚṜḶḸṂḤṄÑṬḌṆŚṢ')
        
        # Skip short words without diacritics (likely French/abbreviations)
        if not has_diacritics and len(headword) < 5:
            return match.group(0)
        
        # Convert to Devanagari
        devanagari = iast_to_devanagari(headword)
        
        return f"{prefix}{devanagari} {headword}{subscript}{suffix}"
    
    # Apply both patterns
    result = pattern_etymology.sub(replace_headword, text)
    result = pattern_grammar.sub(replace_headword, result)
    
    return result


def extract_and_process_page(image_path, use_preprocessing=True, scale=2, add_devanagari=True):
    """Extract text from page and optionally add Devanagari to headwords."""
    left_text, right_text = extract_text_from_columns(image_path, use_preprocessing, scale)
    
    if add_devanagari:
        left_text = add_devanagari_to_headwords(left_text)
        right_text = add_devanagari_to_headwords(right_text)
    
    return left_text, right_text


def extract_text_from_images(page_range, output_path, use_preprocessing=True, scale=2, add_devanagari=True):
    """Extract text from multiple page images."""
    all_text = []
    
    for page_num in page_range:
        image_path = f'pages/page_{page_num}.png'
        print(f"Processing {image_path}...")
        
        try:
            left_text, right_text = extract_and_process_page(
                image_path, use_preprocessing, scale, add_devanagari
            )
            
            page_text = f"--- Page {page_num} ---\n"
            page_text += left_text + "\n\n"
            page_text += right_text
            
            all_text.append(page_text)
            print(f"Processed page {page_num}")
            
        except Exception as e:
            print(f"Error processing page {page_num}: {e}")
            all_text.append(f"--- Page {page_num} ---\nERROR: {e}\n")
    
    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_text))
    
    print(f"Text extracted and saved to {output_path}")


if __name__ == "__main__":
    # Check for credentials
    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        print("Set GOOGLE_APPLICATION_CREDENTIALS to your service account key JSON file")
        print("export GOOGLE_APPLICATION_CREDENTIALS='/path/to/key.json'")
        exit(1)
    
    # Test on page 492 - IAST only (no Devanagari) with preprocessing
    page_range = [492]
    
    print("=" * 60)
    print("Test 1: With preprocessing (scale=2), IAST only")
    print("=" * 60)
    extract_text_from_images(
        page_range, 
        "test_preprocessed_scale2.txt",
        use_preprocessing=True,
        scale=2,
        add_devanagari=False
    )
    
    print("\n" + "=" * 60)
    print("Test 2: Without preprocessing, IAST only")
    print("=" * 60)
    extract_text_from_images(
        page_range,
        "test_no_preprocessing.txt",
        use_preprocessing=False,
        add_devanagari=False
    )
