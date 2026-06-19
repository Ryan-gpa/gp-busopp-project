# Co-work POC — CLAUDE.md

## What this project is

Two related workstreams in one folder:

1. **NVU financial modelling** — one-off, **COMPLETE**. Excel model, two Word comparison reports.
2. **Disclosure Review Kit** — reusable ASX disclosure screening tool. CLI is production-ready. **Web app is substantially built** (see below).

---

## Folder map

```
Co-work POC/
├── NVU_Claude_Code_Prompt.md        — original 4-task brief (reference only)
├── NVU Annual Report.pdf            — NVU FY2025 (Appendix 4E)
├── NVU Half YEar Report.pdf         — NVU HY2025 (Appendix 4D)
├── NVU_Financial_Model.xlsx         — DONE: Excel P&L / BS / CF / Segments / KPIs / Ratios
├── NVU_vs_Accurri_Differences.docx  — DONE: HY2025 vs Pinnacle Interim comparison
├── Annual_Differences.docx          — DONE: FY2025 vs Pinnacle Annual comparison
├── disclosure-review-kit/           — CLI engine (THE DURABLE IP)
└── webapp/                          — React + FastAPI web app (SUBSTANTIALLY BUILT)
```

### disclosure-review-kit/

```
run.ps1                              — main entry point (Windows)
lib/
  review.py                          — PDF extract → checklist screen → findings.json
  asx_history.py                     — paginated ASX announcement engine (12-month window)
  opportunity.py                     — opportunity RAG classifier
  build_report.js                    — findings.json → Word report (.docx)
  docx_lib.js                        — shared Word helpers
config/
  standards_checklist.json           — AASB/IFRS disclosure items (the durable IP)
  opportunity_map.json               — ASX type → GP service RAG mapping (17 rules, 86/86 types)
  user_prefs.json                    — persisted user preferences (excludedTypes + typeHistory)
output/
  findings.json                      — latest run results
  Nanoveu_Limited_*.docx             — generated Word reports
announcements/NVU/                   — local announcement PDFs + index.json
research/
  ASX_ANNOUNCEMENT_TAXONOMY.md      — full 86-type taxonomy mapping notes
```

### webapp/

```
api/
  main.py                  — FastAPI backend (7 endpoints, see below)
  requirements.txt         — fastapi uvicorn python-multipart
src/
  main.tsx                 — React entry point
  App.tsx                  — Router (/ = UploadPage, /results = ResultsPage)
  types.ts                 — TypeScript interfaces: FindingsJSON, ResultItem, AsxItem,
                             AsxBlock, Summary, UserPrefs, TypeHistory
                             + helpers: renderStatus(), formatCurrency(), formatDate()
                             + constants: GP_SERVICES, RENDER_STATUS_ORDER
  pages/
    UploadPage.tsx          — PDF upload form + options → POST /api/review → navigate /results
    ResultsPage.tsx         — 4-tab results, sticky generate bar, prefs loading, TypeConfigPanel
  components/
    ui/                     — shadcn/ui primitives (button, card, tabs, progress) — written manually
    app/
      SummaryCards.tsx      — entity header + 4 status cards + materiality notice
      DisclosuresTab.tsx    — filterable/sortable checklist results table
      CorporateActivityTab.tsx — announcement table with checkboxes, hyperlinks, Configure button
      OpportunitiesTab.tsx  — internal-only RAG service matrix
      TypeConfigPanel.tsx   — slide-over panel: types grouped by RAG, history badges, Save & Apply
      StatusChip.tsx        — renderStatus → coloured chip
index.html
vite.config.ts             — proxy /api → localhost:8000, @/ alias → src/
tailwind.config.js         — GP brand tokens as CSS variables
tsconfig.app.json          — paths: {"@/*": ["./src/*"]} (no baseUrl — TS6 deprecated it)
```

---

## How to run the web app

```powershell
# Terminal 1 — FastAPI backend (port 8000)
cd "Co-work POC\webapp\api"
uvicorn main:app --reload

# Terminal 2 — Vite frontend (port 5173)
cd "Co-work POC\webapp"
npm run dev
```

Open http://localhost:5173

### Prerequisites

```powershell
# Python (first time)
pip install fastapi uvicorn python-multipart pdfplumber

# Node (first time — run in BOTH folders)
cd "Co-work POC\disclosure-review-kit" && npm install docx
cd "Co-work POC\webapp" && npm install
```

---

## How to run the CLI (without the web app)

```powershell
cd "disclosure-review-kit"
.\run.ps1 -Report "..\NVU Annual Report.pdf"
```

---

## Architecture — zero LLM tokens at runtime

```
Browser → POST /api/review
            → FastAPI → python lib/review.py → output/findings.json
            ← {findings}
         → [user reviews in browser, selects/deselects announcements]
         → POST /api/generate {selectedKeys, excludedTypeInfo}
            → FastAPI filters findings → node lib/build_report.js → output/*.docx
            ← {docxName}
         → GET /api/download/{docxName}
```

Claude / AI is only used to maintain `config/*.json`. No LLM calls in the per-report path.

---

## FastAPI endpoints (webapp/api/main.py)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | `{"ok": true, "kitDir": "..."}` |
| POST | `/api/review` | multipart: file + options → runs review.py → returns `{findings}` |
| POST | `/api/generate` | JSON: `{selectedKeys[], excludedTypeInfo[]}` → runs build_report.js → `{docxName}` |
| GET | `/api/announcement/{key}` | Proxies ASX PDF via markitdigital (server-side Bearer token) |
| GET | `/api/download/{filename}` | Streams .docx from output/ |
| GET | `/api/prefs` | Returns user_prefs.json |
| POST | `/api/prefs` | Saves `{excludedTypes[]}` to user_prefs.json |
| POST | `/api/prefs/record` | Records `{typeStats: {typeName: "included"|"excluded"|"mixed"}}` per session |

KIT_DIR = `(webapp/api/../../disclosure-review-kit).resolve()`

ASX token: `83ff96335c2d45a094df02a206a39ff4` (public Bearer, same as asx.com.au)

---

## Key data structures

### findings.json (produced by review.py, consumed by build_report.js)

```json
{
  "entity": "Nanoveu Limited",
  "ticker": "NVU",
  "reportType": "annual",
  "reportFile": "NVU Annual Report.pdf",
  "basis": "...",
  "detectionNote": "...",
  "checklistVersion": "1.0",
  "summary": { "present": N, "not_found": N, "below_materiality": N, "na": N },
  "materiality": 677746,
  "materialityBasis": "5% of total assets",
  "totalAssets": 13554920,
  "results": [ ResultItem... ],
  "asx": {
    "ticker": "NVU",
    "periodStart": "2024-06-XX",
    "periodEnd": "2025-06-XX",
    "count": 92,
    "priceSensitive": 33,
    "items": [ AsxItem... ],
    "oppCounts": { "GREEN": N, "AMBER": N, "RED": N },
    "excludedTypeInfo": [ { "type": "...", "total": N, "excluded": N, "rag": "RED" } ]
  }
}
```

### AsxItem fields

```
date, headline, type, priceSensitive, importance, theme
rag (GREEN/AMBER/RED) — INTERNAL ONLY
oppServices[] — INTERNAL ONLY
priority — INTERNAL ONLY
source, localFile, documentKey, relevant
```

**Client vs internal split is MANDATORY** — `rag`, `oppServices`, `priority` must never appear in the Corporate Activity tab or Section 4 of the Word report.

### user_prefs.json (disclosure-review-kit/config/)

```json
{
  "version": "1.0",
  "excludedTypes": ["Progress Report", "Appendix 2A"],
  "typeHistory": {
    "Progress Report": { "included": 0, "excluded": 3, "mixed": 0 },
    "Placement": { "included": 2, "excluded": 0, "mixed": 1 }
  }
}
```

History badge logic (shown in TypeConfigPanel):
- `excluded === total && total >= 3` → "Always excluded"
- `excluded / total >= 0.8` → "Usually excluded"
- `included / total >= 0.8` → "Usually included"

---

## Word document structure (build_report.js)

| Section | Audience | Content |
|---------|----------|---------|
| 1. Executive summary | Client | Basis, checklist counts, materiality |
| 2. Disclosures to confirm | Client | NOT FOUND + category-B items, ordered high→low |
| 3. Full checklist results | Client | All items with status chips |
| 4. Corporate activity | Client | Announcements: date, headline, theme, mkt-sens, significance |
| Scope note | Client | Excluded types table (if any types were toggled off) |
| APPENDIX — INTERNAL | GP only | RAG opportunity matrix; excluded types warning (red) if GREEN/AMBER types excluded |

The scope note appears **after** Section 4's table. When any announcement types are excluded via the config panel, the note lists them: type name, omitted count, total in period.

The internal appendix warns in red if any excluded type had a GREEN or AMBER opportunity signal (flagging missed BD opportunities).

---

## UI flow

1. **UploadPage** — drag-drop PDF + optional: ticker, report type, materiality, ASX toggles
2. POST `/api/review` → navigate to `/results` with `{findings}` in React Router state
3. **ResultsPage** — 4 tabs:
   - Summary: entity header + status cards + materiality notice
   - Disclosures: filterable table, click row to expand recommendation
   - Corporate Activity: announcement checkboxes + hyperlinks + "Configure types" gear button
   - Opportunities: internal banner + RAG service matrix
4. On mount: GET `/api/prefs` → auto-deselect announcements whose type is in `excludedTypes`
5. **TypeConfigPanel** (slide-over from right):
   - Types grouped by RAG: GREEN / AMBER / RED
   - Each row: checkbox, type name, count in current findings, history badge
   - "Save & Apply" → POST `/api/prefs` → re-applies to selectedKeys
6. Sticky bottom bar: "X of Y announcements selected" + Generate Report button
7. Generate → POST `/api/generate {selectedKeys, excludedTypeInfo}` → Download Report link appears
8. After generate: POST `/api/prefs/record` with per-type included/excluded/mixed stats

---

## Styling

**Tailwind v3** (NOT v4 — shadcn/ui is incompatible with v4).
shadcn primitives were written manually (the CLI detected v4 and refused to run).

CSS variables in `src/index.css`:
```css
--background: 40 33% 98%       /* #FCFAF8 warm cream */
--foreground: 224 47% 14%      /* #1A2540 */
--primary: 220 45% 11%         /* #0F1829 deep navy */
--accent: 215 90% 40%          /* #0A57C2 vivid blue */
--navy-deep: 224 47% 8%        /* #090F1B header */
--radius: .25rem
```

Status chip classes (defined as Tailwind utilities in index.css):
```
.status-addressed  → bg-[#C6E0B4] text-[#375623]
.status-represented → bg-[#FFE699] text-[#806000]
.status-notfound   → bg-[#FFC7CE] text-[#9C0006]
.status-below      → bg-[#DDEBF7] text-[#1F4E79]
```

Fonts: Fraunces (headings, `font-heading`) + Inter (body, `font-sans`), loaded via Google Fonts in index.css.

---

## Key config files (edit these, no code change needed)

**`config/standards_checklist.json`** — each item:
`id, standard, clause, title, category (B/conditional/presentation), appliesTo[], detect[], detectAll[], expectedWhen[], materiality (high/medium/low), assessment (qualitative/quantitative), balanceCaptions[], representationNote, divergent, recommendation`

**`config/opportunity_map.json`** — 17 rules, 86/86 ASX sub-types:
`id, rag (GREEN/AMBER/RED), service, services[], match[], rationale, priority, theme`
Rules evaluated top-to-bottom; first match wins.

**`config/user_prefs.json`** — auto-managed at runtime; edit only to reset.

---

## NVU-specific facts

- Reports in **full Australian dollars** (not $'000)
- Financial year ends **31 December** (Pinnacle template ends 30 June)
- EMASS acquisition: **AASB 2 asset acquisition** (not AASB 3 business combination), $10.47M, 18 March 2025
- **NCI deficit**: Fullveu HK Ltd (49% minority) absorbs losses
- Never paid dividends; no bank borrowings (equity-funded)
- Three divisions: EMASS (semiconductor/Edge AI), EyeFly3D (3D display film), Nanoshield (nano-coating)

---

## What still needs building

| Item | Notes |
|------|-------|
| Admin screen | Edit `config/*.json` in-browser; set default materiality |
| Auth / gating on Opportunities tab | Currently shows "Internal use only" banner with no real gate |
| Deployment | Currently localhost only; needs a host (likely a simple VPS or cloud run) |
| Mobile layout | Designed for desktop; tables need responsive treatment |

---

## Open decisions

| # | Question |
|---|---|
| Q-01 | Materiality default: 5% total assets, or GP planning materiality? |
| Q-02 | Diluted EPS: "Represented differently" vs fully "Addressed"? |
| Q-03 | Opportunity priority: acquisition > capital raise > reporting — confirm? |
| Q-04 | Progress Reports / Trading Halts — keep AMBER, promote to GREEN, or drop? |
| Q-05 | Auditor to confirm exact AASB sub-paragraph refs in section 2 |
| Q-06 | Internal appendix: same file last page vs separate `_Internal.docx`? |
