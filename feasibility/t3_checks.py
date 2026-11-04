"""Topic 3: test the size confound, quarter-to-quarter stability and extended SIC coverage.

Usage: python t3_checks.py <q2_extracted> <q1_extracted> <sec_maps_dir>
Fixed universe from Q2 2026; the same backbone recipe (top-15 z, z>3, managers holding 10-200) per quarter.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

q2, q1, dmap = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SEED = 42


def holdings(folder, period):
    sub = pd.read_csv(folder / "SUBMISSION.tsv", sep="\t", dtype=str)
    keep = sub[(sub["PERIODOFREPORT"] == period) & (sub["SUBMISSIONTYPE"] == "13F-HR")]
    info = pd.read_csv(folder / "INFOTABLE.tsv", sep="\t", dtype=str,
                       usecols=["ACCESSION_NUMBER", "NAMEOFISSUER", "CUSIP", "VALUE", "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL"])
    info = info.merge(keep[["ACCESSION_NUMBER", "CIK"]], on="ACCESSION_NUMBER")
    info = info[info["PUTCALL"].isna() & (info["SSHPRNAMTTYPE"] == "SH")].copy()
    info["VALUE"] = pd.to_numeric(info["VALUE"], errors="coerce").fillna(0)
    info["SHARES"] = pd.to_numeric(info["SSHPRNAMT"], errors="coerce").fillna(0)
    info = info[info["VALUE"] > 0]
    info["CUSIP"] = info["CUSIP"].str.upper()
    info["ISSUER"] = info["CUSIP"].str[:6]
    return info


ftd = []
for zpath in sorted(dmap.glob("cnsfails*.zip")):
    with zipfile.ZipFile(zpath) as z, z.open(z.namelist()[0]) as fh:
        ftd.append(pd.read_csv(io.TextIOWrapper(fh, encoding="latin-1"), sep="|", dtype=str, on_bad_lines="skip"))
ftd = pd.concat(ftd).dropna(subset=["CUSIP", "SYMBOL"])
cusip_ticker = ftd.drop_duplicates("CUSIP").set_index("CUSIP")["SYMBOL"]
tick = json.load(open(dmap / "company_tickers.json", encoding="utf-8"))
ticker_cik = {v["ticker"].upper(): int(v["cik_str"]) for v in tick.values()}
with zipfile.ZipFile(dmap / "fs2026q2.zip") as z, z.open("sub.txt") as fh:
    fs = pd.read_csv(fh, sep="\t", dtype=str, usecols=["cik", "sic"]).dropna()
cik_sic = {int(c): int(s) for c, s in zip(fs["cik"], fs["sic"])}

h2 = holdings(q2, "30-JUN-2026")
cm = pd.DataFrame({"CUSIP": h2["CUSIP"].unique()})
cm["ISSUER"] = cm["CUSIP"].str[:6]
cm["sic"] = cm["CUSIP"].map(cusip_ticker).map(ticker_cik).map(cik_sic)
issuer_sic = cm.dropna(subset=["sic"]).drop_duplicates("ISSUER").set_index("ISSUER")["sic"]
stats = h2.groupby("ISSUER").agg(value=("VALUE", "sum"), name=("NAMEOFISSUER", lambda s: s.value_counts().index[0]))
stats["sic"] = issuer_sic
ranked = stats.sort_values("value", ascending=False)
print(f"FTD files={len(list(dmap.glob('cnsfails*.zip')))} CUSIPs={len(cusip_ticker)}")
print("SIC coverage top1000:", round(ranked.head(1000)["sic"].notna().mean(), 3))
print("top-40 still unmapped:", ranked.head(40)[ranked.head(40)["sic"].isna()]["name"].tolist())
print("top-1000 unmapped non-fund sample:", [n for n in ranked.head(1000)[ranked.head(1000)["sic"].isna()]["name"]
                                             if not any(t in n.upper() for t in ("ETF", " TR", "FD", "FUND", "ISHARES", "SPDR", "INVESCO"))][:15])
uni = ranked[ranked["sic"].notna() & ~ranked["sic"].isin([6726, 6722, 6221])].head(1000).copy()
uni["sic2"] = uni["sic"].astype(int) // 100
uni["size_tier"] = pd.qcut(uni["value"].rank(method="first"), 5, labels=False)


def graph(info):
    h = info.groupby(["CIK", "ISSUER"], as_index=False)["VALUE"].sum()
    h = h[h["ISSUER"].isin(uni.index)]
    size = h.groupby("CIK").size()
    h = h[h["CIK"].isin(size[(size >= 10) & (size <= 200)].index)]
    mgr = {m: i for i, m in enumerate(h["CIK"].unique())}
    iss = {s: i for i, s in enumerate(uni.index)}
    X = sp.csr_matrix((np.ones(len(h)), (h["ISSUER"].map(iss), h["CIK"].map(mgr))), shape=(len(iss), len(mgr)))
    C = (X @ X.T).toarray().astype(float)
    k = np.asarray(X.sum(axis=1)).ravel()
    m = len(mgr)
    exp = np.outer(k, k) / m
    z = (C - exp) / np.sqrt(np.maximum(exp * (1 - k[:, None] / m) * (1 - k[None, :] / m), 1e-9))
    np.fill_diagonal(z, 0)
    names = list(uni.index)
    G = nx.Graph()
    G.add_nodes_from(names)
    for i, row in enumerate(np.argsort(-z, axis=1)[:, :15]):
        for j in row:
            if z[i, j] > 3:
                G.add_edge(names[i], names[int(j)], weight=float(z[i, j]))
    return G, m


G2, m2 = graph(h2)
h1 = holdings(q1, "31-MAR-2026")
G1, m1 = graph(h1)
print(f"Q2 managers={m2} edges={G2.number_of_edges()} ; Q1 managers={m1} edges={G1.number_of_edges()}")
gc2 = G2.subgraph(max(nx.connected_components(G2), key=len))
gc1 = G1.subgraph(max(nx.connected_components(G1), key=len))
print("Edge overlap Jaccard Q1/Q2:", round(len(set(map(frozenset, G1.edges)) & set(map(frozenset, G2.edges))) / len(set(map(frozenset, G1.edges)) | set(map(frozenset, G2.edges))), 3))


def partition(G, seed):
    return {n: i for i, c in enumerate(nx.community.louvain_communities(G, weight="weight", seed=seed)) for n in c}


p2, p1 = partition(gc2, SEED), partition(gc1, SEED)
common = [n for n in p2 if n in p1]
print(f"Quarter-to-quarter Louvain ARI={adjusted_rand_score([p2[n] for n in common], [p1[n] for n in common]):.3f} "
      f"NMI={normalized_mutual_info_score([p2[n] for n in common], [p1[n] for n in common]):.3f}")
nodes = list(gc2)
pl = [p2[n] for n in nodes]
for lab in ("sic2", "size_tier"):
    y = [uni.loc[n, lab] for n in nodes]
    print(f"Q2 communities vs {lab}: NMI={normalized_mutual_info_score(y, pl):.3f} ARI={adjusted_rand_score(y, pl):.3f}")
print("Size tier by community (median rank pct):", sorted(
    (round(float(uni.loc[[n for n in nodes if p2[n] == c], "value"].rank(pct=False).size), 0),
     round(float(uni["value"].rank(pct=True).loc[[n for n in nodes if p2[n] == c]].median()), 2))
    for c in set(pl)))

# 13F-implied quarterly return (value/shares per CUSIP) as a built-in co-movement check
def px(info):
    g = info[info["SHARES"] > 0].groupby("ISSUER")[["VALUE", "SHARES"]].sum()
    return g["VALUE"] / g["SHARES"]


ret = (px(h2) / px(h1) - 1).reindex(nodes).replace([np.inf, -np.inf], np.nan).dropna()
ret = ret[ret.abs() < 2]
df = pd.DataFrame({"ret": ret, "comm": pd.Series(p2).reindex(ret.index), "sic2": uni["sic2"].reindex(ret.index)})
tot = df["ret"].var()
for lab in ("comm", "sic2"):
    between = df.groupby(lab)["ret"].transform("mean").var()
    print(f"Q2 2026 implied-return variance explained by {lab}: {between / tot:.3f} (groups={df[lab].nunique()})")
shuf = df.assign(comm=np.random.default_rng(SEED).permutation(df["comm"]))
print(f"  same, shuffled communities: {shuf.groupby('comm')['ret'].transform('mean').var() / tot:.3f}")
