# Financial Controller feedback log

Capture FC review comments here. Each row maps a comment to the change it drives.
Most feedback is actioned by editing `config/standards_checklist.json` (no code change) —
that is the durable knowledge base. Wording/layout feedback is actioned in
`lib/build_report.js`; detection-accuracy feedback in `lib/review.py`.

## How feedback maps to changes

| Type of feedback | Where it changes |
|---|---|
| "Add a disclosure we should test for" | add an item to `standards_checklist.json` → `items[]` |
| "Remove / this isn't relevant" | delete or set `appliesTo: []` on the item |
| "This is flagged but we already disclose it" (false NOT FOUND) | broaden the item's `detect` keywords |
| "This shows present but the note is thin" (false PRESENT) | tighten via `detectAll` groups, or set `category: "B"` so it always surfaces |
| "Only relevant when X exists" | set/adjust `expectedWhen` triggers |
| "Wrong importance" | change `materiality` (high/medium/low) — reorders recommendations |
| "Reword the recommendation" | edit the item's `recommendation` text |
| "Report layout / sections / branding" | `lib/build_report.js` |
| "Ticker/entity/type detected wrong" | `lib/review.py` (or just pass `-Ticker` / `-Type`) |

## Open feedback

| # | Date | From | Comment | Proposed change | Status |
|---|------|------|---------|-----------------|--------|
| 1 |      |      |         |                 | open   |

## Resolved

| # | Date | Comment | Change made |
|---|------|---------|-------------|
| R1 | 2026-06-18 | Section 2 wording too loose / unclear provenance; reader should see the standard & where it's referenced | Rewrote section 2 ("Disclosures to confirm, by standard"); every item now cites the standard **and paragraph** (e.g. AASB 15 ¶114–115); removed "boilerplate" language; added "review aid, not an audit" caveat. Clauses stored in `standards_checklist.json`. |
| R2 | 2026-06-18 | Tool flagged ECL/ageing (AASB 7) on a ~$11k receivables balance — no materiality lens | Added qualitative vs quantitative assessment. Quantitative items (ECL, leases, contract balances, intangibles, fair value) are gated on materiality (default 5% of total assets, or `--materiality`); below-threshold items show "Below materiality" with the figure, not flagged as gaps. Qualitative items assessed regardless of amount. |
| R3 | 2026-06-18 | Auditor: AASB 15 disaggregation IS in the report (audited & lodged), just presented differently from the standard's table; tool over-prompted ("geographic alone insufficient") | Researched NVU's disclosure: disaggregation is satisfied across the **segment note** (revenue by product/segment), the **geographic** revenue split, and **timing of transfer** in the revenue policy (point-in-time vs over-time). Broadened AASB 15 detection to recognise these, reworded the recommendation to a confirm-prompt, and added a reusable `representationNote` field surfaced as "May be represented differently: …". General lesson: a requirement can be met in an alternative presentation — point the reviewer to where it likely lives rather than asserting a deficiency. |

| R4 | 2026-06-18 | Section 4: add a red/amber/green opportunity status per announcement — GP is a financial-services firm using the list to spot where to offer its services (reviewed growthpartnersadvisory.com) | Added a business-development lens. `config/opportunity_map.json` maps announcement type/headline tokens → RAG + GP service (Transaction Readiness, Financial Reporting, Audit Readiness, Business Process Redesign, Commercial Opportunities). `lib/opportunity.py` classifies each announcement; report shows an opportunity summary, a "Key opportunities (green)" list, and a RAG column. NVU: 16 green / 24 amber / 52 red. RAG direction: GREEN = clear opportunity. CONFIRM items: Progress Report (amber) and Trading Halt/Suspension (amber). |

| R5 | 2026-06-18 | The overt "Importance to GP → Transaction Readiness" list is too salesy for a client-shared doc; want one document, client-shareable, that flags opportunity internally but subtly | Split into (a) a neutral **client-facing** Section 4 "Corporate activity" — Theme + Significance (subtle shading, no RAG/GP wording), and (b) a page-broken **internal appendix** "Engagement opportunities (REMOVE BEFORE SENDING)" with the RAG + GP service + rationale ranked by importance. Verified the client portion contains zero BD language. Added neutral `theme` per type and an importance layer (acquisitions rank above periodic reports). |

| R6 | 2026-06-18 | Auditor: revisit section 2 — at least 3 findings are actually addressed, just represented differently (as with AASB 15) | Researched the NVU annual and resolved them. Added two resolution states: **Addressed** (present in standard form — Critical judgements Note 3, Income-tax recon Note 8, Operating-cash recon Note 9b, Going concern Note 2.3) and **Represented differently** (present, non-standard form — AASB 15 disaggregation, Non-cash items in SOCIE/issued-capital, Diluted EPS combined line + anti-dilutive statement). Encoded generically via `representationNote` + `divergent` flag; no open "confirm" gaps remain for the annual. |

| R7 | 2026-06-18 | Internal appendix: replace the "GP service & rationale" text column with a checkbox matrix of GP's service lines (tick on match, else blank) | Tagged each opportunity rule with its canonical GP service line(s) (`services[]` in opportunity_map.json) and rebuilt the appendix table with 5 columns — Transaction Readiness, Financial Reporting, Business Process Redesign, Commercial Opportunities, Audit Readiness — showing ✓ where matched. e.g. acquisition → Transaction Readiness; capital raise → Transaction Readiness + Financial Reporting. |

| R8 | 2026-06-18 | Importance and RAG columns represent the same thing — merge into RAG | Removed the Importance column from the internal appendix; RAG now carries the priority (green = high-value). Ranking preserved via row order (sorted by priority), so acquisitions still sit above periodic reports within green. |

| R9 | 2026-06-18 | Remove RAG column too — fold its colour into the checkboxes; reorder to Date, Announcement, Type, then service checkboxes | Internal appendix is now Date · Announcement · Type · [5 service checkboxes]. The ✓ cell is filled with the item's RAG colour (green = high-value, amber = monitor), so colour conveys priority without a dedicated column. e.g. "Reinstatement to Quotation" → amber ✓ under Transaction Readiness. |

| R10 | 2026-06-19 | Map everything found (full ASX taxonomy), exclude nothing — baseline for next-phase learning from user experience | Researched the market-wide ASX taxonomy (20 header types via MAP facets + 86 granular sub-types; GN14/GN8 for usage & auto-market-sensitive list). Rebuilt `config/opportunity_map.json` to 17 rules covering 86/86 types (21 GREEN / 26 AMBER / 39 RED) — nothing falls through. Added rules: earnings_guidance, leadership_change, reporting_other, legal_regulatory, buyback_capital, distribution_routine, products_routine; extended existing rules. Normalised apostrophe variants. Research saved to `research/`. |

## Sample under review (baseline)
- `output/Nanoveu_Limited_Annual_Disclosure_Review.docx`
- `output/Nanoveu_Limited_HalfYear_Disclosure_Review.docx`
- Checklist version: 1.0 (`config/standards_checklist.json`)
