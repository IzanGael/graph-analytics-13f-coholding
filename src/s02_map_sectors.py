"""Step 2: classify each candidate issuer: security type (OpenFIGI), SIC (SEC), Fama-French sector.

Route: CUSIP -> ticker and security type (OpenFIGI) -> CIK (SEC company_tickers.json, then exact
normalised-name match) -> SIC (SEC submissions API) -> Fama-French 12 and 48 groups (Ken French).
Responses are cached in data/interim so that re-runs need no network.
Output: data/interim/issuer_map.parquet and results/mapping_coverage.csv
"""
import io
import json
import re
import time
import urllib.error
import urllib.request
import zipfile

import pandas as pd

from config import INTERIM, N_ISSUERS, QUARTERS, RAW, RESULTS, sec_headers

CANDIDATES_PER_QUARTER = 1800
FIGI_URL = "https://api.openfigi.com/v3/mapping"
FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Siccodes{}.zip"
FUND_TYPES = {"ETP", "Closed-End Fund", "Open-End Fund", "Mutual Fund", "Unit", "Preference", "Right", "Warrant"}
FUND_SIC = {6722, 6726, 6221}   # management investment, unit trusts, commodity brokers/pools
FUND_NAME = re.compile(r"\b(ETF|ETN|ISHARES|SPDR|PROSHARES|INVESCO QQQ|SELECT SECTOR|WISDOMTREE|VANGUARD|"
                       r"DIREXION|GRAYSCALE|JANUS DETROIT|TRUST UNITS|FDS|FUNDS?)\b")


def candidates():
    frames = []
    for quarter in QUARTERS:
        h = pd.read_parquet(INTERIM / f"holdings_{quarter}.parquet", columns=["CUSIP", "NAMEOFISSUER", "VALUE", "VALUE_RELIABLE"])
        h["VALUE"] = h["VALUE"].where(h["VALUE_RELIABLE"], 0)
        h["ISSUER"] = h["CUSIP"].str[:6]
        by_cusip = h.groupby(["ISSUER", "CUSIP"], as_index=False)["VALUE"].sum()
        name = h.groupby("ISSUER")["NAMEOFISSUER"].agg(lambda s: s.value_counts().index[0] if s.notna().any() else "")
        top = by_cusip.groupby("ISSUER")["VALUE"].sum().nlargest(CANDIDATES_PER_QUARTER)
        primary = by_cusip.sort_values("VALUE").drop_duplicates("ISSUER", keep="last").set_index("ISSUER")["CUSIP"]
        frames.append(pd.DataFrame({"ISSUER": top.index, "CUSIP": primary.reindex(top.index).values,
                                    "NAME": name.reindex(top.index).values, "quarter": quarter,
                                    "rank": range(1, len(top) + 1)}))
    return pd.concat(frames)


def figi_lookup(cusips):
    cache_path = INTERIM / "figi_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    for exch in ("US", None):
        key = lambda c: f"{c}|{exch}"
        todo = [c for c in cusips if key(c) not in cache and not (exch is None and cache.get(f"{c}|US"))]
        print(f"OpenFIGI exch={exch}: {len(todo)} to query", flush=True)
        for i in range(0, len(todo), 10):
            batch = todo[i:i + 10]
            jobs = [{"idType": "ID_CUSIP", "idValue": c, **({"exchCode": exch} if exch else {})} for c in batch]
            req = urllib.request.Request(FIGI_URL, data=json.dumps(jobs).encode(),
                                         headers={"Content-Type": "application/json"})
            for attempt in range(6):
                try:
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        out = json.load(resp)
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code != 429 or attempt == 5:
                        raise
                    time.sleep(30)
            for c, res in zip(batch, out):
                cache[key(c)] = (res.get("data") or [None])[0]
            time.sleep(2.5)   # unauthenticated limit: 25 requests per minute
            if i % 100 == 0:
                cache_path.write_text(json.dumps(cache))
    cache_path.write_text(json.dumps(cache))
    return {c: cache.get(f"{c}|US") or cache.get(f"{c}|None") for c in cusips}


def norm_name(name):
    name = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper())
    name = re.sub(r"\b(INC|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|NV|N V|SA|S A|AG|SE|LLC|LP|L P|HLDGS?|HOLDINGS?|"
                  r"GROUP|GRP|THE|NEW|DEL|CL A|CL B|COM|ADR|SPONSORED|TR|TRUST)\b", " ", name)
    return " ".join(name.split())


def sec_json(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        req = urllib.request.Request(url, headers=sec_headers())
        with urllib.request.urlopen(req, timeout=60) as resp:
            path.write_bytes(resp.read())
        time.sleep(0.15)   # SEC fair-access limit: 10 requests per second
    return json.loads(path.read_text(encoding="utf-8"))


def french_groups(n):
    path = RAW / "french" / f"Siccodes{n}.zip"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urllib.request.urlopen(FRENCH.format(n), timeout=60) as resp:
            path.write_bytes(resp.read())
    with zipfile.ZipFile(path) as z:
        text = io.TextIOWrapper(z.open(z.namelist()[0]), encoding="latin-1").read()
    ranges, label = [], None
    for line in text.splitlines():
        head = re.match(r"\s*\d+\s+(\S+)\s+", line)
        rng = re.match(r"\s*(\d{4})-(\d{4})", line)
        if rng and label:
            ranges.append((int(rng.group(1)), int(rng.group(2)), label))
        elif head:
            label = head.group(1)
    return ranges


def lookup(ranges, sic, other):
    for lo, hi, label in ranges:
        if lo <= sic <= hi:
            return label
    return other


def main():
    cand = candidates()
    issuers = cand.sort_values("rank").drop_duplicates("ISSUER", keep="first")
    print("candidate issuers:", len(issuers), flush=True)
    figi = figi_lookup(issuers["CUSIP"].tolist())
    issuers["ticker"] = issuers["CUSIP"].map(lambda c: (figi.get(c) or {}).get("ticker"))
    issuers["figi_type"] = issuers["CUSIP"].map(lambda c: (figi.get(c) or {}).get("securityType"))

    tickers = sec_json("https://www.sec.gov/files/company_tickers.json", RAW / "sec" / "company_tickers.json")
    ticker_cik = {v["ticker"].upper(): int(v["cik_str"]) for v in tickers.values()}
    name_cik = {}
    for v in tickers.values():
        name_cik.setdefault(norm_name(v["title"]), int(v["cik_str"]))

    def resolve(row):
        t = str(row["ticker"] or "").upper().replace("/", "-").split(" ")[0]
        if t in ticker_cik:
            return ticker_cik[t], "ticker"
        base = t.split("-")[0]
        if base in ticker_cik:
            return ticker_cik[base], "ticker"
        n = norm_name(row["NAME"])
        if n and n in name_cik:
            return name_cik[n], "name"
        return None, None

    resolved = issuers.apply(resolve, axis=1, result_type="expand")
    issuers["cik"], issuers["cik_source"] = resolved[0], resolved[1]

    # Overrides are hand-checked against EDGAR; see data/manual_overrides.csv
    overrides = RAW.parent / "manual_overrides.csv"
    if overrides.exists():
        ov = pd.read_csv(overrides, dtype={"ISSUER": str}).set_index("ISSUER")["cik"]
        hit = issuers["ISSUER"].isin(ov.index)
        issuers.loc[hit, "cik"] = issuers.loc[hit, "ISSUER"].map(ov)
        issuers.loc[hit, "cik_source"] = "manual"

    sic, desc = {}, {}
    for cik in issuers["cik"].dropna().astype(int).unique():
        d = sec_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", RAW / "sec" / "submissions" / f"{cik}.json")
        sic[cik] = int(d["sic"]) if str(d.get("sic") or "").isdigit() else None
        desc[cik] = d.get("sicDescription")
    issuers["sic"] = issuers["cik"].map(sic)
    issuers["sic_desc"] = issuers["cik"].map(desc)
    issuers["sic2"] = issuers["sic"] // 100

    ff12, ff48 = french_groups(12), french_groups(48)
    issuers["ff12"] = issuers["sic"].map(lambda s: lookup(ff12, int(s), "Other") if pd.notna(s) else None)
    issuers["ff48"] = issuers["sic"].map(lambda s: lookup(ff48, int(s), "Other") if pd.notna(s) else None)

    is_fund = (issuers["figi_type"].isin(FUND_TYPES) | issuers["sic"].isin(FUND_SIC)
               | (issuers["figi_type"].isna() & issuers["NAME"].str.upper().str.contains(FUND_NAME)))
    issuers["is_fund"] = is_fund
    issuers["operating"] = ~is_fund & issuers["sic"].notna()
    issuers.drop(columns=["quarter", "rank"]).to_parquet(INTERIM / "issuer_map.parquet", index=False)

    rows = []
    for quarter, g in cand.groupby("quarter"):
        m = g[["ISSUER", "rank"]].merge(issuers[["ISSUER", "is_fund", "operating", "NAME"]], on="ISSUER")
        non_fund = m[~m["is_fund"]].sort_values("rank").head(N_ISSUERS)
        rows.append({"quarter": quarter, "funds_in_top1800": int(m["is_fund"].sum()),
                     "coverage_top1000_non_funds": round(non_fund["operating"].mean(), 4)})
    print(pd.DataFrame(rows).to_string(index=False))
    pd.DataFrame(rows).to_csv(RESULTS / "mapping_coverage.csv", index=False)
    print("CIK source:", issuers["cik_source"].value_counts(dropna=False).to_dict())
    print("FIGI types:", issuers["figi_type"].value_counts(dropna=False).head(12).to_dict())
    miss = issuers[~issuers["is_fund"] & issuers["sic"].isna()].sort_values("rank")
    print("Unmapped non-funds by best rank:\n", miss[["ISSUER", "CUSIP", "NAME", "ticker", "rank"]].head(60).to_string(index=False))
    print("Rows typed as funds (first 25):", issuers[issuers["is_fund"]].sort_values("rank")["NAME"].head(25).tolist())
    print("name-matched sample:", issuers[issuers["cik_source"] == "name"][["NAME", "cik"]].head(15).values.tolist())


if __name__ == "__main__":
    main()
