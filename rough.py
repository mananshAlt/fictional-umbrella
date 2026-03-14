from fpdf import FPDF

# Create a PDF object
pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=12)

# Add some text to OCR later
pdf.cell(200, 10, txt="This is a sample PDF for OCR testing.", ln=1, align='C')
pdf.cell(200, 10, txt="Line 2: The quick brown fox jumps over the lazy dog.", ln=2, align='L')
pdf.cell(200, 10, txt="Line 3: 1234567890 - Special Characters: !@#$%^&*", ln=3, align='L')

# Save the PDF
pdf.output("sample_document.pdf")
print("sample_document.pdf generated successfully!")