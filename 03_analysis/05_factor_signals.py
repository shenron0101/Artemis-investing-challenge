"""05 — RAAM factor signals (M / V / C / T).

Direct visualisation of every Ranked Asset Allocation Model factor
(see ``02_Research/rank.md`` §III–§V):

- (M) Absolute Momentum: 4-month rate-of-change → cross-sectional rank heatmap.
- (V) Volatility: 90-day annualised stdev (proxy for the GARCH/RiskMetrics
      λ=0.94 model in rank.md §III) → cross-sectional rank heatmap.
- (C) Average Relative Correlation: rolling 4-month avg corr of asset vs the
      rest of the universe → time-series of rank.
- (T) ATR Trend/Breakout: 42-period ATR-based upper/lower bands on the top
      assets, Long/Neutral state shaded.
- Composite RAAM rank preview: equally-weighted blend of M/V/C/T ranks.
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
from _common import DIVERGE, QUAL, SEQ, load, save, universe_with_mcap

STEM = Path(__file__).stem

# %% Load price + OHLC + exclusion flags
ticks = load("coingecko_daily_ticks.parquet").copy()
ticks["date"] = pd.to_datetime(ticks["date"])
ohlcv = load("binance_ohlcv_daily.parquet").copy()
ohlcv["date"] = pd.to_datetime(ohlcv["open_time"]).dt.tz_localize(None).dt.normalize()

master = universe_with_mcap()
sym_to_mcap = master.set_index("symbol")["market_cap"].to_dict()

# Exclude stablecoins / wrapped / bridged — they distort every RAAM factor
# (V picks them as "low vol", C picks them as "uncorrelated"). The exclusion
# flags exist on coingecko_coin_details for exactly this reason.
detail = load("coingecko_coin_details.parquet")
# coingecko_coin_details stores symbols lowercase; everything else uses uppercase
exclude = set(
    detail.loc[
        detail[["is_stablecoin", "is_wrapped", "is_bridged"]].fillna(False).any(axis=1),
        "symbol",
    ]
    .astype(str)
    .str.upper()
)
print(f"Excluding {len(exclude)} stablecoin/wrapped/bridged symbols from RAAM universe")

prices = ticks.pivot_table(
    index="date", columns="symbol", values="price_usd", aggfunc="last"
).sort_index()
log_ret = np.log(prices / prices.shift(1))

# Coverage filter
coverage = log_ret.notna().sum()
mcap_series = pd.Series(sym_to_mcap).reindex(coverage.index).dropna()
ranked_syms = [s for s in mcap_series.sort_values(ascending=False).index if s not in exclude]
core = [s for s in ranked_syms if coverage.get(s, 0) >= 200][:40]
prices_core = prices[core]
ret_core = log_ret[core]

# %% (M) Absolute Momentum: 4-month ROC, cross-sectional rank
window = 84  # ~4 trading-equivalent months
mom = (prices_core / prices_core.shift(window)) - 1.0

# Cross-sectional rank, one column per month-end snapshot
month_ends = mom.resample("ME").last().dropna(how="all")
rank_m = month_ends.rank(axis=1, ascending=False)  # 1 = best momentum
heat_m = rank_m.T  # rows = symbol, cols = month
heat_m = heat_m.sort_index()
heat_m.columns = [c.strftime("%Y-%m") for c in heat_m.columns]

fig = px.imshow(
    heat_m,
    color_continuous_scale=DIVERGE,
    aspect="auto",
    labels=dict(x="month-end", y="symbol", color="rank (1=best M)"),
    title="(M) Absolute Momentum — cross-sectional rank by 4-month ROC, top 40",
)
save(fig, "01_M_momentum_rank_heatmap", STEM, width=1300, height=900)

# %% (V) Volatility — 90-day annualised stdev, cross-sectional rank
vol = ret_core.rolling(90).std() * np.sqrt(365)
vol_me = vol.resample("ME").last().dropna(how="all")
rank_v = vol_me.rank(axis=1, ascending=True)  # 1 = lowest vol = best for V
heat_v = rank_v.T
heat_v = heat_v.sort_index()
heat_v.columns = [c.strftime("%Y-%m") for c in heat_v.columns]

fig = px.imshow(
    heat_v,
    color_continuous_scale=DIVERGE,
    aspect="auto",
    labels=dict(x="month-end", y="symbol", color="rank (1=lowest vol)"),
    title="(V) Volatility — cross-sectional rank by 90-day annualised stdev, top 40",
)
save(fig, "02_V_volatility_rank_heatmap", STEM, width=1300, height=900)

# %% (C) Average Relative Correlation — rolling 90-day avg pairwise corr
def rolling_avg_corr(ret_df: pd.DataFrame, window: int = 90) -> pd.DataFrame:
    cols = ret_df.columns
    out = pd.DataFrame(index=ret_df.index, columns=cols, dtype=float)
    for end_idx in range(window, len(ret_df) + 1):
        sl = ret_df.iloc[end_idx - window : end_idx]
        c = sl.corr()
        np.fill_diagonal(c.values, np.nan)
        out.iloc[end_idx - 1] = c.mean(axis=1)
    return out


avg_corr = rolling_avg_corr(ret_core.dropna(axis=1, thresh=200), window=90)
avg_corr_me = avg_corr.resample("ME").last().dropna(how="all")
rank_c = avg_corr_me.rank(axis=1, ascending=True)  # low avg corr = good diversifier
heat_c = rank_c.T
heat_c = heat_c.sort_index()
heat_c.columns = [c.strftime("%Y-%m") for c in heat_c.columns]

fig = px.imshow(
    heat_c,
    color_continuous_scale=DIVERGE,
    aspect="auto",
    labels=dict(x="month-end", y="symbol", color="rank (1=lowest avg corr)"),
    title="(C) Average Relative Correlation — cross-sectional rank, 90-day window",
)
save(fig, "03_C_correlation_rank_heatmap", STEM, width=1300, height=900)

# %% (T) ATR Trend/Breakout System on the top-12 by mkt cap with OHLC coverage
# Apply same exclusion (no stables/wrapped/bridged) so the RAAM strategy stays clean.
ohlcv_prepared = ohlcv.dropna(subset=["symbol", "high", "low", "close"]).copy()
ohlcv_prepared = ohlcv_prepared[~ohlcv_prepared["symbol"].isin(exclude)]
sym_counts = ohlcv_prepared.groupby("symbol")["date"].nunique()
top_with_ohlc = [s for s in ranked_syms if sym_counts.get(s, 0) >= 200][:12]


def atr(df: pd.DataFrame, period: int = 42) -> pd.DataFrame:
    df = df.sort_values("date").copy()
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.rolling(period).mean()
    df["upper"] = df["high"].rolling(period).max() + df["atr"]
    df["lower"] = df["low"].rolling(period).min() - df["atr"]
    df["state"] = 0
    long_mask = df["high"] > df["upper"].shift(1)
    short_mask = df["low"] < df["lower"].shift(1)
    state = pd.Series(np.nan, index=df.index)
    state[long_mask] = 1.0
    state[short_mask] = -1.0
    df["state"] = state.ffill().fillna(0)
    return df


atr_panels = {s: atr(ohlcv_prepared[ohlcv_prepared["symbol"].eq(s)]) for s in top_with_ohlc}

fig = make_subplots(
    rows=4, cols=3,
    subplot_titles=top_with_ohlc,
    shared_xaxes=False,
    horizontal_spacing=0.05, vertical_spacing=0.08,
)
for i, sym in enumerate(top_with_ohlc):
    r, c = i // 3 + 1, i % 3 + 1
    d = atr_panels[sym]
    fig.add_trace(
        go.Scatter(x=d["date"], y=d["close"], mode="lines",
                   line=dict(color="#1f77b4", width=1.2), name="close",
                   showlegend=(i == 0)),
        row=r, col=c,
    )
    fig.add_trace(
        go.Scatter(x=d["date"], y=d["upper"], mode="lines",
                   line=dict(color="#2ca02c", width=1, dash="dot"),
                   name="upper", showlegend=(i == 0)),
        row=r, col=c,
    )
    fig.add_trace(
        go.Scatter(x=d["date"], y=d["lower"], mode="lines",
                   line=dict(color="#d62728", width=1, dash="dot"),
                   name="lower", showlegend=(i == 0)),
        row=r, col=c,
    )
    long_dates = d.loc[d["state"].eq(1.0), "date"]
    if len(long_dates):
        for grp_start, grp_end in zip(long_dates, long_dates):
            pass
        fig.add_trace(
            go.Scatter(
                x=long_dates, y=d.set_index("date").loc[long_dates, "close"],
                mode="markers", marker=dict(color="#2ca02c", size=4, opacity=0.5),
                name="long", showlegend=(i == 0),
            ),
            row=r, col=c,
        )
fig.update_layout(
    title="(T) ATR Trend/Breakout System — 42-period bands, top 12 with Binance OHLCV",
    height=1100,
)
fig.update_yaxes(type="log")
save(fig, "04_T_atr_trend_breakout", STEM, width=1500, height=1100)

# %% Composite RAAM rank preview — latest snapshot, equal-weight M/V/C/T
latest_M = month_ends.iloc[-1].rank(ascending=False)
latest_V = vol_me.iloc[-1].rank(ascending=True)
latest_C = avg_corr_me.iloc[-1].rank(ascending=True)
latest_T = pd.Series({s: atr_panels[s].iloc[-1]["state"] for s in top_with_ohlc})
# Convert T state → rank: long = best (low rank), short = worst.
T_rank = (-latest_T).rank()

ranks = pd.DataFrame({"M": latest_M, "V": latest_V, "C": latest_C, "T": T_rank})
ranks = ranks.dropna(thresh=3)  # require at least 3 of 4 factors
ranks["composite"] = ranks.mean(axis=1)
top_composite = ranks.sort_values("composite").head(25)

fig = go.Figure()
fig.add_trace(go.Bar(
    x=top_composite["composite"],
    y=top_composite.index,
    orientation="h",
    marker=dict(color=top_composite["composite"], colorscale=SEQ, showscale=False),
    text=top_composite["composite"].round(1),
    textposition="outside",
))
fig.update_layout(
    title="Composite RAAM rank (lower = better) — equal-weight M/V/C/T, top 25",
    xaxis_title="composite rank",
    yaxis=dict(autorange="reversed"),
)
save(fig, "05_composite_RAAM_rank", STEM, width=1100, height=820)

print("done.")
