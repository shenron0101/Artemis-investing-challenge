#!/usr/bin/env python3
"""
Stage 13 — RCFP report + head-to-head comparison
================================================

Combines Plan A (economic classifier) and Plan B (HMM) results, compares them
against benchmarks (equal-weight market, NALFP v3), and writes RCFP_REPORT.md
with Plotly figures:

  * cumulative net return (both plans + benchmarks)
  * Plan A regime timeline + Plan B soft state-probability stacked area
  * per-regime factor-IC attribution (both plans)
  * factor-weight evolution

Run after a01/a02 and b01/b02.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import _rcfp_common as C

PLOTLY_TEMPLATE = "plotly_white"
COL = {"A": "#2196F3", "B": "#7B1FA2", "EW": "#FF9800", "NALFP": "#4CAF50",
       "RiskOn": "#4CAF50", "Neutral": "#FF9800", "RiskOff": "#F44336"}


def ew_market_benchmark() -> pd.DataFrame:
    rets = C.load_returns()
    rets["fwd_ret"] = rets.groupby("symbol")["ret"].shift(-1)
    return (rets.dropna(subset=["fwd_ret"]).groupby("week")["fwd_ret"]
            .mean().rename("pnl_net").reset_index())


def metrics_on(weeks_pnl: pd.DataFrame, lo, hi) -> dict:
    sub = weeks_pnl[(weeks_pnl["week"] >= lo) & (weeks_pnl["week"] <= hi)]
    return C.perf_metrics(sub.set_index("week")["pnl_net"])


def fig_cumulative(series: dict, first_oos) -> go.Figure:
    fig = go.Figure()
    for name, (df, color) in series.items():
        s = df.sort_values("week").set_index("week")["pnl_net"]
        cum = (1 + s).cumprod()
        fig.add_trace(go.Scatter(x=cum.index, y=cum.values, name=name,
                                 line=dict(color=color, width=2)))
    fig.add_vline(x=first_oos.strftime("%Y-%m-%d"), line_dash="dash",
                  line_color="#999", annotation_text="IS / OOS")
    fig.update_layout(template=PLOTLY_TEMPLATE, height=560,
                      title="RCFP cumulative net return vs benchmarks (log scale)",
                      yaxis_type="log", xaxis_title="Week",
                      yaxis_title="Growth of $1 (net)",
                      legend=dict(orientation="h", y=1.02, x=1, xanchor="right"))
    return fig


def fig_regime_timeline(reg_a: pd.DataFrame, reg_b: pd.DataFrame) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                        subplot_titles=("Plan A — regime score (RS) & label",
                                        "Plan B — HMM soft state probabilities"))
    fig.add_trace(go.Scatter(x=reg_a["week"], y=reg_a["rs"], name="RS",
                             line=dict(color="#333", width=1.5)), row=1, col=1)
    fig.add_hline(y=0.5, line_dash="dot", line_color=COL["RiskOn"], row=1, col=1)
    fig.add_hline(y=-0.5, line_dash="dot", line_color=COL["RiskOff"], row=1, col=1)
    for reg in C.REGIMES:
        fig.add_trace(go.Scatter(x=reg_b["week"], y=reg_b[f"p_{reg}"], name=reg,
                                 stackgroup="one", line=dict(width=0.5,
                                 color=COL[reg])), row=2, col=1)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=640,
                      legend=dict(orientation="h", y=1.02, x=1, xanchor="right"))
    fig.update_yaxes(title_text="RS", row=1, col=1)
    fig.update_yaxes(title_text="P(state)", row=2, col=1)
    return fig


def fig_factor_weights(tag: str, title: str) -> go.Figure:
    fw = pd.read_parquet(C.DATA_OUT / f"{tag}_factor_weights.parquet")
    fw["week"] = pd.to_datetime(fw["week"])
    fw = fw.sort_values("week")
    fig = go.Figure()
    for fac in C.FACTORS:
        if fac in fw.columns:
            fig.add_trace(go.Scatter(x=fw["week"], y=fw[fac], name=fac,
                                     stackgroup="one", line=dict(width=0.5)))
    fig.update_layout(template=PLOTLY_TEMPLATE, height=520, title=title,
                      yaxis_title="Factor weight (sums to 1)",
                      legend=dict(orientation="h", y=1.02, x=1, xanchor="right"))
    return fig


def fmt(d: dict) -> str:
    return (f"{d['sharpe']:+.2f} | {d['ann_return']:+.1%} | {d['ann_vol']:.1%} | "
            f"{d['max_dd']:+.1%} | {d['hit_rate']:.0%} | {d['weeks']}")


def main() -> None:
    a_pnl = pd.read_parquet(C.DATA_OUT / "a_weekly_pnl.parquet")
    b_pnl = pd.read_parquet(C.DATA_OUT / "b_weekly_pnl.parquet")
    a_pnl["week"] = pd.to_datetime(a_pnl["week"])
    b_pnl["week"] = pd.to_datetime(b_pnl["week"])
    ew = ew_market_benchmark()
    nalfp = C.load_nalfp_benchmark()

    reg_a = pd.read_parquet(C.DATA_OUT / "a_regime_panel.parquet")
    reg_b = pd.read_parquet(C.DATA_OUT / "b_regime_panel.parquet")
    reg_a["week"] = pd.to_datetime(reg_a["week"])
    reg_b["week"] = pd.to_datetime(reg_b["week"])

    # Common evaluation window across the strategies for a fair comparison
    weeks = sorted(set(a_pnl["week"]) & set(b_pnl["week"]))
    lo, hi = weeks[0], weeks[-1]
    first_oos = pd.to_datetime(weeks[-C.OOS_WEEKS]) if len(weeks) > C.OOS_WEEKS else weeks[len(weeks)//2]

    series = {"Plan A (economic)": (a_pnl, COL["A"]),
              "Plan B (HMM)": (b_pnl, COL["B"]),
              "EW market": (ew, COL["EW"])}
    if nalfp is not None:
        series["NALFP v3"] = (nalfp, COL["NALFP"])

    fig1 = fig_cumulative(series, first_oos)
    fig2 = fig_regime_timeline(reg_a, reg_b)
    fig3 = fig_factor_weights("a", "Plan A — regime-activated factor weights")
    fig4 = fig_factor_weights("b", "Plan B — HMM soft factor weights")
    for fig, name in ((fig1, "c01_cumulative"), (fig2, "c02_regime_timeline"),
                      (fig3, "c03_factor_weights_A"), (fig4, "c04_factor_weights_B")):
        fig.write_html(str(C.FIG_OUT / f"{name}.html"), include_plotlyjs="cdn")
        print(f"  wrote figures/{name}.html")

    # comparison tables (full window + OOS window, on the shared weeks)
    def block(df):
        d = df[(df["week"] >= lo) & (df["week"] <= hi)]
        full = C.perf_metrics(d.set_index("week")["pnl_net"])
        oos = metrics_on(df, first_oos, hi)
        return full, oos

    rows_full, rows_oos = {}, {}
    for name, (df, _) in series.items():
        rows_full[name], rows_oos[name] = block(df)

    ic_a = pd.read_csv(C.TABLE_OUT / "a_regime_ic_attribution.csv", index_col=0)
    ic_b = pd.read_csv(C.TABLE_OUT / "b_regime_ic_attribution.csv", index_col=0)

    def md_table(rows: dict) -> str:
        head = "| Strategy | Sharpe | AnnRet | AnnVol | MaxDD | Hit | Weeks |\n|---|---|---|---|---|---|---|\n"
        body = "".join(f"| {n} | {fmt(d)} |\n" for n, d in rows.items())
        return head + body

    def md_ic(tab: pd.DataFrame) -> str:
        cols = [c for c in C.REGIMES if c in tab.columns]
        head = "| Factor | " + " | ".join(cols) + " |\n|" + "---|" * (len(cols)+1) + "\n"
        body = ""
        for fac in C.FACTORS:
            if fac in tab.index:
                vals = " | ".join(f"{tab.loc[fac, c]:+.3f}" for c in cols)
                body += f"| {fac} | {vals} |\n"
        return head + body

    md = f"""# Stage 13 — Regime-Conditioned Factor Portfolio (RCFP)

*Generated by `c01_report.py`. Evaluation window {lo:%Y-%m-%d} → {hi:%Y-%m-%d};
IS/OOS split at {first_oos:%Y-%m-%d} (last {C.OOS_WEEKS} weeks OOS).*

## What this is

Two ways to make the 7 GX-confirmed factors (VOLC, MAXRET, CRASH8, BETA26,
NEWC, SKEW52, TVLC) regime-aware:

* **Plan A — economic classifier.** Regime score `RS = 0.5·CSD_z − 0.5·ΔBTCdom_z`
  (cross-sectional dispersion up, BTC-dominance falling ⇒ risk-on). Hard
  3-state label gates a factor-activation matrix.
* **Plan B — Gaussian HMM.** A 3-state HMM on `[CSD_z, ΔBTCdom_z, netentropy_z,
  mktmom_z]` produces soft state probabilities; the activation matrix is applied
  as a smooth convex blend. Refit on an expanding window every 4 weeks.

Both then weight factors by regime-activation × lagged rolling IC, build a
dollar-neutral quintile L/S book (inverse-vol, 5% asset cap, 40% Louvain cluster
cap, 30% turnover budget) and scale gross exposure by regime
(100/80/60% risk-on/neutral/off).

## Full-window performance

{md_table(rows_full)}

## Out-of-sample performance

{md_table(rows_oos)}

## Per-regime factor-IC attribution — the validation that conditioning works

If the regime gating is economically real, the *behavioral* factors (BETA26,
SKEW52, NEWC) should earn positive IC in risk-on weeks and ≈0 / negative IC in
risk-off, while *defensive* factors (VOLC, CRASH8, TVLC) should hold up in
risk-off. Mean weekly IC by regime:

### Plan A (hard label)

{md_ic(ic_a)}

### Plan B (HMM argmax label)

{md_ic(ic_b)}

## Figures

* `artifacts/figures/c01_cumulative.html` — cumulative net return vs benchmarks
* `artifacts/figures/c02_regime_timeline.html` — Plan A RS + Plan B state probabilities
* `artifacts/figures/c03_factor_weights_A.html` — Plan A factor-weight evolution
* `artifacts/figures/c04_factor_weights_B.html` — Plan B factor-weight evolution

## Notes & honest caveats

* `mktmom_z` substitutes for the originally-planned `stable_inflow_z` (the 5-year
  panel does not carry stablecoin flows).
* MaxDD over the full 5-year window spans the 2022 bear; it is far larger than
  NALFP v3's 24-week −3.47% figure simply because the window is longer.
* The activation-matrix multipliers are economically motivated, not fit to data —
  the per-regime IC table is the post-hoc check that they point the right way.
"""
    (C.STAGE / "RCFP_REPORT.md").write_text(md)
    print("  wrote RCFP_REPORT.md")
    print("\n=== OOS comparison ===")
    print(md_table(rows_oos))


if __name__ == "__main__":
    main()
