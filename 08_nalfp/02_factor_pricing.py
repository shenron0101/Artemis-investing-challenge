"""02 — Crypto Factor Zoo + Giglio-Xiu (2021) hidden-factor pricing.

Replaces the v1 IPCA layer. The signal that feeds Pillar 3 is now
β_i' λ where β stacks loadings on (a) nine economically-named factor
portfolios and (b) K_hidden latent factors selected by the Bai-Ng (2002)
IC_p2 criterion. The estimator is the three-pass procedure of Giglio &
Xiu (Journal of Political Economy 2021), adapted to a weekly crypto panel.

Factor zoo (sources documented in `_common.FACTOR_RECIPES`):
  RC      crypto market (value-weighted)                         Hartmann 2025
  SMBC    small-minus-big (size)                                 Hartmann 2025; FF 1993
  MomC    momentum                                               Liu-Tsyvinski 2022
  VolC    low-volatility                                         Frazzini-Pedersen 2014
  TVLC    TVL/mcap                                               Hartmann 2025
  FunC    fundamental yield                                      RAAM v2
  SupC    supply absorption                                      RAAM v2
  NetMom  within-cluster momentum (cluster-neutral)              Liu-Tsyvinski 2018
  NetRel  cross-cluster relative strength                        Liu-Tsyvinski 2018

The script writes:
  factor_zoo_returns.parquet  — weekly returns of the nine observed factors
  factor_zoo_stats.parquet    — per-factor descriptive stats incl. IC + Newey-West t
  factor_correlations.parquet — 9×9 (+ hidden) correlation matrix
  gx_hidden_factors.parquet   — F^hidden_t time series
  gx_bai_ng.parquet           — IC_p2 score vs K
  gx_betas.parquet            — per-asset β on observed + hidden
  gx_lambda.parquet           — Fama-MacBeth λ̂ + SE + t-stat + 95% CI
  gx_expected_returns.parquet — walk-forward E[r_{i,t+1}]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    BAI_NG_K_MAX,
    DATA_DIR,
    FACTOR_RECIPES,
    MANIFEST_DIR,
    TRAIN_WEEKS,
    UPSTREAM_06,
    load_characteristics,
    save_plotly,
    write_frame,
    write_json,
)

REFIT_FREQ = 4  # weeks
MIN_FACTOR_WEEKS = 30  # drop a factor from the GX panel if it has < this many observations


# ---------------------------------------------------------------------------
# Factor zoo construction
# ---------------------------------------------------------------------------

def _build_panel() -> pd.DataFrame:
    """Stage-06 characteristics + Pillar-1 network signals, properly aligned."""
    char = load_characteristics()
    net = pd.read_parquet(DATA_DIR / "network_panel.parquet")
    net["week"] = pd.to_datetime(net["week"])
    keep = ["week", "symbol", "cluster_id", "within_cluster_mom",
            "cross_cluster_rel", "network_entropy"]
    df = char.merge(net[keep], on=["week", "symbol"], how="left")
    return df


def _market_factor(df: pd.DataFrame) -> pd.Series:
    """RC — value-weighted (lagged-mcap-weighted) weekly return of the universe."""
    out = df.dropna(subset=["fwd_ret_1w", "market_cap_usd"]).copy() if "market_cap_usd" in df else df.dropna(subset=["fwd_ret_1w"]).copy()
    if "market_cap_usd" not in out.columns:
        # fall back: use ret_1w cross-sectional mean (equal-weight). Lagged mcap
        # is on the stage-06 panel, not the stage-06 characteristics frame —
        # so we re-load it.
        panel = pd.read_parquet(UPSTREAM_06 / "panel.parquet")[["week", "symbol", "market_cap_usd"]].copy()
        panel["week"] = pd.to_datetime(panel["week"])
        panel["symbol"] = panel["symbol"].astype(str).str.upper()
        # shift one week so weights are lagged
        panel = panel.sort_values(["symbol", "week"])
        panel["lag_mcap"] = panel.groupby("symbol")["market_cap_usd"].shift(1)
        out = df.merge(panel[["week", "symbol", "lag_mcap"]], on=["week", "symbol"], how="left")
        out = out.dropna(subset=["fwd_ret_1w", "lag_mcap"])
        w = out.groupby("week").apply(
            lambda block: float((block["lag_mcap"] * block["fwd_ret_1w"]).sum() / max(block["lag_mcap"].sum(), 1e-12))
        )
        return w.rename("RC")
    w = out.groupby("week").apply(
        lambda block: float((block["market_cap_usd"] * block["fwd_ret_1w"]).sum() / max(block["market_cap_usd"].sum(), 1e-12))
    )
    return w.rename("RC")


def _sort_factor(df: pd.DataFrame, recipe: dict, name: str) -> pd.Series:
    """Standard long-short tercile factor on `sort_col`. Equal-weighted within each leg."""
    col = recipe["sort_col"]
    direction = recipe["direction"]
    frac = recipe["frac"]
    keep = df.dropna(subset=["fwd_ret_1w", col]).copy()

    def _one_week(block: pd.DataFrame) -> float:
        if len(block) < 10:
            return np.nan
        n = len(block)
        k = max(int(round(n * frac)), 3)
        ranks = block[col].rank(method="first")
        long_mask  = (ranks >  n - k) if direction == +1 else (ranks <=  k)
        short_mask = (ranks <=  k)    if direction == +1 else (ranks >  n - k)
        r_long = block.loc[long_mask, "fwd_ret_1w"].mean()
        r_short = block.loc[short_mask, "fwd_ret_1w"].mean()
        return float(r_long - r_short)

    return keep.groupby("week").apply(_one_week).rename(name)


def _cluster_neutral_sort(df: pd.DataFrame, recipe: dict, name: str) -> pd.Series:
    """Within each cluster: top half by `sort_col` long, bottom half short. Average
    over clusters to give a single weekly factor return that is cluster-neutral
    by construction. Liu-Tsyvinski 2018 §4 'community-based momentum'."""
    col = recipe["sort_col"]
    direction = recipe["direction"]
    keep = df.dropna(subset=["fwd_ret_1w", col, "cluster_id"]).copy()

    def _one_week(block: pd.DataFrame) -> float:
        per_cluster = []
        for _, grp in block.groupby("cluster_id"):
            if len(grp) < 4:
                continue
            n = len(grp)
            half = n // 2
            ranks = grp[col].rank(method="first")
            long_mask  = (ranks >  n - half) if direction == +1 else (ranks <=  half)
            short_mask = (ranks <=  half)    if direction == +1 else (ranks >  n - half)
            r_long = grp.loc[long_mask, "fwd_ret_1w"].mean()
            r_short = grp.loc[short_mask, "fwd_ret_1w"].mean()
            per_cluster.append(r_long - r_short)
        return float(np.mean(per_cluster)) if per_cluster else np.nan

    return keep.groupby("week").apply(_one_week).rename(name)


def build_factor_zoo(df: pd.DataFrame) -> pd.DataFrame:
    series: dict[str, pd.Series] = {}
    for name, recipe in FACTOR_RECIPES.items():
        if recipe["kind"] == "market":
            series[name] = _market_factor(df)
        elif recipe["kind"] == "sort":
            series[name] = _sort_factor(df, recipe, name)
        elif recipe["kind"] == "cluster_neutral_sort":
            series[name] = _cluster_neutral_sort(df, recipe, name)
        else:
            raise ValueError(f"unknown factor kind: {recipe['kind']}")
    zoo = pd.concat(series.values(), axis=1)
    zoo.index = pd.to_datetime(zoo.index)
    zoo = zoo.dropna(how="all")
    return zoo


# ---------------------------------------------------------------------------
# Per-factor stats
# ---------------------------------------------------------------------------

def _newey_west_se(r: np.ndarray, lags: int = 4) -> float:
    """Newey-West heteroskedasticity- and autocorrelation-robust SE for mean(r)."""
    n = len(r)
    if n < 2:
        return np.nan
    e = r - r.mean()
    gamma0 = (e * e).mean()
    s = gamma0
    for lag in range(1, min(lags, n - 1) + 1):
        cov = (e[lag:] * e[:-lag]).mean()
        s += 2.0 * (1.0 - lag / (lags + 1)) * cov
    return float(np.sqrt(max(s, 0.0) / n))


def _ar1(r: pd.Series) -> float:
    if len(r) < 2:
        return np.nan
    return float(r.autocorr(lag=1))


def _max_drawdown(r: pd.Series) -> float:
    cum = (1.0 + r).cumprod()
    peak = cum.cummax()
    dd = cum / peak - 1.0
    return float(dd.min())


def _ic_for_recipe(df: pd.DataFrame, recipe: dict) -> float:
    """Spearman IC of the underlying characteristic against forward return."""
    if recipe["kind"] == "market":
        return np.nan
    col = recipe["sort_col"]
    sign = recipe["direction"]
    sub = df.dropna(subset=[col, "fwd_ret_1w"])

    def _ic(block: pd.DataFrame) -> float:
        if len(block) < 6:
            return np.nan
        return block[col].rank().corr(block["fwd_ret_1w"].rank())

    ic_series = sub.groupby("week").apply(_ic)
    return float(sign * ic_series.mean())


def _ic_timeseries_for_recipe(df: pd.DataFrame, recipe: dict) -> pd.Series:
    """Per-week Spearman IC of the underlying characteristic vs forward return.

    Returns a Series indexed by week. Direction-signed so positive IC means
    the characteristic predicts returns in the intended direction."""
    if recipe["kind"] == "market":
        return pd.Series(dtype=float)
    col = recipe["sort_col"]
    sign = recipe["direction"]
    sub = df.dropna(subset=[col, "fwd_ret_1w"])

    def _ic(block: pd.DataFrame) -> float:
        if len(block) < 6:
            return np.nan
        return block[col].rank().corr(block["fwd_ret_1w"].rank())

    ic_series = sub.groupby("week").apply(_ic)
    return (sign * ic_series).rename(col)


def build_factor_ic_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """Long (week, factor, ic) frame of per-week signed IC for every sort factor."""
    rows: list[dict] = []
    for name, recipe in FACTOR_RECIPES.items():
        if recipe["kind"] == "market":
            continue
        ic_series = _ic_timeseries_for_recipe(df, recipe)
        for week, ic_val in ic_series.items():
            rows.append({"week": pd.Timestamp(week), "factor": name, "ic": ic_val})
    return pd.DataFrame(rows)


def factor_stats(zoo: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in zoo.columns:
        r = zoo[name].dropna()
        if r.empty:
            continue
        mean_ann = r.mean() * 52
        vol_ann = r.std(ddof=1) * np.sqrt(52)
        sharpe = mean_ann / vol_ann if vol_ann > 0 else np.nan
        nw_se_weekly = _newey_west_se(r.values, lags=4)
        nw_tstat = (r.mean() / nw_se_weekly) if (nw_se_weekly and nw_se_weekly > 0) else np.nan
        ar1 = _ar1(r)
        mdd = _max_drawdown(r)
        ic = _ic_for_recipe(df, FACTOR_RECIPES[name])
        rows.append({
            "factor": name,
            "paper": FACTOR_RECIPES[name].get("paper", ""),
            "n": len(r),
            "ann_mean": mean_ann,
            "ann_vol": vol_ann,
            "sharpe": sharpe,
            "nw_tstat": nw_tstat,
            "ar1": ar1,
            "max_dd": mdd,
            "ic_char_vs_fwd": ic,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Giglio-Xiu three-pass
# ---------------------------------------------------------------------------

def _ts_betas(returns_wide: pd.DataFrame, factors: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """OLS time-series regression for each asset on the factor matrix.

    Returns (betas DataFrame indexed by symbol, residual DataFrame indexed by week × symbol).
    Intercepts are dropped after fitting (alpha is not used downstream)."""
    common = returns_wide.index.intersection(factors.index)
    R = returns_wide.loc[common]
    F = factors.loc[common]
    F_mat = F.values
    X = np.hstack([np.ones((F_mat.shape[0], 1)), F_mat])  # add intercept
    betas: dict[str, np.ndarray] = {}
    resid: dict[str, pd.Series] = {}
    XtX_inv = None
    for sym in R.columns:
        y = R[sym].values
        mask = ~np.isnan(y)
        if mask.sum() < max(F_mat.shape[1] + 2, 8):
            continue
        Xs = X[mask]
        ys = y[mask]
        coef, *_ = np.linalg.lstsq(Xs, ys, rcond=None)
        # drop intercept
        betas[sym] = coef[1:]
        eps = ys - Xs @ coef
        resid[sym] = pd.Series(eps, index=R.index[mask])
    if not betas:
        return pd.DataFrame(), pd.DataFrame()
    beta_df = pd.DataFrame(betas, index=F.columns).T  # symbols × factors
    beta_df.index.name = "symbol"
    # residual wide frame
    res_wide = pd.DataFrame(index=R.index, columns=list(resid.keys()), dtype=float)
    for sym, s in resid.items():
        res_wide.loc[s.index, sym] = s.values
    return beta_df, res_wide


def _bai_ng_ic2(residuals: pd.DataFrame, k_max: int) -> tuple[int, pd.DataFrame]:
    """Bai-Ng (2002) IC_p2 selection of number of latent factors."""
    R = residuals.fillna(0.0).values  # T x N
    T, N = R.shape
    NT = N * T
    log_min_NT = np.log(min(N, T))
    # SVD once
    U, S, Vt = np.linalg.svd(R, full_matrices=False)
    rows = []
    chosen_k = 0
    best_ic = np.inf
    k_upper = min(k_max, len(S))
    for k in range(0, k_upper + 1):
        if k == 0:
            R_resid = R.copy()
        else:
            R_hat = U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :]
            R_resid = R - R_hat
        V_k = float((R_resid ** 2).sum() / NT)
        penalty = k * (N + T) / NT * log_min_NT
        ic = np.log(max(V_k, 1e-12)) + penalty
        rows.append({"k": k, "V_k": V_k, "penalty": penalty, "IC_p2": ic})
        if ic < best_ic:
            best_ic = ic
            chosen_k = k
    diag = pd.DataFrame(rows)
    return chosen_k, diag


def _pca_factors(residuals: pd.DataFrame, k: int) -> pd.DataFrame:
    """Return the top-k principal components of the residual matrix, scaled
    so each component has unit weekly standard deviation in the training
    window. T x k frame indexed by week."""
    if k == 0:
        return pd.DataFrame(index=residuals.index)
    R = residuals.fillna(0.0).values
    U, S, Vt = np.linalg.svd(R, full_matrices=False)
    F = U[:, :k] * S[:k]  # T x k principal-component time series
    # Rescale so each factor has unit weekly std (interpretability)
    sds = F.std(axis=0, ddof=1)
    sds[sds == 0] = 1.0
    F = F / sds
    cols = [f"H{i+1}" for i in range(k)]
    return pd.DataFrame(F, index=residuals.index, columns=cols)


def _fama_macbeth_lambda(betas: pd.DataFrame, returns_wide: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional regression of average returns on betas. iid SE.

    Returns DataFrame with columns [lambda, se, tstat, ci_lo, ci_hi]."""
    rbar = returns_wide.mean(axis=0)  # symbol -> mean weekly return
    common = betas.index.intersection(rbar.index)
    B = betas.loc[common].values
    y = rbar.loc[common].values
    K = B.shape[1]
    X = B  # no intercept — Giglio-Xiu specification
    lam, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ lam
    # heteroskedasticity-robust SE (White)
    XtX_inv = np.linalg.pinv(X.T @ X)
    meat = (X * (resid ** 2).reshape(-1, 1)).T @ X
    cov = XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(cov))
    rows = []
    factor_names = list(betas.columns)
    for k in range(K):
        rows.append({
            "factor": factor_names[k],
            "lambda": float(lam[k]),
            "se": float(se[k]),
            "tstat": float(lam[k] / se[k]) if se[k] > 0 else np.nan,
            "ci_lo": float(lam[k] - 1.96 * se[k]),
            "ci_hi": float(lam[k] + 1.96 * se[k]),
        })
    return pd.DataFrame(rows)


def giglio_xiu_fit(returns_wide: pd.DataFrame, F_obs: pd.DataFrame, k_max: int = BAI_NG_K_MAX):
    """Run the full three-pass GX procedure on a training window.

    Returns dict with keys: betas_obs_only, residuals, k_hidden, bai_ng_diag,
    hidden_factors, betas_full, lambda_obs_only, lambda_full."""
    # Pass 1
    beta_obs, residuals = _ts_betas(returns_wide, F_obs)

    # Bai-Ng on residuals
    k_hidden, diag = _bai_ng_ic2(residuals.fillna(0.0), k_max=k_max)

    # Pass 2
    F_hidden = _pca_factors(residuals.fillna(0.0), k_hidden)

    # Pass 3 — refit betas on combined factor set
    F_full = pd.concat([F_obs, F_hidden], axis=1) if k_hidden > 0 else F_obs.copy()
    beta_full, _ = _ts_betas(returns_wide, F_full)

    # Fama-MacBeth on observed-only and full models
    lam_obs = _fama_macbeth_lambda(beta_obs, returns_wide.loc[F_obs.index])
    lam_full = _fama_macbeth_lambda(beta_full, returns_wide.loc[F_full.index])

    return {
        "k_hidden": k_hidden,
        "bai_ng_diag": diag,
        "betas_obs_only": beta_obs,
        "residuals": residuals,
        "hidden_factors": F_hidden,
        "betas_full": beta_full,
        "lambda_obs_only": lam_obs,
        "lambda_full": lam_full,
    }


# ---------------------------------------------------------------------------
# Walk-forward expected returns
# ---------------------------------------------------------------------------

def returns_wide_from_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Wide T x N matrix of *contemporaneous* weekly returns aligned to weeks
    where the factor return is also defined (i.e. weeks where fwd_ret was
    available => r_{t} is well-defined for the same week)."""
    return df.pivot_table(index="week", columns="symbol", values="fwd_ret_1w", aggfunc="last").sort_index()


def walk_forward_expected_returns(zoo: pd.DataFrame, df: pd.DataFrame, k_max: int = BAI_NG_K_MAX):
    """Walk-forward fit. Returns:
      E_df         — long frame (week, symbol, E_gx, in_sample)
      gx_final     — full GX result dict from the final refit (for reporting)

    Factors with sparse coverage are dropped before fitting so the panel is
    rectangular. Remaining NaN cells (rare) are filled with the factor mean."""
    coverage = zoo.notna().sum()
    keep = coverage[coverage >= MIN_FACTOR_WEEKS].index.tolist()
    dropped = [c for c in zoo.columns if c not in keep]
    if dropped:
        print(f"  dropping low-coverage factors from GX: {dropped} "
              f"(coverage: {coverage[dropped].to_dict()})")
    zoo_full = zoo[keep].copy()
    # fill remaining gaps with column mean so the time-series regression has a balanced panel
    zoo_full = zoo_full.apply(lambda c: c.fillna(c.mean()))
    rw = returns_wide_from_panel(df)
    weeks = sorted(zoo_full.dropna(how="any").index.unique())
    if len(weeks) < TRAIN_WEEKS + 1:
        raise RuntimeError(f"Not enough factor-zoo weeks ({len(weeks)}) for TRAIN={TRAIN_WEEKS}")

    train_weeks = weeks[:TRAIN_WEEKS]
    out_rows: list[pd.DataFrame] = []

    def _fit(history_weeks):
        F_obs = zoo_full.loc[history_weeks].copy()
        rw_h = rw.loc[rw.index.intersection(history_weeks)].copy()
        return giglio_xiu_fit(rw_h, F_obs, k_max=k_max)

    print(f"initial GX fit on {len(train_weeks)} training weeks ...")
    gx = _fit(train_weeks)
    print(f"  K_hidden = {gx['k_hidden']}")
    betas = gx["betas_full"]
    lam = gx["lambda_full"].set_index("factor")["lambda"]
    # Predicted return per asset: β·λ
    pred = betas.dot(lam.reindex(betas.columns).fillna(0.0))
    # In-sample E for diagnostic: broadcast same prediction across train weeks
    for wk in train_weeks:
        out_rows.append(pd.DataFrame({
            "week": pd.Timestamp(wk),
            "symbol": pred.index,
            "E_gx": pred.values,
            "in_sample": True,
        }))

    history = list(train_weeks)
    gx_final = gx
    for i, wk in enumerate(weeks[TRAIN_WEEKS:]):
        if i > 0 and (i % REFIT_FREQ == 0):
            print(f"  refit at {pd.Timestamp(wk).date()} | history={len(history)} weeks")
            gx_final = _fit(history)
            betas = gx_final["betas_full"]
            lam = gx_final["lambda_full"].set_index("factor")["lambda"]
            pred = betas.dot(lam.reindex(betas.columns).fillna(0.0))
        out_rows.append(pd.DataFrame({
            "week": pd.Timestamp(wk),
            "symbol": pred.index,
            "E_gx": pred.values,
            "in_sample": False,
        }))
        history.append(wk)

    return pd.concat(out_rows, ignore_index=True), gx_final


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def _figures(zoo: pd.DataFrame, stats: pd.DataFrame, corr: pd.DataFrame,
             gx: dict, lam_obs: pd.DataFrame, lam_full: pd.DataFrame) -> None:
    import plotly.express as px
    import plotly.graph_objects as go

    fig = go.Figure()
    for c in zoo.columns:
        cum = (1.0 + zoo[c].fillna(0)).cumprod() - 1.0
        fig.add_trace(go.Scatter(x=zoo.index, y=cum, mode="lines", name=c))
    fig.update_layout(title="Crypto Factor Zoo — cumulative return", yaxis_title="cumulative return",
                      height=560)
    save_plotly(fig, "factor_zoo_cumulative", "02_factor_pricing")

    fig = px.imshow(corr.values, x=corr.columns, y=corr.index,
                    color_continuous_scale="RdBu_r",
                    color_continuous_midpoint=0,
                    aspect="auto", text_auto=".2f")
    fig.update_layout(title="Factor return correlation matrix", height=560)
    save_plotly(fig, "factor_correlation_heatmap", "02_factor_pricing")

    diag = gx["bai_ng_diag"]
    chosen = gx["k_hidden"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=diag["k"], y=diag["IC_p2"], mode="lines+markers", name="IC_p2"))
    fig.add_vline(x=chosen, line=dict(color="#d62728", dash="dash"))
    fig.update_layout(title=f"Bai-Ng IC_p2 selection (chosen K_hidden = {chosen})",
                      xaxis_title="K", yaxis_title="IC_p2", height=440)
    save_plotly(fig, "bai_ng_diagnostic", "02_factor_pricing")

    # lambda with CI bars
    def _lambda_fig(lam, title, name):
        fig = go.Figure()
        fig.add_trace(go.Bar(x=lam["factor"], y=lam["lambda"],
                              error_y=dict(type="data",
                                           array=lam["ci_hi"] - lam["lambda"],
                                           arrayminus=lam["lambda"] - lam["ci_lo"]),
                              name="λ̂"))
        fig.add_hline(y=0, line=dict(color="#888"))
        fig.update_layout(title=title, yaxis_title="weekly λ", height=480)
        save_plotly(fig, name, "02_factor_pricing")

    _lambda_fig(lam_obs, "Fama-MacBeth λ (observed factors only)", "lambda_obs_only")
    _lambda_fig(lam_full, "Fama-MacBeth λ (observed + hidden)", "lambda_full")

    # Hidden factor loadings heatmap
    if gx["k_hidden"] > 0:
        betas = gx["betas_full"]
        hidden_cols = [c for c in betas.columns if c.startswith("H")]
        if hidden_cols:
            sub = betas[hidden_cols]
            # show top/bottom 20 by first hidden loading
            order = sub.iloc[:, 0].abs().sort_values(ascending=False).head(40).index
            sub = sub.loc[order]
            fig = px.imshow(sub.values, x=sub.columns, y=sub.index,
                            color_continuous_scale="RdBu_r",
                            color_continuous_midpoint=0,
                            aspect="auto")
            fig.update_layout(title="Asset loadings on hidden factors (top-40 by |β_H1|)",
                              height=720)
            save_plotly(fig, "hidden_factor_loadings", "02_factor_pricing")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    print("loading panel + network ...")
    df = _build_panel()
    print(f"  rows: {len(df):,} | weeks: {df['week'].nunique()} | symbols: {df['symbol'].nunique()}")

    print("building factor zoo ...")
    zoo = build_factor_zoo(df)
    print("  factor counts:")
    print(zoo.notna().sum().to_string())

    stats = factor_stats(zoo, df)
    print("\nfactor stats (full sample):")
    print(stats.to_string(index=False, float_format=lambda x: f"{x: .4f}" if pd.notna(x) else "    nan"))

    corr = zoo.corr()
    write_frame(zoo.reset_index(), DATA_DIR / "factor_zoo_returns")
    write_frame(stats, DATA_DIR / "factor_zoo_stats")
    write_frame(corr.reset_index().rename(columns={"index": "factor"}), DATA_DIR / "factor_correlations")

    print("\nbuilding per-week IC timeseries for signal combination ...")
    ic_ts = build_factor_ic_timeseries(df)
    write_frame(ic_ts, DATA_DIR / "factor_ic_timeseries")

    print("\nrunning Giglio-Xiu walk-forward ...")
    E_df, gx_final = walk_forward_expected_returns(zoo, df)

    lam_obs = gx_final["lambda_obs_only"]
    lam_full = gx_final["lambda_full"]
    betas_full = gx_final["betas_full"]
    hidden = gx_final["hidden_factors"]

    write_frame(E_df, DATA_DIR / "gx_expected_returns")
    write_frame(betas_full.reset_index(), DATA_DIR / "gx_betas")
    write_frame(lam_full, DATA_DIR / "gx_lambda")
    write_frame(lam_obs, DATA_DIR / "gx_lambda_obs_only")
    if not hidden.empty:
        write_frame(hidden.reset_index().rename(columns={"index": "week"}), DATA_DIR / "gx_hidden_factors")
    write_frame(gx_final["bai_ng_diag"], DATA_DIR / "gx_bai_ng")

    # Compare observed-only vs full λ for the observed factors that survived
    # the coverage filter (TVLC / SupC are dropped from GX but kept in the
    # full factor-zoo stats for transparency).
    obs_factors = lam_obs["factor"].tolist()
    cmp = lam_obs.set_index("factor").loc[obs_factors][["lambda", "tstat"]].rename(
        columns={"lambda": "lam_obs_only", "tstat": "t_obs_only"})
    cmp = cmp.join(lam_full.set_index("factor").loc[obs_factors][["lambda", "tstat"]].rename(
        columns={"lambda": "lam_full", "tstat": "t_full"}), how="left")
    cmp["delta_lambda"] = cmp["lam_full"] - cmp["lam_obs_only"]
    cmp = cmp.reset_index()
    write_frame(cmp, DATA_DIR / "gx_lambda_obs_vs_full")

    manifest = {
        "n_obs_factors": len(zoo.columns),
        "obs_factors": list(zoo.columns),
        "k_hidden_chosen": int(gx_final["k_hidden"]),
        "bai_ng_k_max": BAI_NG_K_MAX,
        "train_weeks": TRAIN_WEEKS,
        "refit_freq_weeks": REFIT_FREQ,
        "factor_stats": stats.to_dict(orient="records"),
        "lambda_full": lam_full.to_dict(orient="records"),
        "lambda_obs_only": lam_obs.to_dict(orient="records"),
        "survived_observed_t_ge_1p65": lam_full.loc[
            (lam_full["factor"].isin(obs_factors)) & (lam_full["tstat"].abs() >= 1.65),
            "factor"
        ].tolist(),
    }
    write_json(manifest, MANIFEST_DIR / "02_factor_pricing_manifest.json")

    print("\nrendering figures ...")
    _figures(zoo, stats, corr, gx_final, lam_obs, lam_full)
    print("done.")


if __name__ == "__main__":
    main()
