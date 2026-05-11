# Bug fixes for paper-reproduction folders (04 / 05 / 06 / 07)

## Context

`04_factors`, `05_btc_direction`, `06_artemis_econometrics`, and `07_hidden_factor_pricing` are paper-reproduction studies, not Artemis competition entries. Their value is in helping the user understand the source papers — so output **fidelity** matters more than completeness or backtest performance.

Code review surfaced six concrete correctness bugs and one framing issue that materially affect the figures and REPORT.md numbers each folder generates. The goal is surgical: fix the bugs, re-run the affected scripts, let the generators refresh figures and reports. No methodological revamps (no walk-forward, no panel rebuild), no new analyses, no interface changes.

Priority order is **04 → 05 → 06 → 07**. The user can stop after any folder and still have a clean improvement.

## Fixes

### 04_factors (priority 1)

**A1 — T-factor ATR lower-band sign error.** Effort: S.

The lower band was built with `.max() + atr` (resistance formula) so the short condition never triggers. T-factor IC pinned near zero is an artefact of this, not a real finding.

- `04_factors/04_RAAM_v2_composite.py:107`
  - Before: `d["lower"] = d["low"].rolling(period).max() + d["atr"]`
  - After:  `d["lower"] = d["low"].rolling(period).min() - d["atr"]`
- `03_analysis/05_factor_signals.py:153` (same bug, copy-pasted)
  - Before: `df["lower"] = df["low"].rolling(period).max() + df["atr"]`
  - After:  `df["lower"] = df["low"].rolling(period).min() - df["atr"]`

**A2 — S-factor overhang snapshot leakage.** Effort: M. Drop overhang from the IC test.

`overhang_z` is computed once from today's CoinGecko snapshot (`sym_to_fdv_now`, `sym_to_mcap_now`) and tiled across history with `np.tile`. The repo has no FDV history, so the only honest move is to remove overhang from the time-series IC and keep it only in the latest-cross-section scatter for descriptive purposes.

- `04_factors/02_S_supply_absorption.py`
  - Keep lines 99–105 (the latest-snapshot `overhang` Series) **only** because Panel 3 (lines 130–155) uses it as a one-period scatter.
  - Lines 161–173 (IC panel): drop `overhang_z`, `overhang_z_panel`, and the `-0.4 * overhang_z_panel` term. Replace with `S_score = -emission_z` (and rescale only if you want comparable magnitude — not required).
  - Update the module docstring formula (lines 11–16) to `S_score = -z(emission_90d)`.
- `04_factors/04_RAAM_v2_composite.py:148–165`
  - Delete the `overhang` / `overhang_z` / `overhang_z_panel` block.
  - Replace with: `S_score = -emission_z`
- `04_factors/README.md:23` — change the S formula in the factor table to `−z(emission_90d)`; under "Caveats" add a one-liner: "FDV-overhang removed from the IC test — only the latest snapshot is available, so historical overhang would be look-ahead. Snapshot is still visualised in `02_S_supply_absorption/03_emission_vs_overhang`."
- `04_factors/README.md:40–52` — the IC scoreboard predates the fixes; annotate with a "pre-fix; see `figures/04_RAAM_v2_composite/03_per_factor_cumulative_ic.png` for current values" caption.

### 05_btc_direction (priority 2)

**B1 — Mixed feature-lag regime.** Effort: S.

Technical features (`02_feature_engineering.py:80–87`) are already lagged with `.shift(1)`. Volume, on-chain (`artemis_*`), and DeFi-liquidity (`defillama_*`) features at lines 68–78 / 89–102 / 104–120 are at row t — but the target is t+1 and these series publish T+1 in practice. Apply a single global `.shift(1)` to the exogenous block.

- `05_btc_direction/02_feature_engineering.py`
  - Define `EXOGENOUS_PREFIXES = ("base_volume", "quote_volume", "trade_count", "cg_", "log_base_volume", "log_quote_volume", "log_trade_count", "log_cg_", "log_artemis_", "log_defillama_", "defillama_")` at module top.
  - Just before the target block (line 121–122), insert:
    ```python
    exo_cols = [c for c in features.columns
                if c != "date"
                and any(c.startswith(p) or c == p for p in EXOGENOUS_PREFIXES)]
    features[exo_cols] = features[exo_cols].shift(1)
    ```
  - Update the `leakage_control` manifest string (line 155) to reflect the new lag policy.
- Nothing else in 05 needs editing — `03_feature_selection.py` through `06_report.py` consume `keep` features unchanged.

### 06_artemis_econometrics (priority 3)

**C1 — Latent-controls window includes current week.** Effort: S.

`04_latent_controls.py:97` slices `ret.iloc[i - WINDOW_WEEKS + 1 : i + 1]` — the `+ 1` includes week t and contaminates `pc*_load` with the very week we predict.

- `06_artemis_econometrics/04_latent_controls.py:95–97`
  - Before: `if i < WINDOW_WEEKS - 1: continue` and `window = ret.iloc[i - WINDOW_WEEKS + 1 : i + 1]`
  - After:  `if i < WINDOW_WEEKS: continue` and `window = ret.iloc[i - WINDOW_WEEKS : i]`
- `residual_returns` (lines 70–87) logic unchanged. Update its docstring to note "residual of the most recent in-window week (t-1) now that the window is past-only".

**C2 — Contemporaneous mom regressor in alpha test.** Effort: S. Drop the regressor.

`06_backtest.py:127–137` builds `mom_factor` from same-week `fwd_ret_1w` quintile spreads — i.e., a perfect-foresight benchmark. Simpler and more honest than re-shifting: regress LS-spread on market only.

- `06_artemis_econometrics/06_backtest.py`
  - `market_factors` (107–140): delete lines 125–137 (the `mom = []` loop) and the merge; return `market` only.
  - `alpha_test` (143–174): drop `mom_factor` from `x`. Use `x = merged[["mkt_ret"]].to_numpy(dtype=float)`; drop `beta_mom` from the result row.
- `06_artemis_econometrics/07_report.py:106` (the alpha bullet) — change wording to "intercept of long-short return regressed on equal-weight market return (no contemporaneous momentum control)".

**C3 — `base_lasso` is degenerate.** Effort: S. Remove from comparison.

ElasticNetCV on 36 weeks × 12 features collapses to all-zero coefficients (see REPORT.md). Drop it from the model set; the function stays for future use.

- `06_artemis_econometrics/05_models.py`
  - Remove `lasso = fit_elasticnet(train, base_cols)` (line 182), `lasso_pred = predict_linear(...)` (188), the `base_lasso=lasso_pred.values` field in `.assign` (197), and `lasso.rename("base_lasso")` in the betas concat (213).
- `06_artemis_econometrics/07_report.py` — add a one-line footnote under "Model Comparison": "_`base_lasso` (ElasticNetCV) removed this iteration — degenerate (all-zero) coefficients on 36 weeks × 12 features; kept as a known limitation rather than tuned._"

### 07_hidden_factor_pricing (priority 4)

**D1 — Full-sample SVD is fine; report framing isn't.** Effort: S. No algorithm change.

Following Giglio-Xiu, full-sample latent SVD is defensible *for asset-pricing inference*. The current REPORT.md doesn't say that, so a casual reader will mistake it for a predictive backtest.

- `07_hidden_factor_pricing/05_report.py`
  - Insert a new section above `## Pricing Results` (just before line 82 in the f-string):
    ```
    ## Scope of This Test
    This is an **in-sample asset-pricing inference test**, not a predictive backtest. Following Giglio & Xiu, the latent factor SVD is fit on the full panel and the same panel is priced — appropriate for testing whether observed factor premia survive latent controls, not for trading. The t-stats below cannot be read as out-of-sample alpha.

    ```
  - Append to the survival section (after the existing block, around line 88): `\n\n_Caveat: latent factors are extracted from the full sample; survival here means in-sample robustness, not predictive survival._`

## Critical files to modify

- `04_factors/04_RAAM_v2_composite.py` (A1, A2)
- `04_factors/02_S_supply_absorption.py` (A2)
- `04_factors/README.md` (A2 doc update)
- `03_analysis/05_factor_signals.py` (A1 sibling)
- `05_btc_direction/02_feature_engineering.py` (B1)
- `06_artemis_econometrics/04_latent_controls.py` (C1)
- `06_artemis_econometrics/06_backtest.py` (C2)
- `06_artemis_econometrics/05_models.py` (C3)
- `06_artemis_econometrics/07_report.py` (C2, C3 wording)
- `07_hidden_factor_pricing/05_report.py` (D1)

## Re-run sequence

Run each per-folder chain from the project root using the project venv (`01_Data_Collection/.venv/bin/python`).

| Folder | Re-run order | Refreshed outputs |
|---|---|---|
| 04 | `04_factors/02_S_supply_absorption.py` → `04_factors/04_RAAM_v2_composite.py` → `03_analysis/05_factor_signals.py` | `04_factors/figures/02_S_supply_absorption/*`, `04_factors/figures/04_RAAM_v2_composite/*`, `03_analysis/figures/05_factor_signals/*` |
| 05 | `02_feature_engineering.py` → `03_feature_selection.py` → `04_train_eval.py` → `05_trading_simulation.py` → `06_report.py` | all `05_btc_direction/artifacts/*`, all `figures/*`, `REPORT.md` |
| 06 | `04_latent_controls.py` → `05_models.py` → `06_backtest.py` → `07_report.py` | `latent_controls.parquet`, `model_predictions.parquet`, `model_betas.parquet`, `tables/*`, `figures/06_backtest/*`, `REPORT.md` |
| 07 | `05_report.py` only | `REPORT.md` |

## Verification

After each fix + re-run, visually check the listed outputs. The change you should see is described, not the direction — these are correctness fixes, so unknown sign changes are acceptable.

- **04 / A1**: `04_factors/figures/04_RAAM_v2_composite/03_per_factor_cumulative_ic.png` — the T line should now show meaningful slope (currently flat ≈ 0 because short triggers were silently disabled). `03_analysis/figures/05_factor_signals/*` ATR-band charts: lower band should sit *below* price, not above.
- **04 / A2**: `04_factors/figures/02_S_supply_absorption/04_S_information_coefficient.png` — IC magnitudes change, no longer dominated by a constant cross-sectional tilt. `04_factors/figures/04_RAAM_v2_composite/01_factor_correlation.png` — S's correlations with M / V / G shift modestly.
- **05 / B1**: `05_btc_direction/REPORT.md` — balanced accuracy and ROC AUC should drop slightly (we removed a same-day leak). The over-claimed long-short Sharpe should fall — that is the intended outcome.
- **06 / C1**: `06_artemis_econometrics/artifacts/data/latent_controls.parquet` — first usable week shifts forward by one. `pc*_load` values for any given week no longer correlate mechanically with that week's `mom_1w`.
- **06 / C2**: `06_artemis_econometrics/artifacts/tables/alpha_test.parquet` — `beta_mom` column gone; alpha and `t_alpha` move (typically up in magnitude). `REPORT.md` alpha bullet reads "no contemporaneous momentum control".
- **06 / C3**: `model_summary.parquet` and `REPORT.md` — `base_lasso` row gone, with the footnote present.
- **07 / D1**: `07_hidden_factor_pricing/REPORT.md` has the new "Scope of This Test" section and survival caveat; tables unchanged.

## Effort summary

A1 — S · A2 — M · B1 — S · C1 — S · C2 — S · C3 — S · D1 — S. Total ≈ one focused sitting.

## Reusable helpers worth knowing about

- `04_factors/_common.py`: `spearman_ic`, `ic_summary`, `cross_sectional_rank`, `forward_returns`, `exclude_symbols` — already correct; reuse.
- `06_artemis_econometrics/_common.py`: `standardize_features`, `winsorize_cs`, `coerce_week` — already correct; reuse.
- `05_btc_direction/_common.py`: `chronological_split_indices`, `save_plotly` — already correct; reuse.
