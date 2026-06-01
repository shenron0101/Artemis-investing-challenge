"""Visualise the coin correlation network behind NetMom / NetRel.

Uses the SAME pipeline as 09_nalfp_add/08_factor_validation.py:
    Spearman corr  ->  distance sqrt(2(1-corr))  ->  MST  ->  Louvain communities.

Data: 07_hidden_factor_pricing/.../weekly_asset_panel.parquet (week, symbol, ret_1w),
a real 52-week crypto panel from this project. This is an *illustrative* snapshot
(the production factor rebuilds the graph on a rolling 12-week window); the
construction logic is identical.

Outputs two PNGs into figures/:
    network_clusters.png        the Louvain-clustered MST network
    netmom_netrel_schematic.png the same layout annotated to show what the two
                                network factors actually compute
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
from scipy.sparse.csgraph import minimum_spanning_tree
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "07_hidden_factor_pricing/artifacts/data/weekly_asset_panel.parquet"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

# things that are not "coins moving on crypto narratives" — exclude like the universe does
EXCLUDE = {
    "USDT", "USDC", "DAI", "TUSD", "USDD", "FDUSD", "USDE",        # stablecoins
    "XAUT", "PAXG", "EUTBL", "BUIDL", "USYC", "OUSG",              # tokenised RWA / gold
    "WBTC", "WETH", "WBETH", "STETH", "WEETH", "WSTETH",           # wrapped / LST
    "LEO", "OKB", "KCS", "GT", "BGB", "CRO", "BNB", "DEXE", "BDX", # exchange tokens (keep BNB? drop to reduce clutter)
}


def cluster(returns_wide: pd.DataFrame):
    """corr -> distance -> MST -> Louvain. Returns (graph, labels dict)."""
    corr = returns_wide.corr(method="spearman").dropna(how="all").dropna(axis=1, how="all")
    syms = list(corr.columns)
    dist = np.sqrt(np.clip(2 * (1 - corr.values), 0, None))
    mst = minimum_spanning_tree(dist).toarray()
    g = nx.Graph()
    g.add_nodes_from(syms)
    for i in range(len(syms)):
        for j in range(len(syms)):
            if mst[i, j] > 0:
                # edge weight ~ correlation strength (shorter MST distance = stronger link)
                g.add_edge(syms[i], syms[j], weight=1.0 / (mst[i, j] + 1e-6),
                           dist=float(mst[i, j]))
    parts = nx.community.louvain_communities(g, weight="weight", seed=0)
    labels = {s: k for k, com in enumerate(parts) for s in com}
    return g, labels, parts


def cluster_label(i: int, members) -> str:
    """Neutral label + a few representative members (data-driven clusters over a
    short window won't match canonical human narratives, so we don't overclaim)."""
    letter = chr(ord("A") + i)
    reps = ", ".join(sorted(members)[:4])
    return f"Cluster {letter} (e.g. {reps})"


def main():
    df = pd.read_parquet(PANEL)
    df["week"] = pd.to_datetime(df["week"])
    wide = df.pivot(index="week", columns="symbol", values="ret_1w")
    keep = [c for c in wide.columns if c not in EXCLUDE and wide[c].notna().sum() >= 50]
    wide = wide[keep].dropna(axis=0, how="any")
    print(f"network on {wide.shape[1]} coins x {wide.shape[0]} weeks "
          f"({wide.index.min().date()} -> {wide.index.max().date()})")

    g, labels, parts = cluster(wide)
    parts = sorted(parts, key=len, reverse=True)              # biggest cluster first
    cl_name = {i: cluster_label(i, set(p)) for i, p in enumerate(parts)}
    cl_short = {i: f"Cluster {chr(ord('A')+i)}" for i in range(len(parts))}
    member_cl = {s: i for i, p in enumerate(parts) for s in p}

    # 4-week momentum at the last week, for node sizing + factor illustration
    mom = (1 + wide).tail(4).prod() - 1            # trailing 4-week cumulative return
    pos = nx.spring_layout(g, seed=7, k=0.9, iterations=300)

    palette = plt.cm.Set2(np.linspace(0, 1, max(8, len(parts))))
    node_colors = [palette[member_cl[n]] for n in g.nodes()]

    # ---------- Figure 1: the clustered network ----------
    fig, ax = plt.subplots(figsize=(13, 9))
    nx.draw_networkx_edges(g, pos, ax=ax, alpha=0.35, width=1.2, edge_color="#888")
    sizes = 300 + 1400 * (mom.reindex(g.nodes()).fillna(0).clip(-0.5, 1.0) + 0.5)
    nx.draw_networkx_nodes(g, pos, ax=ax, node_color=node_colors,
                           node_size=sizes.values, edgecolors="white", linewidths=1.5)
    nx.draw_networkx_labels(g, pos, ax=ax, font_size=8, font_weight="bold")

    # cluster legend
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=palette[i], edgecolor="white",
                     label=f"{cl_name[i]}  ({len(p)} coins)")
               for i, p in enumerate(parts)]
    ax.legend(handles=handles, loc="upper left", fontsize=10, title="Louvain clusters",
              frameon=True, framealpha=0.9)
    ax.set_title("Coin correlation network — Spearman → distance → MST → Louvain clusters\n"
                 f"(illustrative 52-week snapshot, {wide.index.min().date()}→{wide.index.max().date()}; "
                 "node size = trailing 4-week return)", fontsize=12)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIG / "network_clusters.png", dpi=140)
    plt.close(fig)
    print(f"wrote {FIG/'network_clusters.png'}")

    # ---------- Figure 2: NetMom vs NetRel schematic on the same layout ----------
    # Pick the most populated cluster as the "focus" cluster for the illustration.
    focus = 0
    focus_members = [n for n in g.nodes() if member_cl[n] == focus]
    # within-cluster: rank the focus coins by their own 4w momentum
    fmom = mom.reindex(focus_members).sort_values(ascending=False)
    leader, laggard = fmom.index[0], fmom.index[-1]
    # cross-cluster: cluster-average momentum
    cl_avg = {i: float(mom.reindex([n for n in g.nodes() if member_cl[n] == i]).mean())
              for i in range(len(parts))}
    hot_cl = max(cl_avg, key=cl_avg.get)
    cold_cl = min(cl_avg, key=cl_avg.get)

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(19, 9))

    # ---- LEFT: NetMom (within-cluster) ----
    ax = axL
    # dim everything, highlight the focus cluster
    other_nodes = [n for n in g.nodes() if member_cl[n] != focus]
    nx.draw_networkx_edges(g, pos, ax=ax, alpha=0.12, width=1.0, edge_color="#bbb")
    nx.draw_networkx_nodes(g, pos, ax=ax, nodelist=other_nodes,
                           node_color="#dddddd", node_size=240, edgecolors="white")
    nx.draw_networkx_nodes(g, pos, ax=ax, nodelist=focus_members,
                           node_color=[palette[focus]] * len(focus_members),
                           node_size=620, edgecolors="white", linewidths=1.5)
    nx.draw_networkx_labels(g, pos, ax=ax,
                            labels={n: n for n in focus_members}, font_size=9, font_weight="bold")
    # mark leader (long, label above) and laggard (short, label below) with a
    # boxed callout offset away from the node cloud to avoid overlap
    for sym, tag, col, dy, va in [(leader, "LONG  (local leader)", "#1a8f3c", 70, "bottom"),
                                  (laggard, "SHORT (local laggard)", "#c0392b", -70, "top")]:
        x, y = pos[sym]
        ax.scatter([x], [y], s=1500, facecolors="none", edgecolors=col, linewidths=3.5, zorder=5)
        ax.annotate(f"{tag}\n{sym}: 4w mom {mom[sym]:+.0%}", (x, y),
                    textcoords="offset points", xytext=(0, dy), ha="center", va=va,
                    fontsize=11, color="white", fontweight="bold", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.4", fc=col, ec="white", lw=1.5),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=2.5))
    ax.set_title(f"NetMom — WITHIN-cluster momentum\nInside {cl_short[focus]}: "
                 "long the coin out-trending its OWN clustermates, short the laggard\n"
                 "(strips out the shared cluster move → isolates idiosyncratic trend)",
                 fontsize=12)
    ax.axis("off")

    # ---- RIGHT: NetRel (cross-cluster) ----
    ax = axR
    nx.draw_networkx_edges(g, pos, ax=ax, alpha=0.15, width=1.0, edge_color="#bbb")
    # colour each node by its cluster, but emphasize hot vs cold clusters
    base = ["#e3e3e3"] * g.number_of_nodes()
    cols = []
    for n in g.nodes():
        if member_cl[n] == hot_cl:
            cols.append("#1a8f3c")
        elif member_cl[n] == cold_cl:
            cols.append("#c0392b")
        else:
            cols.append("#d9d9d9")
    nx.draw_networkx_nodes(g, pos, ax=ax, node_color=cols, node_size=360,
                           edgecolors="white", linewidths=1.0)
    nx.draw_networkx_labels(g, pos, ax=ax, font_size=7)
    # centroid arrows: hot cluster pulling ahead of the rest
    def centroid(i):
        xs = np.array([pos[n] for n in g.nodes() if member_cl[n] == i])
        return xs.mean(axis=0)
    ch, cc = centroid(hot_cl), centroid(cold_cl)
    ax.annotate(f"LONG the leading cluster\n{cl_short[hot_cl]}: avg 4w mom {cl_avg[hot_cl]:+.0%}",
                ch, textcoords="offset points", xytext=(0, 30), ha="center", va="bottom",
                fontsize=11, color="white", fontweight="bold", zorder=6,
                bbox=dict(boxstyle="round,pad=0.4", fc="#1a8f3c", ec="white", lw=1.5),
                arrowprops=dict(arrowstyle="-|>", color="#1a8f3c", lw=2.5))
    ax.annotate(f"SHORT the lagging cluster\n{cl_short[cold_cl]}: avg 4w mom {cl_avg[cold_cl]:+.0%}",
                cc, textcoords="offset points", xytext=(0, -34), ha="center", va="top",
                fontsize=11, color="white", fontweight="bold", zorder=6,
                bbox=dict(boxstyle="round,pad=0.4", fc="#c0392b", ec="white", lw=1.5),
                arrowprops=dict(arrowstyle="-|>", color="#c0392b", lw=2.5))
    ax.set_title("NetRel — CROSS-cluster rotation\nLong coins whose cluster is out-running the "
                 "OTHER clusters, short coins in the lagging cluster\n"
                 "(captures capital rotating between narratives)", fontsize=12)
    ax.axis("off")

    fig.tight_layout()
    fig.savefig(FIG / "netmom_netrel_schematic.png", dpi=140)
    plt.close(fig)
    print(f"wrote {FIG/'netmom_netrel_schematic.png'}")

    # print cluster membership for the doc caption
    print("\nClusters found:")
    for i, p in enumerate(parts):
        print(f"  [{cl_name[i]}] {', '.join(sorted(p))}")


if __name__ == "__main__":
    main()
