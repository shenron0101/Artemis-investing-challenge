"""02 — Universe profile.

Know the universe before factoring:
- Market-cap distribution (log-x histogram, by cohort)
- Top-N concentration curve
- Category mix (CoinGecko categories + DeFiLlama categories)
- Exclusion-flag breakdown (stablecoin / wrapped / bridged)
"""
# %% Imports
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import QUAL, SEQ, load, save, universe_with_mcap

STEM = Path(__file__).stem

# %% Load
master = universe_with_mcap()
detail = load("coingecko_coin_details.parquet")
dl_map = load("defillama_protocol_map.parquet")

# %% Market-cap distribution by cohort (log x)
plot_df = master.dropna(subset=["market_cap"]).copy()
plot_df["log10_mcap"] = np.log10(plot_df["market_cap"].clip(lower=1))
fig = px.histogram(
    plot_df,
    x="log10_mcap",
    color="cohort",
    nbins=30,
    barmode="overlay",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title="Market-cap distribution (log10 USD), by cohort",
    opacity=0.7,
)
fig.update_layout(xaxis_title="log10(market cap, USD)", yaxis_title="count")
save(fig, "01_mcap_distribution", STEM, width=1100, height=560)

# %% Top-N concentration (cumulative share of total mkt cap)
ordered = master.dropna(subset=["market_cap"]).sort_values(
    "market_cap", ascending=False
)
ordered["cum_share"] = ordered["market_cap"].cumsum() / ordered["market_cap"].sum()
ordered["rank"] = np.arange(1, len(ordered) + 1)

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=ordered["rank"],
        y=ordered["cum_share"] * 100,
        mode="lines+markers",
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=4),
        hovertemplate="rank %{x}<br>cum share %{y:.1f}%<extra></extra>",
    )
)
for ref in (0.5, 0.8, 0.95):
    n_for = int((ordered["cum_share"] >= ref).idxmax()) + 1 if (ordered["cum_share"] >= ref).any() else None
    if n_for:
        fig.add_hline(y=ref * 100, line_dash="dot", line_color="grey",
                      annotation_text=f"{int(ref*100)}% reached at N={n_for}")
fig.update_layout(
    title="Cumulative market-cap concentration",
    xaxis_title="N (top-N by market cap)",
    yaxis_title="% of total universe market cap",
)
save(fig, "02_concentration_curve", STEM, width=1100, height=560)

# %% Category mix — CoinGecko (top 25 categories)
def explode_categories(s: pd.Series) -> Counter:
    bag: Counter = Counter()
    for raw in s.dropna():
        if isinstance(raw, (list, tuple, np.ndarray)):
            cats = list(raw)
        elif isinstance(raw, str):
            try:
                import ast
                cats = ast.literal_eval(raw) if raw.startswith("[") else [raw]
            except Exception:
                cats = [raw]
        else:
            continue
        for c in cats:
            if isinstance(c, str) and c.strip():
                bag[c.strip()] += 1
    return bag


cg_cats = explode_categories(detail["categories"])
cg_top = (
    pd.DataFrame(cg_cats.most_common(25), columns=["category", "n_coins"])
    .sort_values("n_coins")
)

fig = px.bar(
    cg_top,
    x="n_coins",
    y="category",
    orientation="h",
    color="n_coins",
    color_continuous_scale=SEQ,
    title="Top 25 CoinGecko categories represented in the universe",
)
fig.update_layout(coloraxis_showscale=False)
save(fig, "03_coingecko_top_categories", STEM, width=1100, height=720)

# %% Category mix — DeFiLlama (mapped protocols only)
dl_cat = (
    dl_map.dropna(subset=["defillama_category"])
    .groupby("defillama_category")
    .agg(n_protocols=("defillama_slug", "nunique"),
         total_tvl_usd=("current_tvl_usd", "sum"))
    .reset_index()
    .sort_values("total_tvl_usd", ascending=False)
)

fig = px.treemap(
    dl_cat,
    path=[px.Constant("DeFi protocols mapped"), "defillama_category"],
    values="total_tvl_usd",
    color="n_protocols",
    color_continuous_scale=SEQ,
    title="DeFiLlama category mix — area = current TVL (USD), colour = protocol count",
)
save(fig, "04_defillama_category_treemap", STEM, width=1200, height=720)

# %% Exclusion-flag breakdown (stablecoin / wrapped / bridged)
flags = detail[["symbol", "is_stablecoin", "is_wrapped", "is_bridged"]].fillna(False)
flags["is_clean"] = ~(flags[["is_stablecoin", "is_wrapped", "is_bridged"]].any(axis=1))
counts = (
    flags[["is_stablecoin", "is_wrapped", "is_bridged", "is_clean"]]
    .sum()
    .reset_index()
)
counts.columns = ["flag", "count"]
counts["pct_of_universe"] = counts["count"] / len(flags) * 100

fig = px.bar(
    counts.sort_values("count", ascending=True),
    x="count",
    y="flag",
    text=counts["pct_of_universe"].round(1).astype(str) + "%",
    orientation="h",
    color="flag",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title=f"Universe exclusion flags (n={len(flags)} symbols with detail records)",
)
fig.update_traces(textposition="outside")
fig.update_layout(showlegend=False)
save(fig, "05_exclusion_flags", STEM, width=900, height=420)

print("done.")
