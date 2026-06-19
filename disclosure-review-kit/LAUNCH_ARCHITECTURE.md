# Disclosure Review Kit — Launch / Productisation Context

> **Purpose of this doc:** hand-off context for turning this kit into a launched service —
> e.g. when building a web app/API (in Antigravity or any stack). It explains what exists, the
> recommended architecture, the token strategy, and the exact interfaces a wrapper should call.
> Pair it with `README.md` (how the kit works), `TEST_CASES.md` (what's verified), and
> `FEEDBACK.md` (change log R1–R6).

---

## 1. The one fact that drives the architecture

**The per-report runtime already uses ZERO LLM tokens.** The pipeline is pure Python/Node:

```
run.ps1 → lib/review.py   (pdfplumber extract + checklist screen + ASX API + materiality)
        → lib/build_report.js (docx generation)
```

No model is called when a report is produced. The LLM (Claude) was only used to *build and refine*
the logic; those judgments are now frozen into `config/*.json` + code. So "reduce tokens" =
**keep the LLM out of the per-report path**, which the kit already does.

---

## 2. Recommended architecture for launch

**Productise the existing engine behind a thin API + simple web UI. Do not re-implement the
logic.** The kit IS the backend.

```
[ Web page: upload PDF / enter ticker ]
            │  HTTP
            ▼
[ API (e.g. FastAPI) ]
   ├─ run lib/review.py  → output/findings.json      (deterministic, 0 tokens)
   ├─ run lib/build_report.js findings.json out.docx  (deterministic, 0 tokens)
   └─ return: client .docx, internal appendix, findings.json (for a live HTML view)
```

- **Tokens per report: zero.** The runtime needs no AI provider at all.
- The web UI can render `findings.json` directly (tables for checklist + announcements + RAG)
  and offer the .docx as a download.

### Where the other options fit
| Option | Use it for | Token cost |
|---|---|---|
| **App / web API → Python** (recommended) | The launched, client-facing service at volume | Zero per report |
| **Routines (scheduled agent)** | "Run our watchlist every quarter" — trigger the API/script | Near-zero if the agent only triggers code |
| **MCP connector** | Internal analysts calling the tools interactively from a Claude client | Low (chat orchestration only) |
| **Cowork / Claude Code** | Building & refining the kit; bespoke one-off engagements | High — keep for dev/maintenance, not production |

---

## 3. Token strategy (pure-code vs hybrid)

Today's intelligence is **rule-based + keyword matching** — deterministic and free, but brittle on
unseen reports. Two tiers:

1. **Pure code (cheapest, default for launch):** ship the rules; extend `config/*.json` as new
   cases appear. Zero runtime tokens.
2. **Hybrid (premium tier, optional):** deterministic core for ~95%, **plus one bounded LLM call
   per report** for the judgment layer only (e.g. "review the flagged section-2 items and the
   opportunity calls against this report text"). Cap spend to that single pass; cache results.

Use Claude **only** to maintain the knowledge base (checklist, opportunity map) — an occasional
human-in-loop session, not per report.

---

## 4. Engine interfaces a wrapper must call

### 4.1 Run the review (Python)
```
python lib/review.py --report "<path-to.pdf>" \
   [--ticker NVU] [--type auto|interim|annual] \
   [--materiality 250000] [--materiality-pct 5] \
   [--no-asx] [--download-asx] [--as-of-period] \
   --out output --announcements announcements
# writes: output/findings.json   (auto-detects entity/ticker/type/period; classifies opportunity RAG)
```

### 4.2 Build the Word report (Node)
```
node lib/build_report.js output/findings.json "output/<Entity>_Disclosure_Review.docx"
# client-facing body (Sections 1–4) + page-broken INTERNAL appendix ("remove before sending")
```

### 4.3 ASX announcements engine (Python, called by review.py; usable standalone)
```
python lib/asx_history.py NVU --months 12 [--xid <entityXid>] [--download]
# writes: announcements/NVU/index.json  (paginated full 12-month history)
```

### 4.4 Knowledge base (edit these, no code change)
- `config/standards_checklist.json` — disclosure items: `standard`, `clause`, `appliesTo`,
  `detect`/`detectAll`, `expectedWhen`, `category`, `materiality`, `assessment`
  (qualitative|quantitative), `balanceCaptions`, `representationNote`, `divergent`,
  `recommendation`.
- `config/opportunity_map.json` — BD rules: token `match` → `rag`, `service`, `theme`,
  `priority`, `rationale`.

---

## 5. Data contract — `output/findings.json`

The wrapper/UI should render from this (no parsing of the .docx needed):

```jsonc
{
  "entity": "Nanoveu Limited", "ticker": "NVU",
  "reportType": "annual",                      // or "interim"
  "summary": { "present": N, "not_found": N, "below_materiality": N, "na": N },
  "materiality": 677746, "materialityBasis": "5% of total assets $13,554,915",
  "results": [                                  // Sections 2 & 3
    { "standard": "AASB 15 / IFRS 15", "clause": "AASB 15 ¶114–115",
      "title": "...", "category": "B", "materiality": "high",
      "assessment": "quantitative", "balance": 484000, "materialityThreshold": 677746,
      "status": "PRESENT|NOT FOUND|BELOW MATERIALITY|N/A",
      "representationNote": "...", "divergent": true,   // true→"Represented differently", false→"Addressed"
      "recommendation": "..." }
  ],
  "asx": {                                      // Section 4 + internal appendix
    "periodStart": "2025-06-18", "periodEnd": "2026-06-18",
    "count": 92, "priceSensitive": 33, "fromApi": 92, "fromLocal": 0,
    "oppCounts": { "GREEN": 16, "AMBER": 24, "RED": 52 },
    "items": [
      { "date": "...", "headline": "...", "type": "...", "priceSensitive": true,
        "theme": "Strategic transaction",      // client-facing
        "importance": "High",                   // significance band (client)
        "rag": "GREEN", "oppService": "Transaction Readiness", "oppRationale": "...",
        "oppServices": ["Transaction Readiness", "Financial Reporting"] } // internal-only; checkbox matrix in appendix
    ]
  }
}
```

**Client vs internal split:** the client-facing view uses `theme` + `importance` (significance)
and **must not** show `rag`, `oppService`, `oppRationale` — those belong only in the internal
appendix / internal screen.

---

## 6. Dependencies & environment
- **Python 3**: `pdfplumber` (extraction), `openpyxl` + `formulas` (financial model, optional in service), standard lib for ASX HTTP.
- **Node**: `docx` (report generation).
- **ASX data**: public markitdigital endpoints (`/markets/announcements`, `/search/predictive`,
  `/file/{key}`) with the public static bearer token in `lib/asx_history.py`. No login required;
  local-folder fallback if the API is unreachable.
- Text-based PDFs only (scanned PDFs need OCR first).

---

## 7. Open decisions to settle before/at launch (from TEST_CASES.md Q-01–Q-06)
1. Materiality threshold (default 5% of total assets, or GP planning materiality).
2. Diluted EPS — "Represented differently" vs "Addressed" (AASB 133 ¶43).
3. Opportunity priority order (acquisition > capital raise > reporting).
4. `[CONFIRM]` opportunity rules — Progress Reports / Trading Halts.
5. Auditor confirmation of exact AASB sub-paragraph references in section 2.
6. Internal appendix as a page in one file vs a separate `_Internal.docx`.

---

## 8. Suggested build sequence (Antigravity or any stack)
1. Stand up a FastAPI app; endpoint `POST /review` (multipart PDF or `{ticker}`) → runs 4.1 then 4.2.
2. Return `findings.json` + the two .docx artifacts (client, internal).
3. Build a one-page UI: upload → progress → results (render `findings.json` tables) → downloads.
4. Add auth + a job queue if running batches/watchlists.
5. (Optional, later) premium "deep analysis" tier = one bounded LLM pass over the flagged items.
6. Keep `config/*.json` editable via an internal admin screen so non-developers tune the rules.
