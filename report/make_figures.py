"""Figures and tables for the report and the defense slides (maroon / orange / beige palette).

Reads the outputs of src/regimes/ (results/regimes/) and writes f1-f6 PNGs. The report uses f2 (regime heatmap),
f4 (ownership vs conviction) and f6 (co-movement); the slides also use f1 (graph measures), f3 (fund example)
and f5 (tribes table).
Usage, from the project folder: python report/make_figures.py results/regimes report/figures
Then compile report/written-report.tex (LaTeX, course template) with biblio.bib.
"""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np, pandas as pd

R = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(exist_ok=True)
BG, MAROON, ORANGE, LORANGE, BEIGE, GREY = "#F7EFE9", "#5B1A18", "#EE6A35", "#F5BC6E", "#DDC9B8", "#9A8A80"
plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": MAROON, "axes.labelcolor": MAROON, "xtick.color": MAROON,
                     "ytick.color": MAROON, "axes.edgecolor": MAROON, "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG})
CMAP = LinearSegmentedColormap.from_list("t", ["#FBF5F0", LORANGE, ORANGE, MAROON])
Q = [f"{y}Q{q}" for y in range(2021, 2027) for q in range(1, 5) if "2021Q4" <= f"{y}Q{q}" <= "2026Q2"]
MAC = [("2021Q4", "2022Q3", "Repricing"), ("2022Q4", "2023Q2", "Disinflation"), ("2023Q3", "2024Q4", "AI soft landing"),
       ("2025Q1", "2025Q2", "Tariff shock"), ("2025Q3", "2025Q4", "Boom"), ("2026Q1", "2026Q2", "Energy shock")]
reg = [next(i for i, (a, b, _) in enumerate(MAC) if a <= q <= b) for q in Q]
starts = [i for i in range(len(Q)) if i == 0 or reg[i] != reg[i - 1]] + [len(Q)]


def table(rows, header, path, col_w, fs=17, row_h=0.62, highlight_col=None, first_bold=True):
    W = sum(col_w); H = row_h * (len(rows) + 1)
    fig, ax = plt.subplots(figsize=(W, H)); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
    x = 0
    for j, h in enumerate(header):
        ax.add_patch(plt.Rectangle((x, H - row_h), col_w[j], row_h, color=MAROON, lw=0))
        ax.text(x + 0.15, H - row_h / 2, h, va="center", ha="left", color="white", fontsize=fs, fontweight="bold")
        x += col_w[j]
    for i, r in enumerate(rows):
        y = H - row_h * (i + 2); x = 0
        ax.add_patch(plt.Rectangle((0, y), W, row_h, color="#EFE3DA" if i % 2 == 0 else BG, lw=0))
        for j, v in enumerate(r):
            bold = (j == 0 and first_bold) or (highlight_col is not None and j == highlight_col)
            ax.text(x + 0.15, y + row_h / 2, v, va="center", ha="left", fontsize=fs, fontweight="bold" if bold else "normal",
                    color=ORANGE if (highlight_col is not None and j == highlight_col) else MAROON)
            x += col_w[j]
    fig.savefig(path, dpi=150, bbox_inches="tight", pad_inches=0.05); plt.close(fig)


# F1 required metrics
table([["Nodes / edges", "1,000 / 10,134", "1,000 / 10,327"],
       ["Components (isolated stocks)", "54 (47)", "17 (14)"],
       ["Largest connected component", "934 stocks", "982 stocks"],
       ["Diameter / radius (LCC, hops)", "14 / 7", "8 / 5"],
       ["Average shortest path", "3.58", "3.10"],
       ["Louvain groups / modularity", "16 / 0.62", "12 / 0.58"],
       ["Most central (eigenvector)", "Blue chips: Merck, P&G, Coca-Cola", "Canadian tribe: Fortis, TD, BCE"],
       ["Bridges between groups", "Newmont, insurers", "T-Mobile, Cheniere, NXP"]],
      ["2026Q2", "Ownership graph", "Conviction graph"], OUT / "f1_metrics.png", [6.2, 5.6, 5.6], fs=16)

# F2 regime heatmap (ownership)
S = pd.read_csv(R / "calendar_similarity_matrix.csv", index_col=0).loc[Q, Q].values
fig, ax = plt.subplots(figsize=(8, 7))
im = ax.imshow(S, cmap=CMAP, vmin=0, vmax=1)
ax.set_xticks(range(len(Q)), Q, rotation=90, fontsize=9); ax.set_yticks(range(len(Q)), Q, fontsize=9)
for k in range(len(starts) - 1):
    a, e = starts[k] - 0.5, starts[k + 1] - 0.5
    ax.add_patch(plt.Rectangle((a, a), e - a, e - a, fill=False, ec=MAROON, lw=2.2))
for s in ax.spines.values(): s.set_visible(False)
cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03); cb.outline.set_visible(False)
cb.set_label("Group similarity between two quarters (ARI)", fontsize=11)
ax.set_title("Squares = the 6 macro regimes", loc="left", fontsize=13)
fig.savefig(OUT / "f2_regime_heatmap.png", dpi=150, bbox_inches="tight"); plt.close(fig)

# F3 fund example
table([["Nvidia", "40%", "5%"], ["Micron", "30%", "10%"], ["Amazon", "25%", "25%"], ["Exxon", "5%", "60%"],
       ["Ownership graph sees", "holds 4 stocks", "holds 4 stocks → no change"],
       ["Conviction graph sees", "bet on tech", "bet moved to Exxon → new group"]],
      ["One fund", "Quarter 1", "Quarter 2"], OUT / "f3_fund_example.png", [4.6, 3.6, 5.6], fs=18, row_h=0.7)

# F4 ownership vs conviction: heatmaps + drift
C = pd.read_csv(R / "conviction" / "conviction_similarity_t2.0.csv", index_col=0).loc[Q, Q].values
fig = plt.figure(figsize=(18, 6.2))
gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.15], wspace=0.25)
for k, (M, t) in enumerate(((S, "Ownership groups (who holds what)"), (C, "Bet groups (who bets on what)"))):
    ax = fig.add_subplot(gs[k]); ax.imshow(M, cmap=CMAP, vmin=0, vmax=1)
    ax.set_xticks([]); ax.set_yticks(range(0, len(Q), 3), Q[::3], fontsize=9)
    for j in range(len(starts) - 1):
        a, e = starts[j] - 0.5, starts[j + 1] - 0.5
        ax.add_patch(plt.Rectangle((a, a), e - a, e - a, fill=False, ec=MAROON, lw=1.6))
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_title(t, loc="left", fontsize=13, fontweight="bold")
ax = fig.add_subplot(gs[2]); n = len(Q)
for M, lab, col in ((S, "Ownership", MAROON), (C, "Bets (conviction)", ORANGE)):
    ax.plot(range(1, n), [np.mean([M[i, i + d] for i in range(n - d)]) for d in range(1, n)], color=col, lw=3, marker="o", ms=5, label=lab)
ax.set_ylim(0, 1); ax.set_xlabel("Quarters apart", fontsize=12); ax.set_ylabel("Group similarity (ARI)", fontsize=12)
ax.set_title("Bet groups move faster", loc="left", fontsize=13, fontweight="bold"); ax.legend(frameon=False, fontsize=12)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.savefig(OUT / "f4_ownership_vs_conviction.png", dpi=150, bbox_inches="tight"); plt.close(fig)

# F5 tribes table
table([["Canadian home bias", "TD, RBC, BMO, BCE, Fortis", "Canadian banks' asset managers", "stable (0.60)"],
       ["Rate-sensitive income", "Apartment REITs + utilities", "Pension funds, insurers", "merged (0.46)"],
       ["Blue-chip dividend", "PepsiCo, Verizon, P&G, J&J", "Trust co. & wealth managers", "grew (0.38)"],
       ["International ADRs", "2022 China tech → 2026 EU/JP banks", "Global quant & wealth", "rotated (0.40)"],
       ["Merger arbitrage", "2022 Activision, VMware, Twitter → 2026 WBD, EA", "Gabelli, Pentwater, Prelude", "same funds, new deals"],
       ["2021 growth casualties", "RingCentral, Teladoc, Zscaler, Snap", "Citadel, Two Sigma", "dissolved"],
       ["AI hardware + biotech", "Viavi, Semtech, FormFactor, Micron, AMD", "Millennium, Jump, Algert", "NEW in 2026"],
       ["Midstream + private markets", "Energy Transfer, Williams, KKR, Apollo", "Tortoise, Infrastructure Cap.", "NEW in 2026"]],
      ["Tribe", "Key stocks", "Who bets", "2022 → 2026"], OUT / "f5_tribes.png", [5.3, 8.3, 5.4, 4.0], fs=15, highlight_col=3)

# F6 co-movement
T = pd.read_csv(R / "comovement" / "comovement_by_period.csv")
fig = plt.figure(figsize=(18, 6)); gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.7], wspace=0.25)
ax = fig.add_subplot(gs[0])
labs = ["Sectors FF48", "Sectors FF12", "Bet tribes", "Ownership groups", "Size"]
vals = [T.excess_ff48.mean(), T.excess_ff12.mean(), T.excess_tribes.mean(), T.excess_ownership.mean(), T.excess_size.mean()]
cols = [BEIGE, GREY, ORANGE, MAROON, BEIGE]
ax.barh(labs[::-1], np.array(vals[::-1]) * 100, color=cols[::-1], height=0.6)
for i, v in enumerate(vals[::-1]): ax.text(v * 100 + 0.2, i, f"{v*100:.1f}%", va="center", fontsize=13, fontweight="bold")
ax.set_xlabel("Next-quarter returns explained, above random groupings (%)", fontsize=11)
ax.set_title("Average over 18 quarters", loc="left", fontsize=13, fontweight="bold")
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax = fig.add_subplot(gs[1]); xs = np.arange(len(T))
down = T.median_return < -0.03
for i in np.where(down)[0]: ax.axvspan(i - 0.5, i + 0.5, color=LORANGE, alpha=0.3, lw=0)
ax.bar(xs - 0.2, T.excess_tribes * 100, 0.4, color=ORANGE, label="Bet tribes")
ax.bar(xs + 0.2, T.excess_ff12 * 100, 0.4, color=GREY, label="Sectors (FF12)")
ax.set_xticks(xs, [p.split("->")[1] for p in T.period], rotation=90, fontsize=10)
ax.set_ylabel("% explained (above random)", fontsize=11)
ax.set_title("Quarter by quarter (shaded = market down quarters)", loc="left", fontsize=13, fontweight="bold")
ax.legend(frameon=False, fontsize=12)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.savefig(OUT / "f6_comovement.png", dpi=150, bbox_inches="tight"); plt.close(fig)
print("done")
