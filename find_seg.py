import pdfplumber
with pdfplumber.open("NVU Annual Report.pdf") as pdf:
    for i,page in enumerate(pdf.pages):
        t = page.extract_text() or ""
        if "Segment" in t and ("Segment (loss)" in t or "Reportable" in t or "EyeFly" in t):
            print("PAGE", i+1, "has segment table")
