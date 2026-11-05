"""Step 1b: flag filer-quarters whose total value is over 5x the filer's own median across quarters.

A few filers inflate value and shares together, which the unit check cannot see. Flagged filers keep
their holdings (graph links), but their value does not count in rankings or money shares.
Adds column VALUE_RELIABLE to each holdings file. Output: results/inflated_filers.csv, results/value_totals.csv
"""
import pandas as pd

from config import INTERIM, QUARTERS, RESULTS

INFLATION_LIMIT = 5
MIN_HOLDERS_FOR_PRICE = 5
UNIT_BAND = (300, 3000)
PRICE_DISAGREEMENT = 2     # a row priced above 2x its security's median is suspect
OFF_SHARE_LIMIT = 0.2      # flag a filer when over 20% of its value sits in such rows


def _fix_pass():
    """One pass over all quarters, using a snapshot of the medians taken at the start of the pass.
    Where a security's median price is about 1,000x off its neighbouring quarters, the row check
    in s01 trusted a wrong reference. Rescale its reference, then re-check its rows against it."""
    medians = {}
    for q in QUARTERS:
        h = pd.read_parquet(INTERIM / f"holdings_{q}.parquet", columns=["CIK", "CUSIP", "VALUE", "SHARES"])
        price = (h["VALUE"] / h["SHARES"]).groupby(h["CUSIP"]).median()
        medians[q] = price[h.groupby("CUSIP")["CIK"].nunique() >= MIN_HOLDERS_FOR_PRICE]
    quarters = list(QUARTERS)
    rows = []
    for i, q in enumerate(quarters):
        if not 0 < i < len(quarters) - 1:   # an end quarter has one neighbour; never correct it from that alone
            rows.append({"quarter": q, "securities_high": 0, "securities_low": 0, "rows_changed": 0, "total_before_tn": None, "total_after_tn": None})
            continue
        neighbours = [medians[quarters[j]] for j in (i - 1, i + 1)]
        # Both neighbours must exist and agree: a security present on one side only (a SPAC liquidating,
        # a delisting) can fall by 1,000x for real reasons, and correcting it made the pass flip-flop.
        ratios = pd.concat([medians[q] / n for n in neighbours], axis=1).dropna()
        high = ratios.apply(lambda r: r.between(*UNIT_BAND).all(), axis=1)
        low = ratios.apply(lambda r: r.between(1 / UNIT_BAND[1], 1 / UNIT_BAND[0]).all(), axis=1)
        reference = pd.concat([medians[q][high[high].index] / 1000, medians[q][low[low].index] * 1000])
        h = pd.read_parquet(INTERIM / f"holdings_{q}.parquet")
        before = h["VALUE"].sum()
        ratio = h["VALUE"] / (h["SHARES"] * h["CUSIP"].map(reference))
        h["VALUE"] = h["VALUE"].where(~ratio.between(*UNIT_BAND), h["VALUE"] / 1000)
        h["VALUE"] = h["VALUE"].where(~ratio.between(1 / UNIT_BAND[1], 1 / UNIT_BAND[0]), h["VALUE"] * 1000)
        h.to_parquet(INTERIM / f"holdings_{q}.parquet", index=False)
        rows.append({"quarter": q, "securities_high": int(high.sum()), "securities_low": int(low.sum()),
                     "rows_changed": int((ratio.between(*UNIT_BAND) | ratio.between(1 / UNIT_BAND[1], 1 / UNIT_BAND[0])).sum()),
                     "total_before_tn": round(before / 1e12, 1), "total_after_tn": round(h["VALUE"].sum() / 1e12, 1)})
    return pd.DataFrame(rows)


def fix_wrong_medians(max_passes=6):
    """Repeat the pass until nothing changes, so that the result no longer depends on how often the script ran."""
    logs = []
    for number in range(1, max_passes + 1):
        log = _fix_pass().assign(**{"pass": number})
        logs.append(log)
        print(f"pass {number}: {int(log['rows_changed'].sum())} rows rescaled", flush=True)
        if log["rows_changed"].sum() == 0:
            break
    else:
        print("WARNING: median corrections did not settle within the pass limit")
    pd.concat(logs).to_csv(RESULTS / "median_fixes.csv", index=False)


def main():
    fix_wrong_medians()
    totals = {}
    for q in QUARTERS:
        h = pd.read_parquet(INTERIM / f"holdings_{q}.parquet", columns=["CIK", "VALUE"])
        totals[q] = h.groupby("CIK")["VALUE"].sum()
    t = pd.DataFrame(totals)
    usual = t.median(axis=1)
    names = pd.concat(pd.read_parquet(INTERIM / f"managers_{q}.parquet") for q in QUARTERS).drop_duplicates("CIK").set_index("CIK")["FILINGMANAGER_NAME"]
    rows, summary = [], []
    quarters = list(QUARTERS)
    for i, q in enumerate(quarters):
        h = pd.read_parquet(INTERIM / f"holdings_{q}.parquet")
        # Rule 1: total far above the filer's own median across quarters (blind for filers seen once)
        by_median = set(t.index[t[q] > INFLATION_LIMIT * usual])
        # Rule 2: total far above both neighbouring quarters (a spike); one neighbour at the ends
        neighbour_max = pd.concat([t[quarters[j]] for j in (i - 1, i + 1) if 0 <= j < len(quarters)], axis=1).max(axis=1)
        by_spike = set(t.index[t[q] > INFLATION_LIMIT * neighbour_max])
        # Rule 3: a large share of the filer's value sits in rows priced well above the security's
        # median. Stand-in for "position bigger than the company", since we have no market-cap data.
        price = h["VALUE"] / h["SHARES"]
        enough = h.groupby("CUSIP")["CIK"].transform("nunique") >= MIN_HOLDERS_FOR_PRICE
        off = (price / price.groupby(h["CUSIP"]).transform("median") > PRICE_DISAGREEMENT) & enough
        off_share = h["VALUE"].where(off, 0).groupby(h["CIK"]).sum() / h.groupby("CIK")["VALUE"].sum()
        by_price = set(off_share.index[off_share > OFF_SHARE_LIMIT])
        flagged = sorted(by_median | by_spike | by_price)
        h["VALUE_RELIABLE"] = ~h["CIK"].isin(flagged)
        h.to_parquet(INTERIM / f"holdings_{q}.parquet", index=False)
        for cik in flagged:
            rows.append({"quarter": q, "CIK": cik, "manager": names.get(cik), "total_bn": t.loc[cik, q] / 1e9,
                         "usual_bn": usual[cik] / 1e9, "times_usual": t.loc[cik, q] / usual[cik],
                         "quarters_filed": int(t.loc[cik].notna().sum()),
                         "rules": "+".join(n for n, s in (("median", by_median), ("spike", by_spike), ("price", by_price)) if cik in s)})
        summary.append({"quarter": q, "filers": int(t[q].notna().sum()), "flagged": len(flagged),
                        "by_median": len(by_median), "by_spike": len(by_spike), "by_price": len(by_price),
                        "total_all_tn": t[q].sum() / 1e12, "total_reliable_tn": t[q].drop(flagged).sum() / 1e12})
    flags = pd.DataFrame(rows)
    flags.to_csv(RESULTS / "inflated_filers.csv", index=False)
    s = pd.DataFrame(summary).round(1)
    s.to_csv(RESULTS / "value_totals.csv", index=False)
    print(s.to_string(index=False))
    print(flags["times_usual"].describe(percentiles=[.25, .5, .75, .9]).round(1).to_dict())
    print("times_usual bands by quarter:")
    print(pd.crosstab(flags["quarter"], pd.cut(flags["times_usual"], [5, 10, 100, 500, 2000, 1e9])).to_string())
    print("flags by rule combination:", flags["rules"].value_counts().to_dict())
    new = flags[~flags["rules"].str.contains("median")]
    print("flagged ONLY by the new rules:", len(new), " in", new["quarter"].nunique(), "quarters; one-quarter filers among them:", int((new["quarters_filed"] == 1).sum()))
    print(new.nlargest(10, "total_bn")[["quarter", "manager", "total_bn", "quarters_filed", "rules"]].round(1).to_string(index=False))
    print(flags[flags["quarter"] == "2022Q2"].nlargest(8, "total_bn")[["manager", "total_bn", "usual_bn", "times_usual"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
