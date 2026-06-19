# ASX Announcement Taxonomy — Research & Mapping Coverage

Research to ensure `config/opportunity_map.json` maps every ASX announcement type to the right
Growth Partners service. Source data is market-wide (not NVU-specific).

## 1. How ASX classifies announcements (from Guidance Note 14)

- Announcements are lodged via **ASX Online → Market Announcements Platform (MAP)**, which
  auto-generates a standard-format PDF and **auto-supplies a header**.
- Classification is **two-level: Announcement Header Type → Header Sub-type** (this matches the
  API exactly — see §2/§3).
- The **Market Announcements Office (MAO)** catalogues each announcement against the entity, and
  **if it is market-sensitive it initiates a brief trading halt** so the market can absorb it.
- **Market sensitive** = information a reasonable person would expect to materially affect price
  (Listing Rule 3.1).
- **Auto-classified market-sensitive (sensitivity cannot be changed by the entity):**
  - Periodic Reports → Monthly/Quarterly Activities (Appendix 4C/5B), Half-Yearly Reports &
    Accounts, **Preliminary Final Report**, **Profit Guidance**
  - Mining/Oil & Gas Exploration → Monthly/Quarterly Activities (Appendix 5B)
  - Takeovers → Intention to make a Takeover Bid, Bidder's/Target's Statement (+ supplementary),
    Variation of Takeover Bid
  - **These auto-sensitive types are almost all GP's high-value triggers** (periodic reporting +
    takeovers), which validates the GREEN mapping.

Sources: [GN14 — Market Announcements Platform](https://www.asx.com.au/content/dam/asx/rules-guidance-notes-waivers/asx-listing-rules/guidance-notes/gn14-asx-market-announcements-platform.pdf) ·
[GN8 — Continuous Disclosure (LR 3.1)](https://www.asx.com.au/documents/rules/Guidance_Note_8.pdf)

## 2. Top-level Header Types (20) — from the MAP facets API

`issued capital · periodic reports · security holder details · progress report · company
administration · notice of meeting · asx announcement · distribution announcement · structured
products · quarterly activities report · quarterly cash flow report · other · asset acquisition &
disposal · mfund · chairman's address · commitments test entity quarterly reports · letter to
shareholders · takeover announcements/scheme announcements · asx query · notice of call`

(Full list + market-wide counts and the 86 granular sub-types are in `asx_taxonomy.json`.)

## 3. Mapping coverage — FULL (86 of 86 granular sub-types mapped)

> **Status: applied.** Every granular type is now explicitly classified in
> `config/opportunity_map.json` (17 rules) — nothing falls through to the default. Distribution
> across the taxonomy: **21 GREEN, 26 AMBER, 39 RED**. The judgement-call items (§3d) were given a
> reasonable baseline assignment so the **next phase can learn/adjust from user experience**.
> Apostrophe variants (straight / curly / missing) are normalised in the matcher.

Rules added in this pass: `earnings_guidance` (Profit Guidance/Trading Update → GREEN),
`leadership_change` (CEO/Chair/Co-Sec → AMBER), `reporting_other` (NTA backing, results-date
notice, sustainability → AMBER), `legal_regulatory` (ASX query, litigation → AMBER),
`buyback_capital` (Market/ESS buy-back → AMBER), `distribution_routine` & `products_routine`
(dividends, structured products, funds → RED). Existing rules extended (asset disposal, takeover
statements, security purchase plan, debt facility, listing status, etc.).

### Original gap analysis (retained for context) — 43 of 86 were mapped before this pass

Run `python research/coverage_check.py` (or `lib`-based) to regenerate. Key outcome:

### 3a. Correctly mapped (sample)
Asset Acquisition / Scheme of Arrangement / Takeover-Other → **GREEN Transaction Readiness**;
Placement / Appendix 3B → **GREEN Transaction Readiness + Financial Reporting**; Annual Report /
Full Year Accounts / Audit Review → **GREEN Financial Reporting + Audit Readiness**; Trading
Halt/Suspension/Reinstatement → **AMBER Transaction Readiness**; substantial-holding & director
changes → **AMBER**; Appendix 2A/3G/3H, cleansing, presentations, proxies → **RED routine**.

### 3b. GP-relevant types currently UNMAPPED — recommended additions (for sign-off)
| Granular type(s) | Recommended | GP service |
|---|---|---|
| **Asset Disposal** | GREEN | Transaction Readiness (M&A both ways) |
| **Supplementary Bidder's / Target's Statement**, Intention to make a Takeover Bid, Variation of Takeover Bid | GREEN | Transaction Readiness |
| **Security Purchase Plan**, **Non-Renounceable Issue**, Alteration to issued capital | GREEN | Transaction Readiness + Financial Reporting |
| **Debt Facility** | GREEN/AMBER | Transaction Readiness |
| **Profit Guidance**, **Trading Update** (auto market-sensitive) | GREEN/AMBER | Commercial Opportunities + Financial Reporting |
| **Notification of Results/Reporting Date** | AMBER | Financial Reporting + Audit Readiness (lead-time signal — you know when they report) |
| **Net Tangible Asset Backing**, **Periodic Reports - Other**, **Sustainability/Climate Action Report** | GREEN/AMBER | Financial Reporting (+ Audit) |
| **CEO/Managing Director**, **Chair**, **Company Secretary** Appointment/Resignation | AMBER | Leadership change (extend `cfo_finance_lead`/`ownership_board`) |
| **Legal Proceedings** | AMBER | Advisory / Transaction Readiness |

### 3c. Correctly routine — leave RED (no change)
Dividend/Interest Record/Pay/Rate dates, Dividend Reinvestment Plan, Daily Share Buy-Back Notice,
Structured Products / mFund / Daily Fund Update, Company/Registered address details, Trading
Policy, Notice Pending, Response to ASX Query, MAP Test, End of Day, Proxy Form, Notices of Meeting.

### 3d. Judgement calls flagged (don't guess — GP to decide)
1. **Buy-backs** — *Daily Share Buy-Back Notice* (high volume) is routine RED; but a *Market
   Buy-Back* / *Employee Share Scheme Buy-Back* initiation could be a capital-advisory opportunity.
2. **Profit Guidance / Trading Update** — GREEN (active earnings event) or AMBER (monitor)?
3. **Notification of Results/Reporting Date** — treat as a valuable lead-time signal (AMBER) or noise?

## 4. Next phase — learn from user experience
The full taxonomy is now mapped as a **baseline**. The judgement calls (buy-backs, Profit Guidance
GREEN vs AMBER, results-date-notice value) are first guesses to be refined once the model can learn
from how GP actually converts each signal. Suggested learning loop:
- Capture per-announcement outcomes (did GP pursue it? did it convert?) against `ruleId`/`rag`.
- Feed back to re-weight `priority`/`rag` and add/adjust `match` tokens in `config/opportunity_map.json`.
- Keep the config as the single source of truth so learning is data-in-config, not code changes.
