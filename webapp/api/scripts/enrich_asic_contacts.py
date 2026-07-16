"""
enrich_asic_contacts.py — find contacts for ASIC infringement companies using
any enrichment tool we have (Hunter.io, RocketReach, Apollo), then persist them.

Reuses the app's own /api/unlisted/contacts dispatch (find_contacts), so "any tool"
means exactly the sources the app supports and nothing has to be re-implemented here.

Setup: keys live in webapp/.env (HUNTER_API_KEY, ROCKETREACH_API_KEY, APOLLO_API_KEY).

Usage:
    python webapp/api/scripts/enrich_asic_contacts.py                     # auto (Hunter if domain, else RocketReach), 20 cos
    python webapp/api/scripts/enrich_asic_contacts.py --source hunter --limit 50
    python webapp/api/scripts/enrich_asic_contacts.py --source rocketreach
    python webapp/api/scripts/enrich_asic_contacts.py --source apollo
    python webapp/api/scripts/enrich_asic_contacts.py --refresh           # re-enrich even companies that already have contacts

Then push:
    python webapp/api/scripts/hubspot_sync.py        # -> HubSpot (needs HUBSPOT_TOKEN in .env)
    python webapp/api/scripts/sync_to_prod.py        # -> Railway prod DB
"""
import sys, os, argparse, time
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent))          # import main
load_dotenv(Path(__file__).parent.parent.parent / ".env")   # webapp/.env
os.environ["DATA_DIR"] = str(Path(__file__).parent.parent)  # real DB lives in webapp/api

from main import _unlisted_cache_conn, _company_identity_for_org, find_contacts


def get_targets(refresh: bool):
    """ASIC org_ids to enrich — those with no contacts yet, or all if --refresh."""
    conn = _unlisted_cache_conn()
    try:
        if refresh:
            q = "SELECT apollo_id FROM companies WHERE apollo_id LIKE 'asic_%'"
        else:
            q = """SELECT c.apollo_id FROM companies c
                     LEFT JOIN contacts_cache cc ON c.apollo_id = cc.org_id
                    WHERE c.apollo_id LIKE 'asic_%'
                      AND (cc.org_id IS NULL OR cc.contacts_json = '[]')"""
        return [r[0] for r in conn.execute(q).fetchall()]
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="Enrich ASIC companies via Hunter/RocketReach/Apollo.")
    ap.add_argument("--source", default="auto",
                    choices=["auto", "hunter", "rocketreach", "apollo"],
                    help="which enrichment tool to use (default: auto = Hunter if domain known, else RocketReach)")
    ap.add_argument("--limit", type=int, default=20, help="max companies to process")
    ap.add_argument("--refresh", action="store_true", help="re-enrich companies that already have contacts")
    args = ap.parse_args()

    ids = get_targets(args.refresh)
    print(f"{len(ids)} ASIC companies to enrich (source={args.source}); processing up to {args.limit}...")

    done = found = 0
    for org_id in ids:
        if done >= args.limit:
            break
        name, _ = _company_identity_for_org(org_id)
        try:
            res = find_contacts(org_id, source=args.source, force=True)  # app dispatch persists to cache + live DB
            n = len(res.get("contacts") or [])
            found += n
            print(f"[{done+1:>3}] {(name or org_id)[:40]:40} -> {n} contacts via {res.get('source', args.source)}")
        except Exception as e:
            print(f"[{done+1:>3}] {(name or org_id)[:40]:40} -> ERROR: {e}")
        done += 1
        time.sleep(1)  # be polite to the enrichment APIs

    print(f"\nDone. {done} companies processed, {found} contacts found.")
    print("Next: python webapp/api/scripts/hubspot_sync.py   (push credible contacts to HubSpot)")


if __name__ == "__main__":
    main()
