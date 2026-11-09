"""Profile the bet groups (conviction graph, threshold 2) of chosen quarters, to name their themes.

Per group: size, key stocks (strength inside the group = sum of z to group members), sector mix (Fama-French 12 and 48),
size mix (value quintile within the 1,000), top betting managers, and how the group maps onto ownership groups.
Then matches groups across the quarters (Jaccard of members).
Usage: python conviction_profiles.py <repo folder> <out folder> <quarter> [<quarter> ...]
"""
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

REPO, OUT, QS = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
sys.path.insert(0, str(REPO / "src"))
import gutils as gl
from config import INTERIM, ISSUER_ALIASES

GC, GO, T = INTERIM / "graphs_conviction", INTERIM / "graphs", 2.0


def best_louvain(e, runs=20):
    G = nx.Graph(); G.add_weighted_edges_from(e[["source", "target", "z"]].itertuples(index=False))
    cs = [nx.community.louvain_communities(G, weight="weight", seed=42 + s) for s in range(runs)]
    best = max(cs, key=lambda c: nx.community.modularity(G, c, weight="weight"))
    return G, sorted(best, key=len, reverse=True)


groups, rows = {}, []
for q in QS:
    nodes = pd.read_parquet(GC / f"nodes_t{T}_{q}.parquet")
    nodes["label"] = nodes["ticker"].fillna(nodes["NAME"].str[:14])
    nodes["size_q"] = pd.qcut(nodes["value"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)  # 5 = largest
    G, comms = best_louvain(pd.read_parquet(GC / f"edges_t{T}_{q}.parquet"))
    _, own = best_louvain(pd.read_parquet(GO / f"edges_k15_{q}.parquet"), runs=5)
    own_lab = {v: i for i, c in enumerate(own) for v in c}
    # bets of this quarter, to find who bets on each group (same rules as conviction_build.py)
    h = pd.read_parquet(INTERIM / f"holdings_{q}.parquet", columns=["CIK", "CUSIP", "VALUE", "VALUE_RELIABLE"])
    h["ISSUER"] = h["CUSIP"].str[:6].replace(ISSUER_ALIASES)
    p = h.groupby(["CIK", "ISSUER"], as_index=False).agg(VALUE=("VALUE", "sum"), REL=("VALUE_RELIABLE", "all"))
    uni = pd.read_parquet(GO / f"nodes_{q}.parquet")
    p = p[p.ISSUER.isin(uni.index) & p.REL & (p.VALUE > 0)]
    p = p[p.groupby("CIK").ISSUER.transform("size") >= 10].copy()
    mkt = p.groupby("ISSUER").VALUE.sum(); mkt /= mkt.sum()
    p["w"] = p.VALUE / p.groupby("CIK").VALUE.transform("sum"); p["W"] = p.ISSUER.map(mkt)
    p["ow"] = p.w / (p.W / p.groupby("CIK").W.transform("sum"))
    bets = p[p.ow > T]
    mnames = pd.read_parquet(INTERIM / f"managers_{q}.parquet").drop_duplicates("CIK").set_index("CIK")["FILINGMANAGER_NAME"]
    groups[q] = []
    print(f"\n{'=' * 30} {q}: {len(comms)} bet groups {'=' * 30}")
    for gi, c in enumerate(comms):
        if len(c) < 10:
            continue
        sub = nodes.loc[sorted(c)]
        strength = {v: sum(d["weight"] for u, d in G[v].items() if u in c) for v in c}
        key = sorted(c, key=lambda v: -strength[v])[:12]
        ff12 = sub["ff12"].fillna("NA").value_counts(normalize=True).head(4)
        ff48 = sub["ff48"].fillna("NA").value_counts(normalize=True).head(5)
        b = bets[bets.ISSUER.isin(c)]
        mgr = b.groupby("CIK").ISSUER.nunique().sort_values(ascending=False).head(6)
        own_counts = pd.Series([own_lab[v] for v in c if v in own_lab]).value_counts(normalize=True)
        biggest = sub.sort_values("value", ascending=False).head(6)["label"].tolist()
        r = {"quarter": q, "group": gi + 1, "stocks": len(c),
             "key_stocks": ", ".join(nodes.loc[key, "label"]), "largest_stocks": ", ".join(biggest),
             "ff12_mix": ", ".join(f"{k} {v:.0%}" for k, v in ff12.items()),
             "ff48_mix": ", ".join(f"{k} {v:.0%}" for k, v in ff48.items()),
             "pct_top_size_quintile": round(100 * (sub.size_q == 5).mean()), "pct_bottom_2_quintiles": round(100 * (sub.size_q <= 2).mean()),
             "median_bettors": int(sub["bettors"].median()),
             "top_bettors": "; ".join(f"{str(mnames.get(m, m))[:30]} ({k})" for m, k in mgr.items()),
             "own_groups_spanned": int((own_counts >= 0.10).sum()), "share_in_main_own_group": round(100 * own_counts.iloc[0])}
        rows.append(r); groups[q].append((gi + 1, set(c)))
        print(f"\n[{q} G{gi+1}] {len(c)} stocks | size: {r['pct_top_size_quintile']}% largest fifth, {r['pct_bottom_2_quintiles']}% smallest two fifths | "
              f"ownership groups spanned: {r['own_groups_spanned']} (main {r['share_in_main_own_group']}%)")
        print("  key:", r["key_stocks"]); print("  biggest:", r["largest_stocks"])
        print("  FF12:", r["ff12_mix"]); print("  FF48:", r["ff48_mix"]); print("  bettors:", r["top_bettors"])

pd.DataFrame(rows).to_csv(OUT / f"bet_group_profiles_{'_'.join(QS)}.csv", index=False)
if len(QS) == 2:
    a, b = QS
    M = pd.DataFrame([[len(x & y) / len(x | y) for _, y in groups[b]] for _, x in groups[a]],
                     index=[f"{a} G{i}" for i, _ in groups[a]], columns=[f"{b} G{i}" for i, _ in groups[b]])
    M.round(2).to_csv(OUT / f"bet_group_match_{a}_{b}.csv")
    print(f"\nOverlap of members (Jaccard) between {a} and {b} groups:\n", M.round(2).to_string())
