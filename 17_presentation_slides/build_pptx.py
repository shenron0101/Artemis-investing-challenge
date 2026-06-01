#!/usr/bin/env python3
"""Build the Artemis Track 1 presentation as a native, editable PowerPoint deck.

Mirrors the 13-slide narrative (problem -> thesis -> evidence -> result ->
honesty -> close). Charts are the faithful PNGs in assets/figures/ (generated
from Stage 15 metrics.json); conceptual slides are built as native shapes so
they stay editable in PowerPoint.
"""
from __future__ import annotations

import struct
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

HERE = Path(__file__).resolve().parent
FIG = HERE / "assets" / "figures"
OUT = HERE.parents[0] / "16_reports" / "Artemis_Track1_Presentation.pptx"

# ---- palette ---------------------------------------------------------------
NAVY = RGBColor(0x1F, 0x3A, 0x5F)
INK = RGBColor(0x2C, 0x3E, 0x50)
MUTED = RGBColor(0x6B, 0x7C, 0x8F)
FAINT = RGBColor(0x9A, 0xA7, 0xB4)
GREEN = RGBColor(0x16, 0xA3, 0x4A)
GREEN_LT = RGBColor(0x7E, 0xE2, 0xA8)
RED = RGBColor(0xDC, 0x26, 0x26)
BLUE = RGBColor(0x34, 0x98, 0xDB)
ORANGE = RGBColor(0xF9, 0x73, 0x16)
AMBER = RGBColor(0xD2, 0x99, 0x22)
INDIGO = RGBColor(0x4F, 0x46, 0xE5)
PANEL = RGBColor(0xF6, 0xF8, 0xFA)
PANEL2 = RGBColor(0xEE, 0xF2, 0xF7)
LINE = RGBColor(0xE3, 0xE8, 0xEE)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

EMU_PER_IN = 914400
SW, SH = 13.333, 7.5

prs = Presentation()
prs.slide_width = Inches(SW)
prs.slide_height = Inches(SH)
BLANK = prs.slide_layouts[6]

FONT = "Segoe UI"


def png_size(path: Path):
    with open(path, "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", path
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def slide(bg=WHITE):
    s = prs.slides.add_slide(BLANK)
    fill = s.background.fill
    fill.solid()
    fill.fore_color.rgb = bg
    return s


def _set_font(run, size, color, bold=False, italic=False, name=FONT):
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = name


def textbox(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
            line_spacing=1.05, wrap=True, space_after=2):
    """runs: list of paragraphs; each paragraph is a list of (text,size,color,bold,italic) tuples."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        p.space_before = Pt(0)
        for spec in para:
            text, size, color = spec[0], spec[1], spec[2]
            bold = spec[3] if len(spec) > 3 else False
            italic = spec[4] if len(spec) > 4 else False
            r = p.add_run()
            r.text = text
            _set_font(r, size, color, bold, italic)
    return tb


def rrect(s, x, y, w, h, fill=PANEL, line=LINE, line_w=1.0, radius=0.08, shadow=False):
    shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    try:
        shp.adjustments[0] = radius
    except Exception:
        pass
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    if shadow:
        _soft_shadow(shp)
    return shp


def rect(s, x, y, w, h, fill):
    shp = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def _soft_shadow(shp):
    sp = shp._element.spPr
    ef = sp.makeelement(qn('a:effectLst'), {})
    sh = sp.makeelement(qn('a:outerShdw'),
                        {'blurRad': '60000', 'dist': '25000', 'dir': '5400000', 'rotWithShape': '0'})
    clr = sp.makeelement(qn('a:srgbClr'), {'val': '9AA7B4'})
    alpha = sp.makeelement(qn('a:alpha'), {'val': '38000'})
    clr.append(alpha)
    sh.append(clr)
    ef.append(sh)
    sp.append(ef)


def topbar(shp, color):
    """add a colored top accent strip on a card by overlaying a thin rect."""
    pass


def image_fit(s, path, x, y, max_w, max_h, align="center", valign="middle"):
    w, h = png_size(path)
    ar = w / h
    bw, bh = max_w, max_w / ar
    if bh > max_h:
        bh, bw = max_h, max_h * ar
    px = x + {"left": 0, "center": (max_w - bw) / 2, "right": max_w - bw}[align]
    py = y + {"top": 0, "middle": (max_h - bh) / 2, "bottom": max_h - bh}[valign]
    return s.shapes.add_picture(str(path), Inches(px), Inches(py), Inches(bw), Inches(bh))


def kicker(s, text, x=0.6, y=0.42, color=GREEN):
    textbox(s, x, y, 9, 0.4, [[(text.upper(), 12, color, True)]])


def title(s, text, x=0.6, y=0.72, w=12.1, size=34):
    textbox(s, x, y, w, 1.1, [[(text, size, NAVY, True)]], line_spacing=1.02)


def footer(s, right):
    textbox(s, 0.6, 7.06, 11, 0.3,
            [[("Artemis Track 1 · Crypto Factor Rebalancing    ·    " + right, 9, FAINT)]])
    ln = s.shapes.add_connector(2, Inches(0.6), Inches(7.02), Inches(SW - 0.6), Inches(7.02))
    ln.line.color.rgb = LINE
    ln.line.width = Pt(0.75)


def pagenum(s, n):
    textbox(s, SW - 1.7, 7.06, 1.1, 0.3, [[(f"{n} / 13", 9, FAINT)]], align=PP_ALIGN.RIGHT)


def card(s, x, y, w, h, accent, heading, body, icon=None, hsize=15, bsize=11):
    rrect(s, x, y, w, h, fill=PANEL, line=LINE, shadow=True)
    rect(s, x, y, w, 0.07, accent)  # top accent strip
    pad = 0.22
    ty = y + 0.18
    if icon:
        textbox(s, x + pad, ty, w - 2 * pad, 0.5, [[(icon, 20, INK)]])
        ty += 0.5
    textbox(s, x + pad, ty, w - 2 * pad, 0.5, [[(heading, hsize, NAVY, True)]])
    textbox(s, x + pad, ty + 0.46, w - 2 * pad, h - (ty + 0.46 - y) - 0.12,
            [[(body, bsize, INK)]], line_spacing=1.08)


# ============================================================================
# 1. TITLE
# ============================================================================
def s1():
    s = slide(WHITE)
    rect(s, 0, 0, 0.22, SH, GREEN)
    textbox(s, 0.9, 1.55, 11, 0.4, [[("ARTEMIS QUANT COMPETITION · TRACK 1", 13, GREEN, True)]])
    textbox(s, 0.9, 2.0, 11.5, 1.7,
            [[("Separating Alpha, Risk Premia &", 40, NAVY, True)],
             [("Regime Sizing in Crypto Factors", 40, NAVY, True)]], line_spacing=1.02)
    textbox(s, 0.9, 3.7, 8, 0.9,
            [[("A systematic, weekly-rebalanced long–short crypto factor portfolio — ", 16, MUTED)],
             [("built to be explained, tested, and stress-checked, not just back-fitted.", 16, MUTED)]],
            line_spacing=1.1)
    # hook bar
    rrect(s, 0.9, 4.75, 11.4, 0.85, fill=RGBColor(0xEA, 0xF7, 0xF0), line=GREEN, line_w=1.5)
    rect(s, 0.9, 4.75, 0.08, 0.85, GREEN)
    textbox(s, 1.2, 4.75, 11.0, 0.85,
            [[("Out-of-sample, the strategy returned ", 16, INK),
              ("+29.9% / +0.84 Sharpe", 16, GREEN, True),
              (" while Bitcoin and the crypto market ", 16, INK),
              ("lost money.", 16, RED, True)]],
            anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.05)
    textbox(s, 0.9, 5.95, 11, 0.4,
            [[("shenron0101 · ~113 large-cap coins · 2017–2026 · 79-week out-of-sample test ending May 2026", 11, FAINT)]])


# ============================================================================
# 2. PROBLEM
# ============================================================================
def s2():
    s = slide(WHITE)
    kicker(s, "The Problem")
    title(s, "Most crypto factor strategies die out-of-sample")
    textbox(s, 0.6, 1.65, 11, 0.6,
            [[("Beautiful backtests are cheap. Four forces quietly destroy them in live trading:", 16, MUTED)]])
    cards = [
        (GREEN, "🎰  Data-mining", "Test enough signals and some look significant by pure chance. Most “discoveries” are noise."),
        (BLUE, "🌊  Regime shifts", "Crypto flips bull→bear violently. A strategy tuned to one regime breaks in the next."),
        (ORANGE, "📉  Fat tails", "Returns are non-normal. Mean-variance intuition badly understates crash risk."),
        (MUTED, "⚰️  Survivorship", "Dead coins vanish from history, flattering every backward-looking test."),
    ]
    x = 0.6; w = 2.92; gap = 0.18; y = 2.5; h = 2.6
    for accent, head, body in cards:
        card(s, x, y, w, h, accent, head, body, hsize=15, bsize=11.5)
        x += w + gap
    textbox(s, 0.6, 5.35, 12.1, 0.5,
            [[("Our design goal was not the highest backtest number — it was the strategy most likely to ", 12, MUTED),
              ("survive contact with an unseen regime.", 12, NAVY, True)]])
    footer(s, "The Problem"); pagenum(s, 2)


# ============================================================================
# 3. THESIS
# ============================================================================
def s3():
    s = slide(WHITE)
    kicker(s, "Our Approach")
    title(s, "Discipline beats complexity")
    textbox(s, 0.6, 1.65, 11, 0.5, [[("Three commitments shape every decision in the pipeline:", 16, MUTED)]])
    cards = [
        (INDIGO, "1 · Separate factor roles", "Don’t mash signals into one score. Split them into three books — alpha, statistical backbone, and a capped risk-premia sleeve — each with a clear job."),
        (GREEN, "2 · Validate on three gates", "A signal must earn its place: ranking power (IC), distributional dominance (ASD), or priced-risk evidence (GX) — not a single lucky metric."),
        (BLUE, "3 · ML only sizes risk", "Machine learning sets how much to trade by regime, never what to trade. Complex return models overfit short crypto histories."),
    ]
    x = 0.6; w = 3.94; gap = 0.22; y = 2.45; h = 2.95
    for accent, head, body in cards:
        card(s, x, y, w, h, accent, head, body, hsize=16, bsize=12.5)
        x += w + gap
    textbox(s, 0.6, 5.6, 12, 0.5,
            [[("The result is a strategy simple enough to explain on one slide — and that is precisely why it holds up.", 12, MUTED)]])
    footer(s, "Thesis"); pagenum(s, 3)


# ============================================================================
# 4. DATA & UNIVERSE
# ============================================================================
def s4():
    s = slide(WHITE)
    kicker(s, "Data & Universe")
    title(s, "A clean, tradable universe — and an honest split")
    bullets = [
        [("•  ", 14, GREEN, True), ("~113 large-cap coins", 14, NAVY, True), (", weekly panel, 2017–2026", 14, INK)],
        [("•  ", 14, GREEN, True), ("Excludes stablecoins, wrapped & bridged duplicates", 14, NAVY, True),
         (", plus illiquid names where slippage kills paper returns", 14, INK)],
        [("•  ", 14, GREEN, True), ("Four data sources: ", 14, INK), ("Binance", 14, NAVY, True),
         (" (returns/vol), ", 14, INK), ("CoinGecko", 14, NAVY, True), (" (mcap), ", 14, INK),
         ("Artemis", 14, NAVY, True), (" (on-chain), ", 14, INK), ("DeFiLlama", 14, NAVY, True), (" (TVL/fees)", 14, INK)],
        [("•  ", 14, GREEN, True), ("Weekly rebalancing", 14, NAVY, True),
         (" — long enough to cut daily noise, short enough to catch crypto reversals", 14, INK)],
    ]
    textbox(s, 0.6, 1.85, 6.4, 3.2, bullets, line_spacing=1.18, space_after=10)
    # IS / OOS panels
    rrect(s, 7.25, 1.85, 5.45, 1.25, fill=PANEL, line=LINE, shadow=True)
    rect(s, 7.25, 1.85, 0.08, 1.25, BLUE)
    textbox(s, 7.55, 1.98, 5.0, 0.5, [[("In-sample", 22, BLUE, True)]])
    textbox(s, 7.55, 2.52, 5.0, 0.5, [[("2021-05-10 → 2024-11-11  ·  model design & factor selection", 11, MUTED)]])
    rrect(s, 7.25, 3.3, 5.45, 1.6, fill=PANEL, line=LINE, shadow=True)
    rect(s, 7.25, 3.3, 0.08, 1.6, ORANGE)
    textbox(s, 7.55, 3.42, 5.0, 0.5, [[("Out-of-sample", 22, ORANGE, True)]])
    textbox(s, 7.55, 3.98, 5.0, 0.85,
            [[("2024-11-18 → 2026-05-25  ·  ", 11, MUTED), ("79 weeks", 11, NAVY, True),
              (", untouched until the end — and it spans a full bull→bear transition.", 11, MUTED)]], line_spacing=1.12)
    textbox(s, 0.6, 5.45, 12.1, 0.7,
            [[("Pre-2025 market cap is reconstructed (price × emissions-anchored supply, drift clamped to a realistic band). "
               "The size factor sorts on cross-sectional ranks, so residual error barely moves it.", 11, FAINT)]], line_spacing=1.1)
    footer(s, "Data & Universe"); pagenum(s, 4)


# ============================================================================
# 5. VALIDATION FRAMEWORK
# ============================================================================
def s5():
    s = slide(WHITE)
    kicker(s, "Validation Framework")
    title(s, "Three gates, three different questions")
    textbox(s, 0.6, 1.65, 11.5, 0.5,
            [[("A characteristic is not a factor until it passes a test that ", 16, MUTED),
              ("means", 16, MUTED, False, True), (" something. We use three:", 16, MUTED)]])
    gates = [
        (BLUE, "IC", "Information Coefficient", "“Does it rank coins correctly week to week?”",
         "Rank correlation of signal vs next-week return, with Newey-West t-stats for autocorrelation."),
        (GREEN, "ASD", "Almost Stochastic Dominance", "“Is the whole return distribution attractive?”",
         "The right test for fat-tailed crypto — checks dominance across the distribution, not just the mean."),
        (AMBER, "GX", "Giglio–Xiu Pricing", "“Is it a priced risk after hidden factors?”",
         "Latent-factor pricing with week-by-week Fama–MacBeth, so a premium isn’t an omitted-factor mirage."),
    ]
    x = 0.6; w = 3.94; gap = 0.22; y = 2.45; h = 3.1
    for accent, tag, head, q, body in gates:
        rrect(s, x, y, w, h, fill=PANEL, line=LINE, shadow=True)
        rrect(s, x + 0.22, y + 0.22, 0.95, 0.42, fill=accent, line=None, radius=0.5)
        textbox(s, x + 0.22, y + 0.235, 0.95, 0.4, [[(tag, 13, WHITE, True)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        textbox(s, x + 0.22, y + 0.78, w - 0.44, 0.5, [[(head, 15, NAVY, True)]])
        textbox(s, x + 0.22, y + 1.3, w - 0.44, 0.5, [[(q, 11.5, MUTED, False, True)]], line_spacing=1.05)
        textbox(s, x + 0.22, y + 1.82, w - 0.44, 1.1, [[(body, 11.5, INK)]], line_spacing=1.1)
        x += w + gap
    textbox(s, 0.6, 5.75, 12.1, 0.5,
            [[("Different gates catch different illusions. Requiring real evidence on at least one — and treating the rest as suggestive — keeps the factor set honest.", 11, MUTED)]])
    footer(s, "Validation"); pagenum(s, 5)


# ============================================================================
# 6. FACTORS THAT SURVIVED
# ============================================================================
def s6():
    s = slide(WHITE)
    kicker(s, "Evidence")
    title(s, "The factors that earned their place")
    # table
    rows = [
        ("Factor", "Role", "GX t", "Grade", True, None),
        ("VolC — low volatility", "Core rank", "−5.05", "Confirmed", False, GREEN),
        ("MAXRET — lottery reversal", "Core rank", "+5.52", "Confirmed", False, GREEN),
        ("MispricingM — composite", "Main alpha", "n/a", "ASD-dom.*", False, GREEN),
        ("CRASH8 / BETA26", "Priced tilt", "+4.79/+4.60", "Priced risk", False, INK),
        ("SKEW52 / NEWC", "Priced tilt", "+3.44/+3.43", "Priced risk", False, INK),
    ]
    tx, ty, tw = 0.6, 1.95, 6.3
    colw = [3.0, 1.35, 1.25, 1.55]
    rh = 0.52
    cy = ty
    for ri, (c0, c1, c2, c3, header, gcol) in enumerate(rows):
        cx = tx
        bg = NAVY if header else (PANEL if ri % 2 == 0 else WHITE)
        rect(s, tx, cy, tw, rh, bg)
        vals = [c0, c1, c2, c3]
        aligns = [PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.LEFT]
        for ci, (val, cw, al) in enumerate(zip(vals, colw, aligns)):
            col = WHITE if header else (gcol if ci == 3 else INK)
            bold = header or (ci == 0) or (ci == 3)
            textbox(s, cx + 0.12, cy, cw - 0.2, rh, [[(val, 11.5, col, bold)]],
                    align=al, anchor=MSO_ANCHOR.MIDDLE)
            cx += cw
        cy += rh
    # divider lines under table rows
    textbox(s, 0.6, cy + 0.12, 6.4, 0.8,
            [[("*MispricingM (RMOM1w+RMOM2w+SMBC+NetRel) almost-stochastically dominates Bitcoin in the in-sample, full, and out-of-sample windows (ε₂ = 0.000).", 10.5, FAINT)]],
            line_spacing=1.1)
    # image
    image_fit(s, FIG / "mispr_is_oos.png", 7.1, 1.75, 5.7, 3.7)
    textbox(s, 7.1, 5.5, 5.7, 0.6,
            [[("MispricingM holds its Sharpe (≈1.3) from in-sample into out-of-sample — the core alpha source.", 11, MUTED)]],
            align=PP_ALIGN.CENTER, line_spacing=1.05)
    footer(s, "Factor Evidence"); pagenum(s, 6)


# ============================================================================
# 7. DATA-MINING FUNNEL
# ============================================================================
def s7():
    s = slide(WHITE)
    kicker(s, "Statistical Honesty")
    title(s, "We assume we’re fooling ourselves — then prove we’re not")
    image_fit(s, FIG / "funnel.png", 2.0, 2.05, 9.3, 3.75)
    textbox(s, 0.6, 5.95, 12.1, 0.8,
            [[("A 56% raw hit rate is exactly what data-mining looks like. So the four behavioural factors are held to a far harsher bar — surviving ", 12, MUTED),
              ("both", 12, NAVY, True),
              (" Bonferroni and Benjamini–Hochberg across all 182 tests — and even then enter only as a small ", 12, MUTED),
              ("capped", 12, NAVY, True), (" sleeve.", 12, MUTED)]], line_spacing=1.12)
    footer(s, "Multiple-Testing Discipline"); pagenum(s, 7)


# ============================================================================
# 8. ARCHITECTURE
# ============================================================================
def s8():
    s = slide(WHITE)
    kicker(s, "Strategy Architecture")
    title(s, "Three books → causal allocator → regime sizing")
    # books column
    bx, bw = 0.6, 3.5
    books = [
        (INDIGO, "MispricingM", "RMOM1w · RMOM2w · SMBC · NetRel — main alpha"),
        (BLUE, "Core Rank", "VolC · MAXRET — statistical backbone"),
        (AMBER, "Priced Tilt", "CRASH8 · BETA26 · TVLC · SKEW52 · NEWC — capped sleeve"),
    ]
    by = 1.95; bh = 0.84; bgap = 0.1
    for accent, head, body in books:
        rrect(s, bx, by, bw, bh, fill=PANEL, line=LINE, shadow=True)
        rect(s, bx, by, 0.08, bh, accent)
        textbox(s, bx + 0.22, by + 0.1, bw - 0.35, 0.4, [[(head, 13.5, NAVY, True)]])
        textbox(s, bx + 0.22, by + 0.46, bw - 0.35, 0.34, [[(body, 9.5, MUTED)]], line_spacing=1.0)
        by += bh + bgap

    def arrow(x, y):
        a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(0.5), Inches(0.5))
        a.fill.solid(); a.fill.fore_color.rgb = FAINT; a.line.fill.background(); a.shadow.inherit = False

    arrow(4.22, 2.95)
    # allocator
    ax = 4.85; aw = 3.0
    rrect(s, ax, 2.05, aw, 2.0, fill=PANEL, line=LINE, shadow=True)
    textbox(s, ax + 0.2, 2.2, aw - 0.4, 0.5, [[("Causal allocator", 14, NAVY, True)]])
    textbox(s, ax + 0.2, 2.72, aw - 0.4, 1.2,
            [[("Each week, weights books by their ", 11, INK), ("recent past", 11, NAVY, True),
              (" performance blended with a conservative base. ", 11, INK), ("No future data.", 11, GREEN, True)]],
            line_spacing=1.1)
    arrow(8.0, 2.95)
    # regime
    rx = 8.62; rw = 2.7
    rrect(s, rx, 2.05, rw, 2.0, fill=RGBColor(0xF0, 0xF4, 0xFF), line=RGBColor(0xD7, 0xE0, 0xFF), shadow=True)
    textbox(s, rx + 0.2, 2.25, rw - 0.4, 0.5, [[("XGBoost regime sizing", 13.5, INDIGO, True)]], align=PP_ALIGN.CENTER)
    textbox(s, rx + 0.2, 2.85, rw - 0.4, 1.1,
            [[("RiskOff · Neutral · RiskOn", 11, INK, True)],
             [("scales gross exposure —", 10.5, MUTED)],
             [("not signal direction", 10.5, MUTED)]], align=PP_ALIGN.CENTER, line_spacing=1.05)
    arrow(11.45, 2.95)
    # output
    rrect(s, 12.0, 2.25, 1.15, 1.6, fill=NAVY, line=None)
    textbox(s, 12.0, 2.25, 1.15, 1.6, [[("Weekly", 11, WHITE, True)], [("long–short", 11, WHITE, True)], [("weights", 11, WHITE, True)]],
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.05)
    # allocation image + notes
    image_fit(s, FIG / "allocations.png", 0.6, 4.85, 6.4, 1.95)
    notes = [
        [("•  ", 13, GREEN, True), ("Sharpe Ensemble", 13, NAVY, True), (" — concentrates on alpha (92% MispricingM)", 13, INK)],
        [("•  ", 13, GREEN, True), ("Defensive / Balanced", 13, NAVY, True), (" — shift toward Core Rank to cut drawdown", 13, INK)],
        [("•  ", 13, GREEN, True), ("Priced Tilt is capped", 13, NAVY, True), (" by design — never allowed to dominate", 13, INK)],
    ]
    textbox(s, 7.2, 5.05, 5.6, 1.8, notes, line_spacing=1.2, space_after=8)
    footer(s, "Architecture"); pagenum(s, 8)


# ============================================================================
# 9. HERO RESULT
# ============================================================================
def s9():
    s = slide(WHITE)
    kicker(s, "The Result")
    title(s, "Positive out-of-sample while the market bled")
    image_fit(s, FIG / "hero_oos.png", 1.7, 1.65, 9.9, 3.15)
    # table
    rows = [
        ("79-week OOS", "Sharpe", "Ann. return", "Volatility", "Max drawdown", True, None),
        ("Sharpe Ensemble", "+0.84", "+29.9%", "35.8%", "−24.7%", False, GREEN),
        ("Defensive Ensemble", "+0.75", "+21.6%", "29.0%", "−19.7%", False, GREEN),
        ("Bitcoin", "−0.33", "−12.3%", "37.7%", "−46.7%", False, RED),
        ("Equal-weight market", "−0.51", "−34.4%", "67.2%", "−68.3%", False, RED),
    ]
    tx, ty, tw = 0.6, 4.88, 12.1
    colw = [3.7, 2.1, 2.1, 2.1, 2.1]
    rh = 0.35
    cy = ty
    for ri, r in enumerate(rows):
        header = r[5]; gcol = r[6]
        bg = NAVY if header else (PANEL if ri % 2 == 0 else WHITE)
        rect(s, tx, cy, tw, rh, bg)
        cx = tx
        for ci, (val, cw) in enumerate(zip(r[:5], colw)):
            al = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.RIGHT
            if header:
                col = WHITE
            elif ci == 0:
                col = INK
            elif ci == 3:
                col = INK
            else:
                col = gcol
            bold = header or ci == 0 or ci in (1, 2, 4)
            textbox(s, cx + 0.15, cy, cw - 0.25, rh, [[(val, 11, col, bold)]], align=al, anchor=MSO_ANCHOR.MIDDLE)
            cx += cw
        cy += rh
    textbox(s, 0.6, cy + 0.05, 12.1, 0.4,
            [[("Same window, half the drawdown of Bitcoin — and a positive return where the market lost a third of its value.", 11, MUTED)]])
    footer(s, "Out-of-Sample Result"); pagenum(s, 9)


# ============================================================================
# 10. ROBUSTNESS & ABLATIONS
# ============================================================================
def s10():
    s = slide(WHITE)
    kicker(s, "Robustness")
    title(s, "Is it luck? We pressure-tested it")
    image_fit(s, FIG / "decay.png", 0.55, 1.7, 6.1, 3.0)
    image_fit(s, FIG / "ablation.png", 6.85, 1.7, 6.0, 3.0)
    cards = [
        (GREEN, "Modest decay", "Ensembles lose ~38% of Sharpe IS→OOS but stay positive; the complex ML optimiser fell from +2.06 to −0.46."),
        (GREEN, "Robust to priors", "Across the full regime × cap grid, OOS Sharpe stays in a tight +0.80 to +0.91 band."),
        (AMBER, "Honest finding", "The priced-tilt sleeve is a drag — removing it raises Sharpe to +0.90. The edge is essentially one composite signal."),
    ]
    x = 0.6; w = 3.94; gap = 0.22; y = 4.95; h = 1.85
    for accent, head, body in cards:
        card(s, x, y, w, h, accent, head, body, hsize=13.5, bsize=11)
        x += w + gap
    footer(s, "Robustness & Ablations"); pagenum(s, 10)


# ============================================================================
# 11. WHAT COULD FAIL
# ============================================================================
def s11():
    s = slide(WHITE)
    kicker(s, "Intellectual Honesty")
    title(s, "What could break this — and what we did about it")
    items = [
        ("79-week OOS", " — one regime transition.  ", "→ framed as single-regime validation, not proof."),
        ("Single-factor dependency", " on MispricingM.  ", "→ quantified openly in the ablation, not hidden."),
        ("Simplified 10bps costs", ".  ", "→ flagged; real costs could trim Sharpe to ~0.65–0.75."),
        ("Survivorship risk", " in deep history.  ", "→ acknowledged; size factor uses ranks to limit impact."),
    ]
    y = 1.95
    for a, b, c in items:
        rrect(s, 0.6, y, 6.3, 0.92, fill=PANEL, line=LINE)
        textbox(s, 0.78, y, 6.0, 0.92, [[(a, 12, RED, True), (b, 12, INK), (c, 12, GREEN, True)]],
                anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.05)
        y += 1.02
    # audit panel
    rrect(s, 7.25, 1.95, 5.45, 2.4, fill=PANEL, line=LINE, shadow=True)
    rect(s, 7.25, 1.95, 5.45, 0.08, GREEN)
    textbox(s, 7.5, 2.15, 5.0, 0.5, [[("Independent audit", 20, GREEN, True)]])
    textbox(s, 7.5, 2.75, 5.0, 1.5,
            [[("An end-to-end audit raised ", 12.5, INK), ("13 findings", 12.5, NAVY, True),
              (" — uncontrolled multiple testing, a supply-backfill bug, full-sample ASD, unvalidated priors. ", 12.5, INK),
              ("Every production-pipeline finding is resolved", 12.5, NAVY, True),
              (" and reflected in the results shown here.", 12.5, INK)]], line_spacing=1.15)
    textbox(s, 7.25, 4.5, 5.45, 0.5,
            [[("We would rather show the judges the cracks ourselves than have them found later.", 11, MUTED)]], line_spacing=1.05)
    footer(s, "Limitations & Audit"); pagenum(s, 11)


# ============================================================================
# 12. WHY THIS WINS
# ============================================================================
def s12():
    s = slide(WHITE)
    kicker(s, "Why This Approach")
    title(s, "Simplicity that survives")
    checks = [
        ("Economic story", " — every factor has a named, cited mechanism"),
        ("Statistically defensible", " — three gates + multiple-testing correction"),
        ("Honest", " — limitations, ablations, and an audit on the record"),
        ("Causal & tradable", " — weekly, no look-ahead, capped risk"),
    ]
    y = 2.1
    for a, b in checks:
        textbox(s, 0.7, y, 6.2, 0.6, [[("✓  ", 16, GREEN, True), (a, 15, NAVY, True), (b, 15, INK)]], line_spacing=1.05)
        y += 0.72
    rrect(s, 7.25, 2.1, 5.45, 2.6, fill=PANEL, line=LINE, shadow=True)
    rect(s, 7.25, 2.1, 5.45, 0.08, GREEN)
    textbox(s, 7.5, 2.35, 5.0, 2.2,
            [[("Complexity lost.", 14, NAVY, True), (" The XGBoost multi-sleeve optimiser reached only ", 14, INK),
              ("+0.61", 14, GREEN, True), (" OOS Sharpe; the simplified ensemble reached ", 14, INK), ("+0.84", 14, GREEN, True), (".", 14, INK)],
             [("", 8, INK)],
             [("The gain came from ", 14, INK), ("removing", 14, NAVY, True),
              (" complexity and concentrating on validated signal — not from adding more model.", 14, INK)]],
            line_spacing=1.2)
    footer(s, "Why It Wins"); pagenum(s, 12)


# ============================================================================
# 13. CLOSE
# ============================================================================
def s13():
    s = slide(NAVY)
    textbox(s, 0.8, 1.6, 11, 0.4, [[("IN CLOSING", 13, GREEN_LT, True)]])
    textbox(s, 0.8, 2.0, 11.5, 1.0, [[("Discipline, not complexity", 38, WHITE, True)]])
    textbox(s, 0.8, 3.05, 8.5, 1.2,
            [[("Separate alpha, risk premia and regime sizing; validate ruthlessly; size risk with ML — and stay honest about the limits.", 16, RGBColor(0xC7, 0xD2, 0xDD))]],
            line_spacing=1.18)
    stats = [("+0.84", "OOS Sharpe vs −0.33 BTC"), ("+29.9%", "OOS return vs −34% market"), ("−24.7%", "max drawdown — half of BTC")]
    x = 0.8; w = 3.85; gap = 0.18; y = 4.55; h = 1.35
    for num, lbl in stats:
        rrect(s, x, y, w, h, fill=RGBColor(0x2B, 0x49, 0x6E), line=RGBColor(0x3A, 0x5A, 0x82))
        textbox(s, x + 0.25, y + 0.18, w - 0.4, 0.6, [[(num, 30, GREEN_LT, True)]])
        textbox(s, x + 0.25, y + 0.82, w - 0.4, 0.45, [[(lbl, 11, RGBColor(0xAE, 0xBC, 0xCB))]])
        x += w + gap
    textbox(s, 0.8, 6.2, 11.5, 0.5,
            [[("A disciplined research prototype — not a finished production strategy.    ·    Thank you. Questions?", 12, RGBColor(0x9F, 0xB0, 0xC0))]])


for fn in (s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12, s13):
    fn()

prs.save(str(OUT))
print("saved", OUT)
