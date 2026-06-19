# Disclosure Review Kit

Drop in any ASX **half-year (Appendix 4D)** or **annual (Appendix 4E)** report PDF and get a
Word report that screens it against an **AASB / IFRS disclosure checklist**, recommends
disclosures, and pulls the entity's recent **ASX announcements**.

Built for the same framework as the Accurri "Example Financial Statements" (Pinnacle) model
accounts: Australian Accounting Standards (AASB, IFRS-equivalent) + Corporations Act + ASX
Listing Rules.

---

## Quick start (Windows / PowerShell)

```powershell
cd "disclosure-review-kit"
.\run.ps1 -Report "C:\path\to\Some Annual Report.pdf"
```

Outputs land in `output\`:
- `findings.json` — structured results
- `<Entity>_Disclosure_Review.docx` — the formatted report

### Common options
```powershell
.\run.ps1 -Report ".\input\half.pdf"                 # auto-detect type, ticker, entity; fetch ASX
.\run.ps1 -Report ".\input\annual.pdf" -DownloadAsx  # also download announcement PDFs locally
.\run.ps1 -Report ".\input\report.pdf" -Ticker NVU   # force the ticker
.\run.ps1 -Report ".\input\report.pdf" -Type annual  # force the report type
.\run.ps1 -Report ".\input\report.pdf" -NoAsx        # skip ASX entirely
```

### Run the steps directly (any OS)
```bash
python lib/review.py --report "../NVU Annual Report.pdf" --download-asx
node   lib/build_report.js output/findings.json "output/Report.docx"
```

---

## What it produces

The Word report has four sections:
1. **Executive summary** — framework basis + a present / not-found / N/A count.
2. **Recommended disclosures & review points** — every keyword *miss* (likely absent) PLUS
   every category-B *disclosure-quality* expectation (confirm it is adequately addressed, since
   boilerplate can mask a thin disclosure). Each cites the governing standard and is graded
   by materiality.
3. **Full checklist results** — every applicable item, colour-coded
   PRESENT (green) / NOT FOUND (red) / N/A (grey).
4. **ASX announcements** — recent announcements (live from ASX, or from a local folder),
   with price-sensitive and financially-relevant items flagged for cross-check against the
   report's "events after the reporting period" note.

---

## ASX announcements — windowed history engine (`lib/asx_history.py`)

The engine pages through the ASX (markitdigital) **markets** announcements endpoint — the same
one the asx.com.au announcements page calls:

```
/asx-research/1.0/markets/announcements?entityXids=<xid>&page=<n>&itemsPerPage=100
```

1. **Resolve** the ticker to its ASX entity xid — automatically, via
   `/asx-research/1.0/search/predictive?searchText=<CODE>` (`xidEntity`). A small `XID_CACHE`
   is a fast-path; `--xid` overrides.
2. **Paginate** `itemsPerPage=100`, `page=0,1,2…`, accumulating until the oldest item passes
   the trailing-12-month boundary.
3. **Merge** any local PDFs, **de-duplicate** (API document key ↔ local filename), clamp to the
   12-month window, and (with `--download`) save the PDFs.

> This endpoint **paginates and returns the full history** (e.g. ~92 announcements for NVU over
> 12 months, vs the 5 the `/companies/{ticker}/announcements` widget returns). It uses the
> public static Bearer token the ASX site uses. Works for **any ASX code** — the ticker→xid
> resolution is automatic. If resolution fails (e.g. offline), the engine falls back to the
> capped latest-5 widget and says so.

**Local folder** is still merged: drop PDFs into `announcements\<TICKER>\` (keep the
`YYYY-MM-DD_…` prefix) and they're combined and de-duplicated with the live feed.

- **Window anchor:** trailing 12 months from today by default (latest announcements + recent
  subsequent events). Pass `-AsOfPeriod` / `--as-of-period` to anchor to the report's own
  period-end instead (review of the reporting year).
- **Ticker** is auto-detected (override with `-Ticker`).
- Run the engine standalone: `python lib/asx_history.py NVU --months 12 --download`.

---

## How it works

```
run.ps1
 └─ lib/review.py        extract PDF text (pdfplumber) → detect entity/ticker/type/period
 │                        → run config/standards_checklist.json → output/findings.json
 │                        → calls lib/asx_history.py (windowed 12-month announcements)
 └─ lib/build_report.js  findings.json → Word report (docx)
```

The **durable IP is `config/standards_checklist.json`** — a standards-keyed list of expected
disclosures. Each item has:

| field | meaning |
|---|---|
| `standard` | AASB / IFRS / Corporations Act / ASX LR reference |
| `appliesTo` | `interim`, `annual`, or both |
| `expectedWhen` | trigger phrases; if none appear the item is **N/A** (a business-model difference, not a gap) |
| `detect` | any-of keywords → PRESENT if matched |
| `detectAll` | list of groups; **all** groups must match (use for precision, e.g. revenue disaggregation needs both a disaggregation term *and* a timing-of-transfer term) |
| `category` | `B` = disclosure-quality point that is always surfaced as a review item |
| `materiality` | `high` / `medium` / `low` — sorts the recommendations |
| `recommendation` | the action text shown in the report |

### Opportunity RAG (business-development lens)
Section 4 flags each announcement red/amber/green for **Growth Partners Advisory** business
development — where an announcement signals a need GP can serve:
- **Green** = clear opportunity (M&A, capital raises, periodic reports/audit, CFO change)
- **Amber** = possible — monitor (market-status events, ownership/board change, operational
  milestones, governance/auditor change)
- **Red** = routine administrative / IR — no direct trigger

The mapping (type/headline token → RAG + GP service + rationale) lives in
`config/opportunity_map.json` and is fully tunable; `lib/opportunity.py` applies it. The report
shows an opportunity summary, a "Key opportunities (green)" shortlist, and a RAG column.

### Qualitative vs quantitative assessment (materiality)
Each checklist item is either **qualitative** (assessed on presence regardless of amount — e.g.
related parties, KMP, going concern, segments) or **quantitative** (`assessment: "quantitative"`
with `balanceCaptions`). For quantitative items the engine reads the underlying balance from the
report and compares it to materiality:
- **Materiality** = `--materiality <AUD>` if given, else `--materiality-pct` (default **5%**) of
  total assets (auto-extracted). Stated in the report's executive summary.
- If the balance is **below** materiality → status **Below materiality** (figure shown), not a gap.
- Set your own planning materiality with `--materiality 250000` (and via `run.ps1 -Materiality`).

### Extending the checklist
Add an object to the `items` array. No code change needed — `review.py` reads it at runtime.
Keep `detect`/`detectAll`/`expectedWhen` lowercase-friendly (matching is case-insensitive).

---

## Limitations (read this)

This is a **first-pass screen**, not an audit, review, or assurance opinion. Detection is
keyword-based over extracted text, so:
- A disclosure can be marked **PRESENT** on boilerplate policy wording even if the substantive
  note is thin — that is why category-B items are *always* listed as "confirm adequacy".
- A **NOT FOUND** is a strong hint the disclosure is missing, but confirm against the source.
- Scanned/image-only PDFs need OCR first (this kit reads text-based PDFs).
- Always have a qualified person confirm findings before relying on them.

---

## Requirements
- Python 3 with `pdfplumber` (`pip install pdfplumber`)
- Node.js with `docx` (`npm install docx`, already vendored in this folder)
- Internet access for live ASX announcements (optional; local fallback otherwise)
