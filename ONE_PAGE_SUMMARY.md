# NALFP — Research Summary

**Track #1: Crypto Factor Rebalancing Strategy** · Artemis Analytics Quant Competition · May 2026

---

**Thesis:** Crypto cross-sectional returns are better predicted by the *interaction* of network community structure and factor pricing than by either source alone. We build a weekly long/short portfolio that adapts between network and latent-factor signals based on their out-of-sample predictive accuracy.

---

### Strategy Architecture (3 Pillars)

| Pillar | Method | Output |
|:-------|:-------|:-------|
| **1 — Network** | Rolling 12-wk Spearman correlation → MST → Louvain communities (7–11/wk, mean entropy 2.18) | `within_cluster_mom`, `cross_cluster_rel`, `cluster_id` |
| **2 — Factor Pricing** | 9 long/short factor portfolios → Giglio–Xiu (2021) 3-pass with K\_hidden=3 latent factors; walk-forward $\hat{\lambda}$ refit every 4 wks | $E_{gx} = \beta' \hat{\lambda}$ per asset per week |
| **3 — Adaptive Blend** | IC-weighted: $E_{final} = w_{net} \cdot z(E_{net}) + (1 - w_{net}) \cdot z(E_{gx})$; $w_{net}$ = rolling 8-wk OOS Spearman IC ratio | Blended expected return ranking |

**Portfolio:** Long top quintile / short bottom quintile · inverse-vol weights · dollar-neutral · 5% max per name · 40% cluster cap · 30% turnover budget · 15% vol target (3× lev cap). Median 16 long + 16 short names/week.

---

### Factor Zoo — Key Results (Full Sample & GX Cross-Section)

| Factor | Ann. Ret | Sharpe | $\hat{\lambda}_{full}$ (%/wk) | t(full) | Verdict |
|:-------|:--------|:-------|:---------------|:--------|:--------|
| SMBC (size) | +93.7% | +3.54 | +0.59 | +1.62 | Priced (borderline) |
| NetRel (cross-cluster rotation) | +74.8% | +2.24 | +1.12 | +2.38 | **Priced** |
| NetMom (within-cluster mom) | +30.4% | +1.33 | +0.76 | +2.42 | **Priced** |
| MomC (momentum) | +40.0% | +1.09 | +0.96 | +1.74 | **Priced** |
| VolC (low-vol) | +10.0% | +0.22 | +0.99 | +3.24 | **Priced** (highest $|t|$) |
| RC (market) | −32.4% | −0.78 | −0.25 | −1.13 | Not priced (regime-dependent) |
| FunC (fund. yield) | +26.6% | +0.85 | −0.12 | −0.32 | Not priced (sparse coverage) |

GX hidden factors H1–H3: individually insignificant ($|t| < 1$). Five of seven observed factors survive $|t| \geq 1.65$ in the observed-only model; four survive after latent adjustment.

---

### OOS Backtest Results (24 Weeks, Walk-Forward)

| | NALFP | NALFP (no cap) | EW Mom Long | `plus_lat` |
|:--|:--|:--|:--|:--|
| **Ann. Return** | −14.8% | −17.4% | +58.1% | +129.0% |
| **Ann. Vol** | 10.3% | 10.3% | 43.0% | 34.4% |
| **Sharpe (OOS)** | **−1.44** | −1.69 | +1.35 | +3.75 |
| **Sharpe 95% CI** | [−3.45, +1.18] | [−3.66, +1.11] | [−2.08, +6.61] | [0.51, +8.89] |
| **Max DD** | −6.6% | −7.8% | −24.8% | −7.4% |
| **Turnover/wk** | 7.4% | 7.4% | 33.4% | 65.1% |

Training Sharpe: +2.30. OOS blend weight on network: $\bar{w}_{net} = 0.25$ (network IC negative OOS → blend tilts heavily to GX). Cluster cap improves OOS Sharpe by +0.25 and reduces drawdown by 1.2 pp.

---

### Honest Assessment

**What worked:** (1) Factor identification is statistically grounded — four factors survive latent-adjustment pricing. (2) The network pillar is operationally useful — the cluster cap reduces drawdown even when its cross-sectional signal is negative OOS. (3) Vol targeting delivers single-digit volatility and −6.6% max drawdown vs. −24.8% for the momentum benchmark.

**What failed:** (1) OOS Sharpe is −1.44 with a CI that crosses zero — the strategy does not earn positive risk-adjusted returns in this sample. (2) Network signal IC is negative OOS (−0.014); the blend defaults to GX. (3) Factor premia reverse between train and test: the strong small-cap premium in training (SMBC Sharpe +3.54) does not persist.

**What would break this:** A regime shift flipping SMBC or MomC signs out-of-sample — exactly what occurred in the OOS window. Whether $\hat{\lambda}$ generalises is an empirical question unanswerable with 24 OOS weeks.

**Structural limits:** 52-wk sample / 24-wk OOS · K\_hidden = 3 capped, not data-driven · TVLC & SupC excluded for sparse coverage · 10 bps cost model optimistic for tail names · no funding-rate or perp-basis data.