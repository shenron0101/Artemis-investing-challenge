"""09 — FunC (Fees/Mcap) Factor Visualisation Pipeline.

FunC = fees per unit of market cap — the crypto equivalent of an earnings yield.
Goes long protocols earning the most fees relative to their valuation, short the least.

Universe note: Only ~37 symbols have fees data; coverage varies over time.

Grade: Economic-only — sound valuation rationale, but GX λ = +6.6%/yr (t = +0.40),
not statistically significant. No IC test run (fundamental factor).

Outputs
-------
    artifacts/figures/func_*.html / .png
    artifacts/data/func_viz_data.parquet
    FUNC_VIZ_REPORT.md
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats as sp_stats

STAGE = Path(__file__).resolve().parent
PARENT = STAGE.parent
DATA_DIR = STAGE / "artifacts" / "data"
MANIFEST_DIR = PARENT / "artifacts" / "manifests"
PANEL_DIR = PARENT / "artifacts" / "data"
FIG_DIR = STAGE / "artifacts" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

FACTOR_NAME = "FunC"
PREFIX = "func"
CHAR_COL = "fees_to_mcap"
DIRECTION = +1    # long high fees/mcap (top 30%), short low (bottom 30%)
FRAC = 0.30
MIN_NAMES = 5

IS_LABEL = "In-Sample (2021-05-10 → 2024-11-11)"
OOS_LABEL = "Out-of-Sample (2024-11-18 → 2026-05-25)"
PLOTLY_TEMPLATE = "plotly_white"
COLORS = {"IS": "#2196F3", "OOS": "#FF5722", "FULL": "#607D8B",
          "SIG_POS": "#4CAF50", "SIG_NEG": "#F44336"}

GX_LAMBDA = 6.6
GX_T = 0.40


def load_manifest():
    return json.loads((MANIFEST_DIR / "universe_manifest.json").read_text())


def build_factor_returns(fund, trade_symbols):
    fund = fund[fund["symbol"].isin(trade_symbols)].copy()

    def one_week(block):
        block = block.dropna(subset=["fwd_ret_1w", CHAR_COL])
        n = len(block)
        if n < MIN_NAMES:
            return np.nan
        k = max(int(round(n * FRAC)), 2)
        r = block[CHAR_COL].rank(method="first")
        long_m = r > n - k
        short_m = r <= k
        return float(block.loc[long_m, "fwd_ret_1w"].mean()
                     - block.loc[short_m, "fwd_ret_1w"].mean())

    return fund.groupby("week").apply(one_week).rename("ret")


def build_factor_ic(fund, trade_symbols):
    fund = fund[fund["symbol"].isin(trade_symbols)].copy()
    keep = fund.dropna(subset=["fwd_ret_1w", CHAR_COL])
    return keep.groupby("week").apply(
        lambda b: b[CHAR_COL].rank().corr(b["fwd_ret_1w"].rank())
        if len(b) >= MIN_NAMES else np.nan
    ).rename("ic")


def newey_west_se(arr, lags=4):
    r = np.asarray(arr, dtype=float)
    n = len(r)
    if n < 2:
        return np.nan
    e = r - r.mean()
    s = (e * e).mean()
    for lag in range(1, min(lags, n - 1) + 1):
        s += 2.0 * (1 - lag / (lags + 1)) * (e[lag:] * e[:-lag]).mean()
    return float(np.sqrt(max(s, 0.0) / n))


def rolling_stat(series, window, func):
    out = {}
    vals = series.dropna()
    for i in range(window, len(vals)):
        sub = vals.iloc[i - window:i]
        out[vals.index[i]] = func(sub)
    return pd.Series(out)


def _ts_str(v):
    return v.strftime("%Y-%m-%d") if isinstance(v, pd.Timestamp) else str(v)


def _add_vline(fig, x, annotation_text=None):
    xs = _ts_str(x)
    fig.add_shape(type="line", x0=xs, x1=xs, y0=0, y1=1,
                  xref="x", yref="paper", line=dict(dash="dash", color="#999", width=1))
    if annotation_text:
        fig.add_annotation(x=xs, y=1.02, xref="x", yref="paper",
                           text=annotation_text, showarrow=False, font=dict(size=10, color="#999"))


def _add_vrect(fig, x0, x1, fillcolor, opacity=0.05):
    fig.add_shape(type="rect", x0=_ts_str(x0), x1=_ts_str(x1), y0=0, y1=1,
                  xref="x", yref="paper", fillcolor=fillcolor, opacity=opacity, line=dict(width=0))


def chart_cumulative_return(ret, ic, is_lo, is_hi, oos_lo, oos_hi):
    cum = (1 + ret).cumprod()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=(f"{FACTOR_NAME} Cumulative Long/Short Return", "Weekly IC"))
    for lbl, lo, hi, color in [(IS_LABEL, is_lo, is_hi, COLORS["IS"]),
                                (OOS_LABEL, oos_lo, oos_hi, COLORS["OOS"])]:
        c = cum[(cum.index >= lo) & (cum.index <= hi)]
        if len(c) > 0:
            fig.add_trace(go.Scatter(x=c.index, y=c.values, name=lbl,
                                     line=dict(color=color, width=2)), row=1, col=1)
        ic_s = ic[(ic.index >= lo) & (ic.index <= hi)].dropna()
        if len(ic_s) > 0:
            fig.add_trace(go.Bar(x=ic_s.index, y=ic_s.values,
                                 marker_color=color, marker_opacity=0.5), row=2, col=1)
    for y, c in [(0, "#666"), (-0.03, COLORS["SIG_NEG"]), (0.03, COLORS["SIG_POS"])]:
        fig.add_hline(y=y, line_dash="dot", line_color=c, line_width=0.8, row=2, col=1)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=700,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_rolling_ic(ic, is_lo, is_hi, oos_lo, oos_hi):
    roll_ic = ic.rolling(26).mean().dropna()
    fig = go.Figure()
    if len(roll_ic) > 0:
        fig.add_trace(go.Scatter(x=roll_ic.index, y=roll_ic.values,
                                 name="26-week Rolling IC", line=dict(color=COLORS["FULL"], width=2)))
    fig.add_hline(y=0, line_dash="dash", line_color="#666")
    for y, c in [(0.03, COLORS["SIG_POS"]), (-0.03, COLORS["SIG_NEG"])]:
        fig.add_hline(y=y, line_dash="dot", line_color=c)
    _add_vrect(fig, is_lo, is_hi, fillcolor=COLORS["IS"])
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"])
    _add_vline(fig, is_hi, annotation_text="IS / OOS")
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500,
                      title=f"{FACTOR_NAME} 26-Week Rolling Mean IC",
                      xaxis_title="Week", yaxis_title="Rolling Mean IC")
    return fig


def chart_return_distribution(ret, is_lo, is_hi, oos_lo, oos_hi):
    is_r = ret[(ret.index >= is_lo) & (ret.index <= is_hi)].dropna()
    oos_r = ret[(ret.index >= oos_lo) & (ret.index <= oos_hi)].dropna()

    def desc(s):
        if len(s) == 0:
            return {}
        se = newey_west_se(s.values, 4)
        return dict(n=len(s), mean=s.mean(), std=s.std(),
                    skew=s.skew(), kurt=s.kurtosis(),
                    sharpe=float(s.mean() / s.std() * np.sqrt(52)) if s.std() > 0 else np.nan,
                    min=s.min(), p25=s.quantile(0.25), median=s.median(),
                    p75=s.quantile(0.75), max=s.max())

    is_d = desc(is_r)
    oos_d = desc(oos_r)
    fig = make_subplots(rows=2, cols=2,
                        subplot_titles=("Return Histogram (IS)", "Return Histogram (OOS)",
                                        "Return Box Plot", "Autocorrelation"),
                        vertical_spacing=0.12, horizontal_spacing=0.10)
    for (r, c_i), series, color, label in [((1, 1), is_r, COLORS["IS"], "IS"),
                                             ((1, 2), oos_r, COLORS["OOS"], "OOS")]:
        if len(series) > 0:
            bins = np.histogram(series, bins=30, density=True)
            fig.add_trace(go.Bar(x=bins[1][:-1], y=bins[0], name=label,
                                 marker_color=color, marker_opacity=0.7), row=r, col=c_i)
    for series, color, name in [(is_r, COLORS["IS"], "IS"), (oos_r, COLORS["OOS"], "OOS")]:
        if len(series) > 0:
            fig.add_trace(go.Box(y=series.values, name=name,
                                 marker_color=color, boxmean="sd"), row=2, col=1)
    ref = oos_r if len(is_r) == 0 else is_r
    if len(ref) > 5:
        acf_vals = [ref.autocorr(lag=l) for l in range(1, 13)]
        fig.add_trace(go.Bar(x=list(range(1, 13)), y=acf_vals,
                             marker_color=COLORS["FULL"], marker_opacity=0.7), row=2, col=2)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=800, showlegend=False)
    return fig, is_d, oos_d


def chart_rolling_sharpe(ret, is_lo, is_hi, oos_lo, oos_hi):
    roll_sr = rolling_stat(ret, 52,
                           lambda s: s.mean() / s.std() * np.sqrt(52) if s.std() > 0 else np.nan)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=roll_sr.index, y=roll_sr.dropna().values,
                             line=dict(color=COLORS["FULL"], width=2)))
    fig.add_hline(y=0, line_dash="dash", line_color="#666")
    fig.add_hline(y=1, line_dash="dot", line_color=COLORS["SIG_POS"], annotation_text="Sharpe = 1")
    fig.add_hline(y=-1, line_dash="dot", line_color=COLORS["SIG_NEG"], annotation_text="Sharpe = −1")
    _add_vrect(fig, is_lo, is_hi, fillcolor=COLORS["IS"])
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"])
    _add_vline(fig, is_hi, annotation_text="IS / OOS")
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500,
                      title=f"{FACTOR_NAME} 52-Week Rolling Sharpe",
                      xaxis_title="Week", yaxis_title="Annualised Sharpe")
    return fig


def chart_qq_plot(ret, is_lo, is_hi, oos_lo, oos_hi):
    is_r = ret[(ret.index >= is_lo) & (ret.index <= is_hi)].dropna().sort_values()
    oos_r = ret[(ret.index >= oos_lo) & (ret.index <= oos_hi)].dropna().sort_values()
    fig = make_subplots(rows=1, cols=2, subplot_titles=("QQ — IS", "QQ — OOS"))
    for col_i, series, color in [(1, is_r, COLORS["IS"]), (2, oos_r, COLORS["OOS"])]:
        if len(series) > 1:
            n = len(series)
            t = sp_stats.norm.ppf(np.arange(1, n + 1) / (n + 1)) * series.std() + series.mean()
            s = series.values
            fig.add_trace(go.Scatter(x=t, y=s, mode="markers",
                                     marker=dict(color=color, size=5, opacity=0.7)), row=1, col=col_i)
            lo, hi = min(t.min(), s.min()), max(t.max(), s.max())
            fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines",
                                     line=dict(color="#999", dash="dash")), row=1, col=col_i)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, showlegend=False)
    return fig


def chart_tercile_returns(fund, trade_symbols, is_lo, is_hi, oos_lo, oos_hi):
    fund = fund[fund["symbol"].isin(trade_symbols)].copy()
    fund = fund.dropna(subset=[CHAR_COL, "fwd_ret_1w"])
    t_labels = ["Low-Fees", "Mid-Fees", "High-Fees"]
    fund["tercile"] = fund.groupby("week")[CHAR_COL].transform(
        lambda x: pd.qcut(x, 3, labels=t_labels, duplicates="drop")
        if len(x.dropna()) >= 4 else pd.NA)
    tr = fund.dropna(subset=["tercile"]).groupby(["week", "tercile"])["fwd_ret_1w"].mean()
    pivot = tr.reset_index().pivot(index="week", columns="tercile", values="fwd_ret_1w")
    for lb in t_labels:
        if lb not in pivot.columns:
            pivot[lb] = np.nan
    pivot = pivot[t_labels].dropna()
    spread = pivot[t_labels[-1]] - pivot[t_labels[0]]

    def ann(s):
        return (1 + s).prod() ** (52 / max(len(s), 1)) - 1 if len(s) > 0 else np.nan

    groups = {"IS": (is_lo, is_hi), "OOS": (oos_lo, oos_hi),
              "Full": (pivot.index.min(), pivot.index.max())}
    bars = {}
    for nm, (lo, hi) in groups.items():
        sub = pivot[(pivot.index >= lo) & (pivot.index <= hi)]
        sp = spread[(spread.index >= lo) & (spread.index <= hi)]
        bars[nm] = [ann(sub[lb]) * 100 if lb in sub else np.nan for lb in t_labels] + [ann(sp) * 100]

    fig = go.Figure(data=[
        go.Bar(name="IS", x=t_labels + ["FunC Spread"], y=bars["IS"],
               marker_color=COLORS["IS"], marker_opacity=0.8),
        go.Bar(name="OOS", x=t_labels + ["FunC Spread"], y=bars["OOS"],
               marker_color=COLORS["OOS"], marker_opacity=0.8),
        go.Bar(name="Full", x=t_labels + ["FunC Spread"], y=bars["Full"],
               marker_color=COLORS["FULL"], marker_opacity=0.5),
    ])
    fig.update_layout(template=PLOTLY_TEMPLATE, height=550, barmode="group",
                      title=f"{FACTOR_NAME} Fees/Mcap Tercile Returns (~37 symbols)",
                      xaxis_title="Fees/Mcap Group", yaxis_title="Annualised Return (%)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_is_oos_metrics(ret, ic, is_lo, is_hi, oos_lo, oos_hi):
    def metrics(r, ic_s):
        if len(r) == 0:
            return [np.nan] * 5
        se = newey_west_se(r.values, 4)
        ic_mean = ic_s.mean() if len(ic_s) > 0 else np.nan
        ic_se = newey_west_se(ic_s.values, 4) if len(ic_s) > 0 else np.nan
        ic_t = float(ic_s.mean() / ic_se) if ic_se and ic_se > 0 else np.nan
        sharpe = float(r.mean() / r.std() * np.sqrt(52)) if r.std() > 0 else np.nan
        ann_ret = (1 + r).prod() ** (52 / len(r)) - 1 if len(r) > 0 else np.nan
        return [ic_mean, ic_t, sharpe, ann_ret, r.mean()]

    is_r = ret[(ret.index >= is_lo) & (ret.index <= is_hi)].dropna()
    oos_r = ret[(ret.index >= oos_lo) & (ret.index <= oos_hi)].dropna()
    is_ic = ic[(ic.index >= is_lo) & (ic.index <= is_hi)].dropna()
    oos_ic = ic[(ic.index >= oos_lo) & (ic.index <= oos_hi)].dropna()

    labels = ["IC", "IC t-stat", "Sharpe", "Ann. Return", "Mean Wkly Ret"]
    fig = go.Figure(data=[
        go.Bar(name="In-Sample", x=labels, y=metrics(is_r, is_ic),
               marker_color=COLORS["IS"], marker_opacity=0.8),
        go.Bar(name="Out-of-Sample", x=labels, y=metrics(oos_r, oos_ic),
               marker_color=COLORS["OOS"], marker_opacity=0.8),
    ])
    fig.add_hline(y=0, line_dash="dash", line_color="#666")
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, barmode="group",
                      title=f"{FACTOR_NAME} Factor: IS vs OOS Dashboard",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_cumulative_tercile(fund, trade_symbols, is_lo, is_hi, oos_lo, oos_hi):
    fund = fund[fund["symbol"].isin(trade_symbols)].copy()
    fund = fund.dropna(subset=[CHAR_COL, "fwd_ret_1w"])
    t_labels = ["Low-Fees", "Mid-Fees", "High-Fees"]
    fund["tercile"] = fund.groupby("week")[CHAR_COL].transform(
        lambda x: pd.qcut(x, 3, labels=t_labels, duplicates="drop")
        if len(x.dropna()) >= 4 else pd.NA)
    fund = fund.dropna(subset=["tercile"])
    tr = fund.groupby(["week", "tercile"])["fwd_ret_1w"].mean().reset_index()
    pivot = tr.pivot(index="week", columns="tercile", values="fwd_ret_1w")
    for lb in t_labels:
        if lb not in pivot.columns:
            pivot[lb] = np.nan
    pivot = pivot[t_labels].sort_index().fillna(0)
    cum = (1 + pivot).cumprod()
    colors_t = {t_labels[0]: "#4CAF50", t_labels[1]: "#FF9800", t_labels[-1]: "#F44336"}
    fig = go.Figure()
    for lb, color in colors_t.items():
        fig.add_trace(go.Scatter(x=cum.index, y=cum[lb], name=lb, line=dict(color=color, width=2)))
    spread_cum = (1 + (pivot[t_labels[-1]] - pivot[t_labels[0]])).cumprod()
    fig.add_trace(go.Scatter(x=spread_cum.index, y=spread_cum.values, name="FunC Spread",
                             line=dict(color="#000", width=2.5, dash="dash")))
    _add_vline(fig, is_hi)
    _add_vrect(fig, is_lo, is_hi, fillcolor=COLORS["IS"], opacity=0.04)
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"], opacity=0.04)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=550,
                      title=f"Cumulative Return by Fees/Mcap Tercile (~37 symbols)",
                      xaxis_title="Week", yaxis_title="Growth of $1",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_fees_yield_over_time(fund, trade_symbols, is_lo, is_hi, oos_lo, oos_hi):
    """Chart 9 (FunC-specific): Median fees/mcap for top vs bottom tercile over time.
    Shows whether the 'earnings yield' spread is growing or narrowing in crypto."""
    fund = fund[fund["symbol"].isin(trade_symbols)].copy()
    fund = fund.dropna(subset=[CHAR_COL])
    fund["group"] = fund.groupby("week")[CHAR_COL].transform(
        lambda x: pd.qcut(x, [0, 0.3, 0.7, 1.0], labels=["Low-Fees", "Mid-Fees", "High-Fees"],
                          duplicates="drop")
        if len(x.dropna()) >= 4 else pd.NA)
    fund = fund.dropna(subset=["group"])
    avg = fund.groupby(["week", "group"])[CHAR_COL].median().reset_index()
    pivot = avg.pivot(index="week", columns="group", values=CHAR_COL)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("Median Fees/Mcap by Tercile Over Time",
                                        "Fees/Mcap Spread (High Fees − Low Fees) — Opportunity"))
    for grp, color in [("Low-Fees", "#4CAF50"), ("High-Fees", "#F44336")]:
        if grp in pivot.columns:
            s = pivot[grp].rolling(4).mean().dropna()
            fig.add_trace(go.Scatter(x=s.index, y=s.values * 100, name=grp,
                                     line=dict(color=color, width=2)), row=1, col=1)
    if "High-Fees" in pivot.columns and "Low-Fees" in pivot.columns:
        spread = (pivot["High-Fees"] - pivot["Low-Fees"]).rolling(4).mean().dropna()
        fig.add_trace(go.Scatter(x=spread.index, y=spread.values * 100,
                                 name="Spread", fill="tozeroy",
                                 line=dict(color=COLORS["FULL"], width=2)), row=2, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="#666", row=2, col=1)
    _add_vline(fig, is_hi, annotation_text="IS / OOS")
    _add_vrect(fig, is_lo, is_hi, fillcolor=COLORS["IS"])
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"])
    fig.update_layout(template=PLOTLY_TEMPLATE, height=700,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Fees/Mcap (%) median", row=1, col=1)
    fig.update_yaxes(title_text="Spread (% annual)", row=2, col=1)
    return fig


def fmt_val(v, fmt=".2f"):
    if isinstance(v, float) and np.isfinite(v):
        return f"{v:{fmt}}"
    return "N/A"


def write_report(is_d, oos_d, adf_stat, adf_p, n_symbols):
    md = f"""# FunC (Fees/Mcap) Factor — Analysis Report

*Generated by `20_func_visualisation.py` from the Stage-09 5-year panel.*

*Universe note: Only ~{n_symbols} symbols have fees data (vs ~113 in the full universe).
Results are less stable than price-based factors.*

---

## The Idea in Plain English

In the stock market, a company with a **low P/E ratio** (price divided by earnings) is
considered cheap — you're paying little for each dollar of profit. The same logic
applies to DeFi protocols: a protocol that generates lots of fees relative to its
market capitalisation is essentially "cheap on earnings."

**FunC** (Fundamental Crypto) uses the **fees-to-market-cap ratio** as a value signal:
- **Buy** protocols earning the most fees per dollar of market cap (top 30%)
- **Short** protocols earning the least (bottom 30%)

The idea: the market will eventually recognise that highly profitable protocols are
undervalued and re-rate them upward.

---

## The Short Answer

**Economic-only — compelling theory, inconclusive data.**

The GX pricing model finds λ = **+{GX_LAMBDA:.1f}%/yr, t = +{GX_T:.2f}** — directionally
positive (high fees/mcap earns more), but not statistically significant. The
"crypto value" factor exists in theory but cannot be confirmed on the available data.

The main constraints are coverage and data quality: only ~{n_symbols} symbols have
usable fees data, and protocol fees are often lumpy and seasonal, adding noise that
makes weekly signals unreliable.

---

## The Economic Case (Why It Should Work)

**1. The equity market value premium analogue.**
High earnings yield (E/P) stocks historically outperform low E/P stocks in equities.
If DeFi protocol fees are analogous to corporate earnings, the same mechanism should
apply. The DeFi market would be "inefficient" at pricing in fundamentals.

**2. Fees proxy real usage and economic value.**
A protocol that generates real fees (not incentivised emissions, not wash trading) has
genuine product-market fit. Over time, real usage should be recognised and re-priced.

**3. The competition explicitly rewards fundamental factors.**
The research design rule from the 10-paper review: "Use quality-adjusted Artemis metrics.
Prefer fees/mcap over TVL." FunC is the direct implementation of this rule.

---

## Why It Hasn't Worked Yet

**1. Only ~{n_symbols} protocols have usable fees data (< 1/3 of the universe).**
The signal is computed over a very thin cross-section. With so few assets per week,
the statistical power to detect a real premium is severely limited.

**2. DeFi fees are lumpy and seasonal.**
Many protocols have fee spikes during high-activity events (airdrops, governance votes,
bull market surges) that don't predict future returns — they just inflate the current
fees/mcap temporarily.

**3. Fee inflation from token emission programmes.**
"Fees" in some protocols include token rewards that are not real economic value. This
contaminates the signal (see Research Design Rule 1: "TVL alone is not alpha; use
quality-adjusted metrics").

**4. The observation window may be too short.**
Value premiums in equity markets took decades to confirm statistically. The 5-year
crypto panel may simply not yet have enough observations to establish significance.

---

## Return Distribution

| Statistic | IS | OOS |
|---|---|---|
| Mean weekly return | {fmt_val(is_d.get('mean', np.nan)*100, '.3f')}% | {fmt_val(oos_d.get('mean', np.nan)*100, '.3f')}% |
| Std (weekly) | {fmt_val(is_d.get('std', np.nan)*100, '.3f')}% | {fmt_val(oos_d.get('std', np.nan)*100, '.3f')}% |
| Skewness | {fmt_val(is_d.get('skew', np.nan), '.2f')} | {fmt_val(oos_d.get('skew', np.nan), '.2f')} |
| Excess Kurtosis | {fmt_val(is_d.get('kurt', np.nan), '.2f')} | {fmt_val(oos_d.get('kurt', np.nan), '.2f')} |

---

## Statistical Tests

### Giglio-Xiu Pricing Result

Full GX (K_hidden = 2): **λ = +{GX_LAMBDA:.1f}%/yr, t = +{GX_T:.2f}** — not significant.
Directionally positive but underpowered. With a larger universe and longer history,
this might achieve significance. Today it cannot.

### ADF Stationarity Test

- ADF: **{fmt_val(adf_stat, '.3f')}**, p = **{fmt_val(adf_p, '.4f')}**
- **{"Stationary" if adf_p < 0.05 else "Non-stationary"}**

---

## Visualisations

### Cumulative Return & Weekly IC

![Cumulative return](artifacts/figures/{PREFIX}_01_cumulative_return.png)

### Rolling Mean IC

![Rolling IC](artifacts/figures/{PREFIX}_02_rolling_ic.png)

### Return Distribution

![Return distribution](artifacts/figures/{PREFIX}_03_return_distribution.png)

### Rolling Sharpe Ratio

![Rolling Sharpe](artifacts/figures/{PREFIX}_04_rolling_sharpe.png)

### QQ-Plot vs Normal Distribution

![QQ plot](artifacts/figures/{PREFIX}_05_qq_plot.png)

### Fees/Mcap Tercile Returns

![Tercile returns](artifacts/figures/{PREFIX}_06_tercile_returns.png)

### IS vs OOS Dashboard

![IS vs OOS](artifacts/figures/{PREFIX}_07_is_oos.png)

### Cumulative Return by Fees/Mcap Tercile

![Cumulative tercile](artifacts/figures/{PREFIX}_08_cumulative_tercile.png)

### Fees/Mcap Yield Spread Over Time

![Fees yield over time](artifacts/figures/{PREFIX}_09_fees_yield.png)

The top panel shows median fees/mcap for the high-fee and low-fee terciles over time.
The bottom panel shows the spread — when it is wide, there is more cross-sectional
variation in protocol earnings, and the factor has more "information" to work with.
Periods of wide spread are the most important for assessing whether the value premium
is real.
"""
    (STAGE / "FUNC_VIZ_REPORT.md").write_text(md)
    print("  wrote FUNC_VIZ_REPORT.md")


def main():
    print("Loading data...")
    man = load_manifest()
    trade = set(man["trading_universe"]["symbols_ever_eligible"])
    is_lo = pd.Timestamp(man["split"]["in_sample"][0])
    is_hi = pd.Timestamp(man["split"]["in_sample"][1])
    oos_lo = pd.Timestamp(man["split"]["out_of_sample"][0])
    oos_hi = pd.Timestamp(man["split"]["out_of_sample"][1])

    fund = pd.read_parquet(PANEL_DIR / "fundamentals_weekly.parquet")
    fund["week"] = pd.to_datetime(fund["week"])

    panel = pd.read_parquet(PANEL_DIR / "price_mcap_panel_weekly.parquet")
    panel["week"] = pd.to_datetime(panel["week"])
    panel = panel[panel["symbol"].isin(trade)]
    px_wide = panel.pivot(index="week", columns="symbol", values="price").sort_index()
    ret_wide = px_wide.pct_change()
    fwd_ret = ret_wide.shift(-1)
    fwd_long = fwd_ret.reset_index().melt(id_vars="week", var_name="symbol", value_name="fwd_ret_1w")
    fund = fund.merge(fwd_long, on=["week", "symbol"], how="left")

    n_symbols = fund["symbol"].nunique()
    print(f"Fundamentals universe: {n_symbols} symbols")

    factor_ret = build_factor_returns(fund, trade)
    factor_ic = build_factor_ic(fund, trade)
    factor_ret.index = pd.to_datetime(factor_ret.index)
    factor_ic.index = pd.to_datetime(factor_ic.index)

    print("Generating charts...")
    fig1 = chart_cumulative_return(factor_ret, factor_ic, is_lo, is_hi, oos_lo, oos_hi)
    fig2 = chart_rolling_ic(factor_ic, is_lo, is_hi, oos_lo, oos_hi)
    fig3, is_d, oos_d = chart_return_distribution(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig4 = chart_rolling_sharpe(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig5 = chart_qq_plot(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig6 = chart_tercile_returns(fund, trade, is_lo, is_hi, oos_lo, oos_hi)
    fig7 = chart_is_oos_metrics(factor_ret, factor_ic, is_lo, is_hi, oos_lo, oos_hi)
    fig8 = chart_cumulative_tercile(fund, trade, is_lo, is_hi, oos_lo, oos_hi)
    fig9 = chart_fees_yield_over_time(fund, trade, is_lo, is_hi, oos_lo, oos_hi)

    charts = [
        (f"{PREFIX}_01_cumulative_return", fig1),
        (f"{PREFIX}_02_rolling_ic", fig2),
        (f"{PREFIX}_03_return_distribution", fig3),
        (f"{PREFIX}_04_rolling_sharpe", fig4),
        (f"{PREFIX}_05_qq_plot", fig5),
        (f"{PREFIX}_06_tercile_returns", fig6),
        (f"{PREFIX}_07_is_oos", fig7),
        (f"{PREFIX}_08_cumulative_tercile", fig8),
        (f"{PREFIX}_09_fees_yield", fig9),
    ]
    for name, fig in charts:
        fig.write_html(str(FIG_DIR / f"{name}.html"))
        fig.write_image(str(FIG_DIR / f"{name}.png"), scale=2)
        print(f"  saved {name}.png")

    pd.DataFrame({"ret": factor_ret, "ic": factor_ic}).to_parquet(
        DATA_DIR / f"{PREFIX}_viz_data.parquet")

    is_r = factor_ret[(factor_ret.index >= is_lo) & (factor_ret.index <= is_hi)].dropna()
    oos_r = factor_ret[(factor_ret.index >= oos_lo) & (factor_ret.index <= oos_hi)].dropna()
    from statsmodels.tsa.stattools import adfuller
    try:
        adf = adfuller(factor_ret.dropna(), autolag="AIC")
        adf_stat, adf_p = adf[0], adf[1]
    except Exception:
        adf_stat, adf_p = np.nan, np.nan

    write_report(is_d, oos_d, adf_stat, adf_p, n_symbols)
    print(f"\nAll done. Charts in {FIG_DIR}")


if __name__ == "__main__":
    main()
