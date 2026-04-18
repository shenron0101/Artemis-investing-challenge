# %% [markdown]
# # 05 -- Factor Engineering
# Standardize the economic and on-chain factor panel for later cross-sectional tests.

# %%
import warnings, os
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

art = pd.read_parquet("../data/processed/panel_artemis_daily.parquet")
uni = pd.read_parquet("../data/processed/universe_monthly.parquet")

art["date"] = pd.to_datetime(art["date"])
uni["date"] = pd.to_datetime(uni["date"])
art = art.sort_values(["symbol", "date"])

rebalance_dates = sorted(uni["date"].unique())
print(f"Artemis: {art.shape} | Universe: {uni.shape}")
print(
    f"Rebalance dates: {len(rebalance_dates)}  ({rebalance_dates[0].date()} -> {rebalance_dates[-1].date()})"
)


def make_wide(df, col):
    return df.pivot_table(index="date", columns="symbol", values=col, aggfunc="last")


price_w = make_wide(art, "price")
fees_w = make_wide(art, "fees")
rev_w = make_wide(art, "revenue")
tvl_w = make_wide(art, "tvl")
dau_w = make_wide(art, "dau")
txns_w = make_wide(art, "txns")
mc_w = make_wide(art, "mc")
print("Wide tables built.")


# %%
## Helper functions (no lookahead: all slices end at or before rebalance date t)


def last_val(wide, t, cols):
    # Last non-null value on or before date t for each column.
    sub = wide.reindex(columns=cols).loc[:t]
    if len(sub) == 0:
        return pd.Series(np.nan, index=cols)
    return sub.ffill().iloc[-1]


def window_mean(wide, t_end, n_days, cols, min_obs=15):
    # Mean over n_days ending at t_end; NaN if fewer than min_obs non-null.
    t_start = t_end - pd.Timedelta(days=n_days - 1)
    sub = wide.reindex(columns=cols).loc[t_start:t_end]
    cnt = sub.notna().sum()
    m = sub.mean()
    m[cnt < min_obs] = np.nan
    return m


def window_std(wide, t_end, n_days, cols, min_obs=15):
    t_start = t_end - pd.Timedelta(days=n_days - 1)
    sub = wide.reindex(columns=cols).loc[t_start:t_end]
    cnt = sub.notna().sum()
    s = sub.std()
    s[cnt < min_obs] = np.nan
    return s


def realized_vol(pw, t_end, n_days, cols, min_obs=10):
    # Annualised realised vol from log daily returns.
    t_start = t_end - pd.Timedelta(days=n_days - 1)
    sub = pw.reindex(columns=cols).loc[t_start:t_end]
    log_ret = np.log(sub).diff()
    cnt = log_ret.notna().sum()
    s = log_ret.std() * np.sqrt(252)
    s[cnt < min_obs] = np.nan
    return s


def safe_ratio(num, denom):
    d = denom.copy().astype(float)
    d[d == 0] = np.nan
    return num / d


def cross_sectional_standardize(df, cols):
    for col in cols:
        for t, idx in df.groupby("date").groups.items():
            s = df.loc[idx, col].astype(float)
            if s.notna().sum() < 3:
                df.loc[idx, col] = 0.0
                continue
            q01, q99 = s.quantile(0.01), s.quantile(0.99)
            s = s.clip(q01, q99)
            mu, sigma = s.mean(), s.std()
            if sigma > 1e-10:
                s = (s - mu) / sigma
            else:
                s = pd.Series(0.0, index=s.index)
            df.loc[idx, col] = s.fillna(0.0).values
    return df


# %%
## Factor computation loop -- no future data used (all windows end at t)
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

all_records = []

for t in rebalance_dates:
    uni_syms = uni[uni["date"] == t]["symbol"].tolist()
    uni_syms = [s for s in uni_syms if s in price_w.columns]

    # Group A: Momentum
    p_now = last_val(price_w, t, uni_syms)
    p_30 = last_val(price_w, t - pd.Timedelta(30), uni_syms)
    p_90 = last_val(price_w, t - pd.Timedelta(90), uni_syms)
    p_180 = last_val(price_w, t - pd.Timedelta(180), uni_syms)

    mom_1m = safe_ratio(p_now, p_30) - 1
    mom_3m = safe_ratio(p_now, p_90) - 1
    mom_6m = safe_ratio(p_now, p_180) - 1
    vol_30 = realized_vol(price_w, t, 31, uni_syms, min_obs=10)

    # Group B: Fundamentals
    mc_now = last_val(mc_w, t, uni_syms)

    f_30 = window_mean(fees_w, t, 30, uni_syms)
    f_lag30 = window_mean(fees_w, t - pd.Timedelta(30), 30, uni_syms)
    fees_mc = safe_ratio(f_30, mc_now)
    fees_growth_30 = safe_ratio(f_30, f_lag30) - 1

    r_30 = window_mean(rev_w, t, 30, uni_syms)
    r_lag30 = window_mean(rev_w, t - pd.Timedelta(30), 30, uni_syms)
    rev_mc = safe_ratio(r_30, mc_now)
    rev_growth_30 = safe_ratio(r_30, r_lag30) - 1

    # Group C: Usage
    d_30 = window_mean(dau_w, t, 30, uni_syms)
    d_lag30 = window_mean(dau_w, t - pd.Timedelta(30), 30, uni_syms)
    dau_growth_30 = safe_ratio(d_30, d_lag30) - 1

    d_90_mean = window_mean(dau_w, t, 90, uni_syms, min_obs=20)
    d_90_std = window_std(dau_w, t, 90, uni_syms, min_obs=20)
    dau_zscore = safe_ratio(d_30 - d_90_mean, d_90_std)

    x_30 = window_mean(txns_w, t, 30, uni_syms)
    x_lag30 = window_mean(txns_w, t - pd.Timedelta(30), 30, uni_syms)
    txns_growth_30 = safe_ratio(x_30, x_lag30) - 1

    # Group D: TVL
    tv_30 = window_mean(tvl_w, t, 30, uni_syms)
    tv_lag30 = window_mean(tvl_w, t - pd.Timedelta(30), 30, uni_syms)
    tvl_mc = safe_ratio(tv_30, mc_now)
    tvl_growth_30 = safe_ratio(tv_30, tv_lag30) - 1

    df_t = pd.DataFrame(
        {
            "symbol": uni_syms,
            "date": t,
            "mom_1m": mom_1m.reindex(uni_syms).values,
            "mom_3m": mom_3m.reindex(uni_syms).values,
            "mom_6m": mom_6m.reindex(uni_syms).values,
            "vol_30d": vol_30.reindex(uni_syms).values,
            "fees_mc": fees_mc.reindex(uni_syms).values,
            "rev_mc": rev_mc.reindex(uni_syms).values,
            "fees_growth_30d": fees_growth_30.reindex(uni_syms).values,
            "rev_growth_30d": rev_growth_30.reindex(uni_syms).values,
            "dau_growth_30d": dau_growth_30.reindex(uni_syms).values,
            "txns_growth_30d": txns_growth_30.reindex(uni_syms).values,
            "dau_zscore": dau_zscore.reindex(uni_syms).values,
            "tvl_mc": tvl_mc.reindex(uni_syms).values,
            "tvl_growth_30d": tvl_growth_30.reindex(uni_syms).values,
        }
    )
    all_records.append(df_t)

factors_raw = pd.concat(all_records, ignore_index=True)
print(f"Raw factors: {factors_raw.shape}")
print("Null rates (raw):")
print(factors_raw[BASE_FACTOR_COLS].isnull().mean().round(3).to_string())


# %%
## Standardization: winsorize at 1/99% -> z-score -> fill NaN = 0

factors_std = cross_sectional_standardize(factors_raw.copy(), BASE_FACTOR_COLS)

print("Standardized factors -- mean / std check (should be ~0 / 1 per date):")
for col in BASE_FACTOR_COLS:
    mu = factors_std.groupby("date")[col].mean().mean()
    sig = factors_std.groupby("date")[col].std().mean()
    print(f"  {col:20s}  mean={mu:+.3f}  std={sig:.3f}")


# %%
## Merge market-structure features so they are part of the research factor panel

NETWORK_FACTOR_COLS = []

clusters_path = "../data/processed/network_clusters_monthly.parquet"
if os.path.exists(clusters_path):
    clusters = pd.read_parquet(clusters_path)
    clusters["date"] = pd.to_datetime(clusters["date"])
    # Merge within-cluster rank (leadership) and corr_density (crowding).
    cluster_merge_cols = ["symbol", "date", "within_cluster_rank"]
    if "corr_density" in clusters.columns:
        cluster_merge_cols.append("corr_density")
    factors_std = factors_std.merge(
        clusters[cluster_merge_cols],
        on=["symbol", "date"],
        how="left",
    )
    factors_std["within_cluster_rank"] = factors_std["within_cluster_rank"].fillna(0.5)
    factors_std = cross_sectional_standardize(factors_std, ["within_cluster_rank"])
    NETWORK_FACTOR_COLS.append("within_cluster_rank")
    if "corr_density" in clusters.columns:
        factors_std["corr_density"] = factors_std["corr_density"].fillna(0.0)
        factors_std = cross_sectional_standardize(factors_std, ["corr_density"])
        NETWORK_FACTOR_COLS.append("corr_density")
        print("Merged cluster-relative rank + corr_density (crowding) into factor panel.")
    else:
        print("Merged cluster-relative rank into factor panel.")
else:
    print(
        "NOTE: network_clusters_monthly.parquet not found - run 03_market_structure_clusters.py first"
    )

centrality_path = "../data/processed/centrality_factors_monthly.parquet"
if os.path.exists(centrality_path):
    centrality = pd.read_parquet(centrality_path)
    centrality["date"] = pd.to_datetime(centrality["date"])
    cent_cols = [
        col
        for col in ["eigenvector_centrality_std", "centrality_change_1m_std"]
        if col in centrality.columns
    ]
    if cent_cols:
        factors_std = factors_std.merge(
            centrality[["symbol", "date"] + cent_cols],
            on=["symbol", "date"],
            how="left",
        )
        for col in cent_cols:
            factors_std[col] = factors_std[col].fillna(0.0)
        NETWORK_FACTOR_COLS.extend(cent_cols)
        print(f"Merged centrality features into factor panel: {cent_cols}")
else:
    print(
        "NOTE: centrality_factors_monthly.parquet not found - run 04_market_structure_centrality.py first"
    )

## Merge macro regime so downstream tests can condition on tight/loose/neutral
regime_path = "../data/processed/macro_regime_monthly.parquet"
if os.path.exists(regime_path):
    regime_df = pd.read_parquet(regime_path)
    regime_df["date"] = pd.to_datetime(regime_df["date"])
    factors_std = factors_std.merge(
        regime_df[["date", "regime", "regime_score"]],
        on="date",
        how="left",
    )
    factors_std["regime"] = factors_std["regime"].fillna("neutral")
    n_regimes = factors_std[["date", "regime"]].drop_duplicates()["regime"].value_counts()
    print(f"Merged macro regime into factor panel.  Distribution: {n_regimes.to_dict()}")
else:
    print(
        "NOTE: macro_regime_monthly.parquet not found - run 02_macro_regime.py first"
    )

FINAL_FACTOR_COLS = BASE_FACTOR_COLS + NETWORK_FACTOR_COLS
print(f"Final factor columns ({len(FINAL_FACTOR_COLS)}): {FINAL_FACTOR_COLS}")


# %%
out_path = "../data/processed/factors_monthly.parquet"
factors_std.to_parquet(out_path, index=False)
print(f"Saved: {out_path}  shape={factors_std.shape}")
print("\nSample (first rebalance date):")
first_t = factors_std["date"].min()
print(
    factors_std[factors_std["date"] == first_t][
        ["symbol"] + FINAL_FACTOR_COLS[:6]
    ].head()
)
print("\n>> Factor engineering complete.")
