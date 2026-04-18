# %% [markdown]
# # 06 -- Cross-Sectional Tests
# Spearman IC per factor against next-month returns; saves `factor_ic_results.csv`.

# %%
import os
import warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

warnings.filterwarnings("ignore")

factors = pd.read_parquet("../data/processed/factors_monthly.parquet")
art = pd.read_parquet("../data/processed/panel_artemis_daily.parquet")

factors["date"] = pd.to_datetime(factors["date"])
art["date"] = pd.to_datetime(art["date"])
art = art.sort_values(["symbol", "date"])

FACTOR_COLS = [
    col
    for col in [
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
        "within_cluster_rank",
        "corr_density",
        "eigenvector_centrality_std",
        "centrality_change_1m_std",
    ]
    if col in factors.columns
]

price_w = art.pivot_table(
    index="date", columns="symbol", values="price", aggfunc="last"
)
rebalance_dates = sorted(factors["date"].unique())
print(f"Factors: {factors.shape}  |  Rebalance dates: {len(rebalance_dates)}")
print(f"Testing factors: {FACTOR_COLS}")


# %%
## Compute forward returns (price at t+1 / price at t - 1)
# No lookahead: we use the rebalance date price, which is already in the past
# when the next period starts.


def last_val(wide, t, cols):
    sub = wide.reindex(columns=cols).loc[:t]
    if len(sub) == 0:
        return pd.Series(np.nan, index=cols)
    return sub.ffill().iloc[-1]


fwd_rows = []
for i, t in enumerate(rebalance_dates[:-1]):
    t_next = rebalance_dates[i + 1]
    syms = factors[factors["date"] == t]["symbol"].tolist()
    syms_in = [s for s in syms if s in price_w.columns]
    p_t = last_val(price_w, t, syms_in)
    p_t1 = last_val(price_w, t_next, syms_in)
    fwd = (p_t1 / p_t.replace(0, np.nan)) - 1
    for sym, r in fwd.items():
        fwd_rows.append({"symbol": sym, "date": t, "fwd_ret": r})

fwd_df = pd.DataFrame(fwd_rows)
print(
    f"Forward returns: {fwd_df.shape}  |  NaN rate: {fwd_df['fwd_ret'].isna().mean():.2%}"
)
print(fwd_df["fwd_ret"].describe().round(3).to_string())


# %%
## Spearman IC per factor
merged = factors.merge(fwd_df, on=["symbol", "date"], how="inner")

ic_records = []

for factor in FACTOR_COLS:
    ics = []
    for t, grp in merged.groupby("date"):
        valid = grp[[factor, "fwd_ret"]].dropna()
        if len(valid) < 5:
            continue
        ic, _ = stats.spearmanr(valid[factor], valid["fwd_ret"])
        ics.append(ic)

    ics = np.array(ics)
    n = len(ics)
    if n < 2:
        ic_records.append(
            {
                "Factor": factor,
                "Mean IC": np.nan,
                "IC Std": np.nan,
                "t-stat": np.nan,
                "Hit Rate": np.nan,
                "Q5-Q1 Spread": np.nan,
                "N": n,
            }
        )
        continue

    mean_ic = ics.mean()
    std_ic = ics.std(ddof=1)
    t_stat = mean_ic / std_ic * np.sqrt(n) if std_ic > 1e-10 else 0.0
    hit_rate = (ics > 0).mean()

    spreads = []
    for t, grp in merged.groupby("date"):
        valid = grp[[factor, "fwd_ret"]].dropna()
        if len(valid) < 10:
            continue
        valid = valid.copy()
        valid["q"] = pd.qcut(valid[factor], 5, labels=False, duplicates="drop")
        q5 = valid[valid["q"] == valid["q"].max()]["fwd_ret"].mean()
        q1 = valid[valid["q"] == valid["q"].min()]["fwd_ret"].mean()
        spreads.append(q5 - q1)
    q5q1 = float(np.mean(spreads)) if spreads else np.nan

    ic_records.append(
        {
            "Factor": factor,
            "Mean IC": round(mean_ic, 4),
            "IC Std": round(std_ic, 4),
            "t-stat": round(t_stat, 2),
            "Hit Rate": round(hit_rate, 3),
            "Q5-Q1 Spread": round(q5q1, 4) if not np.isnan(q5q1) else np.nan,
            "N": n,
        }
    )

ic_df = pd.DataFrame(ic_records).sort_values("t-stat", ascending=False)
print("Factor IC Summary:")
print(ic_df.to_string(index=False))
print()
sig = ic_df[ic_df["t-stat"].abs() > 1.0]["Factor"].tolist()
print(f"Factors with |t-stat| > 1.0: {sig}")


# %%
## Regime-conditional IC
# For each factor: compute mean IC separately for tight / loose / neutral macro states.
# This tests whether factor efficacy is regime-dependent (economic interpretation,
# not just aggregate predictive power).

REGIME_LABELS = ["loose", "neutral", "tight"]

if "regime" in factors.columns:
    # merged already inherits regime from factors; just copy and fill.
    if "regime" in merged.columns:
        merged_regime = merged.copy()
    else:
        merged_regime = merged.merge(
            factors[["symbol", "date", "regime"]].drop_duplicates(),
            on=["symbol", "date"],
            how="left",
        )
    merged_regime["regime"] = merged_regime["regime"].fillna("neutral")
else:
    # Fall back: load regime file directly if factor panel lacks regime column.
    regime_path = "../data/processed/macro_regime_monthly.parquet"
    if os.path.exists(regime_path):
        reg_src = pd.read_parquet(regime_path)
        reg_src["date"] = pd.to_datetime(reg_src["date"])
        merged_regime = merged.merge(
            reg_src[["date", "regime"]],
            on="date",
            how="left",
        )
        merged_regime["regime"] = merged_regime["regime"].fillna("neutral")
    else:
        merged_regime = None
        print("NOTE: regime column not available — skipping regime-conditional IC.")

if merged_regime is not None:
    regime_dist = merged_regime[["date", "regime"]].drop_duplicates()["regime"].value_counts()
    print(f"\nRegime distribution (rebalance dates): {regime_dist.to_dict()}")

    regime_ic_records = []
    for factor in FACTOR_COLS:
        row = {"Factor": factor}
        for reg in REGIME_LABELS:
            sub = merged_regime[merged_regime["regime"] == reg]
            ics = []
            for t, grp in sub.groupby("date"):
                valid = grp[[factor, "fwd_ret"]].dropna()
                if len(valid) < 5:
                    continue
                ic, _ = stats.spearmanr(valid[factor], valid["fwd_ret"])
                ics.append(ic)
            if len(ics) >= 2:
                row[f"IC_{reg}"] = round(float(np.mean(ics)), 4)
                row[f"N_{reg}"] = len(ics)
            else:
                row[f"IC_{reg}"] = np.nan
                row[f"N_{reg}"] = len(ics)
        regime_ic_records.append(row)

    regime_ic_df = pd.DataFrame(regime_ic_records)

    # Join regime IC columns onto the main ic_df for the final saved table.
    ic_df = ic_df.merge(
        regime_ic_df[["Factor"] + [f"IC_{r}" for r in REGIME_LABELS]],
        on="Factor",
        how="left",
    )

    print("\nRegime-Conditional IC:")
    print(
        ic_df[
            ["Factor", "Mean IC", "t-stat", "IC_loose", "IC_neutral", "IC_tight"]
        ].to_string(index=False)
    )
    print()
    print("Interpretation notes:")
    for _, row in ic_df.iterrows():
        ic_l = row.get("IC_loose", np.nan)
        ic_t = row.get("IC_tight", np.nan)
        if pd.isna(ic_l) or pd.isna(ic_t):
            continue
        diff = ic_l - ic_t
        if abs(diff) > 0.05:
            direction = "stronger in LOOSE" if diff > 0 else "stronger in TIGHT"
            print(f"  {row['Factor']:30s}  loose={ic_l:+.3f}  tight={ic_t:+.3f}  -> {direction}")


# %%
## IC bar chart for top 4 factors by |t-stat|
top_factors = ic_df.head(4)["Factor"].tolist()

fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharey=True)
axes = axes.flatten()

for ax, factor in zip(axes, top_factors):
    ics, dates = [], []
    for t, grp in merged.groupby("date"):
        valid = grp[[factor, "fwd_ret"]].dropna()
        if len(valid) < 5:
            continue
        ic, _ = stats.spearmanr(valid[factor], valid["fwd_ret"])
        ics.append(ic)
        dates.append(t)
    ax.bar(
        dates, ics, color=["steelblue" if ic > 0 else "tomato" for ic in ics], width=20
    )
    ax.axhline(0, color="k", lw=0.8)
    ax.set_title(f"{factor}  (mean={float(np.mean(ics)):.3f})")
    ax.set_ylabel("Spearman IC")

plt.suptitle("IC by period -- top 4 factors", fontsize=13)
plt.tight_layout()
plt.savefig("../reports/ic_by_period.png", dpi=100, bbox_inches="tight")
plt.show()


# %%
out_path = "../data/processed/factor_ic_results.csv"
ic_df.to_csv(out_path, index=False)
print(f"Saved: {out_path}")
print("\n>> Cross-sectional tests complete.")
