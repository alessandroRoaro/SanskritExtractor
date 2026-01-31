from pdfminer.high_level import extract_text
import pdfplumber
import re

def extract_text_from_pdf(pdf_path, output_path):
    """Extract text from a PDF file."""
    try:
        text = ""
        # Extract text content from the PDF
        with pdfplumber.open(pdf_path) as pdf:
            for page_num in page_numbers:
                page = pdf.pages[page_num - 1]  # Adjust for zero-based index
                width = page.width

                # Define bounding boxes for left and right columns
                left_box = (0, 0, width / 2, page.height)
                right_box = (width / 2, 0, width, page.height)

                # Extract text from each column
                left_text = page.within_bbox(left_box).extract_text()
                right_text = page.within_bbox(right_box).extract_text()

                # Combine text from the same page for processing
                text += (left_text or "") + "\n"
                text += (right_text or "") + "\n"

        # Save the extracted text to a file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

        print(f"Text extracted and saved to {output_path}")
    except Exception as e:
        print(f"An error occurred while extracting text: {e}")
        return ""


# Input PDF file and output text file paths
pdf_file_path = "dictionary_short.pdf"  # Update with the path to your file
output_text_path = "extracted_text2.txt"

page_numbers = list(range(12, 33))

# Run the extraction
extract_text_from_pdf(pdf_file_path, output_text_path)