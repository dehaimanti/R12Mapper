import pdfplumber

def extract_text_from_pdf(pdf_file):
    full_text = []

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            # Extract regular text
            text = page.extract_text() or ""
            full_text.append(text.strip())

            # Extract tables if any
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    row_text = " | ".join([cell.strip() if cell else "" for cell in row])
                    full_text.append(row_text)

    return "\n".join([line for line in full_text if line.strip()])
