import pdfplumber
with pdfplumber.open("NVU Annual Report.pdf") as pdf:
    for i,page in enumerate(pdf.pages):
        t = (page.extract_text() or "")
        if ("fully paid" in t.lower() or "ordinary shares" in t.lower()) and ("ISSUED CAPITAL" in t.upper() or "Number" in t):
            print("PAGE", i+1)
