#!/usr/bin/env python3
"""Generate presentation charts for the Artemis Track 1 deck.

All numbers are read from Stage 15 `metrics.json` (full/IS/OOS, ablation
baselines, sensitivity grid) plus the IS/OOS values quoted in the research
report. Nothing here is fabricated; this script only *renders* existing
results. Light theme to match the committed factor dashboards.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
METRICS = ROOT / "15_factor_ensemble_strategy" / "artifacts" / "manifests" / "metrics.json"
OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

m = json.load(open(METRICS))

# ---- palette (matches the light plotly-style committed figures) -------------
NAVY = "#1f3a5f"
INK = "#2c3e50"
MUTED = "#6b7c8f"
GRID = "#e3e8ee"
GREEN = "#16a34a"       # strategy / ensembles
GREEN_LT = "#5cb85c"    # secondary strategy (MispricingM)
RED = "#dc2626"         # benchmarks (BTC / EW)
RED_LT = "#ef6b6b"
BLUE = "#3498db"        # in-sample (echoes dashboards)
ORANGE = "#f97316"      # out-of-sample
AMBER = "#d29922"
INDIGO = "#4f46e5"

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK,
    "axes.titlecolor": NAVY,
    "text.color": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 1.0,
    "font.size": 13,
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 160,
})


def _bar_labels(ax, bars, fmt="{:+.2f}", dy=0.0, fs=12):
    for b in bars:
        h = b.get_height()
        va = "bottom" if h >= 0 else "top"
        ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, h + dy),
                    ha="center", va=va, fontsize=fs, fontweight="bold",
                    color=INK)


# =============================================================================
# 1. HERO — OOS Sharpe & OOS annual return: ensembles vs benchmarks
# =============================================================================
def hero_oos():
    oos = m["oos"]
    order = ["Sharpe Ensemble", "Defensive Ensemble", "Balanced Ensemble",
             "mispricing", "BTC", "EW Market"]
    labels = ["Sharpe\nEnsemble", "Defensive\nEnsemble", "Balanced\nEnsemble",
              "MispricingM\n(alone)", "Bitcoin", "Equal-wt\nMarket"]
    colors = [GREEN, GREEN, GREEN, GREEN_LT, RED, RED]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 5.4))

    sharpes = [oos[k]["sharpe"] for k in order]
    b1 = ax1.bar(labels, sharpes, color=colors, width=0.66, zorder=3)
    ax1.axhline(0, color=INK, lw=1.2, zorder=4)
    ax1.set_title("Out-of-sample Sharpe ratio", fontsize=15, fontweight="bold", pad=12)
    _bar_labels(ax1, b1, "{:+.2f}", dy=0.02 if max(sharpes) > 0 else 0)
    ax1.set_ylim(min(sharpes) - 0.25, max(sharpes) + 0.28)
    ax1.grid(axis="x", visible=False)

    rets = [oos[k]["ann_return"] * 100 for k in order]
    b2 = ax2.bar(labels, rets, color=colors, width=0.66, zorder=3)
    ax2.axhline(0, color=INK, lw=1.2, zorder=4)
    ax2.set_title("Out-of-sample annualised return", fontsize=15, fontweight="bold", pad=12)
    _bar_labels(ax2, b2, "{:+.0f}%", dy=1.0 if max(rets) > 0 else 0)
    ax2.set_ylim(min(rets) - 9, max(rets) + 9)
    ax2.grid(axis="x", visible=False)

    fig.suptitle("79-week out-of-sample window (bull → bear): the ensembles stay positive while the market falls",
                 fontsize=13.5, color=MUTED, y=0.99)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT / "hero_oos.png", bbox_inches="tight")
    plt.close(fig)


# =============================================================================
# 2. IS -> OOS Sharpe decay slope chart
# =============================================================================
def decay():
    # Key narrative lines only (the 3 ensembles cluster tightly, so we plot the
    # Sharpe Ensemble as their representative and note the full band).
    # NN optimiser values from report Appendix B (2.06 -> -0.46).
    # (name, IS, OOS, color, linewidth, right-label-y-offset px, left-label-y-offset px)
    series = [
        ("Sharpe Ensemble", m["is"]["Sharpe Ensemble"]["sharpe"], m["oos"]["Sharpe Ensemble"]["sharpe"], GREEN, 3.2, 8, 0),
        ("MispricingM", m["is"]["mispricing"]["sharpe"], m["oos"]["mispricing"]["sharpe"], GREEN_LT, 2.2, -10, -16),
        ("Neural-net optimiser", 2.06, -0.46, "#9333ea", 2.6, 2, 0),
        ("Bitcoin", m["is"]["BTC"]["sharpe"], m["oos"]["BTC"]["sharpe"], RED, 2.6, 16, 2),
        ("Equal-wt market", m["is"]["EW Market"]["sharpe"], m["oos"]["EW Market"]["sharpe"], RED_LT, 2.0, -16, -16),
    ]
    fig, ax = plt.subplots(figsize=(11.8, 6.4))
    for name, a, b, c, lw, rdy, ldy in series:
        ax.plot([0, 1], [a, b], color=c, lw=lw, alpha=0.95, zorder=3,
                marker="o", markersize=8)
        ax.annotate(f"{name}  {b:+.2f}", (1, b), xytext=(12, rdy),
                    textcoords="offset points", va="center", fontsize=12,
                    color=c, fontweight="bold")
        ax.annotate(f"{a:+.2f}", (0, a), xytext=(-12, ldy),
                    textcoords="offset points", va="center", ha="right",
                    fontsize=11, color=MUTED)
    ax.axhline(0, color=INK, lw=1.1, ls="--", alpha=0.6, zorder=2)
    # band note for the three ensembles
    ax.annotate("All 3 ensembles land\n+0.68 to +0.85",
                (1, 0.76), xytext=(12, 34), textcoords="offset points",
                fontsize=10, color=GREEN, va="center",
                bbox=dict(boxstyle="round,pad=0.3", fc="#eafaf0", ec=GREEN, lw=1))
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["In-sample\n(2021–2024, bull)", "Out-of-sample\n(2024–2026, bull→bear)"], fontsize=12.5)
    ax.set_xlim(-0.3, 1.62)
    ax.set_ylim(-0.75, 2.25)
    ax.set_ylabel("Sharpe ratio", fontsize=13)
    ax.set_title("Sharpe decay from in-sample to out-of-sample", fontsize=16, fontweight="bold", pad=14)
    ax.grid(axis="x", visible=False)
    ax.annotate("Disciplined ensembles decay ~38% but stay positive; the complex ML optimiser and the market collapse through zero.",
                (0.0, -0.13), xycoords="axes fraction", fontsize=11, color=MUTED, va="top")
    fig.tight_layout()
    fig.savefig(OUT / "decay.png", bbox_inches="tight")
    plt.close(fig)


# =============================================================================
# 3. Factor-discovery funnel: 182 -> 102 -> 4
# =============================================================================
def funnel():
    stages = [
        ("182 candidate specs\n(91 features × 2 directions)", 182, "#cbd5e1"),
        ("102 clear naive |t| ≥ 2.0\n(56% — a data-mining red flag)", 102, ORANGE),
        ("4 survive Bonferroni (|t|>3.64)\n+ Benjamini-Hochberg (q<0.001)", 4, GREEN),
    ]
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    ymax = 182
    for i, (label, val, color) in enumerate(stages):
        y = len(stages) - 1 - i
        width = val / ymax
        left = (1 - width) / 2
        ax.barh(y, width, left=left, height=0.40, color=color, zorder=3,
                edgecolor="white", linewidth=1.5)
        # descriptive label centred above the bar
        ax.text(0.5, y + 0.30, label, ha="center", va="bottom",
                fontsize=12.5, color=INK, fontweight="bold", zorder=4)
        # big count: inside wide bars, to the right of narrow ones
        cnt_color = color if color != "#cbd5e1" else MUTED
        if width > 0.12:
            ax.text(0.5, y - 0.02, f"{val}", ha="center", va="center",
                    fontsize=17, fontweight="bold", zorder=5,
                    color="white" if color == GREEN else INK)
        else:
            ax.text(left + width + 0.02, y, f"{val}", ha="left", va="center",
                    fontsize=17, fontweight="bold", color=cnt_color)
    ax.set_xlim(0, 1.05)
    ax.set_ylim(-0.7, len(stages) - 0.2)
    ax.axis("off")
    ax.set_title("Guarding against data-mining: 182 → 4 behavioural factors",
                 fontsize=16, fontweight="bold", pad=14, color=NAVY)
    ax.annotate("Only the 4 survivors (CRASH8, BETA26, SKEW52, NEWC) enter the strategy — and only as a small capped sleeve.",
                (0.5, -0.62), xycoords=("axes fraction", "data"), ha="center",
                fontsize=11, color=MUTED)
    fig.tight_layout()
    fig.savefig(OUT / "funnel.png", bbox_inches="tight")
    plt.close(fig)


# =============================================================================
# 4. Ablation: OOS Sharpe across Sharpe-Ensemble variants (robustness band)
# =============================================================================
def ablation():
    bo = m["baselines_oos"]
    headline = m["oos"]["Sharpe Ensemble"]["sharpe"]
    rows = [
        ("No Regime Tilt", bo["SE No Regime Tilt"]["sharpe"], MUTED),
        ("Headline\n(as presented)", headline, GREEN),
        ("MispricingM Only", bo["MispricingM Only"]["sharpe"], GREEN_LT),
        ("Priced-Tilt 5% cap", bo["SE Priced-Tilt 5% cap"]["sharpe"], BLUE),
        ("Priced-Tilt OFF", bo["SE Priced-Tilt Off"]["sharpe"], INDIGO),
    ]
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    colors = [r[2] for r in rows]
    fig, ax = plt.subplots(figsize=(11.2, 5.4))
    # robustness band
    ax.axhspan(0.80, 0.91, color=GREEN, alpha=0.08, zorder=0)
    ax.axhline(0.80, color=GREEN, lw=1, ls=":", alpha=0.5)
    ax.axhline(0.91, color=GREEN, lw=1, ls=":", alpha=0.5)
    bars = ax.bar(labels, vals, color=colors, width=0.6, zorder=3)
    _bar_labels(ax, bars, "{:+.2f}", dy=0.006)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Out-of-sample Sharpe", fontsize=13)
    ax.set_title("Ablations: OOS Sharpe stays in a tight +0.80 to +0.91 band",
                 fontsize=15.5, fontweight="bold", pad=12)
    ax.grid(axis="x", visible=False)
    ax.annotate("Removing the priced-tilt sleeve *raises* Sharpe (+0.84 → +0.90);\nMispricingM alone ≈ the full ensemble — the edge is one composite signal.",
                (0.015, 0.97), xycoords="axes fraction", va="top", fontsize=10.5, color=MUTED)
    fig.tight_layout()
    fig.savefig(OUT / "ablation.png", bbox_inches="tight")
    plt.close(fig)


# =============================================================================
# 5. Book allocations (base/target) for the three variants
# =============================================================================
def allocations():
    va = m["variant_base_allocs"]
    variants = ["Sharpe Ensemble", "Defensive Ensemble", "Balanced Ensemble"]
    books = ["mispricing", "core_rank", "priced_tilt"]
    book_labels = ["MispricingM (alpha)", "Core Rank (backbone)", "Priced Tilt (capped sleeve)"]
    bcolors = [INDIGO, BLUE, AMBER]
    fig, ax = plt.subplots(figsize=(11.2, 4.6))
    left = [0, 0, 0]
    y = range(len(variants))
    for bi, book in enumerate(books):
        widths = [va[v][book] * 100 for v in variants]
        bars = ax.barh(y, widths, left=left, color=bcolors[bi], height=0.55,
                       zorder=3, edgecolor="white", linewidth=1.5,
                       label=book_labels[bi])
        for yi, (w, l) in enumerate(zip(widths, left)):
            if w >= 5:
                ax.text(l + w / 2, yi, f"{w:.0f}%", ha="center", va="center",
                        color="white", fontweight="bold", fontsize=12)
        left = [l + w for l, w in zip(left, widths)]
    ax.set_yticks(list(y))
    ax.set_yticklabels(variants, fontsize=12.5)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Base book allocation (%)", fontsize=12)
    ax.invert_yaxis()
    ax.set_title("Three books, three risk appetites", fontsize=15.5, fontweight="bold", pad=12)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.34), ncol=3, frameon=False, fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "allocations.png", bbox_inches="tight")
    plt.close(fig)


# =============================================================================
# 6. Sensitivity grid heatmap: regime_tilt x priced_cap -> OOS Sharpe
# =============================================================================
def sensitivity():
    grid = m["sharpe_ensemble_sensitivity"]
    caps = sorted({r["priced_cap"] for r in grid})
    tilts = ["on", "off"]
    import numpy as np
    Z = np.zeros((len(tilts), len(caps)))
    for r in grid:
        i = tilts.index(r["regime_tilt"])
        j = caps.index(r["priced_cap"])
        Z[i, j] = r["oos_sharpe"]
    fig, ax = plt.subplots(figsize=(9.0, 4.0))
    im = ax.imshow(Z, cmap="Greens", vmin=0.78, vmax=0.92, aspect="auto")
    ax.set_xticks(range(len(caps)))
    ax.set_xticklabels([f"{int(c*100)}%" for c in caps], fontsize=12)
    ax.set_yticks(range(len(tilts)))
    ax.set_yticklabels(["Regime tilt ON", "Regime tilt OFF"], fontsize=12)
    ax.set_xlabel("Priced-tilt cap", fontsize=12)
    for i in range(len(tilts)):
        for j in range(len(caps)):
            ax.text(j, i, f"{Z[i,j]:.2f}", ha="center", va="center",
                    color="white" if Z[i, j] > 0.87 else INK, fontweight="bold", fontsize=13)
    ax.set_title("OOS Sharpe across the full prior grid: +0.80 to +0.91",
                 fontsize=14.5, fontweight="bold", pad=10)
    ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="OOS Sharpe")
    fig.tight_layout()
    fig.savefig(OUT / "sensitivity.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    hero_oos()
    decay()
    funnel()
    ablation()
    allocations()
    sensitivity()
    print("charts written to", OUT)
    for p in sorted(OUT.glob("*.png")):
        print(" -", p.name, p.stat().st_size, "bytes")
