#!/usr/bin/env python3
"""Generate all figures and summary tables for the PCA + CCA analysis.

Figures:
1. Universe composition over time (stacked area by sector)
2. Universe turnover (weekly entry/exit bar chart)
3. Supply growth distribution
4. Scree plot with Marchenko-Pastur threshold overlay
5. PC loading heatmaps (representative snapshots)
6. PC scores time series with market regime annotations
7. Characteristic correlation table
8. Cluster evolution (Sankey/alluvial)
9. CCA biplot (canonical weights)
10. CCA rolling canonical correlations
11. Canonical variate time series overlaid with macro events

Dependencies: All prior phases
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.data_io import (
    clean_dir,
    features_dir,
    figures_dir,
    get_logger,
    load_settings,
)

PROJ_ROOT = Path(__file__).resolve().parent.parent


def save_fig(fig: plt.Figure, name: str) -> None:
    out_dir = figures_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_universe_composition(universe_df: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    dates = summary_df["rebalance_date"].values
    ax.bar(dates, summary_df["n_assets"], label="Universe size", alpha=0.7)
    ax.set_xlabel("Week")
    ax.set_ylabel("Number of assets")
    ax.set_title("Universe Size Over Time")
    ax.legend()
    fig.autofmt_xdate()
    save_fig(fig, "01_universe_size")


def plot_universe_turnover(summary_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    dates = summary_df["rebalance_date"].values
    width = 0.4
    x = np.arange(len(dates))
    ax.bar(x - width / 2, summary_df["n_entries"], width, label="Entries", color="green", alpha=0.7)
    ax.bar(x + width / 2, summary_df["n_exits"], width, label="Exits", color="red", alpha=0.7)
    ax.set_xlabel("Week index")
    ax.set_ylabel("Count")
    ax.set_title("Weekly Universe Turnover")
    ax.legend()
    save_fig(fig, "02_universe_turnover")


def plot_supply_growth(universe_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    sg = universe_df["supply_growth_4w"].dropna()
    sg = sg[sg.abs() < 2.0]
    ax.hist(sg, bins=100, edgecolor="black", alpha=0.7)
    ax.axvline(x=0.10, color="red", linestyle="--", label="10% threshold")
    ax.set_xlabel("4-week supply growth")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of 4-Week Supply Growth in Universe")
    ax.legend()
    save_fig(fig, "03_supply_growth_distribution")


def plot_scree_with_mp(diagnostics_df: pd.DataFrame) -> None:
    dates = sorted(diagnostics_df["date"].unique())
    if len(dates) == 0:
        return

    sample_date = dates[len(dates) // 2]
    sample = diagnostics_df[diagnostics_df["date"] == sample_date].copy()

    fig, ax = plt.subplots(figsize=(10, 6))
    components = sample["component"].values[:20]
    eigenvalues = sample["eigenvalue"].values[:20]
    mp_thresholds = sample["mp_threshold"].values[:20]
    retained = sample["retained"].values[:20]

    colors = ["green" if r else "gray" for r in retained]
    ax.bar(components, eigenvalues, color=colors, alpha=0.7, label="Eigenvalues")
    ax.plot(components, mp_thresholds, "r--", label="MP 95th percentile", marker="o", markersize=3)
    ax.set_xlabel("Component")
    ax.set_ylabel("Eigenvalue")
    ax.set_title(f"Scree Plot with MP Threshold — Week {sample_date}")
    ax.legend()
    save_fig(fig, "04_scree_mp_threshold")


def plot_pc_scores_time_series(scores_df: pd.DataFrame) -> None:
    pc_cols = [c for c in scores_df.columns if c.startswith("PC")]
    figures_to_plot = min(3, len(pc_cols))

    fig, axes = plt.subplots(figures_to_plot, 1, figsize=(14, 4 * figures_to_plot), sharex=True)
    if figures_to_plot == 1:
        axes = [axes]

    for i, col in enumerate(pc_cols[:figures_to_plot]):
        ax = axes[i]
        ax.plot(scores_df["date"], scores_df[col], linewidth=0.8)
        ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
        ax.set_ylabel(col)
        ax.set_title(f"{col} Score Over Time")

    axes[-1].set_xlabel("Week")
    fig.suptitle("PCA Score Time Series", fontsize=14)
    fig.tight_layout()
    save_fig(fig, "06_pc_scores_timeseries")


def plot_char_correlations(corr_df: pd.DataFrame) -> None:
    if corr_df.empty:
        return

    avg_corr = corr_df.groupby(["pc", "characteristic"])["spearman_rho"].mean().reset_index()
    pivot = avg_corr.pivot(index="characteristic", columns="pc", values="spearman_rho")

    fig, ax = plt.subplots(figsize=(8, 6))
    pivot.plot(kind="bar", ax=ax, width=0.8)
    ax.set_xlabel("Characteristic")
    ax.set_ylabel("Average Spearman rho")
    ax.set_title("PC-Characteristic Correlations (Time-Averaged)")
    ax.legend(title="PC")
    fig.tight_layout()
    save_fig(fig, "07_char_correlations")


def plot_cluster_evolution(cluster_df: pd.DataFrame) -> None:
    if cluster_df.empty:
        return

    cluster_counts = cluster_df.groupby(["date", "cluster"]).size().reset_index(name="count")
    pivot = cluster_counts.pivot(index="date", columns="cluster", values="count").fillna(0)

    fig, ax = plt.subplots(figsize=(14, 6))
    pivot.plot.area(ax=ax, alpha=0.7)
    ax.set_xlabel("Week")
    ax.set_ylabel("Number of assets")
    ax.set_title("Cluster Composition Over Time")
    ax.legend(title="Cluster")
    save_fig(fig, "08_cluster_evolution")


def plot_cca_biplot(results_df: pd.DataFrame) -> None:
    components = results_df[results_df["component"].notna() & results_df["x_weight"].notna()]
    if components.empty:
        return

    n_comp = int(components["component"].max())

    fig, axes = plt.subplots(1, min(2, n_comp), figsize=(10, 5 * min(2, n_comp)))
    if min(2, n_comp) == 1:
        axes = [axes]

    for i, comp in enumerate(range(1, min(3, n_comp + 1))):
        ax = axes[i] if i < len(axes) else axes[0]
        x_vars = results_df[results_df["x_weight"].notna()]
        y_vars = results_df[results_df["y_weight"].notna()]

        comp_x = x_vars[x_vars["component"] == comp]
        comp_y = y_vars[y_vars["component"] == comp]

        for _, row in comp_x.iterrows():
            ax.arrow(0, 0, row["x_weight"], 0, head_width=0.02, head_length=0.02, fc="blue", ec="blue")
            ax.text(row["x_weight"], 0.05, row.get("variable", ""), fontsize=8, ha="center")

        for _, row in comp_y.iterrows():
            ax.arrow(0, 0, 0, row["y_weight"], head_width=0.02, head_length=0.02, fc="red", ec="red")
            ax.text(0.05, row["y_weight"], row.get("variable", ""), fontsize=8)

        ax.set_xlabel("X (Crypto PCs)")
        ax.set_ylabel("Y (Macro)")
        ax.set_title(f"CV{comp} Weights")
        ax.axhline(y=0, color="gray", linewidth=0.5)
        ax.axvline(x=0, color="gray", linewidth=0.5)

    fig.suptitle("CCA Biplot", fontsize=14)
    fig.tight_layout()
    save_fig(fig, "09_cca_biplot")


def plot_cca_rolling(rolling_df: pd.DataFrame) -> None:
    if rolling_df.empty:
        return

    corr_cols = [c for c in rolling_df.columns if c.endswith("_corr")]
    fig, ax = plt.subplots(figsize=(14, 6))
    for col in corr_cols:
        ax.plot(rolling_df["window_end"], rolling_df[col], label=col, linewidth=1.2)

    ax.set_xlabel("Week")
    ax.set_ylabel("Canonical Correlation")
    ax.set_title("Rolling CCA Canonical Correlations (52-week window)")
    ax.legend()
    ax.set_ylim(0, 1)
    fig.tight_layout()
    save_fig(fig, "10_cca_rolling_correlations")


def plot_canonical_variates(variates_df: pd.DataFrame) -> None:
    if variates_df.empty:
        return

    cv_cols = [c for c in variates_df.columns if c.startswith("CV")]
    x_cols = [c for c in cv_cols if "_x" in c]
    y_cols = [c for c in cv_cols if "_y" in c]

    n_pairs = min(len(x_cols), len(y_cols))
    if n_pairs == 0:
        return

    events = [
        ("2021-05-19", "China Crypto Ban"),
        ("2022-05-09", "Luna/UST Crash"),
        ("2022-11-11", "FTX Collapse"),
        ("2024-01-10", "BTC ETF Approval"),
    ]

    fig, axes = plt.subplots(n_pairs, 1, figsize=(14, 4 * n_pairs), sharex=True)
    if n_pairs == 1:
        axes = [axes]

    dates = pd.to_datetime(variates_df["date"])

    for i in range(n_pairs):
        ax = axes[i]
        ax.plot(dates, variates_df[x_cols[i]], label=x_cols[i], linewidth=0.8, color="blue")
        ax2 = ax.twinx()
        ax2.plot(dates, variates_df[y_cols[i]], label=y_cols[i], linewidth=0.8, color="red", alpha=0.7)

        for event_date, event_name in events:
            ed = pd.Timestamp(event_date)
            if dates.min() <= ed <= dates.max():
                ax.axvline(x=ed, color="gray", linestyle=":", linewidth=0.8)
                ax.text(ed, ax.get_ylim()[1], event_name, fontsize=6, rotation=45, ha="right")

        ax.set_ylabel(x_cols[i])
        ax2.set_ylabel(y_cols[i])

    axes[-1].set_xlabel("Week")
    fig.suptitle("Canonical Variates with Macro Events", fontsize=14)
    fig.tight_layout()
    save_fig(fig, "11_canonical_variate_timeseries")


def main() -> None:
    logger = get_logger("report")
    settings = load_settings()

    universe_path = clean_dir() / "universe_weekly.parquet"
    summary_path = clean_dir() / "universe_summary.parquet"
    diagnostics_path = features_dir() / "pca_diagnostics.parquet"
    scores_path = features_dir() / "pca_scores.parquet"
    corr_path = features_dir() / "pc_char_correlations.parquet"
    cluster_path = features_dir() / "pc_clusters.parquet"
    cca_results_path = features_dir() / "cca_results.parquet"
    cca_rolling_path = features_dir() / "cca_rolling.parquet"
    cca_variates_path = features_dir() / "cca_variates.parquet"

    if universe_path.exists():
        universe_df = pd.read_parquet(universe_path)
        summary_df = pd.read_parquet(summary_path)
        logger.info("Plotting universe composition...")
        plot_universe_composition(universe_df, summary_df)
        logger.info("Plotting universe turnover...")
        plot_universe_turnover(summary_df)
        logger.info("Plotting supply growth distribution...")
        plot_supply_growth(universe_df)

    if diagnostics_path.exists():
        diagnostics_df = pd.read_parquet(diagnostics_path)
        logger.info("Plotting scree plot...")
        plot_scree_with_mp(diagnostics_df)

    if scores_path.exists():
        scores_df = pd.read_parquet(scores_path)
        logger.info("Plotting PC scores time series...")
        plot_pc_scores_time_series(scores_df)

    if corr_path.exists():
        corr_df = pd.read_parquet(corr_path)
        logger.info("Plotting characteristic correlations...")
        plot_char_correlations(corr_df)

    if cluster_path.exists():
        cluster_df = pd.read_parquet(cluster_path)
        logger.info("Plotting cluster evolution...")
        plot_cluster_evolution(cluster_df)

    if cca_results_path.exists():
        cca_results_df = pd.read_parquet(cca_results_path)
        logger.info("Plotting CCA biplot...")
        plot_cca_biplot(cca_results_df)

    if cca_rolling_path.exists():
        cca_rolling_df = pd.read_parquet(cca_rolling_path)
        logger.info("Plotting rolling CCA correlations...")
        plot_cca_rolling(cca_rolling_df)

    if cca_variates_path.exists():
        cca_variates_df = pd.read_parquet(cca_variates_path)
        logger.info("Plotting canonical variate time series...")
        plot_canonical_variates(cca_variates_df)

    logger.info("Report generation complete. Figures saved to %s", figures_dir())


if __name__ == "__main__":
    main()