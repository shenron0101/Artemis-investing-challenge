# Stage 09 — NALFP Additions: Goals & Design Brief

**Status:** planning (no implementation yet)
**Date:** 2026-05-29
**Predecessor:** `08_nalfp` (NALFP v3, commit `66bea36`)
**Purpose of this document:** Capture three improvement goals — sourced from professor feedback —
in enough detail to drive implementation later. Each goal states the motivation, the concrete
scope, deliverables, the risks we already know about, and the success criteria we will judge it by.

---

## Context: what we are fixing

NALFP v3 is economically sound but statistically thin. Its own `REPORT.md §8` names the binding
constraint plainly:

- **52 weeks total → 24 out-of-sample weeks** after the network burn-in.
- **T = 24 training weeks** is too short to identify latent risk premia: the Bai-Ng IC_p2 criterion
  saturated the `K_hidden = 3` cap, and the OOS Sharpe bootstrap CI crosses zero
  (−2.01 to +4.80).
- The hidden-factor pillar (dense PCA on GX residuals) produces factors that are **not
  statistically priced and not interpretable**.

So the strategy's *factor structure* is defensible, but its *generalisation* is unproven on this
sample. The three goals below are ordered to attack that directly: extend the usable time series
(Goal 1), replace the weak/uninterpretable latent pillar with economically grounded features
(Goal 2), and make a deliberate, defensible exposure choice (Goal 3).

> **Dependency note.** Goal 2 and Goal 3 both assume Goal 1 has delivered a longer, cleaner panel.
> Sparse PCA and CCA need T ≫ N to be stable, and a net-exposure tilt is only worth backtesting on
> a sample that contains more than one regime. **Goal 1 is the prerequisite.**

---

## Goal 1 — Curate a smaller universe with deep, known history

**Statement.** Replace the breadth-first ~113-asset universe with a depth-first core universe of
assets that each have a long, continuous price history (target: **≥ 5 years of data**), so that
factor estimates rest on enough observations to separate economic signal from noise.

### Why
- T = 24 training weeks is the single largest weakness in v3. Five years of weekly data is ~260
  observations — an order of magnitude more, enough for Bai-Ng selection, rolling IC estimation,
  and the Goal-2 decompositions to be stable.
- Longer history spans **multiple regimes** (2021 bull, 2022 bear, 2023 recovery, 2024–25 cycle),
  which is exactly what is needed to test regime robustness — a stated competition criterion.

### Scope / first tasks
1. **Measure data availability per asset.** For every candidate asset, compute first-tick date,
   last-tick date, % missing days, and longest continuous run, across CoinGecko / Binance.
   Produce a coverage table (`data/universe_coverage.parquet`) and a plot.
2. **Decide the in-sample / out-of-sample split** from the coverage facts, not arbitrarily — find
   the earliest date at which ≥ N assets are simultaneously live.
3. **Define a tiered universe** (see "Design decisions") and freeze it to a manifest.

### Known risks / things to get right
- **Breadth vs. depth trade-off.** A long/short quintile book needs cross-sectional breadth for
  ranking power. With ~30 assets, each quintile leg is ~6 names — noisy. Do not shrink the
  universe below the point where the long/short construction is statistically meaningful.
- **Survivorship bias.** "Assets that have 5 years of data" is, by definition, a survivor set;
  this inflates historical returns. Acknowledge it explicitly and, where feasible, use a
  point-in-time universe (include assets that later delisted, for the period they were live).
- **BTC/ETH dominance.** A deep universe is heavily majors-weighted; guard against the portfolio
  collapsing into a BTC/ETH proxy (cap single-asset and cluster weights as in v3).

### Design decisions to make
- **Tiered universe** is the proposed resolution of the trade-off:
  - *Core (estimation) universe* — ~25–40 assets with full ≥5yr continuous history. Used for
    factor estimation, Sparse PCA, and CCA (Goal 2).
  - *Trading universe* — optionally broader, with assets entering as their history matures, used
    for portfolio construction once they clear a minimum-history gate.
- Confirm the exact history threshold (5yr vs. 4yr) against what the coverage table actually
  supports — 5yr may be too aggressive and leave too few names.

### Success criteria
- A frozen universe manifest with documented inclusion rules and per-asset coverage.
- ≥ 200 weekly observations available for the core universe.
- Explicit written treatment of survivorship bias.

---

## Goal 2 — Economically grounded latent features via Sparse PCA + CCA

**Statement.** Replace (or augment) the dense PCA-on-residuals hidden-factor pillar with two
interpretable, economically anchored decompositions: **Sparse PCA** on the cross-section of coin
returns, and **Canonical Correlation Analysis (CCA)** between crypto returns and a small basket of
traditional market reference tickers. The objective is *economic stability and interpretability* of
the factors, not just in-sample fit.

### Why
- The current GX hidden factors are dense (every asset loads on every factor), statistically
  unpriced in our sample, and impossible to name. They add complexity without earning it.
- **Sparse PCA** forces most loadings to zero, so each latent factor loads on a handful of assets
  and can be *interpreted* ("this factor ≈ the DeFi cluster", "this ≈ L1s"). Interpretability is
  an explicit competition criterion.
- **CCA against a market basket** cleanly separates the part of the crypto cross-section that is
  *spanned by traditional macro risk* from the part that is *crypto-idiosyncratic*. That gives an
  economic story for where returns come from, and a hedge for the macro-driven component.

### Scope / first tasks
1. **Sparse PCA** on the (standardised, rolling-window) matrix of core-universe weekly returns.
   Choose the sparsity penalty out-of-sample; report loadings and the implied factor names.
2. **CCA** between crypto returns and a reference basket. Proposed reference tickers:
   **SPY** (US equity), **BTC** (crypto market), plus 3–4 macro-economic instruments such as
   **gold (GLD)**, **US dollar index (DXY)**, **US Treasuries (TLT/IEF or 10Y yield)**, and
   optionally **ETH** or **VIX**. Report canonical correlations and the canonical loadings.
3. **Wire the resulting features into the factor pipeline** as candidate signals, and test them
   with the same GX / Fama-MacBeth controls already used in the project before crediting them
   (per the standing research rule).

### Known risks / things to get right
- **T ≫ N requirement.** Both methods are unstable when observations don't dominate variables.
  This is why Goal 1 comes first. State the T/N ratio used.
- **BTC double-counting.** BTC appears in both the crypto universe and the reference basket. Use
  BTC as a *reference / market factor only* and exclude it from the asset-return matrix fed to the
  decompositions (or orthogonalise), so the same series isn't on both sides of the CCA.
- **No look-ahead.** Loadings drift over time; estimate on rolling windows and lag them before
  use, consistent with the project rule "chronological splits only, no shuffle CV."
- **Sparsity hyperparameter must not be tuned to the test set.** Select it on training data only.

### Success criteria
- Each retained latent factor has a one-line economic interpretation (a name and the assets it
  loads on).
- CCA reports how much crypto cross-sectional variance is macro-spanned vs. idiosyncratic.
- New features survive GX / FMB controls (|t| ≥ 1.65) before entering the live signal set; ones
  that don't are documented and dropped.

---

## Goal 2.5 — IS/OOS significance test for every factor we present

**Statement (plain English).** Before we put a factor in front of the
competition judges, we must prove it actually *works* — not just in the data we
fit on, but in data it has never seen. For each economic factor, build its
long/short return series, split the timeline into an **in-sample (IS)** first
chunk and an **out-of-sample (OOS)** recent chunk, and check two things:
**(1) is the factor's payoff statistically significant in-sample, and (2) does it
still hold up out-of-sample?** Only factors that pass both are "competition-grade".

### Why
- A factor that looks great in-sample but dies out-of-sample is almost always
  overfitting or luck. The competition explicitly rewards **regime robustness**,
  and an honest IS→OOS hold-up is the simplest, most credible evidence of it.
- It turns "here are some factors" into "here are the factors that survived a
  pre-registered, look-ahead-free test" — a much stronger story.

### What counts as a "factor" here
Every economic signal we might present: the classic factor-zoo factors (size /
SMBC, momentum / MomC, low-vol / VolC, value / FunC, network factors NetMom &
NetRel) **and** the new Stage-09 Sparse-PCA factors (SPC1–SPC4). Each becomes a
weekly long/short portfolio return series on the Stage-09 5-year panel.

### Method (kept simple, no look-ahead)
1. Use the frozen split from the manifest: **IS = 2021-05-10 → 2024-11-11 (184w)**,
   **OOS = 2024-11-18 → 2026-05-25 (80w)**.
2. For each factor compute, on IS and again on OOS: mean weekly return,
   annualised Sharpe, a **Newey-West t-stat** (the "is this real?" number), and
   the rank IC. A t-stat with |t| ≥ ~2 means "unlikely to be luck".
3. **Verdict per factor:**
   - **Robust** — significant IS *and* same-sign (ideally significant) OOS.
   - **In-sample only** — significant IS but fades/flips OOS → flag, don't rely on it.
   - **Weak** — not significant even IS → drop.
4. Apply standard hygiene: returns lagged so signals use only past data, costs
   noted, chronological splits only (no shuffling).

### Deliverable — a results file an undergrad can read
Produce `RESULTS.md` that explains, in plain language: what each factor *is* (one
sentence), the IS vs OOS table, and a one-line verdict per factor ("survived /
faded / dropped"). No unexplained jargon — every statistic gets a short "what
this means" note. This same plain-English style carries into the Goal-3 final
results.

### Success criteria
- One clean IS-vs-OOS table covering every candidate factor, with t-stats.
- A clearly marked **shortlist of competition-grade factors** (passed both).
- `RESULTS.md` readable by someone who has not seen the code.

---

## Goal 3 — Asymmetric (long-biased) factor exposure, done honestly

**Statement.** Introduce a deliberate net-long tilt to the long/short book — an **80/20** bias
toward the long leg of each factor — reflecting a prior that the market continues to trend up,
while being explicit that this is a beta decision, not alpha.

### Why
- A pure dollar-neutral book throws away the (historically positive) crypto market premium. If we
  hold a view that markets keep booming, encoding it as a controlled net-long tilt is reasonable.

### The honest critique (read before building)
- An 80/20 net-long book **breaks dollar-neutrality and injects market beta.** In a bull sample,
  most of the extra return is *beta, not factor alpha*. The competition explicitly rewards
  cross-sectional ranking power, so an undisclosed long tilt risks being seen as levered
  long-the-market dressed up as factor work.
- It also sacrifices v3's current selling point: **−3.47% max drawdown and regime robustness.** A
  static long tilt will look great in bull weeks and hurt badly in any bear regime — precisely the
  weeks the longer Goal-1 sample now includes.

### Proposed framings (pick one, in order of preference)
1. **Regime-conditional tilt (recommended).** Scale the net-long exposure by the regime proxy
   already in the panel — the **stablecoin-inflow z-score** (`06_artemis_econometrics/01_build_panel.py`).
   Net-long in risk-on regimes, neutral/defensive in risk-off. This is defensible market-timing,
   consistent with the project's robustness thesis, rather than a blind bull bet.
2. **Market-neutral core + reported beta sleeve.** Keep the dollar-neutral alpha book as the
   headline strategy and report the 80/20-tilted version as a separate "strategic-beta" variant,
   so returns are cleanly attributable to alpha vs. beta.
3. **Static 80/20, fully disclosed.** If kept static, size it modestly, measure the realised
   market beta explicitly, and disclose it as a deliberate overlay — never hide it inside "factor
   rebalancing."

### Scope / first tasks
1. Parameterise net exposure (long/short leg scaling) in portfolio construction.
2. Implement the regime-conditional scaler (framing 1) using the existing stablecoin z-score.
3. **Always run an alpha/beta attribution**: regress the tilted book's returns on the market
   factor and report alpha, beta, and the share of return attributable to each.

### Known risks / things to get right
- Report the static-neutral and tilted variants side by side; do not let the tilt flatter the
  headline number.
- Re-check max drawdown and turnover under the tilt — these are the metrics it most endangers.

### Success criteria
- Net exposure is an explicit, documented parameter (and, ideally, regime-driven).
- Every tilted result ships with an alpha/beta decomposition.
- Drawdown and turnover under the tilt are reported next to the neutral baseline.

---

---

## Goal 1 — STATUS: COMPLETE (2026-05-29)

Built in `09_nalfp_add/`: `01_universe_coverage.py` (Binance price audit) →
`02_coinmetrics_coverage.py` (mcap tiering) → `03_reconstruct_mcap_panel.py`
(5y price+mcap panel) → `04_freeze_universe.py` (frozen manifest).

**Key outcome — the 52-week bottleneck is broken.** Prior research was capped at
52 weeks because the panel's price/mcap backbone came from CoinGecko, whose free
tier limits history to 365 days. Stage 09 moves price to **Binance (5y, gap-free)**
and reconstructs market cap as **price × circulating supply** (real where free
from CoinMetrics; the recent ~365d is real CoinGecko mcap for every coin; the
deep tail is estimated with a growth-anchored supply trend, validated at
~20–29% median error vs real — acceptable given mcap spans orders of magnitude).

**Frozen universe (`artifacts/manifests/universe_manifest.json`):**
- **Estimation backbone:** 33 coins, **264 balanced weekly obs** from 2021-05-10
  (success criterion ≥200 → PASS). Used for the Goal-2 Sparse PCA / CCA matrix.
- **Trading universe:** 63 ever-eligible, **2–62 live per week**, point-in-time and
  mcap-ranked with entry/exit — the survivorship-safe design from the user's
  refinement (see `SURVIVORSHIP.md`).
- **IS / OOS split:** in-sample 2021-05-10 → 2024-11-11 (184w); out-of-sample
  2024-11-18 → 2026-05-25 (80w).

Deliverables: `universe_coverage.parquet`, `universe_coverage_full.parquet`,
`price_mcap_panel_weekly.parquet`, `mcap_reconstruction_error.parquet`,
`universe_membership.csv`, `universe_manifest.json`, `figures/universe_coverage.png`,
and `SURVIVORSHIP.md`.

---

## Goal 2 — STATUS: COMPLETE (2026-05-29)

Built: `05_returns_and_reference.py` (weekly returns + macro basket) →
`06_sparse_pca.py` (Sparse PCA factors) → `07_cca_macro.py` (CCA vs macro).

**Commodity proxies (PAXG, XAUT) excluded** from the universe; backbone is now 32
coins, trading universe 61.

**"Tied to 33 coins?" — answered and fixed.** 33 was only the count of coins
present for the *entire* 5y (the balanced full-sample matrix). Sparse PCA/CCA need
only a rectangular *window*, so a **rolling 2-year window** is used: it admits
whatever coins are live through that window — **median 32, max 45 coins** — and
yields 305 weeks of OOS factor returns. Available coins by window: 5y→32, 3y→40,
2y→45, 1y→52.

**Sparse PCA — interpretable latent factors** (full-sample backbone, K=4,
cumulative adj. EVR 70%), replacing v3's dense unpriced hidden factors:

| Factor | Top loaders | Reading |
|---|---|---|
| SPC1 | ETH, ETC, BTC, UNI, AAVE | broad market / DeFi-majors beta |
| SPC2 | XLM, XRP, HBAR, ALGO, ADA | payment / old-guard L1s |
| SPC3 | NEAR, AVAX, SOL, ATOM, FET | new smart-contract L1s (alt-L1) |
| SPC4 | ZEC, DASH, BNB, LTC, CAKE | legacy/privacy + exchange coins |

**CCA — crypto vs macro basket** (BTC, SPX, DXY, UST10Y, VIX; 263 weeks; BTC kept
on the macro side only to avoid double-counting):
- **CC1 ρ = +0.875**, driven by BTC+, SPX+, VIX− — crypto's dominant risk-on link
  to BTC and equities. CC2–CC5 (ρ 0.26–0.42) are dollar/rates/vol secondary links.
- **Macro-spanned share of crypto variance ≈ 38%** (per-coin R² on the basket;
  ETH 64% most spanned, ZEC 18% least). **≈ 62% is crypto-idiosyncratic** — the
  alpha space the factor model should target.

Deliverables: `returns_weekly.parquet`, `reference_weekly.parquet`,
`sparse_pca_loadings.parquet`, `sparse_pca_factor_returns.parquet`,
`cca_canonical.parquet`, `cca_macro_spanned.parquet`,
`figures/sparse_pca_loadings.png`.

*Notes:* gold omitted (no clean free daily FRED gold series). **Next:** validate
these features through GX / Fama-MacBeth controls before crediting them in the
live signal set, then Goal 3 (long-tilt exposure).

---

## Goal 2.5 — STATUS: COMPLETE (2026-05-29)

Built `08_factor_validation.py` → `RESULTS.md` (plain-language) +
`factor_validation_stats.parquet`. Factors rebuilt on the 5y panel faithful to
08_nalfp definitions (size, momentum, low-vol, NetMom, NetRel via networkx
Louvain; SPC1–4 from Sparse PCA). FunC/TVLC/SupC not testable over 5y (no
fundamentals). Significance = Newey-West t on the IC (the competition's
ranking-power metric), IS vs OOS.

**Headline finding (honest, and the competition story):**
- **VolC is the only robust factor** — IC significant in-sample (t = −3.3) *and*
  out-of-sample (t = −4.3). Sign is **negative / crypto-inverted**: a mild
  low-vol tilt across the cross-section, though the high-vol tail is fat so the
  raw tercile L/S is noisy. Volatility is an informative ranking signal that must
  have its extremes capped.
- **Size & momentum did NOT survive 5 years** (|IC t| < 2) — the 52-week paper's
  t = 3–4 were short-window / regime-specific (those were Fama-MacBeth λ on 52w,
  not 5y time-series). Network factors weak. SPC1–4 are mostly market beta.
- **Shortlist (passed IS & OOS): VolC.**

This is a stronger, more defensible competition narrative than an overfit zoo:
one characteristic carries robust cross-sectional information over 5 years, with
a crypto-specific twist; the textbook premia are regime-fragile.

## Open questions to resolve before building

1. ~~**History threshold:** 5yr vs 4yr?~~ **RESOLVED:** 5yr — only +3 names at 4yr,
   so 5yr is well-supported and gives 33 backbone coins / 264 weeks.
2. ~~**Core universe size:**~~ **RESOLVED:** 33-coin backbone (quintile legs ~6–7);
   trading universe is broader (point-in-time, up to 62/week).
3. **Reference basket for CCA:** confirm the 5–6 tickers and their data source.
   (One hygiene note: `PAXG` sits in the backbone but is a **gold-backed** token —
   consider excluding it and `XAUT` as commodity proxies before factor work.)
4. **Tilt mechanism:** static 80/20, regime-conditional, or market-neutral-core + beta sleeve?
5. **Relationship to v3:** does Stage 09 replace Pillar 2's hidden factors, or run alongside them
   for comparison?

## Proposed build order
`Goal 1 (universe + coverage)` → `Goal 2 (Sparse PCA, then CCA, then FMB-gated wiring)` →
`Goal 3 (parameterise exposure → regime scaler → attribution)`.
