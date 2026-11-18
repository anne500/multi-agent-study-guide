"""Render the two observed V17 conversion runs as a standalone SVG."""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "data" / "v17-phase-timings.csv"
OUTPUT = ROOT / "docs" / "assets" / "v17-phase-timings.svg"


def main():
    with SOURCE.open(encoding="utf-8", newline="") as data:
        runs = list(csv.DictReader(data))

    labels = [f"{run['environment']}\n(n = {run['observed_runs']})" for run in runs]
    phases = [
        ("Ollama planning", "Seconds", "#7C3AED", [float(run["planning_ms"]) / 1000 for run in runs], 600),
        ("Specialist execution", "Milliseconds", "#0F766E", [float(run["specialist_ms"]) for run in runs], 8),
    ]

    with matplotlib.rc_context({
        "svg.fonttype": "none",
        "svg.hashsalt": "project1-v17-phase-timings",
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "text.color": "#0F172A",
        "axes.labelcolor": "#334155",
        "xtick.color": "#475569",
        "ytick.color": "#0F172A",
    }):
        fig, panels = plt.subplots(1, 2, figsize=(10.8, 3.25), sharey=True)
        fig.subplots_adjust(left=0.18, right=0.96, bottom=0.31, top=0.71, wspace=0.37)
        fig.text(0.07, 0.91, "V17 phase timings", fontsize=19, fontweight="bold")
        fig.text(0.07, 0.81, "Observed 5 km conversion on a Windows laptop", color="#475569")

        for ax, (title, units, color, values, limit) in zip(panels, phases):
            ax.barh(labels, values, color=color, height=0.45, zorder=2)
            ax.set_title(title, loc="left", color=color, fontweight="bold")
            ax.set_xlabel(units)
            ax.set_xlim(0, limit)
            ax.set_ylim(len(labels) - 0.45, -0.55)
            ax.grid(axis="x", color="#CBD5E1", linewidth=0.7)
            ax.tick_params(axis="y", length=0, pad=8)
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.spines["bottom"].set_color("#94A3B8")
            for row, value in enumerate(values):
                ax.text(value - limit * 0.025, row, f"{value:.3f}", color="white",
                        ha="right", va="center", fontweight="bold", fontsize=9)

        fig.text(0.07, 0.12, "One run per environment. Each plan included one retry. Human review time is excluded.",
                 color="#475569", fontsize=9)
        fig.text(0.07, 0.06, "Source: V17 verification log. The panels use separate scales.", color="#475569", fontsize=9)
        fig.savefig(OUTPUT, metadata={
            "Title": "V17 phase timings",
            "Description": "Two recorded conversion runs. The panels show planning in seconds and specialist execution "
                           "in milliseconds on separate scales. Each environment has one observation.",
            "Date": None,
        })
        plt.close(fig)


if __name__ == "__main__":
    main()
