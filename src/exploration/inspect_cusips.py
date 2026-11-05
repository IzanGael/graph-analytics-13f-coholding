"""Read-only: how important are all-zero CUSIPs, and are lowercase CUSIPs the same securities as uppercase?

Covers original 13F-HR filings for each quarter, long share rows. Reported values use the date-based
unit rule, so value shares here are approximate. Changes no data.
Output: results/zero_cusip.csv, results/zero_cusip_names.csv, results/lowercase_cusip.csv
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # shared modules live in src/

import re
import zipfile

import numpy as np
import pandas as pd

from config import QUARTERS, RAW, RESULTS

SWITCH = pd.Timestamp("2023-01-03")


def norm(name):
    name = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper())
    name = re.sub(r"\b(INC|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|NEW|DEL|THE|COM|CL A|CL B)\b", " ", name)
    return " ".join(name.split())


zero_rows, lower_rows, zero_names, odd = [], [], [], {}
for quarter, (period, release) in QUARTERS.items():
    with zipfile.ZipFile(RAW / "13f" / f"{release}_form13f.zip") as z:
        member = {n.rsplit("/", 1)[-1]: n for n in z.namelist() if not n.endswith("/")}
        with z.open(member["SUBMISSION.tsv"]) as fh:
            sub = pd.read_csv(fh, sep="\t", dtype=str)
        with z.open(member["INFOTABLE.tsv"]) as fh:
            info = pd.read_csv(fh, sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "NAMEOFISSUER", "CUSIP", "VALUE", "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL"])
    keep = sub[(sub["PERIODOFREPORT"] == period) & (sub["SUBMISSIONTYPE"] == "13F-HR")].sort_values("ACCESSION_NUMBER").drop_duplicates("CIK", keep="last")
    d = info.merge(keep[["ACCESSION_NUMBER", "CIK", "FILING_DATE"]], on="ACCESSION_NUMBER")
    d = d[d["PUTCALL"].isna() & (d["SSHPRNAMTTYPE"] == "SH")].copy()
    d["VALUE"] = pd.to_numeric(d["VALUE"], errors="coerce").fillna(0)
    d["SHARES"] = pd.to_numeric(d["SSHPRNAMT"], errors="coerce").fillna(0)
    d.loc[pd.to_datetime(d["FILING_DATE"], format="%d-%b-%Y") < SWITCH, "VALUE"] *= 1000
    d["CUSIP"] = d["CUSIP"].fillna("")
    d["UP"] = d["CUSIP"].str.upper()
    d["NORM"] = d["NAMEOFISSUER"].map(norm)
    total_value = d["VALUE"].sum()

    # Other placeholder-looking codes
    placeholder = d["UP"].str.fullmatch(r"(.)\1{8}") | ~d["UP"].str.fullmatch(r"[A-Z0-9]{9}")
    for code, n in d.loc[placeholder, "UP"].value_counts().items():
        odd[code] = odd.get(code, 0) + int(n)

    # Problem 2: all-zero codes, and whether the issuer name identifies a real CUSIP this quarter
    zero = d[d["UP"] == "000000000"]
    valid = d[~placeholder]
    by_name = valid.groupby(["NORM", "UP"]).size().rename("n").reset_index().sort_values("n", ascending=False)
    name_to_cusip = by_name.drop_duplicates("NORM").set_index("NORM")["UP"]
    recoverable = zero["NORM"].isin(name_to_cusip.index)
    by_filer = zero.groupby("CIK")["VALUE"].sum().sort_values(ascending=False)
    zero_rows.append({
        "quarter": quarter, "rows": len(zero), "filers": zero["CIK"].nunique(), "names": zero["NORM"].nunique(),
        "pct_rows": round(len(zero) / len(d) * 100, 4), "value_bn": round(zero["VALUE"].sum() / 1e9, 2),
        "pct_value": round(zero["VALUE"].sum() / total_value * 100, 4),
        "top_filer_pct_of_zero_value": round(by_filer.iloc[0] / max(by_filer.sum(), 1) * 100, 1) if len(by_filer) else 0,
        "pct_rows_name_matches_real_cusip": round(recoverable.mean() * 100, 1) if len(zero) else 0,
        "pct_value_name_matches_real_cusip": round(zero.loc[recoverable, "VALUE"].sum() / max(zero["VALUE"].sum(), 1) * 100, 1) if len(zero) else 0,
    })
    top = zero.groupby("NAMEOFISSUER").agg(value_bn=("VALUE", lambda s: s.sum() / 1e9), rows=("VALUE", "size"), filers=("CIK", "nunique")).nlargest(5, "value_bn").reset_index()
    top.insert(0, "quarter", quarter)
    zero_names.append(top)

    # Problem 3: lowercase codes against their uppercase twin
    is_lower = d["CUSIP"].str.contains("[a-z]")
    low = d[is_lower]
    up = d[~is_lower & ~placeholder]
    twin_name = up.groupby("UP")["NORM"].agg(lambda s: s.value_counts().index[0])
    up_p = up[up["SHARES"] > 0]
    twin_price = (up_p["VALUE"] / up_p["SHARES"]).groupby(up_p["UP"]).median()
    has_twin = low["UP"].isin(twin_name.index)
    same_name = low["NORM"] == low["UP"].map(twin_name)
    low_p = low[low["SHARES"] > 0]
    ratio = (low_p["VALUE"] / low_p["SHARES"]) / low_p["UP"].map(twin_price)
    both = set(zip(low["CIK"], low["UP"])) & set(zip(up["CIK"], up["UP"]))
    unmatched_names = low[has_twin & ~same_name]
    lower_rows.append({
        "quarter": quarter, "rows": len(low), "distinct_codes": low["CUSIP"].nunique(), "filers": low["CIK"].nunique(),
        "top_filer_pct_rows": round(low["CIK"].value_counts().iloc[0] / max(len(low), 1) * 100, 1) if len(low) else 0,
        "pct_rows": round(len(low) / len(d) * 100, 3), "pct_value": round(low["VALUE"].sum() / total_value * 100, 3),
        "pct_rows_with_uppercase_twin": round(has_twin.mean() * 100, 1),
        "pct_twin_rows_same_name": round(same_name[has_twin].mean() * 100, 1),
        "pct_twin_rows_price_within_10pct": round(ratio.dropna().between(0.9, 1.1).mean() * 100, 1),
        "pairs_same_filer_both_cases": len(both), "name_mismatch_sample": unmatched_names[["CUSIP", "NAMEOFISSUER"]].drop_duplicates().head(3).values.tolist(),
    })
    print(quarter, "done", flush=True)

pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_colwidth", 70)
z = pd.DataFrame(zero_rows)
l = pd.DataFrame(lower_rows)
n = pd.concat(zero_names)
z.to_csv(RESULTS / "zero_cusip.csv", index=False)
l.to_csv(RESULTS / "lowercase_cusip.csv", index=False)
n.to_csv(RESULTS / "zero_cusip_names.csv", index=False)
print(z.to_string(index=False))
print(n.nlargest(25, "value_bn").round(2).to_string(index=False))
print(l.drop(columns="name_mismatch_sample").to_string(index=False))
print("name mismatch samples:", [x for s in l["name_mismatch_sample"] for x in s][:20])
print("placeholder-looking codes, rows across all quarters:", sorted(odd.items(), key=lambda kv: -kv[1])[:20], "distinct:", len(odd))
