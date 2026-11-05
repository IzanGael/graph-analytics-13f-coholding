"""Read-only comparison of the raw 13F releases: layout, columns, formats, units. Changes no data.

Output: results/quarter_inspection.csv, results/unit_check.csv, results/reference_prices.csv
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # shared modules live in src/

import zipfile

import numpy as np
import pandas as pd

from config import INTERIM, QUARTERS, RAW, RESULTS

REFERENCE = {"037833100": "Apple", "594918104": "Microsoft", "46625H100": "JPMorgan", "191216100": "Coca-Cola"}
columns_seen, rows, unit_rows, prices = {}, [], [], {}

for quarter, (period, release) in QUARTERS.items():
    with zipfile.ZipFile(RAW / "13f" / f"{release}_form13f.zip") as z:
        member = {n.rsplit("/", 1)[-1]: n for n in z.namelist() if not n.endswith("/")}
        for table in sorted(member):
            if table.endswith(".tsv"):
                with z.open(member[table]) as fh:
                    columns_seen.setdefault(table, {})[quarter] = tuple(fh.readline().decode("utf-8", "replace").strip().split("\t"))
        with z.open(member["SUBMISSION.tsv"]) as fh:
            sub = pd.read_csv(fh, sep="\t", dtype=str)
        with z.open(member["INFOTABLE.tsv"]) as fh:
            info = pd.read_csv(fh, sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "CUSIP", "VALUE", "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL"])

    filed = pd.to_datetime(sub["FILING_DATE"], format="%d-%b-%Y", errors="coerce")
    main = sub["PERIODOFREPORT"] == period
    cusip = info["CUSIP"].fillna("")
    rows.append({
        "quarter": quarter, "release": release, "subfolder": any("/" in n for n in member.values()),
        "tables": len([t for t in member if t.endswith(".tsv")]),
        "submissions": len(sub), "main_period_share": round(main.mean(), 3),
        "period_format_ok": bool(sub["PERIODOFREPORT"].str.fullmatch(r"\d{2}-[A-Z]{3}-\d{4}").all()),
        "bad_filing_dates": int(filed.isna().sum()), "filed_from": filed.min().date(), "filed_to": filed.max().date(),
        "peak_filing_day": filed.mode().iloc[0].date(),
        "hr_main": int((main & (sub["SUBMISSIONTYPE"] == "13F-HR")).sum()),
        "hr_amend_main": int((main & (sub["SUBMISSIONTYPE"] == "13F-HR/A")).sum()),
        "repeat_filers": int(sub[main & (sub["SUBMISSIONTYPE"] == "13F-HR")]["CIK"].duplicated().sum()),
        "info_rows": len(info), "cusip_not_9": int((cusip.str.len() != 9).sum()),
        "cusip_lowercase": int(cusip.str.contains("[a-z]").sum()), "cusip_all_zero": int((cusip == "000000000").sum()),
        "putcall_values": sorted(info["PUTCALL"].dropna().str.strip().str.upper().unique().tolist()),
        "putcall_raw_values": info["PUTCALL"].nunique(),
        "type_values": sorted(info["SSHPRNAMTTYPE"].dropna().unique().tolist()),
        "value_zero": int((pd.to_numeric(info["VALUE"], errors="coerce") == 0).sum()),
    })

    # Position-level price against the quarter's median price for that security
    h = pd.read_parquet(INTERIM / f"holdings_{quarter}.parquet", columns=["CIK", "CUSIP", "VALUE", "SHARES"])
    h["P"] = h["VALUE"] / h["SHARES"]
    h["holders"] = h.groupby("CUSIP")["CIK"].transform("nunique")
    h = h[h["holders"] >= 20]
    h["ratio"] = h["P"] / h.groupby("CUSIP")["P"].transform("median")
    near_1000 = h["ratio"].between(300, 3000)
    near_milli = h["ratio"].between(1 / 3000, 1 / 300)
    by_filer = h.groupby("CIK")["ratio"].median()
    unit_rows.append({
        "quarter": quarter, "rows_checked": len(h),
        "pct_rows_within_10pct": round(h["ratio"].between(0.9, 1.1).mean() * 100, 2),
        "pct_rows_near_1000x": round(near_1000.mean() * 100, 3), "pct_rows_near_1_1000": round(near_milli.mean() * 100, 3),
        "filers": len(by_filer), "filers_near_1000x": int(by_filer.between(300, 3000).sum()),
        "filers_near_1_1000": int(by_filer.between(1 / 3000, 1 / 300).sum()),
        "value_share_near_1000x": round(h.loc[near_1000, "VALUE"].sum() / h["VALUE"].sum() * 100, 2),
    })
    med = h[h["CUSIP"].isin(REFERENCE)].groupby("CUSIP")["P"].median()
    prices[quarter] = {REFERENCE[c]: round(p, 2) for c, p in med.items()}
    print(quarter, "done", flush=True)

pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_colwidth", 60)
report = pd.DataFrame(rows)
report.to_csv(RESULTS / "quarter_inspection.csv", index=False)
units = pd.DataFrame(unit_rows)
units.to_csv(RESULTS / "unit_check.csv", index=False)
price_table = pd.DataFrame(prices).T
price_table.to_csv(RESULTS / "reference_prices.csv")
print(report.drop(columns=["putcall_values", "type_values"]).to_string(index=False))
print("putcall variants:", report["putcall_values"].astype(str).unique().tolist())
print("type variants:", report["type_values"].astype(str).unique().tolist())
print(units.to_string(index=False))
print(price_table.to_string())
for table, seen in columns_seen.items():
    variants = {}
    for q, cols in seen.items():
        variants.setdefault(cols, []).append(q)
    print(table, "column layouts:", len(variants))
    if len(variants) > 1:
        base = max(variants, key=lambda c: len(variants[c]))
        for cols, qs in variants.items():
            if cols != base:
                print("   ", qs, "added", sorted(set(cols) - set(base)), "missing", sorted(set(base) - set(cols)))
print(np.round(pd.read_csv(RESULTS / "quarter_log.csv", index_col=0), 0).to_string())
