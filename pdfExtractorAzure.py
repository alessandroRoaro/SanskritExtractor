import os
import io
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential


def extract_text_from_image(image_path, endpoint, key):
    """Extract text from an image using Azure Document Intelligence."""
    client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    
    with open(image_path, "rb") as f:
        image_data = f.read()
    
    # Use the prebuilt-read model for OCR
    # Wrap bytes in BytesIO for the body parameter
    poller = client.begin_analyze_document(
        "prebuilt-read",
        body=io.BytesIO(image_data),
        content_type="application/octet-stream"
    )
    
    result = poller.result()
    
    # Extract text from all pages
    text_content = []
    for page in result.pages:
        for line in page.lines:
            text_content.append(line.content)
    
    return "\n".join(text_content)


def extract_text_from_images(page_range, output_path, endpoint, key):
    """Extract text from multiple page images."""
    client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    
    all_text = []
    
    for page_num in page_range:
        image_path = f'pages/page_{page_num}.png'
        print(f"Processing {image_path}...")
        
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            # Use the prebuilt-read model for OCR
            # Wrap bytes in BytesIO for the body parameter
            poller = client.begin_analyze_document(
                "prebuilt-read",
                body=io.BytesIO(image_data),
                content_type="application/octet-stream"
            )
            
            result = poller.result()
            
            # Extract text from all pages
            page_text = f"--- Page {page_num} ---\n"
            for page in result.pages:
                for line in page.lines:
                    page_text += line.content + "\n"
            
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
    # Check for Azure credentials
    endpoint = 'https://dictionaryparser.cognitiveservices.azure.com/'
    key = '6MBtEJkBSFYfbJGJDSj6pr04nGdSaB8FKUW012rpI3twEn3ovOgdJQQJ99CAAC5RqLJXJ3w3AAALACOGuvcI'
    
    if not endpoint or not key:
        print("=" * 60)
        print("SETUP REQUIRED: Azure Document Intelligence credentials")
        print("=" * 60)
        print()
        print("1. Go to https://portal.azure.com/")
        print("2. Create a 'Document Intelligence' resource (or 'Form Recognizer')")
        print("   - Search for 'Document Intelligence' in the marketplace")
        print("   - Select Free tier (F0) for testing")
        print("3. Once created, go to 'Keys and Endpoint'")
        print("4. Copy KEY 1 and the Endpoint")
        print("5. Set environment variables:")
        print()
        print("   export AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT='https://your-resource.cognitiveservices.azure.com/'")
        print("   export AZURE_DOCUMENT_INTELLIGENCE_KEY='your-key-here'")
        print()
        print("Then run this script again.")
        print("=" * 60)
        exit(1)
    
    # Test on page 492
    page_range = [492]
    output_path = "extracted_text_azure_test.txt"
    
    extract_text_from_images(page_range, output_path, endpoint, key)
