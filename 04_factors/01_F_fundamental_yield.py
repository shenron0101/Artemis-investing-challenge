"""01 — F factor: Fundamental Yield (crypto P/S analog).

Economic intuition: a token whose protocol generates real cash flow has
implicit backing that survives sentiment unwinds. Equity investors anchor on
P/S; the crypto analog is annualised fees+revenue divided by market cap.

Signal:
    fees_30d_ann    = mean(fees,    last 30d) * 365
    revenue_30d_ann = mean(revenue, last 30d) * 365
    F = (fees_30d_ann + 0.5 * revenue_30d_ann) / market_cap
    F_rank = highest F → rank 1 (best)

Outputs:
    01_yield_distribution.png         — log-x histogram of latest F by cohort
    02_F_rank_heatmap.png             — month-end rank heatmap, top 30 covered
    03_F_vs_M_scatter.png             — independence check vs momentum
    04_F_information_coefficient.png  — daily Spearman IC vs fwd 30/60/90d ret
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
    QUAL,
    SEQ,
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

# %% Load activity + universe
act = load("artemis_activity_long.parquet").copy()
act["date"] = pd.to_datetime(act["date"], errors="coerce")
act = act.dropna(subset=["date"])
act["value"] = pd.to_numeric(act["value"], errors="coerce")
act = act.dropna(subset=["value"])

excl = exclude_symbols()
master = universe_with_mcap()
sym_to_cohort = master.set_index("symbol")["cohort"].to_dict()

prices = prices_wide()
mcaps = market_caps_wide()  # ffill is built into the helper

# %% Build trailing fees + revenue panels (date × symbol)
def daily_panel(metric: str) -> pd.DataFrame:
    sub = act[act["metric"].eq(metric)]
    return (
        sub.pivot_table(index="date", columns="symbol", values="value", aggfunc="last")
        .sort_index()
    )


fees_d = daily_panel("fees")
rev_d = daily_panel("revenue")

# Align indexes — use the price calendar so IC alignment is straightforward
calendar = prices.index
fees_d = fees_d.reindex(calendar)
rev_d = rev_d.reindex(calendar)

fees_30 = fees_d.rolling(30, min_periods=10).mean()
rev_30 = rev_d.rolling(30, min_periods=10).mean()

# Annualise (daily mean × 365). 30d window of daily data → average daily flow.
fund_cashflow = fees_30 * 365 + 0.5 * rev_30 * 365

# F = cashflow / market cap (only where mcap available)
common_cols = fund_cashflow.columns.intersection(mcaps.columns)
F = fund_cashflow[common_cols] / mcaps[common_cols]
F = F.replace([np.inf, -np.inf], np.nan)

# Drop excluded tickers
F = F.drop(columns=[c for c in F.columns if c in excl], errors="ignore")
print(f"F panel: {F.shape[0]} dates × {F.shape[1]} symbols (post-exclusion)")
print(f"latest non-null F coverage: {F.iloc[-1].notna().sum()} symbols")

# %% Panel 1 — distribution of latest F by cohort
latest = F.iloc[-1].dropna()
dist_df = pd.DataFrame({"symbol": latest.index, "F": latest.values})
dist_df["log10_F"] = np.log10(dist_df["F"].clip(lower=1e-6))
dist_df["cohort"] = dist_df["symbol"].map(sym_to_cohort)
dist_df = dist_df.dropna(subset=["cohort"])

q25, q50, q75 = np.percentile(dist_df["log10_F"], [25, 50, 75])
fig = px.histogram(
    dist_df,
    x="log10_F",
    color="cohort",
    nbins=30,
    barmode="overlay",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    opacity=0.7,
    title=(
        f"F = (annualised fees + 0.5 × revenue) / market cap — "
        f"latest cross-section ({F.index[-1].date()}, n={len(dist_df)})"
    ),
)
for q, label in [(q25, "P25"), (q50, "P50"), (q75, "P75")]:
    fig.add_vline(x=q, line_dash="dot", line_color="grey",
                  annotation_text=f"{label}={10**q:.3f}")
fig.update_layout(xaxis_title="log10(F)", yaxis_title="count")
save(fig, "01_yield_distribution", STEM, width=1100, height=560)

# %% Panel 2 — month-end rank heatmap, top 30 covered symbols
month_ends = F.resample("ME").last()
covered = month_ends.notna().sum().sort_values(ascending=False).head(30).index.tolist()
heat = month_ends[covered].rank(axis=1, ascending=False, na_option="keep")
heat = heat.T  # rows = symbol, cols = month
heat = heat.loc[heat.iloc[:, -1].sort_values().index]
heat.columns = [c.strftime("%Y-%m") for c in heat.columns]

fig = px.imshow(
    heat,
    color_continuous_scale=DIVERGE,
    aspect="auto",
    labels=dict(x="month-end", y="symbol", color="rank (1=highest yield)"),
    title="(F) Fundamental yield — cross-sectional rank, top 30 by data coverage",
)
save(fig, "02_F_rank_heatmap", STEM, width=1300, height=900)

# %% Panel 3 — F vs M (independence check)
window = 84
M = (prices / prices.shift(window)) - 1.0  # 4-month ROC
M = M.drop(columns=[c for c in M.columns if c in excl], errors="ignore")

latest_F_rank = F.iloc[-1].rank(ascending=False)
latest_M_rank = M.iloc[-1].rank(ascending=False)

scat_idx = latest_F_rank.dropna().index.intersection(latest_M_rank.dropna().index)
scat = pd.DataFrame({
    "symbol": scat_idx,
    "F_rank": latest_F_rank.loc[scat_idx].values,
    "M_rank": latest_M_rank.loc[scat_idx].values,
})
scat["cohort"] = scat["symbol"].map(sym_to_cohort)
spearman = scat[["F_rank", "M_rank"]].corr(method="spearman").iloc[0, 1]

fig = px.scatter(
    scat,
    x="M_rank",
    y="F_rank",
    color="cohort",
    text="symbol",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title=f"F vs M independence — Spearman ρ = {spearman:.2f} (close to 0 = independent signal)",
)
fig.update_traces(textposition="top center", textfont=dict(size=8))
fig.update_layout(xaxis_title="M rank (1=best momentum)",
                  yaxis_title="F rank (1=highest yield)")
save(fig, "03_F_vs_M_scatter", STEM, width=1200, height=900)

# %% Panel 4 — Information coefficient (load-bearing validation)
fwd = forward_returns(prices, horizons=(30, 60, 90))
F_ranks = cross_sectional_rank(F, ascending=False)  # high yield = rank 1

ic_lines = []
summary_lines = []
for h, ret in fwd.items():
    # Use NEGATIVE rank so positive IC means high-yield → high return.
    ic = spearman_ic(-F_ranks, ret)
    s = ic_summary(ic)
    summary_lines.append(f"h={h}d  mean IC={s['mean_ic']:+.3f}  IR={s['ir']:+.2f}  n={s['n']}")
    ic_lines.append(pd.DataFrame({"date": ic.index, "ic": ic.values, "horizon": f"{h}d"}))

ic_df = pd.concat(ic_lines, ignore_index=True).dropna()
fig = px.line(
    ic_df,
    x="date",
    y="ic",
    color="horizon",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title="(F) Information coefficient — daily Spearman ρ vs forward returns<br>"
          + "<br>".join(summary_lines),
)
fig.add_hline(y=0, line_dash="dot", line_color="grey")
fig.update_layout(yaxis_title="Spearman ρ (per day cross-section)")
save(fig, "04_F_information_coefficient", STEM, width=1300, height=620)

print("done.")
