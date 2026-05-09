"""03 — Price & returns.

The foundation for the M (momentum) and V (volatility) factors:
- Cumulative log returns of top-20 by market cap
- Daily log return distribution by cohort
- Drawdown curves of top-20
- 30-day rolling realised volatility heatmap (top-40)
"""
# %% Imports
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import QUAL, SEQ, load, save, universe_with_mcap

STEM = Path(__file__).stem

# %% Load and shape returns
ticks = load("coingecko_daily_ticks.parquet").copy()
ticks["date"] = pd.to_datetime(ticks["date"])
ticks = ticks.sort_values(["symbol", "date"])

master = universe_with_mcap()
sym_to_cohort = master.set_index("symbol")["cohort"].to_dict()
sym_to_mcap = master.set_index("symbol")["market_cap"].to_dict()

# Stables/wrapped/bridged distort vol & momentum charts; exclude them from
# top-N selection. Cohort distribution chart still uses the full universe.
detail = load("coingecko_coin_details.parquet")
exclude = set(
    detail.loc[
        detail[["is_stablecoin", "is_wrapped", "is_bridged"]].fillna(False).any(axis=1),
        "symbol",
    ]
    .astype(str).str.upper()
)

# Wide price matrix
prices = ticks.pivot_table(
    index="date", columns="symbol", values="price_usd", aggfunc="last"
).sort_index()
log_ret = np.log(prices / prices.shift(1))

# Top 20 by current mkt cap with full price coverage (excluding stables/wrapped/bridged)
coverage = log_ret.notna().sum()
candidates = (
    pd.Series(sym_to_mcap)
    .reindex(coverage.index)
    .dropna()
    .sort_values(ascending=False)
)
candidates = candidates[~candidates.index.isin(exclude)]
top20 = candidates[coverage.reindex(candidates.index).fillna(0) >= 200].head(20).index.tolist()

# %% Cumulative log returns — top 20
cum = log_ret[top20].fillna(0).cumsum()
fig = px.line(
    cum.reset_index().melt(id_vars="date", var_name="symbol", value_name="log_return"),
    x="date",
    y="log_return",
    color="symbol",
    title="Cumulative log return — top 20 by market cap (last 12 months)",
    color_discrete_sequence=px.colors.qualitative.Dark24,
)
fig.update_layout(yaxis_title="cumulative log return")
save(fig, "01_cumulative_log_returns_top20", STEM, width=1300, height=700)

# %% Daily log return distribution by cohort
ret_long = log_ret.reset_index().melt(id_vars="date", var_name="symbol", value_name="log_ret")
ret_long = ret_long.dropna()
ret_long["cohort"] = ret_long["symbol"].map(sym_to_cohort)
ret_long = ret_long.dropna(subset=["cohort"])
clip = ret_long["log_ret"].quantile([0.005, 0.995]).values
ret_long["log_ret_clip"] = ret_long["log_ret"].clip(*clip)

fig = px.violin(
    ret_long,
    x="cohort",
    y="log_ret_clip",
    color="cohort",
    box=True,
    points=False,
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title="Daily log-return distribution by cohort (winsorised at 0.5/99.5%)",
)
fig.update_layout(yaxis_title="daily log return", showlegend=False)
save(fig, "02_return_distribution_by_cohort", STEM, width=1100, height=620)

# %% Drawdown curves — top 20
def drawdown(series: pd.Series) -> pd.Series:
    s = series.dropna()
    peak = s.cummax()
    return (s / peak - 1.0)


dd_frames = []
for s in top20:
    px_series = prices[s].dropna()
    if px_series.empty:
        continue
    dd = drawdown(px_series).rename(s)
    dd_frames.append(dd)
dd_df = pd.concat(dd_frames, axis=1).reset_index().melt(
    id_vars="date", var_name="symbol", value_name="drawdown"
).dropna()

fig = px.line(
    dd_df,
    x="date",
    y="drawdown",
    color="symbol",
    color_discrete_sequence=px.colors.qualitative.Dark24,
    title="Peak-to-trough drawdown — top 20 by market cap",
)
fig.update_yaxes(tickformat=".0%")
fig.update_layout(yaxis_title="drawdown")
save(fig, "03_drawdowns_top20", STEM, width=1300, height=700)

# %% Rolling realised volatility heatmap (top 40)
top40 = candidates[coverage.reindex(candidates.index).fillna(0) >= 200].head(40).index.tolist()
rv = log_ret[top40].rolling(30).std() * np.sqrt(365)
# Sample weekly columns to keep the heatmap legible
rv_w = rv.resample("W").last().dropna(how="all").T
# Order by latest vol descending
last_col = rv_w.columns.max()
rv_w = rv_w.loc[rv_w[last_col].sort_values(ascending=False).index]

fig = px.imshow(
    rv_w,
    color_continuous_scale=SEQ,
    aspect="auto",
    labels=dict(x="week-ending date", y="symbol", color="ann. realised vol"),
    title="30-day rolling realised volatility (annualised) — top 40, weekly resampled",
)
save(fig, "04_rolling_vol_heatmap", STEM, width=1300, height=900)

print("done.")
