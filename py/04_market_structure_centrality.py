# %% [markdown]
# # 04 -- Market Structure: Centrality\nBuild degree/eigenvector/betweenness centrality from monthly correlation graphs.\nSaves `centrality_factors_monthly.parquet`.

# %%
import warnings
import pandas as pd
import numpy as np
import networkx as nx

warnings.filterwarnings("ignore")

art = pd.read_parquet("../data/processed/panel_artemis_daily.parquet")
uni = pd.read_parquet("../data/processed/universe_monthly.parquet")
art["date"] = pd.to_datetime(art["date"])
uni["date"] = pd.to_datetime(uni["date"])
art = art.sort_values(["symbol", "date"])

price_w = art.pivot_table(
    index="date", columns="symbol", values="price", aggfunc="last"
)
rebalance_dates = sorted(uni["date"].unique())

print(f"Price pivot: {price_w.shape}")
print(f"Rebalance dates: {len(rebalance_dates)}")


# %%
## Monthly centrality from 60-day rolling return correlation graph
# Edge condition: correlation > 0.2 (keeps only meaningful co-movement links)
# Centrality measures: degree, eigenvector (importance by neighbours), betweenness (bridge score)

CORR_WINDOW = 60
CORR_THRESHOLD = 0.2

records = []
prev_eigen = {}

for t in rebalance_dates:
    uni_syms = uni[uni["date"] == t]["symbol"].tolist()

    t_start = t - pd.Timedelta(days=CORR_WINDOW)
    sub = price_w.reindex(columns=uni_syms).loc[t_start:t]
    rets = sub.pct_change().dropna(how="all")

    # Require at least 30 non-null return days
    valid_cols = rets.columns[rets.notna().sum() >= 30].tolist()
    rets = rets[valid_cols]

    if len(valid_cols) < 5:
        for sym in uni_syms:
            records.append(
                {
                    "symbol": sym,
                    "date": t,
                    "degree_centrality": np.nan,
                    "eigenvector_centrality": np.nan,
                    "betweenness_centrality": np.nan,
                    "centrality_change_1m": np.nan,
                }
            )
        prev_eigen = {}
        continue

    corr_mat = rets.corr()

    G = nx.Graph()
    G.add_nodes_from(valid_cols)
    for i in range(len(valid_cols)):
        for j in range(i + 1, len(valid_cols)):
            c = corr_mat.iloc[i, j]
            if pd.notna(c) and c > CORR_THRESHOLD:
                G.add_edge(valid_cols[i], valid_cols[j], weight=float(c))

    deg = nx.degree_centrality(G)
    try:
        eig = nx.eigenvector_centrality_numpy(G, weight="weight")
    except Exception:
        eig = {n: 0.0 for n in G.nodes()}
    bet = nx.betweenness_centrality(G, weight="weight", normalized=True)

    for sym in uni_syms:
        in_graph = sym in G.nodes()
        ev = float(eig.get(sym, 0.0)) if in_graph else np.nan
        dc = float(deg.get(sym, 0.0)) if in_graph else np.nan
        bc = float(bet.get(sym, 0.0)) if in_graph else np.nan
        chg = (
            (ev - prev_eigen[sym])
            if (in_graph and sym in prev_eigen and pd.notna(prev_eigen[sym]))
            else np.nan
        )
        records.append(
            {
                "symbol": sym,
                "date": t,
                "degree_centrality": dc,
                "eigenvector_centrality": ev,
                "betweenness_centrality": bc,
                "centrality_change_1m": chg,
            }
        )

    prev_eigen = {sym: eig.get(sym, np.nan) for sym in uni_syms}

centrality = pd.DataFrame(records)

print(f"Centrality shape: {centrality.shape}")
print("Non-null rates:")
print(
    centrality[
        [
            "degree_centrality",
            "eigenvector_centrality",
            "betweenness_centrality",
            "centrality_change_1m",
        ]
    ]
    .notna()
    .mean()
    .round(3)
    .to_string()
)


# %%
## Cross-sectional standardize centrality metrics (winsorise -> z-score -> fillna 0)

CENT_COLS = ["eigenvector_centrality", "centrality_change_1m"]

for col in CENT_COLS:
    out_col = col + "_std"
    centrality[out_col] = np.nan
    for t, idx in centrality.groupby("date").groups.items():
        s = centrality.loc[idx, col].astype(float)
        if s.notna().sum() < 3:
            centrality.loc[idx, out_col] = 0.0
            continue
        q01, q99 = s.quantile(0.01), s.quantile(0.99)
        s = s.clip(q01, q99)
        mu, sigma = s.mean(), s.std()
        if sigma > 1e-10:
            s = (s - mu) / sigma
        else:
            s = pd.Series(0.0, index=s.index)
        centrality.loc[idx, out_col] = s.fillna(0.0).values

print("Standardised centrality -- sample:")
print(
    centrality[
        ["symbol", "date", "eigenvector_centrality_std", "centrality_change_1m_std"]
    ]
    .head(10)
    .to_string(index=False)
)


# %%
out = "../data/processed/centrality_factors_monthly.parquet"
centrality.to_parquet(out, index=False)
print(f"Saved: {out}  shape={centrality.shape}")
print("Columns:", centrality.columns.tolist())
print("\n>> Centrality complete.")
