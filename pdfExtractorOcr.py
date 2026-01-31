import pytesseract
from pytesseract import Output
import cv2

# Absolute path to the Tesseract executable
inputFile = 'dictionary.pdf'
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

def parse_from_images():
    text = ""
    for i in range(492, 493):
        image_path = f'pages/page_{i}.png'

        # Preprocess the image
        image = cv2.imread(image_path)

        # Get dimensions of the image
        height, width = image.shape[:2]

        # Assume the page has two columns and crop each column; adjust as necessary
        left_col = image[0:height, 0:int(width / 2)]
        right_col = image[0:height, int(width / 2):width]

        # Process left column
        left_text = perform_ocr(left_col)

        # Process right column
        right_text = perform_ocr(right_col)

        text += left_text + '\n' + right_text

        print("Processed page", i)

    return text

def preprocess_for_ocr(image, scale=4):
    # Upscale to help small glyphs (e.g., superscripts) and thin strokes
    enlarged = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)

    # Local contrast boost for faint text
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Denoise then sharpen to make thin strokes more distinct
    gray = cv2.medianBlur(gray, 3)
    blurred = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharpened = cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)

    # Binarize with Otsu, then close small gaps (helps small diacritics/superscripts)
    _, thresh = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    return closed

def perform_ocr(image):
    base_config = (
        r'--oem 1 --psm 6 '
        r'-c user_defined_dpi=300 '
        r'-c preserve_interword_spaces=1 '
        r'-c textord_min_linesize=1.0 '
        r'load_freq_dawg=false'
    )
    lang = 'san-chandas-float+san-siddhanta-float+IAST+fra'
    digit_config = r'--oem 1 --psm 10 -c tessedit_char_whitelist=0123456789'

    processed_img = preprocess_for_ocr(image, scale=4)
    data = pytesseract.image_to_data(processed_img, lang=lang, config=base_config, output_type=Output.DICT)

    # Characters that Tesseract often confuses with subscript digits
    MISREAD_DIGIT_CHARS = {'r', 'i', 'l', '|', 'I', ';'}

    def extract_digit_from_roi(roi):
        if roi.size == 0:
            return ""
        # Enlarge and clean for better digit recognition
        enlarged = cv2.resize(roi, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        _, thr = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Try multiple configs to improve 1 vs 7 distinction
        for config in [digit_config, r'--oem 1 --psm 10 -c tessedit_char_whitelist=12']:
            raw = pytesseract.image_to_string(thr, config=config)
            digits = "".join(ch for ch in raw if ch.isdigit())
            if digits:
                return digits[:1]
        return ""

    def rescue_digit_for_iast_word(idx, word):
        """
        For the IAST headword (2nd word after Sanskrit):
        1. Check if word ends with a misread digit char (like 'r')
        2. Look for actual digit in the END of the word's bounding box (the digit is inside)
        3. Return corrected word
        """
        x = data["left"][idx]
        y = data["top"][idx]
        w = data["width"][idx]
        h = data["height"][idx]
        img_h, img_w = processed_img.shape[:2]

        # Check if word already has a digit
        if any(ch.isdigit() for ch in word):
            return word

        # Check if word ends with a char that might be a misread digit
        trailing_misread = word and word[-1] in MISREAD_DIGIT_CHARS
        
        if not trailing_misread:
            return word

        # The digit is INSIDE the word bounding box at the end (misread as 'r')
        # Look at the rightmost ~20% of the word box
        digit_width = max(10, int(w * 0.25))
        rx1 = max(0, x + w - digit_width)
        rx2 = min(img_w, x + w + 5)  # small buffer after word
        ry1 = max(0, y)
        ry2 = min(img_h, y + h)
        
        digit = extract_digit_from_roi(processed_img[ry1:ry2, rx1:rx2])

        if digit:
            # Strip the misread char and append correct digit
            return word[:-1] + digit
        
        return word

    lines = []
    current_key = None
    current_words = []
    word_positions = []  # Track word indices for digit rescue

    for i, word in enumerate(data["text"]):
        if not word or not word.strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if key != current_key:
            if current_words:
                lines.append(" ".join(current_words))
            current_words = []
            word_positions = []
            current_key = key

        word_positions.append(i)
        
        # Only rescue digit for the 2nd word (IAST headword after Sanskrit)
        if len(current_words) == 1:
            word = rescue_digit_for_iast_word(i, word)

        current_words.append(word)

    if current_words:
        lines.append(" ".join(current_words))

    return "\n".join(lines)

text = parse_from_images()
with open('extracted_text_ocr_iast_test.txt', "w", encoding="utf-8") as f:
    f.write(text)
