"""Topic 3: sector mapping coverage and first issuer co-holding graph from one 13F quarter.

Usage: python t3_first_graph.py <13f_extracted_dir> <sec_maps_dir> [period] [n_issuers]
CUSIP -> ticker comes from SEC fails-to-deliver files; ticker -> CIK from company_tickers.json;
CIK -> SIC from the SEC Financial Statement Data Sets (sub.txt).
"""
import io
import json
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

d13f, dmap = Path(sys.argv[1]), Path(sys.argv[2])
PERIOD = sys.argv[3] if len(sys.argv) > 3 else "30-JUN-2026"
N_ISSUERS = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
SEED = 42
rng = np.random.default_rng(SEED)

# --- Sector mapping ------------------------------------------------------------------------------
ftd = []
for zname in ("cnsfails202606a.zip", "cnsfails202606b.zip"):
    with zipfile.ZipFile(dmap / zname) as z:
        with z.open(z.namelist()[0]) as fh:
            ftd.append(pd.read_csv(io.TextIOWrapper(fh, encoding="latin-1"), sep="|", dtype=str,
                                   on_bad_lines="skip"))
ftd = pd.concat(ftd).dropna(subset=["CUSIP", "SYMBOL"])
cusip_ticker = ftd.drop_duplicates("CUSIP").set_index("CUSIP")["SYMBOL"]
tick = json.load(open(dmap / "company_tickers.json", encoding="utf-8"))
ticker_cik = {v["ticker"].upper(): int(v["cik_str"]) for v in tick.values()}
with zipfile.ZipFile(dmap / "fs2026q2.zip") as z:
    with z.open("sub.txt") as fh:
        sub = pd.read_csv(fh, sep="\t", dtype=str, usecols=["cik", "sic", "name"])
sub = sub.dropna(subset=["sic"])
cik_sic = {int(c): int(s) for c, s in zip(sub["cik"], sub["sic"])}
print(f"maps: FTD CUSIPs={len(cusip_ticker)} tickers={len(ticker_cik)} CIK-with-SIC={len(cik_sic)}")


def sic_division(sic):
    # Standard Industrial Classification divisions (by 2-digit major group ranges).
    for lo, hi, label in ((100, 999, "Agriculture"), (1000, 1499, "Mining"), (1500, 1799, "Construction"),
                          (2000, 3999, "Manufacturing"), (4000, 4999, "Transport/Utilities"),
                          (5000, 5199, "Wholesale"), (5200, 5999, "Retail"), (6000, 6799, "Finance/RealEstate"),
                          (7000, 8999, "Services")):
        if lo <= sic <= hi:
            return label
    return "Other"


# --- Holdings ------------------------------------------------------------------------------------
t = time.time()
sub13 = pd.read_csv(d13f / "SUBMISSION.tsv", sep="\t", dtype=str)
keep = sub13[(sub13["PERIODOFREPORT"] == PERIOD) & (sub13["SUBMISSIONTYPE"] == "13F-HR")]
cov = pd.read_csv(d13f / "COVERPAGE.tsv", sep="\t", dtype=str,
                  usecols=["ACCESSION_NUMBER", "FILINGMANAGER_NAME", "FILINGMANAGER_STATEORCOUNTRY"])
print(f"13F-HR filings for {PERIOD}: {len(keep)} ; distinct filer CIKs: {keep['CIK'].nunique()}")
info = pd.read_csv(d13f / "INFOTABLE.tsv", sep="\t", dtype=str,
                   usecols=["ACCESSION_NUMBER", "NAMEOFISSUER", "TITLEOFCLASS", "CUSIP", "VALUE",
                            "SSHPRNAMTTYPE", "PUTCALL"])
info = info.merge(keep[["ACCESSION_NUMBER", "CIK"]], on="ACCESSION_NUMBER")
n0 = len(info)
info = info[info["PUTCALL"].isna() & (info["SSHPRNAMTTYPE"] == "SH")].copy()
info["VALUE"] = pd.to_numeric(info["VALUE"], errors="coerce").fillna(0)
info = info[info["VALUE"] > 0]
print(f"rows: period+HR={n0}  long shares only={len(info)}")
info["ISSUER"] = info["CUSIP"].str[:6].str.upper()
info["CUSIP"] = info["CUSIP"].str.upper()

# Issuer level: CUSIP-6 merges share classes of one issuer
h = info.groupby(["CIK", "ISSUER"], as_index=False)["VALUE"].sum()
print(f"manager-issuer pairs={len(h)} managers={h['CIK'].nunique()} issuers (CUSIP6)={h['ISSUER'].nunique()}")
pos = h.groupby("CIK").size()
print("positions per manager: median", pos.median(), "p90", pos.quantile(.9), "max", pos.max())
stats = info.groupby("ISSUER").agg(value=("VALUE", "sum"), name=("NAMEOFISSUER", lambda s: s.value_counts().index[0]),
                                   cusip=("CUSIP", lambda s: s.value_counts().index[0]))
stats["holders"] = h.groupby("ISSUER").size()

# SIC coverage through any CUSIP-9 of the issuer
cusip_map = pd.DataFrame({"CUSIP": info["CUSIP"].unique()})
cusip_map["ISSUER"] = cusip_map["CUSIP"].str[:6]
cusip_map["ticker"] = cusip_map["CUSIP"].map(cusip_ticker)
cusip_map["cik"] = cusip_map["ticker"].map(ticker_cik)
cusip_map["sic"] = cusip_map["cik"].map(cik_sic)
issuer_sic = cusip_map.dropna(subset=["sic"]).drop_duplicates("ISSUER").set_index("ISSUER")
stats["sic"] = issuer_sic["sic"]
stats["ticker"] = issuer_sic["ticker"]
ranked = stats.sort_values("value", ascending=False)
for n in (500, 1000, 2000, 3000):
    print(f"SIC coverage, top {n} issuers by value: {ranked.head(n)['sic'].notna().mean():.3f} "
          f"; share of value mapped {ranked.head(n).loc[ranked.head(n)['sic'].notna(), 'value'].sum() / ranked.head(n)['value'].sum():.3f}")
print("largest unmapped:", ranked[ranked["sic"].isna()].head(15)["name"].tolist())

# --- First graph ---------------------------------------------------------------------------------
# Operating companies only: SIC 6726 is unit trusts/ETF-like vehicles; 6221 commodity pools
uni = ranked[ranked["sic"].notna() & ~ranked["sic"].isin([6726, 6722, 6221])].head(N_ISSUERS).copy()
uni["div"] = uni["sic"].astype(int).map(sic_division)
uni["sic2"] = (uni["sic"].astype(int) // 100)
print(f"\nuniverse={len(uni)} issuers ; divisions={uni['div'].value_counts().to_dict()} ; SIC2 groups={uni['sic2'].nunique()}")
hu = h[h["ISSUER"].isin(uni.index)]

results = {}
def build(hu, label, top_k=15):
    # Issuer-by-manager matrix of portfolio weights; projection = cosine similarity of holder profiles
    mgr = {m: i for i, m in enumerate(hu["CIK"].unique())}
    iss = {s: i for i, s in enumerate(uni.index)}
    w = hu["VALUE"] / hu.groupby("CIK")["VALUE"].transform("sum")
    # Binary matrix for shared-holder counts and null-corrected lift
    X = sp.csr_matrix((np.ones(len(hu)), (hu["ISSUER"].map(iss), hu["CIK"].map(mgr))),
                      shape=(len(iss), len(mgr)))
    C = (X @ X.T).toarray().astype(float)
    k = np.asarray(X.sum(axis=1)).ravel()
    m = len(mgr)
    print(f"\n[{label}] managers={m} ; holders per issuer median={np.median(k):.0f} max={k.max():.0f}")
    raw = C.copy(); np.fill_diagonal(raw, 0)
    print(f"  raw projection (any shared holder): edges={int((raw > 0).sum() / 2)} density={(raw > 0).sum() / (len(k) * (len(k) - 1)):.3f}")
    # Lift over independent-holding expectation; a popularity-free similarity
    expected = np.outer(k, k) / m
    lift = C / np.maximum(expected, 1e-9)
    z = (C - expected) / np.sqrt(np.maximum(expected * (1 - k[:, None] / m) * (1 - k[None, :] / m), 1e-9))
    np.fill_diagonal(z, 0)
    G = nx.Graph()
    names = list(uni.index)
    G.add_nodes_from(names)
    order = np.argsort(-z, axis=1)[:, :top_k]
    for i in range(len(names)):
        for j in order[i]:
            if z[i, j] > 3:
                G.add_edge(names[i], names[int(j)], weight=float(z[i, j]))
    print(f"  backbone (top-{top_k} z per node, z>3): nodes={G.number_of_nodes()} edges={G.number_of_edges()} density={nx.density(G):.4f}")
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    print("  components:", len(comps), " largest:", [len(c) for c in comps[:4]])
    gcc = G.subgraph(comps[0]).copy()
    s = time.time()
    print(f"  LCC diameter={nx.diameter(gcc)} radius={nx.radius(gcc)} (hop, {time.time() - s:.1f}s)")
    part_runs = []
    for seed in range(5):
        cm = nx.community.louvain_communities(gcc, weight="weight", seed=seed)
        part_runs.append(({n: i for i, c in enumerate(cm) for n in c}, nx.community.modularity(gcc, cm, weight="weight"), cm))
    nodes = list(gcc)
    stab = np.mean([adjusted_rand_score([a[0][n] for n in nodes], [b[0][n] for n in nodes])
                    for i, a in enumerate(part_runs) for b in part_runs[i + 1:]])
    best = max(part_runs, key=lambda r: r[1])
    part, Q, cm = best
    pl = [part[n] for n in nodes]
    print(f"  Louvain: k={len(cm)} modularity={Q:.3f} seed-stability ARI={stab:.3f}")
    for lab in ("div", "sic2"):
        y = [uni.loc[n, lab] for n in nodes]
        shuf = rng.permutation(y)
        print(f"  vs {lab}: NMI={normalized_mutual_info_score(y, pl):.3f} ARI={adjusted_rand_score(y, pl):.3f} "
              f"(shuffled labels NMI={normalized_mutual_info_score(shuf, pl):.3f} ARI={adjusted_rand_score(shuf, pl):.3f})")
    lpa = list(nx.community.asyn_lpa_communities(gcc, weight="weight", seed=SEED))
    print(f"  label propagation: k={len(lpa)} largest={sorted(map(len, lpa), reverse=True)[:5]} "
          f"modularity={nx.community.modularity(gcc, lpa, weight='weight'):.3f}")
    for c in sorted(cm, key=len, reverse=True)[:9]:
        sub_ = uni.loc[list(c)].sort_values("value", ascending=False)
        print(f"   {len(c):4d} {Counter(sub_['div']).most_common(3)}  "
              f"{[str(x)[:22] for x in sub_['name'].head(7)]}")
    pr = nx.pagerank(gcc, weight="weight", alpha=0.85)
    ev = nx.eigenvector_centrality_numpy(gcc, weight="weight")
    bc = nx.betweenness_centrality(gcc, k=min(300, len(gcc)), seed=SEED)
    show = lambda sc: [str(uni.loc[n, "name"])[:20] for n, _ in sorted(sc.items(), key=lambda kv: -kv[1])[:7]]
    print("  PageRank top:", show(pr))
    print("  eigenvector top:", show(ev))
    print("  betweenness top:", show(bc))
    return part, nodes


# (a) All managers
build(hu, "all managers")
# (b) Active-ish managers: exclude near-index portfolios and tiny filers
size = hu.groupby("CIK").size()
active = size[(size >= 10) & (size <= 200)].index
part_active, nodes_active = build(hu[hu["CIK"].isin(active)], "managers holding 10-200 of universe")
print(f"\ntotal seconds: {time.time() - t:.0f}")
