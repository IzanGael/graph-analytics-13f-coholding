"""Read-only: look up the six large unmapped companies in the SEC name file and the SEC submissions API."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # shared modules live in src/

import json

from config import RAW
from s02_map_sectors import sec_json

SEARCH = {"BROOKFIELD": ["BROOKFIELD CORP", "BROOKFIELD ASSET MANAGEMENT"], "JOHNSON CONTROLS": ["JOHNSON CONTROLS INTERNATIONAL"],
          "ROYAL CARIBBEAN": ["ROYAL CARIBBEAN"], "CRH": ["CRH PLC", "CRH PUBLIC"], "FERGUSON": ["FERGUSON"],
          "FIRST REPUBLIC": ["FIRST REPUBLIC BANK", "FIRST REPUBLIC PREFERRED"]}
lines = [l.rstrip("\n").rsplit(":", 2) for l in open(RAW / "sec" / "cik-lookup-data.txt", encoding="latin-1")]
tick = {int(v["cik_str"]): v["ticker"] for v in json.load(open(RAW / "sec" / "company_tickers.json", encoding="utf-8")).values()}
for label, pats in SEARCH.items():
    print("==", label)
    seen = set()
    for name, cik, _ in lines:
        if any(name.startswith(p) for p in pats) and cik.isdigit() and (name, cik) not in seen:
            seen.add((name, cik))
            if len(seen) <= 14:
                print(f"   {name}  CIK {int(cik)}  listed ticker: {tick.get(int(cik))}")
for cik in (1001085, 1937926, 833444, 884887, 849395, 1832633, 2000828):
    try:
        d = sec_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", RAW / "sec" / "submissions" / f"{cik}.json")
        print(cik, d.get("name"), "| SIC", d.get("sic"), d.get("sicDescription"), "| tickers", d.get("tickers"), "| former", [n["name"] for n in d.get("formerNames", [])][:3])
    except Exception as exc:
        print(cik, "lookup failed:", type(exc).__name__)
