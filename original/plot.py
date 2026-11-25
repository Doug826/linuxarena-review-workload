"""Render the primary figure from threshold_transfer.csv (requires matplotlib)."""
import csv
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results")
with (folder / "threshold_transfer.csv").open() as f:
    rows = sorted(csv.DictReader(f), key=lambda r: float(r["alerts_per_1000"]), reverse=True)
fig, ax = plt.subplots(figsize=(8.5, 5.4))
fig.subplots_adjust(left=.22, right=.95, top=.80, bottom=.19)
fig.text(.035, .94, "The same cutoff produces different review workloads", fontsize=17, weight="bold")
fig.text(.035, .875, "Held-out honest actions  ·  20 tasks per environment  ·  GPT-5 Nano monitoring Opus", fontsize=10)
ax.axvline(10, lw=1.4, color="#bc502f", linestyle="--")
ax.text(10.3, 9.3, "1% budget", color="#a54027", fontsize=9)
for i, r in enumerate(rows):
    x = float(r["alerts_per_1000"])
    if r["ci_high_per_1000"]:
        lo, hi = float(r["ci_low_per_1000"]), float(r["ci_high_per_1000"])
        ax.plot([lo, hi], [i, i], color="#98a6b6", lw=2.4, solid_capstyle="round")
    ax.scatter(x, i, s=49, color="#123e57", zorder=3, clip_on=False)
ax.set_yticks(range(len(rows)), [r["environment"].replace("_"," ").title() for r in rows])
ax.invert_yaxis()
ax.set_xlim(-.35,33)
ax.set_xlabel("False alerts per 1,000 scored honest actions", fontsize=11)
ax.spines[["top", "right", "left"]].set_visible(False)
ax.tick_params(axis="y", length=0, pad=8)
ax.grid(axis="x", alpha=.15)
fig.text(.035, .044, "Bars show pointwise 95% task-bootstrap intervals at the fitted cutoff. Web Scraping had no alerts,\nso this bootstrap cannot estimate its upper uncertainty bound.", fontsize=9, color="#394654")
fig.savefig(folder / "false_alerts.png", dpi=165)
