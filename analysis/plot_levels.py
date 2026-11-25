"""Figure for the extended design study. Needs matplotlib. Run after levels_design.py:
    python analysis/plot_levels.py
Writes figures/levels_design_curve.png (standalone, with title) and figures/levels_design_curve_note.png
(sized for page 3 of the research note, with the title and caption left to the page) from
tables/levels_simulation.csv."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = {"pooled": ("Pooled cutoff", "#2a78d6"), "local": ("Local tasks only", "#eb6834"),
          "hierarchical": ("Hierarchical", "#1baf7a"), "oracle": ("Perfect knowledge", MUTED)}
PANELS = [("tie_only", "Old rule: flag 8.0 and above, plus a share of 7.5s"),
          ("levels", "New rule: randomised threshold across 7.0, 7.5 and 8.0")]


def main():
    s = pd.read_csv(ROOT / "tables" / "levels_simulation.csv")
    s = s[(s.levels == "7.0-8.0") & (s.scenario == "fitted") & (s.test_tasks != 100)]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": AXIS,
                         "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.9), sharey=True, facecolor=SURFACE)
    fig.subplots_adjust(left=0.07, right=0.84, top=0.76, bottom=0.17, wspace=0.08)
    for ax, (rule, title) in zip(axes, PANELS):
        ax.set_facecolor(SURFACE)
        ax.axvspan(5, 10, color="#f0efec", zorder=0, lw=0)
        ax.text(7.1, 6.85, "5-10 tasks", ha="center", va="top", fontsize=8.5, color=MUTED)
        d = s[s.rule == rule]
        for method, (label, color) in SERIES.items():
            g = d[d.method == method].sort_values("calibration_tasks")
            ax.plot(g.calibration_tasks, g.true_budget_mae, color=color, lw=2, solid_capstyle="round",
                    solid_joinstyle="round", marker="o", ms=8, mfc=color, mec=SURFACE, mew=2, zorder=3,
                    label=label)
        ax.set_xscale("log")
        ax.set_xticks([1, 2, 5, 10, 20, 40, 80, 160])
        ax.set_xticklabels(["1", "2", "5", "10", "20", "40", "80", "160"])
        ax.minorticks_off()
        ax.set_ylim(0, 7)
        ax.set_xlim(0.85, 190)
        ax.grid(axis="y", color=GRID, lw=1)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(length=0)
        ax.set_title(title, loc="left", fontsize=10.5, color=INK, pad=10)
        ax.set_xlabel("Local calibration tasks in the new environment")
    axes[0].set_ylabel("Distance from budget (alerts per 1,000)")
    # Direct labels on the right panel, with leader lines where the line ends sit close together.
    ax = axes[1]
    end = s[(s.rule == "levels") & (s.calibration_tasks == 160)].set_index("method").true_budget_mae
    placed = {"pooled": end["pooled"], "local": end["local"] + 0.45, "hierarchical": end["hierarchical"] - 0.25,
              "oracle": end["oracle"] - 0.2}
    for method, y_text in placed.items():
        ax.annotate(f"{SERIES[method][0]} {end[method]:.1f}", xy=(160, end[method]), xycoords="data",
                    xytext=(215, y_text), textcoords="data", annotation_clip=False, va="center", fontsize=9.5,
                    color=INK, arrowprops=dict(arrowstyle="-", color=AXIS, lw=1, shrinkA=0, shrinkB=6))
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=c, lw=2, marker="o", ms=7, mfc=c, mec=c) for _, c in SERIES.values()]
    labels = [lab for lab, _ in SERIES.values()]
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.07, 0.885), ncol=4, frameon=False,
               fontsize=9.5, handlelength=2.2, columnspacing=1.8, labelcolor=INK)
    fig.text(0.07, 0.965, "A wider rule only pays off with more local tasks", fontsize=14, color=INK,
             weight="bold", va="top")
    fig.text(0.07, 0.915, "Mean distance from 10 alerts per 1,000 in new simulated environments  ·  fitted model  ·  "
             "500 studies of 10 environments", fontsize=9.5, color=INK2, va="top")
    fig.text(0.07, 0.035, "Perfect knowledge knows each environment's true rates and shows the floor each rule allows. "
             "Values are in tables/levels_simulation.csv.", fontsize=8.5, color=MUTED)
    out = ROOT / "figures"
    out.mkdir(exist_ok=True)
    fig.savefig(out / "levels_design_curve.png", dpi=200, facecolor=SURFACE)
    plt.close(fig)
    note_figure(s, out)


def note_figure(s, out):
    """Compact version at the note's text width (497.3 pt), drawn at final size so type prints at 7-8 pt."""
    from matplotlib.lines import Line2D
    page = "#ffffff"
    plt.rcParams.update({"font.size": 7.5})
    fig, axes = plt.subplots(1, 2, figsize=(497.3 / 72, 164 / 72), sharey=True, facecolor=page)
    fig.subplots_adjust(left=0.075, right=0.80, top=0.78, bottom=0.225, wspace=0.08)
    for ax, (rule, title) in zip(axes, PANELS):
        ax.set_facecolor(page)
        ax.axvspan(5, 10, color="#f0efec", zorder=0, lw=0)
        ax.text(7.1, 6.9, "5-10 tasks", ha="center", va="top", fontsize=6.5, color=MUTED)
        d = s[s.rule == rule]
        for method, (label, color) in SERIES.items():
            g = d[d.method == method].sort_values("calibration_tasks")
            ax.plot(g.calibration_tasks, g.true_budget_mae, color=color, lw=1.5, solid_capstyle="round",
                    solid_joinstyle="round", marker="o", ms=4.5, mfc=color, mec=page, mew=1, zorder=3)
        ax.set_xscale("log")
        ax.set_xticks([1, 2, 5, 10, 20, 40, 80, 160])
        ax.set_xticklabels(["1", "2", "5", "10", "20", "40", "80", "160"], fontsize=7)
        ax.minorticks_off()
        ax.set_ylim(0, 7)
        ax.set_yticks(range(8))
        ax.tick_params(axis="y", labelsize=7)
        ax.set_xlim(0.85, 190)
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_linewidth(0.6)
        ax.tick_params(length=0, pad=3)
        ax.set_title({"tie_only": "Old rule: 8.0 and up, plus some 7.5s",
                      "levels": "New rule: randomised over 7.0 to 8.0"}[rule], loc="left",
                     fontsize=7.8, color=INK, pad=5)
    axes[0].set_ylabel("Alerts per 1,000 from budget", fontsize=7.3)
    fig.text(0.4375, 0.05, "Local calibration tasks in the new environment", ha="center", fontsize=7.3, color=INK2)
    ax = axes[1]
    end = s[(s.rule == "levels") & (s.calibration_tasks == 160)].set_index("method").true_budget_mae
    placed = {"pooled": end["pooled"], "local": end["local"] + 0.55, "hierarchical": end["hierarchical"] - 0.35,
              "oracle": end["oracle"] - 0.15}
    for method, y_text in placed.items():
        ax.annotate(f"{SERIES[method][0]} {end[method]:.1f}", xy=(160, end[method]), xytext=(225, y_text),
                    annotation_clip=False, va="center", fontsize=6.6, color=INK,
                    arrowprops=dict(arrowstyle="-", color=AXIS, lw=0.6, shrinkA=0, shrinkB=3))
    handles = [Line2D([], [], color=c, lw=1.5, marker="o", ms=4, mfc=c, mec=c) for _, c in SERIES.values()]
    fig.legend(handles, [lab for lab, _ in SERIES.values()], loc="upper left", bbox_to_anchor=(0.065, 1.0),
               ncol=4, frameon=False, fontsize=7.3, handlelength=1.8, columnspacing=1.4, labelcolor=INK)
    fig.savefig(out / "levels_design_curve_note.png", dpi=300, facecolor=page)
    plt.close(fig)


if __name__ == "__main__":
    main()
