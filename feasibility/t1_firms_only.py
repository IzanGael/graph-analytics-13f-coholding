"""Topic 1: rerun with firms only and real borrower countries; test stability across two periods.

Usage: python t1_firms_only.py <contracts.jsonl>
"""
import json
import re
import sys
from collections import Counter, defaultdict

import networkx as nx
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

SEED = 42
AGG = re.compile(r"Africa$|^Africa|Asia|Pacific|Caribbean|World|Region|OECS|Countries|Middle East|Caucasus|Latin America|Europe")
ALIASES = [("ERNST", "ERNST YOUNG"), ("KPMG", "KPMG"), ("PRICEWATERHOUSE", "PWC"), ("PRICE WATERHOUSE", "PWC"),
           ("DELOITTE", "DELOITTE"), ("GRANT THORNTON", "GRANT THORNTON"), ("BDO", "BDO"), ("SMEC", "SMEC")]


def norm(name):
    name = re.sub(r"[^A-Z0-9 ]", " ", (name or "").upper())
    name = re.sub(r"\b(LTD|LIMITED|LLC|INC|SA|SARL|SRL|GMBH|CO|COMPANY|CORP|CORPORATION|PVT|PLC|BV|AG|THE)\b", " ", name)
    name = " ".join(name.split())
    for token, alias in ALIASES:
        if token in name:
            return alias
    return name


rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
recs = []
null_name = individual_method = 0
for r in rows:
    if "Individual" in (r.get("procu_meth_text") or ""):
        individual_method += 1
        continue
    borrower = r.get("countryshortname")
    if not borrower or AGG.search(borrower):
        continue
    year = pd.to_datetime(r.get("contr_sgn_date"), format="%d-%b-%Y").year
    for s in r.get("suppinfo") or []:
        name = norm(s.get("name"))
        if not name:
            null_name += 1
            continue
        if name == "INDIVIDUAL CONSULTANT":
            continue
        recs.append((name, borrower, r.get("regionname"), year, s.get("countryshortname"),
                     float(s.get("supplier_contr_amount") or 0), (r.get("mjsecname") or [None])[0]))
df = pd.DataFrame(recs, columns=["firm", "borrower", "region", "year", "home", "amt", "sector"])
print(f"dropped individual-method contracts={individual_method} ; null supplier names={null_name}")
df = df[df["year"] >= 2016]
print(f"firm-contract records 2016+={len(df)} firms={df['firm'].nunique()} borrowers={df['borrower'].nunique()} value=${df['amt'].sum() / 1e9:.1f}bn")
reach = df.groupby("firm")["borrower"].nunique()
print("firms by #countries: 1:", int((reach == 1).sum()), "2:", int((reach == 2).sum()), "3-9:", int(((reach >= 3) & (reach < 10)).sum()), "10+:", int((reach >= 10).sum()))
print("top firms by countries:", reach.sort_values(ascending=False).head(12).to_dict())
share = df.groupby("firm")["amt"].sum().sort_values(ascending=False)
print(f"top 1% firms share of value: {share.head(max(1, len(share) // 100)).sum() / share.sum():.3f}")
region_of = df.drop_duplicates("borrower").set_index("borrower")["region"].to_dict()


def country_graph(d, min_reach=2, top_k=8):
    # Keep firms active in >=2 countries; only these create projection edges
    d = d.drop_duplicates(["firm", "borrower"])
    r = d.groupby("firm")["borrower"].nunique()
    d = d[d["firm"].isin(r[r >= min_reach].index)]
    size = d.groupby("borrower").size()
    pairs = Counter()
    for _, g in d.groupby("firm"):
        c = sorted(g["borrower"])
        for i, a in enumerate(c):
            for b in c[i + 1:]:
                pairs[(a, b)] += 1
    sims = defaultdict(list)
    for (a, b), w in pairs.items():
        cos = w / (size[a] * size[b]) ** 0.5
        sims[a].append((cos, b, w))
        sims[b].append((cos, a, w))
    G = nx.Graph()
    G.add_nodes_from(size.index)
    for a, lst in sims.items():
        for cos, b, w in sorted(lst, reverse=True)[:top_k]:
            G.add_edge(a, b, weight=cos, shared=w)
    return G, d["firm"].nunique()


def run(d, label):
    G, firms = country_graph(d)
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    gc = G.subgraph(comps[0]).copy()
    print(f"\n[{label}] multi-country firms={firms} ; countries={len(G)} edges={G.number_of_edges()} comps={[len(c) for c in comps[:4]]} "
          f"diam={nx.diameter(gc)} rad={nx.radius(gc)}")
    runs = [nx.community.louvain_communities(gc, weight="weight", seed=s) for s in range(5)]
    parts = [{n: i for i, c in enumerate(cm) for n in c} for cm in runs]
    nodes = list(gc)
    stab = sum(adjusted_rand_score([p[n] for n in nodes], [q[n] for n in nodes])
               for i, p in enumerate(parts) for q in parts[i + 1:]) / 10
    Q = [nx.community.modularity(gc, cm, weight="weight") for cm in runs]
    best = int(max(range(5), key=lambda i: Q[i]))
    y = [region_of.get(n) for n in nodes]
    pl = [parts[best][n] for n in nodes]
    print(f"  Louvain k={len(runs[best])} Q={Q[best]:.3f} seed-stability ARI={stab:.3f} NMI vs region={normalized_mutual_info_score(y, pl):.3f} ARI={adjusted_rand_score(y, pl):.3f}")
    for c in sorted(runs[best], key=len, reverse=True):
        print(f"   {len(c):3d} {Counter(region_of.get(n, '?')[:18] for n in c).most_common(2)} {sorted(c)[:11]}")
    bc = nx.betweenness_centrality(gc)
    pr = nx.pagerank(gc, weight="weight")
    print("  betweenness top:", [n for n, _ in sorted(bc.items(), key=lambda kv: -kv[1])[:7]])
    print("  PageRank top:", [n for n, _ in sorted(pr.items(), key=lambda kv: -kv[1])[:7]])
    return {n: p for n, p in parts[best].items()}


full = run(df, "2016-2026")
early = run(df[df["year"] <= 2020], "2016-2020")
late = run(df[df["year"] >= 2021], "2021-2026")
common = [n for n in early if n in late]
print(f"\nperiod stability ARI={adjusted_rand_score([early[n] for n in common], [late[n] for n in common]):.3f} on {len(common)} countries")

# Firm-firm projection size at reach >= 2 (shared countries)
dd = df.drop_duplicates(["firm", "borrower"])
r2 = dd.groupby("firm")["borrower"].nunique()
sel = dd[dd["firm"].isin(r2[r2 >= 3].index)]
print(f"\nfirm projection candidates (3+ countries): firms={sel['firm'].nunique()}")
