from pdf2image import convert_from_path
import os

# Define the input PDF file
inputFile = 'dictionary.pdf'

# Ensure the output directory exists
output_dir = './pages'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Get the total number of pages
pdf_info = convert_from_path(inputFile, 300, first_page=0, last_page=1)  # Just to get the info
total_pages = len(pdf_info)  # Assumes this call provides the correct number of total pages
del pdf_info  # Cleanup


# Function to process a batch of pages
def process_pages(start_page, dpi=300, batch_size=5):
    page_number = start_page  # Start from specified page number

    # Continue until all pages are processed
    while True:
        # Convert to the end of the document if the batch overflows
        pages = convert_from_path(inputFile, dpi, first_page=page_number, last_page=(page_number + batch_size + 1))

        # Break if no more pages are returned
        if not pages:
            break

        # Save each page
        for i, page in enumerate(pages, start=page_number):
            file_path = os.path.join(output_dir, f'page_{i}.png')
            page.save(file_path, 'PNG')
            print(f'Saved page {i} to {file_path}')

        # Update the page number
        page_number += len(pages)


# Start processing from page 12
process_pages(start_page=12)
