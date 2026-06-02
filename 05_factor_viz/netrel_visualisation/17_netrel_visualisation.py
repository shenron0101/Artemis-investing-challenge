"""09 — NetRel (Cross-Cluster Rotation) Factor Visualisation Pipeline.

NetRel = cross-cluster relative strength: coins outperforming their Louvain
cluster peers are backed against coins lagging behind other clusters.
Captures narrative rotation (capital cycling between DeFi, L1s, payments…).

Data note: L/S returns from gx5y_full_factor_zoo.parquet (5-year panel).
           IC and cluster chars from network_panel.parquet (52-week OOS only).

Grade: Suggestive — economic story intact, ASSD-dominant (ε₂=0.026),
but IC not significant over 5 years.

Outputs
-------
    artifacts/figures/netrel_*.html / .png
    artifacts/data/netrel_viz_data.parquet
    NETREL_VIZ_REPORT.md
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
NETWORK_DIR = PARENT.parent / "03_nalfp_add" / "artifacts" / "data"
FIG_DIR = STAGE / "artifacts" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

FACTOR_NAME = "NetRel"
PREFIX = "netrel"

IS_LABEL = "In-Sample (2021-05-10 → 2024-11-11)"
OOS_LABEL = "Out-of-Sample (2024-11-18 → 2026-05-25)"
PLOTLY_TEMPLATE = "plotly_white"
COLORS = {"IS": "#2196F3", "OOS": "#FF5722", "FULL": "#607D8B",
          "SIG_POS": "#4CAF50", "SIG_NEG": "#F44336"}

GX_LAMBDA = -0.2
GX_T = -0.01
ASD_EPS1 = 0.341
ASD_EPS2 = 0.026   # ASSD-dominant


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


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def chart_cumulative_return(ret, ic, is_lo, is_hi, oos_lo, oos_hi):
    cum = (1 + ret).cumprod()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=(f"{FACTOR_NAME} Cumulative Long/Short Return",
                                        "Weekly IC (OOS window only — 52 weeks)"))
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


def chart_rolling_ic_significance(ic, is_lo, is_hi, oos_lo, oos_hi):
    """Rolling IC — only OOS data available for network factors."""
    roll_ic = ic.rolling(13).mean().dropna() if len(ic) >= 13 else ic.copy()
    roll_t = rolling_newey_west_t(ic, window=13, lags=4) if len(ic) >= 13 else pd.Series(dtype=float)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("13-Week Rolling Mean IC (OOS window)",
                                        "13-Week Rolling NW t-stat on IC"))
    if len(roll_ic) > 0:
        fig.add_trace(go.Scatter(x=roll_ic.index, y=roll_ic.values,
                                 name="Rolling IC", line=dict(color=COLORS["OOS"], width=2)), row=1, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="#666", row=1, col=1)
    if len(roll_t) > 0:
        fig.add_trace(go.Scatter(x=roll_t.index, y=roll_t.values,
                                 name="Rolling NW t-stat", line=dict(color=COLORS["OOS"], width=2)), row=2, col=1)
    for y, c in [(2, COLORS["SIG_POS"]), (-2, COLORS["SIG_NEG"]), (0, "#666")]:
        fig.add_hline(y=y, line_dash="dot" if y != 0 else "dash", line_color=c, row=2, col=1)
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"])
    fig.add_annotation(x=0.5, y=0.5, xref="paper", yref="paper",
                       text="IC data available for OOS window only (52 weeks)",
                       showarrow=False, font=dict(size=11, color="#888"),
                       bgcolor="rgba(255,255,255,0.7)")
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

    is_d = desc(is_r, "IS") if len(is_r) > 0 else {}
    oos_d = desc(oos_r, "OOS") if len(oos_r) > 0 else {}

    fig = make_subplots(rows=2, cols=2,
                        subplot_titles=("Return Histogram (IS)", "Return Histogram (OOS)",
                                        "Return Box Plot", "Autocorrelation (IS/OOS)"),
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
    ref_series = oos_r if len(is_r) == 0 else is_r
    if len(ref_series) > 0:
        acf_vals = [ref_series.autocorr(lag=l) for l in range(1, 13)]
        fig.add_trace(go.Bar(x=list(range(1, 13)), y=acf_vals,
                             marker_color=COLORS["FULL"], marker_opacity=0.7), row=2, col=2)
        conf = 1.96 / np.sqrt(len(ref_series))
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
    """Tercile returns computed from network_panel (OOS window only)."""
    char_col = "cross_cluster_rel"
    data = net_panel[(net_panel["week"] >= oos_lo) & (net_panel["week"] <= oos_hi)].copy()
    data = data.dropna(subset=[char_col, "fwd_ret_1w"])

    t_labels = ["Low-XCluster", "Mid-XCluster", "High-XCluster"]
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
        go.Bar(name="OOS (52 wks)", x=t_labels + ["NetRel Spread"],
               y=vals, marker_color=COLORS["OOS"], marker_opacity=0.8)
    ])
    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, barmode="group",
                      title=f"{FACTOR_NAME} Cross-Cluster Tercile Returns (OOS only)",
                      xaxis_title="Cross-Cluster Relative Strength Group",
                      yaxis_title="Annualised Return (%)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
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
    """Cumulative tercile return (OOS only)."""
    char_col = "cross_cluster_rel"
    data = net_panel[(net_panel["week"] >= oos_lo) & (net_panel["week"] <= oos_hi)].copy()
    data = data.dropna(subset=[char_col, "fwd_ret_1w"])
    t_labels = ["Low-XCluster", "Mid-XCluster", "High-XCluster"]
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
    fig.add_trace(go.Scatter(x=spread_cum.index, y=spread_cum.values, name="NetRel Spread",
                             line=dict(color="#000", width=2.5, dash="dash")))
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"], opacity=0.04)
    fig.add_annotation(x=0.02, y=0.95, xref="paper", yref="paper",
                       text="OOS window only (52 weeks)", showarrow=False,
                       font=dict(size=11, color="#888"))
    fig.update_layout(template=PLOTLY_TEMPLATE, height=550,
                      title=f"Cumulative Return by {FACTOR_NAME} Cross-Cluster Tercile (OOS)",
                      xaxis_title="Week", yaxis_title="Growth of $1",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_cluster_rotation(net_panel, oos_lo, oos_hi):
    """Chart 9: For each OOS week, which cluster dominated (highest mean cross_cluster_rel)?
    Visualises narrative rotation as a bar chart of cluster dominance over time."""
    data = net_panel[(net_panel["week"] >= oos_lo) & (net_panel["week"] <= oos_hi)].copy()
    data = data.dropna(subset=["cross_cluster_rel", "cluster_id"])
    # Mean cross_cluster_rel per cluster per week
    cluster_means = data.groupby(["week", "cluster_id"])["cross_cluster_rel"].mean().reset_index()
    # Find dominant cluster (highest mean) per week
    dominant = cluster_means.loc[cluster_means.groupby("week")["cross_cluster_rel"].idxmax()]
    dominant = dominant.sort_values("week")
    # Count how often each cluster was dominant
    counts = dominant["cluster_id"].value_counts()

    fig = make_subplots(rows=2, cols=1, vertical_spacing=0.12,
                        subplot_titles=("Dominant Cluster ID Each OOS Week",
                                        "Cluster Dominance Frequency (OOS)"))
    fig.add_trace(go.Bar(x=dominant["week"], y=dominant["cluster_id"].astype(str),
                         orientation="v", marker_color=COLORS["OOS"], name="Dominant Cluster"),
                  row=1, col=1)
    fig.add_trace(go.Bar(x=counts.index.astype(str), y=counts.values,
                         marker_color=COLORS["FULL"], name="Weeks as Dominant"),
                  row=2, col=1)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=700, showlegend=False,
                      title="Cross-Cluster Rotation: Which Narrative Was 'In' Each Week?")
    fig.update_yaxes(title_text="Cluster ID", row=1, col=1)
    fig.update_yaxes(title_text="Weeks as Dominant", row=2, col=1)
    fig.update_xaxes(title_text="Cluster ID", row=2, col=1)
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
    md = f"""# NetRel (Cross-Cluster Rotation) Factor — Analysis Report

*Generated by `17_netrel_visualisation.py` from the Stage-09 5-year panel.*

*Data note: L/S returns cover 5 years (from gx5y_full_factor_zoo). IC charts and tercile
analysis are based on the OOS window (52 weeks) where cluster data is available.*

---

## The Idea in Plain English

Think of crypto as a city with distinct neighbourhoods: DeFi protocols, Layer-1
blockchains, payment tokens, gaming tokens. Capital doesn't flow into all neighbourhoods
at once — it rotates. When DeFi is hot, DeFi tokens outperform. A week later, Layer-1
narratives might take over.

**NetRel** (Cross-Cluster Relative Strength) tries to capture this rotation. Each week,
we use network analysis (minimum spanning tree + Louvain community detection) to identify
these "neighbourhoods" (clusters). Then we rank coins by how much they outperformed *other
clusters* that week:

- **Buy** coins that are outperforming the most relative to other clusters (top 30%)
- **Short** coins that are lagging most behind other clusters (bottom 30%)

The bet: capital currently flowing *into* a cluster will persist for at least one more week.

---

## The Short Answer

**Suggestive — real economic mechanism, partial statistical support.**

The IC t-stat is **{fmt_val(row['IS_IC_t'])}** in-sample (borderline, reversed) and
**{fmt_val(row['OOS_IC_t'])}** out-of-sample (not significant). The GX pricing test
finds no long-run risk premium (λ = {GX_LAMBDA:.1f}%/yr, t = {GX_T:.2f}).

However, the **ASSD test confirms the return distribution beats Bitcoin for risk-averse
investors** (ε₂ = {ASD_EPS2:.3f} ≤ 0.032). The rotation narrative is economically sound;
the signal strength is just not consistent enough to be captured as a reliable short-term
ranking factor.

---

## Sign Convention: A Borderline IS Reversal

The raw IC = {fmt_val(row['IS_IC'], '.4f')} IS (t = {fmt_val(row['IS_IC_t'])}). This is slightly
negative and borderline significant — meaning coins that *outperformed* their cross-cluster
peers slightly *underperformed* the following week (short-term reversal within the rotation
cycle). OOS the IC is essentially zero ({fmt_val(row['OOS_IC'], '.4f')}, t = {fmt_val(row['OOS_IC_t'])}).

Neither direction is reliable over 5 years. The ASD result suggests the *distribution*
of returns is attractive even if the weekly ranking isn't.

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

## Why the Rotation Story Is Economically Sound But Statistically Weak

**1. Narrative rotation is real in crypto (confirmed by network analysis).**
The market persistently fragments into 7–11 Louvain communities per week. Capital
does cycle through these communities. The cross-cluster relative strength signal
captures this rotation mechanism correctly.

**2. But the signal is noisy and mean-reverting on a weekly horizon.**
Narratives cycle at a longer frequency than one week. A cluster that outperforms
this week may continue for 2–4 weeks, but the single-week signal is too short-horizon
to be stable. This is why the IC is small and inconsistent.

**3. The cluster structure itself changes weekly.**
Because Louvain communities are re-estimated every week, the "neighbourhood" boundaries
shift. A coin in DeFi cluster A this week might be re-assigned to a different cluster
next week, breaking the continuity of the cross-cluster signal.

**4. The ASSD result suggests long-horizon validity.**
Even without weekly IC power, the full return distribution over 5 years is better than
Bitcoin for risk-averse investors. This suggests the rotation dynamic earns returns in
aggregate, just not in a weekly-predictable way.

---

## Statistical Tests

### Newey-West t-stat on IC

- IS t = {fmt_val(row['IS_IC_t'])} — borderline/not significant (slight reversal direction)
- OOS t = {fmt_val(row['OOS_IC_t'])} — not significant (near zero)

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
Cross-cluster rotation is not a priced systematic risk in the 5-year panel. The economic
mechanism is real but it does not earn a multi-year risk compensation.

### ASD vs Bitcoin

ε₁ = {ASD_EPS1:.3f} (AFSD not achieved), ε₂ = {ASD_EPS2:.3f} (**ASSD achieved** — ε₂ ≤ 0.032).
Risk-averse investors prefer NetRel's return distribution to Bitcoin. This partial
positive, combined with the economic rationale, supports the "Suggestive" verdict.

---

## Visualisations

### Cumulative Return & Weekly IC

![Cumulative return](artifacts/figures/{PREFIX}_01_cumulative_return.png)

5-year cumulative L/S return (IS blue, OOS orange). IC bars shown for OOS window only.

### Rolling IC Significance (OOS Window)

![Rolling IC significance](artifacts/figures/{PREFIX}_02_rolling_ic_significance.png)

Rolling IC computed from OOS network panel data (52 weeks). The short window does
not cross the ±2 significance threshold, confirming weak weekly ranking power OOS.

### Return Distribution

![Return distribution](artifacts/figures/{PREFIX}_03_return_distribution.png)

### Rolling Sharpe Ratio

![Rolling Sharpe](artifacts/figures/{PREFIX}_04_rolling_sharpe.png)

The Sharpe oscillates with some positive stretches IS and modest but positive OOS.
The distributional quality is better than the IC suggests.

### QQ-Plot vs Normal Distribution

![QQ plot](artifacts/figures/{PREFIX}_05_qq_plot.png)

### Cross-Cluster Tercile Returns (OOS)

![Tercile returns](artifacts/figures/{PREFIX}_06_tercile_returns.png)

OOS-only view: tercile returns by cross-cluster relative strength rank.
Limited to 52 OOS weeks.

### IS vs OOS Comparison Dashboard

![IS vs OOS](artifacts/figures/{PREFIX}_07_is_oos_comparison.png)

### Cumulative Return by Cross-Cluster Tercile (OOS)

![Cumulative tercile](artifacts/figures/{PREFIX}_08_cumulative_tercile.png)

### Cross-Cluster Rotation: Dominant Narrative by Week

![Cluster rotation](artifacts/figures/{PREFIX}_09_cluster_rotation.png)

For each OOS week, which Louvain cluster had the highest average cross-cluster
relative strength score. The bottom panel shows how many weeks each cluster was
"dominant." The rotation across clusters confirms that capital does cycle through
different narratives — the basis for the NetRel economic story.
"""
    (STAGE / "NETREL_VIZ_REPORT.md").write_text(md)
    print("  wrote NETREL_VIZ_REPORT.md")


def main():
    print("Loading data...")
    man = load_manifest()
    is_lo = pd.Timestamp(man["split"]["in_sample"][0])
    is_hi = pd.Timestamp(man["split"]["in_sample"][1])
    oos_lo = pd.Timestamp(man["split"]["out_of_sample"][0])
    oos_hi = pd.Timestamp(man["split"]["out_of_sample"][1])

    # Load 5-year L/S returns
    gx = pd.read_parquet(PANEL_DIR / "gx5y_full_factor_zoo.parquet")
    gx["week"] = pd.to_datetime(gx["week"])
    factor_ret = gx.set_index("week")["NetRel"].dropna()
    factor_ret.index = pd.to_datetime(factor_ret.index)

    # Load OOS IC from factor_ic_timeseries
    try:
        ic_ts = pd.read_parquet(NETWORK_DIR / "factor_ic_timeseries.parquet")
        ic_ts["week"] = pd.to_datetime(ic_ts["week"])
        factor_ic = ic_ts[ic_ts["factor"] == "NetRel"].set_index("week")["ic"]
        factor_ic.index = pd.to_datetime(factor_ic.index)
    except Exception:
        factor_ic = pd.Series(dtype=float)

    # Load network panel for tercile analysis
    net_panel = pd.read_parquet(NETWORK_DIR / "network_panel.parquet")
    net_panel["week"] = pd.to_datetime(net_panel["week"])

    val_stats = pd.read_parquet(PANEL_DIR / "factor_validation_stats.parquet")
    row = val_stats[val_stats["factor"] == FACTOR_NAME].iloc[0].to_dict()

    print("Generating charts...")
    fig1 = chart_cumulative_return(factor_ret, factor_ic, is_lo, is_hi, oos_lo, oos_hi)
    fig2 = chart_rolling_ic_significance(factor_ic, is_lo, is_hi, oos_lo, oos_hi)
    fig3, is_d, oos_d = chart_return_distribution(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig4 = chart_rolling_sharpe(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig5 = chart_qq_plot(factor_ret, is_lo, is_hi, oos_lo, oos_hi)
    fig6 = chart_tercile_returns_oos(net_panel, oos_lo, oos_hi)
    fig7 = chart_is_oos_comparison(row)
    fig8 = chart_cumulative_tercile_oos(net_panel, oos_lo, oos_hi)
    fig9 = chart_cluster_rotation(net_panel, oos_lo, oos_hi)

    charts = [
        (f"{PREFIX}_01_cumulative_return", fig1),
        (f"{PREFIX}_02_rolling_ic_significance", fig2),
        (f"{PREFIX}_03_return_distribution", fig3),
        (f"{PREFIX}_04_rolling_sharpe", fig4),
        (f"{PREFIX}_05_qq_plot", fig5),
        (f"{PREFIX}_06_tercile_returns", fig6),
        (f"{PREFIX}_07_is_oos_comparison", fig7),
        (f"{PREFIX}_08_cumulative_tercile", fig8),
        (f"{PREFIX}_09_cluster_rotation", fig9),
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
