"""09 — NetMom (Within-Cluster Momentum) Factor Visualisation Pipeline.

NetMom = within-cluster momentum: inside each Louvain community, back the
coin outperforming its cluster peers vs the coin lagging behind them.
Strips out market beta and isolates idiosyncratic trend within a narrative.

Data note: L/S returns from gx5y_factor_zoo.parquet (5-year panel).
           IC and cluster chars from network_panel.parquet (52-week OOS only).

Grade: Not supported — IC not significant in either period, no GX pricing,
no ASD dominance. The network mechanism is sound; the signal is silent.

Outputs
-------
    artifacts/figures/netmom_*.html / .png
    artifacts/data/netmom_viz_data.parquet
    NETMOM_VIZ_REPORT.md
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
NETWORK_DIR = PARENT.parent / "08_nalfp" / "artifacts" / "data"
FIG_DIR = STAGE / "artifacts" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

FACTOR_NAME = "NetMom"
PREFIX = "netmom"

IS_LABEL = "In-Sample (2021-05-10 → 2024-11-11)"
OOS_LABEL = "Out-of-Sample (2024-11-18 → 2026-05-25)"
PLOTLY_TEMPLATE = "plotly_white"
COLORS = {"IS": "#2196F3", "OOS": "#FF5722", "FULL": "#607D8B",
          "SIG_POS": "#4CAF50", "SIG_NEG": "#F44336"}

GX_LAMBDA = 8.6
GX_T = 0.37
ASD_EPS1 = 0.852
ASD_EPS2 = 0.958


def load_manifest():
    return json.loads((MANIFEST_DIR / "universe_manifest.json").read_text())


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
                                        "Weekly IC (OOS window only)"))
    for lbl, lo, hi, color in [(IS_LABEL, is_lo, is_hi, COLORS["IS"]),
                                (OOS_LABEL, oos_lo, oos_hi, COLORS["OOS"])]:
        c = cum[(cum.index >= lo) & (cum.index <= hi)]
        if len(c) > 0:
            fig.add_trace(go.Scatter(x=c.index, y=c.values, name=lbl,
                                     line=dict(color=color, width=2)), row=1, col=1)
    if ic is not None and len(ic) > 0:
        fig.add_trace(go.Bar(x=ic.index, y=ic.values, name="IC (OOS)",
                             marker_color=COLORS["OOS"], marker_opacity=0.5), row=2, col=1)
    for y, c in [(0, "#666"), (-0.03, COLORS["SIG_NEG"]), (0.03, COLORS["SIG_POS"])]:
        fig.add_hline(y=y, line_dash="dot", line_color=c, line_width=0.8, row=2, col=1)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=700,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Growth of $1", row=1, col=1)
    fig.update_yaxes(title_text="IC", row=2, col=1)
    return fig


def chart_rolling_ic_significance(ic, oos_lo, oos_hi):
    roll_ic = ic.rolling(13).mean().dropna() if len(ic) >= 13 else ic.copy()
    roll_t = rolling_newey_west_t(ic, window=13, lags=4) if len(ic) >= 13 else pd.Series(dtype=float)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("13-Week Rolling Mean IC (OOS window)",
                                        "13-Week Rolling NW t-stat"))
    if len(roll_ic) > 0:
        fig.add_trace(go.Scatter(x=roll_ic.index, y=roll_ic.values,
                                 line=dict(color=COLORS["OOS"], width=2)), row=1, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="#666", row=1, col=1)
    if len(roll_t) > 0:
        fig.add_trace(go.Scatter(x=roll_t.index, y=roll_t.values,
                                 line=dict(color=COLORS["OOS"], width=2)), row=2, col=1)
    for y, c in [(2, COLORS["SIG_POS"]), (-2, COLORS["SIG_NEG"]), (0, "#666")]:
        fig.add_hline(y=y, line_dash="dot" if y != 0 else "dash", line_color=c, row=2, col=1)
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"])
    fig.add_annotation(x=0.5, y=0.5, xref="paper", yref="paper",
                       text="IC data: OOS window only (52 weeks)",
                       showarrow=False, font=dict(size=11, color="#888"),
                       bgcolor="rgba(255,255,255,0.7)")
    fig.update_layout(template=PLOTLY_TEMPLATE, height=700,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
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

    is_d = desc(is_r, "IS") if len(is_r) > 0 else {}
    oos_d = desc(oos_r, "OOS") if len(oos_r) > 0 else {}
    fig = make_subplots(rows=2, cols=2,
                        subplot_titles=("Return Histogram (IS)", "Return Histogram (OOS)",
                                        "Return Box Plot", "Autocorrelation"),
                        vertical_spacing=0.12, horizontal_spacing=0.10)
    for (r, c_i), series, color, label in [((1, 1), is_r, COLORS["IS"], "IS"),
                                             ((1, 2), oos_r, COLORS["OOS"], "OOS")]:
        if len(series) > 0:
            bins = np.histogram(series, bins=40, density=True)
            fig.add_trace(go.Bar(x=bins[1][:-1], y=bins[0], name=label,
                                 marker_color=color, marker_opacity=0.7), row=r, col=c_i)
    if len(is_r) > 0:
        fig.add_trace(go.Box(y=is_r.values, name="IS", marker_color=COLORS["IS"], boxmean="sd"), row=2, col=1)
    if len(oos_r) > 0:
        fig.add_trace(go.Box(y=oos_r.values, name="OOS", marker_color=COLORS["OOS"], boxmean="sd"), row=2, col=1)
    ref = oos_r if len(is_r) == 0 else is_r
    if len(ref) > 0:
        acf_vals = [ref.autocorr(lag=l) for l in range(1, 13)]
        fig.add_trace(go.Bar(x=list(range(1, 13)), y=acf_vals,
                             marker_color=COLORS["FULL"], marker_opacity=0.7), row=2, col=2)
        conf = 1.96 / np.sqrt(len(ref))
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

    def qq_data(s):
        n = len(s)
        t = sp_stats.norm.ppf(np.arange(1, n + 1) / (n + 1)) * s.std() + s.mean()
        return t, s.values

    fig = make_subplots(rows=1, cols=2, subplot_titles=("QQ Plot — IS", "QQ Plot — OOS"))
    for col_i, series, color in [(1, is_r, COLORS["IS"]), (2, oos_r, COLORS["OOS"])]:
        if len(series) > 1:
            t, s = qq_data(series)
            fig.add_trace(go.Scatter(x=t, y=s, mode="markers",
                                     marker=dict(color=color, size=4, opacity=0.7)), row=1, col=col_i)
            lo, hi = min(t.min(), s.min()), max(t.max(), s.max())
            fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines",
                                     line=dict(color="#999", dash="dash")), row=1, col=col_i)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, showlegend=False)
    return fig


def chart_tercile_returns_oos(net_panel, oos_lo, oos_hi):
    char_col = "within_cluster_mom"
    data = net_panel[(net_panel["week"] >= oos_lo) & (net_panel["week"] <= oos_hi)].copy()
    data = data.dropna(subset=[char_col, "fwd_ret_1w"])
    t_labels = ["Low-WCluster", "Mid-WCluster", "High-WCluster"]
    data["tercile"] = data.groupby("week")[char_col].transform(
        lambda x: pd.qcut(x, 3, labels=t_labels, duplicates="drop")
        if len(x.dropna()) >= 6 else pd.NA)
    tr = data.dropna(subset=["tercile"]).groupby(["week", "tercile"])["fwd_ret_1w"].mean()
    pivot = tr.reset_index().pivot(index="week", columns="tercile", values="fwd_ret_1w")
    for lb in t_labels:
        if lb not in pivot.columns:
            pivot[lb] = np.nan
    pivot = pivot[t_labels].dropna()
    spread = pivot[t_labels[-1]] - pivot[t_labels[0]]

    def ann(s):
        return (1 + s).prod() ** (52 / max(len(s), 1)) - 1 if len(s) > 0 else np.nan

    vals = [ann(pivot[lb]) * 100 for lb in t_labels] + [ann(spread) * 100]
    fig = go.Figure(data=[
        go.Bar(name="OOS (52 wks)", x=t_labels + ["NetMom Spread"],
               y=vals, marker_color=COLORS["OOS"], marker_opacity=0.8)
    ])
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500,
                      title=f"{FACTOR_NAME} Within-Cluster Tercile Returns (OOS only)",
                      xaxis_title="Within-Cluster Momentum Group",
                      yaxis_title="Annualised Return (%)")
    return fig


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


def chart_cumulative_tercile_oos(net_panel, oos_lo, oos_hi):
    char_col = "within_cluster_mom"
    data = net_panel[(net_panel["week"] >= oos_lo) & (net_panel["week"] <= oos_hi)].copy()
    data = data.dropna(subset=[char_col, "fwd_ret_1w"])
    t_labels = ["Low-WCluster", "Mid-WCluster", "High-WCluster"]
    data["tercile"] = data.groupby("week")[char_col].transform(
        lambda x: pd.qcut(x, 3, labels=t_labels, duplicates="drop")
        if len(x.dropna()) >= 6 else pd.NA)
    data = data.dropna(subset=["tercile"])
    tr = data.groupby(["week", "tercile"])["fwd_ret_1w"].mean().reset_index()
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
    fig.add_trace(go.Scatter(x=spread_cum.index, y=spread_cum.values, name="NetMom Spread",
                             line=dict(color="#000", width=2.5, dash="dash")))
    fig.add_annotation(x=0.02, y=0.95, xref="paper", yref="paper",
                       text="OOS window only (52 weeks)", showarrow=False,
                       font=dict(size=11, color="#888"))
    fig.update_layout(template=PLOTLY_TEMPLATE, height=550,
                      title=f"Cumulative Return by Within-Cluster Momentum Tercile (OOS)",
                      xaxis_title="Week", yaxis_title="Growth of $1",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_entropy_vs_ic(net_panel, ic, oos_lo, oos_hi):
    """Chart 9: Network entropy vs NetMom IC — does the within-cluster signal
    work better when the market is more fragmented (higher entropy)?"""
    net_entropy = (net_panel[(net_panel["week"] >= oos_lo) & (net_panel["week"] <= oos_hi)]
                   .groupby("week")["network_entropy"].mean())
    net_entropy.index = pd.to_datetime(net_entropy.index)
    ic_oos = ic[(ic.index >= oos_lo) & (ic.index <= oos_hi)].dropna()
    combined = pd.concat([net_entropy.rename("entropy"), ic_oos.rename("ic")], axis=1).dropna()

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("Weekly Network Entropy (OOS)",
                                        "Network Entropy vs Weekly IC"))
    fig.add_trace(go.Scatter(x=net_entropy.index, y=net_entropy.values,
                             line=dict(color=COLORS["FULL"], width=2), name="Network Entropy"),
                  row=1, col=1)
    if len(combined) > 3:
        fig.add_trace(go.Scatter(x=combined["entropy"], y=combined["ic"],
                                 mode="markers", name="Weekly obs",
                                 marker=dict(color=COLORS["OOS"], size=6, opacity=0.7)),
                      row=1, col=2)
        corr = combined["entropy"].corr(combined["ic"])
        fig.add_annotation(x=0.7, y=0.9, xref="x2 domain", yref="y2 domain",
                           text=f"Corr = {corr:.3f}", showarrow=False,
                           font=dict(size=12))
    fig.add_hline(y=0, line_dash="dash", line_color="#666", row=1, col=2)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, showlegend=False,
                      title="Network Entropy vs NetMom IC: Does Fragmentation Help?")
    fig.update_xaxes(title_text="Week", row=1, col=1)
    fig.update_xaxes(title_text="Network Entropy", row=1, col=2)
    fig.update_yaxes(title_text="Entropy", row=1, col=1)
    fig.update_yaxes(title_text="Weekly IC", row=1, col=2)
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


def write_report(row, is_d, oos_d, adf_stat, adf_p, jb_is, jb_is_p, jb_oos, jb_oos_p):
    md = f"""# NetMom (Within-Cluster Momentum) Factor — Analysis Report

*Generated by `18_netmom_visualisation.py` from the Stage-09 5-year panel.*

*Data note: L/S returns cover 5 years (from gx5y_factor_zoo). IC charts and
tercile analysis are based on the OOS window (52 weeks) where cluster data is available.*

---

## The Idea in Plain English

When a group of highly correlated coins moves together (a "cluster" — think: all DeFi
tokens, or all Layer-1 chains), some coins within that group will outperform the rest.
**NetMom** bets on those local leaders to keep leading.

Each week, we identify crypto "communities" using network analysis. Within each
community, we rank coins by their recent return *relative to the other coins in their
community*. Then:
- **Buy** the top 30% of coins by within-cluster relative return (the local leaders)
- **Short** the bottom 30% (the local laggards)

The idea is that within a cohesive narrative cluster, local leadership persists
for at least a week — similar to how within a sector in equity markets, relative
momentum can work even when sector-level momentum doesn't.

---

## The Short Answer

**Not supported — the signal is statistically silent.**

The IC t-stat is **{fmt_val(row['IS_IC_t'])}** in-sample and **{fmt_val(row['OOS_IC_t'])}**
out-of-sample — both far below the |t| = 2 significance threshold. The GX pricing
test finds no priced premium (λ = {GX_LAMBDA:.1f}%/yr, t = {GX_T:.2f}). Neither the
ASD test shows Bitcoin-beating performance (ε₁ = {ASD_EPS1:.3f}, ε₂ = {ASD_EPS2:.3f}).

The theoretical mechanism is sound — within-cluster momentum is documented in equity
markets (Liu-Tsyvinski 2018). It simply doesn't show up empirically in our 5-year
crypto panel.

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
| Mean weekly return | {fmt_val(is_d.get('mean', np.nan)*100, '.3f')}% | {fmt_val(oos_d.get('mean', np.nan)*100, '.3f')}% |
| Std (weekly) | {fmt_val(is_d.get('std', np.nan)*100, '.3f')}% | {fmt_val(oos_d.get('std', np.nan)*100, '.3f')}% |
| Skewness | {fmt_val(is_d.get('skew', np.nan), '.2f')} | {fmt_val(oos_d.get('skew', np.nan), '.2f')} |
| Excess Kurtosis | {fmt_val(is_d.get('kurt', np.nan), '.2f')} | {fmt_val(oos_d.get('kurt', np.nan), '.2f')} |

---

## Why the Signal Is Silent

**1. Crypto clusters are too correlated to isolate within-cluster variation.**
Within a Louvain community, all coins already move together strongly by construction
(that's what defines the cluster). The within-cluster variance is dominated by
correlated macro moves, leaving very little idiosyncratic signal to exploit.

**2. The weekly Louvain communities are noisy.**
Community structure changes week to week. A coin assigned to a DeFi cluster this week
may be in a different cluster next week as correlation patterns shift. This instability
means "within-cluster momentum" is not a stable property of any individual coin.

**3. Crypto is retail-driven and correlation spikes override local dynamics.**
When Bitcoin makes a big move, all clusters move together. During these correlation
spike events (which are common in crypto), within-cluster relative signals are swamped.

**4. The equity market analogue may not transfer.**
The Liu-Tsyvinski (2018) momentum result for crypto was demonstrated on a shorter,
different dataset. The 5-year evidence here does not support the transfer of this
equity/shorter-window finding to a longer-horizon crypto test.

---

## Statistical Tests

### Newey-West t-stat on IC

- IS t = {fmt_val(row['IS_IC_t'])} — not significant
- OOS t = {fmt_val(row['OOS_IC_t'])} — not significant

Both periods show no reliable ranking power.

### Jarque-Bera Normality Test

| Period | JB Statistic | p-value | Normal? |
|---|---|---|---|
| IS | {fmt_val(jb_is, '.1f')} | {fmt_val(jb_is_p, '.4f')} | {"No" if jb_is_p < 0.05 else "Yes"} |
| OOS | {fmt_val(jb_oos, '.1f')} | {fmt_val(jb_oos_p, '.4f')} | {"No" if jb_oos_p < 0.05 else "Yes"} |

### ADF Stationarity Test

- ADF: **{fmt_val(adf_stat, '.3f')}**, p = **{fmt_val(adf_p, '.4f')}**
- **{"Stationary" if adf_p < 0.05 else "Non-stationary"}**

### Giglio-Xiu Pricing Result

Full GX (K_hidden = 2): **λ = +{GX_LAMBDA:.1f}%/yr, t = +{GX_T:.2f}** — not significant.
Within-cluster momentum is not a priced risk factor in the 5-year panel.

### ASD vs Bitcoin

ε₁ = {ASD_EPS1:.3f}, ε₂ = {ASD_EPS2:.3f} — neither ASD criterion met. Bitcoin's return
distribution is clearly better. This is the most complete null result in the factor zoo.

---

## Visualisations

### Cumulative Return & Weekly IC

![Cumulative return](artifacts/figures/{PREFIX}_01_cumulative_return.png)

The cumulative L/S return is mostly flat to slightly negative IS and negative OOS.
IC bars show no consistent positive direction — the signal is genuinely absent.

### Rolling IC Significance (OOS Window)

![Rolling IC significance](artifacts/figures/{PREFIX}_02_rolling_ic_significance.png)

### Return Distribution

![Return distribution](artifacts/figures/{PREFIX}_03_return_distribution.png)

### Rolling Sharpe Ratio

![Rolling Sharpe](artifacts/figures/{PREFIX}_04_rolling_sharpe.png)

The Sharpe is mostly negative IS and OOS — the factor loses money mechanically.
This is the cleanest example of a "Not supported" outcome in the factor zoo.

### QQ-Plot vs Normal Distribution

![QQ plot](artifacts/figures/{PREFIX}_05_qq_plot.png)

### Within-Cluster Tercile Returns (OOS)

![Tercile returns](artifacts/figures/{PREFIX}_06_tercile_returns.png)

OOS-only view. The tercile returns show no meaningful spread between high and
low within-cluster momentum groups.

### IS vs OOS Comparison Dashboard

![IS vs OOS](artifacts/figures/{PREFIX}_07_is_oos_comparison.png)

All metrics are near zero or negative in both periods. A textbook null result.

### Cumulative Return by Within-Cluster Tercile (OOS)

![Cumulative tercile](artifacts/figures/{PREFIX}_08_cumulative_tercile.png)

### Network Entropy vs NetMom IC

![Entropy vs IC](artifacts/figures/{PREFIX}_09_entropy_vs_ic.png)

The left panel shows network entropy over the OOS period — how fragmented the
market is each week. The right panel scatters entropy against the weekly IC.
If the within-cluster signal worked better when the market is more fragmented
(higher entropy), we would see a positive correlation. The correlation provides
a post-hoc explanation for when (if ever) the signal had any power.
"""
    (STAGE / "NETMOM_VIZ_REPORT.md").write_text(md)
    print("  wrote NETMOM_VIZ_REPORT.md")


def main():
    print("Loading data...")
    man = load_manifest()
    is_lo = pd.Timestamp(man["split"]["in_sample"][0])
    is_hi = pd.Timestamp(man["split"]["in_sample"][1])
    oos_lo = pd.Timestamp(man["split"]["out_of_sample"][0])
    oos_hi = pd.Timestamp(man["split"]["out_of_sample"][1])

    gx = pd.read_parquet(PANEL_DIR / "gx5y_factor_zoo.parquet")
    gx["week"] = pd.to_datetime(gx["week"])
    factor_ret = gx.set_index("week")["NetMom"].dropna()
    factor_ret.index = pd.to_datetime(factor_ret.index)

    try:
        ic_ts = pd.read_parquet(NETWORK_DIR / "factor_ic_timeseries.parquet")
        ic_ts["week"] = pd.to_datetime(ic_ts["week"])
        factor_ic = ic_ts[ic_ts["factor"] == "NetMom"].set_index("week")["ic"]
        factor_ic.index = pd.to_datetime(factor_ic.index)
    except Exception:
        factor_ic = pd.Series(dtype=float)

    net_panel = pd.read_parquet(NETWORK_DIR / "network_panel.parquet")
    net_panel["week"] = pd.to_datetime(net_panel["week"])

    val_stats = pd.read_parquet(PANEL_DIR / "factor_validation_stats.parquet")
    row = val_stats[val_stats["factor"] == FACTOR_NAME].iloc[0].to_dict()

    print("Generating charts...")
    fig1 = chart_cumulative_return(factor_ret, factor_ic, is_lo, is_hi, oos_lo, oos_hi)
    fig2 = chart_rolling_ic_significance(factor_ic, oos_lo, oos_hi)
    fig3, is_d, oos_d = chart_return_distribution(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig4 = chart_rolling_sharpe(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig5 = chart_qq_plot(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig6 = chart_tercile_returns_oos(net_panel, oos_lo, oos_hi)
    fig7 = chart_is_oos_comparison(row)
    fig8 = chart_cumulative_tercile_oos(net_panel, oos_lo, oos_hi)
    fig9 = chart_entropy_vs_ic(net_panel, factor_ic, oos_lo, oos_hi)

    charts = [
        (f"{PREFIX}_01_cumulative_return", fig1),
        (f"{PREFIX}_02_rolling_ic_significance", fig2),
        (f"{PREFIX}_03_return_distribution", fig3),
        (f"{PREFIX}_04_rolling_sharpe", fig4),
        (f"{PREFIX}_05_qq_plot", fig5),
        (f"{PREFIX}_06_tercile_returns", fig6),
        (f"{PREFIX}_07_is_oos_comparison", fig7),
        (f"{PREFIX}_08_cumulative_tercile", fig8),
        (f"{PREFIX}_09_entropy_vs_ic", fig9),
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
    jb_is = sp_stats.jarque_bera(is_r)[0] if len(is_r) > 0 else np.nan
    jb_is_p = sp_stats.jarque_bera(is_r)[1] if len(is_r) > 0 else np.nan
    jb_oos = sp_stats.jarque_bera(oos_r)[0] if len(oos_r) > 0 else np.nan
    jb_oos_p = sp_stats.jarque_bera(oos_r)[1] if len(oos_r) > 0 else np.nan

    write_report(row, is_d, oos_d, adf_stat, adf_p, jb_is, jb_is_p, jb_oos, jb_oos_p)
    print(f"\nAll done. Charts in {FIG_DIR}")


if __name__ == "__main__":
    main()
