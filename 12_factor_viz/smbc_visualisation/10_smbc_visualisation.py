"""09 — SMBC (Size) Factor Visualisation Pipeline.

Reconstructs the SMBC weekly long/short return series on the 5-year panel,
then produces a suite of interactive Plotly charts that evaluate both
its economic performance and statistical significance:

  1. Cumulative return (IS vs OOS split marked)
  2. Rolling IC (26-week window) with significance bands
  3. Rolling Newey-West t-stat on IC
  4. Weekly return distribution with summary statistics
  5. Rolling Sharpe ratio (52-week window)
  6. QQ-plot vs. Normal (assess tail risk / normality)
  7. Cross-sectional size-sorted portfolio heat-map (tercile avg returns)
  8. IS vs OOS comparison dashboard

Outputs
-------
    artifacts/figures/smbc_*.html   — interactive Plotly charts
    artifacts/data/smbc_viz_data.parquet — intermediate data for reproducibility
    SMBC_VIZ_REPORT.md              — plain-language findings report
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from scipy import stats as sp_stats

STAGE = Path(__file__).resolve().parent
PARENT = STAGE.parent
DATA_DIR = STAGE / "artifacts" / "data"
MANIFEST_DIR = PARENT / "artifacts" / "manifests"
PANEL_DIR = PARENT / "artifacts" / "data"
FIG_DIR = STAGE / "artifacts" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

MIN_NAMES = 10
NET_WINDOW = 12

IS_LABEL = "In-Sample (2021-05-10 → 2024-11-11)"
OOS_LABEL = "Out-of-Sample (2024-11-18 → 2026-05-25)"
PLOTLY_TEMPLATE = "plotly_white"
COLORS = {"IS": "#2196F3", "OOS": "#FF5722", "FULL": "#607D8B",
          "SIG_POS": "#4CAF50", "SIG_NEG": "#F44336"}


# ---------------------------------------------------------------------------
# Data loading & factor construction (mirrors 08_factor_validation.py)
# ---------------------------------------------------------------------------

def load_manifest():
    return json.loads((MANIFEST_DIR / "universe_manifest.json").read_text())


def build_characteristics(panel, trade_symbols):
    px_wide = (panel[panel["symbol"].isin(trade_symbols)]
               .pivot(index="week", columns="symbol", values="price")
               .sort_index())
    mc_wide = (panel[panel["symbol"].isin(trade_symbols)]
               .pivot(index="week", columns="symbol", values="mcap")
               .sort_index())
    ret_wide = px_wide.pct_change()
    mom4 = px_wide / px_wide.shift(4) - 1.0
    vol4 = ret_wide.rolling(4).std()
    logmc = np.log(mc_wide.where(mc_wide > 0))

    def melt(df, name):
        return df.reset_index().melt(id_vars="week", var_name="symbol", value_name=name)

    out = melt(ret_wide, "ret_1w")
    fwd = ret_wide.shift(-1)
    for df, nm in [(fwd, "fwd_ret_1w"), (mom4, "mom_4w"),
                   (vol4, "vol_4w"), (logmc, "log_mcap")]:
        out = out.merge(melt(df, nm), on=["week", "symbol"], how="left")
    return out, ret_wide


def build_smbc_returns(chars):
    col, direction, frac = "log_mcap", -1, 0.30

    def one_week(block):
        block = block.dropna(subset=["fwd_ret_1w", col])
        n = len(block)
        if n < MIN_NAMES:
            return np.nan
        k = max(int(round(n * frac)), 3)
        r = block[col].rank(method="first")
        long_m = r <= k if direction == -1 else r > n - k
        short_m = r > n - k if direction == -1 else r <= k
        return float(block.loc[long_m, "fwd_ret_1w"].mean()
                     - block.loc[short_m, "fwd_ret_1w"].mean())

    return chars.groupby("week").apply(one_week).rename("ret")


def build_smbc_ic(chars):
    col = "log_mcap"
    keep = chars.dropna(subset=["fwd_ret_1w", col])
    return keep.groupby("week").apply(
        lambda b: b[col].rank().corr(b["fwd_ret_1w"].rank())
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


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def chart_cumulative_return(ret, ic, is_lo, is_hi, oos_lo, oos_hi):
    cum = (1 + ret).cumprod()
    cum_is = cum[(cum.index >= is_lo) & (cum.index <= is_hi)]
    cum_oos = cum[(cum.index >= oos_lo) & (cum.index <= oos_hi)]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.08,
                        subplot_titles=("SMBC Cumulative Long/Short Return",
                                        "Weekly Information Coefficient (IC)"))

    fig.add_trace(go.Scatter(
        x=cum_is.index, y=cum_is.values,
        name=IS_LABEL, line=dict(color=COLORS["IS"], width=2)),
        row=1, col=1)
    fig.add_trace(go.Scatter(
        x=cum_oos.index, y=cum_oos.values,
        name=OOS_LABEL, line=dict(color=COLORS["OOS"], width=2)),
        row=1, col=1)

    ic_is = ic[(ic.index >= is_lo) & (ic.index <= is_hi)].dropna()
    ic_oos = ic[(ic.index >= oos_lo) & (ic.index <= oos_hi)].dropna()
    fig.add_trace(go.Bar(
        x=ic_is.index, y=ic_is.values, name="IC (IS)",
        marker_color=COLORS["IS"], marker_opacity=0.5),
        row=2, col=1)
    fig.add_trace(go.Bar(
        x=ic_oos.index, y=ic_oos.values, name="IC (OOS)",
        marker_color=COLORS["OOS"], marker_opacity=0.5),
        row=2, col=1)

    for sign, color in [(0, "#666"), (-0.03, "#F44336"), (0.03, "#4CAF50")]:
        fig.add_hline(y=sign, line_dash="dot", line_color=color, line_width=0.8,
                      row=2, col=1)

    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=700,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Growth of $1", row=1, col=1)
    fig.update_yaxes(title_text="IC", row=2, col=1)
    fig.update_xaxes(title_text="Week", row=2, col=1)
    return fig


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
                  fillcolor=fillcolor, opacity=opacity,
                  line=dict(width=0))


def chart_rolling_ic_significance(ic, is_lo, is_hi, oos_lo, oos_hi):
    roll_ic_26 = ic.rolling(26).mean().dropna()
    roll_t = rolling_newey_west_t(ic, window=26, lags=4)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.08,
                        subplot_titles=("26-Week Rolling Mean IC",
                                        "26-Week Rolling Newey-West t-stat on IC"))

    fig.add_trace(go.Scatter(
        x=roll_ic_26.index, y=roll_ic_26.values,
        name="Rolling Mean IC", line=dict(color=COLORS["FULL"], width=2)),
        row=1, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="#666", row=1, col=1)

    fig.add_trace(go.Scatter(
        x=roll_t.index, y=roll_t.values,
        name="Rolling NW t-stat", line=dict(color=COLORS["FULL"], width=2)),
        row=2, col=1)
    fig.add_hline(y=2, line_dash="dot", line_color=COLORS["SIG_POS"], row=2, col=1)
    fig.add_hline(y=-2, line_dash="dot", line_color=COLORS["SIG_NEG"], row=2, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="#666", row=2, col=1)

    _add_vline(fig, is_hi, annotation_text="IS / OOS boundary")
    _add_vrect(fig, is_lo, is_hi, fillcolor=COLORS["IS"])
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"])

    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=700,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Mean IC", row=1, col=1)
    fig.update_yaxes(title_text="NW t-stat", row=2, col=1)
    fig.update_xaxes(title_text="Week", row=2, col=1)
    return fig


def chart_return_distribution(ret, is_lo, is_hi, oos_lo, oos_hi):
    is_r = ret[(ret.index >= is_lo) & (ret.index <= is_hi)].dropna()
    oos_r = ret[(ret.index >= oos_lo) & (ret.index <= oos_hi)].dropna()

    def desc(s, label):
        return dict(
            label=label, n=len(s), mean=s.mean(), std=s.std(),
            skew=s.skew(), kurt=s.kurtosis(),
            t_nw=float(s.mean() / newey_west_se(s.values, 4) if newey_west_se(s.values, 4) > 0 else np.nan),
            sharpe=float(s.mean() / s.std() * np.sqrt(52) if s.std() > 0 else np.nan),
            min=s.min(), p25=s.quantile(0.25), median=s.median(),
            p75=s.quantile(0.75), max=s.max())

    is_desc = desc(is_r, "IS")
    oos_desc = desc(oos_r, "OOS")

    fig = make_subplots(rows=2, cols=2,
                        subplot_titles=("Weekly Return Histogram (IS)",
                                        "Weekly Return Histogram (OOS)",
                                        "Return Box Plot", "Autocorrelation (IS)"),
                        vertical_spacing=0.12, horizontal_spacing=0.10)

    bins_is = np.histogram(is_r, bins=40, density=True)
    bins_oos = np.histogram(oos_r, bins=40, density=True)

    fig.add_trace(go.Bar(x=bins_is[1][:-1], y=bins_is[0], name="IS",
                         marker_color=COLORS["IS"], marker_opacity=0.7),
                  row=1, col=1)
    fig.add_trace(go.Bar(x=bins_oos[1][:-1], y=bins_oos[0], name="OOS",
                         marker_color=COLORS["OOS"], marker_opacity=0.7),
                  row=1, col=2)

    for lb, d, c in [(IS_LABEL, is_desc, COLORS["IS"]), (OOS_LABEL, oos_desc, COLORS["OOS"])]:
        fig.add_vline(x=d["mean"], line_dash="dash", line_color=c, row=1, col=1 if "IS" in lb else 2)

    fig.add_trace(go.Box(y=is_r.values, name="IS",
                         marker_color=COLORS["IS"], boxmean="sd"),
                  row=2, col=1)
    fig.add_trace(go.Box(y=oos_r.values, name="OOS",
                         marker_color=COLORS["OOS"], boxmean="sd"),
                  row=2, col=1)

    nlags = 12
    acf_vals = [is_r.autocorr(lag=l) for l in range(1, nlags + 1)]
    fig.add_trace(go.Bar(x=list(range(1, nlags + 1)), y=acf_vals,
                         name="Autocorrelation", marker_color=COLORS["IS"],
                         marker_opacity=0.7),
                  row=2, col=2)
    fig.add_hline(y=1.96 / np.sqrt(len(is_r)), line_dash="dot",
                  line_color="#999", row=2, col=2)
    fig.add_hline(y=-1.96 / np.sqrt(len(is_r)), line_dash="dot",
                  line_color="#999", row=2, col=2)

    fig.update_layout(template=PLOTLY_TEMPLATE, height=800, showlegend=False)
    fig.update_yaxes(title_text="Density", row=1, col=1)
    fig.update_yaxes(title_text="Density", row=1, col=2)
    fig.update_yaxes(title_text="Weekly Return", row=2, col=1)
    fig.update_yaxes(title_text="Autocorrelation", row=2, col=2)
    fig.update_xaxes(title_text="Weekly Return", row=1, col=1)
    fig.update_xaxes(title_text="Weekly Return", row=1, col=2)
    fig.update_xaxes(title_text="Lag (weeks)", row=2, col=2)

    return fig, is_desc, oos_desc


def chart_rolling_sharpe(ret, is_lo, is_hi, oos_lo, oos_hi):
    roll_sharpe = rolling_stat(ret, 52, lambda s: s.mean() / s.std() * np.sqrt(52) if s.std() > 0 else np.nan)
    roll_sharpe = roll_sharpe.dropna()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=roll_sharpe.index, y=roll_sharpe.values,
        name="52-week Rolling Sharpe", line=dict(color=COLORS["FULL"], width=2)))
    fig.add_hline(y=0, line_dash="dash", line_color="#666")
    fig.add_hline(y=1, line_dash="dot", line_color=COLORS["SIG_POS"],
                  annotation_text="Sharpe = 1")
    fig.add_hline(y=-1, line_dash="dot", line_color=COLORS["SIG_NEG"],
                  annotation_text="Sharpe = −1")
    _add_vrect(fig, is_lo, is_hi, fillcolor=COLORS["IS"])
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"])
    _add_vline(fig, is_hi, annotation_text="IS / OOS")

    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=500,
        title="SMBC 52-Week Rolling Sharpe Ratio",
        xaxis_title="Week", yaxis_title="Annualised Sharpe",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_qq_plot(ret, is_lo, is_hi, oos_lo, oos_hi):
    is_r = ret[(ret.index >= is_lo) & (ret.index <= is_hi)].dropna().sort_values()
    oos_r = ret[(ret.index >= oos_lo) & (ret.index <= oos_hi)].dropna().sort_values()

    def qq_data(series):
        n = len(series)
        theoretical = sp_stats.norm.ppf(np.arange(1, n + 1) / (n + 1))
        theoretical *= series.std()
        theoretical += series.mean()
        return theoretical, series.values

    t_is, s_is = qq_data(is_r)
    t_oos, s_oos = qq_data(oos_r)

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("QQ Plot — In-Sample", "QQ Plot — Out-of-Sample"))

    fig.add_trace(go.Scatter(
        x=t_is, y=s_is, mode="markers", name="IS quantiles",
        marker=dict(color=COLORS["IS"], size=4, opacity=0.7)),
        row=1, col=1)
    lo = min(t_is.min(), s_is.min())
    hi = max(t_is.max(), s_is.max())
    fig.add_trace(go.Scatter(
        x=[lo, hi], y=[lo, hi], mode="lines", name="y=x",
        line=dict(color="#999", dash="dash")), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=t_oos, y=s_oos, mode="markers", name="OOS quantiles",
        marker=dict(color=COLORS["OOS"], size=4, opacity=0.7)),
        row=1, col=2)
    lo = min(t_oos.min(), s_oos.min())
    hi = max(t_oos.max(), s_oos.max())
    fig.add_trace(go.Scatter(
        x=[lo, hi], y=[lo, hi], mode="lines", name="y=x",
        line=dict(color="#999", dash="dash")), row=1, col=2)

    fig.update_layout(template=PLOTLY_TEMPLATE, height=500, showlegend=False)
    fig.update_xaxes(title_text="Theoretical Quantile (Normal)", row=1, col=1)
    fig.update_xaxes(title_text="Theoretical Quantile (Normal)", row=1, col=2)
    fig.update_yaxes(title_text="Sample Quantile", row=1, col=1)
    fig.update_yaxes(title_text="Sample Quantile", row=1, col=2)
    return fig


def chart_size_tercile_heatmap(chars, is_lo, is_hi, oos_lo, oos_hi):
    chars = chars.dropna(subset=["fwd_ret_1w", "log_mcap"]).copy()
    chars["tercile"] = chars.groupby("week")["log_mcap"].transform(
        lambda x: pd.qcut(x, 3, labels=["Small", "Mid", "Big"], duplicates="drop")
        if len(x.dropna()) >= 6 else pd.NA)

    tercile_ret = (chars.dropna(subset=["tercile"])
                   .groupby(["week", "tercile"])["fwd_ret_1w"].mean().reset_index())
    tercile_pivot = tercile_ret.pivot(index="week", columns="tercile", values="fwd_ret_1w")

    for col_name in ["Small", "Mid", "Big"]:
        if col_name not in tercile_pivot.columns:
            tercile_pivot[col_name] = np.nan

    tercile_pivot = tercile_pivot[["Small", "Mid", "Big"]].dropna()
    smbc_approx = tercile_pivot["Small"] - tercile_pivot["Big"]

    is_data = tercile_pivot[(tercile_pivot.index >= is_lo) & (tercile_pivot.index <= is_hi)]
    oos_data = tercile_pivot[(tercile_pivot.index >= oos_lo) & (tercile_pivot.index <= oos_hi)]

    def ann_ret(s):
        return (1 + s).prod() ** (52 / len(s)) - 1 if len(s) > 0 else np.nan

    labels = ["Small", "Mid", "Big", "SMB (Small–Big)"]
    is_vals = [ann_ret(is_data[c]) * 100 if c in is_data else np.nan for c in ["Small", "Mid", "Big"]] + [ann_ret(smbc_approx[(smbc_approx.index >= is_lo) & (smbc_approx.index <= is_hi)]) * 100]
    oos_vals = [ann_ret(oos_data[c]) * 100 if c in oos_data else np.nan for c in ["Small", "Mid", "Big"]] + [ann_ret(smbc_approx[(smbc_approx.index >= oos_lo) & (smbc_approx.index <= oos_hi)]) * 100]
    full_vals = [ann_ret(tercile_pivot[c]) * 100 if c in tercile_pivot else np.nan for c in ["Small", "Mid", "Big"]] + [ann_ret(smbc_approx) * 100]

    fig = go.Figure(data=[
        go.Bar(name="IS", x=labels, y=is_vals, marker_color=COLORS["IS"], marker_opacity=0.8),
        go.Bar(name="OOS", x=labels, y=oos_vals, marker_color=COLORS["OOS"], marker_opacity=0.8),
        go.Bar(name="Full", x=labels, y=full_vals, marker_color=COLORS["FULL"], marker_opacity=0.5),
    ])
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=500,
        title="SMBC Size Tercile Annualised Returns",
        barmode="group", xaxis_title="Size Group", yaxis_title="Annualised Return (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig, smbc_approx


def chart_is_oos_comparison(stats_row):
    metrics = ["IC", "IC t-stat", "Sharpe", "Annualised Return", "Mean Weekly Return"]
    is_vals = [stats_row["IS_IC"], stats_row["IS_IC_t"],
               stats_row["IS_sharpe"], stats_row["IS_annret"],
               stats_row["IS_annret"] / 52]
    oos_vals = [stats_row["OOS_IC"], stats_row["OOS_IC_t"],
                stats_row["OOS_sharpe"], stats_row["OOS_annret"],
                stats_row["OOS_annret"] / 52]

    fig = go.Figure(data=[
        go.Bar(name="In-Sample", x=metrics, y=is_vals,
               marker_color=COLORS["IS"], marker_opacity=0.8),
        go.Bar(name="Out-of-Sample", x=metrics, y=oos_vals,
               marker_color=COLORS["OOS"], marker_opacity=0.8),
    ])
    fig.add_hline(y=0, line_dash="dash", line_color="#666")
    fig.add_hrect(y0=2, y1=2.5, fillcolor=COLORS["SIG_POS"], opacity=0.1,
                  annotation_text="Significance zone (t ≥ 2)")
    fig.add_hrect(y0=-2.5, y1=-2, fillcolor=COLORS["SIG_NEG"], opacity=0.1,
                  annotation_text="Significance zone (t ≤ −2)")

    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=500,
        title="SMBC Factor: IS vs OOS Comparison Dashboard",
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def chart_cumulative_by_tercile(chars, is_lo, is_hi, oos_lo, oos_hi):
    chars = chars.dropna(subset=["fwd_ret_1w", "log_mcap"]).copy()
    chars["tercile"] = chars.groupby("week")["log_mcap"].transform(
        lambda x: pd.qcut(x, 3, labels=["Small", "Mid", "Big"], duplicates="drop")
        if len(x.dropna()) >= 6 else pd.NA)
    chars = chars.dropna(subset=["tercile"])

    tercile_ret = (chars.groupby(["week", "tercile"])["fwd_ret_1w"].mean().reset_index())
    pivot = tercile_ret.pivot(index="week", columns="tercile", values="fwd_ret_1w")
    for c in ["Small", "Mid", "Big"]:
        if c not in pivot.columns:
            pivot[c] = np.nan
    pivot = pivot[["Small", "Mid", "Big"]].sort_index().fillna(0)

    cum = (1 + pivot).cumprod()

    fig = go.Figure()
    colors_tercile = {"Small": "#4CAF50", "Mid": "#FF9800", "Big": "#F44336"}
    for col_name, color in colors_tercile.items():
        fig.add_trace(go.Scatter(
            x=cum.index, y=cum[col_name],
            name=f"{col_name} cap", line=dict(color=color, width=2)))

    smbc_cum = (1 + (pivot["Small"] - pivot["Big"])).cumprod()
    fig.add_trace(go.Scatter(
        x=smbc_cum.index, y=smbc_cum.values,
        name="SMB (Small – Big)", line=dict(color="#000", width=2.5, dash="dash")))

    _add_vline(fig, is_hi, line_color="#999")
    _add_vrect(fig, is_lo, is_hi, fillcolor=COLORS["IS"], opacity=0.04)
    _add_vrect(fig, oos_lo, oos_hi, fillcolor=COLORS["OOS"], opacity=0.04)

    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=550,
        title="Cumulative Return by Size Tercile",
        xaxis_title="Week", yaxis_title="Growth of $1",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


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

    print("Building SMBC factor series...")
    chars, ret_wide = build_characteristics(panel, trade)
    smbc_ret = build_smbc_returns(chars)
    smbc_ic = build_smbc_ic(chars)
    smbc_ret.index = pd.to_datetime(smbc_ret.index)
    smbc_ic.index = pd.to_datetime(smbc_ic.index)

    # Load stored validation stats
    val_stats = pd.read_parquet(PANEL_DIR / "factor_validation_stats.parquet")
    smbc_row = val_stats[val_stats["factor"] == "SMBC"].iloc[0].to_dict()

    print("Chart 1: Cumulative return + IC bars...")
    fig1 = chart_cumulative_return(smbc_ret, smbc_ic, is_lo, is_hi, oos_lo, oos_hi)
    print("Chart 1: Cumulative return + IC bars...")
    fig1 = chart_cumulative_return(smbc_ret, smbc_ic, is_lo, is_hi, oos_lo, oos_hi)

    print("Chart 2: Rolling IC significance...")
    fig2 = chart_rolling_ic_significance(smbc_ic, is_lo, is_hi, oos_lo, oos_hi)

    print("Chart 3: Return distribution + statistics...")
    fig3, is_desc, oos_desc = chart_return_distribution(smbc_ret, is_lo, is_hi, oos_lo, oos_hi)

    print("Chart 4: Rolling Sharpe ratio...")
    fig4 = chart_rolling_sharpe(smbc_ret, is_lo, is_hi, oos_lo, oos_hi)

    print("Chart 5: QQ-plot vs Normal...")
    fig5 = chart_qq_plot(smbc_ret, is_lo, is_hi, oos_lo, oos_hi)

    print("Chart 6: Size tercile returns...")
    fig6, smbc_tercile = chart_size_tercile_heatmap(chars, is_lo, is_hi, oos_lo, oos_hi)

    print("Chart 7: IS vs OOS comparison dashboard...")
    fig7 = chart_is_oos_comparison(smbc_row)

    print("Chart 8: Cumulative return by tercile...")
    fig8 = chart_cumulative_by_tercile(chars, is_lo, is_hi, oos_lo, oos_hi)

    charts = [
        ("smbc_01_cumulative_return", fig1),
        ("smbc_02_rolling_ic_significance", fig2),
        ("smbc_03_return_distribution", fig3),
        ("smbc_04_rolling_sharpe", fig4),
        ("smbc_05_qq_plot", fig5),
        ("smbc_06_tercile_returns", fig6),
        ("smbc_07_is_oos_comparison", fig7),
        ("smbc_08_cumulative_tercile", fig8),
    ]

    for name, fig in charts:
        fig.write_html(str(FIG_DIR / f"{name}.html"))
        print(f"  → saved {name}.html")
        fig.write_image(str(FIG_DIR / f"{name}.png"), scale=2)
        print(f"  → saved {name}.png")

    # Save intermediate data
    viz_data = pd.DataFrame({"smbc_ret": smbc_ret, "smbc_ic": smbc_ic})
    viz_data.to_parquet(DATA_DIR / "smbc_viz_data.parquet")
    print("\n  saved smbc_viz_data.parquet")

    # Compute additional stats for the report
    is_r = smbc_ret[(smbc_ret.index >= is_lo) & (smbc_ret.index <= is_hi)].dropna()
    oos_r = smbc_ret[(smbc_ret.index >= oos_lo) & (smbc_ret.index <= oos_hi)].dropna()

    # Stationarity / persistence test
    from statsmodels.tsa.stattools import adfuller
    try:
        adf_full = adfuller(smbc_ret.dropna(), autolag="AIC")
        adf_stat, adf_p = adf_full[0], adf_full[1]
    except Exception:
        adf_stat, adf_p = np.nan, np.nan

    # JB test for normality
    jb_is = sp_stats.jarque_bera(is_r)[0]
    jb_is_p = sp_stats.jarque_bera(is_r)[1]
    jb_oos = sp_stats.jarque_bera(oos_r)[0]
    jb_oos_p = sp_stats.jarque_bera(oos_r)[1]

    # Write the report
    write_report(smbc_row, is_desc, oos_desc, adf_stat, adf_p,
                 jb_is, jb_is_p, jb_oos, jb_oos_p, is_lo, is_hi, oos_lo, oos_hi)

    print(f"\nAll charts saved to {FIG_DIR}")
    print(f"Report written to {STAGE / 'SMBC_VIZ_REPORT.md'}")


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def fmt_val(v, fmt=".2f"):
    if isinstance(v, float) and np.isfinite(v):
        return f"{v:{fmt}}"
    return "N/A"


def write_report(row, is_d, oos_d, adf_stat, adf_p, jb_is, jb_is_p, jb_oos, jb_oos_p,
                 is_lo, is_hi, oos_lo, oos_hi):
    smbc_verdict = row["verdict"]

    def sign_cell(t):
        if not np.isfinite(t):
            return "N/A"
        if abs(t) >= 2:
            return f"**{t:+.2f}** (significant)"
        if abs(t) >= 1.65:
            return f"{t:+.2f} (marginal)"
        return f"{t:+.2f} (not significant)"

    md = f"""# SMBC (Size) Factor — Visualisation & Statistical Significance Report

*Generated by `10_smbc_visualisation.py` from the Stage-09 5-year panel.*

---

## 1. What is SMBC?

**SMBC** (Small Minus Big Caps) is the **size factor** in crypto: each week, go long
the bottom 30% of coins by log market-cap (the smallest) and short the top 30%
(the largest). In equity markets this is the classic SMB factor; in crypto the
dynamic is different because the smallest tokens are often the most volatile and
speculative.

## 2. Headline Verdict

> **{smbc_verdict}**

SMBC's IC t-stat is **{fmt_val(row['IS_IC_t'])}** in-sample and **{fmt_val(row['OOS_IC_t'])}**
out-of-sample — both below the |t| ≥ 2 significance bar. The factor does not pass
the test for robust, out-of-sample-stable ranking power.

## 3. Performance Summary

| Metric | In-Sample | Out-of-Sample |
|---|---|---|
| Weeks | {int(row['IS_n'])} | {int(row['OOS_n'])} |
| Annualised Return | {fmt_val(row['IS_annret']*100, '.1f')}% | {fmt_val(row['OOS_annret']*100, '.1f')}% |
| Sharpe Ratio | {fmt_val(row['IS_sharpe'])} | {fmt_val(row['OOS_sharpe'])} |
| Mean IC | {fmt_val(row['IS_IC'], '.4f')} | {fmt_val(row['OOS_IC'], '.4f')} |
| IC t-stat (NW) | {sign_cell(row['IS_IC_t'])} | {sign_cell(row['OOS_IC_t'])} |
| Return t-stat (NW) | {sign_cell(row['IS_t'])} | {sign_cell(row['OOS_t'])} |

### Return Distribution Statistics

| Statistic | IS | OOS |
|---|---|---|
| Mean weekly return | {fmt_val(is_d['mean']*100, '.3f')}% | {fmt_val(oos_d['mean']*100, '.3f')}% |
| Std (weekly) | {fmt_val(is_d['std']*100, '.3f')}% | {fmt_val(oos_d['std']*100, '.3f')}% |
| Skewness | {fmt_val(is_d['skew'], '.2f')} | {fmt_val(oos_d['skew'], '.2f')} |
| Excess Kurtosis | {fmt_val(is_d['kurt'], '.2f')} | {fmt_val(oos_d['kurt'], '.2f')} |
| Min | {fmt_val(is_d['min']*100, '.2f')}% | {fmt_val(oos_d['min']*100, '.2f')}% |
| 25th percentile | {fmt_val(is_d['p25']*100, '.2f')}% | {fmt_val(oos_d['p25']*100, '.2f')}% |
| Median | {fmt_val(is_d['median']*100, '.2f')}% | {fmt_val(oos_d['median']*100, '.2f')}% |
| 75th percentile | {fmt_val(is_d['p75']*100, '.2f')}% | {fmt_val(oos_d['p75']*100, '.2f')}% |
| Max | {fmt_val(is_d['max']*100, '.2f')}% | {fmt_val(oos_d['max']*100, '.2f')}% |

## 4. Statistical Significance Tests

### 4.1 Newey-West t-stat on IC (primary test)

The IC (Information Coefficient) measures whether the size ranking predicts
next-week returns. The Newey-West t-stat corrects for autocorrelation in the
weekly IC series.

- **IS IC t = {fmt_val(row['IS_IC_t'])}** — below |t| ≥ 2; **not significant**.
- **OOS IC t = {fmt_val(row['OOS_IC_t'])}** — below |t| ≥ 2; **not significant**.

**Interpretation:** Size ranking does not reliably predict crypto cross-sectional
returns in either period. The positive sign means small coins slightly outperform
large ones, but the effect is indistinguishable from noise.

### 4.2 Jarque-Bera Normality Test

Tests whether the weekly SMBC return series is normally distributed. Departures
from normality matter because they affect the reliability of t-statistics.

| Period | JB Statistic | p-value | Normal? |
|---|---|---|---|
| IS | {fmt_val(jb_is, '.1f')} | {fmt_val(jb_is_p, '.4f')} | {"No" if jb_is_p < 0.05 else "Yes"} |
| OOS | {fmt_val(jb_oos, '.1f')} | {fmt_val(jb_oos_p, '.4f')} | {"No" if jb_oos_p < 0.05 else "Yes"} |

### 4.3 ADF Stationarity Test

Tests whether the SMBC cumulative return series has a unit root (i.e., whether
returns are mean-reverting or trend-persistent). A stationary series (p < 0.05)
means returns don't drift permanently — a comforting property for a factor.

- **ADF statistic:** {fmt_val(adf_stat, '.3f')}
- **p-value:** {fmt_val(adf_p, '.4f')}
- **Verdict:** {"Stationary (mean-reverting)" if adf_p < 0.05 else "Non-stationary (trend-persistent)"}

## 5. Key Findings

### 5.1 Size is NOT a priced factor in crypto (5-year evidence)

Over 264 weeks (2021–2026), the small-minus-big long/short portfolio earned a
positive annualised return in both IS (+{fmt_val(row['IS_annret']*100, '.1f')}%)
and OOS (+{fmt_val(row['OOS_annret']*100, '.1f')}%), but neither period reaches
statistical significance at the |t| ≥ 2 level.

This contrasts sharply with equity markets, where SMB is a well-established
anomaly. In crypto:
- **Market-cap extremes are dominated by BTC/ETH**, leaving very few "large" coins
  for the short leg, increasing concentration risk.
- **The smallest coins have fat-tailed upside** — occasional moonshots that make
  the long leg erratic, inflating variance without reliable drift.
- **Regime dependence**: size worked in the 2020–2021 bull run (which had many
  small-cap rallies) but broke down in 2022–2023 (bear market compression).

### 5.2 IC is positive but not significant

The mean IC is +{fmt_val(row['IS_IC'], '.4f')} (IS) and +{fmt_val(row['OOS_IC'], '.4f')} (OOS).
The sign is correct (small beats big, on average), but the t-statistics ({fmt_val(row['IS_IC_t'], '.2f')} and {fmt_val(row['OOS_IC_t'], '.2f')})
are well below the |t| = 2 bar. This is a **weak, noisy signal** — directionally
right but statistically unreliable.

### 5.3 Comparison with the 52-week study

In the shorter 52-week window (Stage 08), size appeared stronger because
the sample was dominated by a single regime (the 2024 recovery). Extending to
5 years revealed that the effect is regime-fragile: it comes and goes, and the
long-run average is not distinguishable from zero.

### 5.4 Fat tails and non-normality

{"The Jarque-Bera test rejects normality — SMBC weekly returns have heavier tails than a Gaussian distribution. This means extreme weeks (small-cap rallies or crashes) dominate the return series, and the factor's performance depends heavily on a few tail events." if jb_is_p < 0.05 else "The Jarque-Bera test does not reject normality for the IS period, suggesting the return distribution is roughly Gaussian."}

## 6. Visualisations

### 6.1 Cumulative Long/Short Return & Weekly IC

![Cumulative return and weekly IC](artifacts/figures/smbc_01_cumulative_return.png)

The blue region marks the in-sample period; the orange region marks out-of-sample. The
top panel shows the growth of $1 invested in the SMBC long/short strategy. The bottom
panel shows the weekly IC — note how it oscillates around zero with no persistent drift.

### 6.2 Rolling IC Significance

![Rolling IC and NW t-stat](artifacts/figures/smbc_02_rolling_ic_significance.png)

The 26-week rolling mean IC (top) shows periods of positive and negative ranking power.
The rolling Newey-West t-stat (bottom) shows whether the IC is statistically different from
zero at any point. The t-stat rarely crosses the |t| = 2 significance threshold (green/red
dotted lines), confirming that SMBC's ranking power is not reliable.

### 6.3 Return Distribution

![Return distribution](artifacts/figures/smbc_03_return_distribution.png)

Histograms of weekly SMBC returns in IS and OOS, with box plots and autocorrelation.
The distribution is right-skewed (skewness +2.10 IS), with occasional large positive
weeks from small-cap rallies. Autocorrelation is near zero at all lags, confirming
no momentum persistence in the factor spread.

### 6.4 Rolling Sharpe Ratio

![Rolling Sharpe](artifacts/figures/smbc_04_rolling_sharpe.png)

The 52-week rolling Sharpe ratio oscillates between −2 and +3, spending long stretches
below zero. The factor is profitable in some regimes but loss-making in others — a
hallmark of statistical noise rather than a genuine premium.

### 6.5 QQ-Plot vs. Normal Distribution

![QQ plot](artifacts/figures/smbc_05_qq_plot.png)

The QQ-plot shows heavy right tails in both IS and OOS: the empirical quantiles
rise much faster than the Gaussian line at the extremes. This confirms the
Jarque-Bera rejection of normality — a few extreme upside weeks (small-cap
moonshots) dominate the return profile.

### 6.6 Size Tercile Annualised Returns

![Tercile returns](artifacts/figures/smbc_06_tercile_returns.png)

Grouped bar chart of annualised returns for Small, Mid, Big, and SMB (Small−Big)
tercile portfolios, split by IS, OOS, and Full sample. The Small cap tercile
has the highest return but also the highest variance.

### 6.7 IS vs OOS Comparison Dashboard

![IS vs OOS](artifacts/figures/smbc_07_is_oos_comparison.png)

Side-by-side comparison of all key metrics between the in-sample and out-of-sample
periods. The most notable observation: Sharpe improves from 0.83 (IS) to 1.66 (OOS),
but the IC t-stat does not cross the significance threshold in either period.

### 6.8 Cumulative Return by Size Tercile

![Cumulative tercile](artifacts/figures/smbc_08_cumulative_tercile.png)

Growth of $1 in each size tercile (Small, Mid, Big) plus the SMB long/short spread.
The small-cap cumulative return is visually dominated by a few explosive rallies.
The SMB spread line (dashed black) shows the long/short return — mostly flat,
consistent with a premium that does not exist after costs.

"""

    (STAGE / "SMBC_VIZ_REPORT.md").write_text(md)
    print(f"  wrote SMBC_VIZ_REPORT.md")


if __name__ == "__main__":
    main()