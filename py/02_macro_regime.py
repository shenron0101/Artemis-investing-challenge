# %% [markdown]
# # 02 -- Macro Regime\nBuild monthly tight/loose/neutral regime from FRED data before the market-structure and factor work.\nSaves `macro_regime_monthly.parquet`.

# %%
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

macro = pd.read_parquet("../data/processed/macro_regime_daily.parquet")
macro["date"] = pd.to_datetime(macro["date"])
uni = pd.read_parquet("../data/processed/universe_monthly.parquet")
uni["date"] = pd.to_datetime(uni["date"])

# Filter to backtest window with buffer
macro = macro[(macro["date"] >= "2020-01-01") & (macro["date"] <= "2025-01-01")]
wide = macro.pivot_table(index="date", columns="metric", values="value", aggfunc="last")
wide = wide.sort_index()

rebalance_dates = sorted(uni["date"].unique())
print(f"Macro metrics : {wide.columns.tolist()}")
print(f"Date range    : {wide.index.min().date()} -> {wide.index.max().date()}")
print(f"Rebalance dates: {len(rebalance_dates)}")
print()
print("Recent macro data (last 6 rows):")
print(wide.tail(6).round(3).to_string())


# %%
## Build monthly regime score at each rebalance date
# Signals (positive change = tighter monetary conditions):
#   policy_rate_3m_chg  -- FEDFUNDS 3-month change (monthly series)
#   y2_yield_3m_chg     -- DGS2 3-month change (daily -> last obs)
#   hy_spread_3m_chg    -- BAMLH0A0HYM2 3-month change (daily, available 2023+)
# Regime = majority vote: tight if >0 signals tightening, loose if >0 easing


def last_obs(w_df, t, col):
    if col not in w_df.columns:
        return np.nan
    sub = w_df[[col]].loc[:t]
    vals = sub[col].dropna()
    return float(vals.iloc[-1]) if len(vals) else np.nan


records = []
for t in rebalance_dates:
    t_3m = t - pd.Timedelta(days=90)

    pr_now = last_obs(wide, t, "policy_rate")
    pr_3m = last_obs(wide, t_3m, "policy_rate")
    y2_now = last_obs(wide, t, "2y_yield")
    y2_3m = last_obs(wide, t_3m, "2y_yield")
    hy_now = last_obs(wide, t, "high_yield_spread")
    hy_3m = last_obs(wide, t_3m, "high_yield_spread")

    pr_chg = (pr_now - pr_3m) if (pd.notna(pr_now) and pd.notna(pr_3m)) else np.nan
    y2_chg = (y2_now - y2_3m) if (pd.notna(y2_now) and pd.notna(y2_3m)) else np.nan
    hy_chg = (hy_now - hy_3m) if (pd.notna(hy_now) and pd.notna(hy_3m)) else np.nan

    signals = []
    if pd.notna(pr_chg):
        signals.append(1 if pr_chg > 0 else -1)
    if pd.notna(y2_chg):
        signals.append(1 if y2_chg > 0 else -1)
    if pd.notna(hy_chg):
        signals.append(1 if hy_chg > 0 else -1)

    score = float(np.mean(signals)) if signals else 0.0
    regime = "tight" if score > 0.33 else ("loose" if score < -0.33 else "neutral")

    records.append(
        {
            "date": t,
            "policy_rate": pr_now,
            "policy_rate_3m_chg": pr_chg,
            "2y_yield": y2_now,
            "2y_yield_3m_chg": y2_chg,
            "hy_spread": hy_now,
            "hy_spread_3m_chg": hy_chg,
            "n_signals": len(signals),
            "regime_score": score,
            "regime": regime,
        }
    )

regime_df = pd.DataFrame(records)

print("Regime distribution:")
print(regime_df["regime"].value_counts().to_string())
print()
print(
    regime_df[
        ["date", "policy_rate", "2y_yield", "hy_spread", "regime_score", "regime"]
    ].to_string(index=False)
)


# %%
out = "../data/processed/macro_regime_monthly.parquet"
regime_df.to_parquet(out, index=False)
print(f"Saved: {out}  shape={regime_df.shape}")
print("Columns:", regime_df.columns.tolist())
print("\n>> Macro regime complete.")
