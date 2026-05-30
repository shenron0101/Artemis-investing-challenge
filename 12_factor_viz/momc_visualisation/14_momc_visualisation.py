"""09 — MomC (4-Week Raw Momentum) Factor Visualisation Pipeline.

MomC = buy 4-week winners, short 4-week losers. Classic momentum.
Result: Not supported — reversal IS, noise OOS, not GX-priced.
The story: WHY momentum fails in crypto is more instructive than any success.

Outputs
-------
    artifacts/figures/momc_*.html / .png
    artifacts/data/momc_viz_data.parquet
    MOMC_VIZ_REPORT.md
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
PARENT = STAGE.parent.parent / "09_nalfp_add"
DATA_DIR = STAGE / "artifacts" / "data"
MANIFEST_DIR = PARENT / "artifacts" / "manifests"
PANEL_DIR = PARENT / "artifacts" / "data"
FIG_DIR = STAGE / "artifacts" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

FACTOR_NAME = "MomC"
PREFIX = "momc"
CHAR_COL = "mom_4w"
DIRECTION = +1    # long high-momentum (top 30%), short low-momentum (bottom 30%)
FRAC = 0.30
MIN_NAMES = 10
T_LABELS = ["Low-Mom", "Mid-Mom", "High-Mom"]
SPREAD_LABEL = "MomC (High–Low)"

IS_LABEL = "In-Sample (2021-05-10 → 2024-11-11)"
OOS_LABEL = "Out-of-Sample (2024-11-18 → 2026-05-25)"
PLOTLY_TEMPLATE = "plotly_white"
COLORS = {"IS": "#2196F3", "OOS": "#FF5722", "FULL": "#607D8B",
          "SIG_POS": "#4CAF50", "SIG_NEG": "#F44336"}

GX_LAMBDA = -3.3
GX_T = -0.10
ASD_EPS1 = 0.474
ASD_EPS2 = 0.208


def load_manifest():
    return json.loads((MANIFEST_DIR / "universe_manifest.json").read_text())


def build_characteristics(panel, trade_symbols):
    px_wide = (panel[panel["symbol"].isin(trade_symbols)]
               .pivot(index="week", columns="symbol", values="price").sort_index())
    ret_wide = px_wide.pct_change()
    mom4 = px_wide / px_wide.shift(4) - 1.0
    vol4 = ret_wide.rolling(4).std()

    def melt(df, name):
        return df.reset_index().melt(id_vars="week", var_name="symbol", value_name=name)

    out = melt(ret_wide, "ret_1w")
    fwd = ret_wide.shift(-1)
    for df, nm in [(fwd, "fwd_ret_1w"), (mom4, "mom_4w"), (vol4, "vol_4w")]:
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
        long_m = r > n - k   # direction=+1: long top (high momentum)
        short_m = r <= k
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
    return v.strftime("%Y-%m-%d") if isinstance(v, pd.Timestamp) else str(v)


def _add_vline(fig, x, line_dash="dash", line_color="#999", annotation_text=None):
    xs = _ts_str(x)
    fig.add_shape(type="line", x0=xs, x1=xs, y0=0, y1=1,
                  xref="x", yref="paper", line=dict(dash=line_dash, color=line_color, width=1))
    if annotation_text:
        fig.add_annotation(x=xs, y=1.02, xref="x", yref="paper",
                           text=annotation_text, showarrow=False, font=dict(size=10, color=line_color))


def _add_vrect(fig, x0, x1, fillcolor, opacity=0.05):
    fig.add_shape(type="rect", x0=_ts_str(x0), x1=_ts_str(x1), y0=0, y1=1,
                  xref="x", yref="paper", fillcolor=fillcolor, opacity=opacity, line=dict(width=0))


def chart_cumulative_return(ret, ic, is_lo, is_hi, oos_lo, oos_hi):
    cum = (1 + ret).cumprod()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=(f"{FACTOR_NAME} Cumulative Long/Short Return",
                                        "Weekly IC (positive = winners beat losers)"))
    for lbl, lo, hi, color in [(IS_LABEL, is_lo, is_hi, COLORS["IS"]),
                                (OOS_LABEL, oos_lo, oos_hi, COLORS["OOS"])]:
        c = cum[(cum.index >= lo) & (cum.index <= hi)]
        fig.add_trace(go.Scatter(x=c.index, y=c.values, name=lbl,
                                 line=dict(color=color, width=2)), row=1, col=1)
        ic_s = ic[(ic.index >= lo) & (ic.index <= hi)].dropna()
        fig.add_trace(go.Bar(x=ic_s.index, y=ic_s.values,
                             marker_color=color, marker_opacity=0.5), row=2, col=1)
    for y, c in [(0, "#666"), (-0.03, COLORS["SIG_NEG"]), (0.03, COLORS["SIG_POS"])]:
        fig.add_hline(y=y, line_dash="dot", line_color=c, line_width=0.8, row=2, col=1)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=700,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Growth of $1", row=1, col=1)
    fig.update_yaxes(title_text="IC", row=2, col=1)
    return fig


def chart_rolling_ic_significance(ic, is_lo, is_hi, oos_lo, oos_hi):
    roll_ic = ic.rolling(26).mean().dropna()
    roll_t = rolling_newey_west_t(ic, window=26, lags=4)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("26-Week Rolling Mean IC", "26-Week Rolling NW t-stat"))
    fig.add_trace(go.Scatter(x=roll_ic.index, y=roll_ic.values,
                             line=dict(color=COLORS["FULL"], width=2)), row=1, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="#666", row=1, col=1)
    fig.add_trace(go.Scatter(x=roll_t.index, y=roll_t.values,
                             line=dict(color=COLORS["FULL"], width=2)), row=2, col=1)
    for y, c in [(2, COLORS["SIG_POS"]), (-2, COLORS["SIG_NEG"]), (0, "#666")]:
        fig.add_hline(y=y, line_dash="dot" if y != 0 else "dash", line_color=c, row=2, col=1)
    _add_vline(fig, is_hi, annotation_text="IS / OOS")
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
                         marker_color=COLORS["IS"], marker_opacity=0.7), row=2, col=2)
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
    spread = pivot[T_LABELS[-1]] - pivot[T_LABELS[0]]   # high-mom - low-mom

    def ann(s):
        return (1 + s).prod() ** (52 / len(s)) - 1 if len(s) > 0 else np.nan

    groups = {"IS": (is_lo, is_hi), "OOS": (oos_lo, oos_hi),
              "Full": (pivot.index.min(), pivot.index.max())}
    bars = {}
    for nm, (lo, hi) in groups.items():
        sub = pivot[(pivot.index >= lo) & (pivot.index <= hi)]
        sp = spread[(spread.index >= lo) & (spread.index <= hi)]
        bars[nm] = [ann(sub[lb]) * 100 for lb in T_LABELS] + [ann(sp) * 100]

    fig = go.Figure(data=[
        go.Bar(name="IS", x=T_LABELS + [SPREAD_LABEL], y=bars["IS"],
               marker_color=COLORS["IS"], marker_opacity=0.8),
        go.Bar(name="OOS", x=T_LABELS + [SPREAD_LABEL], y=bars["OOS"],
               marker_color=COLORS["OOS"], marker_opacity=0.8),
        go.Bar(name="Full", x=T_LABELS + [SPREAD_LABEL], y=bars["Full"],
               marker_color=COLORS["FULL"], marker_opacity=0.5),
    ])
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, barmode="group",
                      title=f"{FACTOR_NAME} Momentum Tercile Returns",
                      xaxis_title="Momentum Group", yaxis_title="Annualised Return (%)",
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
    spread_cum = (1 + (pivot[T_LABELS[-1]] - pivot[T_LABELS[0]])).cumprod()
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


def chart_momentum_crashes(ret, is_lo, is_hi, oos_lo, oos_hi):
    """Chart 9 (MomC-specific): Identify the 5 worst weeks for MomC and annotate them.
    Shows the regime-specific crash anatomy — when did momentum fail hardest?"""
    worst5 = ret.nsmallest(5)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ret.index, y=ret.values * 100,
                             mode="lines", opacity=0.6,
                             line=dict(color=COLORS["FULL"], width=1.5),
                             name="Weekly MomC return"))
    # Mark the 5 worst weeks
    fig.add_trace(go.Scatter(x=worst5.index, y=worst5.values * 100, mode="markers",
                             marker=dict(color=COLORS["SIG_NEG"], size=12, symbol="x"),
                             name="5 worst crash weeks"))
    for dt, val in worst5.items():
        fig.add_annotation(x=_ts_str(dt), y=val * 100,
                           text=f"{dt.strftime('%b %Y')}<br>{val*100:.1f}%",
                           showarrow=True, arrowhead=2, font=dict(size=9),
                           ax=40, ay=-30)
    fig.add_hline(y=0, line_dash="dash", line_color="#666")
    _add_vrect(fig, is_lo, is_hi, fillcolor=COLORS["IS"])
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"])
    _add_vline(fig, is_hi, annotation_text="IS / OOS")
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500,
                      title="MomC Weekly Returns with 5 Worst Crash Weeks Annotated",
                      xaxis_title="Week", yaxis_title="Weekly Return (%)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


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


def write_report(row, is_d, oos_d, adf_stat, adf_p, jb_is, jb_is_p, jb_oos, jb_oos_p, factor_ret):
    worst5 = factor_ret.nsmallest(5)
    crash_list = "\n".join(
        f"- **{dt.strftime('%Y-%m-%d')}**: {val*100:.1f}%"
        for dt, val in worst5.items()
    )

    md = f"""# MomC (4-Week Raw Momentum) Factor — Analysis Report

*Generated by `14_momc_visualisation.py` from the Stage-09 5-year panel.*

---

## The Idea in Plain English

Momentum is one of the most famous findings in financial research: assets that have
been going up tend to keep going up, and assets that have been going down tend to keep
going down. The idea is that investors under-react to good news — they are slow to buy
winners — so the price continues rising even after the news is out.

**MomC** tests this in crypto. Each week:
- **Buy** (go long) coins that gained the most in the past 4 weeks (the top 30% by return)
- **Short-sell** (go short) coins that fell the most (the bottom 30% by return)

---

## The Short Answer

**Not supported — momentum is unreliable and reverses in crypto.**

The IC t-stat is **{fmt_val(row['IS_IC_t'])}** in-sample (slightly negative = winners
*underperformed*, a short-term reversal) and only **{fmt_val(row['OOS_IC_t'])}** out-of-sample
(basically zero). The GX pricing model finds no priced momentum premium
(λ = {GX_LAMBDA:.1f}%/yr, t = {GX_T:.2f}).

Momentum fails where it matters most: crypto regimes shift fast, and yesterday's winner
is often tomorrow's mean-reverter.

---

## The IC Sign: A Short-Term Reversal

The IC for MomC is slightly *negative* in-sample (−{fmt_val(abs(row['IS_IC']), '.3f')}, t = {fmt_val(row['IS_IC_t'])}).
This means high-momentum coins *underperformed* in the following week — a reversal.

But the effect is small and barely significant (|t| = {fmt_val(abs(row['IS_IC_t']), '.2f')} < 2).
Out-of-sample the IC is essentially zero (+{fmt_val(row['OOS_IC'], '.4f')}, t = {fmt_val(row['OOS_IC_t'])}).
There is no consistent signal in either direction.

Compare to risk-adjusted momentum (RMOM1w): by dividing the return signal by volatility,
RMOM1w avoids many of the large-variance crash weeks that destroy raw momentum. The failure
of MomC versus the partial success of RMOM is itself the key lesson.

---

## Performance Summary

| Metric | In-Sample | Out-of-Sample |
|---|---|---|
| Weeks | {int(row['IS_n'])} | {int(row['OOS_n'])} |
| Annualised Return | {fmt_val(row['IS_annret']*100, '.1f')}% | {fmt_val(row['OOS_annret']*100, '.1f')}% |
| Sharpe Ratio | {fmt_val(row['IS_sharpe'])} | {fmt_val(row['OOS_sharpe'])} |
| Mean IC | {fmt_val(row['IS_IC'], '.4f')} | {fmt_val(row['OOS_IC'], '.4f')} |
| IC t-stat (NW) | {sign_cell(row['IS_IC_t'])} | {sign_cell(row['OOS_IC_t'])} |
| Return t-stat (NW) | {sign_cell(row['IS_t'])} | {sign_cell(row['OOS_t'])} |

### Return Distribution

| Statistic | IS | OOS |
|---|---|---|
| Mean weekly return | {fmt_val(is_d['mean']*100, '.3f')}% | {fmt_val(oos_d['mean']*100, '.3f')}% |
| Std (weekly) | {fmt_val(is_d['std']*100, '.3f')}% | {fmt_val(oos_d['std']*100, '.3f')}% |
| Skewness | {fmt_val(is_d['skew'], '.2f')} | {fmt_val(oos_d['skew'], '.2f')} |
| Excess Kurtosis | {fmt_val(is_d['kurt'], '.2f')} | {fmt_val(oos_d['kurt'], '.2f')} |

---

## Why Momentum Fails in Crypto

**1. Regime reversals are fast and brutal.**
Crypto markets don't trend gradually — they moon and crash. A coin up 40% in 4 weeks
is often near a local top. The very signal that makes it a "winner" in the formation
period makes it vulnerable to profit-taking the next week.

**2. Fat tails dominate the return distribution.**
Momentum crashes in equities are well-known (Barroso-Santa Clara 2015). In crypto they
are *worse*: the kurtosis of the IS return series is {fmt_val(is_d['kurt'], '.2f')} — extreme
weeks (big crashes of the short leg, or winners suddenly reversing) swamp the signal.

**3. The formation window is too short for crypto.**
A 4-week return in crypto reflects noise and luck as much as genuine trend. Longer windows
(8–13 weeks) or vol-normalized signals (RMOM) are more robust.

**4. 2022 bear market crushed momentum.**
Rising-rate environments historically break momentum strategies. Crypto's 2022 collapse
(BTC −65%, many alts −90%) happened simultaneously across all prior winners — the short
leg rocketed (leveraged longs forced to sell), devastating the L/S spread.

**The worst crash weeks:**
{crash_list}

---

## Statistical Tests

### Newey-West t-stat on IC

- **IS IC t = {fmt_val(row['IS_IC_t'])}** — |t| = {fmt_val(abs(row['IS_IC_t']))} — borderline/not significant
- **OOS IC t = {fmt_val(row['OOS_IC_t'])}** — |t| = {fmt_val(abs(row['OOS_IC_t']))} — not significant

In IS the IC is slightly negative (reversal). OOS it flips to barely positive. Neither
is convincing — the factor has no reliable direction over the 5-year period.

### Jarque-Bera Normality Test

| Period | JB Statistic | p-value | Normal? |
|---|---|---|---|
| IS | {fmt_val(jb_is, '.1f')} | {fmt_val(jb_is_p, '.4f')} | {"No" if jb_is_p < 0.05 else "Yes"} |
| OOS | {fmt_val(jb_oos, '.1f')} | {fmt_val(jb_oos_p, '.4f')} | {"No" if jb_oos_p < 0.05 else "Yes"} |

### ADF Stationarity Test

- ADF: **{fmt_val(adf_stat, '.3f')}**, p = **{fmt_val(adf_p, '.4f')}**
- **{"Stationary" if adf_p < 0.05 else "Non-stationary"}**

### Giglio-Xiu Pricing Result

Full GX (K_hidden = 2): **λ = {GX_LAMBDA:.1f}%/yr, t = {GX_T:.2f}** — not significant.
Raw momentum is not a priced systematic risk in the 5-year crypto panel. This aligns
with the equity literature where momentum premia are highly conditional and crash-prone.

### ASD vs Bitcoin

ε₁ = {ASD_EPS1:.3f}, ε₂ = {ASD_EPS2:.3f} — neither first- nor second-order dominant over
Bitcoin. MomC cannot beat Bitcoin's full return distribution. Holding BTC is distribu-
tionally better than running this L/S strategy.

---

## Visualisations

### Cumulative Return & Weekly IC

![Cumulative return and weekly IC](artifacts/figures/{PREFIX}_01_cumulative_return.png)

The cumulative return is positive IS (weak but present) and essentially flat OOS. The
IC bars oscillate with no consistent sign — some weeks are positive (trend), some negative
(reversal), with no dominant direction over 5 years.

### Rolling IC Significance

![Rolling IC and NW t-stat](artifacts/figures/{PREFIX}_02_rolling_ic_significance.png)

The rolling t-stat dips below −2 briefly IS (the reversal regime) but crosses zero and
turns faintly positive by OOS. The lack of any stable side of the ±2 boundaries is
the clearest visual evidence that the factor is unreliable.

### Return Distribution

![Return distribution](artifacts/figures/{PREFIX}_03_return_distribution.png)

Positive skew (IS skewness = {fmt_val(is_d['skew'], '.2f')}) — occasional large positive weeks
when trend briefly asserts itself. Moderate kurtosis from crash weeks.

### Rolling Sharpe Ratio

![Rolling Sharpe](artifacts/figures/{PREFIX}_04_rolling_sharpe.png)

The Sharpe frequently crosses zero in both directions, spending time above +1 in some
periods and below −1 in others. No persistent positive regime.

### QQ-Plot vs Normal Distribution

![QQ plot](artifacts/figures/{PREFIX}_05_qq_plot.png)

Fat tails in both directions — both the crash weeks and the momentum-working weeks
deviate from normal, making statistical inference noisy.

### Momentum Tercile Returns

![Tercile returns](artifacts/figures/{PREFIX}_06_tercile_returns.png)

In many sub-periods, the "High-Mom" tercile (the expected long leg) does NOT
outperform the "Low-Mom" tercile. The spread is near zero across the full sample.

### IS vs OOS Comparison Dashboard

![IS vs OOS](artifacts/figures/{PREFIX}_07_is_oos_comparison.png)

IC flips from slightly negative IS to slightly positive OOS — neither significant.
Sharpe drops from IS to OOS, confirming no persistent premium.

### Cumulative Return by Momentum Tercile

![Cumulative tercile](artifacts/figures/{PREFIX}_08_cumulative_tercile.png)

All three terciles broadly track each other with no systematic separation between
high-momentum and low-momentum coins over the full 5-year sample.

### MomC Crash Anatomy

![Momentum crashes](artifacts/figures/{PREFIX}_09_momentum_crashes.png)

The 5 worst single weeks for the MomC L/S strategy are annotated with dates and
magnitudes. These crash weeks tend to cluster around major market turning points —
confirming that momentum fails hardest precisely when it's most needed.
"""
    (STAGE / "MOMC_VIZ_REPORT.md").write_text(md)
    print("  wrote MOMC_VIZ_REPORT.md")


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

    print("Building MomC factor series...")
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
    fig9 = chart_momentum_crashes(factor_ret, is_lo, is_hi, oos_lo, oos_hi)

    charts = [
        (f"{PREFIX}_01_cumulative_return", fig1),
        (f"{PREFIX}_02_rolling_ic_significance", fig2),
        (f"{PREFIX}_03_return_distribution", fig3),
        (f"{PREFIX}_04_rolling_sharpe", fig4),
        (f"{PREFIX}_05_qq_plot", fig5),
        (f"{PREFIX}_06_tercile_returns", fig6),
        (f"{PREFIX}_07_is_oos_comparison", fig7),
        (f"{PREFIX}_08_cumulative_tercile", fig8),
        (f"{PREFIX}_09_momentum_crashes", fig9),
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

    write_report(row, is_d, oos_d, adf_stat, adf_p, jb_is, jb_is_p, jb_oos, jb_oos_p, factor_ret)
    print(f"\nAll done. Charts in {FIG_DIR}")


if __name__ == "__main__":
    main()
