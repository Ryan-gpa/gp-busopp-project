"""Business-development opportunity classifier for Growth Partners Advisory.

Maps each ASX announcement to a RAG opportunity signal (and the GP service it points
to) using config/opportunity_map.json. RED is the default when nothing matches.
"""
import json, os

_KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MAP = os.path.join(_KIT, "config", "opportunity_map.json")
with open(_MAP, encoding="utf-8") as f:
    _CFG = json.load(f)
_RULES = _CFG["rules"]
RAG_MEANING = _CFG["meta"]["ragMeaning"]
_BANDS = _CFG["meta"].get("priorityBands", {})


def _band(priority):
    return _BANDS.get(str(priority), "None")


def _norm(s):
    # normalise apostrophe variants (straight, curly, missing) so tokens match robustly
    return (s or "").lower().replace("’", "").replace("'", "")


def _extract_pdf_text(pdf_path):
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return "\n".join(pages)
    except Exception:
        return ""


def classify_opportunity(item):
    # Load custom rules
    custom_rules = []
    rules_file = os.path.join(_KIT, "config", "announcement_rules.json")
    if os.path.exists(rules_file):
        try:
            with open(rules_file, encoding="utf-8") as f:
                custom_rules = json.load(f).get("rules", [])
        except Exception:
            pass

    item_type = item.get("type") or ""
    headline = item.get("headline") or ""

    # Evaluate custom rules first
    if custom_rules:
        pdf_text = None
        for rule in custom_rules:
            r_type = rule.get("announcementType")
            r_text = rule.get("text")
            r_action = rule.get("action", "include")
            
            if r_type and r_text and r_type.lower() in item_type.lower():
                # Check in headline
                match_found = r_text.lower() in headline.lower()
                
                # Check in PDF text if headline did not match
                if not match_found:
                    if pdf_text is None:
                        pdf_text = ""
                        local_path = item.get("localFile")
                        if local_path:
                            if not os.path.isabs(local_path):
                                path_opt1 = os.path.join(_KIT, local_path)
                                path_opt2 = os.path.join(_KIT, "announcements", item.get("ticker", "NVU").upper(), os.path.basename(local_path))
                                if os.path.exists(path_opt1):
                                    pdf_text = _extract_pdf_text(path_opt1)
                                elif os.path.exists(path_opt2):
                                    pdf_text = _extract_pdf_text(path_opt2)
                                else:
                                    ann_dir = os.path.join(_KIT, "announcements")
                                    key = item.get("documentKey")
                                    if key:
                                        import glob
                                        matches = glob.glob(os.path.join(ann_dir, "**", f"*{key[-8:]}*.pdf"), recursive=True)
                                        if matches:
                                            pdf_text = _extract_pdf_text(matches[0])
                            else:
                                if os.path.exists(local_path):
                                    pdf_text = _extract_pdf_text(local_path)
                    
                    match_found = r_text.lower() in pdf_text.lower()
                
                if match_found:
                    if r_action == "exclude":
                        return {
                            "rag": "RED",
                            "service": "—",
                            "rationale": f"Excluded by custom search rule for text '{r_text}'",
                            "ruleId": "custom_exclude",
                            "priority": 5,
                            "importance": "None",
                            "theme": "Administrative",
                            "services": []
                        }
                    else:  # include
                        return {
                            "rag": "GREEN",
                            "service": "Transaction Readiness",
                            "rationale": f"Included by custom search rule for text '{r_text}'",
                            "ruleId": "custom_include",
                            "priority": 1,
                            "importance": "High",
                            "theme": "Strategic transaction",
                            "services": ["Transaction Readiness"]
                        }

    # Evaluate default rules
    hay = _norm((item.get("type") or "") + " " + (item.get("headline") or ""))
    for r in _RULES:
        if any(_norm(tok) in hay for tok in r["match"]):
            return {"rag": r["rag"], "service": r["service"], "rationale": r["rationale"],
                    "ruleId": r["id"], "priority": r.get("priority", 5), "importance": _band(r.get("priority", 5)),
                    "theme": r.get("theme", "Other"), "services": r.get("services", [])}
    return {"rag": "RED", "service": "—", "rationale": "No direct service trigger identified.",
            "ruleId": "none", "priority": 5, "importance": "None", "theme": "Administrative", "services": []}
