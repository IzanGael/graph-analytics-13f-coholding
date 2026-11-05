"""Step 2b: propose CIKs for stocks that s02 could not map, from the SEC's bulk name-to-CIK file.

Rules, in order, for each unmapped non-fund stock:
  unique    one SEC entity has the cleaned name
  listed    several do, and exactly one is in the SEC's current ticker list
  fuzzy     none does; closest SEC name sharing the first word, similarity >= FUZZY_MIN with a clear margin
  review    anything else; no proposal
Proposals only: nothing is written into the mapping until they are approved.
Output: results/name_candidates.csv. SIC is fetched for the proposals as a plausibility check.
"""
import difflib
import json
import re

import pandas as pd

from config import INTERIM, RAW, RESULTS
from s02_map_sectors import candidates, sec_json

FUZZY_MIN = 0.86
FUZZY_MARGIN = 0.03
TOP_N = 300
ABBREV = {"INTL": "INTERNATIONAL", "HLDNGS": "HOLDINGS", "HLDGS": "HOLDINGS", "HLDG": "HOLDING", "TECH": "TECHNOLOGY",
          "GRP": "GROUP", "FINL": "FINANCIAL", "ENTMT": "ENTERTAINMENT", "SYS": "SYSTEMS", "MGMT": "MANAGEMENT",
          "PPTY": "PROPERTY", "PPTYS": "PROPERTIES", "RES": "RESOURCES", "NAT": "NATURAL", "ENGR": "ENGINEERING",
          "INDS": "INDUSTRIES", "MATLS": "MATERIALS", "COS": "COMPANIES", "AMER": "AMERICA", "PAC": "PACIFIC",
          "RY": "RAILWAY", "CAP": "CAPITAL", "BK": "BANK", "REP": "REPUBLIC", "SVCS": "SERVICES", "TECHNOLOGIES": "TECHNOLOGY",
          "PHARMACEUTICALS": "PHARMACEUTICAL", "COMMUNICATIONS": "COMMUNICATION", "LABS": "LABORATORIES"}
DROP = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "NV", "SA", "AG", "SE", "LLC", "LP", "THE",
        "NEW", "DEL", "COM", "ADR", "SPONSORED", "CL", "CLASS", "A", "B", "C", "ORD", "SHS", "REG", "N", "V", "S", "CAN", "IRELAND",
        "DE", "HOLDINGS", "HOLDING", "GROUP", "TRUST", "TR", "INTERNATIONAL", "PUB", "PL", "PLC", "UK", "LT", "NY"}


def key(name):
    name = re.sub(r"/[A-Z]{2,4}/", " ", str(name).upper())          # /CAN/, /DE/ suffixes in the SEC file
    words = re.sub(r"[^A-Z0-9 ]", " ", name).split()
    words = [ABBREV.get(w, w) for w in words]
    return " ".join(w for w in words if w not in DROP)


def main():
    imap = pd.read_parquet(INTERIM / "issuer_map.parquet")
    need = imap[~imap["is_fund"] & imap["sic"].isna()].copy().drop(columns=["cik"])
    cand = candidates()
    need["best_rank"] = need["ISSUER"].map(cand.groupby("ISSUER")["rank"].min())
    need["key"] = need["NAME"].map(key)

    rows = []
    with open(RAW / "sec" / "cik-lookup-data.txt", encoding="latin-1") as fh:
        for line in fh:
            name, cik, _ = line.rstrip("\n").rsplit(":", 2)
            if cik.isdigit():
                rows.append((key(name), name, int(cik)))
    sec = pd.DataFrame(rows, columns=["key", "sec_name", "cik"])
    sec = sec[sec["key"].str.len() > 0]
    # Vectorised: a Python function per group over a million keys took over 20 minutes
    pairs = sec.drop_duplicates(["key", "cik"])
    n_ciks = pairs.groupby("key").size()
    ciks_of = {k: g["cik"].tolist() for k, g in pairs[pairs["key"].map(n_ciks) > 1].groupby("key")}
    ciks_of.update(dict(zip(*(lambda s: (s["key"], s["cik"].map(lambda c: [c])))(pairs[pairs["key"].map(n_ciks) == 1]))))
    first_name = sec.drop_duplicates("key").set_index("key")["sec_name"]
    by_key = pd.DataFrame({"ciks": pd.Series(ciks_of), "sec_name": first_name}).dropna(subset=["ciks"])
    listed = {int(v["cik_str"]) for v in json.load(open(RAW / "sec" / "company_tickers.json", encoding="utf-8")).values()}
    first_word = {}
    for k in by_key.index:
        first_word.setdefault(k.split(" ", 1)[0], []).append(k)
    print(f"SEC names: {len(sec):,}; distinct keys: {len(by_key):,}; currently listed CIKs: {len(listed):,}", flush=True)

    out = []
    for r in need.sort_values("best_rank").itertuples():
        method, cik, sec_name, score, note = "review", None, None, None, ""
        if r.key in by_key.index:
            ciks, sec_name = by_key.loc[r.key, "ciks"], by_key.loc[r.key, "sec_name"]
            if len(ciks) == 1:
                method, cik = "unique", ciks[0]
            else:
                hits = [c for c in ciks if c in listed]
                note = f"{len(ciks)} CIKs share the name"
                if len(hits) == 1:
                    method, cik = "listed", hits[0]
                    sec_name = sec.loc[sec["cik"] == cik, "sec_name"].iloc[0]
        elif r.key:
            pool = first_word.get(r.key.split(" ", 1)[0], [])
            scored = sorted(((difflib.SequenceMatcher(None, r.key, k).ratio(), k) for k in pool), reverse=True)[:2]
            if scored and scored[0][0] >= FUZZY_MIN and (len(scored) == 1 or scored[0][0] - scored[1][0] >= FUZZY_MARGIN):
                ciks, sec_name = by_key.loc[scored[0][1], "ciks"], by_key.loc[scored[0][1], "sec_name"]
                score = round(scored[0][0], 3)
                if len(ciks) == 1:
                    method, cik = "fuzzy", ciks[0]
                else:
                    hits = [c for c in ciks if c in listed]
                    note = f"{len(ciks)} CIKs share the matched name"
                    if len(hits) == 1:
                        method, cik = "fuzzy", hits[0]
        out.append({"best_rank": r.best_rank, "ISSUER": r.ISSUER, "NAME": r.NAME, "ticker": r.ticker, "method": method,
                    "sec_name": sec_name, "cik": cik, "score": score, "note": note})
    out = pd.DataFrame(out)

    # Plausibility check: the proposed company's own SIC description
    top = out[out["cik"].notna() & (out["best_rank"] <= TOP_N)]
    desc = {}
    for c in top["cik"].astype(int).unique():
        try:
            d = sec_json(f"https://data.sec.gov/submissions/CIK{c:010d}.json", RAW / "sec" / "submissions" / f"{c}.json")
            desc[c] = (d.get("name"), d.get("sic"), d.get("sicDescription"))
        except Exception as exc:
            desc[c] = (None, None, f"lookup failed: {type(exc).__name__}")
    out["sec_entity"] = out["cik"].map(lambda c: desc.get(int(c), (None,) * 3)[0] if pd.notna(c) else None)
    out["sic_desc"] = out["cik"].map(lambda c: desc.get(int(c), (None,) * 3)[2] if pd.notna(c) else None)
    out.to_csv(RESULTS / "name_candidates.csv", index=False)

    print("method counts, all unmapped:", out["method"].value_counts().to_dict())
    t = out[out["best_rank"] <= TOP_N]
    print(f"top {TOP_N} by rank:", t["method"].value_counts().to_dict())
    pd.set_option("display.width", 250, "display.max_colwidth", 34)
    cols = ["best_rank", "NAME", "sec_name", "cik", "score", "sic_desc"]
    for m in ("listed", "fuzzy"):
        print(f"\n--- {m} proposals in the top {TOP_N}")
        print(t[t["method"] == m][cols].to_string(index=False))
    print(f"\n--- still no proposal in the top {TOP_N}")
    print(t[t["method"] == "review"][["best_rank", "NAME", "note"]].to_string(index=False))
    print(f"\n--- unique matches in the top {TOP_N}: plausibility sample (NAME -> SEC entity, SIC)")
    print(t[t["method"] == "unique"][["best_rank", "NAME", "sec_entity", "sic_desc"]].head(60).to_string(index=False))


if __name__ == "__main__":
    main()
