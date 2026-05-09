"""01 — Data quality.

Verify the data is fit for purpose before factor work:
- Coverage heatmap (asset × source)
- Daily-tick freshness per symbol
- Missing-day count per symbol
- Sentinel share per Artemis metric
"""
# %% Imports & config
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CLEAN, QUAL, SEQ, load, save, universe_with_mcap

STEM = Path(__file__).stem

# %% Load
master = universe_with_mcap()
ticks = load("coingecko_daily_ticks.parquet")
ohlcv = load("binance_ohlcv_daily.parquet")
act_l = load("artemis_activity_long.parquet")
tvl = load("defillama_protocol_tvl_daily.parquet")
fees = load("defillama_fees_revenue_summary.parquet")
dl_map = load("defillama_protocol_map.parquet")

# %% Coverage heatmap (asset × source)
# Universe is asset_master.symbol; presence in each source table.
universe = master.sort_values("market_cap", ascending=False)
sym_order = universe["symbol"].tolist()

cov = pd.DataFrame(index=sym_order)
cov["CoinGecko (price)"] = cov.index.isin(ticks["symbol"].unique())
cov["Binance (OHLCV)"] = cov.index.isin(ohlcv["symbol"].dropna().unique())
cov["Artemis (activity)"] = cov.index.isin(
    act_l.dropna(subset=["value"])["symbol"].unique()
)
dl_syms = dl_map.loc[dl_map["mapping_status"].eq("mapped"), "symbol"].unique()
cov["DeFiLlama (TVL/fees)"] = cov.index.isin(dl_syms)
cov_int = cov.astype(int)

fig = px.imshow(
    cov_int.T,
    color_continuous_scale=[(0, "#f1f3f5"), (1, "#1f77b4")],
    aspect="auto",
    labels=dict(x="symbol (mkt-cap desc)", y="source", color="present"),
    title="Coverage matrix — universe × source (1 = present, 0 = missing)",
)
fig.update_xaxes(tickfont=dict(size=8))
fig.update_layout(coloraxis_showscale=False)
save(fig, "01_coverage_matrix", STEM, width=1600, height=520)

# %% Per-source coverage rate (summary bar)
rates = (cov_int.sum() / len(cov_int) * 100).round(1).reset_index()
rates.columns = ["source", "coverage_pct"]
fig = px.bar(
    rates.sort_values("coverage_pct"),
    x="coverage_pct",
    y="source",
    orientation="h",
    text="coverage_pct",
    color="source",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title=f"Universe-level coverage by source (n={len(cov_int)} symbols)",
)
fig.update_traces(texttemplate="%{text}%", textposition="outside")
fig.update_layout(showlegend=False, xaxis_title="% of universe", yaxis_title="")
save(fig, "02_source_coverage_rate", STEM, width=900, height=420)

# %% Daily-tick freshness — last seen date per symbol vs run date
last_seen = (
    ticks.groupby("symbol")["date"]
    .max()
    .reset_index()
    .rename(columns={"date": "last_tick"})
)
last_seen["last_tick"] = pd.to_datetime(last_seen["last_tick"])
run_date = last_seen["last_tick"].max()
last_seen["lag_days"] = (run_date - last_seen["last_tick"]).dt.days
fresh = last_seen.merge(
    master[["symbol", "market_cap"]], on="symbol", how="left"
).sort_values("lag_days", ascending=False)
stale = fresh[fresh["lag_days"] > 0]

fig = px.bar(
    stale.head(30),
    x="lag_days",
    y="symbol",
    orientation="h",
    color="lag_days",
    color_continuous_scale=SEQ,
    title=f"CoinGecko daily-tick staleness — top 30 symbols by lag vs {run_date.date()}",
)
fig.update_layout(yaxis=dict(autorange="reversed"))
save(fig, "03_freshness_top_lags", STEM, width=1100, height=720)

# %% Gap detection — count of missing trading days within each symbol's series
def missing_count(g: pd.DataFrame) -> int:
    g = g.sort_values("date")
    rng = pd.date_range(g["date"].min(), g["date"].max(), freq="D")
    return int(rng.size - g["date"].nunique())


gaps = ticks.groupby("symbol").apply(missing_count, include_groups=False).reset_index(
    name="missing_days"
)
gaps = gaps.merge(master[["symbol", "market_cap", "cohort"]], on="symbol", how="left")
worst = gaps.sort_values("missing_days", ascending=False).head(25)

fig = px.bar(
    worst,
    x="missing_days",
    y="symbol",
    orientation="h",
    color="cohort",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title="Top 25 symbols with the most missing daily ticks (within observed window)",
)
fig.update_layout(yaxis=dict(autorange="reversed"))
save(fig, "04_missing_day_count", STEM, width=1100, height=720)

# %% Sentinel share per Artemis metric
sentinel = (
    act_l.assign(value=pd.to_numeric(act_l["value"], errors="coerce"))
    .groupby("metric")["value"]
    .agg(rows="size", missing=lambda s: int(s.isna().sum()))
    .reset_index()
)
sentinel["missing_pct"] = (sentinel["missing"] / sentinel["rows"] * 100).round(1)
sentinel = sentinel.sort_values("missing_pct")

fig = px.bar(
    sentinel,
    x="missing_pct",
    y="metric",
    orientation="h",
    text="missing_pct",
    color="missing_pct",
    color_continuous_scale="Reds",
    title="Artemis sentinel share — % of values returned as 'Metric not available for asset.'",
)
fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig.update_layout(coloraxis_showscale=False, xaxis=dict(range=[0, 110]))
save(fig, "05_artemis_sentinel_share", STEM, width=1100, height=520)

print("done.")
