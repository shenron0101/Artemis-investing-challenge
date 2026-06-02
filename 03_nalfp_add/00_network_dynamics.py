"""00 — Time-Varying Network producer (MST + Louvain).

Upstream producer for stage 03. Runs first: it reads the stage-02 weekly
characteristics panel and writes `network_panel.parquet`, which supplies the
network factors (NetMom, NetRel, cluster_id, network_entropy) consumed by the
factor visualisations (stage 05) and the ensemble engine (stage 06).

For every Monday in the sample we look back W=12 weeks of weekly log returns,
compute the Spearman correlation across symbols with sufficient overlap, turn
correlations into the standard distance d_ij = sqrt(2 (1 - rho)), build the
Minimum Spanning Tree, run Louvain community detection on it, and emit three
asset-level signals plus a market-wide fragmentation signal:

    cluster_id          — Louvain community label at week t
    within_cluster_mom  — rank of asset's 4w return within its cluster (z-score)
    cross_cluster_rel   — asset 4w return − mean 4w return of *other* clusters
    network_entropy     — Shannon entropy of cluster-size distribution (scalar per week)

All quantities are computed using ONLY data through t-1 (strict no look-ahead);
they enter the IPCA panel as lagged characteristics.

Economic intuition. Spearman+MST is the canonical robust-correlation graph
filter for fat-tailed financial returns (Mantegna 1999, Onnela et al. 2003).
Louvain partitions the MST into communities of co-moving assets — these proxy
for narratives (DeFi blue chip, L1 majors, meme rotation, etc.). When the
entropy of cluster sizes is high, the market has many small disconnected
communities — a *fragmented* regime in which within-cluster relative value
matters most. When entropy is low, one or two giant components dominate — a
*risk-on / risk-off* regime in which latent common factors do the work.
"""
from __future__ import annotations

import sys
from pathlib import Path

import community as community_louvain  # python-louvain
import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import minimum_spanning_tree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _network_common import (
    DATA_DIR,
    MANIFEST_DIR,
    cs_zscore,
    load_characteristics,
    load_returns_wide,
    save_plotly,
    write_frame,
    write_json,
)

WINDOW_WEEKS = 12
MIN_OVERLAP = 8
LOUVAIN_RESOLUTION = 1.0
LOUVAIN_SEED = 0


def _corr_distance(corr: pd.DataFrame) -> pd.DataFrame:
    """d_ij = sqrt(2 (1 - rho_ij)) — Mantegna distance."""
    clipped = corr.clip(-1.0, 1.0)
    dist = np.sqrt(2.0 * (1.0 - clipped))
    np.fill_diagonal(dist.values, 0.0)
    return dist


def _build_mst(distance: pd.DataFrame) -> nx.Graph:
    """Minimum-spanning tree of the distance graph (returns weighted nx.Graph)."""
    sym = distance.index.tolist()
    mst_sparse = minimum_spanning_tree(distance.values)
    coo = mst_sparse.tocoo()
    g = nx.Graph()
    g.add_nodes_from(sym)
    for u, v, w in zip(coo.row, coo.col, coo.data):
        if w == 0:
            continue
        g.add_edge(sym[u], sym[v], weight=float(w))
    return g


def _louvain_partition(g: nx.Graph) -> dict[str, int]:
    """Edge weights in our MST are *distances*; Louvain expects similarity.
    Transform with sim = 1 / (1 + d) so closer pairs get larger similarity."""
    h = g.copy()
    for u, v, data in h.edges(data=True):
        data["weight"] = 1.0 / (1.0 + data["weight"])
    return community_louvain.best_partition(
        h, weight="weight", random_state=LOUVAIN_SEED, resolution=LOUVAIN_RESOLUTION
    )


def _shannon_entropy(labels: list[int]) -> float:
    if not labels:
        return 0.0
    counts = pd.Series(labels).value_counts(normalize=True).values
    return float(-(counts * np.log(counts + 1e-12)).sum())


def cluster_one_week(window: pd.DataFrame) -> tuple[pd.Series, float, int]:
    """Cluster symbols in a single 12-week return window.

    Returns (cluster_labels indexed by symbol, network_entropy, n_clusters)."""
    win = window.dropna(axis=1, thresh=MIN_OVERLAP)
    if win.shape[1] < 6:
        return pd.Series(dtype=float), np.nan, 0
    win = win.fillna(0.0)
    corr = win.corr(method="spearman")
    corr = corr.dropna(how="all").dropna(axis=1, how="all")
    if corr.empty:
        return pd.Series(dtype=float), np.nan, 0
    dist = _corr_distance(corr)
    g = _build_mst(dist)
    if g.number_of_edges() == 0:
        return pd.Series(dtype=float), np.nan, 0
    partition = _louvain_partition(g)
    labels = pd.Series(partition, name="cluster_id").astype(int)
    labels = labels.reindex(corr.index).dropna().astype(int)
    entropy = _shannon_entropy(labels.tolist())
    return labels, entropy, int(labels.nunique())


def build_network_panel(ret: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Walk the timeline and emit per-(week, symbol) cluster labels plus per-week network stats."""
    weeks = ret.index
    asset_rows: list[pd.DataFrame] = []
    market_rows: list[dict] = []
    for i, week in enumerate(weeks):
        if i < WINDOW_WEEKS - 1:
            continue
        # The window is the trailing W weeks ENDING at week t inclusive.
        # `ret_1w` at week t is the close-Monday-(t-1) → close-Monday-t return
        # so it is fully known on Monday t. Cluster labels at t are then used
        # to predict r_{t+1} (next-week return) via the IPCA model; this is
        # standard "characteristics-as-instruments" timing (Kelly et al. 2019)
        # and contains no look-ahead.
        window = ret.iloc[i - WINDOW_WEEKS + 1 : i + 1]
        labels, entropy, k = cluster_one_week(window)
        if labels.empty:
            continue
        asset_rows.append(pd.DataFrame({
            "week": week,
            "symbol": labels.index,
            "cluster_id": labels.values,
        }))
        market_rows.append({"week": week, "network_entropy": entropy, "n_clusters": k})
    if not asset_rows:
        return pd.DataFrame(columns=["week", "symbol", "cluster_id"]), pd.DataFrame()
    asset = pd.concat(asset_rows, ignore_index=True)
    market = pd.DataFrame(market_rows)
    return asset, market


def attach_signals(panel: pd.DataFrame, clusters: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    """Compute within_cluster_mom (rank z-score) and cross_cluster_rel."""
    out = panel.merge(clusters, on=["week", "symbol"], how="left")
    out = out.merge(market, on="week", how="left")

    # Within-cluster rank of mom_4w, normalised to z-score so it is comparable
    # across clusters of different sizes.
    def _rank_z(s: pd.Series) -> pd.Series:
        if s.notna().sum() <= 1:
            return s * 0.0
        r = s.rank(method="average")
        return cs_zscore(r)

    out["within_cluster_mom"] = (
        out.groupby(["week", "cluster_id"], dropna=False)["mom_4w"].transform(_rank_z)
    )

    # cross_cluster_rel = asset's mom_4w minus mean mom_4w of *other* clusters
    week_sum = out.groupby("week")["mom_4w"].transform("sum")
    week_count = out.groupby("week")["mom_4w"].transform("count")
    cluster_sum = out.groupby(["week", "cluster_id"], dropna=False)["mom_4w"].transform("sum")
    cluster_count = out.groupby(["week", "cluster_id"], dropna=False)["mom_4w"].transform("count")
    other_count = (week_count - cluster_count).replace(0, np.nan)
    other_mean = (week_sum - cluster_sum) / other_count
    out["cross_cluster_rel"] = out["mom_4w"] - other_mean
    return out


def _figure_signals_overview(out: pd.DataFrame) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    market = out.groupby("week").agg(
        n_clusters=("cluster_id", lambda s: s.dropna().nunique()),
        network_entropy=("network_entropy", "first"),
    ).reset_index()

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=("Cluster count (Louvain on MST)", "Network entropy"))
    fig.add_trace(go.Scatter(x=market["week"], y=market["n_clusters"], mode="lines+markers",
                             name="K", line=dict(color="#1f77b4")), row=1, col=1)
    fig.add_trace(go.Scatter(x=market["week"], y=market["network_entropy"], mode="lines+markers",
                             name="H", line=dict(color="#ff7f0e")), row=2, col=1)
    fig.update_layout(title="Pillar 1 — time-varying community structure", height=650, showlegend=False)
    save_plotly(fig, "network_overview", "01_network_dynamics")


def _figure_mst_snapshots(ret: pd.DataFrame, out: pd.DataFrame) -> None:
    """Three MST snapshots: train start, train end, OOS end."""
    import plotly.graph_objects as go

    weeks = sorted(out["week"].dropna().unique())
    if len(weeks) < 3:
        return
    picks = [weeks[2], weeks[len(weeks) // 2], weeks[-1]]
    for week in picks:
        idx = ret.index.searchsorted(pd.Timestamp(week))
        if idx < WINDOW_WEEKS - 1:
            continue
        window = ret.iloc[idx - WINDOW_WEEKS + 1 : idx + 1]
        win = window.dropna(axis=1, thresh=MIN_OVERLAP).fillna(0.0)
        if win.shape[1] < 6:
            continue
        corr = win.corr(method="spearman")
        dist = _corr_distance(corr)
        g = _build_mst(dist)
        partition = _louvain_partition(g)
        pos = nx.spring_layout(g, seed=42, weight="weight")

        edge_x: list[float] = []
        edge_y: list[float] = []
        for u, v in g.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]
        node_x = [pos[n][0] for n in g.nodes()]
        node_y = [pos[n][1] for n in g.nodes()]
        node_color = [partition.get(n, 0) for n in g.nodes()]
        node_text = list(g.nodes())

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", line=dict(color="#bbb", width=0.5), hoverinfo="none"))
        fig.add_trace(go.Scatter(
            x=node_x, y=node_y, mode="markers+text", text=node_text, textposition="top center",
            marker=dict(size=10, color=node_color, colorscale="Turbo", showscale=False),
            hovertemplate="%{text}<extra></extra>",
        ))
        fig.update_layout(title=f"MST + Louvain — week {pd.Timestamp(week).date()}",
                          xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False,
                          height=720)
        save_plotly(fig, f"mst_{pd.Timestamp(week).date()}", "01_network_dynamics")


def main() -> None:
    print("loading characteristics & returns ...")
    char = load_characteristics()
    ret = load_returns_wide()
    print(f"  panel weeks: {ret.shape[0]}, symbols: {ret.shape[1]}")

    print("clustering weekly windows ...")
    clusters, market = build_network_panel(ret)
    print(f"  clustered weeks: {clusters['week'].nunique()}, rows: {len(clusters)}")

    print("attaching signals ...")
    enriched = attach_signals(char[["week", "symbol", "mom_4w", "fwd_ret_1w"]], clusters, market)

    network_panel = enriched[[
        "week", "symbol", "cluster_id", "within_cluster_mom",
        "cross_cluster_rel", "network_entropy", "n_clusters", "mom_4w", "fwd_ret_1w",
    ]].copy()
    write_frame(network_panel, DATA_DIR / "network_panel")
    write_frame(market, DATA_DIR / "network_market")

    manifest = {
        "window_weeks": WINDOW_WEEKS,
        "min_overlap": MIN_OVERLAP,
        "louvain_resolution": LOUVAIN_RESOLUTION,
        "weeks_clustered": int(clusters["week"].nunique()),
        "min_clusters": int(market["n_clusters"].min()) if len(market) else None,
        "max_clusters": int(market["n_clusters"].max()) if len(market) else None,
        "mean_entropy": float(market["network_entropy"].mean()) if len(market) else None,
    }
    write_json(manifest, MANIFEST_DIR / "00_network_manifest.json")

    print("rendering figures ...")
    _figure_signals_overview(network_panel)
    _figure_mst_snapshots(ret, network_panel)
    print("done.")


if __name__ == "__main__":
    main()
