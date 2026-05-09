"""06 — Cross-sectional structure.

Relationships across the universe:
- Pairwise return-correlation matrix, hierarchically clustered
- Factor rank stability — Spearman scatter, M-rank at t vs t-30
- DeFi category roll-up — TVL share over time (stacked area)
- On-chain activity → forward 30-day return scatter (foreshadows IC tests)
"""
# %% Imports
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DIVERGE, QUAL, SEQ, load, save, universe_with_mcap

STEM = Path(__file__).stem

# %% Load
ticks = load("coingecko_daily_ticks.parquet").copy()
ticks["date"] = pd.to_datetime(ticks["date"])
master = universe_with_mcap()
sym_to_cohort = master.set_index("symbol")["cohort"].to_dict()
sym_to_mcap = master.set_index("symbol")["market_cap"].to_dict()
act_l = load("artemis_activity_long.parquet").copy()
act_l["date"] = pd.to_datetime(act_l["date"])
act_l["value"] = pd.to_numeric(act_l["value"], errors="coerce")
act_l = act_l.dropna(subset=["value"])

tvl = load("defillama_protocol_tvl_daily.parquet").copy()
tvl["date"] = pd.to_datetime(tvl["date"])
dl_map = load("defillama_protocol_map.parquet")

prices = ticks.pivot_table(
    index="date", columns="symbol", values="price_usd", aggfunc="last"
).sort_index()
log_ret = np.log(prices / prices.shift(1))

detail = load("coingecko_coin_details.parquet")
exclude = set(
    detail.loc[
        detail[["is_stablecoin", "is_wrapped", "is_bridged"]].fillna(False).any(axis=1),
        "symbol",
    ]
    .astype(str)
    .str.upper()
)

coverage = log_ret.notna().sum()
mcap = pd.Series(sym_to_mcap).reindex(coverage.index).dropna()
top50 = [
    s for s in mcap.sort_values(ascending=False).index
    if coverage.get(s, 0) >= 200 and s not in exclude
][:50]
# Don't drop rows here — pandas corr() handles pairwise missing values natively
ret = log_ret[top50]

# %% Pairwise correlation matrix, hierarchically ordered
corr = ret.corr().fillna(0)
distance = 1 - corr
condensed = squareform(distance.values, checks=False)
order = leaves_list(linkage(condensed, method="average"))
corr_ord = corr.iloc[order, order]

fig = go.Figure(
    data=go.Heatmap(
        z=corr_ord.values,
        x=corr_ord.columns,
        y=corr_ord.index,
        colorscale=DIVERGE,
        zmin=-1, zmax=1, zmid=0,
        colorbar=dict(title="ρ"),
    )
)
fig.update_layout(
    title=f"Pairwise daily log-return correlation — top {len(corr_ord)}, hierarchically ordered",
    xaxis=dict(side="bottom", tickfont=dict(size=8)),
    yaxis=dict(autorange="reversed", tickfont=dict(size=8)),
)
save(fig, "01_corr_clustermap", STEM, width=1100, height=1100)

# %% Factor rank stability — M(t) vs M(t-30)
window = 84
mom = (prices[top50] / prices[top50].shift(window)) - 1.0
mom_today = mom.iloc[-1].dropna()
mom_lag30 = mom.iloc[-31].dropna() if len(mom) >= 31 else pd.Series(dtype=float)
common = mom_today.index.intersection(mom_lag30.index)
df = pd.DataFrame({
    "rank_today": mom_today.loc[common].rank(ascending=False),
    "rank_30d_ago": mom_lag30.loc[common].rank(ascending=False),
}).reset_index().rename(columns={"index": "symbol"})
df["cohort"] = df["symbol"].map(sym_to_cohort)
spearman = df[["rank_today", "rank_30d_ago"]].corr(method="spearman").iloc[0, 1]

fig = px.scatter(
    df,
    x="rank_30d_ago",
    y="rank_today",
    text="symbol",
    color="cohort",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title=f"M-factor rank stability (top 50) — Spearman ρ(t, t-30) = {spearman:.2f}",
)
fig.add_shape(type="line", x0=0, y0=0, x1=df["rank_30d_ago"].max(),
              y1=df["rank_today"].max(), line=dict(dash="dot", color="grey"))
fig.update_traces(textposition="top center", textfont=dict(size=8))
fig.update_layout(xaxis_title="M rank, 30 days ago",
                  yaxis_title="M rank, today")
save(fig, "02_M_rank_stability_scatter", STEM, width=1100, height=900)

# %% DeFi category roll-up — TVL share over time (stacked area)
tvl_join = tvl.merge(
    dl_map[["defillama_slug", "defillama_category"]].dropna().drop_duplicates(),
    on="defillama_slug",
    how="left",
).dropna(subset=["defillama_category"])
roll = (
    tvl_join.groupby(["date", "defillama_category"])["tvl_usd"].sum().reset_index()
)
total = roll.groupby("date")["tvl_usd"].sum().rename("total")
roll = roll.merge(total, on="date")
roll["share"] = roll["tvl_usd"] / roll["total"]
# Restrict to the period where at least 2 categories exist (avoids spurious 100% bars)
recent = roll[roll["date"] >= "2024-01-01"]

fig = px.area(
    recent.sort_values("date"),
    x="date",
    y="share",
    color="defillama_category",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title="DeFiLlama TVL share by category (mapped universe, since 2024-01)",
)
fig.update_yaxes(tickformat=".0%", range=[0, 1])
fig.update_layout(yaxis_title="share of mapped TVL")
save(fig, "03_defi_category_share", STEM, width=1300, height=720)

# %% Activity → forward 30-day return scatter
fees_series = act_l[act_l["metric"].eq("fees")].copy()
# 30d trailing avg fees per symbol on a reference date 30d before the latest tick
ref_date = ticks["date"].max() - pd.Timedelta(days=30)
trailing_fees = (
    fees_series[(fees_series["date"] >= ref_date - pd.Timedelta(days=30))
                & (fees_series["date"] < ref_date)]
    .groupby("symbol")["value"].mean()
    .rename("avg_fees_30d")
)
fwd_prices = prices.loc[ticks["date"].max()] / prices.loc[ref_date] - 1
fwd_prices = fwd_prices.rename("fwd_30d_ret")
scat = pd.concat([trailing_fees, fwd_prices], axis=1).dropna()
scat = scat[scat["avg_fees_30d"] > 0]
scat["log_avg_fees_30d"] = np.log10(scat["avg_fees_30d"])
scat["cohort"] = scat.index.map(sym_to_cohort)
scat = scat.dropna(subset=["cohort"]).reset_index().rename(columns={"index": "symbol"})

fig = px.scatter(
    scat,
    x="log_avg_fees_30d",
    y="fwd_30d_ret",
    color="cohort",
    text="symbol",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title=f"Activity vs forward 30-day return — log10(avg fees, 30d preceding {ref_date.date()})",
    trendline="ols",
)
fig.update_traces(textposition="top center", textfont=dict(size=8))
fig.update_yaxes(tickformat=".0%")
fig.update_layout(xaxis_title="log10 avg daily fees (USD), trailing 30d before reference",
                  yaxis_title="forward 30-day price return")
save(fig, "04_activity_vs_fwd_return", STEM, width=1300, height=820)

print("done.")
