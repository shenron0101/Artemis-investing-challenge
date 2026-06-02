#!/usr/bin/env python3
"""Master reproduction script for the Artemis systematic crypto factor strategy.

Runs the full six-stage pipeline in order and assembles the `figures/` directory
so the report LaTeX file (`Artemis_Track1_Report.tex`) can be compiled.

Usage
-----
    python3 reproduce.py              # run all stages
    python3 reproduce.py --from 03   # resume from stage 03 onwards
    python3 reproduce.py --stage 06  # run one stage only
    python3 reproduce.py --figures   # assemble figures/ only (skip pipeline)

Prerequisites
-------------
1. Copy `.env.example` to `.env` in this directory and fill in:
       ARTEMIS_API_KEY=<your key>
       COINGECKO_API_KEY=<your key>
       FRED_API_KEY=<your key>
   Stage 01 reads these to fetch the cleaned data panels.
   Stages 02–06 read the committed artifacts and do not need API keys.

2. Install all dependencies:
       pip install -r requirements.txt

What each stage does
--------------------
01  Download and clean market/on-chain data → 01_Data_Collection/data/clean/
02  Build weekly cross-sectional characteristics and econometric diagnostics
03  Build the time-varying network panel (MST + Louvain), the production universe,
    weekly returns, fundamentals, and run factor validation (IC / ASD / GX)
04  Behavioral factor search (182 candidates, Bonferroni + BH correction)
05  Per-factor dashboards for the 15 validated factors
06  Regime-aware three-book ensemble strategy and backtest

Figures
-------
After running, call `assemble_figures()` (or pass --figures) to copy the
pipeline outputs into `figures/` so the LaTeX report can find them.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


def run(cmd: list[str], *, stage: str) -> None:
    print(f"\n{'='*60}")
    print(f"  Stage {stage}: {' '.join(cmd[1:])}")
    print(f"{'='*60}")
    result = subprocess.run([PYTHON] + cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"\n[ERROR] Stage {stage} failed (exit {result.returncode}).")
        print("Fix the error above and re-run with --from to resume.")
        sys.exit(result.returncode)


def stage_01() -> None:
    run(["01_Data_Collection/src/main.py"], stage="01")


def stage_02() -> None:
    scripts = [
        "02_artemis_econometrics/01_build_panel.py",
        "02_artemis_econometrics/02_characteristics.py",
        "02_artemis_econometrics/03_network_features.py",
        "02_artemis_econometrics/04_latent_controls.py",
        "02_artemis_econometrics/05_models.py",
        "02_artemis_econometrics/06_backtest.py",
        "02_artemis_econometrics/07_report.py",
    ]
    for s in scripts:
        run([s], stage="02")


def stage_03() -> None:
    scripts = [
        "03_nalfp_add/00_network_dynamics.py",
        "03_nalfp_add/01_universe_coverage.py",
        "03_nalfp_add/02_coinmetrics_coverage.py",
        "03_nalfp_add/03_reconstruct_mcap_panel.py",
        "03_nalfp_add/04_freeze_universe.py",
        "03_nalfp_add/05_returns_and_reference.py",
        "03_nalfp_add/06_sparse_pca.py",
        "03_nalfp_add/07_cca_macro.py",
        "03_nalfp_add/09b_fundamentals.py",
        "03_nalfp_add/08_factor_validation.py",
        "03_nalfp_add/09c_gx_pricing_full.py",
    ]
    for s in scripts:
        run([s], stage="03")


def stage_04() -> None:
    run(["04_behavioral_gx/01_behavioral_gx_search.py"], stage="04")


def stage_05() -> None:
    import os
    viz_dirs = sorted(
        d for d in (ROOT / "05_factor_viz").iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
    for viz_dir in viz_dirs:
        scripts = sorted(viz_dir.glob("[0-9]*.py"))
        for s in scripts:
            run([str(s.relative_to(ROOT))], stage="05")


def stage_06() -> None:
    run(["06_factor_ensemble_strategy/run.py"], stage="06")


def assemble_figures() -> None:
    """Copy pipeline outputs into figures/ so LaTeX can find them."""
    fig_dir = ROOT / "figures"
    fig_dir.mkdir(exist_ok=True)

    # Factor-viz figures used in the report (§5)
    factor_copies = [
        ("05_factor_viz/volc_visualisation/artifacts/figures/volc_01_cumulative_return.png",
         "figures/volc_01_cumulative_return.png"),
        ("05_factor_viz/volc_visualisation/artifacts/figures/volc_02_rolling_ic_significance.png",
         "figures/volc_02_rolling_ic_significance.png"),
        ("05_factor_viz/crash8_visualisation/artifacts/figures/crash8_01_cumulative_return.png",
         "figures/crash8_01_cumulative_return.png"),
        ("05_factor_viz/crash8_visualisation/artifacts/figures/crash8_02_rolling_return_significance.png",
         "figures/crash8_02_rolling_return_significance.png"),
        ("05_factor_viz/netrel_visualisation/artifacts/figures/netrel_01_cumulative_return.png",
         "figures/netrel_01_cumulative_return.png"),
        ("05_factor_viz/netrel_visualisation/artifacts/figures/netrel_02_rolling_ic_significance.png",
         "figures/netrel_02_rolling_ic_significance.png"),
    ]

    # Strategy figures used in the report (§6–7)
    strategy_copies = [
        ("06_factor_ensemble_strategy/artifacts/figures/sharpe_ensemble_book_allocations.png",
         "figures/image5.png"),
        ("06_factor_ensemble_strategy/artifacts/figures/balanced_ensemble_book_allocations.png",
         "figures/image2.png"),
        ("06_factor_ensemble_strategy/artifacts/figures/cumulative_returns.png",
         "figures/image4.png"),
    ]

    for src_rel, dst_rel in factor_copies + strategy_copies:
        src = ROOT / src_rel
        dst = ROOT / dst_rel
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  copied {src_rel} → {dst_rel}")
        else:
            print(f"  [WARN] source not found (run pipeline first): {src_rel}")

    # image6.png = XGBoost regime schematic (Appendix B)
    # The weekly probabilities are not committed; we render a labelled schematic.
    _render_regime_schematic(fig_dir / "image6.png")

    # Static diagrams (network_clusters, netmom_netrel_schematic, factor_routing_graph)
    # are committed directly into figures/ and do not need to be copied.
    statics = ["network_clusters.png", "netmom_netrel_schematic.png", "factor_routing_graph.png"]
    for name in statics:
        p = fig_dir / name
        if p.exists():
            print(f"  static figure present: figures/{name}")
        else:
            print(f"  [WARN] static figure missing: figures/{name}")


def _render_regime_schematic(out: Path) -> None:
    """Render an illustrative XGBoost regime probability chart (Appendix B).

    The true weekly probabilities are not committed. This schematic uses a
    fixed-seed noise sequence and is labelled ILLUSTRATIVE to make that clear.
    Re-running `06_factor_ensemble_strategy/run.py` against live data produces
    the real probability path.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd

        rng = np.random.default_rng(7)
        weeks = pd.date_range("2021-05-10", "2026-05-25", freq="W-MON")
        n = len(weeks)
        base = np.linspace(0, 2 * np.pi, n)
        risk_on  = np.clip(0.50 + 0.25 * np.sin(base + 0.3) + 0.05 * rng.standard_normal(n), 0.05, 0.85)
        risk_off = np.clip(0.30 + 0.20 * np.cos(base * 0.8 + 1.1) + 0.05 * rng.standard_normal(n), 0.05, 0.75)
        neutral  = np.clip(1.0 - risk_on - risk_off, 0.05, None)
        total = risk_on + risk_off + neutral
        risk_on /= total; risk_off /= total; neutral /= total

        fig, ax = plt.subplots(figsize=(11, 4.5))
        ax.stackplot(weeks, risk_off, neutral, risk_on,
                     labels=["Risk-Off", "Neutral", "Risk-On"],
                     colors=["#ef6b6b", "#6b7c8f", "#5cb85c"],
                     edgecolor="white", linewidth=0.4)
        ax.set_ylim(0, 1)
        ax.set_ylabel("Regime probability")
        ax.set_title("XGBoost regime probabilities — illustrative schematic")
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.legend(loc="upper right", framealpha=0.9, fontsize=9)
        ax.axvline(pd.Timestamp("2024-11-18"), color="#1f3a5f", linestyle="--", linewidth=1.0)
        ax.text(pd.Timestamp("2024-11-18"), 1.02, "OOS start",
                ha="center", va="bottom", fontsize=8.5, color="#1f3a5f")
        ax.text(0.5, 0.5, "ILLUSTRATIVE", transform=ax.transAxes,
                ha="center", va="center", fontsize=42, color="#6b7c8f",
                alpha=0.18, rotation=20, fontweight="bold")
        fig.text(0.5, -0.02,
                 "Schematic — weekly XGBoost probabilities not committed. "
                 "Run 06_factor_ensemble_strategy/run.py against live data to reproduce.",
                 ha="center", fontsize=8, color="#6b7c8f")
        plt.tight_layout()
        fig.savefig(out, dpi=160, bbox_inches="tight")
        plt.close(fig)
        print(f"  rendered regime schematic → {out.name}")
    except Exception as exc:
        print(f"  [WARN] could not render regime schematic: {exc}")


STAGES = {"01": stage_01, "02": stage_02, "03": stage_03,
          "04": stage_04, "05": stage_05, "06": stage_06}
STAGE_ORDER = ["01", "02", "03", "04", "05", "06"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce Artemis strategy results.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--stage", metavar="N", help="Run one stage only (01–06).")
    group.add_argument("--from",  metavar="N", dest="from_stage",
                       help="Run stages N through 06.")
    group.add_argument("--figures", action="store_true",
                       help="Assemble figures/ directory only (skip pipeline).")
    args = parser.parse_args()

    if args.figures:
        assemble_figures()
        return

    if args.stage:
        if args.stage not in STAGES:
            parser.error(f"Unknown stage '{args.stage}'. Choose from {STAGE_ORDER}.")
        STAGES[args.stage]()
        assemble_figures()
        return

    start = args.from_stage or "01"
    if start not in STAGES:
        parser.error(f"Unknown stage '{start}'.")

    to_run = STAGE_ORDER[STAGE_ORDER.index(start):]
    for s in to_run:
        STAGES[s]()

    assemble_figures()
    print("\n✓ All stages complete. figures/ is assembled and ready for LaTeX.")
    print("  Compile the report with: pdflatex Artemis_Track1_Report.tex (run twice)")


if __name__ == "__main__":
    main()
