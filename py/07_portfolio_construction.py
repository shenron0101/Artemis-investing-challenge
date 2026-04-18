# %% [markdown]
# # 07 -- Portfolio Construction
# Translate the research evidence into simple long/short variants.
# Saves `portfolio_weights_monthly.parquet`.

# %%
import warnings, os
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

factors = pd.read_parquet("../data/processed/factors_monthly.parquet")
ic_df = pd.read_csv("../data/processed/factor_ic_results.csv")

factors["date"] = pd.to_datetime(factors["date"])

# Load macro regime (from 02_macro_regime.py)
regime_path = "../data/processed/macro_regime_monthly.parquet"
if os.path.exists(regime_path):
    regime_df = pd.read_parquet(regime_path)
    regime_df["date"] = pd.to_datetime(regime_df["date"])
    regime_map = regime_df.set_index("date")["regime"].to_dict()
    HAS_REGIME = True
    print("Macro regime loaded:", pd.Series(regime_map).value_counts().to_dict())
else:
    regime_map = {}
    HAS_REGIME = False
    print("NOTE: macro_regime_monthly.parquet not found - run 02_macro_regime.py first")

BASE_FACTOR_COLS = [
    "mom_1m",
    "mom_3m",
    "mom_6m",
    "vol_30d",
    "fees_mc",
    "rev_mc",
    "fees_growth_30d",
    "rev_growth_30d",
    "dau_growth_30d",
    "txns_growth_30d",
    "dau_zscore",
    "tvl_mc",
    "tvl_growth_30d",
]
CLUSTER_FACTORS = [f for f in ["within_cluster_rank"] if f in factors.columns]
CENT_FACTORS = [
    f
    for f in ["eigenvector_centrality_std", "centrality_change_1m_std"]
    if f in factors.columns
]
FACTOR_COLS = BASE_FACTOR_COLS + CLUSTER_FACTORS + CENT_FACTORS
MOM_FACTORS = ["mom_1m", "mom_3m", "mom_6m", "vol_30d"]
FUND_FACTORS = [f for f in BASE_FACTOR_COLS if f not in MOM_FACTORS]

sig_pos = ic_df[ic_df["t-stat"] > 1.0]["Factor"].tolist()
sig_mom = [f for f in MOM_FACTORS if f in sig_pos]
sig_fund = [f for f in FUND_FACTORS if f in sig_pos]
neg_sig = ic_df[(ic_df["t-stat"] < -1.0)]["Factor"].tolist()
print(f"Positive-IC significant factors (t>1) : {sig_pos}")
print(f"  Momentum subset                     : {sig_mom}")
print(f"  Fund/usage subset                   : {sig_fund}")
print(f"  Cluster / centrality factors        : {CLUSTER_FACTORS + CENT_FACTORS}")
print(f"Negative-IC significant factors (t<-1): {neg_sig}  [sign will be flipped]")


# %%
## Use the enriched factor panel from 05_factor_engineering.py

factors_full = factors.copy()

print(f"factors_full shape: {factors_full.shape}")
print(f"Columns: {list(factors_full.columns)}")


# %%
## Build long/short weights for five variants

N_LONG = 10  # top quintile of 50-coin universe
N_SHORT = 10  # bottom quintile

# Flip sign of strongly-negative-IC factors so higher score = better return
factors_cs = factors_full.copy()
for f in neg_sig:
    if f in factors_cs.columns:
        factors_cs[f] = -factors_cs[f]

# Fallback to full base set (sign-adjusted) when no base factor passes the threshold
all_sig_base = [f for f in sig_pos + neg_sig if f in BASE_FACTOR_COLS]
v1_factors = sig_mom if sig_mom else MOM_FACTORS
v2_factors = sig_fund if sig_fund else FUND_FACTORS
v3_factors = all_sig_base if all_sig_base else BASE_FACTOR_COLS
v4_factors = v3_factors + CLUSTER_FACTORS
v5_factors = v4_factors + CENT_FACTORS

# Regime exposure scalar: loose=1.0, neutral=0.5, tight=0.0
REGIME_SCALE = {"loose": 1.0, "neutral": 0.5, "tight": 0.0}

VARIANTS = {
    "v1_momentum": v1_factors,
    "v2_fund_usage": v2_factors,
    "v3_full": v3_factors,
    "v4_full_cluster": v4_factors,
    "v5_regime_aware": v5_factors,
}

print("Variant factor sets (negative-IC factors sign-flipped):")
for k, v in VARIANTS.items():
    print(f"  {k:20s}: {v}")

all_weights = []

for variant, sel_factors in VARIANTS.items():
    for t, grp in factors_cs.groupby("date"):
        grp = grp.reset_index(drop=True)
        available = [f for f in sel_factors if f in grp.columns]
        composite = (
            grp[available].mean(axis=1)
            if available
            else pd.Series(0.0, index=grp.index)
        )
        composite.index = grp["symbol"].values

        long_syms = composite.nlargest(N_LONG).index.tolist()
        short_syms = composite.nsmallest(N_SHORT).index.tolist()

        # Regime scaling for v5 only
        if variant == "v5_regime_aware" and HAS_REGIME:
            regime_label = regime_map.get(t, "neutral")
            scale = REGIME_SCALE.get(regime_label, 1.0)
        else:
            scale = 1.0

        for sym in grp["symbol"]:
            if sym in long_syms:
                w = scale / N_LONG
            elif sym in short_syms:
                w = -scale / N_SHORT
            else:
                w = 0.0
            all_weights.append(
                {"symbol": sym, "date": t, "weight": w, "variant": variant}
            )

weights_df = pd.DataFrame(all_weights)
print(f"\nWeights shape: {weights_df.shape}")

# Turnover estimate
print("\nAverage monthly turnover per variant (fraction of portfolio that changes):")
for variant in VARIANTS:
    v_df = weights_df[weights_df["variant"] == variant].pivot_table(
        index="date", columns="symbol", values="weight", fill_value=0
    )
    turnovers = v_df.diff().abs().sum(axis=1) / 2
    print(f"  {variant:22s}: {turnovers.mean():.2f}")

if HAS_REGIME:
    print("\nv5 regime distribution applied:")
    for t, grp in weights_df[weights_df["variant"] == "v5_regime_aware"].groupby(
        "date"
    ):
        gross = grp["weight"].abs().sum()
        regime_label = regime_map.get(t, "neutral")
        if gross < 1.8:
            print(f"  {t.date()} regime={regime_label} gross={gross:.2f}")


# %%
out_path = "../data/processed/portfolio_weights_monthly.parquet"
weights_df.to_parquet(out_path, index=False)
print(f"Saved: {out_path}  shape={weights_df.shape}")
print("\n>> Portfolio construction complete.")
