from PIL import Image
from surya.foundation import FoundationPredictor
from surya.recognition import RecognitionPredictor
from surya.detection import DetectionPredictor
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
import re
import unicodedata


def has_devanagari(text):
    """Check if text contains any Devanagari characters."""
    for char in text:
        try:
            if 'DEVANAGARI' in unicodedata.name(char):
                return True
        except ValueError:
            pass
    return False


def iast_to_devanagari(iast_text):
    """Convert IAST to Devanagari."""
    # Remove subscript numbers before transliteration
    clean_iast = re.sub(r'[₀₁₂₃₄₅₆₇₈₉]', '', iast_text)
    return transliterate(clean_iast, sanscript.IAST, sanscript.DEVANAGARI)


def fix_root_prefixes(text):
    """
    Fix OCR errors where root entries are missing a prefix.
    
    Strategy 1: Look for references like [agt. svar₂] that don't match the entry var₂
    Strategy 2: Compare with neighboring entries
    """
    lines = text.split('\n')
    full_text = text
    
    # Strategy 1: Find root entries and check if they're referenced elsewhere with different prefix
    # Pattern for root entry: √ followed by optional Devanagari, then IAST
    root_pattern = re.compile(r'^(√\s*)([^\s]*\s+)?([a-zA-ZāĀīĪūŪṛṚṝṜḷḶḹḸṃṂḥḤṅṄñÑṭṬḍḌṇṆśŚṣṢ]+[₀₁₂₃₄₅₆₇₈₉]+)')
    
    for i, line in enumerate(lines):
        match = root_pattern.match(line)
        if match:
            prefix = match.group(1)  # √ 
            middle = match.group(2) or ''  # Optional Devanagari + space
            iast_with_num = match.group(3)  # e.g., var₂
            
            # Extract the subscript number
            num_match = re.search(r'[₀₁₂₃₄₅₆₇₈₉]+$', iast_with_num)
            if num_match:
                subscript = num_match.group(0)
                iast_base = iast_with_num[:-len(subscript)]
                
                # Look for references to this entry in the full text
                # Pattern: [agt. X₂], [act. X₂], etc. where X is potentially different
                ref_pattern = re.compile(r'\[(?:agt|act|ppr|pfp|pp|ca|dés)\.\s*([a-zA-ZāĀīĪūŪṛṚṝṜḷḶḹḸṃṂḥḤṅṄñÑṭṬḍḌṇṆśŚṣṢ]+)' + re.escape(subscript) + r'\]')
                
                for ref_match in ref_pattern.finditer(full_text):
                    ref_base = ref_match.group(1)
                    
                    # Check if reference has a longer prefix than our entry
                    if ref_base != iast_base and ref_base.endswith(iast_base):
                        missing_prefix = ref_base[:-len(iast_base)]
                        correct_iast = missing_prefix + iast_with_num
                        
                        print(f"  Fixing: {iast_with_num} -> {correct_iast} (found reference [{ref_match.group(0)}])")
                        
                        # Fix the IAST
                        lines[i] = lines[i].replace(iast_with_num, correct_iast, 1)
                        
                        # Fix the Devanagari if present
                        if has_devanagari(middle):
                            wrong_dev = middle.strip()
                            correct_dev = iast_to_devanagari(ref_base)
                            lines[i] = lines[i].replace(wrong_dev, correct_dev, 1)
                        
                        break  # Found a fix, move to next line
    
    return '\n'.join(lines)


def add_missing_devanagari(text):
    """
    Add Devanagari transliteration where it's missing.
    Only for root entries (√) that sometimes lose Devanagari.
    
    Pattern: √ IAST_word [...] v. -> √ देवनागरी IAST_word [...] v.
    """
    lines = text.split('\n')
    result_lines = []
    
    # IAST pattern
    iast_chars = r'[a-zA-ZāĀīĪūŪṛṚṝṜḷḶḹḸṃṂḥḤṅṄñÑṭṬḍḌṇṆśŚṣṢ₀₁₂₃₄₅₆₇₈₉]+'
    
    # Pattern for root entries without Devanagari: √ followed by IAST word
    # Allow optional content between IAST word and v./var.
    root_pattern = re.compile(
        r'^(√\s*)(' + iast_chars + r')(\s.*?\s*(?:v\.|var\.))'
    )
    
    for line in lines:
        # Check if line already has Devanagari
        if has_devanagari(line):
            result_lines.append(line)
            continue
        
        # Try to match root pattern: √ dhāv₁ v. [1] or √ var₂ [relié à sur] v.
        root_match = root_pattern.match(line)
        if root_match:
            prefix = root_match.group(1)  # √ 
            iast_word = root_match.group(2)  # dhāv₁ or var₂
            middle_and_v = root_match.group(3)  # " v." or " [relié à sur] v."
            rest = line[root_match.end():]
            
            devanagari = iast_to_devanagari(iast_word)
            new_line = f"{prefix}{devanagari} {iast_word}{middle_and_v}{rest}"
            result_lines.append(new_line)
            continue
        
        result_lines.append(line)
    
    return '\n'.join(result_lines)


def convert_math_to_unicode(text):
    r"""
    Convert LaTeX math notation from Surya to proper Unicode IAST.
    Examples:
      <math>dh\bar{a}r\bar{a}_2</math> -> dharaa2 (subscript)
      <math>\sqrt{\,}</math> -> root symbol
      <math>dh\bar{\imath}_1</math> -> dhii1 (subscript)
    """
    # First, extract content from <math> tags and convert
    def convert_math_content(match):
        content = match.group(1)
        
        # Convert macron (bar) notation
        content = re.sub(r'\\bar\{a\}', 'ā', content)
        content = re.sub(r'\\bar\{A\}', 'Ā', content)
        content = re.sub(r'\\bar\{i\}', 'ī', content)
        content = re.sub(r'\\bar\{I\}', 'Ī', content)
        content = re.sub(r'\\bar\{\\imath\}', 'ī', content)
        content = re.sub(r'\\bar\{u\}', 'ū', content)
        content = re.sub(r'\\bar\{U\}', 'Ū', content)
        
        # Convert subscripts
        content = re.sub(r'_0', '₀', content)
        content = re.sub(r'_1', '₁', content)
        content = re.sub(r'_2', '₂', content)
        content = re.sub(r'_3', '₃', content)
        content = re.sub(r'_4', '₄', content)
        content = re.sub(r'_5', '₅', content)
        content = re.sub(r'_6', '₆', content)
        content = re.sub(r'_7', '₇', content)
        content = re.sub(r'_8', '₈', content)
        content = re.sub(r'_9', '₉', content)
        
        # Convert square root
        content = re.sub(r'\\sqrt\{[^}]*\}', '√', content)
        content = re.sub(r'\\sqrt', '√', content)
        
        # Remove remaining LaTeX artifacts
        content = re.sub(r'\\[a-zA-Z]+', '', content)  # Remove remaining commands
        content = re.sub(r'[{}]', '', content)  # Remove braces
        
        return content
    
    # Process <math>...</math> tags
    text = re.sub(r'<math>(.*?)</math>', convert_math_content, text)
    
    # Also handle \(...\) notation (sometimes used)
    text = re.sub(r'\\\((.*?)\\\)', convert_math_content, text)
    
    # Convert <sup> and <sub> tags to Unicode
    sup_map = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', 
               '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', 'e': 'ᵉ'}
    sub_map = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
               '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'}
    
    def convert_sup(match):
        content = match.group(1)
        return ''.join(sup_map.get(c, c) for c in content)
    
    def convert_sub(match):
        content = match.group(1)
        return ''.join(sub_map.get(c, c) for c in content)
    
    text = re.sub(r'<sup>(.*?)</sup>', convert_sup, text)
    text = re.sub(r'<sub>(.*?)</sub>', convert_sub, text)
    
    # Convert any digit that follows a letter to subscript
    def convert_digit_after_letter(match):
        letter = match.group(1)
        digit = match.group(2)
        subscript = sub_map.get(digit, digit)
        return letter + subscript
    
    # Match any letter followed by a digit
    text = re.sub(r'([a-zA-ZāĀīĪūŪṛṚṝṜḷḶḹḸṃṂḥḤṅṄñÑṭṬḍḌṇṆśŚṣṢ\u0900-\u097F])([0-9])', 
                  convert_digit_after_letter, text)
    
    # Fix common OCR misreads: dotless i (ı) at end of word often is subscript 1
    # Pattern: IAST word ending with ı followed by space/bracket/pipe
    text = re.sub(r'([a-zA-ZāĀīĪūŪṛṚṝṜḷḶḹḸṃṂḥḤṅṄñÑṭṬḍḌṇṆśŚṣṢ])ı([\s\|\[\]])', 
                  r'\g<1>₁\2', text)
    
    return text


def clean_page_output(text):
    """
    Clean up the page output:
    - Remove standalone page numbers (lines with just digits)
    """
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        # Skip lines that are just numbers (page numbers)
        if stripped and stripped.isdigit():
            continue
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def extract_text_from_image(image_path):
    """Extract text from an image using Surya OCR."""
    image = Image.open(image_path)
    
    # Initialize predictors (models download on first run)
    foundation_predictor = FoundationPredictor()
    det_predictor = DetectionPredictor()
    rec_predictor = RecognitionPredictor(foundation_predictor)
    
    # Run detection and recognition
    predictions = rec_predictor([image], det_predictor=det_predictor)
    
    # Extract text lines in reading order
    lines = []
    for page_pred in predictions:
        for line in page_pred.text_lines:
            lines.append(line.text)
    
    return "\n".join(lines)


def extract_text_from_images(page_range, output_path):
    """Extract text from multiple page images."""
    # Initialize predictors once for efficiency
    foundation_predictor = FoundationPredictor()
    det_predictor = DetectionPredictor()
    rec_predictor = RecognitionPredictor(foundation_predictor)
    
    all_text = []
    
    for page_num in page_range:
        image_path = f'pages/page_{page_num}.png'
        print(f"Processing {image_path}...")
        
        image = Image.open(image_path)
        
        # Get image dimensions for column splitting
        width, height = image.size
        
        # Split into left and right columns
        left_col = image.crop((0, 0, width // 2, height))
        right_col = image.crop((width // 2, 0, width, height))
        
        # Process both columns
        # math_mode=False prevents IAST diacritics from being converted to LaTeX
        predictions = rec_predictor([left_col, right_col], det_predictor=det_predictor, math_mode=False)
        
        # Extract text from left column
        page_text = ""
        for line in predictions[0].text_lines:
            page_text += line.text + "\n"
        
        page_text += "\n"  # Separator between columns
        
        # Extract text from right column
        for line in predictions[1].text_lines:
            page_text += line.text + "\n"
        
        # Convert LaTeX math notation to Unicode
        page_text = convert_math_to_unicode(page_text)
        
        # Fix root entries with wrong prefixes (e.g., var₂ -> svar₂)
        page_text = fix_root_prefixes(page_text)
        
        # Add missing Devanagari (especially for root entries)
        page_text = add_missing_devanagari(page_text)
        
        # Clean up page numbers and artifacts
        page_text = clean_page_output(page_text)
        
        all_text.append(page_text)
        print(f"Processed page {page_num}")
    
    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_text))
    
    print(f"Text extracted and saved to {output_path}")


# Process pages
if __name__ == "__main__":
    # Process pages 1-950
    page_range = range(1, 951)
    output_path = "extracted_dictionary_surya.txt"
    
    extract_text_from_images(page_range, output_path)
