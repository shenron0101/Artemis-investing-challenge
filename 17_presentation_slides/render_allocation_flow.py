"""Render the allocation flow diagram for Slide 10."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

OUT = Path(__file__).parent / "table_pngs"
OUT.mkdir(exist_ok=True)

# ── Palette ────────────────────────────────────────────────────────────
BG       = "#F5F0E8"
NAVY     = "#1F3A5F"
INK      = "#2C3E50"
MUTED    = "#6B7C8F"
GREEN    = "#16A34A"
GREEN_BG = "#E8F5E9"
BLUE     = "#3498DB"
BLUE_BG  = "#E3F2FD"
AMBER    = "#D29922"
AMBER_BG = "#FFF8E1"
INDIGO   = "#4F46E5"
INDIGO_BG= "#EDE7F6"
WHITE    = "#FFFFFF"
STEP_COLORS = [NAVY, BLUE, GREEN, AMBER, INDIGO]
STEP_BGS    = ["#E8EAF6", BLUE_BG, GREEN_BG, AMBER_BG, INDIGO_BG]

fig, ax = plt.subplots(figsize=(14, 4.2))
ax.set_xlim(0, 14)
ax.set_ylim(0, 4.2)
ax.axis("off")
fig.patch.set_facecolor(BG)

# ── Step data ───────────────────────────────────────────────────────────
steps = [
    ("1", "Base\nAllocation", "Variant-specific prior\n(e.g. 92/8/0 for SE)", NAVY, STEP_BGS[0]),
    ("2", "Rolling\nScore", "26-week lookback:\nmax(Sharpe,0) × (1+DD)", BLUE, STEP_BGS[1]),
    ("3", "Blend", "35% base + 65% recent\n→ adaptive weights", GREEN, STEP_BGS[2]),
    ("4", "Regime\nTilt", "XGBoost RiskOff/Neutral/\nRiskOn probabilities", AMBER, STEP_BGS[3]),
    ("5", "Cap &\nNormalize", "Priced Tilt ≤ 18%\nWeights sum to 100%", INDIGO, STEP_BGS[4]),
]

box_w = 2.15
box_h = 2.5
gap = 0.52
start_x = 0.35
y_center = 2.1

for i, (num, title, body, accent, bg_col) in enumerate(steps):
    x = start_x + i * (box_w + gap)
    
    # Main box
    rect = FancyBboxPatch((x, y_center - box_h/2), box_w, box_h,
                          boxstyle="round,pad=0.08", facecolor=bg_col,
                          edgecolor=accent, linewidth=1.5)
    ax.add_patch(rect)
    
    # Accent top bar
    bar = FancyBboxPatch((x + 0.03, y_center + box_h/2 - 0.14), box_w - 0.06, 0.12,
                         boxstyle="round,pad=0.02", facecolor=accent, edgecolor="none")
    ax.add_patch(bar)
    
    # Number badge
    badge_r = 0.22
    badge_x = x + 0.18
    badge_y = y_center + box_h/2 - 0.42
    circle = plt.Circle((badge_x + badge_r, badge_y + badge_r), badge_r,
                        facecolor=accent, edgecolor="white", linewidth=1.2)
    ax.add_patch(circle)
    ax.text(badge_x + badge_r, badge_y + badge_r, num,
            ha="center", va="center", fontsize=13, fontweight="bold",
            color="white", fontfamily="sans-serif")
    
    # Title
    ax.text(x + box_w/2, y_center + box_h/2 - 0.72, title,
            ha="center", va="center", fontsize=11.5, fontweight="bold",
            color=accent, fontfamily="sans-serif", linespacing=1.15)
    
    # Body text
    ax.text(x + box_w/2, y_center - 0.25, body,
            ha="center", va="center", fontsize=9, color=INK,
            fontfamily="sans-serif", linespacing=1.2)
    
    # Arrow between boxes
    if i < 4:
        arrow_x = x + box_w + 0.06
        arrow_end = start_x + (i+1) * (box_w + gap) - 0.06
        ax.annotate("", xy=(arrow_end, y_center), xytext=(arrow_x, y_center),
                    arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.8,
                                    mutation_scale=14))

# ── Title ───────────────────────────────────────────────────────────────
ax.text(7.0, 3.85, "Causal Allocation Pipeline  —  No Look-Ahead",
        ha="center", va="center", fontsize=15, fontweight="bold",
        color=NAVY, fontfamily="sans-serif")

# ── Footer ──────────────────────────────────────────────────────────────
ax.text(7.0, 0.25, "Final weights are fully determined by data available at time t. No future returns leak into the allocator.",
        ha="center", va="center", fontsize=9.5, color=MUTED, fontstyle="italic",
        fontfamily="sans-serif")

plt.savefig(OUT / "slide10_allocation_flow.png", dpi=200, bbox_inches="tight",
            facecolor=BG, pad_inches=0.2)
plt.close()
print(f"  ✓ slide10_allocation_flow.png")