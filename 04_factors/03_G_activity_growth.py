"""03 — G factor: Activity-Validated Growth (fundamental momentum + bubble flag).

Economic intuition: the crypto analog of earnings-revision momentum
(Bernard & Thomas 1989). Stocks whose fundamentals are improving outperform —
even more so when price hasn't yet noticed. In crypto, fundamentals = on-chain
activity (DAU, fees, revenue). Four regimes matter:

    confirmed     : usage ↑ AND price ↑   (safe ride, fundamentals back the move)
    accumulation  : usage ↑ AND price ↓   (the alpha — re-rate likely)
    blow-off      : usage ↓ AND price ↑   (bubble flag, fade)
    dying         : usage ↓ AND price ↓   (structural short candidate)

Signal: per-symbol short-vs-long activity ratio across DAU / fees / revenue,
averaged into a growth_score, then penalised by recent price drift.

    g_m            = mean(metric, last 30d) / mean(metric, last 120d) - 1
    growth_score   = mean of z-scored g_dau, g_fees, g_revenue (skip-NaN)
    price_score    = z(log_return_90d)
    G_score        = growth_score - 0.5 * price_score
    G_rank         = highest G_score → rank 1

Outputs:
    01_growth_quadrant.png            — growth_score vs price_score scatter
    02_per_metric_growth_heatmap.png  — DAU / fees / revenue growth side-by-side
    03_G_vs_F_scatter.png             — collinearity check vs F
    04_G_information_coefficient.png  — daily Spearman IC vs fwd 30/60/90d ret
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

# %% Load
act = load("artemis_activity_long.parquet").copy()
act["date"] = pd.to_datetime(act["date"], errors="coerce")
act = act.dropna(subset=["date"])
act["value"] = pd.to_numeric(act["value"], errors="coerce")
act = act.dropna(subset=["value"])

excl = exclude_symbols()
master = universe_with_mcap()
sym_to_cohort = master.set_index("symbol")["cohort"].to_dict()
sym_to_mcap = master.set_index("symbol")["market_cap"].to_dict()

prices = prices_wide()
log_prices = np.log(prices)

# %% Build per-metric daily panels
def daily_panel(metric: str) -> pd.DataFrame:
    sub = act[act["metric"].eq(metric)]
    return (
        sub.pivot_table(index="date", columns="symbol", values="value", aggfunc="last")
        .reindex(prices.index)
    )


metrics = ["dau", "fees", "revenue"]
panels = {m: daily_panel(m) for m in metrics}

# Compute g_m = mean(last 30d) / mean(last 120d) - 1
SHORT, LONG = 30, 120
g_panels = {}
for m, p in panels.items():
    short_mean = p.rolling(SHORT, min_periods=10).mean()
    long_mean = p.rolling(LONG, min_periods=40).mean()
    g = (short_mean / long_mean) - 1.0
    g = g.replace([np.inf, -np.inf], np.nan)
    # Drop excluded
    g = g.drop(columns=[c for c in g.columns if c in excl], errors="ignore")
    g_panels[m] = g

# z-score each metric panel cross-sectionally per row, then average
def cross_z(panel: pd.DataFrame) -> pd.DataFrame:
    return panel.sub(panel.mean(axis=1), axis=0).div(panel.std(axis=1), axis=0)


z_panels = {m: cross_z(g) for m, g in g_panels.items()}
all_syms = sorted(set().union(*[set(z.columns) for z in z_panels.values()]))
growth_score = pd.DataFrame(
    np.nanmean(
        np.dstack([z.reindex(columns=all_syms).values for z in z_panels.values()]),
        axis=2,
    ),
    index=z_panels["dau"].index,
    columns=all_syms,
)

# Price score = z(log_return_90d)
price_ret_90 = log_prices - log_prices.shift(90)
price_ret_90 = price_ret_90.drop(columns=[c for c in price_ret_90.columns if c in excl], errors="ignore")
price_score = cross_z(price_ret_90)

# Align columns
common = growth_score.columns.intersection(price_score.columns)
G_score = growth_score[common] - 0.5 * price_score[common]
print(f"G panel: {G_score.shape}")
print(f"latest non-null G: {G_score.iloc[-1].notna().sum()} symbols")

# %% Panel 1 — quadrant scatter at latest date
gs = growth_score.iloc[-1]
ps = price_score.iloc[-1]
common_latest = gs.dropna().index.intersection(ps.dropna().index)
quad = pd.DataFrame({
    "symbol": common_latest,
    "growth_score": gs.loc[common_latest].values,
    "price_score": ps.loc[common_latest].values,
})
quad["cohort"] = quad["symbol"].map(sym_to_cohort)
quad["mcap"] = quad["symbol"].map(sym_to_mcap)
quad = quad.dropna(subset=["mcap"])


def label_quadrant(row):
    if row["growth_score"] > 0 and row["price_score"] > 0:
        return "confirmed"
    if row["growth_score"] > 0 and row["price_score"] <= 0:
        return "accumulation"
    if row["growth_score"] <= 0 and row["price_score"] > 0:
        return "blow-off"
    return "dying"


quad["quadrant"] = quad.apply(label_quadrant, axis=1)

fig = px.scatter(
    quad,
    x="growth_score",
    y="price_score",
    color="quadrant",
    text="symbol",
    size="mcap",
    color_discrete_map={
        "confirmed": "#2ca02c",
        "accumulation": "#1f77b4",
        "blow-off": "#d62728",
        "dying": "#7f7f7f",
    },
    title=f"Activity-validated growth quadrant — {len(quad)} symbols, mcap-sized<br>"
          f"top-right = confirmed momentum; bottom-right = accumulation alpha; "
          f"top-left = blow-off warning; bottom-left = dying",
)
fig.update_traces(textposition="top center", textfont=dict(size=8))
fig.add_vline(x=0, line_dash="dot", line_color="grey")
fig.add_hline(y=0, line_dash="dot", line_color="grey")
fig.update_layout(xaxis_title="growth_score (z-avg of DAU/fees/revenue 30d-vs-120d)",
                  yaxis_title="price_score (z of 90d log return)")
save(fig, "01_growth_quadrant", STEM, width=1300, height=900)

# %% Panel 2 — per-metric growth heatmap (3 sub-panels at latest date)
covered_per_metric = {m: g.iloc[-1].dropna().index.tolist() for m, g in g_panels.items()}
universe_for_heat = sorted(set(covered_per_metric["dau"])
                           & set(covered_per_metric["fees"])
                           & set(covered_per_metric["revenue"]))[:30]

# Build a 3-column heatmap: rows = symbol, cols = month-end, panels = metric
month_ends = pd.date_range(g_panels["dau"].index.min(), g_panels["dau"].index.max(),
                           freq="ME")
fig = make_subplots(rows=1, cols=3, subplot_titles=[m.upper() for m in metrics],
                    horizontal_spacing=0.06, shared_yaxes=True)
for i, m in enumerate(metrics):
    g = g_panels[m].reindex(columns=universe_for_heat)
    me = g.resample("ME").last().dropna(how="all").T
    if me.empty:
        continue
    me = me.loc[me.iloc[:, -1].sort_values(ascending=False).index]
    me.columns = [c.strftime("%Y-%m") for c in me.columns]
    fig.add_trace(
        go.Heatmap(
            z=me.values,
            x=me.columns,
            y=me.index,
            colorscale=DIVERGE,
            zmid=0,
            zmin=-0.5, zmax=0.5,
            showscale=(i == 2),
            colorbar=dict(title="g (Δ short/long − 1)"),
        ),
        row=1, col=i + 1,
    )
fig.update_layout(
    title=f"Per-metric short-vs-long growth (g) — top {len(universe_for_heat)} covered symbols, month-end snapshots",
)
save(fig, "02_per_metric_growth_heatmap", STEM, width=1500, height=900)

# %% Panel 3 — G vs F scatter (collinearity check)
# Recompute F at the latest date so we have something to scatter against
fees_d = panels["fees"]
rev_d = panels["revenue"]
mcaps = market_caps_wide()
fees_30 = fees_d.rolling(30, min_periods=10).mean()
rev_30 = rev_d.rolling(30, min_periods=10).mean()
fund_cashflow = fees_30 * 365 + 0.5 * rev_30 * 365
common_F = fund_cashflow.columns.intersection(mcaps.columns)
F = (fund_cashflow[common_F] / mcaps[common_F]).replace([np.inf, -np.inf], np.nan)
F = F.drop(columns=[c for c in F.columns if c in excl], errors="ignore")

G_latest_rank = G_score.iloc[-1].rank(ascending=False)
F_latest_rank = F.iloc[-1].rank(ascending=False)
sc_idx = G_latest_rank.dropna().index.intersection(F_latest_rank.dropna().index)
sc = pd.DataFrame({
    "symbol": sc_idx,
    "G_rank": G_latest_rank.loc[sc_idx].values,
    "F_rank": F_latest_rank.loc[sc_idx].values,
})
sc["cohort"] = sc["symbol"].map(sym_to_cohort)
spearman_GF = sc[["G_rank", "F_rank"]].corr(method="spearman").iloc[0, 1]

fig = px.scatter(
    sc,
    x="F_rank",
    y="G_rank",
    color="cohort",
    text="symbol",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title=f"G vs F independence — Spearman ρ = {spearman_GF:.2f} (close to 0 = adds new info)",
)
fig.update_traces(textposition="top center", textfont=dict(size=8))
fig.update_layout(xaxis_title="F rank (1=highest yield)",
                  yaxis_title="G rank (1=best activity-validated growth)")
save(fig, "03_G_vs_F_scatter", STEM, width=1200, height=900)

# %% Panel 4 — IC vs forward returns
# Run IC for both the full G_score AND the bare growth_score so we can see
# whether the price-mean-reversion subtraction is helping or hurting.
G_rank_panel = cross_sectional_rank(G_score, ascending=False)
growth_rank_panel = cross_sectional_rank(growth_score[common], ascending=False)
fwd = forward_returns(prices, horizons=(30, 60, 90))

ic_lines, summary_lines = [], []
for label, panel in [("G_score (growth-0.5·price)", G_rank_panel),
                     ("growth_score only", growth_rank_panel)]:
    for h, ret in fwd.items():
        ic = spearman_ic(-panel, ret)
        s = ic_summary(ic)
        summary_lines.append(
            f"{label:<28} h={h}d  mean IC={s['mean_ic']:+.3f}  IR={s['ir']:+.2f}  n={s['n']}"
        )
        ic_lines.append(pd.DataFrame({"date": ic.index, "ic": ic.values,
                                      "series": f"{label} | {h}d"}))

ic_df = pd.concat(ic_lines, ignore_index=True).dropna()
fig = px.line(
    ic_df,
    x="date",
    y="ic",
    color="series",
    color_discrete_sequence=px.colors.qualitative.Dark24,
    title="(G) Information coefficient — G_score vs growth-only, all horizons<br>"
          + "<br>".join(summary_lines),
)
fig.add_hline(y=0, line_dash="dot", line_color="grey")
fig.update_layout(yaxis_title="Spearman ρ (per day cross-section)")
save(fig, "04_G_information_coefficient", STEM, width=1300, height=620)

print("done.")
