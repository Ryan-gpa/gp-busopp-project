You are going to perform financial modelling and reporting analysis for Nanoveu Limited (ASX: NVU). All source files are in the working folder. Complete all tasks below in sequence.

---

## CONTEXT

NVU is an ASX-listed technology company with three divisions:
- EMASS (semiconductor/Edge AI) — acquired 18 March 2025 as an asset acquisition under AASB 2, consideration $10.47M
- EyeFly3D (3D display film)
- Nanoshield (nano-coating)

NVU reports in full Australian dollars (not $'000). Financial year end is 31 December.

The "Pinnacle" documents are Accurri-software-produced template reports showing the correct ASX format for interim and annual reports. Pinnacle Listed Comprehensive Limited/Interim Limited is a fictional template company — not NVU. Differences may simply reflect that NVU doesn't operate in that space, not a reporting deficiency.

---

## SOURCE FILES (all in working folder)

- `NVU Annual Report.pdf` — FY ended 31 December 2025 (Appendix 4E)
- `NVU Half YEar Report.pdf` — HY ended 30 June 2025 (Appendix 4D)
- `Pinnacle Listed Comprehensive Interim Limited - Interim Report - 30062026.docx` — Accurri half-year template
- `Pinnacle Listed Comprehensive Limited - Annual Report - 30062026.docx` — Accurri annual report template

---

## TASK 1 — Extract NVU financials from both PDFs

Use `pdftotext -layout` to extract text from both PDFs. Parse and record every line item from:
- Statement of Profit or Loss and OCI
- Statement of Financial Position
- Statement of Cash Flows
- Statement of Changes in Equity
- Segment data
- EPS

Do this for BOTH the Annual Report (FY2025) and the Half Year Report (HY ended 30 June 2025).

Derive H2 2025 figures mathematically: H2 = FY2025 minus H1 2025.

---

## TASK 2 — Build Excel financial model

Create `NVU_Financial_Model.xlsx` with these sheets:

1. **P&L** — Revenue, COGS, Gross Profit, all operating expenses, EBIT, finance items, net loss. Columns: H1 2025 | H2 2025 (derived) | FY 2025. All figures in actual $.
2. **Balance Sheet** — All asset and liability line items. Columns: 30 Jun 2025 | 31 Dec 2025.
3. **Cash Flow** — Operating / Investing / Financing. Columns: H1 2025 | H2 2025 | FY 2025.
4. **Segments** — Revenue, EBIT/loss, assets by segment (Semiconductor, EyeFly3D, Nanoshield, Corporate) for HY and FY.
5. **KPIs** — Gross margin %, operating cash burn per month, cash runway, net assets per share, revenue growth.
6. **Ratios** — Current ratio, cash ratio, asset turnover, loss per share, cash burn rate.

Formatting requirements:
- Blue text = hardcoded inputs
- Black text = formulas
- Currency in $#,##0 format; zeros show as "-"
- Negative numbers in parentheses
- Zero formula errors (#REF!, #DIV/0! etc.)
- Run `python scripts/recalc.py NVU_Financial_Model.xlsx` to verify

---

## TASK 3 — Half-year differences report

Read the Pinnacle Interim Report docx using:

```python
python3 -c "
import zipfile, re
with zipfile.ZipFile('Pinnacle Listed Comprehensive Interim Limited - Interim Report - 30062026.docx') as z:
    with z.open('word/document.xml') as f:
        xml = f.read().decode('utf-8')
text = re.sub(r'<[^>]+>', ' ', xml)
text = re.sub(r'\s+', ' ', text)
print(text)
"
```

Compare every line item in the Pinnacle interim template against NVU's HY 2025 figures across:
- Appendix 4D cover (sections 1–9)
- Statement of P&L and OCI
- Statement of Financial Position
- Statement of Cash Flows
- Notes to financial statements

Produce `NVU_vs_Accurri_Differences.docx` — a formatted Word document with colour-coded comparison tables using these status labels:
- **NOT IN NVU** (red) = Accurri line item absent from NVU filing
- **NOT IN TEMPLATE** (amber) = NVU line item absent from Accurri format
- **NIL (LOSS CO.)** (amber) = NVU figure is nil because it's a loss-making entity
- **STRUCTURALLY DIFFERENT** (red) = Both have something but different classification/format
- **BOTH PRESENT** (green) = Both disclose; figures differ by scale/nature

Include a summary section listing: (A) items in template not in NVU due to different business model, (B) genuine disclosure gaps NVU should address, (C) NVU-specific items the template doesn't anticipate.

---

## TASK 4 — Annual report differences report

Read the Pinnacle Annual Report docx the same way as Task 3.

Compare against NVU's FY2025 annual figures across all sections:
- Appendix 4E cover
- All four primary financial statements
- Directors' report and remuneration report
- All notes to financial statements
- Consolidated entity disclosure statement
- Shareholder information

Produce `Annual_Differences.docx` — same colour-coded format as Task 3, covering:
1. Appendix 4E cover page comparison
2. P&L and OCI line by line
3. Balance sheet line by line
4. Cash flows line by line
5. Directors' report / remuneration report sections
6. Notes — structural gaps
7. Summary of gaps by category (A/B/C as above)

Note throughout: where Pinnacle has items NVU doesn't, flag clearly whether it's because NVU doesn't operate in that space (not a gap) vs a genuine disclosure deficiency.

---

## DELIVERABLES

Save all outputs to the working folder:
1. `NVU_Financial_Model.xlsx` — zero formula errors, verified by recalc
2. `NVU_vs_Accurri_Differences.docx` — half-year comparison
3. `Annual_Differences.docx` — annual comparison

Use `npm install docx` (local, not -g) and build Word docs with the `docx` npm package in JavaScript. Do not use python-docx.

Important notes:
- NVU reports in full dollars; Pinnacle template uses $'000 — flag this scale difference
- NVU's financial year ends 31 December; Pinnacle's ends 30 June — different year-ends
- EMASS was an asset acquisition under AASB 2 (not a business combination under AASB 3) — the Accurri template only covers AASB 3 format
- NVU has NCI running at a deficit (Fullveu HK 49% minority interest absorbing losses)
- NVU has never paid dividends and has no bank borrowings (equity-funded)
