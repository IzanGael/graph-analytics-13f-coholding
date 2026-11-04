"""Topic 1: data-quality profile and first graphs from World Bank consulting contracts.

Usage: python t1_first_graph.py <contracts.jsonl> [start_year]
"""
import json
import re
import sys
import time
from collections import Counter, defaultdict
from itertools import combinations

import networkx as nx
import pandas as pd
from networkx.algorithms import bipartite
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

path = sys.argv[1]
START = int(sys.argv[2]) if len(sys.argv) > 2 else 2016
SEED = 42

rows = [json.loads(line) for line in open(path, encoding="utf-8")]
ids = [r.get("contr_id") for r in rows]
print(f"rows={len(rows)} unique contr_id={len(set(ids))} missing id={sum(i is None for i in ids)}")
rows = list({r["contr_id"]: r for r in rows if r.get("contr_id")}.values())

dates = pd.to_datetime([r.get("contr_sgn_date") for r in rows], format="%d-%b-%Y", errors="coerce")
print("signing date: missing", int(dates.isna().sum()), "min", dates.min(), "max", dates.max())
print("contracts per year (last 15):", pd.Series(dates.year).value_counts().sort_index().tail(15).astype(int).to_dict())
print("share with 'year' field:", sum("year" in r for r in rows) / len(rows))

no_supp = sum(not r.get("suppinfo") for r in rows)
n_supp = Counter(len(r.get("suppinfo") or []) for r in rows)
print("contracts without suppinfo:", no_supp, " suppliers per contract:", sorted(n_supp.items())[:8])
print("share with sector:", sum(bool(r.get("sector")) for r in rows) / len(rows),
      " with major sector:", sum(bool(r.get("mjsecname")) for r in rows) / len(rows))
print("major sectors:", Counter(s for r in rows for s in (r.get("mjsecname") or [])).most_common(12))
print("review type:", Counter(r.get("rvw_type") for r in rows).most_common())
print("method:", Counter(r.get("procu_meth_text") for r in rows).most_common(8))

# Supplier identity quality
def norm(name):
    name = re.sub(r"[^A-Z0-9 ]", " ", (name or "").upper())
    name = re.sub(r"\b(LTD|LIMITED|LLC|INC|SA|SARL|SRL|GMBH|CO|COMPANY|CORP|CORPORATION|PVT|PLC|BV|AG|THE)\b", " ", name)
    return " ".join(name.split())

names_of, ids_of, ctry_of = defaultdict(set), defaultdict(set), defaultdict(Counter)
missing_id = total_supp = 0
for r in rows:
    for s in r.get("suppinfo") or []:
        total_supp += 1
        if not s.get("id"):
            missing_id += 1
            continue
        names_of[s["id"]].add(s.get("name"))
        ids_of[norm(s.get("name"))].add(s["id"])
        ctry_of[s["id"]][s.get("countryshortname")] += 1
print(f"supplier records={total_supp} missing id={missing_id} unique ids={len(names_of)} "
      f"unique normalised names={len(ids_of)}")
print("ids with >1 spelling:", sum(len(v) > 1 for v in names_of.values()),
      " normalised names with >1 id:", sum(len(v) > 1 for v in ids_of.values()),
      " ids with >1 country:", sum(len(v) > 1 for v in ctry_of.values()))
print("example fragmented names:", [(k, len(v)) for k, v in sorted(ids_of.items(), key=lambda kv: -len(kv[1]))[:12]])
print("individual-looking suppliers (2-3 words, no firm token) sample:",
      [n for n in list(ids_of)[:4000] if re.fullmatch(r"[A-Z]+ [A-Z]+( [A-Z]+)?", n)][:8])

# Modelling window
window = [r for r, d in zip(rows, dates) if pd.notna(d) and d.year >= START and r.get("suppinfo")]
print(f"\n== window {START}+: contracts={len(window)}")
region_of = {}
for r in window:
    region_of.setdefault(r.get("countryshortname"), r.get("regionname"))


def report(G, name, weight="weight"):
    t = time.time()
    print(f"\n-- {name}: nodes={G.number_of_nodes()} edges={G.number_of_edges()} density={nx.density(G):.4f}")
    if G.is_directed():
        print("   weak components:", nx.number_weakly_connected_components(G),
              " strong:", nx.number_strongly_connected_components(G))
        largest_strong = max(nx.strongly_connected_components(G), key=len)
        print("   largest SCC:", len(largest_strong))
        return
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    print("   components:", len(comps), " largest:", [len(c) for c in comps[:5]])
    gcc = G.subgraph(comps[0]).copy()
    if gcc.number_of_nodes() <= 6000:
        print(f"   LCC diameter={nx.diameter(gcc)} radius={nx.radius(gcc)} ({time.time() - t:.1f}s, hop distance)")
    else:
        print("   LCC diameter (2-sweep lower bound):", nx.approximation.diameter(gcc, seed=SEED))
    return gcc


# (a) Bipartite supplier - borrower-country
edges = Counter()
amount = Counter()
for r in window:
    borrower = r.get("countryshortname")
    for s in r["suppinfo"]:
        if s.get("id") and borrower:
            edges[(s["id"], borrower)] += 1
            amount[(s["id"], borrower)] += float(s.get("supplier_contr_amount") or 0)
B = nx.Graph()
suppliers = {u for u, _ in edges}
countries = {v for _, v in edges}
B.add_nodes_from(suppliers, bipartite=0)
B.add_nodes_from(countries, bipartite=1)
B.add_weighted_edges_from((u, v, w) for (u, v), w in edges.items())
report(B, "bipartite supplier-borrower")
deg = Counter(u for u, _ in edges)
print("   suppliers by #borrower countries: 1 ->", sum(v == 1 for v in deg.values()),
      " 2 ->", sum(v == 2 for v in deg.values()), " 3+ ->", sum(v >= 3 for v in deg.values()),
      " 10+ ->", sum(v >= 10 for v in deg.values()))

# (b) Country-country projection (shared suppliers), weighted by shared suppliers, with cosine backbone
P = bipartite.weighted_projected_graph(B, countries)
gcc = report(P, "borrower-country projection (shared suppliers)")
sup_count = Counter(v for _, v in edges)
for u, v, d in P.edges(data=True):
    d["cos"] = d["weight"] / (sup_count[u] * sup_count[v]) ** 0.5
top = sorted(P.edges(data=True), key=lambda e: -e[2]["cos"])
H = nx.Graph()
H.add_nodes_from(P.nodes)
per_node = defaultdict(list)
for u, v, d in top:
    per_node[u].append((v, d["cos"]))
    per_node[v].append((u, d["cos"]))
for u, lst in per_node.items():
    for v, c in lst[:8]:
        H.add_edge(u, v, weight=c)
gh = report(H, "country backbone (top-8 cosine per node)")
labels = {n: region_of.get(n) for n in gh}
comms = nx.community.louvain_communities(gh, weight="weight", seed=SEED)
Q = nx.community.modularity(gh, comms, weight="weight")
part = {n: i for i, c in enumerate(comms) for n in c}
nodes = [n for n in gh if labels[n]]
print(f"   Louvain: k={len(comms)} modularity={Q:.3f} "
      f"NMI vs WB region={normalized_mutual_info_score([labels[n] for n in nodes], [part[n] for n in nodes]):.3f} "
      f"ARI={adjusted_rand_score([labels[n] for n in nodes], [part[n] for n in nodes]):.3f}")
for c in sorted(comms, key=len, reverse=True)[:8]:
    print("   ", len(c), Counter(labels[n] for n in c).most_common(2), sorted(c)[:9])
pr = nx.pagerank(gh, weight="weight", alpha=0.85)
print("   PageRank top:", [n for n, _ in sorted(pr.items(), key=lambda kv: -kv[1])[:10]])

# (c) Directed flow: supplier home country -> borrower country, weighted by contract value
F = nx.DiGraph()
flow, n_flow = Counter(), Counter()
for r in window:
    borrower = r.get("countryshortname")
    for s in r["suppinfo"]:
        home = s.get("countryshortname")
        if home and borrower:
            flow[(home, borrower)] += float(s.get("supplier_contr_amount") or 0)
            n_flow[(home, borrower)] += 1
domestic = sum(v for (a, b), v in flow.items() if a == b)
print(f"\n   domestic share of contract value: {domestic / sum(flow.values()):.3f}")
for (a, b), v in flow.items():
    if a != b and v > 0:
        F.add_edge(a, b, weight=v, n=n_flow[(a, b)])
report(F, "directed cross-border flow (home -> borrower)")
scc = max(nx.strongly_connected_components(F), key=len)
Fs = F.subgraph(scc)
print(f"   SCC diameter={nx.diameter(Fs)} radius={nx.radius(Fs)}")
pr = nx.pagerank(F, weight="weight", alpha=0.85)
print("   PageRank top (receivers):", [n for n, _ in sorted(pr.items(), key=lambda kv: -kv[1])[:8]])
out = Counter()
for (a, b), v in flow.items():
    if a != b:
        out[a] += v
print("   top exporters by value $bn:", [(k, round(v / 1e9, 2)) for k, v in out.most_common(10)])

# (d) Direct co-award graph from multi-supplier contracts
J = nx.Graph()
for r in window:
    sup = sorted({s["id"] for s in r["suppinfo"] if s.get("id")})
    for a, b in combinations(sup, 2):
        J.add_edge(a, b, weight=J.get_edge_data(a, b, {"weight": 0})["weight"] + 1)
jg = report(J, "direct co-award firm graph (consortia)")
name = {k: sorted(v, key=lambda x: len(x or ""))[0] for k, v in names_of.items()}
print("   degree top:", [(name.get(n), d) for n, d in sorted(J.degree, key=lambda kv: -kv[1])[:8]])
if jg is not None:
    comms = nx.community.louvain_communities(jg, weight="weight", seed=SEED)
    print(f"   Louvain on LCC: k={len(comms)} modularity={nx.community.modularity(jg, comms, weight='weight'):.3f}")
