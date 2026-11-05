"""DRAFT, NOT PART OF THE PIPELINE AND NEVER RUN. Written before the design decisions of 5 Nov 2026: it still uses the
superseded 10-200 manager rule and the old chance model. Kept for reference until it is rewritten.

Step 5: do communities persist, and do they predict next-quarter co-movement better than sectors?

Each quarter t builds its own universe and communities from holdings at t only. Returns come from
t to t+1, using prices implied by the filings (value / shares), so there is no look-ahead.
Outputs in results/: persistence.csv, return_variance.csv, pair_gaps.csv, return_cleaning.csv
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # shared modules live in src/

from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

import gutils as gl
from config import N_ISSUERS, QUARTERS, RECIPE, RESULTS, SEED

rng = np.random.default_rng(SEED)
N_PERM = 500


def r2_groups(y, labels):
    s = pd.Series(y)
    fitted = s.groupby(np.asarray(labels)).transform("mean")
    return float(fitted.var() / s.var())


def excess_r2(y, labels):
    """R2 minus its mean under random assignment, so that the number of groups does not flatter it."""
    observed = r2_groups(y, labels)
    null = np.array([r2_groups(y, rng.permutation(labels)) for _ in range(N_PERM)])
    return observed, observed - null.mean(), float((null >= observed).mean())


def dummies(labels):
    return pd.get_dummies(pd.Series(labels).astype(str), drop_first=True, dtype=float).to_numpy()


def nested_f(y, base, extra):
    """F test of whether `extra` dummies add explanatory power beyond `base`."""
    from scipy.stats import f as f_dist

    def rss(X):
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        return float(((y - X @ beta) ** 2).sum()), np.linalg.matrix_rank(X)
    ones = np.ones((len(y), 1))
    rss0, r0 = rss(np.hstack([ones, base]))
    rss1, r1 = rss(np.hstack([ones, base, extra]))
    df1, df2 = r1 - r0, len(y) - r1
    F = ((rss0 - rss1) / df1) / (rss1 / df2)
    return F, float(f_dist.sf(F, df1, df2)), 1 - rss1 / ((y - y.mean()) ** 2).sum(), 1 - rss0 / ((y - y.mean()) ** 2).sum()


def clean_returns(q0, q1):
    """Simple return per issuer; drop likely splits and values a data error would produce."""
    p0, c0 = gl.implied_prices(q0)
    p1, c1 = gl.implied_prices(q1)
    same = c0.index.intersection(c1.index)
    same = same[c0.reindex(same).values == c1.reindex(same).values]
    ratio = (p1.reindex(same) / p0.reindex(same)).replace([np.inf, -np.inf], np.nan).dropna()

    def total_shares(q):
        h = pd.read_parquet(gl.INTERIM / f"holdings_{q}.parquet", columns=["CUSIP", "SHARES"])
        return h.groupby("CUSIP")["SHARES"].sum()
    s0, s1 = total_shares(q0), total_shares(q1)
    share_ratio = pd.Series(s1.reindex(c1.reindex(ratio.index).values).values / s0.reindex(c0.reindex(ratio.index).values).values, index=ratio.index)
    # A split moves price and share count in opposite directions by about the same factor
    split = ((ratio < 0.67) | (ratio > 1.5)) & ((ratio * share_ratio).between(0.8, 1.25))
    extreme = (ratio < 0.2) | (ratio > 5)
    r = (ratio - 1)[~split & ~extreme]
    return r, {"priced": len(ratio), "split_flagged": int(split.sum()), "extreme": int((extreme & ~split).sum())}


def main():
    imap = gl.issuer_map()
    quarters = list(QUARTERS)
    built = {}
    for q in quarters:
        pos = gl.load_positions(q)
        uni = gl.universe(pos, imap, N_ISSUERS)
        uni["size_tier"] = pd.qcut(uni["value"].rank(method="first"), 5, labels=False)
        p = gl.restrict_managers(pos, uni, RECIPE["low"], RECIPE["high"])
        C, z, k, m = gl.shared_holder_z(p, uni)
        G = gl.backbone(z, C, list(uni.index), RECIPE["method"], RECIPE["top_k"], RECIPE["z_min"])
        L = gl.largest_component(G)
        runs = [gl.louvain(L, s) for s in range(5)]
        Qs = [nx.community.modularity(L, c, weight="weight") for c in runs]
        built[q] = dict(G=G, L=L, uni=uni, part=gl.as_labels(runs[int(np.argmax(Qs))]), Q=max(Qs), m=m)
        print(q, "managers", m, "edges", G.number_of_edges(), "k", len(runs[int(np.argmax(Qs))]), "Q", round(max(Qs), 3), flush=True)

    persist, variance, gaps, cleaning = [], [], [], []
    for q0, q1 in zip(quarters, quarters[1:]):
        a, b = built[q0], built[q1]
        common = [n for n in a["part"] if n in b["part"]]
        e0, e1 = set(map(frozenset, a["G"].edges)), set(map(frozenset, b["G"].edges))
        ari_comm = adjusted_rand_score([a["part"][n] for n in common], [b["part"][n] for n in common])
        persist.append({"from": q0, "to": q1, "common_nodes": len(common), "edge_jaccard": round(len(e0 & e1) / len(e0 | e1), 3),
                        "community_ari": round(ari_comm, 3), "k_from": len(set(a["part"].values())), "modularity_from": round(a["Q"], 3)})

        r, log = clean_returns(q0, q1)
        cleaning.append({"from": q0, "to": q1, **log})
        idx = [n for n in a["part"] if n in r.index]
        d = a["uni"].loc[idx, ["ff12", "ff48", "sic2", "size_tier"]].copy()
        d["community"] = pd.Series(a["part"]).reindex(idx)
        y = r.reindex(idx).to_numpy()
        row = {"from": q0, "to": q1, "n": len(idx), "market_mean": round(float(y.mean()), 4), "return_sd": round(float(y.std()), 4)}
        for lab in ("community", "ff12", "ff48", "sic2", "size_tier"):
            obs, exc, pval = excess_r2(y, d[lab].astype(str).to_numpy())
            row.update({f"r2_{lab}": round(obs, 4), f"excess_{lab}": round(exc, 4), f"p_{lab}": round(pval, 4), f"groups_{lab}": d[lab].nunique()})
        base = np.hstack([dummies(d["ff12"]), dummies(d["size_tier"])])
        F, pf, r2_full, r2_base = nested_f(y, base, dummies(d["community"]))
        row.update({"comm_beyond_ff12_size_F": round(F, 2), "comm_beyond_ff12_size_p": pf, "r2_base": round(r2_base, 4), "r2_full": round(r2_full, 4)})
        base2 = dummies(d["community"])
        F2, pf2, _, _ = nested_f(y, base2, dummies(d["ff12"]))
        row.update({"ff12_beyond_comm_F": round(F2, 2), "ff12_beyond_comm_p": pf2})
        variance.append(row)
        print(row, flush=True)

        # Direct comparison: the return gap of stock pairs by shared community / shared sector
        ret = y
        comm, sect = d["community"].to_numpy(), d["ff12"].to_numpy()
        i, j = np.triu_indices(len(idx), 1)
        gap = np.abs(ret[i] - ret[j])
        same_c, same_s = comm[i] == comm[j], sect[i] == sect[j]
        gaps.append({"from": q0, "to": q1,
                     "same_comm_same_sector": round(float(gap[same_c & same_s].mean()), 4),
                     "same_comm_diff_sector": round(float(gap[same_c & ~same_s].mean()), 4),
                     "diff_comm_same_sector": round(float(gap[~same_c & same_s].mean()), 4),
                     "diff_comm_diff_sector": round(float(gap[~same_c & ~same_s].mean()), 4)})

    pd.DataFrame(persist).to_csv(RESULTS / "persistence.csv", index=False)
    pd.DataFrame(variance).to_csv(RESULTS / "return_variance.csv", index=False)
    pd.DataFrame(gaps).to_csv(RESULTS / "pair_gaps.csv", index=False)
    pd.DataFrame(cleaning).to_csv(RESULTS / "return_cleaning.csv", index=False)
    print(pd.DataFrame(persist).to_string(index=False))
    print(pd.DataFrame(gaps).to_string(index=False))
    print(pd.DataFrame(cleaning).to_string(index=False))
    v = pd.DataFrame(variance)
    print(v[["from", "n", "r2_community", "excess_community", "r2_ff12", "excess_ff12", "r2_ff48", "excess_ff48", "r2_size_tier", "excess_size_tier", "comm_beyond_ff12_size_p", "ff12_beyond_comm_p"]].to_string(index=False))
    print("means:", v[["excess_community", "excess_ff12", "excess_ff48", "excess_sic2", "excess_size_tier"]].mean().round(4).to_dict())


if __name__ == "__main__":
    main()
