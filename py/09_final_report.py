"""
09_final_report.py
Two-page visual research brief.  Saves reports/final_report.pdf
"""
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import TwoSlopeNorm
from matplotlib.ticker import FuncFormatter

warnings.filterwarnings("ignore")

# ── colour palette ────────────────────────────────────────────────────────────
BG      = "#0f1117"
PANEL   = "#1a1d27"
BORDER  = "#2a2d3a"
TEXT    = "#e8eaf0"
MUTED   = "#8b90a0"
ACCENT  = "#4f8ef7"       # blue
GREEN   = "#36c794"
ORANGE  = "#f5a623"
RED     = "#e05263"
YELLOW  = "#f7d94f"

VARIANT_STYLE = {
    "v4_full_cluster":  (GREEN,  "Cluster+Factor",   2.0),
    "v5_regime_aware":  (ACCENT, "Regime-Aware",     2.4),
    "BTC":              (MUTED,  "BTC Buy-Hold",     1.4),
}

def pct(x, _): return f"{x:.0%}"
def dark_ax(ax):
    ax.set_facecolor(PANEL)
    ax.spines[:].set_color(BORDER)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    return ax


# ── load data ─────────────────────────────────────────────────────────────────
art      = pd.read_parquet("../data/processed/panel_artemis_daily.parquet")
weights  = pd.read_parquet("../data/processed/portfolio_weights_monthly.parquet")
regime   = pd.read_parquet("../data/processed/macro_regime_monthly.parquet")
ic_df    = pd.read_csv("../data/processed/factor_ic_results.csv")
clusters = pd.read_parquet("../data/processed/network_clusters_monthly.parquet")

art["date"]     = pd.to_datetime(art["date"])
weights["date"] = pd.to_datetime(weights["date"])
regime["date"]  = pd.to_datetime(regime["date"])

price_w = art.pivot_table(index="date", columns="symbol", values="price", aggfunc="last")
rebal   = sorted(weights["date"].unique())


# ── reconstruct monthly return series ─────────────────────────────────────────
def last_px(t, sym):
    if sym not in price_w.columns:
        return np.nan
    v = price_w[sym].loc[:t].dropna()
    return float(v.iloc[-1]) if len(v) else np.nan

ret_series = {}
for var in ["v4_full_cluster", "v5_regime_aware"]:
    w_var = weights[weights["variant"] == var]
    rets, dates = [], []
    for i, t in enumerate(rebal[:-1]):
        t1 = rebal[i + 1]
        syms = [s for s in w_var[w_var["date"] == t]["symbol"].tolist()
                if s in price_w.columns]
        p0 = price_w.reindex(columns=syms).loc[:t].ffill().iloc[-1]
        p1 = price_w.reindex(columns=syms).loc[:t1].ffill().iloc[-1]
        fwd = (p1 / p0.replace(0, np.nan)) - 1
        wts = w_var[w_var["date"] == t].set_index("symbol")["weight"].reindex(syms).fillna(0)
        rets.append(float((fwd * wts).sum()) if float(wts.sum()) != 0 else 0.0)
        dates.append(t)
    ret_series[var] = pd.Series(rets, index=dates)

btc_rets = []
for i, t in enumerate(rebal[:-1]):
    t1 = rebal[i + 1]
    p0, p1 = last_px(t, "BTC"), last_px(t1, "BTC")
    btc_rets.append(float(p1 / p0 - 1) if p0 and p1 and p0 != 0 else 0.0)
ret_series["BTC"] = pd.Series(btc_rets, index=rebal[:-1])

cum = {k: (1 + v).cumprod() for k, v in ret_series.items()}

def stats(v):
    c = (1 + v).cumprod()
    n = len(v)
    ar = c.iloc[-1] ** (12 / n) - 1
    av = v.std() * np.sqrt(12)
    sr = ar / av if av > 1e-6 else 0
    md = float(((c / c.cummax()) - 1).min())
    hr = (v > 0).mean()
    return ar, av, sr, md, hr

perf = {k: stats(v) for k, v in ret_series.items()}


# ── IC data prep ──────────────────────────────────────────────────────────────
FACTOR_LABELS = {
    "corr_density":              "Crowding Density",
    "dau_growth_30d":            "DAU Growth 30d",
    "vol_30d":                   "Realised Volatility",
    "within_cluster_rank":       "Within-Cluster Rank",
    "dau_zscore":                "DAU Z-Score",
    "rev_mc":                    "Revenue / Mkt Cap",
    "fees_mc":                   "Fees / Mkt Cap",
    "mom_1m":                    "Momentum 1m",
    "mom_3m":                    "Momentum 3m",
    "rev_growth_30d":            "Revenue Growth 30d",
    "fees_growth_30d":           "Fees Growth 30d",
    "txns_growth_30d":           "Txns Growth 30d",
    "eigenvector_centrality_std":"Eigenvector Centrality",
    "centrality_change_1m_std":  "Centrality Change 1m",
    "tvl_mc":                    "TVL / Mkt Cap",
    "tvl_growth_30d":            "TVL Growth 30d",
    "mom_6m":                    "Momentum 6m",
}

ic_plot = ic_df[["Factor", "t-stat", "IC_loose", "IC_neutral", "IC_tight"]].copy()
ic_plot["label"] = ic_plot["Factor"].map(FACTOR_LABELS).fillna(ic_plot["Factor"])
ic_plot = ic_plot.dropna(subset=["t-stat"]).sort_values("t-stat")

# heatmap: rows = factors, cols = regime
hm_factors = ["corr_density", "dau_growth_30d", "vol_30d", "within_cluster_rank",
               "dau_zscore", "rev_mc", "fees_mc", "mom_1m", "rev_growth_30d",
               "fees_growth_30d", "txns_growth_30d"]
hm_df = ic_df.set_index("Factor").reindex(hm_factors)[["IC_loose", "IC_neutral", "IC_tight"]]
hm_labels = [FACTOR_LABELS.get(f, f) for f in hm_factors]


# ── PDF layout ────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":      "DejaVu Sans",
    "text.color":       TEXT,
    "axes.labelcolor":  MUTED,
    "xtick.color":      MUTED,
    "ytick.color":      MUTED,
    "figure.facecolor": BG,
    "axes.facecolor":   PANEL,
    "axes.edgecolor":   BORDER,
    "grid.color":       BORDER,
    "grid.linewidth":   0.5,
    "legend.framealpha": 0.0,
    "legend.labelcolor": TEXT,
})

out_path = "../reports/final_report.pdf"

with PdfPages(out_path) as pdf:

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1
    # ══════════════════════════════════════════════════════════════════════════
    fig = plt.figure(figsize=(11, 8.5), facecolor=BG)
    gs  = gridspec.GridSpec(3, 3, figure=fig,
                            top=0.88, bottom=0.07, left=0.07, right=0.97,
                            hspace=0.45, wspace=0.35)

    # ── header ────────────────────────────────────────────────────────────────
    fig.text(0.07, 0.95, "Artemis Quant Competition — Crypto Cross-Sectional Strategy",
             color=TEXT, fontsize=14, fontweight="bold", va="top")
    fig.text(0.07, 0.915,
             "Macro regime × correlation network × on-chain fundamentals  |  Monthly rebalance, Top-50 universe  |  2021–2024",
             color=MUTED, fontsize=8.5, va="top")
    fig.add_artist(plt.Line2D([0.07, 0.97], [0.905, 0.905],
                              transform=fig.transFigure,
                              color=BORDER, linewidth=0.8))

    # ── cumulative returns (full width top row) ────────────────────────────────
    ax_cum = fig.add_subplot(gs[0, :])
    dark_ax(ax_cum)
    for var, (col, lbl, lw) in VARIANT_STYLE.items():
        s = cum[var]
        ax_cum.plot(s.index, s.values, color=col, linewidth=lw, label=lbl, zorder=3)

    # shade regime bands
    reg_map = regime.set_index("date")["regime"]
    for i, t in enumerate(rebal[:-1]):
        t1 = rebal[i + 1]
        reg = reg_map.reindex([t]).ffill().iloc[0] if t in reg_map.index else "neutral"
        shade = {"loose": GREEN, "tight": RED, "neutral": BG}[reg]
        ax_cum.axvspan(t, t1, color=shade, alpha=0.07, zorder=0)

    ax_cum.axhline(1, color=BORDER, linewidth=0.8, linestyle="--")
    ax_cum.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.1f}x"))
    ax_cum.set_title("Cumulative Return (1x = 1.0)", color=MUTED, fontsize=8,
                     loc="left", pad=6)
    ax_cum.legend(loc="upper left", fontsize=8, ncol=3)
    ax_cum.grid(axis="y", zorder=0)

    # combine strategy lines + regime band legend entries
    handles, labels_l = ax_cum.get_legend_handles_labels()
    handles += [mpatches.Rectangle((0, 0), 1, 1, color=GREEN, alpha=0.3),
                mpatches.Rectangle((0, 0), 1, 1, color=RED,   alpha=0.3)]
    labels_l += ["Loose regime", "Tight regime"]
    ax_cum.legend(handles, labels_l, loc="upper left", fontsize=7.5, ncol=5)

    # ── performance table ──────────────────────────────────────────────────────
    ax_tbl = fig.add_subplot(gs[1:, :2])
    ax_tbl.set_facecolor(PANEL)
    ax_tbl.axis("off")

    rows  = list(VARIANT_STYLE.keys())
    cols  = ["CAGR", "Ann Vol", "Sharpe", "Max DD", "Hit Rate"]
    data  = []
    for k in rows:
        ar, av, sr, md, hr = perf[k]
        data.append([f"{ar:.1%}", f"{av:.1%}", f"{sr:.2f}", f"{md:.1%}", f"{hr:.0%}"])
    rlbls = [VARIANT_STYLE[k][1] for k in rows]
    colors_row = [[PANEL]*5 for _ in rows]
    # highlight best sharpe cell
    sharpes = [perf[k][2] for k in rows]
    best_sr = sharpes.index(max(sharpes))
    colors_row[best_sr][2] = "#1e3a2a"  # subtle green tint

    tbl = ax_tbl.table(
        cellText=data, rowLabels=rlbls, colLabels=cols,
        cellLoc="center", loc="center",
        cellColours=colors_row,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.5)
    tbl.scale(1, 1.7)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor(BORDER)
        cell.set_text_props(color=TEXT)
        if r == 0:
            cell.set_text_props(color=MUTED, fontweight="bold")
            cell.set_facecolor(BG)
        if c == -1:
            cell.set_text_props(color=ACCENT if r > 0 else MUTED,
                                fontweight="bold" if r > 0 else "normal")
            cell.set_facecolor(PANEL)

    ax_tbl.set_title("Strategy Performance  |  Jan 2021 – Dec 2024",
                     color=MUTED, fontsize=8, loc="left", pad=8)

    # ── macro regime pie ───────────────────────────────────────────────────────
    ax_pie = fig.add_subplot(gs[1, 2])
    dark_ax(ax_pie)
    reg_counts = regime["regime"].value_counts().reindex(["loose", "neutral", "tight"])
    pie_colors = [GREEN, YELLOW, RED]
    wedges, texts, autotexts = ax_pie.pie(
        reg_counts.values,
        labels=[f"{l.capitalize()}\n{v} months" for l, v in reg_counts.items()],
        colors=pie_colors,
        autopct="%1.0f%%",
        startangle=90,
        textprops={"color": MUTED, "fontsize": 7.5},
        wedgeprops={"edgecolor": BG, "linewidth": 1.5},
    )
    for at in autotexts:
        at.set_color(BG)
        at.set_fontweight("bold")
        at.set_fontsize(8)
    ax_pie.set_title("Macro Regime\nDistribution", color=MUTED, fontsize=8, pad=6)

    # ── corr density over time ─────────────────────────────────────────────────
    ax_crowd = fig.add_subplot(gs[2, 2])
    dark_ax(ax_crowd)
    cd = clusters.groupby("date")["corr_density"].mean().reset_index()
    cd["date"] = pd.to_datetime(cd["date"])
    ax_crowd.fill_between(cd["date"], cd["corr_density"],
                          color=ORANGE, alpha=0.4, linewidth=0)
    ax_crowd.plot(cd["date"], cd["corr_density"], color=ORANGE, linewidth=1.5)
    ax_crowd.set_ylim(0, 1)
    ax_crowd.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.1f}"))
    ax_crowd.set_title("Avg Cluster Crowding\n(mean intra-cluster ρ)",
                       color=MUTED, fontsize=8, pad=6)
    ax_crowd.grid(axis="y")

    plt.suptitle("", y=0)
    pdf.savefig(fig, facecolor=BG, bbox_inches="tight")
    plt.close(fig)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2
    # ══════════════════════════════════════════════════════════════════════════
    fig2 = plt.figure(figsize=(11, 8.5), facecolor=BG)
    gs2  = gridspec.GridSpec(2, 2, figure=fig2,
                             top=0.88, bottom=0.07, left=0.07, right=0.97,
                             hspace=0.50, wspace=0.38)

    fig2.text(0.07, 0.95, "Factor Evidence — Cross-Sectional IC & Regime Conditioning",
              color=TEXT, fontsize=14, fontweight="bold", va="top")
    fig2.text(0.07, 0.915,
              "Spearman IC against next-month returns  |  47 rebalance periods  |  Each factor cross-sectionally standardised",
              color=MUTED, fontsize=8.5, va="top")
    fig2.add_artist(plt.Line2D([0.07, 0.97], [0.905, 0.905],
                               transform=fig2.transFigure,
                               color=BORDER, linewidth=0.8))

    # ── IC heatmap (regime-conditional) ───────────────────────────────────────
    ax_hm = fig2.add_subplot(gs2[:, 0])
    dark_ax(ax_hm)

    hm_vals = hm_df.values.astype(float)
    vmax = np.nanmax(np.abs(hm_vals))
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
    im = ax_hm.imshow(hm_vals, cmap="RdYlGn", norm=norm, aspect="auto")

    ax_hm.set_xticks([0, 1, 2])
    ax_hm.set_xticklabels(["Loose", "Neutral", "Tight"], color=TEXT, fontsize=9)
    ax_hm.set_yticks(range(len(hm_labels)))
    ax_hm.set_yticklabels(hm_labels, color=TEXT, fontsize=8.5)
    ax_hm.tick_params(left=False, bottom=False)

    for i in range(len(hm_factors)):
        for j in range(3):
            val = hm_vals[i, j]
            if np.isnan(val):
                txt = "—"
                c = MUTED
            else:
                txt = f"{val:+.3f}"
                c = BG if abs(val) > vmax * 0.45 else TEXT
            ax_hm.text(j, i, txt, ha="center", va="center",
                       color=c, fontsize=8, fontweight="bold")

    cb = plt.colorbar(im, ax=ax_hm, fraction=0.04, pad=0.04)
    cb.ax.tick_params(labelcolor=MUTED, labelsize=7)
    cb.set_label("Spearman IC", color=MUTED, fontsize=7.5)
    ax_hm.set_title("Regime-Conditional IC\n(green = predicts higher returns)",
                    color=MUTED, fontsize=8.5, loc="left", pad=8)

    # ── t-stat bar chart ───────────────────────────────────────────────────────
    ax_bar = fig2.add_subplot(gs2[0, 1])
    dark_ax(ax_bar)

    bar_df = ic_plot.copy()
    bar_colors = [GREEN if x > 0 else RED for x in bar_df["t-stat"]]
    bars = ax_bar.barh(bar_df["label"], bar_df["t-stat"],
                       color=bar_colors, edgecolor=BG, linewidth=0.5, height=0.65)
    ax_bar.axvline(0, color=MUTED, linewidth=0.8)
    ax_bar.axvline(1.65, color=YELLOW, linewidth=0.8, linestyle="--", alpha=0.7)
    ax_bar.axvline(-1.65, color=YELLOW, linewidth=0.8, linestyle="--", alpha=0.7)
    ax_bar.text(1.65, len(bar_df) - 0.3, " 90% conf.", color=YELLOW,
                fontsize=6.5, va="top")
    ax_bar.set_xlabel("t-statistic", fontsize=8)
    ax_bar.set_title("Factor t-Statistics\n(full sample, 47 periods)",
                     color=MUTED, fontsize=8.5, loc="left", pad=6)
    ax_bar.grid(axis="x", zorder=0)
    ax_bar.tick_params(axis="y", labelsize=7.5)

    # ── key findings text box ─────────────────────────────────────────────────
    ax_txt = fig2.add_subplot(gs2[1, 1])
    ax_txt.set_facecolor(PANEL)
    ax_txt.axis("off")
    ax_txt.set_xlim(0, 1)
    ax_txt.set_ylim(0, 1)

    findings = [
        ("CROWDING DENSITY  |  t = +1.97",
         "High intra-cluster correlation predicts outperformance\n"
         "consistently across all regimes (loose +0.04, tight +0.07).\n"
         "Crowded clusters sustain momentum; fragmented ones mean-revert.",
         GREEN),
        ("USAGE (DAU GROWTH)  |  t = +1.39",
         "On-chain user growth adds predictive power beyond price.\n"
         "Signal is stronger in tight regimes (+0.03) where\n"
         "fundamentals separate survivors from noise.",
         ACCENT),
        ("VOLATILITY  |  t = −3.27",
         "High realised vol strongly predicts underperformance.\n"
         "Effect is most severe in neutral regimes (IC −0.19);\n"
         "tight-regime drawdowns are somewhat less concentrated.",
         RED),
        ("MOMENTUM REGIME FLIP",
         "Momentum IC is negative in loose regimes (−0.07)\n"
         "and positive in tight (+0.03). Cross-sectional\n"
         "momentum only earns when capital is constrained.",
         YELLOW),
    ]

    y = 0.97
    for title, body, col in findings:
        ax_txt.text(0.02, y, title, color=col, fontsize=7.5,
                    fontweight="bold", va="top", transform=ax_txt.transAxes)
        y -= 0.055
        ax_txt.text(0.02, y, body, color=TEXT, fontsize=7.0,
                    va="top", transform=ax_txt.transAxes,
                    linespacing=1.5)
        y -= 0.175
        ax_txt.axhline(y=y + 0.025, xmin=0.02, xmax=0.98,
                       color=BORDER, linewidth=0.5)
        y -= 0.01

    ax_txt.set_title("Key Research Findings", color=MUTED, fontsize=8.5,
                     loc="left", pad=8)

    pdf.savefig(fig2, facecolor=BG, bbox_inches="tight")
    plt.close(fig2)

print(f"Saved: {out_path}")
print(">> Final report complete.")
