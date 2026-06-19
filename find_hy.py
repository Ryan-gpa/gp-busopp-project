import pdfplumber
with pdfplumber.open("NVU Half YEar Report.pdf") as pdf:
    print("total pages", len(pdf.pages))
    for i,page in enumerate(pdf.pages):
        t = (page.extract_text() or "")
        for key in ["STATEMENT OF PROFIT","STATEMENT OF FINANCIAL POSITION","STATEMENT OF CASH FLOWS","STATEMENT OF CHANGES IN EQUITY","SEGMENT","per share","Appendix 4D","Results for announcement"]:
            if key.upper() in t.upper():
                print("PAGE", i+1, "->", key)
