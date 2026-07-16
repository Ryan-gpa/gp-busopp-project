"""
hubspot_sync.py — push ASIC infringement contacts from the local DB into HubSpot.

Agent-safe: reads the HubSpot token from webapp/.env (NO interactive prompt), so
Claude, Gemini, or a cron can all run it head-less. It upserts via the CRM v3 API
(POST, then PATCH on 409), flags every contact lead_source_gp=ASIC + gp_campaign=ASIC,
and by default only pushes credible contacts (real corporate email that matches the
company — skips free-mail and wrong-company addresses).

Setup once:  add a line to webapp/.env
    HUBSPOT_TOKEN=<private app token>
(HubSpot → Settings → Integrations → Private Apps → scopes crm.objects.contacts.read + write)

Usage:
    python webapp/api/scripts/hubspot_sync.py                 # push credible ASIC contacts
    python webapp/api/scripts/hubspot_sync.py --dry-run       # preview, no writes
    python webapp/api/scripts/hubspot_sync.py --source hunter # only contacts found via Hunter
    python webapp/api/scripts/hubspot_sync.py --all           # skip the quality filter
    python webapp/api/scripts/hubspot_sync.py --limit 20
"""
import sqlite3, json, requests, os, sys, re, argparse
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    sys.exit("Missing dependency: pip install python-dotenv")

HERE = Path(__file__).resolve().parent          # webapp/api/scripts
WEBAPP = HERE.parent.parent                       # webapp
load_dotenv(WEBAPP / ".env")                      # <-- the fix: actually load the token

HUBSPOT_URL = "https://api.hubapi.com/crm/v3/objects/contacts"
FREE_MAIL = {"aol.com", "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
             "icloud.com", "proton.me", "live.com", "me.com", "googlemail.com"}
STOP = {"the", "pty", "ltd", "limited", "holdings", "group", "australia", "au", "nz",
        "company", "corporation", "co", "brands", "foods", "electrics", "aust",
        "hennes", "mauritz", "services", "investments", "super"}


def _brand(company: str) -> str:
    toks = [t for t in re.sub(r"[^a-z0-9 ]", " ", (company or "").lower()).split()
            if t not in STOP and len(t) > 2]
    return toks[0] if toks else ""


def is_credible(email: str, company: str):
    """Real corporate email whose domain matches the company brand."""
    if not email or "@" not in email:
        return False, "no email"
    dom = email.split("@")[-1].lower()
    if dom in FREE_MAIL:
        return False, "free-mail"
    b = _brand(company)
    if b and b in dom.replace(".", ""):
        return True, "domain match"
    return False, f"domain {dom} != {company or '?'}"


def _db_path() -> Path:
    for p in (HERE.parent / "unified_companies.db",
              Path("webapp/api/unified_companies.db"), Path("unified_companies.db")):
        if p.exists():
            return p
    sys.exit("unified_companies.db not found — run from repo root.")


def main():
    ap = argparse.ArgumentParser(description="Push ASIC contacts to HubSpot.")
    ap.add_argument("--source", help="only sync contacts with this source (hunter/rocketreach/apollo/organic_web/organic_exa)")
    ap.add_argument("--limit", type=int, help="max contacts to push")
    ap.add_argument("--all", action="store_true", help="skip the domain/quality filter (push every contact with an email)")
    ap.add_argument("--dry-run", action="store_true", help="preview only, no HubSpot writes")
    args = ap.parse_args()

    token = os.environ.get("HUBSPOT_TOKEN") or os.environ.get("HUBSPOT_API_KEY")
    if not token:
        sys.exit(
            "ERROR: no HubSpot token found.\n"
            "  Add  HUBSPOT_TOKEN=<private app token>  to webapp/.env and re-run.\n"
            "  (HubSpot → Settings → Integrations → Private Apps → scopes "
            "crm.objects.contacts.read + crm.objects.contacts.write)\n"
            "  No interactive prompt is used, so any agent/cron can run this head-less."
        )

    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        """SELECT c.email, c.name, c.title, c.linkedin_url, c.source, c.raw_json,
                  comp.name AS company
             FROM contacts c
             LEFT JOIN companies comp ON c.acn = comp.acn
            WHERE c.org_id LIKE 'asic_%' AND c.email IS NOT NULL AND c.email != ''""")]
    conn.close()
    if args.source:
        rows = [r for r in rows if (r["source"] or "") == args.source]

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    created = updated = skipped = errors = 0
    print(f"{len(rows)} ASIC contacts with an email; filter={'off' if args.all else 'on'}, dry_run={args.dry_run}")

    for r in rows:
        if args.limit and (created + updated) >= args.limit:
            break
        ok, why = (True, "override") if args.all else is_credible(r["email"], r["company"])
        if not ok:
            skipped += 1
            print(f"  SKIP  {r['email']:38} [{why}]")
            continue

        first, _, last = (r["name"] or "").partition(" ")
        conf = "smtp_verified"
        try:
            rj = json.loads(r["raw_json"]) if r["raw_json"] else {}
            if (r["source"] or "") in ("organic_web", "organic_exa") and rj.get("emailStatus") != "verified":
                conf = "permutation_only"
        except Exception:
            pass

        props = {
            "email": r["email"],
            "firstname": first or (r["name"] or ""),
            "lastname": last or first or "",
            "jobtitle": (r["title"] or "")[:200],
            "company": r["company"] or "",
            "website": r["email"].split("@")[-1],
            "hs_linkedin_url": r["linkedin_url"] or "",
            "hs_lead_status": "NEW",
            "lead_source_gp": "ASIC",
            "gp_campaign": "ASIC",
            "gp_email_confidence": conf,
        }
        if args.dry_run:
            print(f"  DRY   {r['email']:38} -> {props['firstname']} {props['lastname']} @ {props['company']}")
            created += 1
            continue

        res = requests.post(HUBSPOT_URL, json={"properties": props}, headers=headers, timeout=30)
        if res.status_code == 409:
            m = re.search(r"ID:\s*(\d+)", res.text)
            if m:
                pr = requests.patch(f"{HUBSPOT_URL}/{m.group(1)}", json={"properties": props}, headers=headers, timeout=30)
                if pr.status_code in (200, 201):
                    updated += 1; print(f"  UPDATE {r['email']:38} ({r['source']})")
                else:
                    errors += 1; print(f"  ERR patch {r['email']}: {pr.text[:120]}")
            else:
                errors += 1; print(f"  ERR 409 no-id {r['email']}: {res.text[:120]}")
        elif res.status_code in (200, 201):
            created += 1; print(f"  CREATE {r['email']:38} ({r['source']})")
        else:
            errors += 1; print(f"  ERR {r['email']}: {res.status_code} {res.text[:120]}")

    print(f"\nDone. created={created} updated={updated} skipped={skipped} errors={errors}")
    if skipped and not args.all:
        print("  (skipped = free-mail or domain-mismatch; re-run with --all to force, or --dry-run to inspect)")


if __name__ == "__main__":
    main()
