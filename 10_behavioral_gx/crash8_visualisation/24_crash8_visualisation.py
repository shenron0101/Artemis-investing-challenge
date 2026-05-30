"""Stage 10 — CRASH8 (Capitulation Premium) Visualisation.

CRASH8 = crashed_minus_resilient: long coins with the worst single-week crash
in the trailing 8 weeks, short the most resilient (highest min-return).

Characteristic: minret_8w = rolling(8).min() on weekly returns.
Direction: -1 (long low min-ret = most crashed, short high min-ret = most resilient).

Grade: Priced risk — joint GX λ = +177.9%/yr, t = +4.79.
Strongest of the 4 behavioral factors. Recently punished coins carry a priced
rebound/crash-risk exposure.

Outputs → artifacts/figures/crash8_*.html/.png  +  CRASH8_VIZ_REPORT.md
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
STAGE09 = PARENT.parent / "09_nalfp_add"
DATA_DIR = STAGE / "artifacts" / "data"
BEHAVIORAL_DATA = PARENT / "artifacts" / "data"
PANEL_DIR = STAGE09 / "artifacts" / "data"
MANIFEST_DIR = STAGE09 / "artifacts" / "manifests"
FIG_DIR = STAGE / "artifacts" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

FACTOR_NAME = "CRASH8"
PREFIX = "crash8"
CHAR_COL = "minret_8w"
DIRECTION = -1   # long low min-ret (most crashed), short high min-ret (most resilient)
FRAC = 0.30
MIN_NAMES = 10
T_LABELS = ["Crashed", "Mid", "Resilient"]   # sorted ascending by minret_8w
SPREAD_LABEL = "CRASH8 (Crashed−Resilient)"

IS_LABEL  = "In-Sample (2021-05-10 → 2024-11-11)"
OOS_LABEL = "Out-of-Sample (2024-11-18 → 2026-05-25)"
PLOTLY_TEMPLATE = "plotly_white"
COLORS = {"IS": "#2196F3", "OOS": "#FF5722", "FULL": "#607D8B",
          "SIG_POS": "#4CAF50", "SIG_NEG": "#F44336"}

GX_LAMBDA_ANN = 177.9
GX_T          = 4.79
GX_CI_LO      = 105.1
GX_CI_HI      = 250.8
NEAREST_09    = "VolC"
CORR_09       = 0.677


def load_manifest():
    return json.loads((MANIFEST_DIR / "universe_manifest.json").read_text())


def build_characteristics(panel, trade_symbols):
    px_wide = (panel[panel["symbol"].isin(trade_symbols)]
               .pivot(index="week", columns="symbol", values="price").sort_index())
    ret_wide = px_wide.pct_change()
    minret8 = ret_wide.rolling(8).min()

    def melt(df, name):
        return df.reset_index().melt(id_vars="week", var_name="symbol", value_name=name)

    out = melt(ret_wide, "ret_1w")
    fwd = ret_wide.shift(-1)
    for df, nm in [(fwd, "fwd_ret_1w"), (minret8, CHAR_COL)]:
        out = out.merge(melt(df, nm), on=["week","symbol"], how="left")
    return out, ret_wide


def newey_west_se(arr, lags=4):
    r = np.asarray(arr, dtype=float); n = len(r)
    if n < 2: return np.nan
    e = r - r.mean(); s = (e*e).mean()
    for lag in range(1, min(lags, n-1)+1):
        s += 2.*(1 - lag/(lags+1)) * (e[lag:]*e[:-lag]).mean()
    return float(np.sqrt(max(s, 0.) / n))


def rolling_newey_west_t(series, window=26, lags=4):
    out = {}; vals = series.dropna()
    for i in range(window, len(vals)):
        sub = vals.iloc[i-window:i]; se = newey_west_se(sub.values, lags)
        out[vals.index[i]] = float(sub.mean()/se) if se and se > 0 else np.nan
    return pd.Series(out)


def rolling_stat(series, window, func):
    out = {}; vals = series.dropna()
    for i in range(window, len(vals)):
        out[vals.index[i]] = func(vals.iloc[i-window:i])
    return pd.Series(out)


def _ts_str(v): return v.strftime("%Y-%m-%d") if isinstance(v, pd.Timestamp) else str(v)


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


def chart_cumulative_return(ret, is_lo, is_hi, oos_lo, oos_hi):
    cum = (1+ret).cumprod()
    fig = go.Figure()
    for lbl, lo, hi, color in [(IS_LABEL, is_lo, is_hi, COLORS["IS"]),
                                (OOS_LABEL, oos_lo, oos_hi, COLORS["OOS"])]:
        c = cum[(cum.index>=lo)&(cum.index<=hi)]
        if len(c): fig.add_trace(go.Scatter(x=c.index, y=c.values, name=lbl, line=dict(color=color, width=2)))
    _add_vline(fig, is_hi, "IS / OOS"); _add_vrect(fig, is_lo, is_hi, COLORS["IS"]); _add_vrect(fig, oos_lo, oos_hi, COLORS["OOS"])
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500,
                      title=f"{FACTOR_NAME} Cumulative Return (Crashed − Resilient)",
                      xaxis_title="Week", yaxis_title="Growth of $1",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_rolling_return_significance(ret, is_lo, is_hi, oos_lo, oos_hi):
    roll_ret = ret.rolling(26).mean().dropna()
    roll_t   = rolling_newey_west_t(ret, window=26, lags=4)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("26-Wk Rolling Mean Return","26-Wk Rolling NW t-stat"))
    fig.add_trace(go.Scatter(x=roll_ret.index, y=roll_ret.values*100, line=dict(color=COLORS["FULL"], width=2)), row=1, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="#666", row=1, col=1)
    fig.add_trace(go.Scatter(x=roll_t.index, y=roll_t.values, line=dict(color=COLORS["FULL"], width=2)), row=2, col=1)
    for y, c in [(2, COLORS["SIG_POS"]), (-2, COLORS["SIG_NEG"]), (0, "#666")]:
        fig.add_hline(y=y, line_dash="dot" if y else "dash", line_color=c, row=2, col=1)
    _add_vline(fig, is_hi, "IS / OOS"); _add_vrect(fig, is_lo, is_hi, COLORS["IS"]); _add_vrect(fig, oos_lo, oos_hi, COLORS["OOS"])
    fig.update_layout(template=PLOTLY_TEMPLATE, height=700,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Weekly Return (%)", row=1, col=1)
    fig.update_yaxes(title_text="NW t-stat", row=2, col=1)
    return fig


def chart_return_distribution(ret, is_lo, is_hi, oos_lo, oos_hi):
    is_r  = ret[(ret.index>=is_lo) &(ret.index<=is_hi)].dropna()
    oos_r = ret[(ret.index>=oos_lo)&(ret.index<=oos_hi)].dropna()
    def desc(s):
        se = newey_west_se(s.values, 4)
        return dict(n=len(s), mean=s.mean(), std=s.std(), skew=s.skew(), kurt=s.kurtosis(),
                    t_nw=float(s.mean()/se) if se and se>0 else np.nan,
                    sharpe=float(s.mean()/s.std()*np.sqrt(52)) if s.std()>0 else np.nan,
                    min=s.min(), p25=s.quantile(.25), median=s.median(), p75=s.quantile(.75), max=s.max())
    is_d, oos_d = desc(is_r), desc(oos_r)
    fig = make_subplots(rows=2, cols=2, subplot_titles=("Hist IS","Hist OOS","Box Plot","ACF IS"),
                        vertical_spacing=0.12, horizontal_spacing=0.10)
    for (r,ci), series, color, label in [((1,1),is_r,COLORS["IS"],"IS"),((1,2),oos_r,COLORS["OOS"],"OOS")]:
        if len(series):
            b = np.histogram(series, bins=40, density=True)
            fig.add_trace(go.Bar(x=b[1][:-1], y=b[0], name=label, marker_color=color, marker_opacity=0.7), row=r, col=ci)
    fig.add_trace(go.Box(y=is_r.values,  name="IS",  marker_color=COLORS["IS"],  boxmean="sd"), row=2, col=1)
    fig.add_trace(go.Box(y=oos_r.values, name="OOS", marker_color=COLORS["OOS"], boxmean="sd"), row=2, col=1)
    acf = [is_r.autocorr(lag=l) for l in range(1,13)]
    fig.add_trace(go.Bar(x=list(range(1,13)), y=acf, marker_color=COLORS["IS"], marker_opacity=0.7), row=2, col=2)
    conf = 1.96/np.sqrt(len(is_r))
    fig.add_hline(y=conf, line_dash="dot", line_color="#999", row=2, col=2)
    fig.add_hline(y=-conf, line_dash="dot", line_color="#999", row=2, col=2)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=800, showlegend=False)
    return fig, is_d, oos_d


def chart_rolling_sharpe(ret, is_lo, is_hi, oos_lo, oos_hi):
    rs = rolling_stat(ret, 52, lambda s: s.mean()/s.std()*np.sqrt(52) if s.std()>0 else np.nan)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rs.index, y=rs.dropna().values, line=dict(color=COLORS["FULL"], width=2)))
    fig.add_hline(y=0, line_dash="dash", line_color="#666")
    fig.add_hline(y=1, line_dash="dot", line_color=COLORS["SIG_POS"], annotation_text="Sharpe = 1")
    fig.add_hline(y=-1, line_dash="dot", line_color=COLORS["SIG_NEG"], annotation_text="Sharpe = −1")
    _add_vrect(fig, is_lo, is_hi, COLORS["IS"]); _add_vrect(fig, oos_lo, oos_hi, COLORS["OOS"]); _add_vline(fig, is_hi, "IS / OOS")
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, title=f"{FACTOR_NAME} 52-Week Rolling Sharpe",
                      xaxis_title="Week", yaxis_title="Annualised Sharpe")
    return fig


def chart_qq_plot(ret, is_lo, is_hi, oos_lo, oos_hi):
    is_r  = ret[(ret.index>=is_lo) &(ret.index<=is_hi)].dropna().sort_values()
    oos_r = ret[(ret.index>=oos_lo)&(ret.index<=oos_hi)].dropna().sort_values()
    fig = make_subplots(rows=1, cols=2, subplot_titles=("QQ — IS","QQ — OOS"))
    for ci, series, color in [(1,is_r,COLORS["IS"]),(2,oos_r,COLORS["OOS"])]:
        if len(series) > 1:
            n=len(series); t=sp_stats.norm.ppf(np.arange(1,n+1)/(n+1))*series.std()+series.mean(); s=series.values
            fig.add_trace(go.Scatter(x=t, y=s, mode="markers", marker=dict(color=color, size=4, opacity=0.7)), row=1, col=ci)
            lo,hi=min(t.min(),s.min()),max(t.max(),s.max())
            fig.add_trace(go.Scatter(x=[lo,hi],y=[lo,hi],mode="lines",line=dict(color="#999",dash="dash")), row=1, col=ci)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, showlegend=False)
    return fig


def chart_tercile_returns(chars, is_lo, is_hi, oos_lo, oos_hi):
    chars = chars.dropna(subset=["fwd_ret_1w", CHAR_COL]).copy()
    chars["tercile"] = chars.groupby("week")[CHAR_COL].transform(
        lambda x: pd.qcut(x, 3, labels=T_LABELS, duplicates="drop")
        if len(x.dropna()) >= 6 else pd.NA)
    tr = chars.dropna(subset=["tercile"]).groupby(["week","tercile"])["fwd_ret_1w"].mean()
    pivot = tr.reset_index().pivot(index="week", columns="tercile", values="fwd_ret_1w")
    for lb in T_LABELS:
        if lb not in pivot.columns: pivot[lb] = np.nan
    pivot = pivot[T_LABELS].dropna()
    spread = pivot[T_LABELS[0]] - pivot[T_LABELS[-1]]   # crashed − resilient

    def ann(s): return (1+s).prod()**(52/len(s))-1 if len(s) else np.nan
    groups = {"IS":(is_lo,is_hi),"OOS":(oos_lo,oos_hi),"Full":(pivot.index.min(),pivot.index.max())}
    bars = {}
    for nm,(lo,hi) in groups.items():
        sub=pivot[(pivot.index>=lo)&(pivot.index<=hi)]; sp=spread[(spread.index>=lo)&(spread.index<=hi)]
        bars[nm]=[ann(sub[lb])*100 if lb in sub else np.nan for lb in T_LABELS]+[ann(sp)*100]
    fig = go.Figure(data=[
        go.Bar(name="IS",   x=T_LABELS+[SPREAD_LABEL], y=bars["IS"],   marker_color=COLORS["IS"],   marker_opacity=0.8),
        go.Bar(name="OOS",  x=T_LABELS+[SPREAD_LABEL], y=bars["OOS"],  marker_color=COLORS["OOS"],  marker_opacity=0.8),
        go.Bar(name="Full", x=T_LABELS+[SPREAD_LABEL], y=bars["Full"], marker_color=COLORS["FULL"], marker_opacity=0.5),
    ])
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, barmode="group",
                      title=f"{FACTOR_NAME} — Tercile Returns by 8-Week Min Return",
                      xaxis_title="Crash Depth Group", yaxis_title="Annualised Return (%)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig, spread


def chart_is_oos_dashboard(ret, is_lo, is_hi, oos_lo, oos_hi):
    def metrics(r):
        if not len(r): return [np.nan]*5
        se = newey_west_se(r.values, 4)
        return [float(r.mean()/se) if se and se>0 else np.nan,
                float(r.mean()/r.std()*np.sqrt(52)) if r.std()>0 else np.nan,
                (1+r).prod()**(52/len(r))-1, r.mean(), r.std()]
    labels = ["Return t-stat","Sharpe","Ann. Return","Mean Wkly Ret","Weekly Std"]
    is_r  = ret[(ret.index>=is_lo) &(ret.index<=is_hi)].dropna()
    oos_r = ret[(ret.index>=oos_lo)&(ret.index<=oos_hi)].dropna()
    fig = go.Figure(data=[
        go.Bar(name="In-Sample",     x=labels, y=metrics(is_r),  marker_color=COLORS["IS"],  marker_opacity=0.8),
        go.Bar(name="Out-of-Sample", x=labels, y=metrics(oos_r), marker_color=COLORS["OOS"], marker_opacity=0.8),
    ])
    fig.add_hline(y=0, line_dash="dash", line_color="#666")
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, barmode="group",
                      title=f"{FACTOR_NAME}: IS vs OOS Dashboard",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_cumulative_tercile(chars, is_lo, is_hi, oos_lo, oos_hi):
    chars = chars.dropna(subset=["fwd_ret_1w", CHAR_COL]).copy()
    chars["tercile"] = chars.groupby("week")[CHAR_COL].transform(
        lambda x: pd.qcut(x, 3, labels=T_LABELS, duplicates="drop")
        if len(x.dropna()) >= 6 else pd.NA)
    chars = chars.dropna(subset=["tercile"])
    tr = chars.groupby(["week","tercile"])["fwd_ret_1w"].mean().reset_index()
    pivot = tr.pivot(index="week", columns="tercile", values="fwd_ret_1w")
    for lb in T_LABELS:
        if lb not in pivot.columns: pivot[lb] = np.nan
    pivot = pivot[T_LABELS].sort_index().fillna(0)
    cum = (1+pivot).cumprod()
    colors_t = {T_LABELS[0]:"#F44336", T_LABELS[1]:"#FF9800", T_LABELS[-1]:"#4CAF50"}
    fig = go.Figure()
    for lb, color in colors_t.items():
        fig.add_trace(go.Scatter(x=cum.index, y=cum[lb], name=lb, line=dict(color=color, width=2)))
    sc = (1+(pivot[T_LABELS[0]]-pivot[T_LABELS[-1]])).cumprod()
    fig.add_trace(go.Scatter(x=sc.index, y=sc.values, name=SPREAD_LABEL, line=dict(color="#000", width=2.5, dash="dash")))
    _add_vline(fig, is_hi); _add_vrect(fig, is_lo, is_hi, COLORS["IS"], 0.04); _add_vrect(fig, oos_lo, oos_hi, COLORS["OOS"], 0.04)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=550,
                      title="Cumulative Return by 8-Week Crash Depth Tercile",
                      xaxis_title="Week", yaxis_title="Growth of $1",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_crash_depth_vs_rebound(chars, is_lo, is_hi, oos_lo, oos_hi):
    """Chart 9: Scatter of 8-week min return (crash depth) vs next-week return.
    Directly shows the capitulation premium: deeper crash → higher next-week return?"""
    chars = chars.dropna(subset=["fwd_ret_1w", CHAR_COL]).copy()

    def bin_data(data):
        try: data["bin"] = pd.qcut(data[CHAR_COL], 20, labels=False, duplicates="drop")
        except Exception: return None
        return data.groupby("bin").agg(x=(CHAR_COL,"mean"), y=("fwd_ret_1w","mean")).reset_index()

    is_data  = chars[(chars["week"]>=is_lo) &(chars["week"]<=is_hi)]
    oos_data = chars[(chars["week"]>=oos_lo)&(chars["week"]<=oos_hi)]
    is_agg, oos_agg = bin_data(is_data), bin_data(oos_data)

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("IS: 8-Wk Min Return → Next-Week Return",
                                        "OOS: 8-Wk Min Return → Next-Week Return"))
    for ci, agg, color in [(1,is_agg,COLORS["IS"]),(2,oos_agg,COLORS["OOS"])]:
        if agg is not None and len(agg):
            fig.add_trace(go.Scatter(x=agg["x"]*100, y=agg["y"]*100,
                                     mode="markers+lines",
                                     marker=dict(color=color, size=7),
                                     line=dict(color=color, width=1.5)), row=1, col=ci)
        fig.add_hline(y=0, line_dash="dash", line_color="#999", row=1, col=ci)
        fig.add_vline(x=0, line_dash="dot", line_color="#ccc", row=1, col=ci)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, showlegend=False,
                      title="Capitulation Premium: 8-Week Crash Depth vs Next-Week Return (binned)")
    fig.update_xaxes(title_text="8-Wk Min Return (%) — more negative = deeper crash")
    fig.update_yaxes(title_text="Mean Next-Week Return (%)")
    return fig


def fmt_val(v, fmt=".2f"):
    if isinstance(v, float) and np.isfinite(v): return f"{v:{fmt}}"
    return "N/A"


def write_report(is_d, oos_d, adf_stat, adf_p, jb_is, jb_is_p, jb_oos, jb_oos_p):
    md = f"""# CRASH8 (Capitulation Premium) — Analysis Report

*Generated by `24_crash8_visualisation.py` from the Stage-10 behavioral factor search.*

---

## The Idea in Plain English

Imagine a coin just fell 40% in a single week. Most retail investors who held it
are now in pain — some are selling in panic, driving the price further down. The
coin is *capitulating*. But once the panic selling exhausts itself, there are no
more sellers left. The next move can only be up.

**CRASH8** bets on this **capitulation premium**. Each week, we find which coins
had their worst single-week crash over the past 8 weeks:
- **Buy** the coins that crashed deepest (bottom 30% by 8-week minimum return)
- **Short-sell** the most resilient coins (top 30% — they never had a big crash)

The bet: recently punished coins carry a rebound premium the market charges for
bearing the crash-risk exposure.

---

## The Short Answer

**The strongest of the 4 behavioral factors — a highly significant priced risk.**

Joint GX-full: **λ = +{GX_LAMBDA_ANN:.1f}%/yr, t = +{GX_T:.2f}**,
95% CI [{GX_CI_LO:.1f}%, {GX_CI_HI:.1f}%]. This is the third-largest t-stat
in the entire Stage-10 + Stage-09 joint factor zoo, behind only CRASH8's own
related factors and MAXRET.

---

## Why the Capitulation Premium Is Real

**1. Forced selling / margin calls.**
Leveraged investors in deeply crashed coins are forced to sell at market regardless
of fundamental value. This mechanical selling creates transient undervaluation that
a risk-tolerant buyer can capture.

**2. Behavioral over-extrapolation of bad news.**
When a coin crashes hard, investors extrapolate: "this coin is broken, it will keep
falling." They over-sell, pushing the price below fair value. Patient investors who
can hold through the fear earn a premium.

**3. Flight to quality / liquidity hoarding.**
After a big crash, investors reduce risk across the board. Money flows out of
punished coins and into safer alternatives. This systematic outflow creates a
consistent rebound opportunity for the next period.

**4. Correlation with VolC ({CORR_09:.3f}): a deep crash implies high realized volatility.**
The most-crashed coins over 8 weeks also tend to have high recent volatility. CRASH8
and VolC are correlated but the joint GX model confirms CRASH8 adds independent
information beyond volatility alone.

---

## CRASH8 vs VolC — what's different?

| | VolC (Stage-09) | CRASH8 (Stage-10) |
|---|---|---|
| Measures | 4-week rolling std (symmetric) | 8-week min return (left tail only) |
| Signal | High-vol → short it | Deep crash → buy it |
| Direction | Short high-vol | Long the most crashed |
| GX t-stat | −5.05 | +4.79 |
| Correlation | — | {CORR_09:.3f} |

VolC captures the *level* of volatility. CRASH8 captures the *worst realized loss* —
it is sensitive to the left tail specifically. A high-volatility coin can be symmetric
(equal up and down moves); a high-CRASH8 coin has specifically had a dramatic
downward extreme.

---

## Performance Summary

| Metric | In-Sample | Out-of-Sample |
|---|---|---|
| Annualised Return (L/S) | {fmt_val(is_d.get('mean',np.nan)*52*100,'.1f')}% | {fmt_val(oos_d.get('mean',np.nan)*52*100,'.1f')}% |
| Sharpe Ratio | {fmt_val(is_d.get('sharpe',np.nan))} | {fmt_val(oos_d.get('sharpe',np.nan))} |
| Return t-stat (NW) | {fmt_val(is_d.get('t_nw',np.nan))} | {fmt_val(oos_d.get('t_nw',np.nan))} |
| GX-full λ (joint) | +{GX_LAMBDA_ANN:.1f}%/yr (t = +{GX_T:.2f}) | — |

---

## Statistical Tests

### GX Joint Pricing

**λ = +{GX_LAMBDA_ANN:.1f}%/yr, t = +{GX_T:.2f}**, CI [{GX_CI_LO:.1f}%, {GX_CI_HI:.1f}%].
Strongest in the behavioral shortlist. Highly significant at |t| ≥ 2 in the joint model.

### Jarque-Bera

| Period | JB | p-value | Normal? |
|---|---|---|---|
| IS  | {fmt_val(jb_is,'.1f')}  | {fmt_val(jb_is_p,'.4f')}  | {"No" if jb_is_p<0.05  else "Yes"} |
| OOS | {fmt_val(jb_oos,'.1f')} | {fmt_val(jb_oos_p,'.4f')} | {"No" if jb_oos_p<0.05 else "Yes"} |

### ADF Stationarity

ADF = {fmt_val(adf_stat,'.3f')}, p = {fmt_val(adf_p,'.4f')} → **{"Stationary" if adf_p<0.05 else "Non-stationary"}**

---

## Visualisations

### Cumulative L/S Return
![Cumulative return](artifacts/figures/{PREFIX}_01_cumulative_return.png)

### Rolling Return Significance
![Rolling significance](artifacts/figures/{PREFIX}_02_rolling_return_significance.png)

### Return Distribution
![Return distribution](artifacts/figures/{PREFIX}_03_return_distribution.png)

### Rolling Sharpe
![Rolling Sharpe](artifacts/figures/{PREFIX}_04_rolling_sharpe.png)

### QQ-Plot
![QQ plot](artifacts/figures/{PREFIX}_05_qq_plot.png)

### Crash Depth Tercile Returns
![Tercile returns](artifacts/figures/{PREFIX}_06_tercile_returns.png)

The "Crashed" tercile is the long leg; "Resilient" is the short leg. The spread shows whether recently punished coins consistently outperform resilient ones.

### IS vs OOS Dashboard
![IS vs OOS](artifacts/figures/{PREFIX}_07_is_oos_dashboard.png)

### Cumulative Return by Crash Depth Tercile
![Cumulative tercile](artifacts/figures/{PREFIX}_08_cumulative_tercile.png)

### Crash Depth vs Next-Week Return (Scatter)
![Crash vs rebound](artifacts/figures/{PREFIX}_09_crash_depth_vs_rebound.png)

Each point is a quantile bin of 8-week minimum return (x-axis, more negative = deeper crash) against average next-week return (y-axis). An upward slope would directly confirm the capitulation premium: the deeper the crash, the higher the subsequent return. The scatter makes the causal mechanism visible rather than just implied by the L/S spread.
"""
    (STAGE / "CRASH8_VIZ_REPORT.md").write_text(md)
    print("  wrote CRASH8_VIZ_REPORT.md")


def main():
    print("Loading data...")
    man   = load_manifest()
    trade = set(man["trading_universe"]["symbols_ever_eligible"])
    is_lo  = pd.Timestamp(man["split"]["in_sample"][0])
    is_hi  = pd.Timestamp(man["split"]["in_sample"][1])
    oos_lo = pd.Timestamp(man["split"]["out_of_sample"][0])
    oos_hi = pd.Timestamp(man["split"]["out_of_sample"][1])

    beh = pd.read_parquet(BEHAVIORAL_DATA / "behavioral_factor_returns.parquet")
    beh["week"] = pd.to_datetime(beh["week"])
    factor_ret = beh.set_index("week")["CRASH8_crashed_minus_resilient"].dropna()

    panel = pd.read_parquet(PANEL_DIR / "price_mcap_panel_weekly.parquet")
    panel["week"] = pd.to_datetime(panel["week"])
    panel = panel[panel["symbol"].isin(trade)]
    chars, _ = build_characteristics(panel, trade)
    chars["week"] = pd.to_datetime(chars["week"])

    print("Generating charts...")
    fig1 = chart_cumulative_return(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig2 = chart_rolling_return_significance(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig3, is_d, oos_d = chart_return_distribution(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig4 = chart_rolling_sharpe(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig5 = chart_qq_plot(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig6, _ = chart_tercile_returns(chars, is_lo, is_hi, oos_lo, oos_hi)
    fig7 = chart_is_oos_dashboard(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig8 = chart_cumulative_tercile(chars, is_lo, is_hi, oos_lo, oos_hi)
    fig9 = chart_crash_depth_vs_rebound(chars, is_lo, is_hi, oos_lo, oos_hi)

    charts = [(f"{PREFIX}_0{i+1}_{n}", f) for i,(n,f) in enumerate([
        ("cumulative_return", fig1), ("rolling_return_significance", fig2),
        ("return_distribution", fig3), ("rolling_sharpe", fig4), ("qq_plot", fig5),
        ("tercile_returns", fig6), ("is_oos_dashboard", fig7), ("cumulative_tercile", fig8),
        ("crash_depth_vs_rebound", fig9),
    ])]
    for name, fig in charts:
        fig.write_html(str(FIG_DIR / f"{name}.html"))
        fig.write_image(str(FIG_DIR / f"{name}.png"), scale=2)
        print(f"  saved {name}.png")

    pd.DataFrame({"ret": factor_ret}).to_parquet(DATA_DIR / f"{PREFIX}_viz_data.parquet")

    is_r  = factor_ret[(factor_ret.index>=is_lo) &(factor_ret.index<=is_hi)].dropna()
    oos_r = factor_ret[(factor_ret.index>=oos_lo)&(factor_ret.index<=oos_hi)].dropna()
    from statsmodels.tsa.stattools import adfuller
    try: adf = adfuller(factor_ret.dropna(), autolag="AIC"); adf_stat, adf_p = adf[0], adf[1]
    except Exception: adf_stat, adf_p = np.nan, np.nan
    jb_is,  jb_is_p  = sp_stats.jarque_bera(is_r)[:2]  if len(is_r)  > 5 else (np.nan, np.nan)
    jb_oos, jb_oos_p = sp_stats.jarque_bera(oos_r)[:2] if len(oos_r) > 5 else (np.nan, np.nan)
    write_report(is_d, oos_d, adf_stat, adf_p, jb_is, jb_is_p, jb_oos, jb_oos_p)
    print(f"\nAll done. Charts in {FIG_DIR}")


if __name__ == "__main__":
    main()
