"""Step 1: download the quarterly 13F releases and keep long share positions in compact files.

Filters: original 13F-HR filings for the release's main report period; no options; shares only;
positive value. Amendments and late filings are excluded so that each quarter is one snapshot.
Output: data/interim/holdings_<quarter>.parquet and a per-quarter log in results/.
"""
import time
import urllib.request
import zipfile

import pandas as pd

from config import INTERIM, QUARTERS, RAW, RESULTS, sec_headers

BASES = ("https://www.sec.gov/files/structureddata/data/form-13f-data-sets/",
         "https://www.sec.gov/files/datastandardsinnovation/data/form-13f-data-sets/")


def download(release):
    target = RAW / "13f" / f"{release}_form13f.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target
    for base in BASES:
        req = urllib.request.Request(f"{base}{release}_form13f.zip", headers=sec_headers())
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                target.write_bytes(resp.read())
            time.sleep(1)
            return target
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
    raise FileNotFoundError(release)


def extract(path, period):
    with zipfile.ZipFile(path) as z:
        with z.open("SUBMISSION.tsv") as fh:
            sub = pd.read_csv(fh, sep="\t", dtype=str)
        with z.open("COVERPAGE.tsv") as fh:
            cover = pd.read_csv(fh, sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "FILINGMANAGER_NAME"])
        with z.open("INFOTABLE.tsv") as fh:
            info = pd.read_csv(fh, sep="\t", dtype=str,
                               usecols=["ACCESSION_NUMBER", "NAMEOFISSUER", "TITLEOFCLASS", "CUSIP", "VALUE",
                                        "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL"])
    keep = sub[(sub["PERIODOFREPORT"] == period) & (sub["SUBMISSIONTYPE"] == "13F-HR")]
    # A manager filing twice for the period keeps its largest accession number (the latest one)
    keep = keep.sort_values("ACCESSION_NUMBER").drop_duplicates("CIK", keep="last")
    info = info.merge(keep[["ACCESSION_NUMBER", "CIK"]], on="ACCESSION_NUMBER")
    log = {"filings": len(keep), "rows_all": len(info)}
    info = info[info["PUTCALL"].isna() & (info["SSHPRNAMTTYPE"] == "SH")].copy()
    info["VALUE"] = pd.to_numeric(info["VALUE"], errors="coerce")
    info["SHARES"] = pd.to_numeric(info["SSHPRNAMT"], errors="coerce")
    info = info[(info["VALUE"] > 0) & (info["SHARES"] > 0)]
    info["CUSIP"] = info["CUSIP"].str.upper().str.strip()
    info = info[info["CUSIP"].str.len() == 9]
    log["rows_long_shares"] = len(info)
    log["managers"] = info["CIK"].nunique()
    log["cusips"] = info["CUSIP"].nunique()
    managers = keep.merge(cover, on="ACCESSION_NUMBER")[["CIK", "FILINGMANAGER_NAME"]]
    return info[["CIK", "CUSIP", "NAMEOFISSUER", "TITLEOFCLASS", "VALUE", "SHARES"]], managers, log


def main():
    INTERIM.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    logs = {}
    for quarter, (period, release) in QUARTERS.items():
        path = download(release)
        holdings, managers, log = extract(path, period)
        holdings.to_parquet(INTERIM / f"holdings_{quarter}.parquet", index=False)
        managers.to_parquet(INTERIM / f"managers_{quarter}.parquet", index=False)
        logs[quarter] = log
        print(quarter, log, flush=True)
    pd.DataFrame(logs).T.to_csv(RESULTS / "quarter_log.csv")


if __name__ == "__main__":
    main()
