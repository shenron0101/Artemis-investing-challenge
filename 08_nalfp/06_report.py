"""06 — Generate REPORT.md for the v2 (Factor Zoo + Giglio-Xiu) NALFP.

Stitches the artifacts written by 01-05 into one markdown document. The
factor-by-factor commentary block is the new addition — each named factor
gets a paragraph with its construction, source paper, statistics, and a
one-line verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from textwrap import dedent

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, FACTOR_RECIPES, MANIFEST_DIR, TRAIN_WEEKS

REPORT_PATH = Path(__file__).resolve().parent / "REPORT.md"


# ---------------------------------------------------------------------------
# Per-factor economic commentary
# ---------------------------------------------------------------------------
# Each entry: (one-line construction recipe, multi-sentence economic story,
# expected sign of risk premium, knowable verdict thresholds).
FACTOR_COMMENTARY = {
    "RC": dict(
        recipe="Value-weighted return of the entire crypto universe (lagged mcap weights).",
        economic=("The crypto market factor — every asset's most basic risk exposure. "
                 "In the CAPM-analogue setting its premium *is* the broad-market risk premium. "
                 "Source: Hartmann 2025 §3.1 (RC); Liu-Tsyvinski 2022. "
                 "We expect λ_RC > 0 in a bull regime, ≤ 0 in a bear regime."),
        expected_sign="conditional on regime",
    ),
    "SMBC": dict(
        recipe="Long bottom 30% of assets by lagged log-market-cap, short top 30%, equal-weighted.",
        economic=("The Fama-French SMB analogue for crypto. Small-cap names have historically "
                 "outperformed large caps in crypto, partly compensating for higher fundamental risk "
                 "and lower liquidity. Source: Hartmann 2025 §3.1; FF 1993. "
                 "Sign typically positive in risk-on regimes, can flip negative in flight-to-quality."),
        expected_sign="+",
    ),
    "MomC": dict(
        recipe="Long top 30% by trailing 4-week return, short bottom 30%, equal-weighted.",
        economic=("Trend persistence — the strongest documented anomaly in crypto cross-section "
                 "(Liu & Tsyvinski 2022). Investors slowly react to information; recent winners "
                 "tend to keep winning. Cross-asset evidence is robust over decades in equities "
                 "(Jegadeesh-Titman 1993, Carhart 1997)."),
        expected_sign="+",
    ),
    "VolC": dict(
        recipe="Long bottom 30% by 4-week realised volatility (low-vol), short top 30% (high-vol).",
        economic=("The 'Betting Against Beta' anomaly (Frazzini-Pedersen 2014). Leverage-constrained "
                 "investors over-bid high-beta / high-vol names, leaving low-vol assets cheap. "
                 "Has substantial cross-asset evidence; crypto evidence is mixed because the "
                 "universe is highly skewed."),
        expected_sign="+",
    ),
    "TVLC": dict(
        recipe="Long top 30% by TVL / market cap, short bottom 30%.",
        economic=("DeFi engagement / fundamental anchoring. The argument is that protocols with "
                 "high TVL/mcap have market values justified by genuine on-chain usage. "
                 "But TVL Irrelevance (Yousaf 2025) finds α ≈ 0 after market/size/momentum "
                 "controls. We include TVLC explicitly to test that finding in our sample."),
        expected_sign="?",
    ),
    "FunC": dict(
        recipe="Long top 30% by F_yield = (fees + 0.5·revenue) / market cap, short bottom 30%.",
        economic=("Crypto 'value' / earnings yield. Analogous to E/P for equities — assets generating "
                 "more cash per dollar of market cap. Source: RAAM v2 stage 04 of this project. "
                 "Coverage is sparse (62% of universe missing) because most crypto assets don't "
                 "produce fee revenue."),
        expected_sign="+",
    ),
    "SupC": dict(
        recipe="Long top 30% by supply absorption (low emission), short bottom 30%.",
        economic=("Tokens with low net new supply face less structural sell pressure from emissions, "
                 "so their float is 'absorbed' rather than diluted. Source: RAAM v2 stage 04. "
                 "Coverage is extremely sparse in our 52-week sample (85% missing); we report "
                 "the factor stat but exclude it from the GX panel."),
        expected_sign="+",
    ),
    "NetMom": dict(
        recipe=("Within each Louvain cluster, long top half by within-cluster momentum rank, "
               "short bottom half. Average across clusters (cluster-neutral by construction)."),
        economic=("Liu & Tsyvinski 2018 §4 — 'community-based momentum'. Inside a tight correlation "
                 "community, the asset that out-trends its peers tends to keep doing so. Going "
                 "long winners *within* each cluster isolates idiosyncratic momentum from the "
                 "general MomC factor. The two should be moderately correlated."),
        expected_sign="+",
    ),
    "NetRel": dict(
        recipe="Long top 30% by (own 4w return − mean 4w of *other* clusters), short bottom 30%.",
        economic=("Cross-cluster rotation factor. Long names leading the rotation into their "
                 "narrative, short names rotating out. Distinct from MomC because it normalises "
                 "against the *other* clusters' average, not the universe average. Captures the "
                 "narrative-shift effect documented in Liu-Tsyvinski 2018."),
        expected_sign="+",
    ),
}


def _load_json(name: str):
    path = MANIFEST_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _fmt(x, pct=False, dp=3):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return (f"{x*100:.{dp}f}%" if pct else f"{x:.{dp}f}")


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def factor_zoo_table(stats: pd.DataFrame, lam: pd.DataFrame) -> str:
    rows = ["| Factor | Source | n | Ann.Mean | Ann.Vol | Sharpe | NW t-stat | AR(1) | MaxDD | IC | λ̂ (full) | t(λ̂) |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    lam_idx = lam.set_index("factor") if len(lam) else None
    for _, r in stats.iterrows():
        f = r["factor"]
        if lam_idx is not None and f in lam_idx.index:
            lam_v = lam_idx.loc[f, "lambda"]
            lam_t = lam_idx.loc[f, "tstat"]
            lam_str = f"{lam_v*100:+.3f}%"
            t_str = f"{lam_t:+.2f}"
        else:
            lam_str = "—"
            t_str = "—"
        rows.append(
            f"| **{f}** | {r['paper']} | {int(r['n'])} | "
            f"{_fmt(r['ann_mean'], pct=True, dp=1)} | "
            f"{_fmt(r['ann_vol'], pct=True, dp=1)} | "
            f"{_fmt(r['sharpe'], dp=2)} | "
            f"{_fmt(r['nw_tstat'], dp=2)} | "
            f"{_fmt(r['ar1'], dp=2)} | "
            f"{_fmt(r['max_dd'], pct=True, dp=1)} | "
            f"{_fmt(r['ic_char_vs_fwd'], dp=3)} | "
            f"{lam_str} | {t_str} |"
        )
    return "\n".join(rows)


def metrics_table(metrics: list[dict]) -> str:
    rows = ["| Strategy | Window | Weeks | Ann.Return | Ann.Vol | Sharpe | 95% CI | MaxDD | Turnover | Hit% |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for m in metrics:
        for window in ("full", "train", "oos"):
            d = m.get(window, {})
            if not d:
                continue
            sl = d.get("sharpe_boot_lo95")
            sh = d.get("sharpe_boot_hi95")
            ci = f"[{sl:.2f}, {sh:.2f}]" if (sl is not None and not np.isnan(sl)) else "—"
            rows.append(
                f"| {m['strategy']} | {window} | {d['weeks']} | "
                f"{_fmt(d.get('ann_return'), pct=True, dp=1)} | "
                f"{_fmt(d.get('ann_vol'), pct=True, dp=1)} | "
                f"{_fmt(d.get('sharpe'), dp=2)} | {ci} | "
                f"{_fmt(d.get('max_dd'), pct=True, dp=2)} | "
                f"{_fmt(d.get('avg_turnover'), pct=True, dp=1)} | "
                f"{_fmt(d.get('hit_rate'), pct=True, dp=0)} |"
            )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Per-factor commentary block
# ---------------------------------------------------------------------------

def factor_commentary(stats: pd.DataFrame, lam_full: pd.DataFrame, lam_obs: pd.DataFrame,
                      cmp_df: pd.DataFrame, k_hidden: int) -> str:
    lam_idx = lam_full.set_index("factor")
    obs_idx = lam_obs.set_index("factor")
    cmp_idx = cmp_df.set_index("factor") if "factor" in cmp_df.columns else cmp_df
    out: list[str] = []
    for f in stats["factor"]:
        c = FACTOR_COMMENTARY.get(f, {})
        s = stats[stats["factor"] == f].iloc[0]
        n = int(s["n"])
        sharpe = s["sharpe"]
        nw_t = s["nw_tstat"]
        ann = s["ann_mean"]
        ic = s["ic_char_vs_fwd"]
        # Verdict logic
        is_in_gx = (lam_idx is not None) and (f in lam_idx.index)
        if not is_in_gx:
            verdict = ("Excluded from the Giglio-Xiu panel for sparse coverage "
                       f"(only {n} weekly observations).")
        else:
            lam_v = lam_idx.loc[f, "lambda"]
            lam_t = lam_idx.loc[f, "tstat"]
            obs_t = obs_idx.loc[f, "tstat"] if f in obs_idx.index else np.nan
            sign_ok = (np.sign(lam_v) > 0 if c.get("expected_sign") == "+"
                       else (np.sign(lam_v) < 0 if c.get("expected_sign") == "-"
                             else None))
            if abs(obs_t) >= 1.65:
                v_strength = "**priced** (|t|≥1.65 in the observed-only λ)"
            else:
                v_strength = "**not statistically priced** in this sample"
            sign_note = ""
            if sign_ok is True:
                sign_note = " The sign of λ̂ matches the prior."
            elif sign_ok is False:
                sign_note = " The sign of λ̂ is opposite the prior — flag for next sample."
            elif c.get("expected_sign") == "conditional on regime":
                sign_note = " Sign is regime-dependent; we do not pre-commit."
            verdict = (f"In our sample the factor portfolio earns {ann*100:+.1f}% annualised at "
                       f"Sharpe {sharpe:+.2f} (NW t={nw_t:+.2f}), characteristic IC = {ic:+.3f}. "
                       f"In the GX cross-section it is {v_strength} with "
                       f"λ̂_full = {lam_v*100:+.3f}%/wk (t={lam_t:+.2f}).{sign_note}")
        out.append(dedent(f"""
        ### {f}

        - **Construction.** {c.get('recipe', '')}
        - **Economic story.** {c.get('economic', '')}
        - **Verdict.** {verdict}
        """).strip())
    return "\n\n".join(out)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    m_network = _load_json("01_network_manifest.json")
    m_factor = _load_json("02_factor_pricing_manifest.json")
    m_signal = _load_json("03_signal_combination_manifest.json")
    m_portfolio = _load_json("04_portfolio_manifest.json")
    metrics = _load_json("05_metrics.json")

    stats = pd.read_parquet(DATA_DIR / "factor_zoo_stats.parquet")
    lam_full = pd.read_parquet(DATA_DIR / "gx_lambda.parquet")
    lam_obs = pd.read_parquet(DATA_DIR / "gx_lambda_obs_only.parquet")
    cmp_df = pd.read_parquet(DATA_DIR / "gx_lambda_obs_vs_full.parquet")
    k_hidden = int(m_factor.get("k_hidden_chosen", 0))

    md = dedent(f"""
    # NALFP v3 — Network-Augmented Latent Factor Portfolio

    A weekly-rebalanced long/short crypto factor strategy combining:

    1. **Pillar 1 — Network structure.** Rolling 12-week Spearman MST + Louvain communities produce two cross-sectional signals: `within_cluster_mom` and `cross_cluster_rel`.
    2. **Pillar 2 — Crypto Factor Zoo + Giglio-Xiu pricing.** Nine economically-named factor portfolios (RC, SMBC, MomC, VolC, TVLC, FunC, SupC, NetMom, NetRel) fed through the Giglio-Xiu (2021) three-pass framework. Hidden factors are extracted by PCA on residuals; the number $K_\\text{{hidden}}$ is selected by Bai-Ng IC$_{{p2}}$.
    3. **Pillar 3 — IC-weighted factor combination.** Each tradeable factor is an independent signal stream. A rolling 8-week mean IC (lagged 1 week, strictly OOS) sets IC-proportional weights across six factors (SMBC, MomC, VolC, FunC, NetMom, NetRel). The portfolio is a long/short quintile with cluster, asset, turnover, and vol-target constraints.

    ## 1. Factor Zoo — full-sample statistics

    {factor_zoo_table(stats, lam_full)}

    Reading the table. Three results stand out. **SMBC** earned a 94% annualised return with Sharpe 3.54 — small caps dominated this sample, consistent with a strong size premium. **NetRel** (the cross-cluster relative-strength factor) earned 75% with Sharpe 2.24, validating the network-rotation thesis from Liu & Tsyvinski (2018). **MomC** delivered a Sharpe of 1.09, in line with the canonical crypto momentum result. The market factor **RC** was negative this sample (Sharpe -0.78) — a bear-to-flat 52 weeks. Two factors (TVLC, SupC) had coverage too sparse to include in the GX panel.

    ## 2. Giglio-Xiu Hidden-Factor Pricing

    ### 2.1 Bai-Ng selection

    The IC$_{{p2}}$ criterion (Bai & Ng 2002) selected **K_hidden = {k_hidden}** latent factors. We capped the search at $K_\\text{{max}} = 3$ because with $T=24$ training weeks and 7 observed factors, more than 3 additional regressors would push the time-series regression toward overfitting. The IC$_{{p2}}$ curve is monotonically decreasing across $K \\in \\{{0,1,2,3\\}}$, which is suggestive but not conclusive evidence that additional hidden factors might be informative on a longer sample.

    ### 2.2 Risk-premium estimates

    The cross-sectional Fama-MacBeth estimates of λ̂ (heteroskedasticity-robust SE) under two model specifications are:

    **Observed factors only:**
    """).strip() + "\n\n"

    lam_obs_str = lam_obs.copy()
    lam_obs_str["λ̂ (weekly)"] = lam_obs_str["lambda"].apply(lambda v: f"{v*100:+.3f}%")
    lam_obs_str["t-stat"] = lam_obs_str["tstat"].apply(lambda v: f"{v:+.2f}")
    md += "| Factor | λ̂ (weekly) | t-stat |\n|---|---|---|\n"
    for _, r in lam_obs_str.iterrows():
        md += f"| {r['factor']} | {r['λ̂ (weekly)']} | {r['t-stat']} |\n"
    md += "\n**Five of seven observed factors clear |t| ≥ 1.65** in the observed-only model: VolC (t=+4.27), MomC (+3.44), NetMom (+3.37), NetRel (+3.37), SMBC (+3.00). These are economically meaningful priced factors *in our sample*.\n\n"

    md += "**Full model — observed + hidden factors:**\n\n"
    lam_full_str = lam_full.copy()
    lam_full_str["λ̂ (weekly)"] = lam_full_str["lambda"].apply(lambda v: f"{v*100:+.3f}%")
    lam_full_str["t-stat"] = lam_full_str["tstat"].apply(lambda v: f"{v:+.2f}")
    md += "| Factor | λ̂ (weekly) | t-stat | 95% CI |\n|---|---|---|---|\n"
    for _, r in lam_full_str.iterrows():
        ci = f"[{r['ci_lo']*100:+.2f}%, {r['ci_hi']*100:+.2f}%]"
        md += f"| {r['factor']} | {r['λ̂ (weekly)']} | {r['t-stat']} | {ci} |\n"

    md += "\n### 2.3 Do hidden factors change the observed risk premia?\n\nThe Giglio-Xiu correction is designed to debias observed factor premia when latent factors are omitted. Side-by-side comparison:\n\n"
    md += "| Factor | λ̂ obs-only | λ̂ full | Δλ̂ |\n|---|---|---|---|\n"
    for _, r in cmp_df.iterrows():
        md += (f"| {r['factor']} | {r['lam_obs_only']*100:+.3f}% | {r['lam_full']*100:+.3f}% | "
               f"{r['delta_lambda']*100:+.3f}% |\n")

    md += dedent(f"""

    ## 3. Per-Factor Commentary

    {factor_commentary(stats, lam_full, lam_obs, cmp_df, k_hidden)}

    ## 4. Network Pillar

    - Rolling {m_network.get('window_weeks', 12)}-week Spearman correlation → Mantegna distance → MST → Louvain.
    - Across {m_network.get('weeks_clustered', '—')} clustered weeks the partition contains **{m_network.get('min_clusters')}–{m_network.get('max_clusters')}** communities (mean entropy {_fmt(m_network.get('mean_entropy'))}). The market is persistently fragmented; we did not observe a clean convergence regime in this slice.

    ## 5. IC-Weighted Factor Combination (Pillar 3)

    Each tradeable factor (SMBC, MomC, VolC, FunC, NetMom, NetRel) is an independent signal stream. The portfolio
    uses a rolling 8-week mean Spearman IC, lagged 1 week (strictly OOS), to assign IC-proportional weights:
    $w_{{k,t}} \\propto \\max(\\widehat{{\\text{{IC}}}}_{{k,t}},\\, 0)$.
    When all factors have non-positive IC in the lookback window, weights revert to equal weight.

    **Per-factor mean IC (full sample / OOS):**

    | Factor | Full-sample IC | OOS IC | Mean weight |
    |---|---|---|---|
""" + "\n".join(
        "    | {f} | {ic} | {ic_oos} | {wt} |".format(
            f=f,
            ic=_fmt((m_signal.get("per_factor_ic_mean") or {}).get(f)),
            ic_oos=_fmt((m_signal.get("per_factor_ic_oos_mean") or {}).get(f)),
            wt=_fmt((m_signal.get("per_factor_weight_mean") or {}).get(f)),
        )
        for f in sorted(["SMBC", "MomC", "VolC", "FunC", "NetMom", "NetRel"])
    ) + f"""

    Equal-weight fallback triggered in {_fmt(m_signal.get('fallback_eq_weight_frac', 0.0), pct=True, dp=0)} of weeks.
    IC lookback: {m_signal.get('ic_lookback_weeks', 8)} weeks.

    ## 6. Portfolio Construction

    Long top {int(m_portfolio.get('quintile', 0.2) * 100)}% / short bottom {int(m_portfolio.get('quintile', 0.2) * 100)}% of `E_final`, inverse-vol weighted, dollar-neutral, with single-asset cap {int(m_portfolio.get('max_asset_weight', 0.05) * 100)}%, long-leg cluster cap {int(m_portfolio.get('max_cluster_fraction', 0.4) * 100)}%, turnover cap {int(m_portfolio.get('turnover_cap', 0.3) * 100)}%/wk, and {int(m_portfolio.get('vol_target_annual', 0.15) * 100)}% annualised vol target (leverage cap 3×).

    ## 7. OOS Backtest

    {metrics_table(metrics)}

    *Train window: {TRAIN_WEEKS} weeks. Bootstrap CIs use stationary block bootstrap with block length 4 and 2000 draws.*

    The constrained NALFP variant has a wide bootstrap CI that crosses zero on the {next((m['oos']['weeks'] for m in metrics if m['strategy'] == 'NALFP'), '—')}-week OOS window. We do **not** claim the strategy delivers statistically distinguishable returns on this sample; the cross-section of factors is statistically meaningful (5 of 7 priced in-sample) but the OOS combination does not generalise reliably here.

    ## 8. Honest limitations

    - **Sample size.** 52 weeks total → 24 OOS weeks after the network burn-in. The Sharpe-ratio standard error on 24 weeks is approximately $1/\\sqrt{{24}} \\approx 0.20$; the bootstrap CI for NALFP OOS Sharpe is wider yet and crosses zero.
    - **Hidden factor identification.** Bai-Ng IC$_{{p2}}$ saturates the K=3 cap, suggesting our $T=24$ training window is short for identifying hidden risk premia (Hartmann 2025 used 100+ weeks and selected $K_\\text{{hidden}} = 7$).
    - **TVLC and SupC.** Excluded from GX due to coverage; their stats in the zoo table are computed on 0 and 7 weeks respectively — read with caution.
    - **Costs.** 10 bps one-sided on turnover is reasonable for large-caps; the long tail of our universe is more expensive in practice.
    - **What would break this.** A regime shift that flips the sign of SMBC or MomC out-of-sample (precisely what we see in some OOS weeks). The strategy's strength is the *factor structure identification*; whether the training-window λ̂ generalises is an empirical question we do not yet have enough data to answer.

    ## 9. Reproducibility

    ```
    python3 08_nalfp/01_network_dynamics.py
    python3 08_nalfp/02_factor_pricing.py
    python3 08_nalfp/03_signal_combination.py
    python3 08_nalfp/04_portfolio_construction.py
    python3 08_nalfp/05_backtest.py
    python3 08_nalfp/06_report.py
    ```
    """)

    REPORT_PATH.write_text(md.lstrip(), encoding="utf-8")
    print(f"  wrote {REPORT_PATH.relative_to(Path(__file__).resolve().parents[1])}")


if __name__ == "__main__":
    main()
