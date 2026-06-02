"""03 — Network / community features from rolling return correlations.

Minimum viable network layer: at every week t we look back W=26 weeks of
weekly log returns, compute the pairwise correlation matrix across symbols
with sufficient overlap, and cluster the rows with KMeans on the top
correlation eigenvectors. Cluster labels are then used to build two features:

    cluster_id            — categorical cluster label at week t
    within_cluster_mom    — average mom_4w of other cluster members at t
    cross_cluster_rel     — own mom_4w minus mean mom_4w of *other* clusters

This is the placeholder for a richer time-varying network (e.g. the
predictive-link Granger-style structure from the time-varying network paper).
The interface — adding network features to the long panel — stays stable when
the upstream computation changes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, MANIFEST_DIR, write_frame, write_json

INPUT_CHARACTERISTICS = DATA_DIR / "characteristics.parquet"

WINDOW_WEEKS = 26
MIN_OVERLAP = 16
N_CLUSTERS = 5
N_COMPONENTS = 8


def returns_wide(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.pivot_table(index="week", columns="symbol", values="ret_1w", aggfunc="last")
        .sort_index()
    )


def momentum_wide(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.pivot_table(index="week", columns="symbol", values="mom_4w", aggfunc="last")
        .sort_index()
    )


def cluster_one_week(window: pd.DataFrame) -> pd.Series:
    """Cluster symbols based on their column vectors in `window` (returns matrix).

    Drops columns with too few non-null observations in the window before
    correlating. Returns a Series of cluster labels indexed by symbol; symbols
    not eligible for clustering get NaN.
    """
    win = window.dropna(axis=1, thresh=MIN_OVERLAP).copy()
    if win.shape[1] < N_CLUSTERS + 1:
        return pd.Series(dtype=float)

    win = win.fillna(0.0)
    corr = win.corr()
    corr = corr.dropna(how="all").dropna(axis=1, how="all")
    if corr.empty or corr.shape[0] < N_CLUSTERS + 1:
        return pd.Series(dtype=float)

    n_comp = min(N_COMPONENTS, max(2, corr.shape[0] - 1))
    svd = TruncatedSVD(n_components=n_comp, random_state=0)
    embed = svd.fit_transform(corr.fillna(0.0).values)
    k = min(N_CLUSTERS, embed.shape[0])
    km = KMeans(n_clusters=k, n_init=10, random_state=0)
    labels = km.fit_predict(embed)
    return pd.Series(labels, index=corr.index, name="cluster_id")


def build_clusters(ret: pd.DataFrame) -> pd.DataFrame:
    """Return long frame: (week, symbol, cluster_id)."""
    weeks = ret.index
    out_rows: list[pd.DataFrame] = []
    for i, week in enumerate(weeks):
        if i < WINDOW_WEEKS - 1:
            continue
        window = ret.iloc[i - WINDOW_WEEKS + 1 : i + 1]
        labels = cluster_one_week(window)
        if labels.empty:
            continue
        out_rows.append(
            pd.DataFrame(
                {"week": week, "symbol": labels.index, "cluster_id": labels.values}
            )
        )
    if not out_rows:
        return pd.DataFrame(columns=["week", "symbol", "cluster_id"])
    return pd.concat(out_rows, ignore_index=True)


def add_cluster_features(panel: pd.DataFrame, clusters: pd.DataFrame) -> pd.DataFrame:
    """Attach within-cluster and cross-cluster momentum spreads to the panel."""
    out = panel.merge(clusters, on=["week", "symbol"], how="left")

    by_wc = out.groupby(["week", "cluster_id"])["mom_4w"]
    cluster_mom_sum = by_wc.transform("sum")
    cluster_mom_count = by_wc.transform("count")
    # leave-one-out mean of mom_4w inside the cluster (excludes the asset itself)
    out["within_cluster_mom"] = (cluster_mom_sum - out["mom_4w"].fillna(0)) / (
        cluster_mom_count - out["mom_4w"].notna().astype(int)
    ).replace(0, np.nan)

    week_mom_sum = out.groupby("week")["mom_4w"].transform("sum")
    week_mom_count = out.groupby("week")["mom_4w"].transform("count")
    other_clusters_mean = (week_mom_sum - cluster_mom_sum) / (
        week_mom_count - cluster_mom_count
    ).replace(0, np.nan)
    out["cross_cluster_rel"] = out["mom_4w"] - other_clusters_mean

    return out


def main() -> None:
    panel = pd.read_parquet(INPUT_CHARACTERISTICS)
    ret = returns_wide(panel)
    clusters = build_clusters(ret)
    out = add_cluster_features(panel, clusters)

    keep_cols = ["week", "symbol", "cluster_id", "within_cluster_mom", "cross_cluster_rel"]
    network_only = out[keep_cols].copy()
    write_frame(network_only, DATA_DIR / "network_features")
    write_json(
        {
            "window_weeks": WINDOW_WEEKS,
            "min_overlap": MIN_OVERLAP,
            "n_clusters": N_CLUSTERS,
            "n_components": N_COMPONENTS,
            "weeks_clustered": int(network_only["cluster_id"].notna().any()) and int(
                network_only.dropna(subset=["cluster_id"])["week"].nunique()
            ),
            "rows_with_cluster": int(network_only["cluster_id"].notna().sum()),
        },
        MANIFEST_DIR / "03_network_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
