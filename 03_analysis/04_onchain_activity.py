"""04 — On-chain activity & monetisation.

Artemis usage signals + DeFiLlama economics:
- DAU + transactions / volume small-multiples for top symbols
- Revenue mix: active vs passive over time (top symbols)
- Latest 30d fees / revenue ranking from DeFiLlama
- TVL trajectories (log-y) for the mapped DeFi slugs
"""
# %% Imports
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import QUAL, SEQ, load, save, universe_with_mcap

STEM = Path(__file__).stem

# %% Load
act_l = load("artemis_activity_long.parquet").copy()
act_l["date"] = pd.to_datetime(act_l["date"])
act_l["value"] = pd.to_numeric(act_l["value"], errors="coerce")
act_l = act_l.dropna(subset=["value"])

tvl = load("defillama_protocol_tvl_daily.parquet").copy()
tvl["date"] = pd.to_datetime(tvl["date"])

fees = load("defillama_fees_revenue_summary.parquet").copy()
dl_map = load("defillama_protocol_map.parquet")
slug_to_name = dl_map.set_index("defillama_slug")["defillama_name"].to_dict()

master = universe_with_mcap()

# %% DAU time series — top 8 by trailing-30d average DAU
dau = act_l[act_l["metric"].eq("dau")].copy()
last30 = dau["date"].max() - pd.Timedelta(days=30)
top_dau_syms = (
    dau[dau["date"] >= last30].groupby("symbol")["value"].mean().sort_values(ascending=False).head(8).index.tolist()
)
plot = dau[dau["symbol"].isin(top_dau_syms)].pivot_table(
    index="date", columns="symbol", values="value"
).sort_index()
fig = px.line(
    plot.reset_index().melt(id_vars="date", var_name="symbol", value_name="dau"),
    x="date",
    y="dau",
    color="symbol",
    color_discrete_sequence=px.colors.qualitative.Dark24,
    title="Daily Active Addresses (Artemis) — top 8 by trailing-30d average",
)
fig.update_yaxes(type="log")
fig.update_layout(yaxis_title="DAU (log)")
save(fig, "01_dau_top8", STEM, width=1300, height=620)

# %% Revenue split — active vs passive (top 6 by total 90-day revenue)
rev = act_l[act_l["metric"].isin(["active_revenue", "passive_revenue"])]
last90 = rev["date"].max() - pd.Timedelta(days=90)
top_rev = (
    rev[rev["date"] >= last90].groupby("symbol")["value"].sum().sort_values(ascending=False).head(6).index.tolist()
)
plot = rev[rev["symbol"].isin(top_rev)].copy()
plot = plot.groupby(["date", "symbol", "metric"], as_index=False)["value"].sum()

fig = px.area(
    plot.sort_values(["symbol", "date"]),
    x="date",
    y="value",
    color="metric",
    facet_col="symbol",
    facet_col_wrap=3,
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title="Active vs passive revenue (Artemis) — top 6 by trailing-90d total",
)
fig.update_yaxes(matches=None, showticklabels=True)
fig.update_layout(yaxis_title="USD/day")
save(fig, "02_active_vs_passive_revenue", STEM, width=1400, height=820)

# %% Latest fees & revenue ranking (DeFiLlama 30d totals, log scale)
fees_plot = fees.merge(
    dl_map[["defillama_slug", "defillama_name"]].drop_duplicates(),
    on="defillama_slug",
    how="left",
)
fees_plot["protocol"] = fees_plot["defillama_name"].fillna(fees_plot["defillama_slug"])
fees_plot = fees_plot.dropna(subset=["total30d"])
fees_plot["total30d"] = pd.to_numeric(fees_plot["total30d"], errors="coerce")
fees_plot = fees_plot.dropna(subset=["total30d"])

fig = px.bar(
    fees_plot.sort_values("total30d"),
    x="total30d",
    y="protocol",
    color="data_type",
    barmode="group",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title="DeFiLlama 30-day totals — fees / revenue / holders revenue (USD)",
    log_x=True,
)
fig.update_layout(xaxis_title="USD (30d total, log scale)", yaxis_title="")
save(fig, "03_defillama_fees_30d_ranking", STEM, width=1300, height=820)

# %% TVL trajectories — top 15 by current TVL
current = tvl.sort_values("date").groupby("defillama_slug").tail(1)
top_slugs = current.sort_values("tvl_usd", ascending=False).head(15)["defillama_slug"].tolist()
tvl_plot = tvl[tvl["defillama_slug"].isin(top_slugs)].copy()
tvl_plot["protocol"] = tvl_plot["defillama_slug"].map(slug_to_name).fillna(tvl_plot["defillama_slug"])

fig = px.line(
    tvl_plot.sort_values(["protocol", "date"]),
    x="date",
    y="tvl_usd",
    color="protocol",
    color_discrete_sequence=px.colors.qualitative.Dark24,
    title="DeFiLlama Total Value Locked — top 15 by current TVL (log y)",
)
fig.update_yaxes(type="log")
fig.update_layout(yaxis_title="TVL (USD, log)")
save(fig, "04_tvl_top15", STEM, width=1400, height=720)

print("done.")
