"""02 — S factor: Supply Absorption (issuance pressure, crypto-native).

Economic intuition: in equities, the issuance factor (Pontiff & Woodgate
2008) is one of the most robust return predictors — firms that aggressively
issue new shares underperform. Crypto's analog is mechanical and observable:
emission schedules are public, vesting cliffs are visible, and FDV/Mcap
quantifies dilution overhang. Tokens absorbing new supply without proportional
dilution are in competitive equilibrium; tokens being diluted faster than the
market grows face structural headwinds.

Signal:
    implied_supply_t = market_cap_usd_t / price_usd_t
    emission_90d     = implied_supply_t / implied_supply_{t-90} - 1
    overhang_fdv     = (fdv - market_cap) / fdv
    S_score = -0.6 * z(emission_90d) - 0.4 * z(overhang_fdv)
    S_rank  = highest S_score → rank 1 (least dilutive)

Outputs:
    01_implied_supply_sanity.png    — line chart for known emitters
    02_emission_distribution.png    — violin by cohort
    03_emission_vs_overhang.png     — quadrant scatter
    04_S_information_coefficient.png — daily Spearman IC vs fwd 30/60/90d ret
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

# %% Load
excl = exclude_symbols()
master = universe_with_mcap()
sym_to_cohort = master.set_index("symbol")["cohort"].to_dict()
sym_to_mcap_now = master.set_index("symbol")["market_cap"].to_dict()
sym_to_fdv_now = master.set_index("symbol")["fdv"].to_dict()

prices = prices_wide()
mcaps = market_caps_wide()  # ffill built-in

# implied_supply matrix (date × symbol). NaN rows where price=0 or NaN.
implied = (mcaps / prices).replace([np.inf, -np.inf], np.nan)
implied = implied.drop(columns=[c for c in implied.columns if c in excl], errors="ignore")
print(f"implied-supply panel: {implied.shape}")

# %% Panel 1 — sanity check on known emitters/non-emitters
sanity_syms = [s for s in ["BTC", "ETH", "SOL", "BNB", "ADA", "AVAX", "ARB", "OP"]
               if s in implied.columns]
sanity = implied[sanity_syms].copy()
# Normalise to 1.0 at first non-null obs per symbol so % growth is comparable
norm = sanity.divide(sanity.bfill().iloc[0])

melt = norm.reset_index().melt(id_vars="date", var_name="symbol", value_name="supply_norm")
fig = px.line(
    melt,
    x="date",
    y="supply_norm",
    color="symbol",
    color_discrete_sequence=px.colors.qualitative.Dark24,
    title="Implied circulating supply (back-out from market_cap / price), normalised at t0<br>"
          "Sanity check — BTC should drift up ~3% / yr, ETH ~flat post-merge, ARB/OP step at unlocks",
)
fig.update_layout(yaxis_title="implied supply, indexed (1.0 = first obs)")
save(fig, "01_implied_supply_sanity", STEM, width=1300, height=620)

# %% Build factor inputs at the latest date
latest_date = implied.index[-1]
latest_supply = implied.iloc[-1]
lookback = 90
if len(implied) > lookback:
    past_supply = implied.iloc[-lookback - 1]
else:
    past_supply = implied.iloc[0]

emission_90 = (latest_supply / past_supply) - 1.0
emission_90 = emission_90.replace([np.inf, -np.inf], np.nan)

overhang = pd.Series({
    s: (sym_to_fdv_now[s] - sym_to_mcap_now[s]) / sym_to_fdv_now[s]
    if pd.notna(sym_to_fdv_now.get(s)) and pd.notna(sym_to_mcap_now.get(s)) and sym_to_fdv_now[s] > 0
    else np.nan
    for s in implied.columns
})
overhang = overhang.clip(lower=0)  # negative overhang means snapshot mismatch — clip

# %% Panel 2 — emission_90d distribution by cohort
df2 = pd.DataFrame({"symbol": emission_90.index, "emission_90d": emission_90.values})
df2["cohort"] = df2["symbol"].map(sym_to_cohort)
df2 = df2.dropna(subset=["cohort", "emission_90d"])
# Cap absolute extremes for the violin (data revisions can produce ±100% jumps)
df2["emission_90d_clip"] = df2["emission_90d"].clip(lower=-0.5, upper=1.0)

fig = px.violin(
    df2,
    x="cohort",
    y="emission_90d_clip",
    color="cohort",
    box=True,
    points="all",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    hover_name="symbol",
    title=f"90-day implied-supply growth by cohort — {len(df2)} symbols (clipped to ±100%)",
)
fig.add_hline(y=0, line_dash="dot", line_color="grey")
fig.update_layout(yaxis_title="implied supply growth, 90d", showlegend=False)
save(fig, "02_emission_distribution", STEM, width=1100, height=620)

# %% Panel 3 — emission vs FDV overhang scatter
df3 = (
    pd.DataFrame({"emission_90d": emission_90, "overhang_fdv": overhang})
    .reset_index().rename(columns={"index": "symbol"})
)
df3["cohort"] = df3["symbol"].map(sym_to_cohort)
df3["mcap"] = df3["symbol"].map(sym_to_mcap_now)
df3 = df3.dropna(subset=["emission_90d", "overhang_fdv", "cohort", "mcap"])

fig = px.scatter(
    df3,
    x="emission_90d",
    y="overhang_fdv",
    color="cohort",
    size="mcap",
    text="symbol",
    color_discrete_sequence=px.colors.qualitative.__dict__[QUAL],
    title="Realised emission (90d) vs forward dilution overhang (FDV-Mcap)/FDV<br>"
          "Top-right quadrant = both already issuing AND huge unissued float = avoid",
)
fig.update_traces(textposition="top center", textfont=dict(size=8))
fig.add_vline(x=0, line_dash="dot", line_color="grey")
fig.add_hline(y=df3["overhang_fdv"].median(), line_dash="dot", line_color="grey",
              annotation_text=f"median overhang={df3['overhang_fdv'].median():.2f}")
fig.update_layout(xaxis_title="emission_90d (Δ implied circulating supply)",
                  yaxis_title="overhang_fdv = (FDV-Mcap)/FDV")
save(fig, "03_emission_vs_overhang", STEM, width=1300, height=900)

# %% Panel 4 — Information coefficient
# Build daily S_score panel using rolling 90d implied-supply growth.
# Overhang we approximate with the LATEST snapshot (FDV is reported as a current
# field only). This is a known limitation: overhang is constant over the window.
emission_90_panel = (implied / implied.shift(lookback)) - 1.0
emission_z = (emission_90_panel.sub(emission_90_panel.mean(axis=1), axis=0)
              .div(emission_90_panel.std(axis=1), axis=0))
overhang_z = (overhang - overhang.mean()) / overhang.std()
# Broadcast overhang z across all dates (constant per asset). Assets without an
# FDV cap (BTC, ETH, USDT) get a neutral z=0 so the IC test isn't starved of
# observations — they contribute via emission only.
overhang_z_filled = overhang_z.fillna(0.0)
overhang_z_panel = pd.DataFrame(
    np.tile(overhang_z_filled.values, (len(emission_z), 1)),
    index=emission_z.index, columns=emission_z.columns
)
S_score = (-0.6 * emission_z).add(-0.4 * overhang_z_panel, fill_value=0.0)

# Rank descending — highest score = rank 1 = least dilutive
S_rank = cross_sectional_rank(S_score, ascending=False)

fwd = forward_returns(prices, horizons=(30, 60, 90))
ic_lines, summary_lines = [], []
for h, ret in fwd.items():
    ic = spearman_ic(-S_rank, ret)
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
    title="(S) Information coefficient — daily Spearman ρ vs forward returns<br>"
          + "<br>".join(summary_lines),
)
fig.add_hline(y=0, line_dash="dot", line_color="grey")
fig.update_layout(yaxis_title="Spearman ρ (per day cross-section)")
save(fig, "04_S_information_coefficient", STEM, width=1300, height=620)

print("done.")
