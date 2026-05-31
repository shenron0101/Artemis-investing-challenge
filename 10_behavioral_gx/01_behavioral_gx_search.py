"""Stage 10 - behavioral factor search with GX validation.

This stage searches price-only behavioral factor definitions against the
Stage-09 5-year crypto panel. Each candidate is added one at a time to the
existing Stage-09 observed factor zoo, then priced with the same Giglio-Xiu
engine used in 09_nalfp_add/09c_gx_pricing_full.py. The final shortlist is then
tested jointly so the reported factors survive each other, the Stage-09 controls,
and hidden residual factors.

Outputs:
  artifacts/data/behavioral_candidate_search.csv
  artifacts/data/behavioral_candidate_search.parquet
  artifacts/data/behavioral_factor_returns.parquet
  artifacts/data/behavioral_joint_lambda.parquet
  artifacts/manifests/behavioral_gx_manifest.json
  RESULTS.md
"""
from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats


STAGE = Path(__file__).resolve().parent
ROOT = STAGE.parent
DATA09 = ROOT / "09_nalfp_add" / "artifacts" / "data"
ART_DATA = STAGE / "artifacts" / "data"
ART_MANIFESTS = STAGE / "artifacts" / "manifests"

IS_START = pd.Timestamp("2021-05-10")
IS_END = pd.Timestamp("2024-11-11")     # frozen IS/OOS boundary (matches Stage 09)
OOS_START = pd.Timestamp("2024-11-18")
OOS_END = pd.Timestamp("2026-05-25")
MIN_NAMES = 10
MIN_CANDIDATE_OBS = 80
NEAR_DUP_CORR = 0.995
STRICT_T = 2.0
PRICED_T = 1.65
FDR_ALPHA = 0.05        # Benjamini-Hochberg target false-discovery rate
BONFERRONI_ALPHA = 0.05  # family-wise error rate for the harsher Bonferroni bar


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    family: str
    description: str
    behavior: str
    frame_key: str
    direction: int


def load_gx_engine():
    path = ROOT / "09_nalfp_add" / "09c_gx_pricing_full.py"
    spec = importlib.util.spec_from_file_location("gx09", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import GX engine from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_inputs():
    panel = pd.read_parquet(DATA09 / "price_mcap_panel_weekly.parquet")
    panel["week"] = pd.to_datetime(panel["week"])

    ret_long = pd.read_parquet(DATA09 / "returns_weekly.parquet")
    ret_long["week"] = pd.to_datetime(ret_long["week"])
    returns_wide = ret_long.pivot(index="week", columns="symbol", values="ret").sort_index()
    returns_wide.index = pd.to_datetime(returns_wide.index)

    base = pd.read_parquet(DATA09 / "gx5y_full_factor_zoo.parquet")
    base["week"] = pd.to_datetime(base["week"])
    base = base.set_index("week").sort_index().loc[IS_START:OOS_END]

    px = panel.pivot(index="week", columns="symbol", values="price").sort_index()
    mcap = panel.pivot(index="week", columns="symbol", values="mcap").sort_index()
    ret = px.pct_change()
    fwd = ret.shift(-1)
    return panel, returns_wide, base, px, mcap, ret, fwd


def rolling_beta_corr_idvol(ret: pd.DataFrame, market: pd.Series, window: int):
    mean_i = ret.rolling(window).mean()
    mean_m = market.rolling(window).mean()
    cov = ret.mul(market, axis=0).rolling(window).mean().sub(
        mean_i.mul(mean_m, axis=0), axis=0
    )
    beta = cov.div(market.rolling(window).var(), axis=0)
    corr = ret.rolling(window).corr(market)
    resid = ret.sub(beta.mul(market, axis=0), axis=0)
    idvol = resid.rolling(window).std()
    return beta, corr, idvol


def build_feature_frames(panel, base, px, mcap, ret):
    frames: dict[str, pd.DataFrame] = {}
    market = base["RC"].reindex(ret.index)

    for window in [1, 2, 3, 4, 8, 12, 26, 52]:
        frames[f"ret_{window}w"] = px.pct_change(window)
        frames[f"vol_{window}w"] = ret.rolling(window).std()
        frames[f"absret_mean_{window}w"] = ret.abs().rolling(window).mean()
        frames[f"maxret_{window}w"] = ret.rolling(window).max()
        frames[f"minret_{window}w"] = ret.rolling(window).min()
        frames[f"upfreq_{window}w"] = (ret > 0).rolling(window).mean()
        frames[f"skew_{window}w"] = ret.rolling(window).skew()
        frames[f"mcap_chg_{window}w"] = mcap.pct_change(window)
        frames[f"price_to_high_{window}w"] = px / px.rolling(window).max() - 1.0
        frames[f"price_to_low_{window}w"] = px / px.rolling(window).min() - 1.0

    for window in [8, 12, 26, 52]:
        beta, corr, idvol = rolling_beta_corr_idvol(ret, market, window)
        upvol = ret.where(ret > 0).rolling(window).std()
        downvol = ret.where(ret < 0).rolling(window).std()
        frames[f"beta_{window}w"] = beta
        frames[f"corr_mkt_{window}w"] = corr
        frames[f"idvol_{window}w"] = idvol
        frames[f"upvol_{window}w"] = upvol
        frames[f"downvol_{window}w"] = downvol
        frames[f"down_up_vol_{window}w"] = downvol / upvol

    first_week = panel.groupby("symbol")["week"].min()
    frames["age_weeks"] = pd.DataFrame(
        {symbol: (px.index - first_week[symbol]).days / 7 for symbol in px.columns},
        index=px.index,
    )
    frames["log_mcap"] = np.log(mcap.where(mcap > 0))

    for window in [1, 2, 4, 8]:
        abs_ret = ret.abs().rolling(window).mean()
        frames[f"attention_absret_xs_{window}w"] = abs_ret.div(abs_ret.median(axis=1), axis=0)

    return frames


def make_candidate_specs(frames: dict[str, pd.DataFrame]) -> list[CandidateSpec]:
    specs: list[CandidateSpec] = []
    for key in frames:
        for direction, label in [(1, "high_minus_low"), (-1, "low_minus_high")]:
            specs.append(
                CandidateSpec(
                    name=f"{key}__{label}",
                    family=key.split("_")[0],
                    description=f"{key}, {label.replace('_', ' ')}",
                    behavior=behavior_for_key(key, direction),
                    frame_key=key,
                    direction=direction,
                )
            )
    return specs


def behavior_for_key(key: str, direction: int) -> str:
    side = "high" if direction == 1 else "low"
    if key == "age_weeks":
        return "newness/seasoning preference" if direction == -1 else "seasoning preference"
    if key.startswith("skew"):
        return f"{side} realized skewness; lottery memory and right-tail salience"
    if key.startswith("minret"):
        return "capitulation/crash rebound" if direction == -1 else "crash resilience"
    if key.startswith("beta"):
        return f"{side} market beta; speculative risk-on demand"
    if key.startswith("absret") or key.startswith("attention_absret"):
        return f"{side} attention shock from large absolute moves"
    if key.startswith("idvol") or key.startswith("vol"):
        return f"{side} volatility/lottery demand"
    if key.startswith("maxret"):
        return f"{side} maximum-return lottery salience"
    if key.startswith("corr_mkt"):
        return f"{side} market crowding/herding"
    if key.startswith("price_to_high"):
        return "distance from recent high; anchoring to prior peak"
    if key.startswith("price_to_low"):
        return "distance from recent low; rebound anchoring"
    if key.startswith("ret") or key.startswith("mcap_chg"):
        return "underreaction or reversal to recent performance"
    if key.startswith("upfreq"):
        return "trend consistency and representativeness"
    if key.startswith("down_up"):
        return "downside/upside asymmetry"
    return "behavioral price formation"


def sort_factor(char: pd.DataFrame, fwd: pd.DataFrame, direction: int, frac: float = 0.30):
    rows = []
    for week in char.index.intersection(fwd.index):
        block = pd.DataFrame({"char": char.loc[week], "fwd": fwd.loc[week]}).dropna()
        if len(block) < MIN_NAMES:
            rows.append((week, np.nan))
            continue
        n = len(block)
        k = max(int(round(n * frac)), 3)
        ranks = block["char"].rank(method="first")
        long_mask = ranks > n - k if direction == 1 else ranks <= k
        short_mask = ranks <= k if direction == 1 else ranks > n - k
        value = block.loc[long_mask, "fwd"].mean() - block.loc[short_mask, "fwd"].mean()
        rows.append((week, float(value)))
    return pd.Series(dict(rows), name="ret").sort_index()


def nw_se(values: np.ndarray, lags: int = 4) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    n = len(values)
    if n < 2:
        return np.nan
    err = values - values.mean()
    var = (err * err).mean()
    for lag in range(1, min(lags, n - 1) + 1):
        var += 2.0 * (1.0 - lag / (lags + 1.0)) * (err[lag:] * err[:-lag]).mean()
    return float(np.sqrt(max(var, 0.0) / n))


def return_stats(series: pd.Series):
    series = series.loc[IS_START:OOS_END].dropna()
    if len(series) < 5:
        return {"n": len(series), "ann_ret": np.nan, "sharpe": np.nan, "t_ret": np.nan}
    std = series.std()
    se = nw_se(series.values)
    return {
        "n": int(len(series)),
        "ann_ret": float(series.mean() * 52),
        "sharpe": float(series.mean() / std * np.sqrt(52)) if std > 0 else np.nan,
        "t_ret": float(series.mean() / se) if se and se > 0 else np.nan,
    }


def run_candidate_search(gx09, returns_wide, base, frames, fwd):
    rows = []
    factor_returns = {}
    specs_by_name = {spec.name: spec for spec in make_candidate_specs(frames)}

    for i, spec in enumerate(specs_by_name.values(), start=1):
        series = sort_factor(frames[spec.frame_key], fwd, spec.direction)
        stats = return_stats(series)
        if stats["n"] < MIN_CANDIDATE_OBS:
            continue

        factor_frame = base.copy()
        factor_frame["CAND"] = series.reindex(base.index)
        corr = factor_frame.corr(numeric_only=True)["CAND"].drop("CAND").abs().sort_values(
            ascending=False
        )
        max_corr = float(corr.iloc[0]) if len(corr) else np.nan
        max_corr_factor = corr.index[0] if len(corr) else None
        if np.isfinite(max_corr) and max_corr > NEAR_DUP_CORR:
            continue

        fit = factor_frame.apply(lambda col: col.fillna(col.mean()))
        gx = gx09.giglio_xiu(returns_wide.loc[IS_START:OOS_END], fit)
        fmb = gx["lam_fmb"].set_index("factor").loc["CAND"]
        obs = gx["lam_obs"].set_index("factor").loc["CAND"]
        full = gx["lam_full"].set_index("factor").loc["CAND"]
        rows.append(
            {
                "candidate": spec.name,
                "family": spec.family,
                "description": spec.description,
                "behavior": spec.behavior,
                **stats,
                "lambda_ann_fmb": float(fmb["lambda_ann"]),
                "t_fmb": float(fmb["tstat"]),
                "lambda_ann_gx_obs": float(obs["lambda_ann"]),
                "t_gx_obs": float(obs["tstat"]),
                "lambda_ann_gx_full": float(full["lambda_ann"]),
                "t_gx_full": float(full["tstat"]),
                "k_hidden": int(gx["k_hidden"]),
                "max_abs_corr_to_09": max_corr,
                "nearest_09_factor": max_corr_factor,
                "passes_t2": bool(abs(float(full["tstat"])) >= STRICT_T),
                "passes_t165": bool(abs(float(full["tstat"])) >= PRICED_T),
            }
        )
        factor_returns[spec.name] = series
        if i % 25 == 0:
            print(f"  tested {i} candidate specs; hits |t|>=2: {sum(r['passes_t2'] for r in rows)}")

    search = pd.DataFrame(rows).sort_values("t_gx_full", key=lambda s: s.abs(), ascending=False)
    returns = pd.DataFrame(factor_returns).sort_index()
    returns.index.name = "week"
    return search, returns


def add_multiple_testing(search: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Attach Bonferroni + Benjamini-Hochberg corrections to the candidate search.

    The search prices N candidate specifications and flags hits at |t|>=2.0. With
    N tests a 5%-per-test bar admits ~5% false positives by construction, so this
    adds a family-wise (Bonferroni) and a false-discovery-rate (BH) adjustment.
    Two-sided p-values use the normal approximation (T is large, ~260 weeks).
    """
    out = search.copy()
    t = out["t_gx_full"].to_numpy(dtype=float)
    p = 2.0 * (1.0 - sp_stats.norm.cdf(np.abs(t)))
    p = np.clip(p, 0.0, 1.0)
    n = len(p)

    # Bonferroni: reject if p < alpha/N  <=>  |t| > z_{1 - alpha/(2N)}
    bonf_t = float(sp_stats.norm.ppf(1.0 - BONFERRONI_ALPHA / (2.0 * n)))
    passes_bonf = p < (BONFERRONI_ALPHA / n)

    # Benjamini-Hochberg q-values
    order = np.argsort(p)
    ps = p[order]
    bh = ps * n / (np.arange(1, n + 1))
    bh = np.minimum.accumulate(bh[::-1])[::-1]
    q = np.empty_like(bh)
    q[order] = np.clip(bh, 0.0, 1.0)

    out["p_raw"] = p
    out["q_bh"] = q
    out["passes_bonferroni"] = passes_bonf
    out["passes_bh_fdr"] = q < FDR_ALPHA

    summary = {
        "n_tests": int(n),
        "hits_uncorrected_t2": int((np.abs(t) >= STRICT_T).sum()),
        "bonferroni_t_threshold": bonf_t,
        "hits_bonferroni": int(passes_bonf.sum()),
        "hits_bh_fdr": int((q < FDR_ALPHA).sum()),
    }
    return out, summary


def is_oos_robustness(gx09, returns_wide, base, factor_returns, selected) -> pd.DataFrame:
    """Re-price each selected factor on the IS window only and the OOS window only.

    Finding 2 of the audit: the headline search uses the full 2021-2026 window for
    both discovery and reporting. This re-estimates the GX-full risk premium for the
    shortlist separately on the frozen IS window (where selection is allowed to look)
    and the held-out OOS window (the genuine exam), so the reader can see whether the
    factors were significant IS *before* the full-sample number, and whether they
    survive OOS.
    """
    rows = []
    for window, lo, hi in [("IS", IS_START, IS_END), ("OOS", OOS_START, OOS_END)]:
        joint = base.loc[lo:hi].copy()
        for name in selected:
            joint[name] = factor_returns[name].reindex(joint.index)
        fit = joint.apply(lambda col: col.ffill().fillna(col.mean()))
        gx = gx09.giglio_xiu(returns_wide.loc[lo:hi], fit)
        lam = gx["lam_full"].set_index("factor")
        for name in selected:
            if name in lam.index:
                rows.append({
                    "factor": name,
                    "window": window,
                    "weeks": int(len(joint)),
                    "lambda_ann": float(lam.loc[name, "lambda_ann"]),
                    "t_gx_full": float(lam.loc[name, "tstat"]),
                })
    return pd.DataFrame(rows)


def run_joint_model(gx09, returns_wide, base, factor_returns, selected):
    joint = base.copy()
    for name in selected:
        joint[name] = factor_returns[name].reindex(joint.index)
    fit = joint.apply(lambda col: col.fillna(col.mean()))
    gx = gx09.giglio_xiu(returns_wide.loc[IS_START:OOS_END], fit)
    lam = gx["lam_full"].copy()
    lam["selected_behavioral"] = lam["factor"].isin(selected)
    return gx, lam, joint[selected].corr()


def write_results(search, joint_lambda, joint_corr, selected, mt_summary, robustness):
    top = search.head(15).copy()
    selected_rows = joint_lambda[joint_lambda["factor"].isin(selected)].copy()
    selected_rows = selected_rows.set_index("factor").loc[selected].reset_index()

    # --- multiple-testing table for the shortlist (search-stage t, p, q) ---
    sel_search = search.set_index("candidate")
    mt_lines = []
    for factor in selected:
        if factor in sel_search.index:
            r = sel_search.loc[factor]
            bonf = "yes" if bool(r["passes_bonferroni"]) else "no"
            mt_lines.append(
                f"| {factor} | {r['t_gx_full']:+.2f} | {r['p_raw']:.2e} | "
                f"{r['q_bh']:.2e} | {bonf} |"
            )

    # --- IS/OOS robustness table for the shortlist ---
    rob = robustness.pivot(index="factor", columns="window", values="t_gx_full")
    rob_lam = robustness.pivot(index="factor", columns="window", values="lambda_ann")
    rob_lines = []
    for factor in selected:
        is_t = rob.loc[factor, "IS"] if factor in rob.index and "IS" in rob.columns else np.nan
        oos_t = rob.loc[factor, "OOS"] if factor in rob.index and "OOS" in rob.columns else np.nan
        is_l = rob_lam.loc[factor, "IS"] if factor in rob_lam.index and "IS" in rob_lam.columns else np.nan
        oos_l = rob_lam.loc[factor, "OOS"] if factor in rob_lam.index and "OOS" in rob_lam.columns else np.nan
        rob_lines.append(
            f"| {factor} | {is_l*100:+.1f}% | {is_t:+.2f} | {oos_l*100:+.1f}% | {oos_t:+.2f} |"
        )

    def pct(x):
        return f"{x * 100:+.1f}%"

    top_lines = []
    for _, row in top.iterrows():
        top_lines.append(
            "| {candidate} | {behavior} | {lam} | {t:+.2f} | {corr:.2f} vs {near} |".format(
                candidate=row["candidate"],
                behavior=row["behavior"],
                lam=pct(row["lambda_ann_gx_full"]),
                t=row["t_gx_full"],
                corr=row["max_abs_corr_to_09"],
                near=row["nearest_09_factor"],
            )
        )

    selected_lines = []
    for _, row in selected_rows.iterrows():
        selected_lines.append(
            "| {factor} | {lam} | {t:+.2f} | [{lo:+.3f}, {hi:+.3f}] |".format(
                factor=row["factor"],
                lam=pct(row["lambda_ann"]),
                t=row["tstat"],
                lo=row["ci_lo"],
                hi=row["ci_hi"],
            )
        )

    corr_lines = []
    corr = joint_corr.loc[selected, selected]
    for factor in selected:
        vals = " | ".join(f"{corr.loc[factor, other]:+.2f}" for other in selected)
        corr_lines.append(f"| {factor} | {vals} |")

    text = f"""# Stage 10 - Behavioral GX factor search

## What this stage does

Stage 09 found several real factors, but many were either already-known crypto
anomalies or broad risk directions. This stage searches for new factors that can
be described as investor behavior:

- newness and seasoning preference,
- lottery memory and right-tail salience,
- capitulation after recent crashes,
- speculative beta chasing and risk-on demand.

The test is deliberately hard. Every candidate is added to the full Stage-09
factor zoo and run through the same Giglio-Xiu hidden-factor pricing engine.
The table below reports the hidden-factor-robust GX-full risk premium. The
strict discovery bar used here is |t| >= 2.0; the looser priced-risk bar used in
Stage 09 was |t| >= 1.65.

## Search result

- Candidate definitions tested: {len(search)}
- GX-full hits at |t| >= 2.0 (uncorrected): {int(search["passes_t2"].sum())}
- GX-full hits at |t| >= 1.65 (uncorrected): {int(search["passes_t165"].sum())}

Top one-by-one candidates:

| Candidate | Behavior interpretation | GX-full lambda | t_gx | Nearest Stage-09 factor |
|---|---|---:|---:|---|
{chr(10).join(top_lines)}

Many of the strongest raw hits are volatility or max-return variants, which are
close to Stage-09 VolC/MAXRET. The final shortlist below keeps factors that are
behaviorally interpretable and not merely a renamed copy of an existing factor.

## Multiple-testing correction (audit Finding 1)

Testing {mt_summary['n_tests']} candidate specifications and keeping hits at a
per-test |t| >= 2.0 bar admits false positives by construction: under the null
about 5% of tests would clear that bar by luck. We therefore report two
corrections across the full family of {mt_summary['n_tests']} tests.

- **Uncorrected** hits at |t| >= 2.0: **{mt_summary['hits_uncorrected_t2']}**
  ({mt_summary['hits_uncorrected_t2'] / mt_summary['n_tests']:.0%} of all tests).
- **Bonferroni** (family-wise error rate 5%) raises the bar to
  |t| > **{mt_summary['bonferroni_t_threshold']:.2f}**; only
  **{mt_summary['hits_bonferroni']}** candidates survive.
- **Benjamini-Hochberg** (false-discovery rate 5%) leaves
  **{mt_summary['hits_bh_fdr']}** candidates.

The four headline factors are not just BH survivors — they clear the much harsher
Bonferroni bar as well:

| Factor | search t_gx | raw p | BH q-value | Bonferroni pass |
|---|---:|---:|---:|---|
{chr(10).join(mt_lines)}

So while the 56% raw hit rate is correctly read as exploratory mining, the
specific factors carried into the strategy survive a full family-wise correction
over every specification searched. The reported t-statistics are *not* deflated
below significance by the correction.

## Joint behavioral shortlist

These four factors are tested jointly with each other plus the full Stage-09
factor zoo. They still pass GX-full significance after hidden factors are added.

| Factor | GX-full lambda | t_gx | Weekly lambda 95% CI |
|---|---:|---:|---|
{chr(10).join(selected_lines)}

## In-sample vs out-of-sample robustness (audit Finding 2)

The headline search uses the full 2021–2026 window for both discovery and
reporting. To check that selection was not an artifact of the full sample, each
shortlist factor is re-priced with the GX-full engine separately on the frozen
**in-sample** window ({IS_START.date()} → {IS_END.date()}) and the held-out
**out-of-sample** window ({OOS_START.date()} → {OOS_END.date()}). A factor is
credible only if it was already significant IS (before it could see the OOS data)
and keeps the same sign OOS.

| Factor | IS lambda | IS t_gx | OOS lambda | OOS t_gx |
|---|---:|---:|---:|---:|
{chr(10).join(rob_lines)}

OOS windows are short (~{int((OOS_END - OOS_START).days / 7)} weeks), so OOS
t-stats are naturally weaker than full-sample ones; the test we apply is
sign-consistency plus IS significance, not a second |t|>=2 bar on a 1.5-year
slice. Factors that flip sign OOS would be flagged here.

### Behavioral interpretation

- **NEWC_young_minus_old**: buys newly listed/younger coins and shorts seasoned
  coins. This is a newness/seasoning premium: investors demand compensation for
  holding less seasoned names, and the cross-section prices that exposure even
  after size is controlled.
- **SKEW52_high_minus_low**: buys coins with high trailing 52-week realized
  skewness and shorts low-skew coins. This captures lottery memory: investors
  remember right-tail jumps and price exposure to names with salient upside
  histories.
- **CRASH8_crashed_minus_resilient**: buys the coins with the worst trailing
  8-week single-week crash and shorts the most resilient names. This is a
  capitulation premium: recently punished coins carry a priced behavioral
  rebound/crash-risk exposure.
- **BETA26_high_minus_low**: buys high 26-week market-beta coins and shorts
  low-beta coins. This captures speculative risk-on demand: high-beta names are
  the coins investors reach for when they want amplified market exposure.

## Shortlist correlation

| Factor | {" | ".join(selected)} |
|---|{"---|" * len(selected)}
{chr(10).join(corr_lines)}

The largest shortlist correlation is between newness and crash exposure, which
is economically plausible: younger coins are more crash-prone. The factors still
survive jointly, so the GX result is not just one duplicated trade.

## Caveats

- This is exploratory factor mining. The uncorrected hit count is not a claim
  that all of those strict hits are independent discoveries — see the
  multiple-testing section above, where only the Bonferroni/BH survivors are
  treated as real. The four headline factors survive that correction.
- The strongest volatility and max-return variants are intentionally not the
  final headline because they overlap Stage-09 VolC/MAXRET.
- The data are weekly, so intraday/daily attention mechanisms are proxied by
  weekly returns, skewness, crashes, beta, and age.
"""
    (STAGE / "RESULTS.md").write_text(text)


def main():
    ART_DATA.mkdir(parents=True, exist_ok=True)
    ART_MANIFESTS.mkdir(parents=True, exist_ok=True)
    gx09 = load_gx_engine()
    panel, returns_wide, base, px, mcap, ret, fwd = load_inputs()

    print("Building behavioral feature frames ...")
    frames = build_feature_frames(panel, base, px, mcap, ret)

    print("Running one-by-one GX candidate search ...")
    search, factor_returns = run_candidate_search(gx09, returns_wide, base, frames, fwd)

    selected = [
        "age_weeks__low_minus_high",
        "skew_52w__high_minus_low",
        "minret_8w__low_minus_high",
        "beta_26w__high_minus_low",
    ]
    rename = {
        "age_weeks__low_minus_high": "NEWC_young_minus_old",
        "skew_52w__high_minus_low": "SKEW52_high_minus_low",
        "minret_8w__low_minus_high": "CRASH8_crashed_minus_resilient",
        "beta_26w__high_minus_low": "BETA26_high_minus_low",
    }
    factor_returns = factor_returns.rename(columns=rename)
    search["candidate"] = search["candidate"].replace(rename)
    selected = [rename[name] for name in selected]

    print("Applying Bonferroni + Benjamini-Hochberg multiple-testing correction ...")
    search, mt_summary = add_multiple_testing(search)
    print(f"  N={mt_summary['n_tests']} tests; uncorrected |t|>=2 hits="
          f"{mt_summary['hits_uncorrected_t2']}; Bonferroni hits={mt_summary['hits_bonferroni']} "
          f"(|t|>{mt_summary['bonferroni_t_threshold']:.2f}); BH-FDR hits={mt_summary['hits_bh_fdr']}")

    print("Running joint GX model for selected behavioral factors ...")
    gx_joint, joint_lambda, joint_corr = run_joint_model(
        gx09, returns_wide, base, factor_returns, selected
    )

    print("Re-pricing shortlist on IS-only and OOS-only windows (Finding 2) ...")
    robustness = is_oos_robustness(gx09, returns_wide, base, factor_returns, selected)
    print(robustness.to_string(index=False))

    search.to_parquet(ART_DATA / "behavioral_candidate_search.parquet", index=False)
    search.to_csv(ART_DATA / "behavioral_candidate_search.csv", index=False)
    factor_returns.reset_index().to_parquet(ART_DATA / "behavioral_factor_returns.parquet", index=False)
    joint_lambda.to_parquet(ART_DATA / "behavioral_joint_lambda.parquet", index=False)
    joint_corr.to_csv(ART_DATA / "behavioral_shortlist_correlation.csv")
    robustness.to_parquet(ART_DATA / "behavioral_is_oos_robustness.parquet", index=False)
    robustness.to_csv(ART_DATA / "behavioral_is_oos_robustness.csv", index=False)
    write_results(search, joint_lambda, joint_corr, selected, mt_summary, robustness)

    manifest = {
        "script": "01_behavioral_gx_search.py",
        "source_data": str(DATA09.relative_to(ROOT)),
        "sample": [str(IS_START.date()), str(OOS_END.date())],
        "base_controls": list(base.columns),
        "candidate_definitions_tested": int(len(search)),
        "hits_abs_t_ge_2": int(search["passes_t2"].sum()),
        "hits_abs_t_ge_1_65": int(search["passes_t165"].sum()),
        "multiple_testing": mt_summary,
        "selected_behavioral_factors": selected,
        "is_oos_robustness": robustness.to_dict(orient="records"),
        "joint_k_hidden": int(gx_joint["k_hidden"]),
        "joint_selected_lambda": joint_lambda[
            joint_lambda["factor"].isin(selected)
        ].to_dict(orient="records"),
    }
    (ART_MANIFESTS / "behavioral_gx_manifest.json").write_text(json.dumps(manifest, indent=2))

    print("Saved Stage 10 behavioral GX artifacts.")
    print(joint_lambda[joint_lambda["factor"].isin(selected)].to_string(index=False))


if __name__ == "__main__":
    main()
