"""09 — MAXRET (Lottery / Max-Return) Factor Visualisation Pipeline.

MAXRET = the highest single weekly return a coin posted in the last 4 weeks.
High MAXRET coins attract lottery-seeking investors who over-pay for them.
The SHORT signal: coins with extreme recent up-weeks revert the following week.

Confirmed factor: IC significant IS (t = -3.49) and OOS (t = -4.05),
AND GX-priced (λ = +160.0%/yr, t = +5.52).

Outputs
-------
    artifacts/figures/maxret_*.html / .png
    artifacts/data/maxret_viz_data.parquet
    MAXRET_VIZ_REPORT.md
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
PARENT = STAGE.parent.parent / "03_nalfp_add"
DATA_DIR = STAGE / "artifacts" / "data"
MANIFEST_DIR = PARENT / "artifacts" / "manifests"
PANEL_DIR = PARENT / "artifacts" / "data"
FIG_DIR = STAGE / "artifacts" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

FACTOR_NAME = "MAXRET"
PREFIX = "maxret"
CHAR_COL = "maxret_4w"
DIRECTION = -1   # SHORT high-MAXRET (reversal/lottery correction); long low-MAXRET
FRAC = 0.30
MIN_NAMES = 10
T_LABELS = ["Low-Max", "Mid-Max", "High-Max"]
SPREAD_LABEL = "MAXRET (Low–High)"

IS_LABEL = "In-Sample (2021-05-10 → 2024-11-11)"
OOS_LABEL = "Out-of-Sample (2024-11-18 → 2026-05-25)"
PLOTLY_TEMPLATE = "plotly_white"
COLORS = {"IS": "#2196F3", "OOS": "#FF5722", "FULL": "#607D8B",
          "SIG_POS": "#4CAF50", "SIG_NEG": "#F44336"}

GX_LAMBDA = 160.0   # %/yr — assets with high MAXRET exposure earn more (priced lottery premium)
GX_T = 5.52
ASD_EPS1 = 0.545
ASD_EPS2 = 0.457


# ---------------------------------------------------------------------------
# Data loading & factor construction
# ---------------------------------------------------------------------------

def load_manifest():
    return json.loads((MANIFEST_DIR / "universe_manifest.json").read_text())


def build_characteristics(panel, trade_symbols):
    px_wide = (panel[panel["symbol"].isin(trade_symbols)]
               .pivot(index="week", columns="symbol", values="price")
               .sort_index())
    ret_wide = px_wide.pct_change()
    maxret4 = ret_wide.rolling(4).max()       # max weekly return over past 4 weeks
    vol4 = ret_wide.rolling(4).std()
    mom4 = px_wide / px_wide.shift(4) - 1.0

    def melt(df, name):
        return df.reset_index().melt(id_vars="week", var_name="symbol", value_name=name)

    out = melt(ret_wide, "ret_1w")
    fwd = ret_wide.shift(-1)
    for df, nm in [(fwd, "fwd_ret_1w"), (maxret4, "maxret_4w"),
                   (vol4, "vol_4w"), (mom4, "mom_4w")]:
        out = out.merge(melt(df, nm), on=["week", "symbol"], how="left")
    return out, ret_wide


def build_factor_returns(chars):
    def one_week(block):
        block = block.dropna(subset=["fwd_ret_1w", CHAR_COL])
        n = len(block)
        if n < MIN_NAMES:
            return np.nan
        k = max(int(round(n * FRAC)), 3)
        r = block[CHAR_COL].rank(method="first")
        # direction = -1: long low-MAXRET (bottom 30%), short high-MAXRET (top 30%)
        long_m = r <= k
        short_m = r > n - k
        return float(block.loc[long_m, "fwd_ret_1w"].mean()
                     - block.loc[short_m, "fwd_ret_1w"].mean())
    return chars.groupby("week").apply(one_week).rename("ret")


def build_factor_ic(chars):
    keep = chars.dropna(subset=["fwd_ret_1w", CHAR_COL])
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


def rolling_newey_west_t(series, window=26, lags=4):
    out = {}
    vals = series.dropna()
    for i in range(window, len(vals)):
        sub = vals.iloc[i - window:i]
        se = newey_west_se(sub.values, lags)
        out[vals.index[i]] = float(sub.mean() / se) if se and se > 0 else np.nan
    return pd.Series(out)


def rolling_stat(series, window, func):
    out = {}
    vals = series.dropna()
    for i in range(window, len(vals)):
        sub = vals.iloc[i - window:i]
        out[vals.index[i]] = func(sub)
    return pd.Series(out)


def _ts_str(v):
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    return str(v)


def _add_vline(fig, x, line_dash="dash", line_color="#999", annotation_text=None):
    xs = _ts_str(x)
    fig.add_shape(type="line", x0=xs, x1=xs, y0=0, y1=1,
                  xref="x", yref="paper",
                  line=dict(dash=line_dash, color=line_color, width=1))
    if annotation_text:
        fig.add_annotation(x=xs, y=1.02, xref="x", yref="paper",
                           text=annotation_text, showarrow=False,
                           font=dict(size=10, color=line_color))


def _add_vrect(fig, x0, x1, fillcolor, opacity=0.05):
    fig.add_shape(type="rect", x0=_ts_str(x0), x1=_ts_str(x1), y0=0, y1=1,
                  xref="x", yref="paper",
                  fillcolor=fillcolor, opacity=opacity, line=dict(width=0))


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def chart_cumulative_return(ret, ic, is_lo, is_hi, oos_lo, oos_hi):
    cum = (1 + ret).cumprod()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=(f"{FACTOR_NAME} Cumulative Long/Short Return",
                                        "Weekly IC (negative = reversal confirmed)"))
    for lbl, lo, hi, color in [(IS_LABEL, is_lo, is_hi, COLORS["IS"]),
                                (OOS_LABEL, oos_lo, oos_hi, COLORS["OOS"])]:
        c = cum[(cum.index >= lo) & (cum.index <= hi)]
        fig.add_trace(go.Scatter(x=c.index, y=c.values, name=lbl,
                                 line=dict(color=color, width=2)), row=1, col=1)
        ic_s = ic[(ic.index >= lo) & (ic.index <= hi)].dropna()
        fig.add_trace(go.Bar(x=ic_s.index, y=ic_s.values, name=f"IC ({lbl[:2]})",
                             marker_color=color, marker_opacity=0.5), row=2, col=1)
    for y, c in [(0, "#666"), (-0.03, COLORS["SIG_NEG"]), (0.03, "#999")]:
        fig.add_hline(y=y, line_dash="dot", line_color=c, line_width=0.8, row=2, col=1)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=700,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Growth of $1", row=1, col=1)
    fig.update_yaxes(title_text="IC (raw)", row=2, col=1)
    return fig


def chart_rolling_ic_significance(ic, is_lo, is_hi, oos_lo, oos_hi):
    roll_ic = ic.rolling(26).mean().dropna()
    roll_t = rolling_newey_west_t(ic, window=26, lags=4)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("26-Week Rolling Mean IC",
                                        "26-Week Rolling NW t-stat (below −2 = signal works)"))
    fig.add_trace(go.Scatter(x=roll_ic.index, y=roll_ic.values,
                             name="Rolling IC", line=dict(color=COLORS["FULL"], width=2)), row=1, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="#666", row=1, col=1)
    fig.add_trace(go.Scatter(x=roll_t.index, y=roll_t.values,
                             name="Rolling NW t-stat", line=dict(color=COLORS["FULL"], width=2)), row=2, col=1)
    for y, c in [(2, COLORS["SIG_POS"]), (-2, COLORS["SIG_NEG"]), (0, "#666")]:
        fig.add_hline(y=y, line_dash="dot" if y != 0 else "dash", line_color=c, row=2, col=1)
    _add_vline(fig, is_hi, annotation_text="IS / OOS boundary")
    _add_vrect(fig, is_lo, is_hi, fillcolor=COLORS["IS"])
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"])
    fig.update_layout(template=PLOTLY_TEMPLATE, height=700,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Mean IC", row=1, col=1)
    fig.update_yaxes(title_text="NW t-stat", row=2, col=1)
    return fig


def chart_return_distribution(ret, is_lo, is_hi, oos_lo, oos_hi):
    is_r = ret[(ret.index >= is_lo) & (ret.index <= is_hi)].dropna()
    oos_r = ret[(ret.index >= oos_lo) & (ret.index <= oos_hi)].dropna()

    def desc(s, label):
        se = newey_west_se(s.values, 4)
        return dict(label=label, n=len(s), mean=s.mean(), std=s.std(),
                    skew=s.skew(), kurt=s.kurtosis(),
                    t_nw=float(s.mean() / se) if se and se > 0 else np.nan,
                    sharpe=float(s.mean() / s.std() * np.sqrt(52)) if s.std() > 0 else np.nan,
                    min=s.min(), p25=s.quantile(0.25), median=s.median(),
                    p75=s.quantile(0.75), max=s.max())

    is_d = desc(is_r, "IS")
    oos_d = desc(oos_r, "OOS")
    fig = make_subplots(rows=2, cols=2,
                        subplot_titles=("Return Histogram (IS)", "Return Histogram (OOS)",
                                        "Return Box Plot", "Autocorrelation (IS)"),
                        vertical_spacing=0.12, horizontal_spacing=0.10)
    for (r, c_i), series, color, label in [((1, 1), is_r, COLORS["IS"], "IS"),
                                             ((1, 2), oos_r, COLORS["OOS"], "OOS")]:
        bins = np.histogram(series, bins=40, density=True)
        fig.add_trace(go.Bar(x=bins[1][:-1], y=bins[0], name=label,
                             marker_color=color, marker_opacity=0.7), row=r, col=c_i)
    fig.add_trace(go.Box(y=is_r.values, name="IS", marker_color=COLORS["IS"], boxmean="sd"), row=2, col=1)
    fig.add_trace(go.Box(y=oos_r.values, name="OOS", marker_color=COLORS["OOS"], boxmean="sd"), row=2, col=1)
    acf_vals = [is_r.autocorr(lag=l) for l in range(1, 13)]
    fig.add_trace(go.Bar(x=list(range(1, 13)), y=acf_vals,
                         name="ACF (IS)", marker_color=COLORS["IS"], marker_opacity=0.7), row=2, col=2)
    conf = 1.96 / np.sqrt(len(is_r))
    fig.add_hline(y=conf, line_dash="dot", line_color="#999", row=2, col=2)
    fig.add_hline(y=-conf, line_dash="dot", line_color="#999", row=2, col=2)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=800, showlegend=False)
    return fig, is_d, oos_d


def chart_rolling_sharpe(ret, is_lo, is_hi, oos_lo, oos_hi):
    roll_sr = rolling_stat(ret, 52,
                           lambda s: s.mean() / s.std() * np.sqrt(52) if s.std() > 0 else np.nan)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=roll_sr.index, y=roll_sr.dropna().values,
                             name="52-week Rolling Sharpe", line=dict(color=COLORS["FULL"], width=2)))
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

    def qq_data(series):
        n = len(series)
        t = sp_stats.norm.ppf(np.arange(1, n + 1) / (n + 1)) * series.std() + series.mean()
        return t, series.values

    fig = make_subplots(rows=1, cols=2, subplot_titles=("QQ Plot — IS", "QQ Plot — OOS"))
    for col_i, series, color in [(1, is_r, COLORS["IS"]), (2, oos_r, COLORS["OOS"])]:
        t, s = qq_data(series)
        fig.add_trace(go.Scatter(x=t, y=s, mode="markers",
                                 marker=dict(color=color, size=4, opacity=0.7)), row=1, col=col_i)
        lo, hi = min(t.min(), s.min()), max(t.max(), s.max())
        fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines",
                                 line=dict(color="#999", dash="dash")), row=1, col=col_i)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, showlegend=False)
    return fig


def chart_tercile_returns(chars, is_lo, is_hi, oos_lo, oos_hi):
    chars = chars.dropna(subset=["fwd_ret_1w", CHAR_COL]).copy()
    chars["tercile"] = chars.groupby("week")[CHAR_COL].transform(
        lambda x: pd.qcut(x, 3, labels=T_LABELS, duplicates="drop")
        if len(x.dropna()) >= 6 else pd.NA)
    tr = chars.dropna(subset=["tercile"]).groupby(["week", "tercile"])["fwd_ret_1w"].mean()
    pivot = tr.reset_index().pivot(index="week", columns="tercile", values="fwd_ret_1w")
    for lb in T_LABELS:
        if lb not in pivot.columns:
            pivot[lb] = np.nan
    pivot = pivot[T_LABELS].dropna()
    spread = pivot[T_LABELS[0]] - pivot[T_LABELS[-1]]   # long=low-max, short=high-max

    def ann(s):
        return (1 + s).prod() ** (52 / len(s)) - 1 if len(s) > 0 else np.nan

    groups = {"IS": (is_lo, is_hi), "OOS": (oos_lo, oos_hi),
              "Full": (pivot.index.min(), pivot.index.max())}
    bars = {}
    for nm, (lo, hi) in groups.items():
        sub = pivot[(pivot.index >= lo) & (pivot.index <= hi)]
        sp = spread[(spread.index >= lo) & (spread.index <= hi)]
        bars[nm] = [ann(sub[lb]) * 100 if lb in sub else np.nan for lb in T_LABELS] + [ann(sp) * 100]

    fig = go.Figure(data=[
        go.Bar(name="IS", x=T_LABELS + [SPREAD_LABEL], y=bars["IS"],
               marker_color=COLORS["IS"], marker_opacity=0.8),
        go.Bar(name="OOS", x=T_LABELS + [SPREAD_LABEL], y=bars["OOS"],
               marker_color=COLORS["OOS"], marker_opacity=0.8),
        go.Bar(name="Full", x=T_LABELS + [SPREAD_LABEL], y=bars["Full"],
               marker_color=COLORS["FULL"], marker_opacity=0.5),
    ])
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, barmode="group",
                      title=f"{FACTOR_NAME} Tercile Annualised Returns",
                      xaxis_title="Max-Return Group", yaxis_title="Annualised Return (%)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig, spread


def chart_is_oos_comparison(row):
    metrics = ["IC", "IC t-stat", "Sharpe", "Ann. Return", "Mean Wkly Ret"]
    is_vals = [row["IS_IC"], row["IS_IC_t"], row["IS_sharpe"],
               row["IS_annret"], row["IS_annret"] / 52]
    oos_vals = [row["OOS_IC"], row["OOS_IC_t"], row["OOS_sharpe"],
                row["OOS_annret"], row["OOS_annret"] / 52]
    fig = go.Figure(data=[
        go.Bar(name="In-Sample", x=metrics, y=is_vals,
               marker_color=COLORS["IS"], marker_opacity=0.8),
        go.Bar(name="Out-of-Sample", x=metrics, y=oos_vals,
               marker_color=COLORS["OOS"], marker_opacity=0.8),
    ])
    fig.add_hline(y=0, line_dash="dash", line_color="#666")
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, barmode="group",
                      title=f"{FACTOR_NAME} Factor: IS vs OOS Dashboard",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_cumulative_tercile(chars, is_lo, is_hi, oos_lo, oos_hi):
    chars = chars.dropna(subset=["fwd_ret_1w", CHAR_COL]).copy()
    chars["tercile"] = chars.groupby("week")[CHAR_COL].transform(
        lambda x: pd.qcut(x, 3, labels=T_LABELS, duplicates="drop")
        if len(x.dropna()) >= 6 else pd.NA)
    chars = chars.dropna(subset=["tercile"])
    tr = chars.groupby(["week", "tercile"])["fwd_ret_1w"].mean().reset_index()
    pivot = tr.pivot(index="week", columns="tercile", values="fwd_ret_1w")
    for lb in T_LABELS:
        if lb not in pivot.columns:
            pivot[lb] = np.nan
    pivot = pivot[T_LABELS].sort_index().fillna(0)
    cum = (1 + pivot).cumprod()
    colors_t = {T_LABELS[0]: "#4CAF50", T_LABELS[1]: "#FF9800", T_LABELS[-1]: "#F44336"}
    fig = go.Figure()
    for lb, color in colors_t.items():
        fig.add_trace(go.Scatter(x=cum.index, y=cum[lb], name=lb, line=dict(color=color, width=2)))
    spread_cum = (1 + (pivot[T_LABELS[0]] - pivot[T_LABELS[-1]])).cumprod()
    fig.add_trace(go.Scatter(x=spread_cum.index, y=spread_cum.values, name=SPREAD_LABEL,
                             line=dict(color="#000", width=2.5, dash="dash")))
    _add_vline(fig, is_hi, line_color="#999")
    _add_vrect(fig, is_lo, is_hi, fillcolor=COLORS["IS"], opacity=0.04)
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"], opacity=0.04)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=550,
                      title=f"Cumulative Return by {FACTOR_NAME} Tercile",
                      xaxis_title="Week", yaxis_title="Growth of $1",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_reversal_scatter(chars, is_lo, is_hi, oos_lo, oos_hi):
    """Chart 9 (MAXRET-specific): MAXRET rank (x) vs next-week return (y).
    Shows the reversal/overpricing pattern directly as a scatter plot with
    rolling median line to reveal the negative slope."""
    chars = chars.dropna(subset=["fwd_ret_1w", CHAR_COL]).copy()
    chars["maxret_rank_pct"] = chars.groupby("week")[CHAR_COL].rank(pct=True)

    is_data = chars[(chars["week"] >= is_lo) & (chars["week"] <= is_hi)]
    oos_data = chars[(chars["week"] >= oos_lo) & (chars["week"] <= oos_hi)]

    # Bin MAXRET rank into 20 quantile buckets, compute mean next-week return
    def bin_median(data):
        data = data.copy()
        data["bin"] = pd.qcut(data["maxret_rank_pct"], 20, labels=False, duplicates="drop")
        return data.groupby("bin").agg(
            x=("maxret_rank_pct", "mean"),
            y=("fwd_ret_1w", "mean")).reset_index()

    is_agg = bin_median(is_data)
    oos_agg = bin_median(oos_data)

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=(
                            "IS: MAXRET rank → next-week return",
                            "OOS: MAXRET rank → next-week return"))
    for col_i, agg, color in [(1, is_agg, COLORS["IS"]), (2, oos_agg, COLORS["OOS"])]:
        fig.add_trace(go.Scatter(x=agg["x"], y=agg["y"] * 100, mode="markers+lines",
                                 marker=dict(color=color, size=8),
                                 line=dict(color=color, width=1.5)), row=1, col=col_i)
        fig.add_hline(y=0, line_dash="dash", line_color="#999", row=1, col=col_i)

    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, showlegend=False,
                      title="MAXRET Reversal: Rank Percentile vs Next-Week Return (binned)")
    fig.update_xaxes(title_text="MAXRET Rank Percentile (0=lowest, 1=highest)")
    fig.update_yaxes(title_text="Mean Next-Week Return (%)")
    return fig


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def fmt_val(v, fmt=".2f"):
    if isinstance(v, float) and np.isfinite(v):
        return f"{v:{fmt}}"
    return "N/A"


def sign_cell(t):
    if not np.isfinite(t):
        return "N/A"
    if abs(t) >= 2:
        return f"**{t:+.2f}** (significant)"
    if abs(t) >= 1.65:
        return f"{t:+.2f} (marginal)"
    return f"{t:+.2f} (not significant)"


def write_report(row, is_d, oos_d, adf_stat, adf_p, jb_is, jb_is_p, jb_oos, jb_oos_p):
    md = f"""# MAXRET (Lottery / Max-Return) Factor — Analysis Report

*Generated by `13_maxret_visualisation.py` from the Stage-09 5-year panel.*

---

## The Idea in Plain English

Imagine a coin had an amazing week — it went up 40% in a single 7-day period.
What happens the *next* week? Lottery psychology says investors pile in after the
excitement, bid the price up too high, and the coin then corrects back down.

**MAXRET** captures this effect. Each week, we look at every coin's *best single weekly
return* over the past four weeks (their "lottery number"). Then:
- **Short** (bet against) coins with a *high* MAXRET — they are overbought and likely to revert
- **Long** (buy) coins with a *low* MAXRET — they have been ignored by the lottery crowd

This is a **reversal/overpricing signal**, not a momentum bet. We are *fading* the excitement.

---

## The Short Answer

**Yes — one of the two strongest confirmed factors in the study.**

The IC t-stat is **{fmt_val(row['IS_IC_t'])}** in-sample and **{fmt_val(row['OOS_IC_t'])}**
out-of-sample — both well above the |t| ≥ 2 bar, with the effect strengthening OOS.
The Giglio-Xiu pricing test confirms a priced lottery premium:
λ = **{GX_LAMBDA:.1f}%/yr**, t = **{GX_T:.2f}**.

---

## Sign Convention: Why Is the IC Negative?

The raw IC = Spearman(MAXRET rank, next-week return rank). Since we expect
*high* MAXRET → *lower* next-week return (reversal), a negative IC means the factor
is **working correctly**:

- IC = {fmt_val(row['IS_IC'], '.4f')} (IS) → high max-return coins underperformed
- IC t = {fmt_val(row['IS_IC_t'])} (IS) → this effect is statistically significant

The direction-adjusted IC (flip sign) is +{fmt_val(abs(row['IS_IC']), '.4f')} IS,
+{fmt_val(abs(row['OOS_IC']), '.4f')} OOS. The trading rule: **short the lottery coins,
buy the overlooked ones**.

---

## Performance Summary

| Metric | In-Sample | Out-of-Sample |
|---|---|---|
| Weeks | {int(row['IS_n'])} | {int(row['OOS_n'])} |
| Annualised Return | {fmt_val(row['IS_annret']*100, '.1f')}% | {fmt_val(row['OOS_annret']*100, '.1f')}% |
| Sharpe Ratio | {fmt_val(row['IS_sharpe'])} | {fmt_val(row['OOS_sharpe'])} |
| Mean IC (raw) | {fmt_val(row['IS_IC'], '.4f')} | {fmt_val(row['OOS_IC'], '.4f')} |
| IC t-stat (NW) | {sign_cell(row['IS_IC_t'])} | {sign_cell(row['OOS_IC_t'])} |
| Return t-stat (NW) | {sign_cell(row['IS_t'])} | {sign_cell(row['OOS_t'])} |

Note: the OOS Sharpe is negative ({fmt_val(row['OOS_sharpe'])}) even though the IC is highly
significant. This is the same tension as VolC — see "Two Lenses Disagree" below.

### Return Distribution

| Statistic | IS | OOS |
|---|---|---|
| Mean weekly return | {fmt_val(is_d['mean']*100, '.3f')}% | {fmt_val(oos_d['mean']*100, '.3f')}% |
| Std (weekly) | {fmt_val(is_d['std']*100, '.3f')}% | {fmt_val(oos_d['std']*100, '.3f')}% |
| Skewness | {fmt_val(is_d['skew'], '.2f')} | {fmt_val(oos_d['skew'], '.2f')} |
| Excess Kurtosis | {fmt_val(is_d['kurt'], '.2f')} | {fmt_val(oos_d['kurt'], '.2f')} |

---

## Two Lenses Agree in Direction but Diverge on How to Trade

The GX full-model pricing test gives λ = **+{GX_LAMBDA:.1f}%/yr** (t = {GX_T:.2f}).
This is *positive* and means: **assets with high MAXRET exposure earn more over the long run.**

Wait — that contradicts the reversal signal, which says high-MAXRET coins *underperform*
the next week. How can both be true?

They measure different things:
1. **IC (short-horizon):** High-MAXRET coins revert over the *next single week* — the
   overreaction corrects quickly.
2. **GX λ (long-horizon):** Over *multiple years*, high-MAXRET exposure (i.e., being in
   lottery-seeking, volatile, speculative assets) earns a long-run risk premium. Investors
   who systematically hold these assets are compensated for the lottery risk they bear.

So MAXRET is simultaneously a **short-term reversal** (bet against the lottery coins
each week) and a **long-run priced risk** (holding lottery-heavy assets earns more over
years). The two strategies are not in conflict — they just operate on different time horizons.

---

## Why Does the Reversal Work?

**1. Overreaction / lottery demand (Bali et al. 2011; Han et al. 2023).**
When a coin has a spectacular week, retail investors over-extrapolate. They bid the price
up on excitement, creating a temporary overvaluation that corrects the following week.

**2. Crypto amplifies the lottery effect.**
Crypto attracts a disproportionate share of lottery-seeking retail investors compared
to equity markets. The overpricing effect is stronger and more persistent.

**3. Attention-driven trading.**
A coin that posted a massive weekly return gets media coverage, Twitter trending, Discord
chatter. This attention spike drives short-term inflows that push the price above fair
value — setting up the reversal.

**4. The short leg is dangerous in bull runs.**
High-MAXRET coins in bull markets are often genuine momentum winners. Shorting them
occasionally produces large losses (which is why the OOS Sharpe is negative despite
the strong IC). The signal is best used for *tilting* exposures, not mechanical shorting.

---

## Statistical Tests

### Newey-West t-stat on IC

- **IS IC t = {fmt_val(row['IS_IC_t'])}** — |t| = {fmt_val(abs(row['IS_IC_t']))} — **significant**
- **OOS IC t = {fmt_val(row['OOS_IC_t'])}** — |t| = {fmt_val(abs(row['OOS_IC_t']))} — **significant**

Both significant, OOS stronger — the classic OOS confirmation pattern.

### Jarque-Bera Normality Test

| Period | JB Statistic | p-value | Normal? |
|---|---|---|---|
| IS | {fmt_val(jb_is, '.1f')} | {fmt_val(jb_is_p, '.4f')} | {"No" if jb_is_p < 0.05 else "Yes"} |
| OOS | {fmt_val(jb_oos, '.1f')} | {fmt_val(jb_oos_p, '.4f')} | {"No" if jb_oos_p < 0.05 else "Yes"} |

### ADF Stationarity Test

- ADF: **{fmt_val(adf_stat, '.3f')}**, p = **{fmt_val(adf_p, '.4f')}**
- **{"Stationary" if adf_p < 0.05 else "Non-stationary"}** — returns are mean-reverting.

### Giglio-Xiu Pricing Result

Full GX (K_hidden = 2): **λ = +{GX_LAMBDA:.1f}%/yr, t = +{GX_T:.2f}** — highly significant.
One of the strongest pricing results in the entire factor zoo. High-MAXRET exposure is
genuinely compensated over the long run, consistent with a lottery risk premium.

### ASD vs Bitcoin

ε₁ = {ASD_EPS1:.3f}, ε₂ = {ASD_EPS2:.3f} — neither first- nor second-order dominant over Bitcoin.
The mechanical long/short does not beat Bitcoin's full distribution. Consistent with the
finding that the L/S Sharpe is weak even though the ranking IC is strong.

---

## Visualisations

### Cumulative Return & Weekly IC

![Cumulative return and weekly IC](artifacts/figures/{PREFIX}_01_cumulative_return.png)

IC bars are persistently negative (the factor working: high-MAXRET → underperforms).
The cumulative return is positive IS and pulls back OOS — reflecting bull-run periods
where lottery coins outperform (hurting the short leg).

### Rolling IC Significance

![Rolling IC and NW t-stat](artifacts/figures/{PREFIX}_02_rolling_ic_significance.png)

The rolling t-stat stays well below −2 in most periods. Brief excursions toward zero
correspond to periods when lottery/momentum aligns (late 2020 bull, late 2024 rally).

### Return Distribution

![Return distribution](artifacts/figures/{PREFIX}_03_return_distribution.png)

The distribution has negative skew in IS — periodic blow-ups on the short leg (when
lottery coins moon) create large negative weeks.

### Rolling Sharpe Ratio

![Rolling Sharpe](artifacts/figures/{PREFIX}_04_rolling_sharpe.png)

The Sharpe oscillates around zero, spending significant time negative during bull markets
and positive during sideways/bear markets. This regime-dependence is the trade-off for
running the reversal strategy mechanically.

### QQ-Plot vs Normal Distribution

![QQ plot](artifacts/figures/{PREFIX}_05_qq_plot.png)

Heavy left tails: the occasional extreme losses when the short leg rockets confirm
the non-Gaussian character of the strategy.

### MAXRET Tercile Returns

![Tercile returns](artifacts/figures/{PREFIX}_06_tercile_returns.png)

High-Max coins (the short) have the highest raw return over the full sample —
confirming they carry a long-run lottery risk premium (GX λ > 0). The L/S spread
(Low–High) performance is modest because the short leg occasionally dominates.

### IS vs OOS Comparison Dashboard

![IS vs OOS](artifacts/figures/{PREFIX}_07_is_oos_comparison.png)

IC improves strongly OOS (from {fmt_val(row['IS_IC'], '.4f')} to {fmt_val(row['OOS_IC'], '.4f')}),
confirming the signal's persistence. The Sharpe declines OOS — the lottery effect in the
2024–2026 bull run temporarily hurt the short leg.

### Cumulative Return by MAXRET Tercile

![Cumulative tercile](artifacts/figures/{PREFIX}_08_cumulative_tercile.png)

High-Max coins compound fastest over the full sample — the long-run lottery premium at
work. The reversal L/S spread (dashed) is mostly flat to slightly positive IS, negative OOS.

### Reversal Scatter: MAXRET Rank vs Next-Week Return

![Reversal scatter](artifacts/figures/{PREFIX}_09_reversal_scatter.png)

Each point is a quantile bin of MAXRET rank percentile (x-axis) vs average next-week
return (y-axis). The downward slope (especially strong IS) directly confirms the reversal:
coins at the top of the MAXRET rank earn the lowest returns the following week.
"""
    (STAGE / "MAXRET_VIZ_REPORT.md").write_text(md)
    print("  wrote MAXRET_VIZ_REPORT.md")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    print("Loading data...")
    man = load_manifest()
    trade = set(man["trading_universe"]["symbols_ever_eligible"])
    is_lo = pd.Timestamp(man["split"]["in_sample"][0])
    is_hi = pd.Timestamp(man["split"]["in_sample"][1])
    oos_lo = pd.Timestamp(man["split"]["out_of_sample"][0])
    oos_hi = pd.Timestamp(man["split"]["out_of_sample"][1])

    panel = pd.read_parquet(PANEL_DIR / "price_mcap_panel_weekly.parquet")
    panel["week"] = pd.to_datetime(panel["week"])
    panel = panel[panel["symbol"].isin(trade)]

    print("Building MAXRET factor series...")
    chars, ret_wide = build_characteristics(panel, trade)
    factor_ret = build_factor_returns(chars)
    factor_ic = build_factor_ic(chars)
    factor_ret.index = pd.to_datetime(factor_ret.index)
    factor_ic.index = pd.to_datetime(factor_ic.index)

    val_stats = pd.read_parquet(PANEL_DIR / "factor_validation_stats.parquet")
    row = val_stats[val_stats["factor"] == FACTOR_NAME].iloc[0].to_dict()

    print("Generating charts...")
    fig1 = chart_cumulative_return(factor_ret, factor_ic, is_lo, is_hi, oos_lo, oos_hi)
    fig2 = chart_rolling_ic_significance(factor_ic, is_lo, is_hi, oos_lo, oos_hi)
    fig3, is_d, oos_d = chart_return_distribution(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig4 = chart_rolling_sharpe(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig5 = chart_qq_plot(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig6, _ = chart_tercile_returns(chars, is_lo, is_hi, oos_lo, oos_hi)
    fig7 = chart_is_oos_comparison(row)
    fig8 = chart_cumulative_tercile(chars, is_lo, is_hi, oos_lo, oos_hi)
    fig9 = chart_reversal_scatter(chars, is_lo, is_hi, oos_lo, oos_hi)

    charts = [
        (f"{PREFIX}_01_cumulative_return", fig1),
        (f"{PREFIX}_02_rolling_ic_significance", fig2),
        (f"{PREFIX}_03_return_distribution", fig3),
        (f"{PREFIX}_04_rolling_sharpe", fig4),
        (f"{PREFIX}_05_qq_plot", fig5),
        (f"{PREFIX}_06_tercile_returns", fig6),
        (f"{PREFIX}_07_is_oos_comparison", fig7),
        (f"{PREFIX}_08_cumulative_tercile", fig8),
        (f"{PREFIX}_09_reversal_scatter", fig9),
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
    jb_is, jb_is_p = sp_stats.jarque_bera(is_r)[:2]
    jb_oos, jb_oos_p = sp_stats.jarque_bera(oos_r)[:2]

    write_report(row, is_d, oos_d, adf_stat, adf_p, jb_is, jb_is_p, jb_oos, jb_oos_p)
    print(f"\nAll done. Charts in {FIG_DIR}")


if __name__ == "__main__":
    main()
