# Disclosure Review Kit — Test Cases for Reviewer Sign-off

Each improvement is expressed as a test case: input → expected result → actual (verified on the
Nanoveu Limited FY2025 annual and HY2025 half-year reports). Status reflects verification in build.

**How to reproduce:** `cd disclosure-review-kit` then `.\run.ps1 -Report "..\NVU Annual Report.pdf"`
(outputs to `output\`). Half-year: `.\run.ps1 -Report "..\NVU Half YEar Report.pdf"`.

Ref = related feedback item in `FEEDBACK.md`.

---

## A. Document detection

| ID | Scenario / Input | Expected result | Actual (verified) | Status |
|----|------------------|-----------------|-------------------|--------|
| TC-01 | Annual PDF, no entity supplied | Entity auto-detected from the report | "Nanoveu Limited" | Pass |
| TC-02 | Annual PDF mentions other companies' ASX codes in the remuneration report | Detect the subject ticker, not a director's other directorship | "NVU" (not "I88") | Pass |
| TC-03 | Appendix 4D vs 4E cover | Report type auto-classified | HY → interim; Annual → annual | Pass |
| TC-04 | Report period-end | Detected for windowing | 31 Dec 2025 / 30 Jun 2025 | Pass |

## B. Standards checklist & section 2 (disclosure screen)

| ID | Scenario / Input | Expected result | Actual (verified) | Ref | Status |
|----|------------------|-----------------|-------------------|-----|--------|
| TC-05 | Any flagged disclosure | Cites the standard AND paragraph | e.g. "AASB 15 ¶114–115", "AASB 112 ¶81(c)" | R1 | Pass |
| TC-06 | Section 2 intro | Plain provenance + "review aid, not an audit" caveat; no loose "boilerplate" wording | Present | R1 | Pass |
| TC-07 | ECL/ageing on $11k receivables | Not flagged as a gap (immaterial) | "Below materiality" (balance $484k < $678k) | R2 | Pass |
| TC-08 | Materiality threshold | Default 5% of total assets; `--materiality` override; stated in report | $677,746 (5% of $13.55m), overridable | R2 | Pass |
| TC-09 | Intangibles $10.5m | Stays flagged (above materiality) | Present / assessed | R2 | Pass |
| TC-10 | AASB 15 disaggregation across segment + geography + timing-in-policy | Recognised, not a false gap | "Represented differently" | R3 | Pass |
| TC-11 | A disclosure present but not in the standard's form | Surfaced as a consultation point, not a clean pass | "Represented differently" status + note | R3 | Pass |
| TC-12 | Critical judgements, income-tax recon, operating-cash recon, going concern | Detected in standard form → resolved | "Addressed" (Notes 3, 8, 9b, 2.3) | R6 | Pass |
| TC-13 | Non-cash items, diluted EPS, AASB 15 | Present in non-standard form → consultation point | "Represented differently" (3 items) | R6 | Pass |
| TC-14 | Annual section 2 overall | No open "confirm" gaps remaining | 0 open gaps (all Addressed / Diff / Below materiality) | R6 | Pass |
| TC-15 | Conditional item with no trigger (e.g. associates, inventory) | Marked Not Applicable, not a gap | "N/A" | — | Pass |

## C. ASX announcements engine

| ID | Scenario / Input | Expected result | Actual (verified) | Status |
|----|------------------|-----------------|-------------------|--------|
| TC-16 | Free `companies/{ticker}` endpoint | Cap identified, no pagination | Returns only latest 5; ignores page/date params (proven) | Pass |
| TC-17 | Paginated `markets/announcements` endpoint | Full 12-month history retrieved | 92 announcements for NVU | Pass |
| TC-18 | Any ASX code (no hard-coding) | Ticker → entity xid auto-resolved | NVU/BHP/CBA/WBC/DRO resolved live | Pass |
| TC-19 | Counts | Total + price-sensitive reported | 92 total, 33 price-sensitive | Pass |
| TC-20 | API result + local PDFs for same announcement | Merged and de-duplicated (no double count) | 5 API + 2 local → 7 unique | Pass |
| TC-21 | Trailing 12-month window | Older items clamped out; window stated | 2025-06-18 → 2026-06-18 | Pass |
| TC-22 | ASX API unreachable | Graceful fallback to local folder | Falls back; reports source | Pass |

## D. Opportunity / business-development lens

| ID | Scenario / Input | Expected result | Actual (verified) | Ref | Status |
|----|------------------|-----------------|-------------------|-----|--------|
| TC-23 | Each announcement | RAG opportunity vs GP services | 16 green / 24 amber / 52 red | R4 | Pass |
| TC-24 | Acquisition vs annual report | Acquisition ranks above periodic report | Acquisition = High; Annual report = Medium | R5 | Pass |
| TC-25 | Client-facing section | Neutral; no "opportunity / GP service / RAG" wording | Zero BD terms in client portion (verified) | R5 | Pass |
| TC-26 | Internal appendix | Page-broken, "REMOVE BEFORE SENDING", RAG + GP service + rationale | Present, ranked by importance | R5 | Pass |
| TC-27 | Mapping change request | Tunable without code change | All in `config/opportunity_map.json` | R4/R5 | Pass |

## E. Financial model (original deliverable)

| ID | Scenario / Input | Expected result | Actual (verified) | Status |
|----|------------------|-----------------|-------------------|--------|
| TC-28 | `scripts/recalc.py NVU_Financial_Model.xlsx` | Zero formula errors | Pass: 0 errors across 436 cells | Pass |
| TC-29 | Reconciliations | Net loss, net assets = total equity, cash roll-forward tie | All tie (e.g. FY loss −7,601,225) | Pass |
| TC-30 | H2 derivation | H2 = FY − H1 | Verified (e.g. H2 net loss −4,563,629) | Pass |

## F. Output robustness

| ID | Scenario / Input | Expected result | Actual (verified) | Status |
|----|------------------|-----------------|-------------------|--------|
| TC-31 | Output .docx open in Word | Build does not fail; writes timestamped copy, consolidates when free | Handled | Pass |
| TC-32 | Generated .docx | Valid OOXML; all sections present | zip OK; sections 1–4 + appendix present | Pass |

---

## Open items for reviewer decision (not defects)

| ID | Item | Question for reviewer |
|----|------|-----------------------|
| Q-01 | Materiality threshold | Confirm 5% of total assets, or set GP planning materiality. |
| Q-02 | Diluted EPS classification | "Represented differently" vs fully "Addressed" under AASB 133 ¶43 (anti-dilutive). |
| Q-03 | Opportunity priority order | Confirm acquisition > capital raise > reporting ranking. |
| Q-04 | `[CONFIRM]` opportunity rules | Progress Reports (Amber) and Trading Halts (Amber) — keep / promote / drop. |
| Q-05 | Paragraph references | Auditors to confirm exact AASB sub-paragraphs cited in section 2. |
| Q-06 | Internal appendix | Keep as a page in the same file, or switch to a separate `_Internal.docx`. |
