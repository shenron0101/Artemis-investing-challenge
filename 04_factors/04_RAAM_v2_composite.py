"""04 — RAAM v2 composite (M / V / C / T  +  F / S / G).

Recompute the four RAAM v1 factors from rank.md and blend in the three new
fundamental factors (F = fundamental yield, S = supply absorption, G =
activity-validated growth) into a single composite. Side-by-side bar of v1
vs v2 makes the re-rating visible. Cumulative-IC line answers the only
question that matters: does adding F/S/G improve the breadth of useful signal?

NaN handling: if a symbol is missing one of F/S/G it gets a neutral z=0 for
that factor only. M/V/C/T are required; if missing the symbol is dropped.

Outputs:
    01_factor_correlation.png         — Spearman ρ matrix between latest M/V/C/T/F/S/G ranks
    02_v1_vs_v2_top25.png             — horizontal bar comparing v1 vs v2 top-25
    03_per_factor_cumulative_ic.png   — cumulative IC per factor vs fwd 30d returns
    04_composite_v1_vs_v2_ic.png      — v1 composite IC vs v2 composite IC over time
"""
# %% Imports
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    DIVERGE,
    cross_sectional_rank,
    exclude_symbols,
    forward_returns,
    ic_summary,
    load,
    market_caps_wide,
    prices_wide,
    save,
    spearman_ic,
    universe_with_mcap,
)

STEM = Path(__file__).stem

# %% Load
excl = exclude_symbols()
master = universe_with_mcap()
sym_to_cohort = master.set_index("symbol")["cohort"].to_dict()
sym_to_mcap = master.set_index("symbol")["market_cap"].to_dict()
sym_to_fdv = master.set_index("symbol")["fdv"].to_dict()

prices = prices_wide()
log_prices = np.log(prices)
log_ret = log_prices.diff()
mcaps = market_caps_wide()

ohlcv = load("binance_ohlcv_daily.parquet").copy()
ohlcv["date"] = pd.to_datetime(ohlcv["open_time"]).dt.tz_localize(None).dt.normalize()

act = load("artemis_activity_long.parquet").copy()
act["date"] = pd.to_datetime(act["date"], errors="coerce")
act = act.dropna(subset=["date"])
act["value"] = pd.to_numeric(act["value"], errors="coerce")
act = act.dropna(subset=["value"])

# Drop excluded
def drop_excl(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[c for c in df.columns if c in excl], errors="ignore")


prices = drop_excl(prices)
log_ret = drop_excl(log_ret)
mcaps = drop_excl(mcaps)

# %% v1 factor panels (M / V / C / T)
# (M) 4-month price ROC
M = (prices / prices.shift(84)) - 1.0

# (V) 90-day annualised stdev (negative — lower vol = better)
V = log_ret.rolling(90).std() * np.sqrt(365)

# (C) 90-day rolling avg pairwise correlation per asset (lower = better)
def rolling_avg_corr(ret_df: pd.DataFrame, window: int = 90) -> pd.DataFrame:
    cols = ret_df.columns
    out = pd.DataFrame(index=ret_df.index, columns=cols, dtype=float)
    for end_idx in range(window, len(ret_df) + 1):
        sl = ret_df.iloc[end_idx - window : end_idx]
        c = sl.corr()
        np.fill_diagonal(c.values, np.nan)
        out.iloc[end_idx - 1] = c.mean(axis=1)
    return out


C_panel = rolling_avg_corr(log_ret.dropna(axis=1, thresh=200), window=90)

# (T) ATR breakout state (long = +1, short = -1, neutral = 0)
def atr_state(df: pd.DataFrame, period: int = 42) -> pd.Series:
    d = df.sort_values("date").copy()
    prev_close = d["close"].shift(1)
    tr = pd.concat([
        (d["high"] - d["low"]).abs(),
        (d["high"] - prev_close).abs(),
        (d["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    d["atr"] = tr.rolling(period).mean()
    d["upper"] = d["high"].rolling(period).max() + d["atr"]
    d["lower"] = d["low"].rolling(period).min() - d["atr"]
    state = pd.Series(np.nan, index=d.index)
    state[d["high"] > d["upper"].shift(1)] = 1.0
    state[d["low"] < d["lower"].shift(1)] = -1.0
    return pd.Series(state.ffill().fillna(0.0).values, index=d["date"].values)


T_per_sym = {}
ohlcv_clean = ohlcv.dropna(subset=["symbol", "high", "low", "close"])
ohlcv_clean = ohlcv_clean[~ohlcv_clean["symbol"].isin(excl)]
for sym, df_ in ohlcv_clean.groupby("symbol"):
    T_per_sym[sym] = atr_state(df_)

T_panel = pd.DataFrame(T_per_sym).reindex(prices.index).ffill()

# Cross-sectional ranks (1 = best)
M_rank = cross_sectional_rank(M, ascending=False)            # high momentum = best
V_rank = cross_sectional_rank(V, ascending=True)             # low vol = best
C_rank = cross_sectional_rank(C_panel, ascending=True)       # low avg corr = best
T_rank = cross_sectional_rank(T_panel, ascending=False)      # +1 long = best

# %% v2 factor panels (F / S / G) — recomputed inline so this file is self-contained
def daily_panel(metric: str) -> pd.DataFrame:
    sub = act[act["metric"].eq(metric)]
    return (
        sub.pivot_table(index="date", columns="symbol", values="value", aggfunc="last")
        .reindex(prices.index)
    )


# F — fundamental yield
fees_d = daily_panel("fees")
rev_d = daily_panel("revenue")
fees_30 = fees_d.rolling(30, min_periods=10).mean()
rev_30 = rev_d.rolling(30, min_periods=10).mean()
fund_cashflow = fees_30 * 365 + 0.5 * rev_30 * 365
common_F = fund_cashflow.columns.intersection(mcaps.columns)
F_panel = (fund_cashflow[common_F] / mcaps[common_F]).replace([np.inf, -np.inf], np.nan)
F_panel = drop_excl(F_panel)
F_rank = cross_sectional_rank(F_panel, ascending=False)

# S — supply absorption
implied = (mcaps / prices).replace([np.inf, -np.inf], np.nan)
emission_90_panel = (implied / implied.shift(90)) - 1.0
emission_z = emission_90_panel.sub(emission_90_panel.mean(axis=1), axis=0).div(
    emission_90_panel.std(axis=1), axis=0
)
S_score = -emission_z
S_rank = cross_sectional_rank(S_score, ascending=False)

# G — activity-validated growth
metrics_g = ["dau", "fees", "revenue"]
g_panels = {}
for m in metrics_g:
    p = daily_panel(m)
    short_mean = p.rolling(30, min_periods=10).mean()
    long_mean = p.rolling(120, min_periods=40).mean()
    g = (short_mean / long_mean) - 1.0
    g = drop_excl(g.replace([np.inf, -np.inf], np.nan))
    g_panels[m] = g


def cross_z(panel: pd.DataFrame) -> pd.DataFrame:
    return panel.sub(panel.mean(axis=1), axis=0).div(panel.std(axis=1), axis=0)


z_panels = {m: cross_z(g) for m, g in g_panels.items()}
all_g_syms = sorted(set().union(*[set(z.columns) for z in z_panels.values()]))
growth_score = pd.DataFrame(
    np.nanmean(
        np.dstack([z.reindex(columns=all_g_syms).values for z in z_panels.values()]),
        axis=2,
    ),
    index=z_panels["dau"].index,
    columns=all_g_syms,
)
price_score = cross_z(log_prices.sub(log_prices.shift(90)))
common_G = growth_score.columns.intersection(price_score.columns)
G_score = growth_score[common_G] - 0.5 * price_score[common_G]
G_rank = cross_sectional_rank(G_score, ascending=False)

# %% Panel 1 — factor correlation matrix at the latest date
ranks_latest = pd.DataFrame({
    "M": M_rank.iloc[-1],
    "V": V_rank.iloc[-1],
    "C": C_rank.iloc[-1],
    "T": T_rank.iloc[-1],
    "F": F_rank.iloc[-1],
    "S": S_rank.iloc[-1],
    "G": G_rank.iloc[-1],
})
corr = ranks_latest.corr(method="spearman")

fig = go.Figure(data=go.Heatmap(
    z=corr.values,
    x=corr.columns,
    y=corr.index,
    colorscale=DIVERGE,
    zmin=-1, zmax=1, zmid=0,
    text=corr.round(2).values,
    texttemplate="%{text}",
    colorbar=dict(title="ρ"),
))
fig.update_layout(
    title="Factor rank correlation (Spearman, latest cross-section) — checks for redundancy",
    yaxis=dict(autorange="reversed"),
)
save(fig, "01_factor_correlation", STEM, width=900, height=820)

# %% Panel 2 — v1 vs v2 top-25 ranking bar
def composite(factors: list[str]) -> pd.Series:
    """Equal-weight average rank across factors. Lower = better. Skip-NaN per asset."""
    rows = pd.concat([ranks_latest[f] for f in factors], axis=1)
    rows = rows[(rows.notna().sum(axis=1) >= max(2, len(factors) - 2))]
    return rows.mean(axis=1)


comp_v1 = composite(["M", "V", "C", "T"])
comp_v2 = composite(["M", "V", "C", "T", "F", "S", "G"])

universe_v1v2 = comp_v1.index.intersection(comp_v2.index)
both = pd.DataFrame({"v1": comp_v1.loc[universe_v1v2], "v2": comp_v2.loc[universe_v1v2]})
both["delta"] = both["v2"] - both["v1"]   # negative delta = improved (lower rank in v2)
both["best_of_either"] = both.min(axis=1)
top25 = both.sort_values("best_of_either").head(25).copy()
top25 = top25.sort_values("v2", ascending=False)  # plotly horizontal bars: bottom = best

fig = go.Figure()
fig.add_trace(go.Bar(
    y=top25.index, x=top25["v1"], orientation="h", name="RAAM v1 (M/V/C/T)",
    marker_color="#9ecae1",
))
fig.add_trace(go.Bar(
    y=top25.index, x=top25["v2"], orientation="h", name="RAAM v2 (+F/S/G)",
    marker_color="#1f77b4",
))
fig.update_layout(
    title="RAAM v1 vs v2 composite rank (lower = better) — top 25 by best-of-either",
    barmode="group",
    xaxis_title="composite rank (mean of factor ranks)",
)
save(fig, "02_v1_vs_v2_top25", STEM, width=1200, height=900)

# %% Panel 3 — per-factor cumulative IC vs fwd 30d return
fwd = forward_returns(prices, horizons=(30,))
fwd30 = fwd[30]


def ic_series(panel: pd.DataFrame, name: str) -> pd.DataFrame:
    ic = spearman_ic(-panel, fwd30)
    s = ic_summary(ic)
    cum = ic.fillna(0).cumsum()
    return pd.DataFrame({
        "date": cum.index, "cum_ic": cum.values, "factor": name,
        "label": f"{name} (mean={s['mean_ic']:+.3f}, IR={s['ir']:+.2f})",
    })


lines = pd.concat([
    ic_series(M_rank, "M"),
    ic_series(V_rank, "V"),
    ic_series(C_rank, "C"),
    ic_series(T_rank, "T"),
    ic_series(F_rank, "F"),
    ic_series(S_rank, "S"),
    ic_series(G_rank, "G"),
], ignore_index=True)

fig = px.line(
    lines.dropna(),
    x="date",
    y="cum_ic",
    color="label",
    color_discrete_sequence=px.colors.qualitative.Dark24,
    title="Cumulative Spearman IC vs forward 30d return — per factor (positive slope = useful)",
)
fig.add_hline(y=0, line_dash="dot", line_color="grey")
fig.update_layout(yaxis_title="cumulative Spearman ρ (sum of daily IC)")
save(fig, "03_per_factor_cumulative_ic", STEM, width=1300, height=720)

# %% Panel 4 — v1 vs v2 composite IC over time
def composite_panel(rank_panels: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Daily composite rank: average of available factor ranks per (date, symbol)."""
    cols = sorted(set().union(*[set(p.columns) for p in rank_panels.values()]))
    idx = sorted(set().union(*[set(p.index) for p in rank_panels.values()]))
    aligned = [p.reindex(index=idx, columns=cols).values for p in rank_panels.values()]
    arr = np.dstack(aligned)
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(arr, axis=2)
    return pd.DataFrame(mean, index=idx, columns=cols)


comp_v1_panel = composite_panel({"M": M_rank, "V": V_rank, "C": C_rank, "T": T_rank})
comp_v2_panel = composite_panel({"M": M_rank, "V": V_rank, "C": C_rank, "T": T_rank,
                                 "F": F_rank, "S": S_rank, "G": G_rank})

ic_v1 = spearman_ic(-comp_v1_panel, fwd30)
ic_v2 = spearman_ic(-comp_v2_panel, fwd30)
s_v1 = ic_summary(ic_v1)
s_v2 = ic_summary(ic_v2)

scoreboard = pd.concat([
    pd.DataFrame({"date": ic_v1.index, "ic": ic_v1.values, "version": "v1 (M/V/C/T)"}),
    pd.DataFrame({"date": ic_v2.index, "ic": ic_v2.values, "version": "v2 (+F/S/G)"}),
], ignore_index=True).dropna()

fig = px.line(
    scoreboard,
    x="date",
    y="ic",
    color="version",
    color_discrete_sequence=["#9ecae1", "#1f77b4"],
    title=(
        "Composite IC vs forward 30d return — v1 vs v2<br>"
        f"v1: mean IC={s_v1['mean_ic']:+.3f}  IR={s_v1['ir']:+.2f}  n={s_v1['n']}<br>"
        f"v2: mean IC={s_v2['mean_ic']:+.3f}  IR={s_v2['ir']:+.2f}  n={s_v2['n']}"
    ),
)
fig.add_hline(y=0, line_dash="dot", line_color="grey")
fig.update_layout(yaxis_title="Spearman ρ (per day cross-section)")
save(fig, "04_composite_v1_vs_v2_ic", STEM, width=1300, height=620)

print("done.")
