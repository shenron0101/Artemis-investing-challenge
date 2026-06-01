"""Render slide-deck tables as PNGs."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "table_pngs"
OUT.mkdir(exist_ok=True)

# ── Color palette (matches LaTeX report) ─────────────────────────────
BG       = "#F5F0E8"
HEAD_BG  = "#5C4A32"
HEAD_FG  = "#FFFFFF"
ROW_EVEN = "#F5F0E8"
ROW_ODD  = "#EDE6D8"
TEXT     = "#3B3022"
ACCENT   = "#8B7355"
BORDER   = "#A89880"
GREEN    = "#2E7D32"
RED      = "#C62828"

def color_val(v):
    """Return green/red for positive/negative numeric strings."""
    s = str(v).strip().replace("~", "").replace("≈", "")
    if s.startswith("+") or (s.replace(".", "").replace("%", "").lstrip("-").isdigit() and not s.startswith("-") and not s.startswith("—")):
        if s.startswith("+"):
            return GREEN
    if s.startswith("-") or s.startswith("−"):
        return RED
    return TEXT

def render_table(headers, rows, filename, title=None, footer=None,
                 col_widths=None, figscale=1.0, color_cols=None):
    """Render a table to PNG."""
    n_cols = len(headers)
    n_rows = len(rows)

    if col_widths is None:
        col_widths = [1.0 / n_cols] * n_cols

    fig_w = 14 * figscale
    row_h = 0.48
    header_h = 0.55
    fig_h = header_h + n_rows * row_h + 0.6
    if title:
        fig_h += 0.5
    if footer:
        fig_h += 0.45

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(BG)

    # Normalize col_widths
    total = sum(col_widths)
    col_widths = [w / total for w in col_widths]

    # Compute positions
    y_top = 0.95
    if title:
        ax.text(0.5, y_top, title, ha="center", va="top",
                fontsize=14, fontweight="bold", color=HEAD_BG,
                fontfamily="sans-serif")
        y_top -= 0.06

    # Header
    x = 0.02
    header_y = y_top
    header_bottom = header_y - 0.06

    # Draw header background
    from matplotlib.patches import FancyBboxPatch, Rectangle
    rect = Rectangle((0.01, header_bottom), 0.98, header_y - header_bottom,
                      facecolor=HEAD_BG, edgecolor="none", clip_on=False)
    ax.add_patch(rect)

    for j, h in enumerate(headers):
        cx = x + col_widths[j] * 0.96 / 2
        ax.text(cx, (header_y + header_bottom) / 2, h,
                ha="center", va="center", fontsize=10, fontweight="bold",
                color=HEAD_FG, fontfamily="sans-serif")
        x += col_widths[j] * 0.96

    # Rows
    row_height = min(row_h / fig_h, 0.065)
    y = header_bottom

    for i, row in enumerate(rows):
        y_bottom = y - row_height
        bg = ROW_EVEN if i % 2 == 0 else ROW_ODD
        rect = Rectangle((0.01, y_bottom), 0.98, row_height,
                          facecolor=bg, edgecolor="none", clip_on=False)
        ax.add_patch(rect)

        x = 0.02
        for j, cell in enumerate(row):
            cx = x + col_widths[j] * 0.96 / 2
            cy = (y + y_bottom) / 2

            fc = TEXT
            if color_cols and j in color_cols:
                fc = color_val(cell)

            fw = "bold" if j == 0 else "normal"
            ax.text(cx, cy, str(cell), ha="center", va="center",
                    fontsize=9.5, color=fc, fontweight=fw,
                    fontfamily="sans-serif")
            x += col_widths[j] * 0.96

        # Separator line
        ax.plot([0.01, 0.99], [y_bottom, y_bottom],
                color=BORDER, linewidth=0.3, clip_on=False)
        y = y_bottom

    # Bottom border
    ax.plot([0.01, 0.99], [y, y], color=HEAD_BG, linewidth=1.0, clip_on=False)

    if footer:
        ax.text(0.5, y - 0.025, footer, ha="center", va="top",
                fontsize=8, color=ACCENT, fontstyle="italic",
                fontfamily="sans-serif")

    plt.savefig(OUT / filename, dpi=200, bbox_inches="tight",
                facecolor=BG, pad_inches=0.15)
    plt.close()
    print(f"  ✓ {filename}")


# ═══════════════════════════════════════════════════════════════════════
# TABLE 1a: Slide 2 — OOS headline (4-col, matching blueprint exactly)
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Strategy", "Sharpe", "Ann. Return", "Max DD"],
    rows=[
        ["Sharpe Ensemble",    "+0.84", "+29.9%", "−24.7%"],
        ["Defensive Ensemble", "+0.75", "+21.6%", "−19.7%"],
        ["Balanced Ensemble",  "+0.68", "+18.8%", "−18.3%"],
        ["Bitcoin",            "−0.33", "−12.3%", "−46.7%"],
        ["Equal-Weight",       "−0.51", "−34.4%", "−68.3%"],
    ],
    filename="slide02_oos_headline_4col.png",
    title="Out-of-Sample Performance (Nov 2024 – May 2026)",
    footer="79 weeks held-out. Bitcoin and equal-weight market both negative.",
    col_widths=[2.2, 1, 1.2, 1.2],
    color_cols={1, 2, 3},
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 1: Slide 2 — OOS headline performance (6-col)
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Strategy", "Sharpe", "Ann. Return", "Volatility", "Max DD", "Weeks"],
    rows=[
        ["Sharpe Ensemble",    "+0.84", "+29.9%", "35.8%", "−24.7%", "79"],
        ["Defensive Ensemble", "+0.75", "+21.6%", "29.0%", "−19.7%", "79"],
        ["Balanced Ensemble",  "+0.68", "+18.8%", "27.6%", "−18.3%", "79"],
        ["Bitcoin",            "−0.33", "−12.3%", "37.7%", "−46.7%", "78"],
        ["Equal-Weight",       "−0.51", "−34.4%", "67.2%", "−68.3%", "78"],
    ],
    filename="slide02_oos_headline.png",
    title="Out-of-Sample Performance  (Nov 2024 – May 2026)",
    footer="79 weeks held-out. Bitcoin and equal-weight market both negative.",
    col_widths=[2.2, 1, 1.2, 1.1, 1.1, 0.7],
    color_cols={1, 2, 4},
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 2: Slide 7 — Master evidence table
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["#", "Factor", "Family", "IC IS t", "IC OOS t", "ASD?", "GX t", "Grade"],
    rows=[
        ["1",  "VolC",        "Anomaly",    "−3.32", "−4.31", "No",  "−5.05", "Confirmed"],
        ["2",  "MAXRET",      "Lottery",    "−3.49", "−4.05", "No",  "+5.52", "Confirmed"],
        ["3",  "CRASH8",      "Behavioral", "—",     "—",     "—",   "+4.79", "Behav.-confirmed"],
        ["4",  "BETA26",      "Behavioral", "—",     "—",     "—",   "+4.60", "Behav.-confirmed"],
        ["5",  "TVLC",        "Fundamental","—",     "—",     "—",   "−4.71", "Priced risk"],
        ["6",  "SKEW52",      "Behavioral", "—",     "—",     "—",   "+3.44", "Behav.-confirmed"],
        ["7",  "NEWC",        "Behavioral", "—",     "—",     "—",   "+3.43", "Behav.-confirmed"],
        ["8",  "RMOM1w",      "Momentum",   "−1.07", "−0.27", "Yes", "+1.86", "Priced risk"],
        ["9",  "SMBC",        "Size",       "+1.49", "+1.25", "Yes", "+0.36", "Suggestive"],
        ["10", "NetRel",      "Network",    "−1.72", "−0.10", "Yes", "−0.01", "Suggestive"],
        ["11", "RMOM2w",      "Momentum",   "−2.46", "−0.24", "Yes", "+1.05", "Suggestive"],
        ["12", "MispricingM", "Composite",  "—",     "—",     "Yes", "—",     "Suggestive"],
    ],
    filename="slide07_master_evidence.png",
    title="Master Factor Evidence — All Three Tests",
    footer="Behavioral factors survive Bonferroni (|t| > 3.64) and BH (q < 0.001) across 182 candidates. IC t-stats: Newey-West (4 lags).",
    col_widths=[0.4, 1.3, 1.1, 0.9, 0.9, 0.6, 0.8, 1.6],
    color_cols={3, 4, 6},
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 3: Slide 8 — Three books
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Book", "Members", "Unifying Evidence", "Economic Role"],
    rows=[
        ["Core Rank",   "VolC (0.55), MAXRET (0.45)",                          "IC-robust weekly rankers",             "Defensive sleeve for risk-off"],
        ["MispricingM", "RMOM1w, RMOM2w, SMBC, NetRel\n(0.25 each)",           "ASSD-dominant distribution",           "Main alpha source"],
        ["Priced Tilt", "TVLC, CRASH8, BETA26, SKEW52, NEWC",                  "GX-priced behavioral risks",           "Capped offensive sleeve (≤18%)"],
    ],
    filename="slide08_three_books.png",
    title="Strategy Sub-Books",
    col_widths=[1.2, 2.5, 1.8, 1.8],
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 4: Slide 10 — Realized allocations
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Variant", "MispricingM", "Core Rank", "Priced Tilt"],
    rows=[
        ["Sharpe Ensemble",    "80.8%", "15.3%", "3.9%"],
        ["Balanced Ensemble",  "54.8%", "36.7%", "8.5%"],
        ["Defensive Ensemble", "60.4%", "35.7%", "3.9%"],
    ],
    filename="slide10_allocations.png",
    title="Realized Average Allocations",
    footer="After rolling-performance scoring, regime filtering, and caps.",
    col_widths=[2, 1.3, 1.3, 1.3],
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 5: Slide 11 — Full OOS performance
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Strategy", "Sharpe", "Ann. Return", "Volatility", "Max DD", "Hit Rate", "Weeks"],
    rows=[
        ["Sharpe Ensemble",    "+0.84", "+29.9%", "35.8%", "−24.7%", "51%", "79"],
        ["Balanced Ensemble",  "+0.68", "+18.8%", "27.6%", "−18.3%", "53%", "79"],
        ["Defensive Ensemble", "+0.75", "+21.6%", "29.0%", "−19.7%", "53%", "79"],
        ["MispricingM",        "+0.85", "+37.2%", "44.1%", "−29.9%", "52%", "79"],
        ["Core Rank",          "+0.11", "+2.0%",  "18.1%", "−18.8%", "47%", "79"],
        ["Priced Tilt",        "−0.43", "−13.7%", "31.8%", "−32.6%", "39%", "79"],
        ["Bitcoin",            "−0.33", "−12.3%", "37.7%", "−46.7%", "47%", "78"],
        ["Equal-Weight",       "−0.51", "−34.4%", "67.2%", "−68.3%", "45%", "78"],
    ],
    filename="slide11_oos_full.png",
    title="Out-of-Sample Performance — All Strategies",
    footer="OOS window: 2024-11-25 to 2026-05-25.",
    col_widths=[2, 1, 1.2, 1.1, 1.1, 0.9, 0.7],
    color_cols={1, 2, 4},
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 6: Slide 12 — IS→OOS decay
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Strategy", "IS Sharpe", "OOS Sharpe", "Decay"],
    rows=[
        ["Sharpe Ensemble",       "+1.36", "+0.84",  "−38%"],
        ["Defensive Ensemble",    "+1.31", "+0.75",  "−43%"],
        ["Balanced Ensemble",     "+1.28", "+0.68",  "−47%"],
        ["Bitcoin benchmark",     "+1.14", "−0.33",  "−129%"],
        ["Neural-net optimizer",  "+2.06", "−0.46",  "−122%"],
    ],
    filename="slide12_decay.png",
    title="IS-to-OOS Sharpe Decay",
    footer="38% decay is meaningful overfitting but far better than ML variants (122%) and benchmark (129%).",
    col_widths=[2.2, 1.2, 1.2, 1],
    color_cols={1, 2, 3},
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 7: Slide 12 — Cost sensitivity
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Cost Assumption", "Est. Net Sharpe", "Impact"],
    rows=[
        ["10 bps one-way (base)", "+0.84",  "As reported"],
        ["25 bps one-way",        "~+0.72", "−14%"],
        ["50 bps one-way",        "~+0.58", "−31%"],
    ],
    filename="slide12_cost_sensitivity.png",
    title="Execution Cost Sensitivity",
    footer="Strategy remains positive even at aggressive cost assumptions, but margin narrows.",
    col_widths=[2, 1.3, 1],
    color_cols={1, 2},
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 8: Slide 13 — Ablation
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Variant", "OOS Sharpe", "OOS Ann. Return", "Note"],
    rows=[
        ["SE (headline)",       "+0.84", "+29.9%", "Three-book ensemble"],
        ["SE Priced-Tilt Off",  "+0.90", "+34.2%", "Sleeve removed entirely"],
        ["SE Priced-Tilt 5%",   "+0.87", "+31.8%", "Cap cut from 18% to 5%"],
        ["SE No Regime Tilt",   "+0.80", "+27.9%", "Regime multipliers = 1.0"],
        ["MispricingM Only",    "+0.85", "+37.2%", "Mispricing book alone"],
    ],
    filename="slide13_ablation.png",
    title="Ablation & Sensitivity Analysis",
    footer="OOS Sharpe stays in +0.80 to +0.91 across the full regime-tilt × priced-cap grid.",
    col_widths=[2, 1.2, 1.4, 2.2],
    color_cols={1, 2},
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 9: Slide 14 — Sub-book decay
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Sub-book", "IS Sharpe", "OOS Sharpe", "Decay"],
    rows=[
        ["MispricingM",  "+1.32", "+0.85",  "−36%"],
        ["Core Rank",    "+0.60", "+0.11",  "−82%"],
        ["Priced Tilt",  "+0.47", "−0.43",  "−192%"],
    ],
    filename="slide14_subbook_decay.png",
    title="Sub-Book IS-to-OOS Sharpe Decay",
    footer="Only MispricingM maintains a meaningful positive Sharpe out-of-sample.",
    col_widths=[1.8, 1.2, 1.2, 1],
    color_cols={1, 2, 3},
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 10: Slide 16 — Regime experiments
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Plan", "Method", "OOS Sharpe", "Ann. Return"],
    rows=[
        ["Plan A", "Economic classifier", "+0.19", "+2.6%"],
        ["Plan B", "Hidden Markov Model", "+0.36", "+4.6%"],
    ],
    filename="slide16_regime_plans.png",
    title="Regime-Only Strategies (Appendix A)",
    footer="Regime conditioning helps risk control but doesn't create standalone alpha.",
    col_widths=[0.8, 2, 1.2, 1.2],
    color_cols={2, 3},
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 11: Slide 16 — ML optimizer failures
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Variant", "OOS Sharpe", "Ann. Return", "Max DD"],
    rows=[
        ["Sharpe optimized",         "+0.61",  "+26.8%",  "−24.2%"],
        ["Return optimized",         "−0.52",  "−27.1%",  "−58.9%"],
        ["Balanced",                 "−0.53",  "−29.7%",  "−62.8%"],
        ["Neural network optimizer", "−0.46",  "−19.1%",  "−45.5%"],
    ],
    filename="slide16_ml_variants.png",
    title="ML Optimizer Variants (Appendix B)",
    footer="3 of 4 ML variants lose money OOS. Final strategy improvement (+0.61 → +0.84) came from simplification.",
    col_widths=[2.2, 1.2, 1.2, 1.1],
    color_cols={1, 2, 3},
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 12: Slide 5 — Regime timeline
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Period", "Regime", "Relevance"],
    rows=[
        ["2021 Q2–Q4", "Speculative excess, DeFi peak", "Tests momentum / lottery factors at peak retail leverage"],
        ["2022 Q1–Q4", "Terra/Luna crash, FTX fraud", "Stress-tests low-vol and crash-rebound during tail events"],
        ["2023", "Recovery & re-rating", "Factor rotation: defensive → risk-seeking"],
        ["2024 Q1–Q4", "BTC ETF, institutional entry", "Regime change: institutional flows compress BTC vol"],
        ["2024 Q4–2026 Q2", "OOS: bear market", "BTC −12.3%, EW −34.4% — hardest possible test"],
    ],
    filename="slide05_regime_timeline.png",
    title="Backtest Regimes Across the Full Window",
    footer="In-sample: 2021-05-10 → 2024-11-11 (184 weeks). Out-of-sample: 2024-11-25 → 2026-05-25 (79 weeks).",
    col_widths=[1.8, 2.2, 3.5],
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 13: Slide 16 — ML variants (simple 2-col, matching blueprint)
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Variant", "OOS Sharpe"],
    rows=[
        ["Sharpe optimized", "+0.61"],
        ["Return optimized", "−0.52"],
        ["Balanced", "−0.53"],
        ["Neural network", "−0.46"],
    ],
    filename="slide16_ml_variants_simple.png",
    title="ML Optimizer Variants — OOS (Appendix B)",
    footer="3 of 4 ML variants lose money OOS. Simplicity, not signal, drove the +0.84 result.",
    col_widths=[2.5, 1.5],
    color_cols={1},
)

# ═══════════════════════════════════════════════════════════════════════
# TABLE 14: Slide 16 — Regime plans (simple 3-col matching blueprint)
# ═══════════════════════════════════════════════════════════════════════
render_table(
    headers=["Plan", "Method", "OOS Sharpe", "Ann. Return"],
    rows=[
        ["Plan A", "Economic classifier", "+0.19", "+2.6%"],
        ["Plan B", "Hidden Markov Model", "+0.36", "+4.6%"],
    ],
    filename="slide16_regime_plans_simple.png",
    title="Regime-Only Strategies (Appendix A)",
    footer="Regime conditioning helps risk control but doesn't create standalone alpha.",
    col_widths=[0.8, 2.2, 1.2, 1.2],
    color_cols={2, 3},
)

print(f"\nAll tables saved to {OUT}/")
