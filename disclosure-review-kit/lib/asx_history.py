"""ASX announcement history engine — paginated full-history fetch.

Uses the ASX (markitdigital) markets endpoint that the asx.com.au announcements page
itself calls:

    /asx-research/1.0/markets/announcements?entityXids=<xid>&page=<n>&itemsPerPage=100

This endpoint PAGINATES (unlike the capped /companies/{ticker}/announcements widget,
which only ever returns the latest 5). We page through it until we pass the trailing
12-month boundary, accumulating every announcement, then de-duplicate, clamp to the
window, and optionally download the PDFs. The local folder is still merged in.

Ticker -> entityXid resolution uses a small cache (extend as needed) or an explicit
--xid. The Bearer token below is the public static token used by the ASX website.

Usage:
    python asx_history.py NVU --out ../announcements --months 12 [--download] [--xid 493241600]
"""
import argparse, json, os, re, sys, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

TOKEN = "83ff96335c2d45a094df02a206a39ff4"   # public token used by asx.com.au
BASE = "https://asx.api.markitdigital.com/asx-research/1.0"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
           "Origin": "https://www.asx.com.au", "Referer": "https://www.asx.com.au/",
           "Authorization": "Bearer " + TOKEN}
FILE_URL = BASE + "/file/{key}"
ANN_URL = BASE + "/markets/announcements?entityXids={xid}&page={page}&itemsPerPage={ipp}"
CAPPED_URL = BASE + "/companies/{ticker}/announcements?pageSize=5"   # fallback (latest 5)
RESOLVE_URL = BASE + "/search/predictive?searchText={ticker}"        # ticker -> entity xid

# ticker -> entity xid fast-path cache (resolver fills this automatically too).
XID_CACHE = {"NVU": 493241600, "BHP": 199003248, "CBA": 204245597}

RELEVANT = re.compile(
    r"(half[\s-]?year|interim|annual report|appendix 4[de]|4c|full year|financial report|"
    r"results|dividend|capital rais|placement|entitlement|acquisition|guidance|"
    r"agm|notice of meeting|change in substantial|director'?s interest|prospectus)", re.I)


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
        return json.load(r)


def resolve_xid(ticker, override=None):
    """Resolve an ASX ticker to its markitdigital entity xid.
    Order: explicit override -> cache -> live predictive search."""
    if override:
        return int(override)
    t = ticker.upper()
    if t in XID_CACHE:
        return XID_CACHE[t]
    try:
        d = _get(RESOLVE_URL.format(ticker=t))
        items = d.get("data", {}).get("items") or []
        exact = next((i for i in items if (i.get("symbol") or "").upper() == t), items[0] if items else None)
        if exact and exact.get("xidEntity"):
            XID_CACHE[t] = int(exact["xidEntity"])
            return XID_CACHE[t]
    except Exception as e:
        print(f"[asx_history] xid resolve failed for {t}: {str(e)[:60]}", file=sys.stderr)
    return None


def to_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_paginated(xid, cutoff, ipp=100, max_pages=30):
    """Page through the announcements endpoint until we pass the cutoff date."""
    out, page = [], 0
    while page < max_pages:
        d = _get(ANN_URL.format(xid=xid, page=page, ipp=ipp))
        items = d.get("data", {}).get("items") or []
        if not items:
            break
        out += items
        oldest = to_dt(items[-1].get("date"))
        if oldest and oldest < cutoff:
            break
        page += 1
    return out


def normalise(it, source):
    types = it.get("announcementTypes") or ([it.get("announcementType")] if it.get("announcementType") else [])
    return {
        "date": it.get("date"),
        "headline": it.get("headline"),
        "type": ", ".join(t for t in types if t) or it.get("type") or "",
        "priceSensitive": it.get("isPriceSensitive"),
        "documentKey": it.get("documentKey"),
        "keyTail": it.get("keyTail") or (it.get("documentKey")[-8:] if it.get("documentKey") else None),
        "fileSize": it.get("fileSize"),
        "relevant": bool(RELEVANT.search((it.get("headline") or "") + " " + " ".join(types))),
        "localFile": it.get("localFile"),
        "source": it.get("source", source),
    }


def read_local(ticker, announce_dir):
    tdir = os.path.join(announce_dir, ticker.upper())
    items = []
    if not os.path.isdir(tdir):
        return items
    for fn in sorted(os.listdir(tdir)):
        if fn.lower().endswith(".pdf"):
            m = re.match(r"(\d{4}-\d{2}-\d{2})", fn)
            tail = re.search(r"_([A-Za-z0-9]{8})\.pdf$", fn)
            items.append({"date": (m.group(1) + "T00:00:00.000Z") if m else None,
                          "headline": re.sub(r"^\d{4}-\d{2}-\d{2}_", "", fn).rsplit("_", 1)[0].replace("_", " "),
                          "announcementTypes": ["(local file)"], "isPriceSensitive": None,
                          "documentKey": None, "keyTail": tail.group(1) if tail else None,
                          "fileSize": None, "localFile": os.path.join(tdir, fn), "source": "local"})
    return items


def dedupe(items):
    seen, out = {}, []
    for it in items:
        key = it.get("keyTail") or ((it.get("date") or "")[:10] + "|" + (it.get("headline") or "").lower()[:40])
        if key in seen:
            kept = seen[key]
            if not kept.get("localFile") and it.get("localFile"):
                kept["localFile"] = it["localFile"]
            continue
        seen[key] = it
        out.append(it)
    return out


def download_docs(items, ticker, announce_dir):
    tdir = os.path.join(announce_dir, ticker.upper())
    os.makedirs(tdir, exist_ok=True)
    n = 0
    for it in items:
        if it.get("documentKey") and not it.get("localFile"):
            safe = re.sub(r"[^A-Za-z0-9]+", "_", it.get("headline") or "doc")[:55].strip("_")
            dest = os.path.join(tdir, f"{(it.get('date') or '')[:10]}_{safe}_{it['documentKey'][-8:]}.pdf")
            try:
                if not os.path.exists(dest):
                    req = urllib.request.Request(FILE_URL.format(key=it["documentKey"]), headers={"User-Agent": "Mozilla/5.0", "Authorization": "Bearer " + TOKEN})
                    with urllib.request.urlopen(req, timeout=60) as r:
                        data = r.read()
                    if data[:5] == b"%PDF-":
                        open(dest, "wb").write(data); n += 1
                if os.path.exists(dest):
                    it["localFile"] = os.path.relpath(dest)
            except Exception as e:
                print(f"[asx_history] download failed: {str(e)[:60]}", file=sys.stderr)
    return n


def build_history(ticker, months=12, announce_dir="announcements", as_of=None, download=False, xid=None):
    end = to_dt(as_of + "T00:00:00+00:00") if as_of else datetime.now(timezone.utc)
    start = end - timedelta(days=int(months * 30.44))

    online, method, items = True, None, []
    xid = resolve_xid(ticker, xid)
    try:
        if xid:
            method = "paginated"
            raw = fetch_paginated(xid, start)
            items = [normalise(it, "asx") for it in raw]
        else:
            method = "capped-fallback"
            d = _get(CAPPED_URL.format(ticker=ticker.upper()))
            items = [normalise(it, "asx") for it in (d.get("data", {}).get("items") or [])]
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, Exception) as e:
        online = False
        print(f"[asx_history] API error ({type(e).__name__}: {str(e)[:70]}); using local folder only.", file=sys.stderr)

    if download and online:
        download_docs(items, ticker, announce_dir)

    items += [normalise(it, "local") for it in read_local(ticker, announce_dir)]
    items = dedupe(items)
    in_window = [it for it in items if (to_dt(it.get("date")) is None) or (start <= to_dt(it["date"]) <= end)]
    in_window.sort(key=lambda x: (x.get("date") or ""), reverse=True)

    return {
        "ticker": ticker.upper(), "entityXid": xid, "online": online, "method": method,
        "periodStart": start.strftime("%Y-%m-%d"), "periodEnd": end.strftime("%Y-%m-%d"), "months": months,
        "apiCapped": method == "capped-fallback",
        "count": len(in_window),
        "priceSensitive": sum(1 for i in in_window if i.get("priceSensitive")),
        "relevant": sum(1 for i in in_window if i.get("relevant")),
        "fromApi": len([i for i in in_window if i["source"] == "asx"]),
        "fromLocal": len([i for i in in_window if i["source"] == "local"]),
        "items": in_window,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--out", default="announcements")
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--xid", default=None, help="entity xid override (if ticker not in cache)")
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()

    res = build_history(args.ticker, args.months, args.out, args.as_of, args.download, args.xid)
    tdir = os.path.join(args.out, args.ticker.upper())
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(tdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)

    print(f"[asx_history] {res['ticker']} (xid={res['entityXid']}, method={res['method']}): "
          f"{res['count']} announcements in {res['periodStart']}..{res['periodEnd']} "
          f"({res['priceSensitive']} price-sensitive, {res['relevant']} review-relevant; "
          f"api={res['fromApi']}, local={res['fromLocal']})")
    if res["method"] == "capped-fallback":
        print(f"[asx_history] NOTE: no entity xid for {res['ticker']} — fell back to the capped latest-5 feed. "
              f"Add it to XID_CACHE or pass --xid for full history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
