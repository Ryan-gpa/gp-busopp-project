// Annual_Differences.docx — Annual comparison
// NVU FY ended 31 December 2025 vs Pinnacle Listed Comprehensive Limited (Accurri annual template).
const fs = require("fs");
const L = require("./docx_lib.js");
const { Document, Packer, Paragraph, TextRun, AlignmentType,
        H1, H2, P, bullet, comparisonTable, legend, refTable, titlePage } = L;

const children = [];

titlePage(
  "NVU vs Accurri — Annual Differences",
  "Nanoveu Limited (ASX: NVU) — Appendix 4E & Annual Financial Report",
  ["NVU year ended 31 December 2025  vs  Pinnacle Listed Comprehensive Limited (Accurri template)",
   "Prepared 17 June 2026",
   "All NVU figures in full Australian dollars; all template figures in $'000"]
).forEach(p => children.push(p));

children.push(new Paragraph({ pageBreakBefore: true, children: [] }));

children.push(H1("1.  Purpose, scope and reading notes"));
children.push(P("This document compares the Accurri-produced Pinnacle annual template (the correct ASX Appendix 4E / annual report format) against Nanoveu Limited's audited annual report for the year ended 31 December 2025. The Pinnacle entity is a fictional, mature, profitable, three-division computer group used only to illustrate format; it is not NVU. Where the template carries an item NVU does not, each note states whether the difference reflects NVU's different business model and stage (not a deficiency) or a genuine disclosure gap NVU should address."));
children.push(P("Structural differences that apply throughout:", { bold: true }));
children.push(bullet("Scale and units: NVU reports in full dollars; the template in $'000."));
children.push(bullet("Year-end: NVU's year ends 31 December 2025; the template's sample year ends 30 June 2026. NVU presents two comparative columns (2025/2024); the template presents restated three-period balances (note 3 Restatement of comparatives)."));
children.push(bullet("Profit vs loss: Pinnacle is profitable, tax-paying and dividend-paying; NVU is loss-making, recognises no tax asset, and has never paid a dividend."));
children.push(bullet("EMASS: NVU's 18 March 2025 EMASS acquisition (consideration $10.47m) is an asset acquisition under AASB 2 with the consideration allocated to an intangible (R&D/IP). The template only contemplates AASB 3 business-combination accounting (note 58)."));
children.push(bullet("Capital structure: NVU is equity-funded with no bank borrowings; the template carries borrowings, a deed of cross guarantee, defined-benefit plans and supplier-finance arrangements. NVU's non-controlling interest (Fullveu HK, 49%) runs at a deficit."));

children.push(H2("Status legend"));
children.push(legend());

// 1b. Reporting framework & standards basis
children.push(H1("2.  Reporting framework and standards basis"));
children.push(P("The Pinnacle template is one of Accurri's \"Example Financial Statements\" — illustrative model accounts the Accurri statutory-reporting software refreshes each year to the current standards (30 June for Australia). Accurri does not publish a separate proprietary \"modelling standard\"; the examples are built to International Financial Reporting Standards (IFRS) and, for the Australian set, the Australian Accounting Standards (AASB Standards issued by the AASB), which are IFRS-equivalent. NVU's annual report is likewise prepared under AASB Standards and the Corporations Act 2001, and lodged under ASX Listing Rule 4.3A (Appendix 4E). Both documents therefore sit on the same AASB/IFRS framework — so every difference below is a presentation, classification or business-model difference within that shared framework, not a different GAAP. The table maps each comparison theme to the governing standard."));
children.push(refTable(
  ["AASB / IFRS", "Standard", "Where it bears on this comparison"],
  [
    ["AASB 101 / IAS 1", "Presentation of Financial Statements", "Face vs note classification; $'000 rounding vs full dollars; current/non-current splits"],
    ["AASB 108 / IAS 8", "Accounting Policies, Estimates & Errors", "Restatement of comparatives (template note 3); NVU did not restate"],
    ["AASB 15 / IFRS 15", "Revenue from Contracts with Customers", "Revenue recognition; disaggregation by geography and timing of transfer (candidate gap)"],
    ["AASB 112 / IAS 12", "Income Taxes", "Tax expense, numerical reconciliation, unrecognised deferred tax — NVU discloses in note 8"],
    ["AASB 107 / IAS 7", "Statement of Cash Flows", "Operating/investing/financing split; profit-to-operating-cash reconciliation — NVU note 9(b)"],
    ["AASB 133 / IAS 33", "Earnings per Share", "Basic vs diluted; NVU combines (anti-dilutive); per-ops split"],
    ["AASB 2 / IFRS 2", "Share-based Payment", "SBP expense on face; EMASS performance-rights consideration recognition"],
    ["AASB 3 / IFRS 3", "Business Combinations", "Template's acquisition accounting; NVU's EMASS is NOT in scope (asset acquisition)"],
    ["AASB 138 / IAS 38", "Intangible Assets", "EMASS R&D/IP intangible recognised on the asset acquisition"],
    ["AASB 9 / IFRS 9", "Financial Instruments", "HTS loan at fair value (6% discount); ECL on receivables"],
    ["AASB 7 / IFRS 7", "Financial Instruments: Disclosures", "Credit-risk / ECL ageing disclosure (candidate gap)"],
    ["AASB 13 / IFRS 13", "Fair Value Measurement", "Fair-value hierarchy for the HTS loan (candidate gap)"],
    ["AASB 16 / IFRS 16", "Leases", "Right-of-use assets and lease liabilities — both present"],
    ["AASB 10 / IFRS 10", "Consolidated Financial Statements", "Control of Fullveu HK; NCI losses attributed in full (deficit NCI)"],
    ["AASB 8 / IFRS 8", "Operating Segments", "Segment note structure (3 product segments + Corporate)"],
    ["AASB 136 / IAS 36", "Impairment of Assets", "Template's goodwill impairment; NVU has no goodwill"],
    ["AASB 5 / IFRS 5", "Non-current Assets Held for Sale & Discontinued Operations", "Template only; NVU has neither"],
    ["AASB 128 / IAS 28", "Investments in Associates and Joint Ventures", "Equity method — template only; NVU has none"],
    ["AASB 140 / IAS 40", "Investment Property", "Template only; NVU holds none"],
    ["AASB 119 / IAS 19", "Employee Benefits", "Defined-benefit plans (template); NVU folds entitlements into provisions"],
    ["AASB 137 / IAS 37", "Provisions, Contingent Liabilities & Assets", "Provisions, commitments and contingencies"],
    ["AASB 124 / IAS 24", "Related Party Disclosures", "Related-party loan and KMP disclosures"],
    ["Corporations Act 2001 / ASX LR 4.3A", "Consolidated Entity Disclosure Statement; Appendix 4E", "Australian-specific cover and CEDS — both present"],
  ],
  [16, 32, 52]
));

// 1. Appendix 4E cover
children.push(H1("3.  Appendix 4E cover page comparison"));
children.push(comparisonTable([
  { item: "1. Company details", tpl: "Present", nvu: "Present", status: "BOTH", note: "NVU: Nanoveu Limited, ABN 97 624 421 085." },
  { item: "2. Results — revenue", tpl: "up 7.3% to 467,835", nvu: "up to 297,582 (+4,230% YoY)", status: "BOTH", note: "Both report movement; NVU off a tiny base." },
  { item: "2. Results — profit/(loss) after tax to members", tpl: "profit up 74.8% to 27,126", nvu: "loss 7,423,319 (FY24: 2,809,710)", status: "BOTH", note: "Sign reversed." },
  { item: "2. Results — dividends (amount & franking)", tpl: "Final 15.0c + interim 5.0c, fully franked", nvu: "Nil — none paid or declared", status: "NIL_LOSS", note: "NVU has never paid a dividend." },
  { item: "3. Net tangible assets per security", tpl: "149.66c / 146.35c", nvu: "~0.16c (NTA ≈ net assets less 10.5m intangible)", status: "BOTH", note: "NVU NTA minimal after excluding EMASS intangible." },
  { item: "4. Control gained over entities", tpl: "CompCarrier (AASB 3)", nvu: "EMASS (AASB 2 asset acq.) / Fullveu HK", status: "STRUCT_DIFF", note: "NVU's control events are an asset acquisition and an existing controlled entity, not an AASB 3 combination." },
  { item: "5. Loss of control over entities", tpl: "Sold Retailing Intl", nvu: null, status: "NOT_IN_NVU", note: "No disposals." },
  { item: "6. Details of associates and JVs", tpl: "Compdesign Partnership 35%", nvu: null, status: "NOT_IN_NVU", note: "No associates/JVs." },
  { item: "7. Audit qualification or review", tpl: "Audited, unmodified", nvu: "Audited by BDO (sec 9)", status: "BOTH", note: "Both audited." },
  { item: "8. Attachments / Foreign entities", tpl: "Attachments", nvu: "Sec 8 Foreign Entities + sec 10 Attachments", status: "STRUCT_DIFF", note: "NVU adds a Foreign Entities accounting-standards statement (HK/SG subsidiaries)." },
  { item: "9. Signed by director", tpl: "Present", nvu: "Present", status: "BOTH", note: "" },
  { item: "Dividend Reinvestment Plan section", tpl: null, nvu: "Section 6", status: "NOT_IN_TPL", note: "NVU 4E carries a discrete DRP section." },
]));

// 2. P&L
children.push(H1("4.  Statement of Profit or Loss and OCI — line by line"));
children.push(comparisonTable([
  { item: "Revenue from continuing operations", tpl: "442,127", nvu: "297,582", status: "BOTH", note: "Scale differs." },
  { item: "Share of profits of associates (equity method)", tpl: "3,211", nvu: null, status: "NOT_IN_NVU", note: "No associates." },
  { item: "Other income", tpl: "692", nvu: "6,436", status: "BOTH", note: "" },
  { item: "Interest / finance income", tpl: "1,057", nvu: "32,756", status: "BOTH", note: "NVU labels finance income." },
  { item: "Net gain on derecognition of financial assets", tpl: "50", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "Changes in inventories / Raw materials", tpl: "(3,379) / (115,660)", nvu: "in COGS (929,715)", status: "STRUCT_DIFF", note: "NVU shows one 'Cost of sale of goods' line." },
  { item: "Employee benefits expense", tpl: "(217,234)", nvu: "in admin", status: "STRUCT_DIFF", note: "Not separately disclosed on NVU's face." },
  { item: "Depreciation and amortisation", tpl: "(51,963)", nvu: "(173,112) in seg. note", status: "STRUCT_DIFF", note: "NVU discloses D&A in the segment note, not the P&L face." },
  { item: "Impairment of goodwill", tpl: "(500)", nvu: null, status: "NOT_IN_NVU", note: "NVU has no goodwill (asset acquisition, not AASB 3)." },
  { item: "Impairment of receivables", tpl: "(491)", nvu: "—", status: "NIL_LOSS", note: "No receivables impairment recognised." },
  { item: "Net fair value loss on investment properties", tpl: "(600)", nvu: null, status: "NOT_IN_NVU", note: "No investment property." },
  { item: "Other / selling & research expenses", tpl: "(2,136)", nvu: "S&D (386,930); Research (760,818)", status: "STRUCT_DIFF", note: "NVU breaks out selling and R&D costs." },
  { item: "Share-based payment expense (face)", tpl: null, nvu: "(1,421,890)", status: "NOT_IN_TPL", note: "NVU presents SBP as a face line (note 7)." },
  { item: "Finance costs", tpl: "(18,930)", nvu: "(13,706)", status: "BOTH", note: "" },
  { item: "Profit / (loss) before income tax", tpl: "36,244", nvu: "(7,601,225)", status: "BOTH", note: "Profit vs loss." },
  { item: "Income tax expense", tpl: "(10,114)", nvu: "—", status: "NIL_LOSS", note: "No tax; note 8 reconciles nil expense." },
  { item: "Profit after tax — continuing operations", tpl: "26,130", nvu: "no split", status: "STRUCT_DIFF", note: "NVU has no continuing/discontinued split." },
  { item: "Profit after tax — discontinued operations", tpl: "1,138", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "Profit / (loss) for the year", tpl: "27,268", nvu: "(7,601,225)", status: "BOTH", note: "" },
  { item: "OCI — revaluation of land & buildings", tpl: "— (pr 1,400)", nvu: null, status: "NOT_IN_NVU", note: "No revalued PP&E." },
  { item: "OCI — actuarial gain on defined benefit plans", tpl: "105", nvu: null, status: "NOT_IN_NVU", note: "No defined-benefit plans." },
  { item: "OCI — FVOCI equity revaluation / cash flow hedges", tpl: "35 / (7)", nvu: null, status: "NOT_IN_NVU", note: "No FVOCI equities or hedge accounting." },
  { item: "OCI — foreign currency translation", tpl: "(257)", nvu: "9,462", status: "BOTH", note: "Both translate foreign operations." },
  { item: "OCI — derecognition of FX reserve", tpl: "769", nvu: null, status: "NOT_IN_NVU", note: "From subsidiary disposal; n/a." },
  { item: "Total comprehensive income / (loss)", tpl: "27,910", nvu: "(7,591,763)", status: "BOTH", note: "" },
  { item: "Attributable to NCI / owners", tpl: "142 / 27,126", nvu: "(177,906) / (7,423,319)", status: "BOTH", note: "NVU NCI absorbs losses (deficit)." },
  { item: "EPS / LPS — basic & diluted", tpl: "18.47 / 18.41c (split by ops)", nvu: "(0.9)c single", status: "STRUCT_DIFF", note: "NVU: one LPS; no continuing/discontinued split; no dilution (anti-dilutive)." },
  { item: "Restatement of comparatives reference", tpl: "Refer note 3", nvu: null, status: "NOT_IN_NVU", note: "NVU did not restate prior-year comparatives." },
]));

// 3. Balance sheet
children.push(H1("5.  Statement of Financial Position — line by line"));
children.push(comparisonTable([
  { item: "Cash and cash equivalents", tpl: "26,136", nvu: "1,807,712", status: "BOTH", note: "" },
  { item: "Trade and other receivables", tpl: "13,003", nvu: "11,234", status: "BOTH", note: "" },
  { item: "Contract assets", tpl: "2,617", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "Inventories", tpl: "38,692", nvu: null, status: "NOT_IN_NVU", note: "No material inventory." },
  { item: "Financial assets at FVTPL", tpl: "360", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "Other current / prepayments", tpl: "3,907", nvu: "454,731 (Prepayments)", status: "BOTH", note: "NVU breaks out prepayments." },
  { item: "Loan receivable (current)", tpl: null, nvu: "472,374", status: "NOT_IN_TPL", note: "HTS loan reclassified to current at year-end (note 14)." },
  { item: "Assets held for sale / disposal groups", tpl: "6,000", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "Non-current receivables", tpl: "145", nvu: "—", status: "BOTH", note: "NVU's loan now current; prior-year was non-current." },
  { item: "Investments — equity method", tpl: "34,192", nvu: null, status: "NOT_IN_NVU", note: "No associates." },
  { item: "Financial assets at FVOCI", tpl: "170", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "Investment properties", tpl: "46,900", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "Property, plant and equipment", tpl: "116,698", nvu: "119,190", status: "BOTH", note: "" },
  { item: "Right-of-use assets", tpl: "318,292", nvu: "131,399", status: "BOTH", note: "" },
  { item: "Intangibles", tpl: "12,170", nvu: "10,500,307", status: "BOTH", note: "NVU's is the EMASS intangible (R&D/IP) — the headline asset." },
  { item: "Non-current prepayments", tpl: null, nvu: "57,968", status: "NOT_IN_TPL", note: "NVU-specific non-current prepayment." },
  { item: "Deferred tax asset", tpl: "14,490", nvu: null, status: "NIL_LOSS", note: "No DTA — losses not yet probable of recovery." },
  { item: "Other non-current assets", tpl: "2,262", nvu: null, status: "NOT_IN_NVU", note: "" },
  { item: "Trade and other payables", tpl: "18,854", nvu: "1,004,988", status: "BOTH", note: "" },
  { item: "Contract liabilities", tpl: "2,269", nvu: "169,196", status: "BOTH", note: "" },
  { item: "Borrowings (current + non-current)", tpl: "4,500 + 19,000", nvu: "—", status: "NOT_IN_NVU", note: "No bank borrowings." },
  { item: "Lease liabilities (current + non-current)", tpl: "22,072 + 310,978", nvu: "64,168 + 71,891", status: "BOTH", note: "" },
  { item: "Interest-free related-party loan", tpl: null, nvu: "134,011", status: "NOT_IN_TPL", note: "NVU-specific (shown as 'Loan')." },
  { item: "Derivative financial instruments", tpl: "122", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "Income tax payable", tpl: "6,701", nvu: "—", status: "NIL_LOSS", note: "No current tax." },
  { item: "Employee benefits / Provisions", tpl: "8,084 / 3,494 + NC", nvu: "17,231 (Provisions)", status: "STRUCT_DIFF", note: "NVU folds employee entitlements into a single Provisions line." },
  { item: "Deferred tax liability", tpl: "4,617", nvu: null, status: "NIL_LOSS", note: "None recognised." },
  { item: "Net assets", tpl: "216,909", nvu: "12,093,430", status: "BOTH", note: "" },
  { item: "Issued capital", tpl: "182,953", nvu: "39,377,691", status: "BOTH", note: "987,087,553 shares on issue." },
  { item: "Reserves", tpl: "4,045", nvu: "1,722,677", status: "BOTH", note: "" },
  { item: "Retained profits / (accumulated losses)", tpl: "12,548", nvu: "(28,792,375)", status: "BOTH", note: "NVU in deficit." },
  { item: "Non-controlling interest", tpl: "17,363", nvu: "(214,563)", status: "BOTH", note: "NVU NCI is a deficit (Fullveu HK)." },
  { item: "Total equity", tpl: "216,909", nvu: "12,093,430", status: "BOTH", note: "" },
]));

// 4. Cash flows
children.push(H1("6.  Statement of Cash Flows — line by line"));
children.push(comparisonTable([
  { item: "Receipts from customers", tpl: "507,999", nvu: "161,727", status: "BOTH", note: "" },
  { item: "Payments to suppliers and employees", tpl: "(401,934)", nvu: "(6,033,547)", status: "BOTH", note: "" },
  { item: "Interest received", tpl: "1,084", nvu: "32,756", status: "BOTH", note: "" },
  { item: "Other revenue (operating)", tpl: "3,964", nvu: null, status: "NOT_IN_NVU", note: "Not separately presented." },
  { item: "Interest / finance costs paid", tpl: "(18,845)", nvu: "(6,774)", status: "BOTH", note: "" },
  { item: "Income taxes paid", tpl: "(9,142)", nvu: "—", status: "NIL_LOSS", note: "No tax paid." },
  { item: "Net cash from / (used in) operating", tpl: "83,126", nvu: "(5,845,838)", status: "BOTH", note: "Template generates cash; NVU burns ~$487k/month." },
  { item: "Payment for purchase of business (net of cash)", tpl: "(8,072)", nvu: "2,910 cash acquired (EMASS)", status: "STRUCT_DIFF", note: "Asset acquisition: NVU recorded net cash acquired, not a purchase outflow." },
  { item: "Payments for investments", tpl: "(510)", nvu: null, status: "NOT_IN_NVU", note: "" },
  { item: "Payments for property, plant and equipment", tpl: "(6,215)", nvu: "(76,510)", status: "BOTH", note: "" },
  { item: "Proceeds from sale of subsidiary / investments / PP&E", tpl: "41 / 80 / 1,511", nvu: null, status: "NOT_IN_NVU", note: "No disposals." },
  { item: "Loan receivable / funds to third parties (HTS)", tpl: null, nvu: "(213,711)", status: "NOT_IN_TPL", note: "NVU-specific related-party loan." },
  { item: "Net cash used in investing", tpl: "(13,010)", nvu: "(287,311)", status: "BOTH", note: "" },
  { item: "Proceeds from issue of shares (net)", tpl: "25", nvu: "7,471,773", status: "BOTH", note: "NVU is materially equity-funded; template raises little." },
  { item: "Proceeds from borrowings", tpl: "12,000", nvu: null, status: "NOT_IN_NVU", note: "No borrowings." },
  { item: "Dividends paid", tpl: "(29,383)", nvu: "—", status: "NIL_LOSS", note: "Never paid." },
  { item: "Repayment of borrowings", tpl: "(5,500)", nvu: null, status: "NOT_IN_NVU", note: "No borrowings." },
  { item: "Interest-free related-party loan (net)", tpl: null, nvu: "14,011 (134,011 less 120,000)", status: "NOT_IN_TPL", note: "NVU-specific." },
  { item: "Repayment of lease liabilities", tpl: "(25,385)", nvu: "(43,226)", status: "BOTH", note: "" },
  { item: "Net cash from / (used in) financing", tpl: "(48,243)", nvu: "7,442,558", status: "BOTH", note: "Opposite direction." },
  { item: "Effects of FX rate changes on cash", tpl: "12", nvu: "—", status: "NOT_IN_NVU", note: "NVU nets FX within OCI." },
  { item: "Net change / opening / closing cash", tpl: "21,873 / 4,251 / 26,136", nvu: "1,309,409 / 498,303 / 1,807,712", status: "BOTH", note: "" },
]));

// 5. Directors' / Remuneration report
children.push(H1("7.  Directors' report and Remuneration report"));
children.push(comparisonTable([
  { item: "Directors' report — directors & company secretary", tpl: "Present", nvu: "Present", status: "BOTH", note: "NVU lists directors, CFO/Co-Sec changes (Haydari → Spindler)." },
  { item: "Principal activities", tpl: "3 computer divisions", nvu: "Semiconductor / 3D display / nano-coating", status: "BOTH", note: "" },
  { item: "Review of operations / financial position", tpl: "Profit narrative", nvu: "Loss & development narrative", status: "BOTH", note: "" },
  { item: "Dividends — paid/declared", tpl: "Final + interim, franked", nvu: "None paid or declared", status: "NIL_LOSS", note: "" },
  { item: "Significant changes in state of affairs", tpl: "Acquisition + disposal", nvu: "EMASS asset acquisition; capital raises", status: "BOTH", note: "" },
  { item: "Rounding (ASIC instrument)", tpl: "Rounded to nearest $'000", nvu: "Reports in full dollars", status: "STRUCT_DIFF", note: "NVU does not apply $'000 rounding." },
  { item: "Rem. report — principles of remuneration", tpl: "Present", nvu: "Present", status: "BOTH", note: "" },
  { item: "Rem. report — details of remuneration", tpl: "Present", nvu: "Present", status: "BOTH", note: "" },
  { item: "Rem. report — service agreements", tpl: "Present", nvu: "Present", status: "BOTH", note: "" },
  { item: "Rem. report — share-based compensation", tpl: "Options/rights", nvu: "Performance rights (incl. EMASS classes)", status: "BOTH", note: "NVU's SBC is dominated by performance rights tied to the EMASS acquisition." },
  { item: "Rem. report — STI/LTI cash bonus & KPIs", tpl: "Present (profit-linked)", nvu: "Limited / nil cash STI", status: "NIL_LOSS", note: "No profit-linked cash bonuses — pre-profit company." },
  { item: "Rem. report — AGM vote on remuneration", tpl: "91% support FY25", nvu: "Disclosed for NVU AGM", status: "BOTH", note: "" },
  { item: "Indemnity & insurance of officers/auditor", tpl: "Present", nvu: "Present", status: "BOTH", note: "" },
  { item: "Non-audit services / auditor independence", tpl: "Present (note 52)", nvu: "Present (note 22 auditors' remuneration)", status: "BOTH", note: "" },
]));

// 6. Notes structural gaps
children.push(H1("8.  Notes to the financial statements — structural mapping"));
children.push(P("The template carries 68 notes; NVU's annual carries 23. The table maps the template's note groups to NVU's equivalents and flags genuine gaps.", { italic: true }));
children.push(comparisonTable([
  { item: "Material accounting policies", tpl: "Note 1", nvu: "Note 2", status: "BOTH", note: "" },
  { item: "Critical judgements, estimates & assumptions", tpl: "Note 2", nvu: "Embedded (Fullveu control, HTS recoverability, EMASS asset-acq)", status: "STRUCT_DIFF", note: "NVU discloses key judgements within policy/segment text rather than a dedicated note." },
  { item: "Restatement of comparatives", tpl: "Note 3", nvu: null, status: "NOT_IN_NVU", note: "NVU did not restate comparatives." },
  { item: "Operating segments", tpl: "Note 4 (3 divisions)", nvu: "Note 4 (4 segments + adj/elim)", status: "BOTH", note: "Semiconductor/EyeFly3D/Nanoshield/Corporate." },
  { item: "Revenue (AASB 15 disaggregation)", tpl: "Note 5", nvu: "Geographic split in seg. note", status: "STRUCT_DIFF", note: "NVU shows geographic revenue but no standalone AASB 15 disaggregation note (candidate gap)." },
  { item: "Share of associate profits / Other income", tpl: "Notes 6, 7", nvu: "Note 6 'Result for the period'", status: "STRUCT_DIFF", note: "No associates; NVU groups income/expense detail in note 6." },
  { item: "Expenses", tpl: "Note 8", nvu: "Note 6", status: "BOTH", note: "NVU discloses expense detail in note 6." },
  { item: "Income tax", tpl: "Note 9", nvu: "Note 8", status: "BOTH", note: "NVU reconciles a nil expense and unrecognised tax losses." },
  { item: "Discontinued operations", tpl: "Note 10", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "Cash / receivables / contract assets / inventories", tpl: "Notes 11-14", nvu: "Notes 9-11 (cash, contract liab, prepayments)", status: "STRUCT_DIFF", note: "NVU has no inventory/contract-asset notes." },
  { item: "Financial assets FVTPL / FVOCI", tpl: "Notes 15, 21", nvu: null, status: "NOT_IN_NVU", note: "None held." },
  { item: "Held-for-sale / disposal groups", tpl: "Notes 17, 18", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "Investments (equity method) / Investment properties", tpl: "Notes 20, 22", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "PP&E / Right-of-use / Intangibles", tpl: "Notes 23-25", nvu: "Note 13 Intangibles", status: "BOTH", note: "NVU's note 13 details the EMASS intangible; PP&E/ROU on face." },
  { item: "Loan receivable", tpl: "Note 19 (receivables)", nvu: "Note 14", status: "BOTH", note: "HTS loan at fair value (6% discount)." },
  { item: "Borrowings (current & non-current)", tpl: "Notes 30, 38", nvu: null, status: "NOT_IN_NVU", note: "No borrowings." },
  { item: "Lease liabilities", tpl: "Notes 31, 39", nvu: "On face", status: "BOTH", note: "" },
  { item: "Deferred tax", tpl: "Notes 26, 40", nvu: "Within note 8", status: "NIL_LOSS", note: "No balances recognised." },
  { item: "Employee benefits / Retirement benefit obligations", tpl: "Notes 34, 41, 43", nvu: "Within provisions", status: "NOT_IN_NVU", note: "No defined-benefit/retirement plans." },
  { item: "Issued capital / Reserves / Retained / NCI / Dividends", tpl: "Notes 44-48", nvu: "Note 15 + SOCIE", status: "BOTH", note: "Dividends nil." },
  { item: "Financial instruments / Fair value measurement", tpl: "Notes 49, 50", nvu: "Note 21 Financial risk management", status: "STRUCT_DIFF", note: "NVU covers risk but gives limited AASB 13 fair-value-hierarchy disclosure for the HTS loan (candidate gap)." },
  { item: "KMP disclosures / Remuneration of auditors", tpl: "Notes 51, 52", nvu: "Notes 17, 22", status: "BOTH", note: "" },
  { item: "Contingent assets/liabilities / Commitments", tpl: "Notes 53-55", nvu: "Note 20 Commitments", status: "BOTH", note: "" },
  { item: "Related party transactions", tpl: "Note 56", nvu: "Note 16", status: "BOTH", note: "" },
  { item: "Parent entity information", tpl: "Note 57", nvu: "Note 18", status: "BOTH", note: "" },
  { item: "Business combinations (AASB 3)", tpl: "Note 58", nvu: "EMASS = AASB 2 asset acq.", status: "STRUCT_DIFF", note: "Template only covers AASB 3; NVU's is an asset acquisition (note 13)." },
  { item: "Interests in subsidiaries / associates", tpl: "Notes 59, 60", nvu: "Note 19 Subsidiaries", status: "BOTH", note: "NVU includes Fullveu HK (deficit NCI)." },
  { item: "Deed of cross guarantee", tpl: "Note 61", nvu: null, status: "NOT_IN_NVU", note: "No deed of cross guarantee." },
  { item: "Events after the reporting period", tpl: "Note 62", nvu: "Note 23", status: "BOTH", note: "" },
  { item: "Reconciliation of profit to operating cash", tpl: "Note 63", nvu: "Note in cash-flow section", status: "BOTH", note: "NVU's annual DOES include this reconciliation (unlike its interim)." },
  { item: "Non-cash investing/financing; changes in financing liabilities; supplier finance", tpl: "Notes 64-66", nvu: null, status: "NOT_IN_NVU", note: "NVU had material non-cash items (EMASS shares, performance rights) — a reconciliation/non-cash note is a candidate gap (B)." },
  { item: "Earnings per share", tpl: "Note 67", nvu: "Note 5", status: "BOTH", note: "" },
  { item: "Share-based payments", tpl: "Note 68", nvu: "Note 7", status: "BOTH", note: "NVU's includes EMASS performance-rights classes." },
  { item: "Consolidated entity disclosure statement", tpl: "Present", nvu: "Present (31 Dec 2025)", status: "BOTH", note: "Both include the CEDS." },
]));

// 7. Summary
children.push(H1("9.  Summary of gaps by category"));

children.push(H2("(A) Template items absent from NVU due to a different business model — not deficiencies"));
[ "Inventories, contract assets and inventory-management disclosure (NVU is pre-scale).",
  "Investments in associates/JVs, equity-method accounting and investment properties.",
  "Financial assets at FVTPL and FVOCI; derivatives and cash-flow hedge accounting.",
  "Goodwill and goodwill impairment (NVU's EMASS is an asset acquisition, so no goodwill arises).",
  "Bank borrowings (current and non-current); proceeds/repayments of borrowings; deed of cross guarantee.",
  "Dividends, franking and dividend cash flows — NVU has never paid a dividend.",
  "Income tax expense, current and deferred tax balances — loss-making, no recognised tax asset.",
  "Discontinued operations, loss of control / disposals, and held-for-sale assets/liabilities.",
  "Defined-benefit / retirement-benefit plans and actuarial OCI; separately disclosed employee-benefit provisions.",
  "Restatement of comparatives, supplier-finance arrangements, and revaluation of land & buildings.",
  "AASB 3 business-combination accounting (NVU's EMASS is an AASB 2 asset acquisition).",
].forEach(t => children.push(bullet(t)));

children.push(P("Each point cites the governing standard. (For completeness: NVU was independently verified to ALREADY disclose the AASB 112 income-tax reconciliation (note 8) and the AASB 107 profit-to-operating-cash reconciliation (note 9b) — so those are NOT gaps, contrary to some reviews.)", { italic: true, color: "808080" }));
[ "AASB 15 / IFRS 15 — standalone revenue disaggregation: NVU shows only geographic revenue in the segment note; disaggregation by timing of transfer (point-in-time vs over-time) and major product line on the face/notes is expected.",
  "AASB 13 / IFRS 13 — fair-value-hierarchy disclosure for the HTS loan receivable carried at fair value (6% discount): NVU's note 21 covers credit risk but not the Level 1/2/3 hierarchy or valuation inputs.",
  "AASB 107 / IAS 7 — non-cash investing and financing activities note: NVU had large non-cash items (EMASS consideration shares $9.14m, performance rights, loan conversions) that warrant a dedicated disclosure (this is separate from the operating-cash reconciliation, which NVU does provide).",
  "AASB 133 / IAS 33 — present diluted EPS as its own line even where it equals basic: NVU combines \"basic and diluted\"; permitted while anti-dilutive but a separate line is the convention.",
  "AASB 7 / IFRS 7 — credit-risk / expected-credit-loss ageing analysis on receivables is thin (low materiality: receivables are only $11,234, but the disclosure is still expected).",
  "AASB 101 / IAS 1 — depreciation and amortisation is presented only in the segment note, not on the P&L face.",
  "AASB 134 / AASB 108 — interim-to-annual consistency: interest paid and lease-repayment figures differ markedly between the reviewed H1 and audited FY numbers, indicating reclassification; ensure the bridge is explained.",
  "AASB 108 / IAS 8 — a dedicated critical-judgements-and-estimates note (template note 2) would consolidate the EMASS, Fullveu-control and HTS-recoverability judgements now spread through the text.",
].forEach(t => children.push(bullet(t)));

children.push(H2("(C) NVU-specific items the template does not anticipate"));
[ "AASB 2 asset acquisition (EMASS, $10.47m) with consideration allocated to an intangible (R&D/IP) and performance-rights consideration — no AASB 3 template equivalent.",
  "Non-controlling interest running at a deficit (Fullveu HK 49% minority absorbing losses) — the template NCI is positive.",
  "Interest-free related-party loan (financing) and a related-party loan receivable from HTS measured at fair value (investing/non-current then current).",
  "Share-based payment expense as a discrete P&L face line, dominated by EMASS performance-right classes.",
  "Research costs as a discrete expense line (R&D-stage company).",
  "A 'Foreign Entities' statement on the Appendix 4E cover (HK/Singapore subsidiaries) and a Dividend Reinvestment Plan section.",
  "Reporting in full dollars (not $'000) and a 31 December year-end versus the template's 30 June presentation.",
].forEach(t => children.push(bullet(t)));

children.push(P(""));
children.push(P("End of annual comparison.", { italic: true, color: "808080" }));

const doc = new Document({
  creator: "NVU financial analysis", title: "NVU vs Accurri — Annual Differences",
  styles: { default: { document: { run: { font: "Calibri" } } } },
  sections: [{ properties: { page: { margin: { top: 720, bottom: 720, left: 720, right: 720 } } }, children }],
});

Packer.toBuffer(doc).then(buf => {
  const target = "Annual_Differences.docx";
  try {
    fs.writeFileSync(target, buf);
    console.log("Wrote", target, buf.length, "bytes");
  } catch (e) {
    if (e.code === "EBUSY" || e.code === "EPERM") {
      fs.writeFileSync("_work/Annual_Differences.docx", buf);
      console.log("TARGET LOCKED — wrote _work/Annual_Differences.docx", buf.length, "bytes (close the open file, then copy over).");
    } else { throw e; }
  }
});
