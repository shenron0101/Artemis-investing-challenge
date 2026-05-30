"""09 — Giglio-Xiu (2021) three-pass factor pricing on the 5-year panel.

Runs the same GX methodology as 08_nalfp/02_factor_pricing.py, but on the
full 5-year backbone (T=184 IS weeks vs the prior T=24).  With T=184 the
Bai-Ng IC_p2 criterion can reliably select up to K_max=7 hidden factors
(following Hartmann 2025, who used 100+ weeks).

Factors tested (FunC / TVLC / SupC excluded — no 5yr fundamentals):
  RC      crypto market (value-weighted by reconstructed mcap)
  SMBC    small-minus-big (size)
  MomC    momentum (trailing 4-week return)
  VolC    low-volatility (trailing 4-week return std)
  NetMom  within-cluster momentum (cluster-neutral, Louvain)
  NetRel  cross-cluster relative strength

Two fits are reported:
  IS-only   2021-05-10 → 2024-11-11 (184 weeks) — main inference window
  Full      2021-05-10 → 2026-05-25 (264 weeks) — robustness check

Outputs
-------
  artifacts/data/gx5y_factor_zoo.parquet       — weekly factor returns (W x 6)
  artifacts/data/gx5y_lambda_is.parquet        — IS  λ̂ + t-stat (obs-only + full GX)
  artifacts/data/gx5y_lambda_full.parquet      — full-sample λ̂ + t-stat
  artifacts/data/gx5y_bai_ng_is.parquet        — Bai-Ng IC_p2 curve (IS fit)
  artifacts/manifests/09_gx_pricing_manifest.json
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.sparse import csr_matrix

STAGE = Path(__file__).resolve().parent
DATA_DIR = STAGE / "artifacts" / "data"
MAN_DIR  = STAGE / "artifacts" / "manifests"

NET_WINDOW   = 12   # rolling weeks for Spearman MST + Louvain
BAI_NG_K_MAX =  7   # viable with T=184 (Hartmann 2025 used same cap)
MIN_ASSET_OBS = 24  # drop asset from GX cross-section if fewer IS obs


# ---------------------------------------------------------------------------
# 1. Characteristics
# ---------------------------------------------------------------------------

def build_characteristics(panel: pd.DataFrame) -> pd.DataFrame:
    """From weekly (symbol, week, price, mcap) build the model characteristics."""
    px = panel.pivot(index="week", columns="symbol", values="price").sort_index()
    mc = panel.pivot(index="week", columns="symbol", values="mcap").sort_index()

    fwd  = px.pct_change().shift(-1)          # forward 1-week return
    mom4 = px.pct_change(4)                   # trailing 4-week return
    vol4 = px.pct_change().rolling(4).std()   # trailing 4-week return std
    logmc = np.log(mc.clip(lower=1))          # log market cap

    rows = []
    for df, nm in [(fwd, "fwd_ret_1w"), (mom4, "mom_4w"),
                   (vol4, "vol_4w"), (logmc, "log_mcap"), (mc, "mcap")]:
        m = df.stack(future_stack=True).reset_index()
        m.columns = ["week", "symbol", nm]
        rows.append(m)

    chars = rows[0]
    for m in rows[1:]:
        chars = chars.merge(m, on=["week", "symbol"], how="outer")
    chars["week"] = pd.to_datetime(chars["week"])
    return chars.sort_values(["week", "symbol"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. Network clustering → within_cluster_mom / cross_cluster_rel
# ---------------------------------------------------------------------------

def cluster_one_week(window: pd.DataFrame) -> pd.Series:
    """Spearman → Mantegna distance → MST → Louvain. Returns symbol→cluster_id."""
    corr = window.corr(method="spearman").clip(-0.9999, 0.9999)
    dist = np.sqrt(0.5 * (1 - corr.values))
    np.fill_diagonal(dist, 0)
    mst = minimum_spanning_tree(csr_matrix(dist)).toarray()
    g = nx.Graph()
    syms = list(window.columns)
    g.add_nodes_from(syms)
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            if mst[i, j] > 0 or mst[j, i] > 0:
                w = float(corr.iloc[i, j])
                g.add_edge(syms[i], syms[j], weight=max(w, 0.01))
    parts = nx.community.louvain_communities(g, weight="weight", seed=0)
    labels = {}
    for cl, members in enumerate(parts):
        for s in members:
            labels[s] = cl
    return pd.Series(labels)


def build_clusters(ret_wide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    weeks = list(ret_wide.index)
    for i in range(NET_WINDOW, len(weeks) + 1):
        w = weeks[i - 1]
        sub = ret_wide.iloc[i - NET_WINDOW:i].dropna(axis=1, thresh=NET_WINDOW // 2)
        if sub.shape[1] < 4:
            continue
        labels = cluster_one_week(sub)
        for sym, cl in labels.items():
            rows.append({"week": w, "symbol": sym, "cluster_id": int(cl)})
    return pd.DataFrame(rows)


def add_cluster_features(df: pd.DataFrame, clusters: pd.DataFrame) -> pd.DataFrame:
    out = df.merge(clusters, on=["week", "symbol"], how="left")
    # within_cluster_mom: coin's mom_4w minus leave-one-out cluster mean
    cms = out.groupby(["week", "cluster_id"])["mom_4w"].transform("sum")
    cmc = out.groupby(["week", "cluster_id"])["mom_4w"].transform("count")
    out["within_cluster_mom"] = (cms - out["mom_4w"].fillna(0)) / (
        cmc - out["mom_4w"].notna().astype(int)).replace(0, np.nan)
    # cross_cluster_rel: coin's mom_4w minus leave-one-out universe mean (excl own cluster)
    wms = out.groupby("week")["mom_4w"].transform("sum")
    wmc = out.groupby("week")["mom_4w"].transform("count")
    other = (wms - cms) / (wmc - cmc).replace(0, np.nan)
    out["cross_cluster_rel"] = out["mom_4w"] - other
    return out


# ---------------------------------------------------------------------------
# 3. Factor zoo construction
# ---------------------------------------------------------------------------

def market_factor(df: pd.DataFrame) -> pd.Series:
    """RC — value-weighted (lagged mcap) universe return."""
    sub = df.dropna(subset=["fwd_ret_1w", "mcap"]).copy()
    sub = sub.sort_values(["symbol", "week"])
    sub["lag_mcap"] = sub.groupby("symbol")["mcap"].shift(1)
    sub = sub.dropna(subset=["lag_mcap"])

    def _wt(block):
        tot = block["lag_mcap"].sum()
        if tot <= 0:
            return np.nan
        return float((block["lag_mcap"] * block["fwd_ret_1w"]).sum() / tot)

    return sub.groupby("week").apply(_wt).rename("RC")


def sort_factor(df: pd.DataFrame, col: str, direction: int,
                frac: float = 0.30) -> pd.Series:
    keep = df.dropna(subset=["fwd_ret_1w", col])

    def one(block):
        if len(block) < 10:
            return np.nan
        n = len(block)
        k = max(int(round(n * frac)), 3)
        ranks = block[col].rank(method="first")
        long_mask  = (ranks >  n - k) if direction == +1 else (ranks <=  k)
        short_mask = (ranks <=  k)    if direction == +1 else (ranks >  n - k)
        return float(block.loc[long_mask, "fwd_ret_1w"].mean() -
                     block.loc[short_mask, "fwd_ret_1w"].mean())

    return keep.groupby("week").apply(one)


def cluster_factor(df: pd.DataFrame, col: str, direction: int) -> pd.Series:
    keep = df.dropna(subset=["fwd_ret_1w", col, "cluster_id"])

    def one(block):
        per_cl = []
        for _, g in block.groupby("cluster_id"):
            if len(g) < 4:
                continue
            n = len(g)
            half = n // 2
            ranks = g[col].rank(method="first")
            lm = (ranks > n - half) if direction == +1 else (ranks <= half)
            sm = (ranks <= half)    if direction == +1 else (ranks > n - half)
            per_cl.append(g.loc[lm, "fwd_ret_1w"].mean() - g.loc[sm, "fwd_ret_1w"].mean())
        return float(np.mean(per_cl)) if per_cl else np.nan

    return keep.groupby("week").apply(one)


def build_zoo(df: pd.DataFrame) -> pd.DataFrame:
    zoo = {
        "RC":     market_factor(df),
        "SMBC":   sort_factor(df, "log_mcap",          -1, 0.30),
        "MomC":   sort_factor(df, "mom_4w",            +1, 0.30),
        "VolC":   sort_factor(df, "vol_4w",            -1, 0.30),
        "NetMom": cluster_factor(df, "within_cluster_mom", +1),
        "NetRel": sort_factor(df, "cross_cluster_rel", +1, 0.30),
    }
    out = pd.concat(zoo.values(), axis=1, keys=zoo.keys())
    out.index = pd.to_datetime(out.index)
    return out.sort_index()


# ---------------------------------------------------------------------------
# 4. Giglio-Xiu three-pass (ported from 08_nalfp/02_factor_pricing.py)
# ---------------------------------------------------------------------------

def ts_betas(returns_wide: pd.DataFrame,
             factors: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    common = returns_wide.index.intersection(factors.index)
    R = returns_wide.loc[common]
    F = factors.loc[common]
    Fmat = F.values
    X = np.hstack([np.ones((Fmat.shape[0], 1)), Fmat])
    betas, resid = {}, {}
    for sym in R.columns:
        y = R[sym].values
        mask = ~np.isnan(y)
        if mask.sum() < max(Fmat.shape[1] + 2, 8):
            continue
        coef, *_ = np.linalg.lstsq(X[mask], y[mask], rcond=None)
        betas[sym] = coef[1:]
        eps = y[mask] - X[mask] @ coef
        resid[sym] = pd.Series(eps, index=R.index[mask])
    if not betas:
        return pd.DataFrame(), pd.DataFrame()
    beta_df = pd.DataFrame(betas, index=F.columns).T
    beta_df.index.name = "symbol"
    res_wide = pd.DataFrame(index=R.index, columns=list(resid.keys()), dtype=float)
    for sym, s in resid.items():
        res_wide.loc[s.index, sym] = s.values
    return beta_df, res_wide


def bai_ng_ic2(residuals: pd.DataFrame, k_max: int) -> tuple[int, pd.DataFrame]:
    R = residuals.fillna(0.0).values
    T, N = R.shape
    NT = N * T
    log_min = np.log(min(N, T))
    U, S, Vt = np.linalg.svd(R, full_matrices=False)
    rows, chosen_k, best_ic = [], 0, np.inf
    for k in range(0, min(k_max, len(S)) + 1):
        if k == 0:
            Rr = R.copy()
        else:
            Rr = R - U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :]
        V_k = float((Rr ** 2).sum() / NT)
        pen  = k * (N + T) / NT * log_min
        ic   = np.log(max(V_k, 1e-12)) + pen
        rows.append({"k": k, "V_k": V_k, "penalty": pen, "IC_p2": ic})
        if ic < best_ic:
            best_ic = ic
            chosen_k = k
    return chosen_k, pd.DataFrame(rows)


def pca_factors(residuals: pd.DataFrame, k: int) -> pd.DataFrame:
    if k == 0:
        return pd.DataFrame(index=residuals.index)
    R = residuals.fillna(0.0).values
    U, S, Vt = np.linalg.svd(R, full_matrices=False)
    F = U[:, :k] * S[:k]
    sds = F.std(axis=0, ddof=1)
    sds[sds == 0] = 1.0
    return pd.DataFrame(F / sds, index=residuals.index,
                        columns=[f"H{i+1}" for i in range(k)])


def fama_macbeth_lambda(betas: pd.DataFrame,
                        returns_wide: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional OLS of mean returns on betas (White SE, no intercept — GX spec)."""
    rbar = returns_wide.mean(axis=0)
    common = betas.index.intersection(rbar.index)
    B = betas.loc[common].values
    y = rbar.loc[common].values
    lam, *_ = np.linalg.lstsq(B, y, rcond=None)
    resid = y - B @ lam
    XtX_inv = np.linalg.pinv(B.T @ B)
    meat = (B * (resid ** 2).reshape(-1, 1)).T @ B
    cov  = XtX_inv @ meat @ XtX_inv
    se   = np.sqrt(np.maximum(np.diag(cov), 0.0))
    return pd.DataFrame([{
        "factor": f,
        "lambda_wk":  float(lam[k]),
        "lambda_ann": float(lam[k] * 52),
        "se":         float(se[k]),
        "tstat":      float(lam[k] / se[k]) if se[k] > 0 else np.nan,
        "ci_lo":      float(lam[k] - 1.96 * se[k]),
        "ci_hi":      float(lam[k] + 1.96 * se[k]),
    } for k, f in enumerate(betas.columns)])


def giglio_xiu(returns_wide: pd.DataFrame, F_obs: pd.DataFrame,
               k_max: int = BAI_NG_K_MAX) -> dict:
    # drop assets with too few observations in this window
    ok = returns_wide.notna().sum()
    rw = returns_wide[ok[ok >= MIN_ASSET_OBS].index]

    beta_obs, resid = ts_betas(rw, F_obs)
    k_hidden, bai_ng = bai_ng_ic2(resid.fillna(0.0), k_max)
    F_hidden = pca_factors(resid.fillna(0.0), k_hidden)
    F_full   = pd.concat([F_obs, F_hidden], axis=1) if k_hidden > 0 else F_obs.copy()
    beta_full, _ = ts_betas(rw, F_full)

    lam_obs  = fama_macbeth_lambda(beta_obs,  rw.loc[F_obs.index])
    lam_full = fama_macbeth_lambda(beta_full, rw.loc[F_full.index])

    return {
        "k_hidden":  k_hidden,
        "bai_ng":    bai_ng,
        "lam_obs":   lam_obs,
        "lam_full":  lam_full,
        "beta_full": beta_full,
    }


# ---------------------------------------------------------------------------
# 5. Reporting helpers
# ---------------------------------------------------------------------------

def newey_west_tstat(r: np.ndarray, lags: int = 4) -> float:
    n = len(r)
    if n < 5:
        return np.nan
    e = r - r.mean()
    s = (e * e).mean()
    for lag in range(1, min(lags, n - 1) + 1):
        s += 2.0 * (1.0 - lag / (lags + 1)) * (e[lag:] * e[:-lag]).mean()
    se = np.sqrt(max(s, 0.0) / n)
    return float(r.mean() / se) if se > 0 else np.nan


def factor_descriptives(zoo: pd.DataFrame, lo, hi) -> pd.DataFrame:
    rows = []
    for f in zoo.columns:
        r = zoo[f].loc[lo:hi].dropna()
        if r.empty:
            continue
        ann_ret = r.mean() * 52
        ann_vol = r.std(ddof=1) * np.sqrt(52)
        rows.append({
            "factor": f,
            "n": len(r),
            "ann_ret": ann_ret,
            "ann_vol": ann_vol,
            "sharpe":  ann_ret / ann_vol if ann_vol > 0 else np.nan,
            "nw_tstat": newey_west_tstat(r.values),
        })
    return pd.DataFrame(rows)


def print_lambda_table(label: str, lam_obs: pd.DataFrame, lam_full: pd.DataFrame) -> None:
    obs = lam_obs.set_index("factor")[["lambda_ann", "tstat"]].rename(
        columns={"lambda_ann": "λ_obs_ann", "tstat": "t_obs"})
    full = lam_full[lam_full["factor"].isin(obs.index)].set_index("factor")[
        ["lambda_ann", "tstat"]].rename(
        columns={"lambda_ann": "λ_full_ann", "tstat": "t_full"})
    tbl = obs.join(full, how="left").reset_index()
    print(f"\n  ===== GX λ̂ — {label} =====")
    print(f"  {'Factor':<10} {'λ_obs (%/yr)':>13} {'t_obs':>8} "
          f"{'λ_full (%/yr)':>14} {'t_full':>8}")
    print("  " + "-" * 58)
    for _, r in tbl.iterrows():
        sig_obs  = "**" if abs(r.get("t_obs",  0) or 0) >= 1.65 else "  "
        sig_full = "**" if abs(r.get("t_full", 0) or 0) >= 1.65 else "  "
        print(f"  {r['factor']:<10} {r['λ_obs_ann']*100:>12.1f}% {sig_obs}{r['t_obs']:>+6.2f}  "
              f"{r['λ_full_ann']*100:>13.1f}% {sig_full}{r['t_full']:>+6.2f}")
    priced = tbl[tbl["t_full"].abs() >= 1.65]["factor"].tolist()
    print(f"  Priced at |t|≥1.65 in full GX: {priced}")


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main() -> None:
    man = json.loads((MAN_DIR / "universe_manifest.json").read_text())
    IS_START = pd.Timestamp(man["split"]["in_sample"][0])
    IS_END   = pd.Timestamp(man["split"]["in_sample"][1])
    OOS_END  = pd.Timestamp(man["split"]["out_of_sample"][1])

    print("loading price/mcap panel ...")
    panel = pd.read_parquet(DATA_DIR / "price_mcap_panel_weekly.parquet")
    panel["week"] = pd.to_datetime(panel["week"])

    print("building characteristics ...")
    chars = build_characteristics(panel)
    chars = chars[chars["week"] >= IS_START]

    print("building network clusters (rolling 12w Louvain) ...")
    ret_wide = (pd.read_parquet(DATA_DIR / "returns_weekly.parquet")
                .pivot(index="week", columns="symbol", values="ret")
                .sort_index())
    ret_wide.index = pd.to_datetime(ret_wide.index)
    clusters = build_clusters(ret_wide[ret_wide.index >= IS_START])
    chars = add_cluster_features(chars, clusters)

    print("building factor zoo ...")
    zoo = build_zoo(chars)
    zoo = zoo[zoo.index >= IS_START]
    print(f"  factor obs: {zoo.notna().sum().to_dict()}")

    # descriptive stats
    desc_is   = factor_descriptives(zoo, IS_START, IS_END)
    desc_full = factor_descriptives(zoo, IS_START, OOS_END)
    print("\n  factor descriptives (IS):")
    print(desc_is.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # --- GX on IS window ---
    zoo_is = zoo.loc[IS_START:IS_END].copy()
    zoo_is = zoo_is.apply(lambda c: c.fillna(c.mean()))

    ret_long = pd.read_parquet(DATA_DIR / "returns_weekly.parquet")
    ret_long["week"] = pd.to_datetime(ret_long["week"])
    rw = ret_long.pivot(index="week", columns="symbol", values="ret").sort_index()
    rw.index = pd.to_datetime(rw.index)
    rw_is = rw.loc[IS_START:IS_END]

    print(f"\nrunning GX on IS window ({IS_START.date()} → {IS_END.date()}, "
          f"{len(zoo_is)} weeks) ...")
    gx_is = giglio_xiu(rw_is, zoo_is, k_max=BAI_NG_K_MAX)
    print(f"  Bai-Ng selected K_hidden = {gx_is['k_hidden']}")
    print_lambda_table("IS only", gx_is["lam_obs"], gx_is["lam_full"])

    # --- GX on full window ---
    zoo_full = zoo.loc[IS_START:OOS_END].copy()
    zoo_full = zoo_full.apply(lambda c: c.fillna(c.mean()))
    rw_full  = rw.loc[IS_START:OOS_END]

    print(f"\nrunning GX on full window ({IS_START.date()} → {OOS_END.date()}, "
          f"{len(zoo_full)} weeks) ...")
    gx_full = giglio_xiu(rw_full, zoo_full, k_max=BAI_NG_K_MAX)
    print(f"  Bai-Ng selected K_hidden = {gx_full['k_hidden']}")
    print_lambda_table("Full sample", gx_full["lam_obs"], gx_full["lam_full"])

    # --- annotate with IS vs full comparison ---
    def _compare(lam_obs_is, lam_full_is, lam_obs_fl, lam_full_fl):
        obs_is  = lam_obs_is.set_index("factor")[["lambda_ann","tstat"]].rename(
            columns={"lambda_ann":"lo_is","tstat":"to_is"})
        full_is = lam_full_is[lam_full_is["factor"].isin(obs_is.index)].set_index("factor")[
            ["lambda_ann","tstat"]].rename(columns={"lambda_ann":"lf_is","tstat":"tf_is"})
        obs_fl  = lam_obs_fl.set_index("factor")[["lambda_ann","tstat"]].rename(
            columns={"lambda_ann":"lo_fl","tstat":"to_fl"})
        full_fl = lam_full_fl[lam_full_fl["factor"].isin(obs_is.index)].set_index("factor")[
            ["lambda_ann","tstat"]].rename(columns={"lambda_ann":"lf_fl","tstat":"tf_fl"})
        return obs_is.join([full_is, obs_fl, full_fl], how="left").reset_index()

    cmp = _compare(gx_is["lam_obs"], gx_is["lam_full"],
                   gx_full["lam_obs"], gx_full["lam_full"])

    # --- save outputs ---
    zoo.reset_index().to_parquet(DATA_DIR / "gx5y_factor_zoo.parquet", index=False)

    lam_is_out = gx_is["lam_full"].copy()
    lam_is_out["model"] = "IS"
    lam_obs_is = gx_is["lam_obs"].copy()
    lam_obs_is["model"] = "IS_obs_only"
    lam_is_all = pd.concat([lam_obs_is, lam_is_out], ignore_index=True)
    lam_is_all.to_parquet(DATA_DIR / "gx5y_lambda_is.parquet", index=False)

    lam_fl_out = gx_full["lam_full"].copy()
    lam_fl_out["model"] = "Full"
    lam_obs_fl = gx_full["lam_obs"].copy()
    lam_obs_fl["model"] = "Full_obs_only"
    lam_fl_all = pd.concat([lam_obs_fl, lam_fl_out], ignore_index=True)
    lam_fl_all.to_parquet(DATA_DIR / "gx5y_lambda_full.parquet", index=False)

    gx_is["bai_ng"].to_parquet(DATA_DIR / "gx5y_bai_ng_is.parquet", index=False)

    manifest = {
        "script": "09_gx_pricing.py",
        "is_window": [str(IS_START.date()), str(IS_END.date())],
        "is_weeks": int(len(zoo_is)),
        "full_weeks": int(len(zoo_full)),
        "factors_tested": list(zoo.columns),
        "bai_ng_k_max": BAI_NG_K_MAX,
        "k_hidden_is":   int(gx_is["k_hidden"]),
        "k_hidden_full": int(gx_full["k_hidden"]),
        "priced_is_full_gx_t165": gx_is["lam_full"][
            gx_is["lam_full"]["tstat"].abs() >= 1.65]["factor"].tolist(),
        "priced_full_full_gx_t165": gx_full["lam_full"][
            gx_full["lam_full"]["tstat"].abs() >= 1.65]["factor"].tolist(),
        "lambda_is_full_gx":   gx_is["lam_full"].to_dict(orient="records"),
        "lambda_full_full_gx": gx_full["lam_full"].to_dict(orient="records"),
    }
    (MAN_DIR / "09_gx_pricing_manifest.json").write_text(json.dumps(manifest, indent=2))
    print("\nsaved: gx5y_factor_zoo, gx5y_lambda_is, gx5y_lambda_full, "
          "gx5y_bai_ng_is, 09_gx_pricing_manifest.json")
    print("done.")


if __name__ == "__main__":
    main()
