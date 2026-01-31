from google.cloud import vision
from PIL import Image
import io
import os


def extract_text_from_image(image_path):
    """Extract text from an image using Google Cloud Vision API."""
    client = vision.ImageAnnotatorClient()
    
    with open(image_path, 'rb') as image_file:
        content = image_file.read()
    
    image = vision.Image(content=content)
    
    # Use document_text_detection for better handling of dense text/documents
    response = client.document_text_detection(image=image)
    
    if response.error.message:
        raise Exception(f"API Error: {response.error.message}")
    
    return response.full_text_annotation.text


def extract_text_from_image_columns(image_path):
    """Extract text from an image, processing left and right columns separately."""
    client = vision.ImageAnnotatorClient()
    
    # Open and split image into columns
    image = Image.open(image_path)
    width, height = image.size
    
    left_col = image.crop((0, 0, width // 2, height))
    right_col = image.crop((width // 2, 0, width, height))
    
    # Language hints for Sanskrit (Devanagari), Hindi, and French
    image_context = vision.ImageContext(
        language_hints=["sa", "hi", "fr"]  # Sanskrit, Hindi, French
    )
    
    results = []
    
    for col_name, col_image in [("left", left_col), ("right", right_col)]:
        # Convert PIL image to bytes
        img_byte_arr = io.BytesIO()
        col_image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        vision_image = vision.Image(content=img_byte_arr)
        
        # Use document_text_detection with language hints for better OCR
        response = client.document_text_detection(
            image=vision_image,
            image_context=image_context
        )
        
        if response.error.message:
            raise Exception(f"API Error for {col_name} column: {response.error.message}")
        
        text = response.full_text_annotation.text if response.full_text_annotation.text else ""
        results.append(text)
    
    return results[0], results[1]


def extract_text_full_page(image_path, use_text_detection=False, lang_hints=None):
    """Extract text from full page without splitting columns."""
    client = vision.ImageAnnotatorClient()
    
    with open(image_path, 'rb') as image_file:
        content = image_file.read()
    
    vision_image = vision.Image(content=content)
    
    # Language hints
    if lang_hints is None:
        lang_hints = ["hi", "sa", "fr"]  # Hindi first, then Sanskrit, French
    
    # Only create image_context if we have language hints
    image_context = None
    if lang_hints:
        image_context = vision.ImageContext(
            language_hints=lang_hints
        )
    
    if use_text_detection:
        # Try text_detection instead of document_text_detection
        if image_context:
            response = client.text_detection(image=vision_image, image_context=image_context)
        else:
            response = client.text_detection(image=vision_image)
        
        if response.error.message:
            raise Exception(f"API Error: {response.error.message}")
        
        # text_detection returns text in text_annotations[0].description
        if response.text_annotations:
            return response.text_annotations[0].description
        return ""
    else:
        # document_text_detection
        if image_context:
            response = client.document_text_detection(image=vision_image, image_context=image_context)
        else:
            response = client.document_text_detection(image=vision_image)
        
        if response.error.message:
            raise Exception(f"API Error: {response.error.message}")
        
        return response.full_text_annotation.text


def run_ocr_columns(image_path):
    """Run Google Vision OCR on an image with column splitting, return combined text."""
    left_text, right_text = extract_text_from_image_columns(image_path)
    return left_text + "\n\n" + right_text


def extract_text_from_images(page_range, output_path, use_columns=True):
    """Extract text from multiple page images."""
    all_text = []
    
    for page_num in page_range:
        image_path = f'pages/page_{page_num}.png'
        print(f"Processing {image_path}...")
        
        try:
            if use_columns:
                left_text, right_text = extract_text_from_image_columns(image_path)
                page_text = f"--- Page {page_num} ---\n"
                page_text += left_text + "\n\n"
                page_text += right_text
            else:
                # Full page mode
                full_text = extract_text_full_page(image_path)
                page_text = f"--- Page {page_num} ---\n"
                page_text += full_text
            
            all_text.append(page_text)
            print(f"Processed page {page_num}")
            
        except Exception as e:
            print(f"Error processing page {page_num}: {e}")
            all_text.append(f"--- Page {page_num} ---\nERROR: {e}\n")
    
    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_text))
    
    print(f"Text extracted and saved to {output_path}")


# Test on a single page
if __name__ == "__main__":
    # Check for credentials
    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        print("=" * 60)
        print("SETUP REQUIRED: Google Cloud Vision API credentials")
        print("=" * 60)
        print()
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project (or select existing)")
        print("3. Enable 'Cloud Vision API' for your project")
        print("4. Go to 'IAM & Admin' > 'Service Accounts'")
        print("5. Create a service account with 'Cloud Vision API User' role")
        print("6. Create and download a JSON key for the service account")
        print("7. Set the environment variable:")
        print()
        print("   export GOOGLE_APPLICATION_CREDENTIALS='/path/to/your/key.json'")
        print()
        print("Then run this script again.")
        print("=" * 60)
        exit(1)
    
    # Test on page 492
    image_path = 'pages/page_492.png'
    
    print("=" * 60)
    print("Testing different Google Vision configurations for Devanagari")
    print("=" * 60)
    
    # Test 1: text_detection with Hindi only
    print("\n1. text_detection with Hindi hint only...")
    try:
        text = extract_text_full_page(image_path, use_text_detection=True, lang_hints=["hi"])
        with open("test_gv_text_detection_hi.txt", "w", encoding="utf-8") as f:
            f.write(text)
        # Show first 500 chars
        print(f"   First 500 chars:\n   {text[:500]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: text_detection with no hints (auto-detect)
    print("\n2. text_detection with NO language hints (auto-detect)...")
    try:
        text = extract_text_full_page(image_path, use_text_detection=True, lang_hints=[])
        with open("test_gv_text_detection_auto.txt", "w", encoding="utf-8") as f:
            f.write(text)
        print(f"   First 500 chars:\n   {text[:500]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: document_text_detection with Hindi only
    print("\n3. document_text_detection with Hindi hint only...")
    try:
        text = extract_text_full_page(image_path, use_text_detection=False, lang_hints=["hi"])
        with open("test_gv_doc_detection_hi.txt", "w", encoding="utf-8") as f:
            f.write(text)
        print(f"   First 500 chars:\n   {text[:500]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 60)
    print("Check the output files for full results")
    print("=" * 60)
