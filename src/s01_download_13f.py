"""Step 1: download the quarterly 13F releases and keep long share positions in compact files.

Filters: for each manager and report period, the filing chain is the original 13F-HR, replaced by its latest
RESTATEMENT amendment (13F-HR/A) when one exists; NEW HOLDINGS amendments filed after that base add their positions
(a position already in the base is not duplicated). No options; shares only; positive value.
Output: data/interim/holdings_<quarter>.parquet and a per-quarter log in results/.
"""
import http.client
import shutil
import time
import urllib.error
import urllib.request
import zipfile

import pandas as pd

from config import INTERIM, QUARTERS, RAW, RESULTS, sec_headers

MAX_ATTEMPTS = 12
DOLLAR_REPORTING_START = pd.Timestamp("2023-01-03")
MIN_HOLDERS_FOR_PRICE = 5
UNIT_BAND = (300, 3000)   # a ratio this far from 1 reads as a 1,000x unit error

BASES = ("https://www.sec.gov/files/structureddata/data/form-13f-data-sets/",
         "https://www.sec.gov/files/datastandardsinnovation/data/form-13f-data-sets/")


def fetch(url, target):
    """Stream to a .part file, resuming after dropped connections; rename only when complete."""
    part = target.with_suffix(".part")
    for attempt in range(MAX_ATTEMPTS):
        done = part.stat().st_size if part.exists() else 0
        headers = {**sec_headers(), **({"Range": f"bytes={done}-"} if done else {})}
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as resp:
                # A server that ignores Range answers 200 and restarts from the first byte
                with open(part, "ab" if resp.status == 206 else "wb") as fh:
                    shutil.copyfileobj(resp, fh, 1024 * 1024)
                    if resp.length:
                        raise http.client.IncompleteRead(b"")
            if not zipfile.is_zipfile(part):
                raise ValueError(f"not a valid zip: {part.name}")
            part.replace(target)
            return
        except (http.client.HTTPException, ConnectionError, TimeoutError, urllib.error.URLError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 404:
                raise
            print(f"  retry {attempt + 1}: {type(exc).__name__}", flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}")


def download(release):
    target = RAW / "13f" / f"{release}_form13f.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target
    for base in BASES:
        try:
            fetch(f"{base}{release}_form13f.zip", target)
            time.sleep(1)
            return target
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
    raise FileNotFoundError(release)


def median_price(info):
    """Quarter's median value/shares per security, row-aligned; NaN if too few holders to trust."""
    price = (info["VALUE"] / info["SHARES"]).groupby(info["CUSIP"]).transform("median")
    holders = info.groupby("CUSIP")["CIK"].transform("nunique")
    return price.where(holders >= MIN_HOLDERS_FOR_PRICE)


def fix_units(info):
    """Keep reported value; rescale by 1,000 only when that brings it close to shares x median price."""
    ratio = info["VALUE"] / (info["SHARES"] * median_price(info))
    too_big = ratio.between(*UNIT_BAND)
    too_small = ratio.between(1 / UNIT_BAND[1], 1 / UNIT_BAND[0])
    value = info["VALUE"].where(~too_big, info["VALUE"] / 1000).where(~too_small, info["VALUE"] * 1000)
    return value, int(too_big.sum()), int(too_small.sum())


def filing_chain(filings):
    """Which filings make up each manager's report for the period.

    Base: the latest RESTATEMENT amendment if there is one (it replaces the whole original report), otherwise
    the latest original 13F-HR. Adds: NEW HOLDINGS amendments filed on or after the base (they add positions).
    A position already in the base is not taken again from an add; among adds the latest filing wins.
    Returns the chain (one row per filing used, with a role column) and counts for the log.
    """
    key = ["_filed", "ACCESSION_NUMBER"]
    original = filings[filings["SUBMISSIONTYPE"] == "13F-HR"].sort_values(key).drop_duplicates("CIK", keep="last")
    restated = (filings[(filings["SUBMISSIONTYPE"] == "13F-HR/A") & (filings["AMENDMENTTYPE"] == "RESTATEMENT")]
                .sort_values(key).drop_duplicates("CIK", keep="last"))
    base = pd.concat([original[~original["CIK"].isin(restated["CIK"])], restated]).assign(role="base")
    new = filings[filings["AMENDMENTTYPE"] == "NEW HOLDINGS"].merge(
        base[["CIK", "_filed"]].rename(columns={"_filed": "_base_filed"}), on="CIK")
    new = new[new["_filed"] >= new["_base_filed"]].drop(columns="_base_filed").assign(role="add")
    chain = pd.concat([base, new], ignore_index=True)
    log = {"managers_restated": int(restated["CIK"].nunique()), "new_holdings_filings_used": int(new["ACCESSION_NUMBER"].nunique())}
    return chain, log


def extract(path, period):
    with zipfile.ZipFile(path) as z:
        # Some releases keep the tables at the archive root, others inside a dated subfolder
        member = {name.rsplit("/", 1)[-1]: name for name in z.namelist()}
        with z.open(member["SUBMISSION.tsv"]) as fh:
            sub = pd.read_csv(fh, sep="\t", dtype=str)
        with z.open(member["COVERPAGE.tsv"]) as fh:
            cover = pd.read_csv(fh, sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "FILINGMANAGER_NAME", "AMENDMENTTYPE"])
        with z.open(member["INFOTABLE.tsv"]) as fh:
            info = pd.read_csv(fh, sep="\t", dtype=str,
                               usecols=["ACCESSION_NUMBER", "NAMEOFISSUER", "TITLEOFCLASS", "CUSIP", "VALUE",
                                        "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL"])
    filings = sub[(sub["PERIODOFREPORT"] == period) & sub["SUBMISSIONTYPE"].isin(["13F-HR", "13F-HR/A"])]
    filings = filings.merge(cover, on="ACCESSION_NUMBER", how="left")
    filings = filings.assign(_filed=pd.to_datetime(filings["FILING_DATE"], format="%d-%b-%Y"))
    chain, chain_log = filing_chain(filings)
    info = info.merge(chain[["ACCESSION_NUMBER", "CIK", "FILING_DATE", "_filed", "role"]], on="ACCESSION_NUMBER")
    base_rows = info[info["role"] == "base"]
    add_rows = info[info["role"] == "add"]
    # Positions added by NEW HOLDINGS: skip any already in the base; across adds keep the latest filing
    add_rows = add_rows[~add_rows.set_index(["CIK", "CUSIP"]).index.isin(base_rows.set_index(["CIK", "CUSIP"]).index)]
    add_rows = add_rows[add_rows["_filed"] == add_rows.groupby(["CIK", "CUSIP"])["_filed"].transform("max")]
    info = pd.concat([base_rows, add_rows], ignore_index=True)
    log = {"filings": int(chain["ACCESSION_NUMBER"].nunique()), "rows_all": len(info), **chain_log, "rows_added_new_holdings": len(add_rows)}
    info = info[info["PUTCALL"].isna() & (info["SSHPRNAMTTYPE"] == "SH")].copy()
    info["VALUE"] = pd.to_numeric(info["VALUE"], errors="coerce")
    # SEC readme: value is in dollars from 3 Jan 2023 and in thousands of dollars before that
    filed = pd.to_datetime(info["FILING_DATE"], format="%d-%b-%Y")
    log["rows_in_thousands"] = int((filed < DOLLAR_REPORTING_START).sum())
    info.loc[filed < DOLLAR_REPORTING_START, "VALUE"] *= 1000
    info["SHARES"] = pd.to_numeric(info["SSHPRNAMT"], errors="coerce")
    info = info[(info["VALUE"] > 0) & (info["SHARES"] > 0)]
    info["CUSIP"] = info["CUSIP"].str.upper().str.strip()
    info = info[info["CUSIP"].str.len() == 9]
    placeholder = info["CUSIP"].str.fullmatch(r"(.)\1{8}")   # 000000000, 999999999, AAAAAAAAA...
    log["rows_placeholder_cusip"] = int(placeholder.sum())
    info = info[~placeholder].copy()
    log["value_before_unit_fix_tn"] = info["VALUE"].sum() / 1e12
    info["VALUE"], log["rows_divided_1000"], log["rows_multiplied_1000"] = fix_units(info)
    log["value_after_unit_fix_tn"] = info["VALUE"].sum() / 1e12
    log["shares_x_price_tn"] = (info["SHARES"] * median_price(info)).sum() / 1e12
    log["rows_long_shares"] = len(info)
    log["managers"] = info["CIK"].nunique()
    log["cusips"] = info["CUSIP"].nunique()
    managers = chain[["CIK", "FILINGMANAGER_NAME"]].drop_duplicates("CIK", keep="last")
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
