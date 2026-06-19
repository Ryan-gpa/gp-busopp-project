// NVU_vs_Accurri_Differences.docx — Half-year comparison
// NVU HY ended 30 June 2025 vs Pinnacle Listed Comprehensive Interim Limited template.
const fs = require("fs");
const L = require("./docx_lib.js");
const { Document, Packer, Paragraph, TextRun, AlignmentType,
        H1, H2, P, bullet, comparisonTable, legend, refTable, titlePage } = L;

const children = [];

// ---- Title
titlePage(
  "NVU vs Accurri — Half-Year Differences",
  "Nanoveu Limited (ASX: NVU) — Appendix 4D & Interim Financial Report",
  ["NVU half-year ended 30 June 2025  vs  Pinnacle Listed Comprehensive Interim Limited (Accurri template)",
   "Prepared 17 June 2026",
   "All NVU figures in full Australian dollars; all template figures in $'000"]
).forEach(p => children.push(p));

children.push(new Paragraph({ pageBreakBefore: true, children: [] }));

// ---- Scope & caveats
children.push(H1("1.  Purpose, scope and reading notes"));
children.push(P("This document compares every line item in the Accurri-produced Pinnacle interim template (the correct ASX Appendix 4D / interim report format) against Nanoveu Limited's reviewed half-year report for the period ended 30 June 2025. The Pinnacle entity is a fictional, mature, profitable, dividend-paying computer group used only to illustrate the format; it is not NVU. Where the template carries an item NVU does not, the note states whether this reflects NVU's different business model and stage (not a deficiency) or a genuine disclosure gap NVU should address."));
children.push(P("Structural differences that apply throughout — read first:", { bold: true }));
children.push(bullet("Scale and units: NVU reports in full dollars; the Pinnacle template reports in $'000. A NVU revenue of $281,115 sits against a template figure of 233,900 ($'000 = $233.9m). Magnitudes are not comparable; only presence/structure is.", {}));
children.push(bullet("Year-end: NVU's financial year ends 31 December (this is the first-half to 30 June 2025); the template entity's year ends 31 December but the sample interim is to 30 June 2026 with a 30 June 2025 comparative. Period labels therefore differ.", {}));
children.push(bullet("Profit vs loss: Pinnacle is profitable and tax-paying; NVU is loss-making and pre-tax-asset. Many template lines (income tax, deferred tax, dividends, retained profits) are necessarily nil or reversed in sign for NVU — flagged NIL (LOSS CO.).", {}));
children.push(bullet("EMASS acquisition: NVU accounted for the 18 March 2025 EMASS acquisition as an asset acquisition under AASB 2 (consideration $10.47m allocated to intangibles representing R&D/IP), not a business combination under AASB 3. The template only contemplates the AASB 3 business-combination format.", {}));
children.push(bullet("Capital structure: NVU is equity-funded with no bank borrowings and has never paid a dividend; the template entity carries borrowings and pays franked dividends. NVU also carries a non-controlling interest running at a deficit (Fullveu HK, 49% minority absorbing losses).", {}));

children.push(H2("Status legend"));
children.push(legend());

// ---- Reporting framework & standards basis
children.push(H1("2.  Reporting framework and standards basis"));
children.push(P("The Pinnacle interim template is one of Accurri's \"Example Financial Statements\" — illustrative model accounts the Accurri statutory-reporting software refreshes to the current standards each year. Accurri publishes no separate proprietary \"modelling standard\": the examples are built to International Financial Reporting Standards (IFRS) and, for the Australian set, the Australian Accounting Standards (AASB Standards issued by the AASB). A half-year report is governed specifically by AASB 134 / IAS 34 Interim Financial Reporting. NVU's interim is prepared on the same AASB/IFRS basis and lodged under ASX Listing Rule 4.2A (Appendix 4D). Every difference below is therefore a presentation, classification or business-model difference within that shared framework. The table maps each comparison theme to the governing standard."));
children.push(refTable(
  ["AASB / IFRS", "Standard", "Where it bears on this comparison"],
  [
    ["AASB 134 / IAS 34", "Interim Financial Reporting", "Condensed interim form; selected-note basis; what an interim must (and need not) disclose"],
    ["AASB 101 / IAS 1", "Presentation of Financial Statements", "Face vs note classification; $'000 vs full dollars; current/non-current splits"],
    ["AASB 15 / IFRS 15", "Revenue from Contracts with Customers", "Revenue recognition and disaggregation (candidate gap)"],
    ["AASB 112 / IAS 12", "Income Taxes", "Nil tax expense; tax reconciliation expectation"],
    ["AASB 107 / IAS 7", "Statement of Cash Flows", "Operating/investing/financing; profit-to-operating-cash reconciliation (omitted in NVU's interim)"],
    ["AASB 133 / IAS 33", "Earnings per Share", "Basic vs diluted LPS; NVU combines (anti-dilutive)"],
    ["AASB 2 / IFRS 2", "Share-based Payment", "SBP expense on face; EMASS performance-rights consideration"],
    ["AASB 3 / IFRS 3", "Business Combinations", "Template scope; NVU's EMASS is NOT a business combination"],
    ["AASB 138 / IAS 38", "Intangible Assets", "EMASS R&D/IP intangible on the asset acquisition"],
    ["AASB 9 / IFRS 9", "Financial Instruments", "HTS loan at fair value (6% discount); ECL"],
    ["AASB 13 / IFRS 13", "Fair Value Measurement", "Fair-value hierarchy for the HTS loan (candidate gap)"],
    ["AASB 16 / IFRS 16", "Leases", "Right-of-use assets and lease liabilities"],
    ["AASB 10 / IFRS 10", "Consolidated Financial Statements", "Control of Fullveu HK; deficit NCI (losses attributed in full)"],
    ["AASB 8 / IFRS 8", "Operating Segments", "3 product segments + Corporate"],
    ["AASB 5 / IFRS 5", "Held for Sale & Discontinued Operations", "Template only; NVU has neither"],
    ["AASB 128 / IAS 28", "Investments in Associates & JVs", "Equity method — template only; NVU has none"],
    ["ASX Listing Rule 4.2A", "Appendix 4D — half-year report", "Cover sections 1–9; NTA backing"],
  ],
  [16, 30, 54]
));

// ---- Section: Appendix 4D cover
children.push(H1("3.  Appendix 4D cover (sections 1–9)"));
children.push(comparisonTable([
  { item: "1. Entity / company details", tpl: "Present", nvu: "Present", status: "BOTH",
    note: "NVU: Nanoveu Limited, ABN 97 624 421 085." },
  { item: "2. Results for announcement — revenue", tpl: "up 6.7% to 233,900", nvu: "up 270 (2,450%) to 281",
    status: "BOTH", note: "NVU reports the $'000 movement on the cover even though statements are full $." },
  { item: "2. Results — profit/(loss) after tax to members", tpl: "profit up 82.2% to 14,526", nvu: "loss up 1,874 (171%) to 2,969",
    status: "BOTH", note: "Sign reversed: NVU reports a widening loss." },
  { item: "2. Results — EPS / LPS movement", tpl: "n/a on cover", nvu: "LPS up 0.24 (119%) to 0.44",
    status: "BOTH", note: "Both ultimately disclose per-share result." },
  { item: "3. Net tangible assets per security", tpl: "149.41c / 151.54c", nvu: "$0.0028 / $0.0017",
    status: "BOTH", note: "NVU NTA ~0.28c — far lower; large intangible (EMASS) excluded from NTA." },
  { item: "4. Control gained over entities", tpl: "CompCarrier (AASB 3 business comb.)", nvu: "EMASS = AASB 2 asset acq.",
    status: "STRUCT_DIFF", note: "NVU gained control of Fullveu HK and acquired EMASS as an asset acquisition, not an AASB 3 combination." },
  { item: "5. Loss of control over entities", tpl: "Sold Pinnacle Retailing Intl", nvu: null,
    status: "NOT_IN_NVU", note: "NVU made no disposals in the period — not a deficiency." },
  { item: "6. Details of associates and JVs", tpl: "Compdesign Partnership 35%", nvu: null,
    status: "NOT_IN_NVU", note: "NVU has no associates or joint ventures." },
  { item: "7. Audit qualification / review", tpl: "Reviewed", nvu: "Independent Review Report (sec 8)",
    status: "BOTH", note: "Both reviewed; section numbering differs." },
  { item: "8. Attachments", tpl: "Present", nvu: "Present", status: "BOTH", note: "Interim report attached." },
  { item: "9. Signed by director", tpl: "Present", nvu: "Present", status: "BOTH", note: "" },
  { item: "Dividend Reinvestment Plan section", tpl: null, nvu: "Section 6 (DRP status)",
    status: "NOT_IN_TPL", note: "NVU's 4D carries a discrete DRP section the template lacks." },
]));

// ---- Section: P&L and OCI
children.push(H1("4.  Statement of Profit or Loss and OCI — line by line"));
children.push(comparisonTable([
  { item: "Revenue from continuing operations", tpl: "208,736", nvu: "281,115", status: "BOTH", note: "Scale differs ($'000 vs full $)." },
  { item: "Share of profits of associates (equity method)", tpl: "1,616", nvu: null, status: "NOT_IN_NVU", note: "No associates." },
  { item: "Other income", tpl: "692", nvu: "5,645", status: "BOTH", note: "NVU: other operating income." },
  { item: "Interest / finance income", tpl: "513", nvu: "5,168", status: "BOTH", note: "NVU labels it finance income." },
  { item: "Net gain on derecognition of financial assets", tpl: "50", nvu: null, status: "NOT_IN_NVU", note: "No such financial assets." },
  { item: "Changes in inventories", tpl: "(516)", nvu: "in COGS", status: "STRUCT_DIFF", note: "NVU shows a single 'Cost of sale of goods' (104,080)." },
  { item: "Raw materials and consumables used", tpl: "(51,121)", nvu: "in COGS", status: "STRUCT_DIFF", note: "Subsumed within NVU cost of sales." },
  { item: "Employee benefits expense", tpl: "(104,765)", nvu: "in admin", status: "STRUCT_DIFF", note: "NVU does not disclose employee benefits separately on the face." },
  { item: "Depreciation and amortisation", tpl: "(25,825)", nvu: "(74,932) in seg. note", status: "STRUCT_DIFF", note: "NVU shows D&A only in the segment note, not on the P&L face." },
  { item: "Impairment of receivables", tpl: "(256)", nvu: "—", status: "NIL_LOSS", note: "NVU recognised no receivables impairment this period." },
  { item: "Other expenses", tpl: "(865)", nvu: "S&D (112,797); Research (138,137)", status: "STRUCT_DIFF", note: "NVU uses function-based opex lines; template lumps 'other'." },
  { item: "Share-based payment expense (face)", tpl: null, nvu: "(1,332,119)", status: "NOT_IN_TPL", note: "NVU presents SBP as a discrete face line; template keeps it in notes/equity." },
  { item: "Finance costs", tpl: "(9,465)", nvu: "(6,554)", status: "BOTH", note: "" },
  { item: "Profit / (loss) before income tax", tpl: "18,794", nvu: "(3,037,596)", status: "BOTH", note: "Profit vs loss." },
  { item: "Income tax expense", tpl: "(5,335)", nvu: "—", status: "NIL_LOSS", note: "No tax — loss-making, no tax asset recognised." },
  { item: "Profit after tax — continuing operations", tpl: "13,459", nvu: "no split", status: "STRUCT_DIFF", note: "NVU has no continuing/discontinued split." },
  { item: "Profit after tax — discontinued operations", tpl: "1,138", nvu: null, status: "NOT_IN_NVU", note: "NVU has no discontinued operations." },
  { item: "Profit / (loss) for the half-year", tpl: "14,597", nvu: "(3,037,596)", status: "BOTH", note: "" },
  { item: "OCI — revaluation of FVOCI equity instruments", tpl: "35", nvu: null, status: "NOT_IN_NVU", note: "No FVOCI equities." },
  { item: "OCI — cash flow hedges (3 lines)", tpl: "(1) to (3)", nvu: null, status: "NOT_IN_NVU", note: "NVU does no hedge accounting." },
  { item: "OCI — foreign currency translation", tpl: "(157)", nvu: "56,359", status: "BOTH", note: "Both translate foreign operations." },
  { item: "OCI — derecognition of FX reserve", tpl: "769", nvu: null, status: "NOT_IN_NVU", note: "Arose on Pinnacle subsidiary disposal; n/a to NVU." },
  { item: "Total comprehensive income / (loss)", tpl: "15,240", nvu: "(2,981,237)", status: "BOTH", note: "" },
  { item: "Attributable to NCI", tpl: "71", nvu: "(68,823)", status: "BOTH", note: "NVU NCI absorbs losses (deficit)." },
  { item: "Attributable to owners", tpl: "14,526", nvu: "(2,968,773)", status: "BOTH", note: "" },
  { item: "EPS — continuing / discontinued split", tpl: "9.12 / 0.77 c", nvu: "single LPS (0.44)c", status: "STRUCT_DIFF", note: "NVU reports one basic & diluted LPS; no ops split." },
]));

// ---- Section: Financial Position
children.push(H1("5.  Statement of Financial Position — line by line"));
children.push(comparisonTable([
  { item: "Cash and cash equivalents", tpl: "26,136", nvu: "2,075,432", status: "BOTH", note: "" },
  { item: "Trade and other receivables", tpl: "13,074", nvu: "34,328", status: "BOTH", note: "" },
  { item: "Contract assets", tpl: "2,458", nvu: null, status: "NOT_IN_NVU", note: "No contract assets recognised." },
  { item: "Inventories", tpl: "38,692", nvu: null, status: "NOT_IN_NVU", note: "Pre-scale; NVU holds no material inventory." },
  { item: "Financial assets at FVTPL", tpl: "360", nvu: null, status: "NOT_IN_NVU", note: "None held." },
  { item: "Other current assets / prepayments", tpl: "3,907 (Other)", nvu: "415,543 (Prepayments)", status: "BOTH", note: "NVU breaks out prepayments; template uses 'Other'." },
  { item: "Non-current assets held for sale", tpl: "6,000", nvu: null, status: "NOT_IN_NVU", note: "No disposal group." },
  { item: "Non-current receivables / loan receivable", tpl: "145", nvu: "441,902", status: "STRUCT_DIFF", note: "NVU's is the HTS related-party loan at fair value (6% discount)." },
  { item: "Investments — equity method", tpl: "34,192", nvu: null, status: "NOT_IN_NVU", note: "No associates/JVs." },
  { item: "Financial assets at FVOCI", tpl: "170", nvu: null, status: "NOT_IN_NVU", note: "None held." },
  { item: "Investment properties", tpl: "46,900", nvu: null, status: "NOT_IN_NVU", note: "NVU holds no investment property." },
  { item: "Property, plant and equipment", tpl: "116,698", nvu: "141,048", status: "BOTH", note: "" },
  { item: "Right-of-use assets", tpl: "318,292", nvu: "207,900", status: "BOTH", note: "" },
  { item: "Intangibles", tpl: "12,170", nvu: "10,494,942", status: "BOTH", note: "NVU's is dominated by the EMASS intangible (R&D/IP)." },
  { item: "Deferred tax asset", tpl: "14,490", nvu: null, status: "NIL_LOSS", note: "No DTA recognised — losses not yet probable of recovery." },
  { item: "Other non-current assets", tpl: "2,262", nvu: null, status: "NOT_IN_NVU", note: "" },
  { item: "Trade and other payables", tpl: "18,854", nvu: "492,133", status: "BOTH", note: "" },
  { item: "Contract liabilities", tpl: "2,269", nvu: "140,620", status: "BOTH", note: "" },
  { item: "Borrowings (current)", tpl: "4,500", nvu: "—", status: "NOT_IN_NVU", note: "NVU is equity-funded; no bank borrowings (interest-free related-party loan nil at 30 Jun)." },
  { item: "Lease liabilities (current)", tpl: "22,072", nvu: "109,937", status: "BOTH", note: "" },
  { item: "Derivative financial instruments", tpl: "122", nvu: null, status: "NOT_IN_NVU", note: "No derivatives." },
  { item: "Income tax payable", tpl: "6,701", nvu: "—", status: "NIL_LOSS", note: "No current tax — loss-making." },
  { item: "Employee benefits (current)", tpl: "8,084", nvu: "in provisions", status: "STRUCT_DIFF", note: "NVU folds employee entitlements into Provisions (8,189)." },
  { item: "Provisions (current)", tpl: "3,494", nvu: "8,189", status: "BOTH", note: "" },
  { item: "Other current liabilities", tpl: "2,083", nvu: null, status: "NOT_IN_NVU", note: "" },
  { item: "Liabilities held for sale", tpl: "4,000", nvu: null, status: "NOT_IN_NVU", note: "No disposal group." },
  { item: "Borrowings (non-current)", tpl: "19,000", nvu: "—", status: "NOT_IN_NVU", note: "No borrowings." },
  { item: "Lease liabilities (non-current)", tpl: "310,978", nvu: "100,578", status: "BOTH", note: "" },
  { item: "Deferred tax liability", tpl: "4,617", nvu: null, status: "NIL_LOSS", note: "None recognised." },
  { item: "Employee benefits / Provisions (non-current)", tpl: "10,818 / 1,445", nvu: null, status: "NOT_IN_NVU", note: "No material non-current employee/other provisions." },
  { item: "Net assets", tpl: "216,909", nvu: "12,959,638", status: "BOTH", note: "" },
  { item: "Issued capital", tpl: "182,953", nvu: "35,816,939", status: "BOTH", note: "" },
  { item: "Reserves", tpl: "4,045", nvu: "1,586,008", status: "BOTH", note: "" },
  { item: "Retained profits / (accumulated losses)", tpl: "12,548", nvu: "(24,337,829)", status: "BOTH", note: "NVU in accumulated deficit." },
  { item: "Non-controlling interest", tpl: "17,363", nvu: "(105,480)", status: "BOTH", note: "NVU NCI is a deficit (Fullveu HK absorbing losses)." },
  { item: "Total equity", tpl: "216,909", nvu: "12,959,638", status: "BOTH", note: "" },
]));

// ---- Section: Cash flows
children.push(H1("6.  Statement of Cash Flows — line by line"));
children.push(comparisonTable([
  { item: "Receipts from customers", tpl: "253,020", nvu: "131,765", status: "BOTH", note: "" },
  { item: "Payments to suppliers and employees", tpl: "(200,907)", nvu: "(2,082,572)", status: "BOTH", note: "" },
  { item: "Interest received", tpl: "543", nvu: "5,168", status: "BOTH", note: "" },
  { item: "Other revenue (operating)", tpl: "2,123", nvu: null, status: "NOT_IN_NVU", note: "Not separately presented by NVU." },
  { item: "Interest / finance costs paid", tpl: "(9,465)", nvu: "(48,888)", status: "BOTH", note: "Note: NVU FY interest paid (6,774) < H1 — interim/annual reclassification." },
  { item: "Income taxes paid", tpl: "(5,266)", nvu: "—", status: "NIL_LOSS", note: "No tax paid — loss-making." },
  { item: "Net cash from / (used in) operating", tpl: "40,048", nvu: "(1,994,527)", status: "BOTH", note: "Template generates cash; NVU burns it." },
  { item: "Payment for purchase of business (net of cash)", tpl: "(8,072)", nvu: "2,909 cash acquired (EMASS)", status: "STRUCT_DIFF", note: "EMASS = asset acquisition; NVU recorded net cash acquired, not a purchase outflow." },
  { item: "Payments for investments", tpl: "(510)", nvu: null, status: "NOT_IN_NVU", note: "" },
  { item: "Payments for property, plant and equipment", tpl: "— (pr. 1,524)", nvu: "— (FY 76,510)", status: "BOTH", note: "Nil in both current periods; NVU incurs PP&E spend in H2." },
  { item: "Proceeds from sale of subsidiary / investments / PP&E", tpl: "41 / 80 / 1,511", nvu: null, status: "NOT_IN_NVU", note: "No disposals." },
  { item: "Funds loaned to third parties (HTS)", tpl: null, nvu: "(183,239)", status: "NOT_IN_TPL", note: "NVU-specific related-party loan advance." },
  { item: "Net cash used in investing", tpl: "(6,950)", nvu: "(180,330)", status: "BOTH", note: "" },
  { item: "Proceeds from borrowings", tpl: "10,000", nvu: null, status: "NOT_IN_NVU", note: "No bank borrowings." },
  { item: "Dividends paid", tpl: "(22,037)", nvu: "—", status: "NIL_LOSS", note: "NVU has never paid a dividend." },
  { item: "Repayment of borrowings", tpl: "(4,500)", nvu: null, status: "NOT_IN_NVU", note: "No borrowings." },
  { item: "Interest-free related-party loan (proceeds/repayment)", tpl: null, nvu: "(120,000)", status: "NOT_IN_TPL", note: "NVU-specific interest-free loan from related party." },
  { item: "Proceeds from issue of shares (net)", tpl: null, nvu: "3,916,520", status: "NOT_IN_TPL", note: "NVU is equity-funded; template entity funds via borrowings/earnings." },
  { item: "Repayment of lease liabilities", tpl: "(12,692)", nvu: "(44,534)", status: "BOTH", note: "" },
  { item: "Net cash from / (used in) financing", tpl: "(29,229)", nvu: "3,751,986", status: "BOTH", note: "Opposite direction — NVU raising capital." },
  { item: "Effects of FX rate changes on cash", tpl: "9", nvu: "—", status: "NOT_IN_NVU", note: "NVU nets FX within OCI; no separate cash line." },
  { item: "Net change / opening / closing cash", tpl: "3,869 / 22,258 / 26,136", nvu: "1,577,129 / 498,303 / 2,075,432", status: "BOTH", note: "" },
]));

// ---- Section: Notes
children.push(H1("7.  Notes to the financial statements — structural mapping"));
children.push(P("Template carries 23 notes; NVU's interim carries 10. The table maps each template note to its NVU equivalent.", { italic: true }));
children.push(comparisonTable([
  { item: "N1 Material accounting policies", tpl: "Note 1", nvu: "Note 1", status: "BOTH", note: "" },
  { item: "N2 Operating segments", tpl: "3 segments + other", nvu: "3 product segments + Corporate", status: "BOTH", note: "Computer mfg/retail/dist. vs Semiconductor/EyeFly3D/Nanoshield." },
  { item: "N3 Revenue (AASB 15 disaggregation)", tpl: "Note 3", nvu: "no dedicated note", status: "STRUCT_DIFF", note: "NVU's Note 3 is LPS; revenue disaggregation is a candidate gap (B)." },
  { item: "N4 Share of associate profits", tpl: "Note 4", nvu: null, status: "NOT_IN_NVU", note: "No associates." },
  { item: "N5 Other income", tpl: "Note 5", nvu: "on face only", status: "NOT_IN_NVU", note: "Minor; NVU shows other income on the face." },
  { item: "N6 Expenses breakdown", tpl: "Note 6", nvu: "Note 6 = SBP", status: "STRUCT_DIFF", note: "NVU lacks a nature-based expenses note; candidate gap (B)." },
  { item: "N7 Discontinued operations", tpl: "Note 7", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "N8 Cash and cash equivalents", tpl: "Note 8", nvu: "on face only", status: "NOT_IN_NVU", note: "Minor." },
  { item: "N9 Held for sale", tpl: "Note 9", nvu: null, status: "NOT_IN_NVU", note: "None." },
  { item: "N10 Property, plant and equipment", tpl: "Note 10", nvu: "on face only", status: "NOT_IN_NVU", note: "Minor; PP&E small." },
  { item: "N11 Intangibles", tpl: "Note 11", nvu: "Note 8 (EMASS)", status: "BOTH", note: "NVU's is the headline EMASS asset-acquisition intangible." },
  { item: "N12/N13 Borrowings", tpl: "Notes 12, 13", nvu: null, status: "NOT_IN_NVU", note: "No borrowings." },
  { item: "N14 Issued capital", tpl: "Note 14", nvu: "Note 5", status: "BOTH", note: "" },
  { item: "N15 Dividends", tpl: "Note 15", nvu: "Note 4 (nil)", status: "NIL_LOSS", note: "No dividends." },
  { item: "N16 Fair value measurement", tpl: "Note 16", nvu: null, status: "NOT_IN_NVU", note: "NVU measures the HTS loan at fair value but gives no FV-hierarchy note (candidate gap)." },
  { item: "N17/N18 Contingent assets / liabilities", tpl: "Notes 17, 18", nvu: "Note 9 (commitments & contingencies)", status: "BOTH", note: "Combined by NVU." },
  { item: "N19 Related party transactions", tpl: "Note 19", nvu: "Note 7", status: "BOTH", note: "" },
  { item: "N20 Business combinations (AASB 3)", tpl: "Note 20", nvu: "EMASS = AASB 2 asset acq.", status: "STRUCT_DIFF", note: "Template only covers AASB 3; NVU's is an asset acquisition." },
  { item: "N21 Events after reporting period", tpl: "Note 21", nvu: "Note 10", status: "BOTH", note: "" },
  { item: "N22 Reconciliation of profit to operating cash", tpl: "Note 22", nvu: null, status: "NOT_IN_NVU", note: "NVU does not present this reconciliation (candidate gap B)." },
  { item: "N23 Earnings per share", tpl: "Note 23", nvu: "Note 3 (LPS)", status: "BOTH", note: "" },
  { item: "Share-based payments (own note)", tpl: "within notes", nvu: "Note 6", status: "NOT_IN_TPL", note: "NVU elevates SBP to its own note (performance rights for EMASS)." },
]));

// ---- Summary
children.push(H1("8.  Summary of differences by category"));

children.push(H2("(A) Template items absent from NVU due to a different business model — not deficiencies"));
[ "Inventories, contract assets and 'real-time' inventory management disclosure (NVU is pre-scale).",
  "Investments in associates/JVs and share of associate profits (NVU has none).",
  "Investment properties; financial assets at FVTPL and FVOCI; derivatives and cash-flow hedge accounting.",
  "Bank borrowings (current and non-current) and proceeds/repayments of borrowings — NVU is equity-funded.",
  "Dividends, dividend franking and dividend reinvestment cash flows — NVU has never paid a dividend.",
  "Income tax expense, current tax payable and deferred tax balances — NVU is loss-making with no recognised tax asset.",
  "Discontinued operations, loss of control / disposal of subsidiaries, and assets/liabilities held for sale.",
  "Employee-benefits provisions disclosed separately (NVU folds these into Provisions).",
  "Business combination accounting under AASB 3 (NVU's EMASS is an AASB 2 asset acquisition).",
].forEach(t => children.push(bullet(t)));

children.push(P("Each point cites the governing standard.", { italic: true, color: "808080" }));
[ "AASB 15 / IFRS 15 — revenue disaggregation: NVU has no dedicated revenue note (template Note 3); disaggregate by geography and timing of transfer.",
  "AASB 101 / IAS 1 — nature-based expenses, including employee benefits expense: NVU shows only function-level lines on the face (template Note 6).",
  "AASB 107 / IAS 7 — reconciliation of loss after tax to net cash used in operating activities is absent from NVU's interim (template Note 22). Note: NVU's ANNUAL does include it (note 9b), so this is interim-specific.",
  "AASB 13 / IFRS 13 — fair-value-measurement note: NVU carries the HTS loan receivable at fair value (6% discount) but provides no Level 1/2/3 hierarchy disclosure (template Note 16).",
  "AASB 133 / IAS 33 — present diluted LPS as its own line even where equal to basic (NVU combines them; permitted while anti-dilutive).",
  "AASB 7 / IFRS 7 — credit-risk / ECL ageing on receivables is thin (low materiality at this scale, but expected).",
  "AASB 101 / IAS 1 — depreciation and amortisation is shown only in the segment note, not on the P&L face.",
  "AASB 134 / AASB 108 — interim/annual consistency: H1 interest paid (48,888) and lease repayments differ markedly from the audited FY figures, indicating reclassification between the reviewed interim and audited annual numbers.",
].forEach(t => children.push(bullet(t)));

children.push(H2("(C) NVU-specific items the template does not anticipate"));
[ "AASB 2 asset acquisition (EMASS) with the $10.47m consideration allocated to an intangible (R&D/IP) and performance-rights consideration — no template equivalent.",
  "Non-controlling interest running at a deficit (Fullveu HK 49% minority absorbing losses) — the template NCI is positive.",
  "Interest-free related-party loan within financing, and a related-party loan receivable from HTS within investing, measured at fair value.",
  "Share-based payment expense presented as a discrete line on the P&L face and as its own note.",
  "Research costs as a separate expense line (R&D-stage company).",
  "Reporting in full dollars (not $'000) and a 31 December year-end versus the template's 30 June presentation.",
].forEach(t => children.push(bullet(t)));

children.push(P(""));
children.push(P("End of half-year comparison.", { italic: true, color: "808080" }));

const doc = new Document({
  creator: "NVU financial analysis", title: "NVU vs Accurri — Half-Year Differences",
  styles: { default: { document: { run: { font: "Calibri" } } } },
  sections: [{ properties: { page: { margin: { top: 720, bottom: 720, left: 720, right: 720 } } }, children }],
});

Packer.toBuffer(doc).then(buf => {
  const target = "NVU_vs_Accurri_Differences.docx";
  try {
    fs.writeFileSync(target, buf);
    console.log("Wrote", target, buf.length, "bytes");
  } catch (e) {
    if (e.code === "EBUSY" || e.code === "EPERM") {
      fs.writeFileSync("_work/NVU_vs_Accurri_Differences.docx", buf);
      console.log("TARGET LOCKED — wrote _work/NVU_vs_Accurri_Differences.docx", buf.length, "bytes (close the open file, then copy over).");
    } else { throw e; }
  }
});
