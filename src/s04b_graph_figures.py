"""Step 4b: charts of the graph over time (reads results/graph_summary.csv). Output: figures/f9_graph_over_time.png"""
import matplotlib.pyplot as plt
import pandas as pd

from config import FIGURES, RESULTS

BLUE, ORANGE, MUTED, INK, SOFT, GRID = "#2a78d6", "#eb6834", "#b9b7ae", "#0b0b0b", "#52514e", "#e6e5df"
d = pd.read_csv(RESULTS / "graph_summary.csv")
x = range(len(d))
ticks = list(range(0, len(d), 3))

plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False, "axes.titlelocation": "left",
                     "axes.titleweight": "bold", "axes.titlesize": 10, "text.color": INK, "axes.labelcolor": SOFT, "xtick.color": SOFT,
                     "ytick.color": SOFT, "font.size": 9, "xtick.bottom": False, "ytick.left": False, "axes.grid": True,
                     "axes.grid.axis": "y", "grid.color": GRID, "axes.axisbelow": True})
fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))

ax = axes[0]
ax.plot(x, d["edges_k25"], color=MUTED, lw=1.5, label="each stock keeps top 25")
ax.plot(x, d["edges_k15"], color=BLUE, lw=2.4, label="top 15 (main)")
ax.plot(x, d["edges_k10"], color=MUTED, lw=1.5, ls="--", label="top 10")
ax.set_ylim(0, d["edges_k25"].max() * 1.15)
ax.set_title("Links in the graph")
ax.legend(frameon=False, loc="lower right", fontsize=8)

ax = axes[1]
ax.plot(x, d["largest_component"], color=BLUE, lw=2.4, label="stocks in the biggest connected group")
ax.plot(x, d["isolated"], color=ORANGE, lw=2.4, label="stocks with no link at all")
ax.set_ylim(0, 1000)
ax.set_title("How connected is it? (out of 1,000 stocks)")
ax.legend(frameon=False, loc="center right", fontsize=8)
for col, c in (("largest_component", BLUE), ("isolated", ORANGE)):
    ax.annotate(f"{d[col].iloc[-1]}", (len(d) - 1, d[col].iloc[-1]), xytext=(4, -3), textcoords="offset points", color=c, fontsize=9)

ax = axes[2]
ax.plot(x[1:], d["stock_overlap"].iloc[1:] * 100, color=MUTED, lw=2.0, label="same stocks as the quarter before")
ax.plot(x[1:], d["edge_jaccard_common_stocks"].iloc[1:] * 100, color=BLUE, lw=2.4, label="same links as the quarter before*")
ax.set_ylim(0, 100)
ax.set_title("How much stays the same? (%)")
ax.legend(frameon=False, loc="lower center", fontsize=8)
ax.text(0, -0.28, "* share of all distinct links that appear in both quarters, stocks present in both", transform=ax.transAxes, fontsize=7.5, color=SOFT)

for ax in axes:
    ax.set_xticks(ticks)
    ax.set_xticklabels([d["quarter"].iloc[i] for i in ticks], rotation=45, ha="right")
fig.suptitle("The main graph, quarter by quarter: size is steady, but about a third of the links change each quarter", x=0.01, ha="left", fontsize=11, fontweight="bold")
fig.tight_layout()
fig.savefig(FIGURES / "f9_graph_over_time.png", dpi=200, bbox_inches="tight")
print("saved")
