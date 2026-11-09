"""Export the clean 13F dataset for one quarter as CSVs, for loading into Neo4j.

Exploration/visualization only -- not part of the graded pipeline (s01-s04), does not
touch any file under data/ or results/. Scope: the project's own universe (the N_ISSUERS
largest operating companies, as used everywhere else in the analysis) for one quarter.

Graph model: bipartite. (:Manager)-[:HOLDS]->(:Stock)
Output: neo4j/export/stocks.csv, managers.csv, holds.csv

Run: python neo4j/export_to_neo4j.py [QUARTER]   (default: config.MAIN_QUARTER)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

import gutils as gl  # noqa: E402
from config import INTERIM, MAIN_QUARTER, N_ISSUERS  # noqa: E402

OUT = Path(__file__).resolve().parent / "export"


def main():
    quarter = sys.argv[1] if len(sys.argv) > 1 else MAIN_QUARTER
    OUT.mkdir(parents=True, exist_ok=True)

    imap = gl.issuer_map()
    uni = gl.universe(gl.load_positions(quarter), imap, N_ISSUERS)

    # Raw holdings rows (not yet summed across share classes), restricted to the universe,
    # so the relationship carries both value (same convention as gutils.load_positions:
    # unreliable filers keep the link, lose the value) and raw shares.
    h = pd.read_parquet(INTERIM / f"holdings_{quarter}.parquet",
                        columns=["CIK", "CUSIP", "VALUE", "SHARES", "VALUE_RELIABLE"])
    h["ISSUER"] = h["CUSIP"].str[:6]
    h = h[h["ISSUER"].isin(uni.index)].copy()
    h["VALUE_CLEAN"] = h["VALUE"].where(h["VALUE_RELIABLE"], 0)

    holds = h.groupby(["CIK", "ISSUER"], as_index=False).agg(
        value=("VALUE_CLEAN", "sum"),
        shares=("SHARES", "sum"),
        reliable=("VALUE_RELIABLE", "all"),
    )
    holds.to_csv(OUT / "holds.csv", index=False)

    stocks = uni.reset_index().rename(columns={"NAME": "name", "ticker": "ticker", "sic_desc": "sic_desc",
                                               "ff12": "ff12", "ff48": "ff48", "value": "value"})
    stocks = stocks[["ISSUER", "name", "ticker", "sic", "sic_desc", "ff12", "ff48", "value"]]
    stocks.columns = ["issuer", "name", "ticker", "sic", "sic_desc", "ff12", "ff48", "universe_value"]
    stocks.insert(1, "rank", range(1, len(stocks) + 1))
    stocks.to_csv(OUT / "stocks.csv", index=False)

    names = pd.read_parquet(INTERIM / f"managers_{quarter}.parquet").drop_duplicates("CIK").set_index("CIK")["FILINGMANAGER_NAME"]
    agg = holds.groupby("CIK").agg(positions=("ISSUER", "size"), total_value=("value", "sum"))
    managers = agg.join(names).reset_index().rename(columns={"CIK": "cik", "FILINGMANAGER_NAME": "name"})
    managers = managers[["cik", "name", "positions", "total_value"]]
    managers.to_csv(OUT / "managers.csv", index=False)

    print(f"quarter {quarter}")
    print(f"stocks.csv:   {len(stocks):,} rows")
    print(f"managers.csv: {len(managers):,} rows")
    print(f"holds.csv:    {len(holds):,} rows")
    print(f"written to {OUT}")


if __name__ == "__main__":
    main()
