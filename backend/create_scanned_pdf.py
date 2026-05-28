from PIL import Image, ImageDraw
import fitz
import os

print("1. Creating an image with text...")
# Create a white image
img = Image.new('RGB', (800, 600), color=(255, 255, 255))
d = ImageDraw.Draw(img)

# Draw some text (this is purely pixels, no text layer)
text = "CONFIDENTIAL DOCUMENT\n\nProject: TITAN\nSecret Code: 8492-AX99-BETA\n\nDo not share this document."
d.text((50, 50), text, fill=(0, 0, 0))

# Save image
img.save("test_scanned.png")

print("2. Converting image to PDF...")
# Convert image to PDF
pdf_bytes = fitz.open("test_scanned.png").convert_to_pdf()
pdf_doc = fitz.open("pdf", pdf_bytes)
pdf_doc.save("test_scanned.pdf")
pdf_doc.close()

print("3. Testing PyMuPDF text extraction on the scanned PDF...")
# Try to extract text using the same code our endpoint uses
doc = fitz.open("test_scanned.pdf")
text_extracted = ""
for page in doc:
    text_extracted += page.get_text("text").strip()

print(f"Extracted characters: {len(text_extracted)}")
if len(text_extracted) == 0:
    print("WARNING: PyMuPDF could not read the text because it is an image (no OCR installed).")
else:
    print("SUCCESS: Text was extracted!")
    print(text_extracted)
