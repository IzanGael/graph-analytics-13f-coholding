"""Topic 1: pull contracts for one procurement group from the World Bank Contracts API to JSONL.

Usage: python -I t1_pull.py <out.jsonl> [procurement_group]
"""
import json
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://search.worldbank.org/api/contractdata"
UA = {"User-Agent": "graph-analytics-coursework/0.1"}
FIELDS = ("contr_id,contr_sgn_date,year,countryshortname,regionname,projectid,project_name,"
          "total_contr_amnt,procurement_group,procu_meth_text,rvw_type,suppinfo,"
          "sector,sectorcode,mjsecname,mjsector")
PAGE = 5000


def fetch(offset, group):
    params = {"format": "json", "rows": PAGE, "os": offset, "fl": FIELDS,
              "procurement_group_exact": group}
    url = BASE + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            print(f"retry {attempt} at os={offset}: {exc}", flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"gave up at os={offset}")


def main(out, group="CS"):
    start = time.time()
    offset, total, written = 0, None, 0
    with open(out, "w", encoding="utf-8") as fh:
        while total is None or offset < total:
            d = fetch(offset, group)
            total = int(d["total"])
            rows = d.get("contract") or []
            if not rows:
                print(f"empty page at os={offset}", flush=True)
                break
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += len(rows)
            offset += PAGE
            print(f"{written}/{total} in {time.time() - start:.0f}s", flush=True)
            time.sleep(1)
    print(f"DONE rows={written} total={total} secs={time.time() - start:.0f}", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
