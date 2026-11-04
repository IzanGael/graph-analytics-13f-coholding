"""Topic 1: probe the World Bank Contracts API (paging, page-size limit, filters, latency)."""
import json
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://search.worldbank.org/api/contractdata"
UA = {"User-Agent": "graph-analytics-coursework/0.1"}


def get(**params):
    url = BASE + "?" + urllib.parse.urlencode({"format": "json", **params})
    start = time.time()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
    return json.loads(raw), len(raw), time.time() - start, url


def summarise(label, **params):
    try:
        d, size, secs, url = get(**params)
    except Exception as exc:
        print(f"{label:38s} ERROR {exc}")
        return None
    rows = d.get("contract") or d.get("contracts") or d.get("documents") or {}
    n = len(rows)
    print(f"{label:38s} total={d.get('total')} rows={d.get('rows')} os={d.get('os')} "
          f"returned={n} bytes={size} secs={secs:.2f}")
    return d, rows


if __name__ == "__main__":
    first = summarise("default")
    d, rows = first
    print("top-level keys:", list(d.keys()))
    sample = rows if isinstance(rows, list) else list(rows.values())
    print(json.dumps(sample[0], indent=1)[:2500])
    for size in (100, 500, 1000, 5000, 10000, 20000):
        summarise(f"rows={size}", rows=size)
    # Does paging work, and how deep?
    for os_ in (1000, 10000, 100000, 400000, 487000):
        summarise(f"rows=100 os={os_}", rows=100, os=os_)
    # Filter candidates
    summarise("procurement_group=CS", rows=10, procurement_group="CS")
    summarise("procurement_group_exact=CS", rows=10, procurement_group_exact="CS")
    summarise("fl subset", rows=10, fl="supp_name,suppinfo,countryshortname,contr_sgn_date")
    sys.stdout.flush()
