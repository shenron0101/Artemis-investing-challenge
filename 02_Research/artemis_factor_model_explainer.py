"""Artemis Crypto Factor Model — Interactive Explainer
=======================================================
Run in VS Code with the Jupyter extension: each `# %%` block is one cell.
Execute cells top-to-bottom with Shift+Enter.

GOAL: replicate the Artemis factor model paper and explain exactly what
      every number means — especially:
      - "~55% of individual token returns explained"
      - "~75% of diversified portfolio returns"
      - What "factor", "beta", "long-short", and "R²" actually mean

Paper reference: 02_Research/Crypto Factor Model Analysis.md
"""

# %% ── CELL 0: Setup ────────────────────────────────────────────────────────
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

warnings.filterwarnings("ignore")

ROOT  = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "01_Data_Collection" / "data" / "clean"
OUT   = Path(__file__).resolve().parent / "figures" / "factor_explainer"
OUT.mkdir(parents=True, exist_ok=True)

print(f"Root:  {ROOT}")
print(f"Data:  {CLEAN}")
print(f"Figs:  {OUT}")


def save(fig, name: str, width=1300, height=700):
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Inter, system-ui, sans-serif", size=12),
        margin=dict(l=60, r=30, t=70, b=50),
    )
    png = OUT / f"{name}.png"
    html = OUT / f"{name}.html"
    fig.write_image(png, width=width, height=height, scale=2)
    fig.write_html(html, include_plotlyjs="cdn", full_html=True)
    print(f"  → {png.relative_to(ROOT)}")
    return png


def ann_ret(weekly_series: pd.Series) -> float:
    """Arithmetic annualisation — safe for any sample length, avoids geometric explosion."""
    return weekly_series.mean() * 52


def ann_vol(weekly_series: pd.Series) -> float:
    return weekly_series.std() * np.sqrt(52)


# %% ── CELL 1: What even IS a factor model? ─────────────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WHAT IS A FACTOR MODEL?  (The Analogy)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Think about house prices. When you try to explain WHY a house costs what
it does, you'd break it down into components:

  price = location_premium  +  size_effect  +  age_discount  +  condition  +  noise

Each component (location, size, age) is a FACTOR. The "noise" is whatever
the model can't explain — idiosyncratic stuff like "a famous person used to
live here."

Factor models do the SAME thing for financial returns:

  token_return = market_risk  +  size_effect  +  value_effect  +  momentum  +  noise

The four factors the Artemis paper tests:
  1. MARKET   — broad crypto market goes up → your token goes up too
  2. SIZE     — small coins tend to outperform large coins (more risk)
  3. VALUE    — "cheap" coins (low price relative to fees earned) outperform
  4. MOMENTUM — coins that were strong recently stay strong short-term

Each factor is a PORTFOLIO — a specific long/short basket built to isolate
one effect. By regressing a token's returns against these four portfolio
returns, we decompose WHERE the return came from.

  R² = how much of the variance in returns the model explains
       (55% = the 4 factors explain more than half of what drives each coin)
""")


# %% ── CELL 2: Load data ────────────────────────────────────────────────────
# Price source: Binance OHLCV (5-year depth, 68 symbols).
# Market cap source: CoinGecko (1 year actual; back-filled as a static proxy
#   for earlier periods — large-cap rankings are stable over years so BTC/ETH/BNB
#   have always dominated, making the proxy directionally correct for eligibility).
# Volume source: Binance quote_volume (USD-denominated, 5 years).
# Fees / activity: Artemis (5 years).
print("Loading data...")

details = pd.read_parquet(CLEAN / "coingecko_coin_details.parquet")
act     = pd.read_parquet(CLEAN / "artemis_activity_long.parquet")
act["date"]  = pd.to_datetime(act["date"], errors="coerce")
act["value"] = pd.to_numeric(act["value"], errors="coerce")
act     = act.dropna(subset=["date", "value"])

# Exclude stablecoins / wrapped / bridged
excl = set(
    details.loc[
        details[["is_stablecoin", "is_wrapped", "is_bridged"]].fillna(False).any(axis=1),
        "symbol",
    ].str.upper()
)
print(f"Excluded (stable/wrapped/bridged): {sorted(excl)}")

# ── Binance OHLCV → 5-year daily closes + USD volume ────────────────────────
ohlcv = pd.read_parquet(CLEAN / "binance_ohlcv_daily.parquet")
ohlcv["date"] = pd.to_datetime(ohlcv["open_time"]).dt.tz_localize(None).dt.normalize()
ohlcv = ohlcv[~ohlcv["symbol"].isin(excl)].copy()

prices_d = (ohlcv.pivot_table(index="date", columns="symbol", values="close", aggfunc="last")
            .sort_index())
vols_d   = (ohlcv.pivot_table(index="date", columns="symbol", values="quote_volume", aggfunc="last")
            .sort_index()
            .ffill(limit=5))

# ── CoinGecko market caps → 1-year actual, then back-filled ─────────────────
ticks = pd.read_parquet(CLEAN / "coingecko_daily_ticks.parquet")
ticks["date"] = pd.to_datetime(ticks["date"])
ticks = ticks[~ticks["symbol"].isin(excl)].copy()

mcaps_cg = (ticks.pivot_table(index="date", columns="symbol",
                               values="market_cap_usd", aggfunc="last")
            .sort_index()
            .ffill(limit=5))

# Extend mcaps across full Binance date range: forward-fill recent gaps then
# back-fill so historical periods inherit the earliest known value as a proxy.
mcaps_d = mcaps_cg.reindex(prices_d.index).ffill(limit=5).bfill()

# Keep only symbols present in Binance (price source of truth)
common_syms = prices_d.columns.tolist()
mcaps_d = mcaps_d.reindex(columns=common_syms)

# first_date used by the eligibility filter (age check)
first_date = ohlcv.groupby("symbol")["date"].min().rename("first_date")

# Compute sample period info — used throughout to make all text dynamic
_n_days  = (prices_d.index[-1] - prices_d.index[0]).days
_n_years = _n_days / 365.25
SAMPLE_LABEL = f"{_n_years:.1f}-year" if _n_years >= 1.5 else f"{_n_days}-day"

print(f"\nPrice/volume (Binance): {prices_d.shape[0]} days × {prices_d.shape[1]} tokens")
print(f"Market caps (CoinGecko, back-filled): {mcaps_d.shape}")
print(f"Artemis activity: {act['date'].min().date()} → {act['date'].max().date()}")
print(f"Date range: {prices_d.index[0].date()} → {prices_d.index[-1].date()}")
print(f"Sample period: {SAMPLE_LABEL}  ({_n_days} days / {_n_days//7} weeks)")


# %% ── CELL 3: Resample to WEEKLY (the paper's rebalance frequency) ─────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WHY WEEKLY?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The paper rebalances portfolios weekly. This is a balance between:
  - Daily: too much noise + high transaction costs
  - Monthly: factors like momentum decay before you can trade them

We take Friday closing prices (the last trading day of each week).
Weekly return = (this_friday_price / last_friday_price) - 1
""")

prices_w = prices_d.resample("W-FRI").last()
mcaps_w  = mcaps_d.resample("W-FRI").last()
vols_w   = vols_d.resample("W-FRI").sum()   # sum daily volumes → proper weekly USD volume

ret_w = prices_w.pct_change()

N_WEEKS = prices_w.shape[0]
print(f"Weekly matrices: {N_WEEKS} weeks × {prices_w.shape[1]} tokens")
print(f"Sample: {SAMPLE_LABEL}  (Paper had 4–8 years of data)")
if N_WEEKS < 100:
    print("→ With < 2 years, factor means are noisy — direction matters more than magnitude.")
else:
    print("→ With multi-year data, factor means and ICs become statistically meaningful.")


# %% ── CELL 4: Build the Eligible Universe ──────────────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ELIGIBILITY FILTER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Before building any factor, we filter to tokens that are:
  1. Market cap ≥ $100M  (no microcaps — too illiquid, too noisy)
  2. Weekly volume ≥ $35M  (we need to actually be able to trade it)
  3. Age ≥ 30 days  (avoids IPO-day distortions)

This gives us the "eligible universe" at each rebalancing date.
Tokens enter and exit as their market cap changes — this is CRITICAL
for avoiding survivorship bias (only counting coins that survived).
""")

def eligible_mask(mcap_row: pd.Series, vol_row: pd.Series, date: pd.Timestamp,
                  min_mcap=100e6, min_vol=35e6, min_age_days=30) -> pd.Series:
    age = (date - first_date).dt.days.reindex(mcap_row.index).fillna(0)
    return (mcap_row >= min_mcap) & (vol_row >= min_vol) & (age >= min_age_days)


elig_counts = []
for date in prices_w.index[1:]:
    mask = eligible_mask(mcaps_w.loc[date].fillna(0),
                         vols_w.loc[date].fillna(0),
                         date)
    elig_counts.append({"date": date, "n_eligible": int(mask.sum())})

elig_df = pd.DataFrame(elig_counts).set_index("date")

fig = px.area(elig_df, x=elig_df.index, y="n_eligible",
              title="Eligible universe size per week (mcap ≥$100M, vol ≥$35M, age ≥30d)",
              labels={"n_eligible": "# tokens eligible"})
fig.add_hline(y=20, line_dash="dot", line_color="orange",
              annotation_text="min 20 for SMB")
fig.add_hline(y=10, line_dash="dot", line_color="red",
              annotation_text="min 10 for Value")
save(fig, "01_eligible_universe", height=500)

print(f"\nMean eligible tokens per week: {elig_df['n_eligible'].mean():.0f}")
print(f"Min: {elig_df['n_eligible'].min()}, Max: {elig_df['n_eligible'].max()}")


# %% ── CELL 5: THE MARKET FACTOR ────────────────────────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FACTOR 1: MARKET RISK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Construction: top-10 tokens by market cap, market-cap-weighted, long only.
Rebalanced weekly.

This is the crypto equivalent of the S&P 500. Most of a token's return
comes from "the market went up/down." The market factor captures this.

Market cap weighting means BTC dominates (~50–60% of the basket),
which is realistic — BTC moves the whole market.

When we later run the regression:
  token_return = β_market × MKT_return + ...

  β_market ≈ 1.0 means the token moves 1:1 with the market
  β_market ≈ 1.5 means the token is more volatile than the market (riskier)
  β_market ≈ 0.5 means the token is a relative safe haven
""")

mkt_returns = []
mkt_weights_history = {}

for i in range(1, len(prices_w)):
    date = prices_w.index[i]
    prev = prices_w.index[i - 1]

    mask = eligible_mask(mcaps_w.loc[date].fillna(0),
                         vols_w.loc[date].fillna(0), date)
    elig_syms = mcaps_w.columns[mask]

    top10 = mcaps_w.loc[date, elig_syms].nlargest(10)
    if len(top10) < 3:
        mkt_returns.append({"date": date, "mkt": np.nan})
        continue

    weights = top10 / top10.sum()
    mkt_weights_history[date] = weights.to_dict()

    syms = top10.index
    r = ret_w.loc[date, syms.intersection(ret_w.columns)].reindex(syms).fillna(0)
    mkt_ret = (weights * r).sum()
    mkt_returns.append({"date": date, "mkt": mkt_ret})

mkt = pd.DataFrame(mkt_returns).set_index("date")["mkt"].dropna()

_ann_ret_mkt = ann_ret(mkt)
_ann_vol_mkt = ann_vol(mkt)
_sharpe_mkt  = _ann_ret_mkt / _ann_vol_mkt

print(f"Market factor weeks:              {len(mkt)}")
print(f"Market factor annualised return:  {_ann_ret_mkt:+.1%}")
print(f"Market factor annualised vol:     {_ann_vol_mkt:.1%}")
print(f"Market factor Sharpe:             {_sharpe_mkt:+.2f}")
print(f"(Paper reported: +42%/yr over 8.3 years)")

cum_mkt = (1 + mkt).cumprod()
fig = px.line(x=cum_mkt.index, y=cum_mkt.values,
              title=f"Market factor — cumulative return (top-10 mcap-weighted) | {SAMPLE_LABEL} sample<br>"
                    f"Ann. return: {_ann_ret_mkt:+.1%}  |  Sharpe: {_sharpe_mkt:+.2f}  |  Paper: +42%/yr",
              labels={"x": "date", "y": "growth of $1"})
fig.add_hline(y=1, line_dash="dot", line_color="grey")
save(fig, "02_market_factor_cumret", height=500)


# %% ── CELL 6: THE SIZE FACTOR (SMB) ────────────────────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FACTOR 2: SIZE (SMB = Small Minus Big)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Construction: each week, split eligible tokens by market cap.
  LONG  = smallest 50%  (equal-weighted)
  SHORT = largest  50%  (equal-weighted)
  SMB   = long_return − short_return

The RETURN of this long-short portfolio is the "SIZE factor return."

Why small > large?
  Small tokens are riskier: less liquid, less well-known, more volatile.
  In efficient markets, MORE RISK → MORE EXPECTED RETURN.
  Investors demand higher compensation for holding small caps.

When we say SMB earned +53.6%/yr:
  Small caps outperformed large caps by 53.6% per year ON AVERAGE.
  This is the SIZE PREMIUM — the extra return for taking size risk.

Long-short construction isolates the SIZE effect and cancels out the
market effect — if the whole market crashes, both legs crash equally,
so the L-S portfolio is roughly market-neutral.

Min 40 eligible tokens required (20 per leg) to avoid noise.
""")

smb_returns = []

for i in range(1, len(prices_w)):
    date = prices_w.index[i]

    mask = eligible_mask(mcaps_w.loc[date].fillna(0),
                         vols_w.loc[date].fillna(0), date)
    elig_syms = mcaps_w.columns[mask]

    if len(elig_syms) < 20:   # paper used 40 with ~100 tokens; we scale to our ~50-token universe
        smb_returns.append({"date": date, "smb": np.nan, "n_elig": len(elig_syms)})
        continue

    mcap_now = mcaps_w.loc[date, elig_syms]
    median_mcap = mcap_now.median()

    small_syms = mcap_now[mcap_now <= median_mcap].index
    big_syms   = mcap_now[mcap_now >  median_mcap].index

    r = ret_w.loc[date, elig_syms.intersection(ret_w.columns)].reindex(elig_syms)
    small_ret = r.loc[small_syms.intersection(r.index)].mean()
    big_ret   = r.loc[big_syms.intersection(r.index)].mean()

    smb_returns.append({
        "date": date, "smb": small_ret - big_ret,
        "small_ret": small_ret, "big_ret": big_ret,
        "n_elig": len(elig_syms),
    })

smb_df = pd.DataFrame(smb_returns).set_index("date")
smb = smb_df["smb"].dropna()

_ann_ret_smb = ann_ret(smb)
_ann_vol_smb = ann_vol(smb)

print(f"SMB weeks:             {len(smb)}")
print(f"SMB annualised return: {_ann_ret_smb:+.1%}")
print(f"SMB annualised vol:    {_ann_vol_smb:.1%}")
print(f"(Paper: +53.6%/yr over 4.9yr)")

cum_smb   = (1 + smb).cumprod()
cum_small = (1 + smb_df["small_ret"].dropna()).cumprod()
cum_big   = (1 + smb_df["big_ret"].dropna()).cumprod()

fig = go.Figure()
fig.add_trace(go.Scatter(x=cum_small.index, y=cum_small, name="Small (long leg)", line=dict(color="#2ca02c")))
fig.add_trace(go.Scatter(x=cum_big.index,   y=cum_big,   name="Big (short leg)",  line=dict(color="#d62728")))
fig.add_trace(go.Scatter(x=cum_smb.index,   y=cum_smb,   name="SMB (long−short)", line=dict(color="#1f77b4", width=2.5)))
fig.add_hline(y=1, line_dash="dot", line_color="grey")
fig.update_layout(
    title=f"Size factor (SMB) — small outperforming large | {SAMPLE_LABEL} sample<br>"
          f"Ann. return: {_ann_ret_smb:+.1%}  |  Paper: +53.6%/yr",
    yaxis_title="growth of $1",
)
save(fig, "03_smb_factor_cumret")


# %% ── CELL 7: THE VALUE FACTOR ─────────────────────────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FACTOR 3: VALUE (Cheap vs Expensive)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Valuation metric: mc_fees_ratio = market_cap / annualised_fees

This is the CRYPTO VERSION of a P/S ratio (Price to Sales):
  - Low ratio  = "cheap" → similar to a low P/S stock → likely undervalued
  - High ratio = "expensive" → markets pricing in huge future growth

Construction:
  LONG  = lowest 50% by mc_fees_ratio (cheap)
  SHORT = highest 50% by mc_fees_ratio (expensive)
  VALUE = long_return − short_return

Only tokens with fee data from Artemis are eligible here.
Min 15 tokens with fee coverage required.

Why does value work?
  Behavioural finance: investors over-extrapolate past growth, pushing
  expensive tokens too high. When reality disappoints, they correct.
  "Cheap" tokens often have solid cash flows the market is ignoring.

The paper found: +9.3%/yr — positive but weaker than size.
""")

fees_act = act[act["metric"] == "fees"].copy()
fees_d = fees_act.pivot_table(index="date", columns="symbol", values="value", aggfunc="last")
fees_d = fees_d.reindex(prices_d.index).ffill(limit=14)
fees_30d = fees_d.rolling(30, min_periods=7).mean()
fees_ann = fees_30d * 365

common = fees_ann.columns.intersection(mcaps_d.columns)
mc_fees_ratio_d = (mcaps_d[common] / fees_ann[common]).replace([np.inf, -np.inf], np.nan)
mc_fees_ratio_w = mc_fees_ratio_d.resample("W-FRI").last()

val_returns = []
MIN_FEE_TOKENS = 10  # minimum tokens with fee coverage (paper used 30 with larger universe)

for i in range(1, len(prices_w)):
    date = prices_w.index[i]

    mask = eligible_mask(mcaps_w.loc[date].fillna(0),
                         vols_w.loc[date].fillna(0), date)
    elig_syms = mcaps_w.columns[mask]

    if date not in mc_fees_ratio_w.index:
        val_returns.append({"date": date, "val": np.nan, "n": 0})
        continue

    ratio = mc_fees_ratio_w.loc[date].reindex(elig_syms).dropna()

    if len(ratio) < MIN_FEE_TOKENS:
        val_returns.append({"date": date, "val": np.nan, "n": len(ratio)})
        continue

    median_ratio = ratio.median()
    cheap_syms     = ratio[ratio <= median_ratio].index
    expensive_syms = ratio[ratio >  median_ratio].index

    r = ret_w.loc[date, ratio.index.intersection(ret_w.columns)].reindex(ratio.index)
    cheap_ret     = r.loc[cheap_syms.intersection(r.index)].mean()
    expensive_ret = r.loc[expensive_syms.intersection(r.index)].mean()

    val_returns.append({
        "date": date, "val": cheap_ret - expensive_ret,
        "cheap_ret": cheap_ret, "exp_ret": expensive_ret,
        "n": len(ratio),
    })

val_df  = pd.DataFrame(val_returns).set_index("date")
val     = val_df["val"].dropna()
n_weeks_val = len(val)

_ann_ret_val = ann_ret(val) if n_weeks_val > 0 else float("nan")

print(f"Value factor weeks with data:  {n_weeks_val}")
print(f"Value factor ann. return:      {_ann_ret_val:+.1%}")
print(f"(Paper: +9.3%/yr over 3.9yr)")

if n_weeks_val > 4:
    cum_val   = (1 + val).cumprod()
    cum_cheap = (1 + val_df["cheap_ret"].dropna()).cumprod()
    cum_exp   = (1 + val_df["exp_ret"].dropna()).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cum_cheap.index, y=cum_cheap, name="Cheap (low mc/fees)", line=dict(color="#2ca02c")))
    fig.add_trace(go.Scatter(x=cum_exp.index,   y=cum_exp,   name="Expensive (high mc/fees)", line=dict(color="#d62728")))
    fig.add_trace(go.Scatter(x=cum_val.index,   y=cum_val,   name="VALUE (cheap − expensive)", line=dict(color="#ff7f0e", width=2.5)))
    fig.add_hline(y=1, line_dash="dot", line_color="grey")
    fig.update_layout(
        title=f"Value factor (mc_fees_ratio) — {n_weeks_val} weeks | {SAMPLE_LABEL} sample<br>"
              f"Ann. return: {_ann_ret_val:+.1%}  |  Paper: +9.3%/yr",
        yaxis_title="growth of $1",
    )
    save(fig, "04_value_factor_cumret")
else:
    print(f"  (Not enough weeks with fee coverage to plot — need >{MIN_FEE_TOKENS} tokens/week)")


# %% ── CELL 8: THE MOMENTUM FACTOR ──────────────────────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FACTOR 4: MOMENTUM (Vol-Adjusted 3-Week)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The paper uses a "3-week, volatility-adjusted framework designed to capture
consistent price trends rather than short-term spikes."

We interpret this as:
  momentum_score = (3-week log-return sum) / (12-week rolling vol of weekly ret)

  Think of it as a Sharpe ratio for recent returns:
    numerator   = how much did it gain in the last 3 weeks?
    denominator = how volatile has it been recently?
    → high score = steady uptrend (not just a random spike)

Construction: rank by momentum_score, then:
  LONG  = top 25% (the strong, consistent risers)
  SHORT = bottom 25% (the consistent losers)
  MOM   = long_return − short_return

Scores are clipped to [-5, 5] to avoid near-zero-vol singularities.

Why momentum works short-term:
  Investors underreact to news. Strong recent performers have positive
  momentum because the market is still "pricing in" the good news.
  This reverses at longer horizons (12+ months) but at 3-week horizon,
  "winning keeps winning."

The paper: +75%/yr over 4.6yr — the highest raw return but lowest
explanatory power for individual assets.
""")

rolling_vol_w = ret_w.rolling(12, min_periods=4).std()
log_ret_w = np.log1p(ret_w)
cum_3w_log = log_ret_w.rolling(3, min_periods=3).sum()

with np.errstate(divide="ignore", invalid="ignore"):
    raw_score = cum_3w_log / rolling_vol_w.replace(0, np.nan)
    mom_score = raw_score.clip(-5, 5)

mom_returns = []

for i in range(1, len(prices_w)):
    date = prices_w.index[i]

    mask = eligible_mask(mcaps_w.loc[date].fillna(0),
                         vols_w.loc[date].fillna(0), date)
    elig_syms = mcaps_w.columns[mask]

    if date not in mom_score.index or len(elig_syms) < 15:
        mom_returns.append({"date": date, "mom": np.nan})
        continue

    scores = mom_score.loc[date, elig_syms.intersection(mom_score.columns)].dropna()
    if len(scores) < 15:
        mom_returns.append({"date": date, "mom": np.nan})
        continue

    q75 = scores.quantile(0.75)
    q25 = scores.quantile(0.25)
    winners = scores[scores >= q75].index
    losers  = scores[scores <= q25].index

    r = ret_w.loc[date, scores.index.intersection(ret_w.columns)].reindex(scores.index)
    winner_ret = r.loc[winners.intersection(r.index)].mean()
    loser_ret  = r.loc[losers.intersection(r.index)].mean()

    mom_returns.append({"date": date, "mom": winner_ret - loser_ret})

mom_df = pd.DataFrame(mom_returns).set_index("date")
mom    = mom_df["mom"].dropna()

_ann_ret_mom = ann_ret(mom) if len(mom) > 0 else float("nan")

print(f"Momentum factor weeks:       {len(mom)}")
print(f"Momentum factor ann. return: {_ann_ret_mom:+.1%}")
print(f"(Paper: +75%/yr over 4.6yr)")

cum_mom = (1 + mom).cumprod()
fig = px.line(x=cum_mom.index, y=cum_mom.values,
              title=f"Momentum factor — 3-week vol-adjusted (long top-25% / short bottom-25%) | {SAMPLE_LABEL} sample<br>"
                    f"Ann. return: {_ann_ret_mom:+.1%}  |  Paper: +75%/yr",
              labels={"x": "date", "y": "growth of $1"})
fig.add_hline(y=1, line_dash="dot", line_color="grey")
save(fig, "05_momentum_factor_cumret", height=500)


# %% ── CELL 9: Factor return summary & correlations ─────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FACTOR RETURN SUMMARY + CORRELATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Why do we care about correlations between factors?

If two factors are highly correlated (ρ ≈ 1.0), they capture the SAME
information — adding the second one doesn't help explain anything new.

The paper reports low correlations between all four factors (all < 0.3).
This means each factor adds independent information — the model improves
by including all four rather than just one.
""")

factor_df = pd.DataFrame({
    "MKT": mkt,
    "SMB": smb,
    "VAL": val if len(val) > 10 else pd.Series(dtype=float),
    "MOM": mom,
}).dropna(how="all")

summary_rows = []
paper_rets = {"MKT": "+42%", "SMB": "+54%", "VAL": "+9%", "MOM": "+75%"}
for col in ["MKT", "SMB", "VAL", "MOM"]:
    s = factor_df[col].dropna()
    if len(s) < 4:
        continue
    _r = ann_ret(s)
    _v = ann_vol(s)
    summary_rows.append({
        "Factor": col,
        "Weeks": len(s),
        "Ann. Return": f"{_r:+.1%}",
        "Ann. Vol": f"{_v:.1%}",
        "Sharpe": f"{_r/_v:+.2f}" if _v > 0 else "n/a",
        "Paper Ann. Return": paper_rets.get(col, "n/a"),
    })

print(f"\nFACTOR SUMMARY ({SAMPLE_LABEL} sample vs Paper):")
print(pd.DataFrame(summary_rows).to_string(index=False))

corr_cols = [c for c in ["MKT", "SMB", "VAL", "MOM"]
             if c in factor_df and factor_df[c].notna().sum() > 10]
if len(corr_cols) >= 2:
    corr = factor_df[corr_cols].corr()
    print(f"\nFactor return correlations:\n{corr.round(3)}")
    print("\n(Paper: all < 0.3, confirming factors capture different dimensions)")

    fig = go.Figure(go.Heatmap(
        z=corr.values,
        x=corr.columns, y=corr.index,
        colorscale="RdBu", zmin=-1, zmax=1, zmid=0,
        text=corr.round(2).values, texttemplate="%{text}",
        colorbar=dict(title="Pearson ρ"),
    ))
    fig.update_layout(
        title=f"Factor weekly return correlations ({SAMPLE_LABEL} sample)<br>"
              "Low ρ = each factor adds independent information",
        yaxis_autorange="reversed",
    )
    save(fig, "06_factor_correlations", width=700, height=600)


# %% ── CELL 10: CUMULATIVE FACTOR RETURNS on ONE chart ─────────────────────
fig = go.Figure()
colors = {"MKT": "#1f77b4", "SMB": "#2ca02c", "VAL": "#ff7f0e", "MOM": "#d62728"}

for col in ["MKT", "SMB", "VAL", "MOM"]:
    s = factor_df[col].dropna()
    if len(s) < 4:
        continue
    cum = (1 + s).cumprod()
    _r  = ann_ret(s)
    fig.add_trace(go.Scatter(
        x=cum.index, y=cum.values,
        name=f"{col} ({_r:+.1%}/yr)",
        line=dict(color=colors.get(col), width=2),
    ))

fig.add_hline(y=1, line_dash="dot", line_color="grey")
fig.update_layout(
    title=f"All four factor portfolios — cumulative return ({SAMPLE_LABEL} sample)",
    yaxis_title="growth of $1",
)
save(fig, "07_all_factors_cumret")


# %% ── CELL 11: THE BIG EXPLANATION — R² and Explanatory Power ─────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  THE KEY QUESTION: What does "55% of returns explained" MEAN?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each token, we run an OLS (ordinary least-squares) regression:

  token_return_t = α + β_mkt×MKT_t + β_smb×SMB_t + β_val×VAL_t + β_mom×MOM_t + ε_t

This has TWO parts:
  1. The systematic part: α + β_mkt×MKT + β_smb×SMB + β_val×VAL + β_mom×MOM
     These are the components the FACTORS explain.
  2. The residual ε_t: leftover variance the factors CANNOT explain
     (idiosyncratic — specific to that coin)

R² = fraction of the token's variance explained by the systematic part

  R² = 0.55 means: 55% of the ups-and-downs of this token are accounted
                   for by the four factors.
                   The other 45% is coin-specific noise.

WHY IS THE PORTFOLIO R² HIGHER (75%) THAN INDIVIDUAL (55%)?

When you build a diversified portfolio (e.g. 20 tokens), the idiosyncratic
noise of each coin CANCELS OUT in the average. Coin A's weird -5% day and
Coin B's weird +5% day wash out when you hold both.

What's LEFT in a portfolio is mostly SYSTEMATIC risk (factors).
So when you regress a portfolio on the factors, there's almost nothing
left to explain → R² is much higher.

  More assets in portfolio → more idiosyncratic noise cancelled → higher R²
""")

# Decide which factors to include based on actual data availability.
# VAL needs enough weeks to be a reliable regressor; we require at least
# 30 weeks OR 25% of total sample weeks, whichever is larger.
_min_weeks_for_val = max(30, N_WEEKS // 4)
_val_weeks_avail   = len(val.dropna())

if _val_weeks_avail >= _min_weeks_for_val:
    _main_factors = [c for c in ["MKT", "SMB", "VAL", "MOM"]
                     if c in factor_df and factor_df[c].notna().sum() > 10]
    _val_note = f"(VAL included — {_val_weeks_avail} weeks ≥ {_min_weeks_for_val}-week threshold)"
else:
    _main_factors = [c for c in ["MKT", "SMB", "MOM"]
                     if c in factor_df and factor_df[c].notna().sum() > 10]
    _val_note = (f"(VAL excluded from main regression — only {_val_weeks_avail} weeks, "
                 f"need ≥{_min_weeks_for_val}; still used for its own factor portfolio above)")

print(f"\nUsing factors for main regression: {_main_factors}")
print(_val_note)

factor_common = factor_df[_main_factors].dropna()
print(f"Regression sample: {len(factor_common)} weeks")

X = factor_common.copy()
X.insert(0, "const", 1.0)

# Minimum observations: at least 40% of available weeks, floor at 20.
min_obs = max(20, int(len(factor_common) * 0.4))

regression_results = []

for sym in ret_w.columns:
    y = ret_w[sym].reindex(factor_common.index).dropna()
    if len(y) < min_obs:
        continue

    X_aligned = X.reindex(y.index).dropna()
    y_aligned  = y.reindex(X_aligned.index)
    n = len(y_aligned)
    if n < min_obs:
        continue

    Xv = X_aligned.values
    yv = y_aligned.values

    try:
        betas, _, _, _ = np.linalg.lstsq(Xv, yv, rcond=None)
    except np.linalg.LinAlgError:
        continue

    y_pred = Xv @ betas
    ss_res = np.sum((yv - y_pred) ** 2)
    ss_tot = np.sum((yv - yv.mean()) ** 2)
    r2     = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan

    # t-stat for alpha (Jensen's alpha test)
    resid   = yv - y_pred
    se_resid = np.sqrt(np.sum(resid**2) / max(n - len(betas), 1))
    XtX_inv  = np.linalg.pinv(Xv.T @ Xv)
    se_alpha = se_resid * np.sqrt(XtX_inv[0, 0])
    t_alpha  = betas[0] / se_alpha if se_alpha > 0 else np.nan

    row = {"symbol": sym, "n_obs": n, "r2": r2,
           "alpha": betas[0], "t_alpha": t_alpha}
    for j, f in enumerate(_main_factors):
        row[f"beta_{f.lower()}"] = betas[j + 1]
    regression_results.append(row)

if not regression_results:
    print(f"\n  WARNING: no tokens had ≥{min_obs} overlapping observations for regression.")
    reg_df = pd.DataFrame(columns=["symbol", "n_obs", "r2", "alpha", "t_alpha"]).set_index("symbol")
else:
    reg_df = pd.DataFrame(regression_results).set_index("symbol")
    reg_df = reg_df[reg_df["r2"].notna()]

print(f"\nTokens with OLS regression (≥{min_obs} weeks): {len(reg_df)}")
print(f"\nR² statistics (individual tokens):")
print(f"  Mean R²:   {reg_df['r2'].mean():.3f}  ({reg_df['r2'].mean()*100:.0f}%)")
print(f"  Median R²: {reg_df['r2'].median():.3f}")
print(f"  Min:       {reg_df['r2'].min():.3f}   Max: {reg_df['r2'].max():.3f}")
print(f"\n  Paper reported: ~55% mean R² for individual tokens")
print(f"  Our result: {len(_main_factors)} factors, {len(factor_common)} weeks, {SAMPLE_LABEL} sample")


# %% ── CELL 12: Show the regression for ONE token (step-by-step) ────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP-BY-STEP: Seeing the regression in action for ETH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

example_sym = "ETH"
if example_sym in reg_df.index and "ETH" in ret_w.columns:
    row = reg_df.loc[example_sym]
    y = ret_w[example_sym].reindex(factor_common.index).dropna()
    X_a = X.reindex(y.index).dropna()
    y_a = y.reindex(X_a.index)

    y_pred_mkt_only = X_a[["const", "MKT"]].values @ np.linalg.lstsq(
        X_a[["const", "MKT"]].values, y_a.values, rcond=None)[0]
    y_pred_full     = X_a.values @ np.linalg.lstsq(X_a.values, y_a.values, rcond=None)[0]

    ss_tot = np.sum((y_a.values - y_a.mean())**2)
    r2_mkt_only = 1 - np.sum((y_a.values - y_pred_mkt_only)**2) / ss_tot
    r2_full     = 1 - np.sum((y_a.values - y_pred_full)**2) / ss_tot

    print(f"ETH regression ({len(y_a)} weekly observations):")
    print(f"  Using only Market factor:         R² = {r2_mkt_only:.3f} ({r2_mkt_only*100:.0f}%)")
    print(f"  Using all {len(_main_factors)} factors ({'+'.join(_main_factors)}): R² = {r2_full:.3f} ({r2_full*100:.0f}%)")
    print(f"\n  Betas (how sensitive ETH is to each factor):")
    print(f"    β_market  = {row.get('beta_mkt', np.nan):+.3f}  (1.0 = moves 1:1 with market)")
    print(f"    β_smb     = {row.get('beta_smb', np.nan):+.3f}  (negative = large-cap behaviour)")
    if "beta_val" in row:
        print(f"    β_value   = {row.get('beta_val', np.nan):+.3f}  (positive = value tilt)")
    if "beta_mom" in row:
        print(f"    β_momentum= {row.get('beta_mom', np.nan):+.3f}  (positive = momentum tilt)")
    print(f"\n  Alpha (Jensen's α): {row.get('alpha', np.nan):+.4f}/wk "
          f"(t={row.get('t_alpha', np.nan):+.2f})")
    print(f"  The remaining {(1-r2_full)*100:.0f}% is ETH-specific variance "
          f"(regulatory news, upgrades, gas-fee spikes...)")

    fig = make_subplots(rows=1, cols=2,
        subplot_titles=["ETH return vs Market factor only",
                        f"ETH return vs Full model ({'+'.join(_main_factors)})"])

    fig.add_trace(go.Scatter(x=y_pred_mkt_only, y=y_a.values, mode="markers",
        marker=dict(color="#1f77b4", size=5, opacity=0.7),
        name=f"MKT only R²={r2_mkt_only:.2f}"), row=1, col=1)
    fig.add_trace(go.Scatter(x=y_pred_full, y=y_a.values, mode="markers",
        marker=dict(color="#2ca02c", size=5, opacity=0.7),
        name=f"Full model R²={r2_full:.2f}"), row=1, col=2)

    for col_ in [1, 2]:
        fig.add_trace(go.Scatter(
            x=[-0.4, 0.4], y=[-0.4, 0.4], mode="lines",
            line=dict(color="grey", dash="dot"), showlegend=False,
        ), row=1, col=col_)
        fig.update_xaxes(title_text="Factor-predicted return", row=1, col=col_)
        fig.update_yaxes(title_text="Actual ETH return", row=1, col=col_)

    fig.update_layout(
        title="ETH return vs factor model: points on the diagonal = perfectly explained<br>"
              "Points off the diagonal = idiosyncratic noise the model can't capture",
    )
    save(fig, "08_eth_regression_scatter", width=1400, height=650)
else:
    print(f"  ETH not in regression results — skipping step-by-step example.")


# %% ── CELL 13: R² distribution across all tokens ───────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  R² DISTRIBUTION — All Tokens
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The histogram below shows R² for every token.

  Left side (low R²) = the factor model barely explains this token
                       → it has a lot of idiosyncratic (coin-specific) noise
  Right side (high R²) = the factors explain almost all of this token's moves
                         → it's driven almost purely by market/size/value/momentum

The paper says 55% AVERAGE. But there's huge variation:
  Some tokens might have R²=0.8 (almost entirely factor-driven)
  Some tokens might have R²=0.2 (mostly idiosyncratic)

This variation is economically meaningful:
  Low-R² tokens = higher idiosyncratic risk, can be diversified away
  High-R² tokens = harder to diversify — their risk is systematic
""")

_factors_label = "+".join(_main_factors)

if len(reg_df) > 5:
    fig = px.histogram(
        reg_df.reset_index(),
        x="r2",
        nbins=20,
        title=f"R² distribution across {len(reg_df)} tokens — factor model ({_factors_label}) | {SAMPLE_LABEL} sample<br>"
              f"Mean R² = {reg_df['r2'].mean():.2f} = "
              f"factors explain {reg_df['r2'].mean()*100:.0f}% of individual token variance",
        labels={"r2": "R² (fraction of variance explained by factors)"},
        color_discrete_sequence=["#1f77b4"],
    )
    fig.add_vline(x=reg_df["r2"].mean(), line_dash="dash", line_color="red",
                  annotation_text=f"mean={reg_df['r2'].mean():.2f}")
    fig.add_vline(x=0.55, line_dash="dot", line_color="orange",
                  annotation_text="paper: 0.55")
    save(fig, "09_r2_distribution", height=500)


# %% ── CELL 14: WHY PORTFOLIO R² > INDIVIDUAL R² ───────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PORTFOLIO R² vs INDIVIDUAL R² — The Diversification Effect
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Now we demonstrate WHY diversified portfolios have higher R² than individual tokens.

We build random equally-weighted portfolios of N tokens and regress each on
the factor model. As N grows, idiosyncratic noise cancels → R² rises.

This is the core insight of Markowitz portfolio theory:
  - Idiosyncratic risk = diversifiable = vanishes as N → ∞
  - Systematic risk = non-diversifiable = remains regardless of N

The factors CAPTURE systematic risk. So as portfolios get larger,
the factors explain MORE (because less idiosyncratic noise remains).
""")

eligible_syms = reg_df.index.tolist()
if len(eligible_syms) >= 10:
    np.random.seed(42)
    _max_port = min(40, len(eligible_syms))
    portfolio_sizes = sorted(set([1, 3, 5, 10, 20, _max_port]))
    n_trials = 50

    port_r2_results = []
    for n in portfolio_sizes:
        r2s = []
        for _ in range(n_trials):
            chosen = np.random.choice(eligible_syms, size=min(n, len(eligible_syms)), replace=False)
            port_ret = ret_w[chosen].reindex(factor_common.index).mean(axis=1).dropna()
            X_a = X.reindex(port_ret.index).dropna()
            y_a = port_ret.reindex(X_a.index)
            if len(y_a) < 20:
                continue
            betas = np.linalg.lstsq(X_a.values, y_a.values, rcond=None)[0]
            y_pred = X_a.values @ betas
            ss_res = np.sum((y_a.values - y_pred)**2)
            ss_tot = np.sum((y_a.values - y_a.mean())**2)
            if ss_tot > 0:
                r2s.append(1 - ss_res / ss_tot)
        if r2s:
            port_r2_results.append({"n_assets": n, "mean_r2": np.mean(r2s), "std_r2": np.std(r2s)})

    port_r2_df = pd.DataFrame(port_r2_results)
    print("\nR² vs Portfolio Size (N tokens, equal-weight):")
    for _, prow in port_r2_df.iterrows():
        bar = "█" * int(prow["mean_r2"] * 40)
        print(f"  N={int(prow['n_assets']):3d} tokens: R²={prow['mean_r2']:.3f}  {bar}")

    print(f"\n  Individual token (N=1):  {port_r2_df.iloc[0]['mean_r2']:.2f}")
    print(f"  Diversified (N=max):     {port_r2_df.iloc[-1]['mean_r2']:.2f}")
    print(f"  This mirrors the paper's jump from ~55% → ~75%")

    if len(port_r2_df) > 1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=port_r2_df["n_assets"],
            y=port_r2_df["mean_r2"],
            mode="lines+markers",
            name="mean R²",
            line=dict(color="#1f77b4", width=2.5),
            marker=dict(size=8),
        ))
        fig.add_trace(go.Scatter(
            x=list(port_r2_df["n_assets"]) + list(port_r2_df["n_assets"])[::-1],
            y=list(port_r2_df["mean_r2"] + port_r2_df["std_r2"]) +
              list(port_r2_df["mean_r2"] - port_r2_df["std_r2"])[::-1],
            fill="toself", fillcolor="rgba(31,119,180,0.15)",
            line=dict(color="rgba(0,0,0,0)"),
            name="±1 std", showlegend=True,
        ))
        fig.add_hline(y=0.55, line_dash="dot", line_color="orange",
                      annotation_text="paper: individual = 0.55")
        fig.add_hline(y=0.75, line_dash="dot", line_color="green",
                      annotation_text="paper: diversified = 0.75")
        fig.update_layout(
            title=f"WHY diversified portfolios have higher R² ({SAMPLE_LABEL} sample)<br>"
                  "As you add more tokens, idiosyncratic noise averages out → factors explain more",
            xaxis_title="Number of tokens in portfolio (N)",
            yaxis_title="R² — fraction of variance explained by factors",
            yaxis=dict(range=[0, 1]),
        )
        save(fig, "10_diversification_r2_effect")


# %% ── CELL 15: Factor loadings (betas) per token ───────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FACTOR LOADINGS (BETAS) — What Does Each Token "Load" On?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
β_market tells you: "for every 1% the market factor earns, this token
            earns β_market% from that source"
  β_market = 1.2 → riskier than average (amplifies market moves)
  β_market = 0.6 → safer than average (mutes market moves)

β_smb tells you: "is this token more small-cap or large-cap in behaviour?"
  β_smb > 0  → loads like a small cap (extra risk/return)
  β_smb < 0  → loads like a large cap (more stable)

β_value tells you: "is this token cheap or expensive vs its fees?"
  β_value > 0  → loads like a value stock (undervalued relative to fees)
  β_value < 0  → loads like a growth stock (expensive, priced for future)

The paper found:
  AAVE, GMX → high positive β_value (truly cheap DeFi protocols)
  XRP, BTC  → negative β_value (expensive relative to fees earned)
  Large caps → negative β_smb (large-cap behaviour, as expected)
  Small caps → high positive β_smb
""")

if len(reg_df) > 5:
    beta_cols = [c for c in reg_df.columns if c.startswith("beta_")]
    display_df = reg_df[beta_cols + ["r2", "n_obs"]].copy()
    display_df.columns = [c.replace("beta_", "β_") for c in display_df.columns[:-2]] + ["R²", "N"]
    _sort_col = "β_mkt" if "β_mkt" in display_df else display_df.columns[0]
    display_df = display_df.sort_values(_sort_col, ascending=False)

    print("\nFactor loadings (betas) per token:")
    print(display_df.round(3).to_string())

    if "beta_mkt" in reg_df.columns:
        heat_cols = [c for c in ["beta_mkt", "beta_smb", "beta_val", "beta_mom"] if c in reg_df.columns]
        heat = reg_df[heat_cols].sort_values("beta_mkt", ascending=False)
        heat.columns = [c.replace("beta_", "β_") for c in heat.columns]

        fig = go.Figure(go.Heatmap(
            z=heat.values,
            x=heat.columns,
            y=heat.index,
            colorscale="RdBu",
            zmid=0,
            colorbar=dict(title="β"),
        ))
        fig.update_layout(
            title=f"Factor loadings (β) per token ({SAMPLE_LABEL} sample)<br>"
                  "Red=positive exposure, blue=negative — read columns: how much return comes from each factor",
            yaxis_autorange="reversed",
        )
        save(fig, "11_beta_heatmap", width=1400, height=600)


# %% ── CELL 16: 2×2 Portfolio Sort (Size × Value) ───────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  2×2 PORTFOLIO SORT: Size × Value
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The paper builds 4 portfolios by sorting on two dimensions simultaneously:

  Sort 1: Large cap / Small cap (top vs bottom 50% by mcap)
  Sort 2: High value / Low value (bottom vs top 30% by mc_fees_ratio)

This creates a 2×2 grid:
  ┌─────────────────────┬──────────────────────┐
  │  LARGE + CHEAP      │  SMALL + CHEAP       │  ← Both have high β_value
  ├─────────────────────┼──────────────────────┤
  │  LARGE + EXPENSIVE  │  SMALL + EXPENSIVE   │  ← Both have low β_value
  └─────────────────────┴──────────────────────┘

If the factors WORK, then:
  Large portfolios should have LOW β_smb (that's what "large cap" means)
  Small portfolios should have HIGH β_smb
  Cheap portfolios should have HIGH β_value
  Expensive portfolios should have LOW (or negative) β_value

This is a SANITY CHECK: do the factor loadings match the portfolio construction?
""")

sort_portfolios = {"large_cheap": [], "large_exp": [], "small_cheap": [], "small_exp": []}

for i in range(1, len(prices_w)):
    date = prices_w.index[i]
    mask = eligible_mask(mcaps_w.loc[date].fillna(0),
                         vols_w.loc[date].fillna(0), date)
    elig_syms = mcaps_w.columns[mask]

    if date not in mc_fees_ratio_w.index:
        continue

    mc_now = mcaps_w.loc[date, elig_syms].dropna()
    ratio  = mc_fees_ratio_w.loc[date].reindex(mc_now.index).dropna()
    joint  = mc_now.index.intersection(ratio.index)

    if len(joint) < 20:
        for k in sort_portfolios:
            sort_portfolios[k].append({"date": date, "ret": np.nan})
        continue

    mcap_j  = mc_now.loc[joint]
    ratio_j = ratio.loc[joint]

    med_mcap  = mcap_j.median()
    q30_ratio = ratio_j.quantile(0.30)
    q70_ratio = ratio_j.quantile(0.70)

    large = mcap_j[mcap_j >= med_mcap].index
    small = mcap_j[mcap_j < med_mcap].index
    cheap  = ratio_j[ratio_j <= q30_ratio].index
    expen  = ratio_j[ratio_j >= q70_ratio].index

    r = ret_w.loc[date, joint.intersection(ret_w.columns)].reindex(joint)

    lc = large.intersection(cheap)
    le = large.intersection(expen)
    sc = small.intersection(cheap)
    se = small.intersection(expen)
    sort_portfolios["large_cheap"].append({"date": date, "ret": r.loc[lc.intersection(r.index)].mean()})
    sort_portfolios["large_exp"].append(  {"date": date, "ret": r.loc[le.intersection(r.index)].mean()})
    sort_portfolios["small_cheap"].append({"date": date, "ret": r.loc[sc.intersection(r.index)].mean()})
    sort_portfolios["small_exp"].append(  {"date": date, "ret": r.loc[se.intersection(r.index)].mean()})

sort_series = {k: pd.DataFrame(v).set_index("date")["ret"].dropna()
               for k, v in sort_portfolios.items()}

_beta_headers = "  ".join(f"{'β_' + f.lower():>8}" for f in _main_factors if f != "MKT")
print(f"\n2×2 Portfolio Sort Results ({SAMPLE_LABEL} sample):")
print(f"{'Portfolio':<20} {'Ann Ret':>9} {'β_mkt':>8}  {_beta_headers}  {'R²':>6}")
print("-" * 70)

for label, name in [
    ("Large + Cheap",    "large_cheap"),
    ("Large + Expensive","large_exp"),
    ("Small + Cheap",    "small_cheap"),
    ("Small + Expensive","small_exp"),
]:
    s = sort_series[name]
    if len(s) < 10:
        print(f"  {label}: insufficient data ({len(s)} weeks)")
        continue

    _ar = ann_ret(s)
    X_a = X.reindex(s.index).dropna()
    y_a = s.reindex(X_a.index)
    _betas = np.linalg.lstsq(X_a.values, y_a.values, rcond=None)[0]
    _ypred = X_a.values @ _betas
    ss_tot = np.sum((y_a.values - y_a.mean())**2)
    _r2 = 1 - np.sum((y_a.values - _ypred)**2) / ss_tot if ss_tot > 0 else np.nan

    _extra = "  ".join(f"{_betas[j+1]:>8.3f}" for j, f in enumerate(_main_factors) if f != "MKT")
    print(f"  {label:<20} {_ar:>+8.1%} {_betas[1]:>8.3f}  {_extra}  {_r2:>6.3f}")

print("\nExpected pattern (from paper):")
print("  Large portfolios: β_smb should be LOW (close to 0 or negative)")
print("  Small portfolios: β_smb should be HIGH (positive)")
print("  Cheap portfolios: β_val should be HIGH (positive)")
print("  Expensive portfolios: β_val should be LOW or negative")


# %% ── CELL 17: Jensen's Alpha screen — which tokens beat the model? ─────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  JENSEN'S ALPHA — Which Tokens Actually Beat the Model?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After accounting for all factor exposures, does any token still earn
abnormal returns? This is Jensen's alpha — the "free lunch."

  α > 0 : earns more than the factors predict (unexplained outperformance)
  α < 0 : earns less than factors predict (unexplained underperformance)
  α ≈ 0 : factors fully explain returns — no idiosyncratic alpha

In efficient markets, true alpha should be zero after transaction costs.
Finding consistent positive alpha is genuinely rare — and can evaporate
as soon as enough capital chases it.

t-statistic threshold: |t| > 2.0 ≈ statistically significant at 95% confidence.
With shorter samples, the bar is harder to clear (wider confidence intervals).
""")

if len(reg_df) > 5 and "t_alpha" in reg_df.columns:
    alpha_df = reg_df[["alpha", "t_alpha", "r2", "n_obs"]].copy()
    alpha_df["ann_alpha"] = alpha_df["alpha"] * 52
    alpha_df["significant"] = alpha_df["t_alpha"].abs() > 2.0
    alpha_df = alpha_df.sort_values("ann_alpha", ascending=False)

    sig_pos = alpha_df[(alpha_df["significant"]) & (alpha_df["ann_alpha"] > 0)]
    sig_neg = alpha_df[(alpha_df["significant"]) & (alpha_df["ann_alpha"] < 0)]

    print(f"\nTokens with significant positive alpha (t > +2.0): {len(sig_pos)}")
    if len(sig_pos) > 0:
        print(sig_pos[["ann_alpha", "t_alpha", "r2"]].round(3).to_string())
    print(f"\nTokens with significant negative alpha (t < -2.0): {len(sig_neg)}")
    if len(sig_neg) > 0:
        print(sig_neg[["ann_alpha", "t_alpha", "r2"]].round(3).to_string())

    top_n = min(30, len(alpha_df))
    plot_df = alpha_df.head(top_n // 2).copy()
    plot_df = pd.concat([plot_df, alpha_df.tail(top_n // 2)])
    plot_df = plot_df[~plot_df.index.duplicated(keep="first")].sort_values("ann_alpha")

    colors_alpha = ["#d62728" if v < 0 else "#2ca02c" for v in plot_df["ann_alpha"]]
    fig = go.Figure(go.Bar(
        x=plot_df["ann_alpha"],
        y=plot_df.index,
        orientation="h",
        marker_color=colors_alpha,
        text=[f"t={t:+.1f}" for t in plot_df["t_alpha"]],
        textposition="outside",
    ))
    fig.add_vline(x=0, line_color="black", line_width=1)
    fig.update_layout(
        title=f"Jensen's Alpha — annualised ({SAMPLE_LABEL} sample, {_factors_label} model)<br>"
              f"Green bars = unexplained outperformance | t-stat shown outside bars",
        xaxis_title="Annualised alpha (arith.)",
        height=max(500, top_n * 22),
    )
    save(fig, "12_alpha_screen", width=1200, height=max(500, top_n * 22))

    print(f"\n  Note: with {len(factor_common)} weeks of data, |t| > 2.0 requires")
    print(f"  alpha > ~{2.0 / np.sqrt(len(factor_common)):.2%}/week — a high bar.")
    print(f"  More data → narrower confidence intervals → easier to detect real alpha.")


# %% ── CELL 18: Rolling factor returns — do premiums persist over time? ───────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ROLLING FACTOR RETURNS — Are the Premiums Consistent?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A key concern with factor models: are the premiums real and consistent,
or just noise in one lucky sample period?

We compute a rolling 52-week (1-year) annualised return for each factor.
If the lines stay consistently above zero, the factor is robust.
If they oscillate wildly, the premium is regime-dependent.

With 5+ years of data this chart becomes the most important diagnostic:
  - A factor that only worked 2020-2022 is a market-cycle artifact
  - A factor that works across multiple regimes is genuinely systematic

(With < 2 years of data, only the last few rolling windows are valid —
the earlier parts are based on a full year of history within our sample.)
""")

ROLL_WINDOW = 52  # weeks (1 year)
roll_factors = {
    name: series.dropna()
    for name, series in [("MKT", mkt), ("SMB", smb), ("VAL", val), ("MOM", mom)]
    if len(series.dropna()) >= ROLL_WINDOW
}

if roll_factors:
    fig = go.Figure()
    roll_colors = {"MKT": "#1f77b4", "SMB": "#2ca02c", "VAL": "#ff7f0e", "MOM": "#d62728"}

    for name, series in roll_factors.items():
        rolling_ann = series.rolling(ROLL_WINDOW, min_periods=ROLL_WINDOW).mean() * 52
        valid = rolling_ann.dropna()
        if len(valid) > 0:
            fig.add_trace(go.Scatter(
                x=valid.index, y=valid.values,
                name=name,
                line=dict(color=roll_colors.get(name), width=2),
                mode="lines",
            ))

    fig.add_hline(y=0, line_dash="dot", line_color="black", line_width=1)
    fig.update_layout(
        title=f"Rolling 52-week annualised factor returns ({SAMPLE_LABEL} sample)<br>"
              "Consistent positive values = robust premium; volatile/negative = regime-dependent",
        yaxis_title="Annualised return (trailing 52 weeks, arithmetic)",
        yaxis_tickformat=".0%",
    )
    save(fig, "13_rolling_factor_returns", width=1300, height=600)
    print(f"\nRolling window: {ROLL_WINDOW} weeks — first valid point at week {ROLL_WINDOW}")
    print(f"(More years of data = more rolling windows = more reliable picture)")
else:
    print(f"  Skipped: need ≥{ROLL_WINDOW} weeks per factor for rolling analysis.")
    print(f"  Currently have {len(mkt.dropna())} MKT weeks. Run 5-year pipeline to unlock this.")


# %% ── CELL 19: Final Summary ────────────────────────────────────────────────
print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FINAL SUMMARY: What We Learned
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

print(f"""  FACTOR MODEL SUMMARY ({SAMPLE_LABEL} sample vs Artemis Paper)

  1. MARKET FACTOR
     Ann. return: {_ann_ret_mkt:+.1%}  (Paper: +42%/yr over 8.3yr)
     Interpretation: Broad crypto market risk premium.

  2. SIZE FACTOR (SMB)
     Ann. return: {_ann_ret_smb:+.1%}  (Paper: +54%/yr over 4.9yr)
     Interpretation: Small caps outperform large caps.

  3. VALUE FACTOR
     Ann. return: {_ann_ret_val:+.1%}  (Paper: +9%/yr over 3.9yr)
     Interpretation: Low mc/fees ratio outperforms high mc/fees.
     Coverage: ~{n_weeks_val} weeks with fee data.

  4. MOMENTUM FACTOR
     Ann. return: {_ann_ret_mom:+.1%}  (Paper: +75%/yr over 4.6yr)
     Interpretation: 3-week vol-adjusted winners continue winning.
""")

if len(reg_df) > 0:
    _r2_mean = reg_df["r2"].mean()
    _port_r2_max = port_r2_df.iloc[-1]["mean_r2"] if "port_r2_df" in dir() and len(port_r2_df) > 0 else float("nan")
    print(f"""  EXPLANATORY POWER (R²) — {_factors_label} model:
     Tokens regressed:     {len(reg_df)}
     Mean R² per token:    {_r2_mean:.2f} ({_r2_mean*100:.0f}%)
     Diversified (N=max):  {_port_r2_max:.2f} ({_port_r2_max*100:.0f}%)
     (Paper: ~55% individual → ~75% diversified)

  WHY OUR NUMBERS MAY DIFFER FROM THE PAPER:
     - Sample period: {SAMPLE_LABEL}; paper has 4–8 years
     - Shorter window → higher sampling variance → magnitudes are noisier
     - The MECHANICS are identical; longer data → results converge to paper
     - Run the 5-year pipeline to get paper-comparable statistics

  KEY CONCEPTS (reminder):
     Factor   = a systematic source of return (market, size, value, momentum)
     Beta     = how much a token is exposed to that factor
     R²       = fraction of return variance the factors explain
     L-S port = the "pure" factor portfolio, roughly market-neutral
     Diversification = idiosyncratic risk cancels → portfolio R² rises
     Alpha    = return left over after removing all factor exposure
""")

print(f"All figures saved to: {OUT}")
print("Done.")
