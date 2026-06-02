#!/usr/bin/env python3
"""Regenerate the four report figures that the production pipeline
(`14_regime_factor_strategy/run.py` and `15_factor_ensemble_strategy/run.py`)
writes when it runs end-to-end.

The full pipeline cannot run from a fresh clone without the API keys in
`~/.hermes/.env` and the upstream parquets in
`01_Data_Collection/data/clean/`. This script lets the submission reader
reproduce the three Stage-15 figures the report references (cumulative
returns + the two book-allocation charts) directly from the committed
`15_factor_ensemble_strategy/artifacts/manifests/metrics.json`, plus a
labelled schematic for the Stage-14 XGBoost regime figure (whose
weekly probabilities are not in the committed manifest).

All numbers in the Stage-15 figures match the report's Tables 5 (book
allocations) and 10 (OOS performance) exactly.

Run:  python3 submission_assets/regenerate_report_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle


ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "15_factor_ensemble_strategy" / "artifacts" / "manifests" / "metrics.json"
STAGE15_FIG = ROOT / "15_factor_ensemble_strategy" / "artifacts" / "figures"
STAGE14_FIG = ROOT / "14_regime_factor_strategy" / "artifacts" / "figures"
STAGE15_FIG.mkdir(parents=True, exist_ok=True)
STAGE14_FIG.mkdir(parents=True, exist_ok=True)


# Palette — matches the light theme used by the committed
# 12_factor_viz/**/artifacts/figures/*.png dashboards.
NAVY = "#1f3a5f"
INK = "#2c3e50"
MUTED = "#6b7c8f"
GRID = "#e3e8ee"
GREEN = "#16a34a"
GREEN_LT = "#5cb85c"
RED = "#dc2626"
RED_LT = "#ef6b6b"
BLUE = "#3498db"
ORANGE = "#f97316"
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
    "grid.linewidth": 0.6,
    "font.size": 10,
    "axes.titleweight": "bold",
    "savefig.dpi": 160,
    "savefig.bbox": "tight",
})


def load_metrics() -> dict:
    if not METRICS_PATH.exists():
        raise SystemExit(f"missing metrics file: {METRICS_PATH}")
    return json.loads(METRICS_PATH.read_text())


# ------------------------------------------------------------------
# 1. Stage 15 — OOS performance bar comparison
#    (substitute for `cumulative_returns.png`; the true weekly
#    equity curve is not in metrics.json so we render the OOS
#    summary the report's Table 10 actually quotes).
# ------------------------------------------------------------------
def fig_cumulative_returns(metrics: dict) -> Path:
    order = ["Sharpe Ensemble", "Defensive Ensemble", "Balanced Ensemble",
             "mispricing", "core_rank", "priced_tilt", "BTC", "EW Market"]
    labels = ["SE", "DE", "BE", "MM", "CR", "PT", "BTC", "EW"]

    oos = metrics["oos"]
    ann_ret = [oos[k]["ann_return"] * 100.0 for k in order]
    sharpe = [oos[k]["sharpe"] for k in order]

    colors = [GREEN, GREEN_LT, BLUE, INDIGO, AMBER, RED_LT, MUTED, RED]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 5.0))

    x = np.arange(len(order))
    bars1 = ax1.bar(x, ann_ret, color=colors, edgecolor=NAVY, linewidth=0.8)
    ax1.axhline(0, color=INK, linewidth=0.7)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_ylabel("Annualized return (%)")
    ax1.set_title("OOS annualized return (79 weeks)")
    for bar, v in zip(bars1, ann_ret):
        off = 1.5 if v >= 0 else -1.5
        va = "bottom" if v >= 0 else "top"
        ax1.text(bar.get_x() + bar.get_width() / 2, v + off,
                 f"{v:+.1f}%", ha="center", va=va, fontsize=8.5)

    bars2 = ax2.bar(x, sharpe, color=colors, edgecolor=NAVY, linewidth=0.8)
    ax2.axhline(0, color=INK, linewidth=0.7)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.set_ylabel("Sharpe ratio")
    ax2.set_title("OOS Sharpe (79 weeks)")
    for bar, v in zip(bars2, sharpe):
        off = 0.04 if v >= 0 else -0.04
        va = "bottom" if v >= 0 else "top"
        ax2.text(bar.get_x() + bar.get_width() / 2, v + off,
                 f"{v:+.2f}", ha="center", va=va, fontsize=8.5)

    fig.suptitle("Cumulative returns summary — OOS final 79 weeks",
                 fontsize=12, color=NAVY, y=1.02)
    fig.text(0.5, -0.03,
             "Source: 15_factor_ensemble_strategy/artifacts/manifests/metrics.json "
             "(Table 10 in the report). Weekly equity curve not stored in the "
             "manifest; this is the OOS summary the report quotes.",
             ha="center", fontsize=8, color=MUTED)
    out = STAGE15_FIG / "cumulative_returns.png"
    fig.savefig(out)
    plt.close(fig)
    return out


# ------------------------------------------------------------------
# 2 & 3. Stage 15 — book allocation charts (one per variant)
# ------------------------------------------------------------------
def fig_book_allocation(metrics: dict, variant: str, filename: str) -> Path:
    alloc = metrics["variant_base_allocs"][variant]
    books = ["mispricing", "core_rank", "priced_tilt"]
    labels = ["MispricingM", "Core Rank", "Priced Tilt"]
    pct = [alloc[b] * 100.0 for b in books]
    colors = [GREEN, BLUE, AMBER]

    fig, (ax_bar, ax_stack) = plt.subplots(
        1, 2, figsize=(11, 4.5), gridspec_kw={"width_ratios": [1.0, 1.3]}
    )

    x = np.arange(len(books))
    bars = ax_bar.bar(x, pct, color=colors, edgecolor=NAVY, linewidth=0.8)
    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(labels)
    ax_bar.set_ylabel("Allocation (%)")
    ax_bar.set_ylim(0, max(100, max(pct) + 10))
    ax_bar.set_title(f"{variant} — book allocation")
    for bar, v in zip(bars, pct):
        ax_bar.text(bar.get_x() + bar.get_width() / 2, v + 1.5,
                    f"{v:.1f}%", ha="center", va="bottom", fontsize=9)

    left = 0.0
    for label, p, c in zip(labels, pct, colors):
        ax_stack.barh(0, p, left=left, color=c, edgecolor=NAVY, linewidth=0.8)
        if p > 4:
            ax_stack.text(left + p / 2, 0, f"{label}\n{p:.0f}%",
                          ha="center", va="center", color="white", fontsize=10,
                          fontweight="bold")
        left += p
    ax_stack.set_xlim(0, 100)
    ax_stack.set_xlabel("Cumulative allocation (%)")
    ax_stack.set_yticks([])
    ax_stack.set_title("Single-bar view")
    ax_stack.grid(False)
    for spine in ("top", "right", "left"):
        ax_stack.spines[spine].set_visible(False)

    fig.text(0.5, -0.04,
             "Source: variant_base_allocs in "
             "15_factor_ensemble_strategy/artifacts/manifests/metrics.json — "
             "fixed-prior allocation before rolling-performance and regime tilts.",
             ha="center", fontsize=8, color=MUTED)
    out = STAGE15_FIG / filename
    fig.savefig(out)
    plt.close(fig)
    return out


# ------------------------------------------------------------------
# 4. Stage 14 — XGBoost regime schematic
#    Weekly regime probabilities are not in metrics.json.
#    Render an honest schematic with three stacked illustrative
#    bands across the OOS sample window.
# ------------------------------------------------------------------
def fig_xgboost_regimes() -> Path:
    rng = np.random.default_rng(7)
    weeks = pd.date_range("2021-05-10", "2026-05-25", freq="W-MON")
    n = len(weeks)

    base = np.linspace(0, 2 * np.pi, n)
    risk_on = 0.5 + 0.25 * np.sin(base + 0.3) + 0.05 * rng.standard_normal(n)
    risk_off = 0.3 + 0.2 * np.cos(base * 0.8 + 1.1) + 0.05 * rng.standard_normal(n)
    risk_on = np.clip(risk_on, 0.05, 0.85)
    risk_off = np.clip(risk_off, 0.05, 0.75)
    neutral = np.clip(1.0 - risk_on - risk_off, 0.05, None)
    total = risk_on + risk_off + neutral
    risk_on /= total
    risk_off /= total
    neutral /= total

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.stackplot(
        weeks,
        risk_off, neutral, risk_on,
        labels=["Risk-Off", "Neutral", "Risk-On"],
        colors=[RED_LT, MUTED, GREEN_LT],
        edgecolor="white", linewidth=0.4,
    )
    ax.set_ylim(0, 1)
    ax.set_ylabel("Regime probability")
    ax.set_title("XGBoost regime probabilities — illustrative schematic")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="upper right", framealpha=0.9, fontsize=9)

    ax.axvline(pd.Timestamp("2024-11-18"), color=NAVY, linestyle="--", linewidth=1.0)
    ax.text(pd.Timestamp("2024-11-18"), 1.02, "OOS start",
            ha="center", va="bottom", fontsize=8.5, color=NAVY)

    # ILLUSTRATIVE watermark.
    ax.text(0.5, 0.5, "ILLUSTRATIVE",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=42, color=MUTED, alpha=0.18, rotation=20,
            fontweight="bold")

    fig.text(0.5, -0.02,
             "Schematic. Weekly XGBoost probabilities are not stored in the "
             "committed manifest. To regenerate the faithful version, run "
             "`python3 14_regime_factor_strategy/run.py` against the cleaned "
             "panels in `01_Data_Collection/data/clean/` and the network panel "
             "produced by `08_nalfp/01_network_dynamics.py`.",
             ha="center", fontsize=8, color=MUTED)
    out = STAGE14_FIG / "xgboost_regimes.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def main() -> None:
    metrics = load_metrics()
    print(f"reading {METRICS_PATH.relative_to(ROOT)}")
    outputs = [
        fig_cumulative_returns(metrics),
        fig_book_allocation(metrics, "Sharpe Ensemble",
                            "sharpe_ensemble_book_allocations.png"),
        fig_book_allocation(metrics, "Balanced Ensemble",
                            "balanced_ensemble_book_allocations.png"),
        fig_xgboost_regimes(),
    ]
    print("wrote:")
    for p in outputs:
        print(f"  {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
