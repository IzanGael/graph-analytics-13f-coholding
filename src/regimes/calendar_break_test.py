"""Are individual breaks sharper than smooth drift, and do macro boundaries break harder than other transitions?
Reads calendar_similarity_matrix.csv and calendar_break_strength.csv (from investor_calendar.py) in <folder>,
and adds the p-values to calendar_break_strength.csv. Usage: python calendar_break_test.py <folder>"""
import itertools, sys
from pathlib import Path
import numpy as np, pandas as pd
D = Path(sys.argv[1])
S = pd.read_csv(D / "calendar_similarity_matrix.csv", index_col=0).values
b = pd.read_csv(D / "calendar_break_strength.csv")
n, WIN = len(S), 2
rng = np.random.default_rng(42)
lag_mean = {d: np.mean([S[i, i + d] for i in range(n - d)]) for d in range(1, n)}
def strengths(M):
    out = []
    for c in range(1, n):
        L = list(range(max(0, c - WIN), c)); R = list(range(c, min(n, c + WIN)))
        w = [M[i, j] for g in (L, R) for i, j in itertools.combinations(g, 2)]
        out.append(np.mean(w) - np.mean([M[i, j] for i in L for j in R]))
    return np.array(out)
null = []
for _ in range(5000):
    N = S.copy()
    for d in range(1, n):
        r = np.array([S[i, i + d] - lag_mean[d] for i in range(n - d)]); rng.shuffle(r)
        for i in range(n - d):
            N[i, i + d] = N[i + d, i] = lag_mean[d] + r[i]
    null.append(strengths(N))
null = np.array(null)
b["p_vs_drift"] = [(null[:, k] >= b.break_strength[k]).mean().round(3) for k in range(len(b))]
mx = null.max(axis=1)
b["p_any_of_18"] = [(mx >= v).mean().round(3) for v in b.break_strength]
print(b.sort_values("break_strength", ascending=False).to_string(index=False))
x, m = b.break_strength.values, b.macro_boundary.values
obs = x[m].mean() - x[~m].mean()
nulld = [x[list(c)].mean() - np.delete(x, list(c)).mean() for c in itertools.combinations(range(18), 5)]
print(f"\nmacro boundaries mean={x[m].mean():.4f} others={x[~m].mean():.4f} gap={obs:.4f} p={np.mean(np.array(nulld) >= obs - 1e-12):.3f}")
b.to_csv(D / "calendar_break_strength.csv", index=False)
