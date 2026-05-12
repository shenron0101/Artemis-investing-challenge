"""06 — Generate REPORT.md and a summary table for NALFP.

This is a *report generator*, not the report itself: it stitches the previously
written artifacts into a single markdown document so the LaTeX/PDF report can
embed the same numbers without manual transcription. Plots are referenced by
relative path; the LaTeX paper (separate file) re-uses them via includegraphics.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from textwrap import dedent

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    DATA_DIR,
    MANIFEST_DIR,
    TABLE_DIR,
    TRAIN_WEEKS,
    write_frame,
)

REPORT_PATH = Path(__file__).resolve().parent / "REPORT.md"


def _load_json(name: str) -> dict | list:
    path = MANIFEST_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _fmt(x, pct=False, dp=3):
    if x is None or (isinstance(x, float) and (np.isnan(x))):
        return "—"
    if pct:
        return f"{x*100:.{dp}f}%"
    return f"{x:.{dp}f}"


def metrics_table(metrics: list[dict]) -> str:
    rows = ["| Strategy | Window | Weeks | Ann.Return | Ann.Vol | Sharpe | MaxDD | Turnover | Hit% |",
            "|---|---|---|---|---|---|---|---|---|"]
    for m in metrics:
        for window in ("full", "train", "oos"):
            d = m.get(window, {})
            if not d:
                continue
            rows.append(
                f"| {m['strategy']} | {window} | {d['weeks']} | "
                f"{_fmt(d.get('ann_return'), pct=True, dp=2)} | "
                f"{_fmt(d.get('ann_vol'), pct=True, dp=2)} | "
                f"{_fmt(d.get('sharpe'), dp=2)} | "
                f"{_fmt(d.get('max_dd'), pct=True, dp=2)} | "
                f"{_fmt(d.get('avg_turnover'), pct=True, dp=2)} | "
                f"{_fmt(d.get('hit_rate'), pct=True, dp=1)} |"
            )
    return "\n".join(rows)


def factor_table(premia: list[dict]) -> str:
    rows = ["| Factor | Mean (weekly) | SE | t-stat | n |",
            "|---|---|---|---|---|"]
    for p in premia:
        rows.append(
            f"| {p['factor']} | {_fmt(p['mean'], dp=4)} | "
            f"{_fmt(p['se'], dp=4)} | {_fmt(p['tstat'], dp=2)} | {p['n']} |"
        )
    return "\n".join(rows)


def main() -> None:
    m_network = _load_json("01_network_manifest.json")
    m_ipca = _load_json("02_ipca_manifest.json")
    m_regime = _load_json("03_regime_manifest.json")
    m_portfolio = _load_json("04_portfolio_manifest.json")
    metrics = _load_json("05_metrics.json")

    # Verification checklist
    verif: list[tuple[str, bool, str]] = []
    cluster_ok = (m_network.get("min_clusters", 0) or 0) >= 2 and (m_network.get("max_clusters", 0) or 0) <= 10
    verif.append(("MST + Louvain produces 2–10 clusters across all weeks", cluster_ok,
                  f"observed range {m_network.get('min_clusters')}–{m_network.get('max_clusters')}"))
    survived = m_ipca.get("survived_factors_t_ge_1p65", [])
    verif.append((">=1 IPCA factor survives |t|>=1.65 filter", len(survived) >= 1,
                  f"{len(survived)}/{m_ipca.get('n_factors')} survived"))
    w_min = m_regime.get("w_net_min", 0.5)
    w_max = m_regime.get("w_net_max", 0.5)
    verif.append(("Regime weight w_net spans a meaningful range", (w_max - w_min) > 0.1,
                  f"{_fmt(w_min)}–{_fmt(w_max)}"))
    oos = next((m["oos"] for m in metrics if m["strategy"] == "NALFP"), {})
    bench = next((m["oos"] for m in metrics if m["strategy"] == "EW_mom_long"), {})
    sharpe_ok = (oos.get("sharpe") or -1) >= (bench.get("sharpe") or 0)
    verif.append(("OOS Sharpe ≥ equal-weight momentum baseline", sharpe_ok,
                  f"NALFP {_fmt(oos.get('sharpe'))} vs EW {_fmt(bench.get('sharpe'))}"))

    md = dedent(f"""
    # NALFP — Network-Augmented Latent Factor Portfolio

    A weekly-rebalanced long/short crypto factor strategy that:

    1. extracts time-varying community structure from the rolling Spearman MST + Louvain,
    2. fits an Instrumented PCA (Kelly–Pruitt–Su 2019) model on 11 lagged characteristics — including the three network signals — to produce expected returns,
    3. blends the network and IPCA signals with adaptive IC weights, and
    4. trades the top vs bottom quintile under explicit cluster-diversification, single-asset, turnover, and volatility-target constraints.

    The novel piece is **(2)** — using network topology as instruments for latent factor loadings. No prior work in the three source papers (Time-Varying Network, Crypto Pricing with Hidden Factors, RAAM) does this jointly.

    ## 1. Hypothesis

    Cryptocurrency cross-sectional returns are better predicted by the *interaction* of community structure and fundamental factor exposure than by either alone. When the correlation network is **fragmenting** (high entropy, many small communities), within-cluster relative strength is the dominant signal. When the network is **converging** (low entropy, one giant component), latent common factors take over.

    ## 2. Data

    - 86 cryptocurrencies, weekly close-to-close, 52 weeks (2025-05-12 → 2026-05-04).
    - Stablecoins, wrapped and bridged tokens excluded up front (mirrors stage-04/06 universe).
    - 11 instruments per asset per week (all lagged one week):
      `mom_4w, vol_4w, log_mcap, turnover, F_yield, S_supply, G_growth, within_cluster_mom, cross_cluster_rel, network_entropy, stable_inflow_z`.
    - Backtest split: first {TRAIN_WEEKS} weeks for training, last {52 - TRAIN_WEEKS} weeks OOS.

    ## 3. Pillar 1 — Time-Varying Network

    - Rolling {m_network.get('window_weeks', 12)}-week Spearman correlations → Mantegna distance → MST → Louvain.
    - Across all clustered weeks the partition contains **{m_network.get('min_clusters')}** to **{m_network.get('max_clusters')}** communities (mean entropy {_fmt(m_network.get('mean_entropy'))}).
    - Per-asset signals: within-cluster rank z-score of `mom_4w`, and own `mom_4w` minus the mean `mom_4w` of every *other* cluster.
    - Market-wide fragmentation: Shannon entropy of cluster-size distribution.

    ![network overview](figures/01_network_dynamics/network_overview.html)

    ## 4. Pillar 2 — Instrumented PCA Expected Returns

    Restricted IPCA model (no alpha): `r_{{i,t+1}} = z_{{i,t}}' Γ f_{{t+1}} + e`, with `Γ' Γ = I_K`, `K = {m_ipca.get('n_factors', 3)}` latent factors. Estimation by alternating least squares on the training window, then walk-forward refit every 4 weeks on an expanding history.

    ### IPCA factor premia (training window)

    {factor_table(m_ipca.get('premia', []))}

    Survival filter (|t| ≥ 1.65): **{", ".join(m_ipca.get('survived_factors_t_ge_1p65', [])) or 'none'}**.

    ![IPCA loadings Γ](figures/02_ipca_pricing/gamma_loadings.html)
    ![cumulative latent factor returns](figures/02_ipca_pricing/factor_cumulative.html)

    ## 5. Pillar 3a — Regime-Adaptive Signal Blend

    Each week we set the network weight by IC-proportional blending with an 8-week lookback of *past* ICs (strictly OOS):

    `w_net_t = clip+(IC_net_{{t-1}}) / [ clip+(IC_net_{{t-1}}) + clip+(IC_ipca_{{t-1}}) ]`.

    Observed range of `w_net`: **{_fmt(m_regime.get('w_net_min'))}–{_fmt(m_regime.get('w_net_max'))}** (mean {_fmt(m_regime.get('w_net_mean'))}). Sample-level IC averages — network: {_fmt(m_regime.get('ic_net_full_sample_mean'))}, IPCA: {_fmt(m_regime.get('ic_ipca_full_sample_mean'))}. OOS-only IC averages — network: {_fmt(m_regime.get('ic_net_oos_mean'))}, IPCA: {_fmt(m_regime.get('ic_ipca_oos_mean'))}.

    ![regime blend](figures/03_regime_detector/regime_blend.html)

    ## 6. Pillar 3b — Portfolio Construction

    - Long the top {int(m_portfolio.get('quintile', 0.2) * 100)}% by `E_final`, short the bottom {int(m_portfolio.get('quintile', 0.2) * 100)}%.
    - Inverse-volatility weights within each leg, normalised to ±1 (dollar-neutral).
    - Single-asset cap **{int(m_portfolio.get('max_asset_weight', 0.05) * 100)}%**; long-leg cluster cap **{int(m_portfolio.get('max_cluster_fraction', 0.4) * 100)}%** of leg notional; turnover budget **{int(m_portfolio.get('turnover_cap', 0.3) * 100)}%** per week; gross-vol target **{int(m_portfolio.get('vol_target_annual', 0.15) * 100)}%** annualised (leverage capped at 2×).
    - Median long leg: {m_portfolio.get('median_long_n')} names; median short leg: {m_portfolio.get('median_short_n')} names.

    ![portfolio diagnostics](figures/04_portfolio_construction/portfolio_diagnostics.html)
    ![cluster composition](figures/04_portfolio_construction/cluster_composition.html)

    ## 7. Headline Results

    {metrics_table(metrics)}

    ![cumulative pnl](figures/05_backtest/cumulative_pnl.html)

    ## 8. Verification Checklist

    """).strip() + "\n\n"
    for label, passed, note in verif:
        check = "✅" if passed else "⚠️"
        md += f"- {check} {label} — {note}\n"

    md += dedent("""

    ## 9. Honest limitations

    - **Sample size.** 52 weeks total → 16 OOS weeks. Statistical power on Sharpe ratios is limited; any number we quote has a wide confidence interval.
    - **One regime.** The OOS window covers one liquidity cycle. The strategy's regime detector is mechanical, but its *validation* depends on observing both fragmented and converged regimes, and we do not have many transitions in this slice of history.
    - **Activity coverage.** `F_yield`, `S_supply` and `G_growth` are sparse (38–85% missing) because Artemis fundamentals are not yet wired in for the long tail of the universe. We median-impute within week, which biases those instruments toward neutrality.
    - **Costs.** 10 bps one-sided turnover cost is reasonable for top-50 names but optimistic for the long tail; the short leg further assumes uncapped borrow at zero financing cost.
    - **Hidden factors are statistical.** We do not assign economic labels to the latent factors. We deliberately follow Crypto Pricing with Hidden Factors here — the alpha is supposed to be in the *projection* onto characteristics, not in any individual factor narrative.
    - **What would break this.** A sustained risk-off cascade where every cluster moves with one factor (entropy collapses) plus IPCA's training history loses predictive power → both signal streams degrade. In that scenario the strategy reverts to inverse-vol cluster diversification — fine, but unexceptional.

    ## 10. Reproducibility

    ```
    python3 08_nalfp/01_network_dynamics.py
    python3 08_nalfp/02_ipca_pricing.py
    python3 08_nalfp/03_regime_detector.py
    python3 08_nalfp/04_portfolio_construction.py
    python3 08_nalfp/05_backtest.py
    python3 08_nalfp/06_report.py
    ```

    All upstream data is checked into `01_Data_Collection/data/clean/` and 06/07 artifacts are re-derived deterministically from there.
    """)

    REPORT_PATH.write_text(md.lstrip(), encoding="utf-8")
    print(f"  wrote {REPORT_PATH.relative_to(Path(__file__).resolve().parents[1])}")


if __name__ == "__main__":
    main()
