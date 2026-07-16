# GP Business Opportunities — Project State (CLAUDE.md)

> **AI AGENT RULES — READ FIRST, ALWAYS:**
> 1. **NEVER use DROP TABLE on `company_news`, `contacts`, or `metrics`** — these contain scraped data that took days to collect. Use `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN` only.
> 2. **NEVER commit `.env`, `railway_db.sqlite`, `data/afr_session.json`, or scratch `patch*.py` files.**
> 3. **After ANY schema change to `migrate_to_erd.py`, run `sync_to_prod.py` immediately after deploy.**
> 4. **`playwright` and `playwright-stealth` are LOCAL-ONLY dependencies — never add them to `webapp/api/requirements.txt`.**
> 5. **Always query the ERD tables (`companies`, `infringements`, `contacts`, `metrics`, `company_news`) — never JSON files.**
> 6. **After every code change, commit and push to GitHub so Railway auto-deploys.**
> 7. **Production = Railway. Local = `webapp/api/unified_companies.db`. Sync local → prod with `sync_to_prod.py` after every scrape.**

---

## What This Project Is

A **GP Business Development Intelligence Platform** for identifying and researching unlisted Australian private company prospects.

**Production URL:** https://gp-busopp-project.vercel.app (frontend)
**API URL:** https://gp-busopp-project-production.up.railway.app (backend)
**GitHub:** https://github.com/Ryan-gpa/gp-busopp-project

---

## Architecture

```
Vercel (React/Vite frontend)
    ↓ fetch /api/*
Railway (FastAPI backend, port 8080)
    ↓ reads/writes
SQLite (Railway persistent volume: /var/lib/... unified_companies.db)
```

### Local Development
```
webapp/api/unified_companies.db   ← LOCAL copy of the DB (not in git)
webapp/api/scripts/sync_to_prod.py ← push local scraped data → Railway DB
```

---

## ERD Database Schema (unified_companies.db)

### `companies` table (3.96M rows — ASIC bulk data)
| Column | Type | Notes |
|--------|------|-------|
| acn | TEXT PK | 9-digit ACN |
| name | TEXT | Company name |
| name_norm | TEXT | Normalised for search |
| status | TEXT | REGD, DRGD, etc. |
| type | TEXT | APTY=Proprietary, FNOS=Foreign, etc. |
| class | TEXT | LMSH=Limited by shares |
| subclass | TEXT | PROP=Proprietary |
| state | TEXT | |
| is_large_prop | INTEGER | 0/1 |
| revenue | REAL | From ASIC bulk data |
| employees | INTEGER | |

### `infringements` table (54 rows — ASIC notices)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| acn | TEXT | |
| name | TEXT | Company name |
| notice_date | TEXT | |
| offence | TEXT | |
| penalty_paid | TEXT | |
| amount | REAL | |
| url | TEXT | PDF link |
| raw_json | TEXT | Full JSON |

**Source:** `webapp/api/scripts/asic_infringement_notices.json` (also `webapp/asic_infringement_notices.json`)
**Loaded by:** `migrate_to_erd.py` — DROP + recreate is OK for this table only (reloaded from JSON each time)

### `metrics` table (~3,996 rows — RocketReach/Apollo enrichment)
| Column | Type | Notes |
|--------|------|-------|
| org_id | TEXT PK | e.g. `asic_123456789` |
| acn | TEXT | |
| revenue | REAL | Annual revenue AUD |
| employees | INTEGER | |
| source | TEXT | `apollo` or `rocketreach` |
| updated_at | REAL | Unix timestamp |

**⚠️ NEVER DELETE FROM metrics — use INSERT OR REPLACE**

### `contacts` table (11 rows — Apollo/RocketReach people)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| org_id | TEXT | |
| acn | TEXT | |
| name | TEXT | |
| title | TEXT | |
| email | TEXT | |
| linkedin_url | TEXT | |
| source | TEXT | `apollo` or `rocketreach` |
| updated_at | REAL | |
| raw_json | TEXT | Full contact JSON |

**⚠️ NEVER DELETE FROM contacts — use INSERT OR IGNORE**

### `company_news` table (65 rows — AFR scraper)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| acn | TEXT | |
| source | TEXT | `AFR` (future: other sources) |
| url | TEXT UNIQUE | |
| title | TEXT | |
| summary | TEXT | AI-generated summary |
| fetched_at | REAL | Unix timestamp |

**⚠️ NEVER DROP company_news — use CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN**

---

## Key Scripts

### `webapp/api/scripts/migrate_to_erd.py`
Applies ERD schema to `unified_companies.db`. **Auto-runs on every Railway startup** (background thread in `main.py`).
- `infringements`: DROP + recreate (reloaded from JSON) ✅ OK
- `metrics`: `INSERT OR REPLACE` from cache — never DELETE ✅
- `contacts`: `INSERT OR IGNORE` from cache — never DELETE ✅
- `company_news`: `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN` — never DROP ✅

### `webapp/api/scripts/afr_scraper.py`
Scrapes AFR for news about ASIC infringement companies.
- Reads company names from `infringements` table (NOT from JSON)
- Strips legal suffixes before search query
- Relevance-gates articles (must mention company in title/slug)
- Saves to `company_news` with `source='AFR'`
- **Local only** — requires Playwright + AFR login session
- After running: execute `sync_to_prod.py`

### `webapp/api/scripts/sync_to_prod.py`
**Run this after every local scraping session** to push data to Railway.
```powershell
cd C:\Users\88hon\gp-busopp-project
python webapp/api/scripts/sync_to_prod.py
```
Syncs in batches of 100 rows:
- `company_news` → INSERT OR IGNORE
- `metrics` → INSERT OR REPLACE
- `contacts` → INSERT OR IGNORE

### `webapp/api/scripts/migrate_contacts.py`
Migrates contacts from legacy cache format.

---

## Contact enrichment → HubSpot pipeline (agent-runnable)

Any agent (Claude, Gemini, cron) can run this head-less. Enrichment tools = **Hunter.io,
RocketReach, Apollo** — keys live in `webapp/.env` (`HUNTER_API_KEY`, `ROCKETREACH_API_KEY`,
`APOLLO_API_KEY`). The app dispatch is `GET /api/unlisted/contacts/{org_id}?source=auto|hunter|rocketreach|apollo`.

**Step 1 — enrich** (populates `contacts_cache` + the live `contacts` table):
```powershell
python webapp/api/scripts/enrich_asic_contacts.py --source hunter --limit 50
# --source: auto (Hunter if domain else RocketReach) | hunter | rocketreach | apollo
# --refresh to re-enrich companies that already have contacts
```

**Step 2 — push to HubSpot** (`scripts/hubspot_sync.py`):
```powershell
python webapp/api/scripts/hubspot_sync.py            # credible contacts only
python webapp/api/scripts/hubspot_sync.py --dry-run  # preview
python webapp/api/scripts/hubspot_sync.py --all      # skip the quality filter
```
- **Requires `HUBSPOT_TOKEN` in `webapp/.env`** (HubSpot → Settings → Private Apps; scopes
  `crm.objects.contacts.read`+`write`). The script loads `.env` itself and **never prompts**
  (that was the old bug — `getpass` hung non-interactive agents; there was also no token and a
  bad `comp.domain` query). Claude's HubSpot **MCP** path needs no token.
- Flags every contact `lead_source_gp=ASIC` + `gp_campaign=ASIC`, sets `hs_linkedin_url`,
  `gp_email_confidence`; upserts via POST→PATCH-on-409.
- **Quality filter (default on):** skips free-mail (aol/gmail…) and emails whose domain doesn't
  match the company — RocketReach/Hunter return some wrong-company matches. `--all` overrides.

**Step 3 — push to prod app DB:** `python webapp/api/scripts/sync_to_prod.py`

**Gotcha:** the two paths can duplicate a person if their real email ≠ the guessed one. Dedupe
by merging in the HubSpot UI (the MCP can't delete/merge).

---

## Frontend Filters (UnlistedCompaniesPage.tsx)

All 5 filters send to backend and trigger a new search:

| Filter | State Var | Backend Field | SQL Clause |
|--------|-----------|---------------|------------|
| Status | `dbStatusFilter` | `dbStatusFilter` | `c.status = ?` |
| Type | `entityTypeFilter` | `entityTypeFilter` | `c.type = ?` |
| Class | `classFilter` | `classFilter` | `c.class = ?` |
| Subclass | `subclassFilter` | `subclassFilter` | `c.subclass = ?` |
| News Source | `newsSourceFilter` | `newsSourceFilter` | `EXISTS (SELECT 1 FROM company_news WHERE acn=c.acn AND source=?)` |

**Type values:** `APTY` (Proprietary), `FNOS` (Foreign), `PUBA` (Public), `RGAS` (Reg Aust Body)

---

## Backend API (webapp/api/main.py)

Key endpoints:
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/admin/system-status` | DB status, table counts |
| POST | `/api/admin/sql` | Run raw SQL (admin use) |
| POST | `/api/admin/migrate-erd` | Run migrate_to_erd.py manually |
| POST | `/api/unlisted/search` | Main company search with all filters |
| POST | `/api/unlisted/enrich/{acn}` | Fetch contacts for a company |

**Startup sequence:**
1. `_load_dotenv()` — loads `webapp/.env`
2. `_ensure_db_schema()` — creates `company_news` if missing
3. Background thread runs `migrate_to_erd.py`
4. `[asic]` loads 122 infringement records
5. `[asx]` loads ASX companies from disk cache

---

## Environment Variables (webapp/.env — never commit)

```
APOLLO_API_KEY=...
ROCKETREACH_API_KEY=...
ANTHROPIC_API_KEY=...     # Used for AFR article summarisation
BOX_CLIENT_ID=...
BOX_CLIENT_SECRET=...
```

---

## Data Sources

| Source | What | How |
|--------|------|-----|
| ASIC bulk data | 3.96M companies | Loaded into `companies` table via migration |
| ASIC infringement notices | 54 notices, 118 companies | JSON → `infringements` table |
| Apollo.io | Contacts, revenue | `/api/unlisted/enrich` endpoint |
| RocketReach | Contacts, revenue | `/api/unlisted/enrich` endpoint |
| AFR scraper | News articles | `afr_scraper.py` (local only) → `company_news` |

---

## Workflow: After Local Scraping

```
1. Run scraper locally:
   python webapp/api/scripts/afr_scraper.py

2. Sync to production:
   python webapp/api/scripts/sync_to_prod.py

3. Verify production:
   curl -X POST https://gp-busopp-project-production.up.railway.app/api/admin/sql \
     -H "Content-Type: application/json" \
     -d '{"query": "SELECT COUNT(*) FROM company_news"}'
```

---

## Outstanding Work

| Item | Priority | Notes |
|------|----------|-------|
| Apollo 199 credits — enrich infringement companies | HIGH | Use remaining credits on the 118 ASIC infringement companies |
| UX credit limit display | MEDIUM | Show Apollo credit balance in the UI |
| ASIC Form 388 validation | LOW | Manual deep-link approach currently |

---

## Known Gotchas

1. **CORS on 500 errors** — Fixed: exception handler now returns explicit CORS headers
2. **`import json` inside function** — causes `UnboundLocalError` if placed after first use in same function
3. **Playwright on Railway** — NEVER add to `requirements.txt`. Playwright is local-only.
4. **`DELETE FROM metrics/contacts`** in `migrate_to_erd.py` wipes prod data — now fixed to INSERT OR REPLACE/IGNORE
5. **`DROP TABLE company_news`** wipes scraped articles — now fixed to CREATE TABLE IF NOT EXISTS
6. **newsSourceFilter was missing from useEffect deps** — now fixed
7. **Filter payload was missing entityTypeFilter/classFilter/subclassFilter** — now fixed

---

## Disclosure Review Kit (Original Feature — Still Working)

The original ASIC disclosure screening tool is still live. See the original CLAUDE.md content for details. Runs at the same Railway URL under `/api/review`, `/api/generate`, etc.


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

### Unlisted Companies Search (NEW)
A new feature was recently added to find private Australian companies as GP prospects using Apollo's API. It includes:
- A `UnlistedCompaniesPage.tsx` React frontend that takes revenue filters.
- A `/api/unlisted/search` FastAPI backend that translates those revenue queries into headcount estimates (as a proxy, since Apollo ignores exact revenue).
- Automatic ASX cross-referencing to exclude companies already captured by the main review kit.
- Note: It queries Apollo's `mixed_companies/search` endpoint and sorts by ascending employee headcount to discover mid-tier businesses rather than giants.

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
  main.py                  — FastAPI backend (7 endpoints + PDF gen + Apollo unlisted search)
  requirements.txt         — fastapi uvicorn python-multipart pdfplumber boxsdk docx2pdf requests
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
    UnlistedCompaniesPage.tsx — Apollo-backed search for private prospects
  components/
    ui/                     — shadcn/ui primitives (button, card, tabs, progress) — written manually
    app/
      SummaryCards.tsx      — entity header + 4 status cards + materiality notice + board/management table
      DisclosuresTab.tsx    — filterable/sortable checklist results table
      CorporateActivityTab.tsx — announcement table with checkboxes, hyperlinks, Configure button
      OpportunitiesTab.tsx  — internal-only RAG service matrix; RED shown as plain count (no badge)
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
pip install fastapi uvicorn python-multipart pdfplumber docx2pdf

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
            → LibreOffice / docx2pdf → output/*.pdf (if available)
            ← {docxName, pdfName}
         → GET /api/download/{docxName|pdfName}
```

Claude / AI is only used to maintain `config/*.json`. No LLM calls in the per-report path.

---

## FastAPI endpoints (webapp/api/main.py)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | `{"ok": true, "kitDir": "..."}` |
| POST | `/api/review` | multipart: file + options → runs review.py → returns `{findings}` |
| POST | `/api/generate` | JSON: `{selectedKeys[], excludedTypeInfo[]}` → runs build_report.js → `{docxName, pdfName}` |
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
  "officers": [ { "name": "...", "role": "...", "roleNorm": "..." } ],
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
| 1. Executive summary | Client | Basis, checklist counts, materiality + board/management table |
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
7. Generate → POST `/api/generate {selectedKeys, excludedTypeInfo}` → Download PDF + Download Word links appear (PDF requires LibreOffice or Microsoft Word installed; falls back gracefully)
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

Current service assignments (GP-confirmed):
- `ma_transaction` → Financial Reporting + Commercial Opportunities
- `capital_raise` → Financial Reporting (share-based payments / AASB 2)
- `cfo_finance_lead` → Commercial Opportunities + Business Process Redesign
- `periodic_reporting` → Financial Reporting + Audit Readiness
- `earnings_guidance` → Commercial Opportunities + Financial Reporting

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

## Future Considerations: ASIC Form 388 Validation

Checking if a private company has genuinely lodged a **Form 388 (Financial Report)** is the ultimate test of whether they are a Large Proprietary company (and therefore a prime GP prospect). The current implementation uses a "Deep Link" approach to ASIC Connect. 
If we need to fully automate this in the future, these are the paths:

- **Approach 1 (Current): Deep Link.** Generates an ASIC Connect search URL using the ACN. Free, safe, but requires the user to manually scroll the document list to spot the "388".
- **Approach 2 (Paid API):** Integrate a commercial broker API (e.g., InfoTrack, Equifax, CreditorWatch). The backend would query their API for the document index. **Drawback:** Costs ~$2 to $5 AUD per company just to view the index.
- **Approach 3 (Web Scraper):** Build a Python scraper to navigate ASIC Connect and parse the HTML for "388". **Drawback:** Highly brittle. ASIC uses aggressive Imperva/Incapsula bot protection, making it prone to breaking and risking server IP bans.

---

## What still needs building

| Item | Notes |
|------|-------|
| Admin screen | Edit `config/*.json` in-browser; set default materiality |
| Auth / gating on Opportunities tab | Currently shows "Internal use only" banner with no real gate |
| Mobile layout | Designed for desktop; tables need responsive treatment |

Deployment is live on Railway (Docker, port 8000, LibreOffice included for server-side PDF).

---

## Open decisions

| # | Question |
|---|---|
| Q-01 | Materiality default: 5% total assets, or GP planning materiality? |
| Q-02 | Diluted EPS: "Represented differently" vs fully "Addressed"? |
| Q-03 | ~~Opportunity priority: acquisition > capital raise > reporting — confirm?~~ Service assignments confirmed by GP Jun 2026 |
| Q-04 | Progress Reports / Trading Halts — keep AMBER, promote to GREEN, or drop? |
| Q-05 | Auditor to confirm exact AASB sub-paragraph refs in section 2 |
| Q-06 | Internal appendix: same file last page vs separate `_Internal.docx`? |


---

## AI Agent Directives

1. **Maintain Data Models**: Whenever modifying database schema, adding new tables, or changing core architecture, you MUST automatically update the corresponding Data Dictionary and Entity Relationship Diagram (ERD) artifacts to reflect the new state. This ensures documentation always stays in sync with code.
