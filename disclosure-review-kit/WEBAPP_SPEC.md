# Web App Build Spec — Disclosure Review (Antigravity hand-off)

Companion to `LAUNCH_ARCHITECTURE.md` (architecture & engine interfaces). This doc gives the
**theme** to match growthpartnersadvisory.com and the **complete meta-field catalogue** the web
app must surface. The Word documents remain the outcome artefacts; the app orchestrates the
existing engine and exposes every field below.

---

## 1. Outcome artefacts (unchanged)
1. **Client report** `.docx` — Sections 1–4 (neutral, client-facing).
2. **Internal appendix** — engagement-opportunities (RAG service matrix). Same file last page, or
   a separate `_Internal.docx` (see Q-06).
3. **`findings.json`** — machine-readable; **this powers the web UI** (render tables/cards from it,
   offer the `.docx` as downloads). Engine call sequence is in `LAUNCH_ARCHITECTURE.md §4`.

---

## 2. Theme — match the Growth Partners website

Stack on the live site: **Vite + React + Tailwind + shadcn/ui**, HSL design tokens.

### Fonts (Google Fonts)
- **Headings / display:** `Fraunces` (serif) — weights 300–600, optical sizing `9..144`.
- **Body / UI:** `Inter` (sans-serif). Mono: `ui-monospace, Menlo, Consolas`.

### Palette (exact tokens from the site)
| Token | HSL (light) | Hex | Use |
|---|---|---|---|
| `--background` | `40 33% 98%` | `#FCFAF8` | warm cream page background |
| `--foreground` / `--primary` | `220 45% 11%` | `#0F1829` | deep navy text / primary |
| `--navy-deep` | `220 50% 7%` | `#090F1B` | darkest navy (hero/footer) |
| `--primary-foreground` | `40 33% 98%` | `#FCFAF8` | text on navy |
| `--accent` | `215 90% 40%` | `#0A57C2` | vivid blue accent (links, CTAs) |
| `--accent-foreground` | `0 0% 100%` | `#FFFFFF` | text on accent |
| `--ring` | `215 90% 52%` | `#1672F3` | focus ring |
| `--secondary` | `220 20% 95%` | `#F0F1F5` | secondary surfaces |
| `--muted` | `220 14% 94%` | `#EEEFF2` | muted surfaces |
| `--muted-foreground` | `220 15% 40%` | `#576175` | slate secondary text |
| `--border` / `--input` | `220 18% 88%` | `#DBDFE6` | hairline borders |
| `--card` | `0 0% 100%` | `#FFFFFF` | cards |
| `--destructive` | `0 72% 51%` | `#DC2828` | errors / red |
| `--radius` | `.25rem` | — | corner radius (rounded-sm) |

**Look & feel:** editorial serif headings (Fraunces) over clean Inter body; warm-cream canvas,
deep-navy primary, restrained vivid-blue accent; thin borders; generous whitespace; small radius.
Professional advisory aesthetic — understated, not flashy.

### Paste-ready `:root` (shadcn/Tailwind)
```css
:root{
  --background:40 33% 98%; --foreground:220 45% 11%;
  --card:0 0% 100%; --card-foreground:220 45% 11%;
  --primary:220 45% 11%; --primary-foreground:40 33% 98%;
  --secondary:220 20% 95%; --secondary-foreground:220 45% 11%;
  --accent:215 90% 40%; --accent-foreground:0 0% 100%;
  --muted:220 14% 94%; --muted-foreground:220 15% 40%;
  --border:220 18% 88%; --input:220 18% 88%; --ring:215 90% 52%;
  --destructive:0 72% 51%; --destructive-foreground:0 0% 100%;
  --navy-deep:220 50% 7%; --radius:.25rem;
}
.dark{ --background:220 50% 7%; --foreground:40 33% 98%; --primary:40 33% 98%;
  --primary-foreground:220 45% 11%; --accent:215 90% 40%; }
```

### Report status colours → brand-aligned (used in UI **and** the .docx)
Keep semantic meaning; harmonise with the palette.
| Meaning | Fill | Text |
|---|---|---|
| GREEN / Present / Addressed / High | `#C6E0B4` | `#375623` |
| AMBER / Represented differently / Medium | `#FFE699` | `#806000` |
| RED / Not detected / destructive | `#FCE4D6` / `#FFC7CE` | `#843C0C` / `#9C0006` |
| Below materiality (info) | `#DDEBF7` | `#1F4E79` |
| Header bars / section titles | `--navy-deep` `#090F1B` | cream `#FCFAF8` |
| Accent / links / active | `--accent` `#0A57C2` | — |

---

## 3. Meta-field catalogue (everything the app must represent)

### A. User inputs (upload / run form)
| Field | Type | Maps to engine arg | Notes |
|---|---|---|---|
| Report file | file (PDF) | `--report` | text-based PDF; OCR out of scope |
| Ticker | text (override) | `--ticker` | else auto-detected |
| Report type | select `auto / interim / annual` | `--type` | default auto |
| Planning materiality (AUD) | number (optional) | `--materiality` | overrides % default |
| Materiality % of total assets | number (default 5) | `--materiality-pct` | used if no AUD given |
| Window anchor | toggle `today / report period-end` | `--as-of-period` | ASX 12-month window anchor |
| Include ASX announcements | toggle | `--no-asx` (inverse) | default on |
| Download announcement PDFs | toggle | `--download-asx` | default off |

### B. Detected / derived (read-only, top of results)
`entity` · `ticker` · `reportType` · `reportFile` · `checklistVersion` · `basis` (framework text) ·
`detectionNote` · `materiality` · `materialityBasis` · `totalAssets`.

### C. Summary cards (aggregates)
`summary.present` · `summary.not_found` · `summary.below_materiality` · `summary.na` ·
derived `addressed` (present + representationNote + !divergent) · `repDiff` (present + representationNote + divergent) ·
`asx.count` · `asx.priceSensitive` · `asx.oppCounts.{GREEN,AMBER,RED}`.

### D. Disclosure checklist — `results[]` (Sections 2 & 3)
| Field | Type | Notes |
|---|---|---|
| `id` | string | stable item key |
| `standard` | string | e.g. "AASB 15 / IFRS 15" |
| `clause` | string | e.g. "AASB 15 ¶114–115" |
| `title` | string | disclosure name |
| `category` | enum `B / conditional / presentation` | B = always-surfaced quality point |
| `materiality` | enum `high / medium / low` | significance band for sort |
| `assessment` | enum `qualitative / quantitative` | quant = materiality-gated |
| `balance` | number\|null | extracted underlying balance (quant) |
| `materialityThreshold` | number\|null | threshold applied |
| `status` | enum `PRESENT / NOT FOUND / BELOW MATERIALITY / N/A` | raw screen result |
| `divergent` | bool | true → "Represented differently"; false+note → "Addressed" |
| `representationNote` | string | where/how it's represented |
| `recommendation` | string | action text |
| **derived `renderStatus`** | enum `Addressed / Represented differently / Not detected / Below materiality / N/A / Detected` | UI label (see build_report logic) |

### E. Corporate activity / announcements — `asx.items[]` (Section 4 + internal)
| Field | Type | Audience | Notes |
|---|---|---|---|
| `date` | ISO datetime | client + internal | |
| `headline` | string | client + internal | |
| `type` | string | client + internal | ASX header/sub-type |
| `priceSensitive` | bool | client + internal | ASX market-sensitive flag |
| `theme` | string | **client** | neutral category (Strategic transaction, Capital management, Financial reporting, …) |
| `importance` | enum `High / Medium / Low / None` | **client** (as "Significance") | |
| `rag` | enum `GREEN / AMBER / RED` | **internal only** | opportunity signal |
| `oppServices` | string[] (of the 5 service lines) | **internal only** | checkbox matrix |
| `oppService` | string | **internal only** | combined label |
| `oppRationale` | string | **internal only** | why |
| `priority` | int 1–5 | **internal only** | ranking |
| `documentKey` / `fileSize` / `localFile` / `source` / `relevant` | — | internal/system | PDF retrieval & provenance |

ASX block meta: `asx.periodStart` · `periodEnd` · `months` · `method` (`paginated`/`capped-fallback`) ·
`entityXid` · `online` · `apiCapped` · `fromApi` · `fromLocal` · `ragMeaning`.

> **Client vs internal separation is mandatory.** The client view shows only `theme` + `importance`
> (as "Significance"); it must NOT render `rag`, `oppService(s)`, `oppRationale`, or `priority`.
> Those belong to the internal opportunities view/appendix.

### F. Admin / reference data (editable in-app, no code change)
- **`config/standards_checklist.json`** — disclosure items: `id, standard, clause, title, category,
  appliesTo[], detect[]/detectAll[], expectedWhen[], materiality, assessment, balanceCaptions[],
  representationNote, divergent, recommendation`. + `meta.version`.
- **`config/opportunity_map.json`** — `rules[]`: `id, rag, service, services[], match[], rationale,
  priority, theme`; `meta.serviceLines[]` (the 5 GP services), `ragMeaning`, `priorityBands`.
- Surface these as an **admin screen** so analysts tune mappings/thresholds (this is the substrate
  for the next-phase learning loop).

### G. The 5 GP service lines (checkbox columns / filters)
`Transaction Readiness` · `Financial Reporting` · `Business Process Redesign` ·
`Commercial Opportunities` · `Audit Readiness`.

---

## 4. Suggested screens
1. **New review** — the Group-A form (upload + options).
2. **Results dashboard** — Group-B header + Group-C summary cards; downloads (client docx, internal, findings.json).
3. **Disclosures tab** — `results[]` table with `renderStatus` chips (brand status colours), clause references, filter by status/standard.
4. **Corporate activity tab (client)** — `asx.items[]`: Date · Announcement · Type · Mkt-sens · Significance (neutral; no RAG/service).
5. **Opportunities tab (internal, gated)** — same items as a RAG-coloured **service checkbox matrix** (Date · Announcement · Type · 5 service ticks), sorted by priority.
6. **Admin** — edit `standards_checklist.json` / `opportunity_map.json`; set default materiality.

---

## 5. Open decisions (carry over from TEST_CASES.md Q-01–Q-06)
Materiality default · diluted-EPS classification · opportunity priority order · `[CONFIRM]` rules ·
paragraph-reference sign-off · internal appendix as same-file page vs separate `_Internal.docx`.
