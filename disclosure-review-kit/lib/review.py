"""Disclosure review engine.

Takes a half-year or annual report PDF, screens it against the AASB/IFRS
disclosure checklist, optionally pulls ASX announcements, and writes a
findings.json that build_report.js turns into a Word report.

Usage:
    python review.py --report "path/to/report.pdf" [--ticker NVU] [--type auto|interim|annual]
                     [--out ../output] [--announcements ../announcements] [--no-asx]

Detection is keyword-based screening, not assurance. Every PRESENT/NOT FOUND
result should be confirmed by a human reviewer.
"""
import argparse, json, os, re, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
CHECKLIST = os.path.join(KIT, "config", "standards_checklist.json")


def extract_text(pdf_path):
    # pypdf uses ~10x less peak memory than pdfplumber/pdfminer for large PDFs.
    # Fall back to pdfplumber if pypdf is unavailable or fails.
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        pass
    import pdfplumber
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def detect_type(text):
    t = text.lower()
    interim = sum(t.count(k) for k in ["half-year", "half year", "appendix 4d", "interim financial", "30 june"])
    annual = sum(t.count(k) for k in ["appendix 4e", "annual financial report", "annual report", "remuneration report", "directors' report"])
    # 4D/4E are the strongest signals
    if "appendix 4d" in t and "appendix 4e" not in t:
        return "interim"
    if "appendix 4e" in t:
        return "annual"
    return "annual" if annual >= interim else "interim"


def detect_ticker(text):
    # Gather candidate codes from high-precision patterns, then pick the one that
    # occurs most often as a standalone token (the entity's own code dominates;
    # other companies named in the remuneration report appear only once).
    candidates = {}
    for pat in [
        r"\b([A-Z]{2,4}),\s*(?:the\s+)?Company\b",      # "(Nanoveu, NVU, the Company)"
        r"ASX\s*Code\s*[:\-]?\s*([A-Z0-9]{2,5})\b",
        r"ASX[:\s]+([A-Z0-9]{2,5})\b",
        r"\(ASX\s*[:\-]?\s*([A-Z0-9]{2,5})\)",
    ]:
        for m in re.finditer(pat, text):
            code = m.group(1)
            if code in ("CODE", "LTD"):
                continue
            candidates.setdefault(code, 0)
    if not candidates:
        return None
    # score each candidate by standalone frequency across the whole document
    for code in list(candidates):
        candidates[code] = len(re.findall(rf"\b{re.escape(code)}\b", text))
    return max(candidates, key=candidates.get)


MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


def detect_period_end(text):
    """Report period-end date (the 12-month announcement window ends here)."""
    head = text[:6000]
    m = re.search(r"(?:year|half-year|period)\s+ended\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", head, re.I)
    if not m:
        m = re.search(r"as at\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", head, re.I)
    if m and m.group(2).lower() in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return None


def detect_entity(text):
    # Most frequent "<Name> Limited/Ltd/Group/Holdings" phrase (the entity recurs
    # throughout; other named companies do not).
    head = text[:200000]
    counts = {}
    for m in re.finditer(r"([A-Z][A-Za-z&.'\- ]{2,40}?(?:Limited|Ltd|Group|Holdings|PLC|plc))", head):
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        # drop obvious non-entity leading words
        name = re.sub(r"^(The|And|Of|For|To|In|A) ", "", name)
        if len(name) > 5:
            counts[name] = counts.get(name, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def has_any(text_lower, phrases):
    return any(p.lower() in text_lower for p in phrases)


def extract_amount(text, caption):
    """Return the current-period figure reported against a caption, or None.
    On the caption's line, prefer the first number with a comma/decimal (a real
    balance) over bare 1–2 digit integers (which are usually note references)."""
    for m in re.finditer(re.escape(caption), text, re.I):
        seg = text[m.end():m.end() + 90]
        nums = re.findall(r"\(?\$?(\d[\d,]*(?:\.\d+)?)\)?", seg)
        cand = [(("," in n or "." in n), float(n.replace(",", "")), n) for n in nums]
        if not cand:
            continue
        withcomma = [c for c in cand if c[0]]
        return withcomma[0][1] if withcomma else max(cand, key=lambda c: c[1])[1]
    return None


def extract_total_assets(text):
    for cap in ["TOTAL ASSETS", "Total assets", "Total Assets"]:
        v = extract_amount(text, cap)
        if v:
            return v
    return None


def extract_financials(text):
    """Extract key financial figures used for materiality benchmarks."""
    def first(*captions):
        for cap in captions:
            v = extract_amount(text, cap)
            if v and v > 0:
                return v
        return None

    total_assets   = first("TOTAL ASSETS", "Total assets", "Total Assets")
    total_liab     = first("TOTAL LIABILITIES", "Total liabilities", "Total Liabilities")
    net_assets     = first("NET ASSETS", "Net assets", "Total equity", "TOTAL EQUITY",
                           "Equity attributable", "Total Equity")
    # Fall back to assets minus liabilities
    if not net_assets and total_assets and total_liab:
        net_assets = total_assets - total_liab

    revenue        = first("Total revenue", "TOTAL REVENUE", "Revenue", "REVENUE",
                           "Total income", "TOTAL INCOME", "Net revenue")
    pbt            = first("Profit before income tax", "Loss before income tax",
                           "Profit/(loss) before income tax",
                           "(Loss)/profit before income tax",
                           "Profit before tax", "Loss before tax",
                           "PROFIT BEFORE TAX", "LOSS BEFORE TAX")
    total_exp      = first("Total expenses", "TOTAL EXPENSES",
                           "Total expenditure", "TOTAL EXPENDITURE",
                           "Total operating expenses", "Total costs")

    return {
        "totalAssets":   total_assets,
        "totalLiab":     total_liab,
        "netAssets":     net_assets,
        "revenue":       revenue,
        "profitBeforeTax": pbt,
        "totalExpenditure": total_exp,
    }


def extract_officers(text):
    """Extract directors, CFO and company secretary from the Company Directory page.

    Reads the Company Directory section (typically a single page before the
    Directors' Report) where each person is listed on their own line.  Falls
    back to the Directors' Report if no Company Directory is found.

    Returns a list of {name, role, roleNorm} dicts ordered by seniority.
    Silently returns [] on any extraction failure or when the section is absent.
    """
    try:
        _NORM = {
            "executive chairman": "Executive Chairman",
            "non-executive chairman": "Non-Executive Chairman",
            "independent non-executive chairman": "Non-Executive Chairman",
            "independent chairman": "Non-Executive Chairman",
            "chairman": "Chairman",
            "managing director": "Managing Director",
            "managing director / ceo": "Managing Director / CEO",
            "managing director/ceo": "Managing Director / CEO",
            "managing director and ceo": "Managing Director / CEO",
            "managing director & ceo": "Managing Director / CEO",
            "founder and director": "Executive Director",
            "executive director": "Executive Director",
            "non-executive director": "Non-Executive Director",
            "independent non-executive director": "Non-Executive Director",
            "independent director": "Non-Executive Director",
            "chief executive officer": "CEO",
            "chief financial officer": "CFO",
            "company secretary": "Company Secretary",
            "joint company secretary": "Company Secretary",
        }
        _ORDER = {
            "Executive Chairman": 0, "Non-Executive Chairman": 0, "Chairman": 0,
            "Managing Director": 1, "Managing Director / CEO": 1, "CEO": 2,
            "Executive Director": 3, "Non-Executive Director": 4,
            "CFO": 5, "Company Secretary": 6,
        }
        _INVALID_WORDS = {
            "ltd", "pty", "inc", "corp", "limited", "holdings",
            "terrace", "street", "road", "avenue", "drive", "lane",
            "web", "address", "code", "registry", "auditors", "solicitors",
        }
        _R = (
            r"Non-Executive\s+Chairman|Executive\s+Chairman|"
            r"Independent\s+(?:Non-Executive\s+)?Chairman|Chairman|"
            r"Managing\s+Director(?:\s*/\s*CEO|\s+and\s+CEO|\s+&\s+CEO)?|"
            r"Founder\s+and\s+Director|"
            r"Non-Executive\s+Director|Executive\s+Director|"
            r"Independent\s+(?:Non-Executive\s+)?Director|"
            r"Chief\s+Executive\s+Officer|Chief\s+Financial\s+Officer|"
            r"Company\s+Secretary|Joint\s+Company\s+Secretary"
        )
        _ROLE_RE = re.compile(r"(" + _R + r")\b", re.I)
        # Title prefix pattern — matches Mr/Ms/Mrs/Dr/Prof (optional dot, optional space)
        _TITLE = re.compile(
            r"^(?:Mr\.?\s*|Ms\.?\s*|Mrs\.?\s*|Dr\.?\s*|Prof\.?\s*)"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z']+){1,2})",
        )

        seen, officers = set(), []

        def _clean_name(raw: str) -> str:
            """Strip title prefix, parentheticals, trailing invalid words."""
            name = re.sub(r"^(?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?|Prof\.?)\s*", "", raw.strip())
            name = re.sub(r"\s*\([^)]+\)\s*", " ", name)   # remove (Raymond) etc.
            name = re.sub(r"\s{2,}", " ", name).strip()
            # Trim trailing words that are clearly not part of a person's name
            words = name.split()
            while len(words) > 1 and words[-1].lower() in _INVALID_WORDS:
                words = words[:-1]
            return " ".join(words)

        def _add(name: str, role_raw: str) -> None:
            name = _clean_name(name)
            if len(name.split()) < 2 or len(name) > 50:
                return
            if any(w.lower() in _INVALID_WORDS for w in name.split()):
                return
            key = name.lower()
            if key in seen:
                return
            seen.add(key)
            norm = _NORM.get(role_raw.strip().lower(), role_raw.strip())
            officers.append({"name": name, "role": role_raw.strip(), "roleNorm": norm})

        # ── Find the section to parse ─────────────────────────────────────────
        # Prefer the Company Directory page: one clean line per person, roles
        # appear within 2 lines.  Fall back to the Directors' Report only if
        # no Company Directory heading is present.
        #
        # NOTE: Australian PDF headings often use U+2019 right-single-quote
        # ("Directors’ Report") — use ’ in the pattern explicitly so
        # the editor cannot silently replace it with an ASCII apostrophe.
        cd_m = re.search(r"Company\s+Directory", text, re.I)
        dr_m = None
        # Find the *body* Directors' Report (skip TOC entry which is followed by a digit)
        for m in re.finditer(r"directors[’'‘]?\s*report", text, re.I):
            following = text[m.end(): m.end() + 200].strip()
            first = following.split()[0] if following.split() else ""
            if not first.isdigit():
                dr_m = m
                break

        if cd_m:
            # Company Directory: clip at "Share Registry" (end of people list)
            # to avoid running into the Directors’ Report on the next page.
            window = text[cd_m.start(): cd_m.start() + 3500]
            for end_pat in [r"Share\s+Registry", r"Annual\s+Financial\s+Report\s+for"]:
                em = re.search(end_pat, window, re.I)
                if em and em.start() > 300:
                    window = window[:em.start()]
                    break
            section = window
        elif dr_m:
            section = text[dr_m.start(): dr_m.start() + 20000]
            for marker in ["remuneration report", "financial statements",
                           "statement of profit", "auditor’s independence",
                           "auditor’s independence"]:
                em = re.search(re.escape(marker), section, re.I)
                if em and em.start() > 2500:
                    section = section[:em.start()]
                    break
        else:
            return []

        # ── Line-by-line extraction ───────────────────────────────────────────
        # Walk each line.  When a titled name is found:
        #   • If a pending role heading preceded it (CFO / Company Secretary),
        #     pair them immediately.
        #   • Otherwise scan the next 3 lines for a role that starts that line.
        #
        # Only CFO and Company Secretary headings set pending_role — regular
        # director roles (Executive Chairman, Managing Director …) appear AFTER
        # the name in the directory and must not be treated as headings for the
        # NEXT person.
        _HEADING_ROLES = {"chief financial officer", "company secretary",
                          "joint company secretary"}

        lines = section.split("\n")
        pending_role: str | None = None

        for idx, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line:
                continue

            # Strip parenthetical nicknames before matching so that
            # "Mr Siyuan (Raymond) Chan" → "Mr Siyuan Chan" and matches _TITLE.
            line_clean = re.sub(r"\([^)]+\)", " ", line)
            line_clean = re.sub(r"\s{2,}", " ", line_clean).strip()

            # Check for role-heading-before-name patterns (CFO, Company Secretary only)
            role_heading = _ROLE_RE.match(line_clean)
            if role_heading:
                role_key = role_heading.group(1).strip().lower()
                if role_key in _HEADING_ROLES:
                    # Always set pending_role — trailing right-column text on the
                    # same line (e.g. "Company Secretary Mia Yellagonga Tower 2")
                    # must not block detection of the name on the next line.
                    pending_role = role_heading.group(1)
                continue

            # Check whether this line starts with a titled name
            name_m = _TITLE.match(line_clean)
            if not name_m:
                # Non-name, non-role line — do NOT clear pending_role so it
                # survives junk lines between "Chief Financial Officer" and the name
                continue
                continue

            raw_name = name_m.group(1)

            if pending_role:
                # CFO / Company Secretary: role heading came before name
                _add(raw_name, pending_role)
                pending_role = None
            else:
                # Regular director: role appears on one of the next 3 lines
                for j in range(idx + 1, min(idx + 4, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    role_m = _ROLE_RE.match(next_line)
                    if role_m:
                        _add(raw_name, role_m.group(1))
                        break

        return sorted(officers, key=lambda o: _ORDER.get(o["roleNorm"], 99))
    except Exception:
        return []


def build_materiality_benchmarks(fins):
    """Return a list of benchmark rows for the materiality analysis table."""
    rows = []

    def add(basis, figure, pct, note=""):
        if figure and figure > 0:
            amount = round(pct / 100.0 * figure)
            rows.append({
                "basis": basis,
                "figure": round(figure),
                "pct": pct,
                "amount": amount,
                "note": note,
            })

    add("5% of total assets",  fins["totalAssets"],      5.0,
        "Common default for asset-heavy or pre-revenue entities")
    add("1% of total assets",  fins["totalAssets"],      1.0,
        "Conservative asset-based — financial institutions, property")
    add("2% of net assets",    fins["netAssets"],        2.0,
        "Net asset base — appropriate where equity is the key measure")
    add("1% of net assets",    fins["netAssets"],        1.0,
        "Conservative net asset — financial services")
    add("1% of revenue",       fins["revenue"],          1.0,
        "Revenue-driven businesses: retail, services, distribution")
    add("0.5% of revenue",     fins["revenue"],          0.5,
        "Conservative revenue-based — high-turnover, low-margin")
    add("5% of profit before tax", fins["profitBeforeTax"], 5.0,
        "Standard for consistently profitable entities")
    add("2% of total expenditure", fins["totalExpenditure"], 2.0,
        "Pre-revenue / exploration / biotech entities with minimal income")

    return rows


def balance_for(text, captions):
    """Sum the current-period figures for an item's governing captions (deduped by value)."""
    vals, seen = [], set()
    for cap in captions:
        v = extract_amount(text, cap)
        if v is not None and round(v) not in seen:
            seen.add(round(v)); vals.append(v)
    return sum(vals) if vals else None


def run_checklist(text, rtype, materiality=None, domicile="UNKNOWN"):
    with open(CHECKLIST, encoding="utf-8") as f:
        cfg = json.load(f)
    tl = text.lower()
    results = []
    for item in cfg["items"]:
        if rtype not in item.get("appliesTo", []):
            continue
        assessment = item.get("assessment", "qualitative")
        balance = None
        # Australian-only items are N/A for confirmed foreign-domiciled entities
        if item.get("auOnly") and domicile not in ("AU", "UNKNOWN"):
            r = _row(item, "N/A", assessment, None, materiality)
            r["naReason"] = "foreign-domiciled"
            results.append(r)
            continue
        expected_when = item.get("expectedWhen", [])
        expected = True if not expected_when else has_any(tl, expected_when)
        if not expected:
            status = "N/A"  # business-model: trigger absent
        else:
            # Quantitative items: gate on materiality of the underlying balance.
            if assessment == "quantitative" and item.get("balanceCaptions") and materiality:
                balance = balance_for(text, item["balanceCaptions"])
                if balance is not None and balance < materiality:
                    status = "BELOW MATERIALITY"
                    results.append(_row(item, status, assessment, balance, materiality))
                    continue
            detect_all = item.get("detectAll")
            if detect_all:
                present = all(any(p.lower() in tl for p in group) for group in detect_all)
            else:
                present = has_any(tl, item.get("detect", []))
            status = "PRESENT" if present else "NOT FOUND"
        results.append(_row(item, status, assessment, balance, materiality))
    return cfg["meta"], results


def _row(item, status, assessment, balance, materiality):
    return {
        "id": item["id"], "standard": item["standard"], "clause": item.get("clause", ""),
        "title": item["title"], "category": item.get("category"),
        "materiality": item.get("materiality", "medium"),
        "assessment": assessment, "balance": balance, "materialityThreshold": materiality,
        "status": status, "recommendation": item["recommendation"],
        "representationNote": item.get("representationNote", ""),
        "divergent": item.get("divergent", False),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--ticker", default=None)
    ap.add_argument("--type", default="auto", choices=["auto", "interim", "annual"])
    ap.add_argument("--out", default=os.path.join(KIT, "output"))
    ap.add_argument("--announcements", default=os.path.join(KIT, "announcements"))
    ap.add_argument("--no-asx", action="store_true")
    ap.add_argument("--download-asx", action="store_true")
    ap.add_argument("--as-of-period", action="store_true",
                    help="anchor the 12-month ASX window to the report's period-end (default: today)")
    ap.add_argument("--materiality", default=None, help="planning materiality in AUD (overrides the %-of-total-assets default)")
    ap.add_argument("--materiality-pct", type=float, default=5.0, help="materiality as %% of total assets when --materiality not given (default 5)")
    args = ap.parse_args()

    if not os.path.exists(args.report):
        print(f"ERROR: report not found: {args.report}"); return 2
    os.makedirs(args.out, exist_ok=True)

    print(f"[review] extracting {args.report} ...")
    text = extract_text(args.report)
    rtype = detect_type(text) if args.type == "auto" else args.type
    ticker = args.ticker or detect_ticker(text)
    entity = detect_entity(text) or "Reporting Entity"

    # Extract financials, board/management, and build all materiality benchmarks
    fins = extract_financials(text)
    officers = extract_officers(text)
    if officers:
        print(f"[review] directors/officers found: {len(officers)}")
    total_assets = fins["totalAssets"]
    mat_benchmarks = build_materiality_benchmarks(fins)

    # Working materiality for quantitative checklist gates: prefer manual override,
    # then 5% of total assets, then first benchmark available.
    if args.materiality:
        materiality = float(args.materiality)
        mat_basis = f"manual override ${materiality:,.0f}"
    elif total_assets:
        materiality = round(args.materiality_pct / 100.0 * total_assets)
        mat_basis = f"{args.materiality_pct:g}% of total assets ${total_assets:,.0f}"
    elif mat_benchmarks:
        materiality = mat_benchmarks[0]["amount"]
        mat_basis = f"{mat_benchmarks[0]['pct']}% of {mat_benchmarks[0]['basis'].split('%')[1].strip()} (auto-selected)"
    else:
        materiality, mat_basis = None, "not applied (financial figures not detected)"
    print(f"[review] entity='{entity}' ticker={ticker} type={rtype} | materiality={materiality} ({mat_basis})")

    # Domicile detection — company profile + announcement signals
    domicile_info = {"domicile": "UNKNOWN"}
    foreign_signals = []
    if ticker and not args.no_asx:
        try:
            sys.path.insert(0, HERE)
            from asx_history import fetch_company_profile
            domicile_info = fetch_company_profile(ticker)
            print(f"[review] domicile={domicile_info.get('domicile')} "
                  f"country={domicile_info.get('registeredCountry')} "
                  f"isin={domicile_info.get('isin')}")
        except Exception as e:
            print(f"[review] domicile detection skipped: {e}", file=sys.stderr)

    domicile = domicile_info.get("domicile", "UNKNOWN")
    meta, results = run_checklist(text, rtype, materiality, domicile)

    # ASX announcements — trailing 12 months.
    period_end = detect_period_end(text)
    asx = {"ticker": ticker, "online": False, "items": []}
    if ticker and not args.no_asx:
        try:
            cmd = [sys.executable, os.path.join(HERE, "asx_history.py"), ticker,
                   "--out", args.announcements, "--months", "12"]
            if args.as_of_period and period_end:
                cmd += ["--as-of", period_end]
            if args.download_asx:
                cmd.append("--download")
            subprocess.run(cmd, check=False)
            idx = os.path.join(args.announcements, ticker.upper(), "index.json")
            if os.path.exists(idx):
                with open(idx, encoding="utf-8") as f:
                    asx = json.load(f)
        except Exception as e:
            print(f"[review] ASX step skipped: {e}", file=sys.stderr)

    # Foreign-listing signals from announcement stream
    try:
        from asx_history import detect_foreign_signals
        foreign_signals = detect_foreign_signals(asx.get("items", []))
        if foreign_signals:
            # Upgrade domicile if profile said UNKNOWN but announcements say NZX
            if domicile == "UNKNOWN":
                exchanges = {s["exchange"] for s in foreign_signals}
                if "NZX" in exchanges:
                    domicile = "NZ"
                    domicile_info["domicile"] = "NZ"
                    domicile_info["domicileSource"] = "announcement-signals"
                else:
                    domicile = "FOREIGN"
                    domicile_info["domicile"] = "FOREIGN"
                    domicile_info["domicileSource"] = "announcement-signals"
                # Re-run checklist with upgraded domicile
                _, results = run_checklist(text, rtype, materiality, domicile)
            print(f"[review] foreign signals: {[s['exchange'] for s in foreign_signals]}")
    except Exception as e:
        foreign_signals = []
        print(f"[review] foreign signal detection skipped: {e}", file=sys.stderr)

    # Business-development opportunity RAG on each announcement (Growth Partners lens)
    try:
        from opportunity import classify_opportunity, RAG_MEANING
        counts = {"GREEN": 0, "AMBER": 0, "RED": 0}
        for it in asx.get("items", []):
            o = classify_opportunity(it)
            it["rag"], it["oppService"], it["oppRationale"] = o["rag"], o["service"], o["rationale"]
            it["priority"], it["importance"], it["theme"] = o["priority"], o["importance"], o["theme"]
            it["oppServices"] = o.get("services", [])
            counts[o["rag"]] = counts.get(o["rag"], 0) + 1
        asx["oppCounts"] = counts
        asx["ragMeaning"] = RAG_MEANING
    except Exception as e:
        print(f"[review] opportunity classification skipped: {e}", file=sys.stderr)

    summary = {
        "present": sum(1 for r in results if r["status"] == "PRESENT"),
        "not_found": sum(1 for r in results if r["status"] == "NOT FOUND"),
        "below_materiality": sum(1 for r in results if r["status"] == "BELOW MATERIALITY"),
        "na": sum(1 for r in results if r["status"] == "N/A"),
    }
    findings = {
        "entity": entity, "ticker": ticker, "reportType": rtype,
        "reportFile": os.path.basename(args.report),
        "basis": meta["basis"], "detectionNote": meta["detection_note"],
        "checklistVersion": meta["version"], "summary": summary,
        "materiality": materiality, "materialityBasis": mat_basis, "totalAssets": total_assets,
        "domicile": domicile,
        "domicileInfo": domicile_info,
        "foreignSignals": foreign_signals,
        "officers": officers,
        "financials": fins,
        "materialityBenchmarks": mat_benchmarks,
        "results": results, "asx": asx,
    }
    out_json = os.path.join(args.out, "findings.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=1)
    print(f"[review] PRESENT={summary['present']} NOT FOUND={summary['not_found']} "
          f"N/A={summary['na']} -> {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
