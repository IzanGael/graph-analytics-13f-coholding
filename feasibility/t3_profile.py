"""Topic 3: profile the SEC Form 13F flat tables for one quarterly release.

Usage: python -I t3_profile.py <extracted_dir>
"""
import sys
from pathlib import Path

import pandas as pd

d = Path(sys.argv[1])
pd.set_option("display.width", 200, "display.max_columns", 40, "display.max_colwidth", 40)

for name in ("SUBMISSION", "COVERPAGE", "SUMMARYPAGE", "OTHERMANAGER", "OTHERMANAGER2", "SIGNATURE"):
    t = pd.read_csv(d / f"{name}.tsv", sep="\t", dtype=str, nrows=200000)
    print(f"\n== {name}: {len(t)} rows ; cols={list(t.columns)}")

sub = pd.read_csv(d / "SUBMISSION.tsv", sep="\t", dtype=str)
cov = pd.read_csv(d / "COVERPAGE.tsv", sep="\t", dtype=str)
print("\nsubmission types:\n", sub["SUBMISSIONTYPE"].value_counts())
print("\nperiods of report (top):\n", sub["PERIODOFREPORT"].value_counts().head(8))
print("\nfiling dates:", sub["FILING_DATE"].min(), "...", sub["FILING_DATE"].value_counts().head(3).to_dict())
print("\nreport types:\n", cov["REPORTTYPE"].value_counts())

info = pd.read_csv(d / "INFOTABLE.tsv", sep="\t", dtype=str)
print(f"\n== INFOTABLE: {len(info)} rows ; cols={list(info.columns)}")
print(info.head(3).T)
print("\nunique accessions:", info["ACCESSION_NUMBER"].nunique(), " unique CUSIP:", info["CUSIP"].nunique(),
      " unique NAMEOFISSUER:", info["NAMEOFISSUER"].nunique())
print("\nTITLEOFCLASS top:\n", info["TITLEOFCLASS"].str.upper().value_counts().head(12))
print("\nPUTCALL:\n", info["PUTCALL"].value_counts(dropna=False))
print("\nSSHPRNAMTTYPE:\n", info["SSHPRNAMTTYPE"].value_counts(dropna=False))
if "FIGI" in info.columns:
    print("\nFIGI non-null:", info["FIGI"].notna().mean())
print("\nCUSIP length:\n", info["CUSIP"].str.len().value_counts().head(5))
names_per_cusip = info.groupby("CUSIP")["NAMEOFISSUER"].nunique()
print("\nspellings per CUSIP: mean", names_per_cusip.mean(), "p95", names_per_cusip.quantile(.95), "max", names_per_cusip.max())
print("\nvalue column sample / units check (top 5 by value):")
info["V"] = pd.to_numeric(info["VALUE"], errors="coerce")
print(info.nlargest(5, "V")[["NAMEOFISSUER", "CUSIP", "V", "SSHPRNAMT"]])
print("\nSEC field-name check for sector info:", [c for c in info.columns if "SIC" in c or "SECT" in c or "INDUS" in c])
print("\ncover columns:", list(cov.columns))
