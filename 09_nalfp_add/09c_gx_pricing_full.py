"""09c — Full 9-factor GX pricing on the 5-year panel.

Extends 09_gx_pricing.py with:
  FunC   fees / mcap (Artemis FEES, from 09b)
  TVLC   TVL  / mcap (Artemis CHAIN_TVL + DeFiLlama, from 09b)
  CCA1–3 macro-spanned crypto directions from CCA (fitted IS-only,
          applied walk-forward to avoid lookahead bias)

Full factor list (FunC/TVLC only where coverage ≥ 10 names/week):
  RC, SMBC, MomC, VolC, NetMom, NetRel, FunC, TVLC, CCA1, CCA2, CCA3

Two GX fits: IS (2021-05-10→2024-11-11) and Full (→2026-05-25).

Outputs
-------
  artifacts/data/gx5y_full_factor_zoo.parquet
  artifacts/data/gx5y_full_lambda_is.parquet
  artifacts/data/gx5y_full_lambda_full.parquet
  artifacts/manifests/09c_gx_full_manifest.json
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import minimum_spanning_tree
from sklearn.cross_decomposition import CCA

STAGE   = Path(__file__).resolve().parent
DATA    = STAGE / "artifacts" / "data"
MAN_DIR = STAGE / "artifacts" / "manifests"

NET_WINDOW    = 12
BAI_NG_K_MAX  =  7
MIN_ASSET_OBS = 24
MIN_NAMES_FACTOR = 10   # min per-week names to include a factor in GX


# ── characteristics ────────────────────────────────────────────────────────

def build_characteristics(panel: pd.DataFrame) -> pd.DataFrame:
    px = panel.pivot(index="week", columns="symbol", values="price").sort_index()
    mc = panel.pivot(index="week", columns="symbol", values="mcap").sort_index()
    fwd  = px.pct_change().shift(-1)
    mom4 = px.pct_change(4)
    vol4 = px.pct_change().rolling(4).std()
    logmc = np.log(mc.clip(lower=1))
    rows = []
    for df, nm in [(fwd,"fwd_ret_1w"),(mom4,"mom_4w"),(vol4,"vol_4w"),
                   (logmc,"log_mcap"),(mc,"mcap")]:
        m = df.stack(future_stack=True).reset_index()
        m.columns = ["week","symbol",nm]
        rows.append(m)
    chars = rows[0]
    for m in rows[1:]:
        chars = chars.merge(m, on=["week","symbol"], how="outer")
    chars["week"] = pd.to_datetime(chars["week"])
    return chars.sort_values(["week","symbol"]).reset_index(drop=True)


# ── network clustering ──────────────────────────────────────────────────────

def cluster_one_week(window: pd.DataFrame) -> pd.Series:
    corr = window.corr(method="spearman").clip(-0.9999, 0.9999)
    dist = np.sqrt(0.5 * (1 - corr.values))
    np.fill_diagonal(dist, 0)
    mst = minimum_spanning_tree(csr_matrix(dist)).toarray()
    g = nx.Graph()
    syms = list(window.columns)
    g.add_nodes_from(syms)
    for i in range(len(syms)):
        for j in range(i+1, len(syms)):
            if mst[i,j] > 0 or mst[j,i] > 0:
                g.add_edge(syms[i], syms[j], weight=max(float(corr.iloc[i,j]),0.01))
    parts = nx.community.louvain_communities(g, weight="weight", seed=0)
    return pd.Series({s: cl for cl, members in enumerate(parts) for s in members})


def build_clusters(ret_wide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    weeks = list(ret_wide.index)
    for i in range(NET_WINDOW, len(weeks)+1):
        w = weeks[i-1]
        sub = ret_wide.iloc[i-NET_WINDOW:i].dropna(axis=1, thresh=NET_WINDOW//2)
        if sub.shape[1] < 4:
            continue
        for sym, cl in cluster_one_week(sub).items():
            rows.append({"week": w, "symbol": sym, "cluster_id": int(cl)})
    return pd.DataFrame(rows)


def add_cluster_features(df: pd.DataFrame, clusters: pd.DataFrame) -> pd.DataFrame:
    out = df.merge(clusters, on=["week","symbol"], how="left")
    cms = out.groupby(["week","cluster_id"])["mom_4w"].transform("sum")
    cmc = out.groupby(["week","cluster_id"])["mom_4w"].transform("count")
    out["within_cluster_mom"] = (cms - out["mom_4w"].fillna(0)) / (
        cmc - out["mom_4w"].notna().astype(int)).replace(0, np.nan)
    wms = out.groupby("week")["mom_4w"].transform("sum")
    wmc = out.groupby("week")["mom_4w"].transform("count")
    out["cross_cluster_rel"] = out["mom_4w"] - (wms - cms) / (wmc - cmc).replace(0, np.nan)
    return out


# ── fundamental signals ─────────────────────────────────────────────────────

def add_fundamentals(chars: pd.DataFrame) -> pd.DataFrame:
    fund = pd.read_parquet(DATA / "fundamentals_weekly.parquet")
    fund["week"] = pd.to_datetime(fund["week"])
    return chars.merge(
        fund[["week","symbol","fees_to_mcap","tvl_to_mcap"]],
        on=["week","symbol"], how="left"
    )


# ── CCA canonical factors (IS-fitted, walk-forward) ────────────────────────

def build_cca_factors(ret_wide: pd.DataFrame, ref: pd.DataFrame,
                      backbone: list[str], is_start, is_end,
                      n_components: int = 3) -> pd.DataFrame:
    """Fit CCA on IS backbone vs macro; compute CC1-CC3 returns walk-forward.

    The IS-period means/stds are used for normalization in OOS to prevent
    lookahead bias. CC_t = zscore_IS(crypto_ret_t) @ x_weights.
    """
    crypto_cols = [c for c in backbone if c not in ref.columns]
    rw_is = ret_wide.loc[is_start:is_end, crypto_cols].dropna(axis=1, how="any")
    ref_is = ref.loc[is_start:is_end].dropna(axis=1, how="any")
    shared_weeks = rw_is.index.intersection(ref_is.index)
    rw_is = rw_is.loc[shared_weeks]
    ref_is = ref_is.loc[shared_weeks]

    # Standardize on IS window
    mu_x  = rw_is.mean()
    sd_x  = rw_is.std(ddof=0).replace(0, np.nan)
    mu_y  = ref_is.mean()
    sd_y  = ref_is.std(ddof=0).replace(0, np.nan)
    Xz_is = ((rw_is - mu_x) / sd_x).fillna(0)
    Yz_is = ((ref_is - mu_y) / sd_y).fillna(0)

    m = min(n_components, Xz_is.shape[1], Yz_is.shape[1])
    cca = CCA(n_components=m, max_iter=2000)
    cca.fit(Xz_is.values, Yz_is.values)
    rhos = [float(np.corrcoef(
        Xz_is.values @ cca.x_weights_[:,i],
        Yz_is.values @ cca.y_weights_[:,i])[0,1]) for i in range(m)]
    print(f"  CCA canonical correlations (IS): {[f'{r:.3f}' for r in rhos]}")

    # Walk-forward: apply IS weights to all weeks
    rw_all = ret_wide[crypto_cols].dropna(axis=1, how="any")
    common_cryptos = [c for c in crypto_cols if c in rw_all.columns]
    w = cca.x_weights_[[list(crypto_cols).index(c) for c in common_cryptos], :]

    rows = []
    for wk, row in rw_all[common_cryptos].iterrows():
        r = row.fillna(0).values
        sd = sd_x[common_cryptos].fillna(1).values
        mu = mu_x[common_cryptos].values
        zr = (r - mu) / sd
        cc = zr @ w
        for i in range(m):
            rows.append({"week": wk, "factor": f"CCA{i+1}", "value": float(cc[i])})

    cc_long = pd.DataFrame(rows)
    cc_wide = cc_long.pivot(index="week", columns="factor", values="value").sort_index()
    return cc_wide


# ── factor zoo construction ─────────────────────────────────────────────────

def market_factor(df: pd.DataFrame) -> pd.Series:
    sub = df.dropna(subset=["fwd_ret_1w","mcap"]).copy()
    sub = sub.sort_values(["symbol","week"])
    sub["lag_mcap"] = sub.groupby("symbol")["mcap"].shift(1)
    sub = sub.dropna(subset=["lag_mcap"])
    def _wt(block):
        t = block["lag_mcap"].sum()
        return float((block["lag_mcap"]*block["fwd_ret_1w"]).sum()/t) if t>0 else np.nan
    return sub.groupby("week").apply(_wt).rename("RC")


def sort_factor(df, col, direction, frac=0.30, min_names=MIN_NAMES_FACTOR):
    keep = df.dropna(subset=["fwd_ret_1w", col])
    def one(block):
        if len(block) < min_names:
            return np.nan
        n = len(block)
        k = max(int(round(n*frac)), 3)
        ranks = block[col].rank(method="first")
        lm = (ranks > n-k) if direction==+1 else (ranks <= k)
        sm = (ranks <= k) if direction==+1 else (ranks > n-k)
        return float(block.loc[lm,"fwd_ret_1w"].mean() - block.loc[sm,"fwd_ret_1w"].mean())
    return keep.groupby("week").apply(one)


def cluster_factor(df, col, direction, min_names=MIN_NAMES_FACTOR):
    keep = df.dropna(subset=["fwd_ret_1w", col, "cluster_id"])
    def one(block):
        per_cl = []
        for _, g in block.groupby("cluster_id"):
            if len(g) < 4: continue
            n = len(g); half = n//2
            ranks = g[col].rank(method="first")
            lm = (ranks > n-half) if direction==+1 else (ranks <= half)
            sm = (ranks <= half) if direction==+1 else (ranks > n-half)
            per_cl.append(g.loc[lm,"fwd_ret_1w"].mean() - g.loc[sm,"fwd_ret_1w"].mean())
        return float(np.mean(per_cl)) if per_cl else np.nan
    return keep.groupby("week").apply(one)


def load_spc_factors() -> pd.DataFrame:
    """Load rolling Sparse PCA factor returns from script 06."""
    df = pd.read_parquet(DATA / "sparse_pca_factor_returns.parquet")
    df.index = pd.to_datetime(df.index)
    return df[["SPC1", "SPC2", "SPC3", "SPC4"]]


def build_zoo(df: pd.DataFrame, cca_factors: pd.DataFrame,
              spc_factors: pd.DataFrame) -> pd.DataFrame:
    zoo = {
        "RC":     market_factor(df),
        "SMBC":   sort_factor(df,"log_mcap",          -1),
        "MomC":   sort_factor(df,"mom_4w",            +1),
        "VolC":   sort_factor(df,"vol_4w",            -1),
        "NetMom": cluster_factor(df,"within_cluster_mom",+1),
        "NetRel": sort_factor(df,"cross_cluster_rel", +1),
        "FunC":   sort_factor(df,"fees_to_mcap",      +1),
        "TVLC":   sort_factor(df,"tvl_to_mcap",       +1),
    }
    out = pd.concat(zoo.values(), axis=1, keys=zoo.keys())
    out.index = pd.to_datetime(out.index)
    if not spc_factors.empty:
        out = out.join(spc_factors, how="left")
    if not cca_factors.empty:
        out = out.join(cca_factors, how="left")
    return out.sort_index()


# ── Giglio-Xiu three-pass (same engine as 09_gx_pricing.py) ────────────────

def ts_betas(returns_wide, factors):
    common = returns_wide.index.intersection(factors.index)
    R, F = returns_wide.loc[common], factors.loc[common]
    X = np.hstack([np.ones((len(F),1)), F.values])
    betas, resid = {}, {}
    for sym in R.columns:
        y = R[sym].values; mask = ~np.isnan(y)
        if mask.sum() < max(F.shape[1]+2, 8): continue
        coef, *_ = np.linalg.lstsq(X[mask], y[mask], rcond=None)
        betas[sym] = coef[1:]
        resid[sym] = pd.Series(y[mask] - X[mask]@coef, index=R.index[mask])
    if not betas: return pd.DataFrame(), pd.DataFrame()
    beta_df = pd.DataFrame(betas, index=F.columns).T
    beta_df.index.name = "symbol"
    res_wide = pd.DataFrame(index=R.index, columns=list(resid), dtype=float)
    for s, sr in resid.items():
        res_wide.loc[sr.index, s] = sr.values
    return beta_df, res_wide


def bai_ng_ic2(residuals, k_max):
    R = residuals.fillna(0.).values; T,N = R.shape; NT = N*T
    log_min = np.log(min(N,T))
    U,S,Vt = np.linalg.svd(R, full_matrices=False)
    rows, chosen_k, best_ic = [], 0, np.inf
    for k in range(0, min(k_max,len(S))+1):
        Rr = R if k==0 else R - U[:,:k]@np.diag(S[:k])@Vt[:k,:]
        V_k = float((Rr**2).sum()/NT)
        pen = k*(N+T)/NT*log_min
        ic = np.log(max(V_k,1e-12))+pen
        rows.append({"k":k,"V_k":V_k,"penalty":pen,"IC_p2":ic})
        if ic < best_ic: best_ic=ic; chosen_k=k
    return chosen_k, pd.DataFrame(rows)


def pca_factors(residuals, k):
    if k==0: return pd.DataFrame(index=residuals.index)
    R = residuals.fillna(0.).values
    U,S,Vt = np.linalg.svd(R, full_matrices=False)
    F = U[:,:k]*S[:k]
    sds = F.std(axis=0,ddof=1); sds[sds==0]=1.
    return pd.DataFrame(F/sds, index=residuals.index,
                        columns=[f"H{i+1}" for i in range(k)])


def nw_se(r: np.ndarray, lags: int = 4) -> float:
    n = len(r)
    if n < 2: return np.nan
    e = r - r.mean()
    s = (e * e).mean()
    for lag in range(1, min(lags, n-1) + 1):
        s += 2.0 * (1 - lag / (lags + 1)) * (e[lag:] * e[:-lag]).mean()
    return float(np.sqrt(max(s, 0.0) / n))


def fama_macbeth(betas: pd.DataFrame, returns_wide: pd.DataFrame,
                 lags: int = 4) -> pd.DataFrame:
    """Proper Fama-MacBeth (1973): week-by-week cross-sectional OLS, then average.

    For each week t, regress realized returns r_{i,t} on pre-estimated betas β_i.
    λ̂ = mean(λ_t), t-stat uses Newey-West SE over the time series of λ_t."""
    common = betas.index.intersection(returns_wide.columns)
    B = betas.loc[common].values          # N × K
    factor_names = list(betas.columns)
    lam_t = []
    for wk in sorted(returns_wide.index):
        r = returns_wide.loc[wk, common].values
        mask = ~np.isnan(r)
        if mask.sum() < B.shape[1] + 2:
            continue
        lam_wk, *_ = np.linalg.lstsq(B[mask], r[mask], rcond=None)
        lam_t.append(lam_wk)
    if not lam_t:
        return pd.DataFrame()
    arr = np.array(lam_t)                 # T × K
    rows = []
    for k, fname in enumerate(factor_names):
        series = arr[:, k]
        se = nw_se(series, lags)
        mean = float(series.mean())
        rows.append({
            "factor":     fname,
            "lambda_wk":  mean,
            "lambda_ann": mean * 52,
            "se":         se,
            "tstat":      float(mean / se) if se and se > 0 else np.nan,
        })
    return pd.DataFrame(rows)


def fmb_lambda(betas, returns_wide):
    """Single-cross-section FMB on mean returns (used inside GX only)."""
    rbar = returns_wide.mean(axis=0)
    common = betas.index.intersection(rbar.index)
    B = betas.loc[common].values; y = rbar.loc[common].values
    lam, *_ = np.linalg.lstsq(B, y, rcond=None)
    resid = y - B@lam
    XtX_inv = np.linalg.pinv(B.T@B)
    cov = XtX_inv @ ((B*(resid**2).reshape(-1,1)).T@B) @ XtX_inv
    se = np.sqrt(np.maximum(np.diag(cov),0.))
    return pd.DataFrame([{
        "factor": f,
        "lambda_wk": float(lam[k]),
        "lambda_ann": float(lam[k]*52),
        "se": float(se[k]),
        "tstat": float(lam[k]/se[k]) if se[k]>0 else np.nan,
        "ci_lo": float(lam[k]-1.96*se[k]),
        "ci_hi": float(lam[k]+1.96*se[k]),
    } for k,f in enumerate(betas.columns)])


def giglio_xiu(returns_wide, F_obs, k_max=BAI_NG_K_MAX):
    ok = returns_wide.notna().sum()
    rw = returns_wide[ok[ok >= MIN_ASSET_OBS].index]
    beta_obs, resid = ts_betas(rw, F_obs)
    k_hidden, bai_ng = bai_ng_ic2(resid.fillna(0.), k_max)
    F_hidden = pca_factors(resid.fillna(0.), k_hidden)
    F_full = pd.concat([F_obs, F_hidden],axis=1) if k_hidden>0 else F_obs.copy()
    beta_full, _ = ts_betas(rw, F_full)
    lam_obs  = fmb_lambda(beta_obs,  rw.loc[F_obs.index])
    lam_full = fmb_lambda(beta_full, rw.loc[F_full.index])
    # Proper FMB uses the observed-factor betas (same first pass), week-by-week
    lam_fmb  = fama_macbeth(beta_obs, rw.loc[F_obs.index])
    return {"k_hidden":k_hidden,"bai_ng":bai_ng,
            "lam_obs":lam_obs,"lam_full":lam_full,"lam_fmb":lam_fmb}


# ── helpers ─────────────────────────────────────────────────────────────────

def nw_tstat(r, lags=4):
    n = len(r)
    if n<5: return np.nan
    e = r - r.mean(); s = (e*e).mean()
    for lag in range(1, min(lags,n-1)+1):
        s += 2.*(1-lag/(lags+1))*(e[lag:]*e[:-lag]).mean()
    se = np.sqrt(max(s,0.)/n)
    return float(r.mean()/se) if se>0 else np.nan


def print_lambda_table(label, lam_fmb, lam_obs, lam_full):
    fmb   = lam_fmb.set_index("factor")[["lambda_ann","tstat"]].rename(
        columns={"lambda_ann":"λ_fmb","tstat":"t_fmb"})
    obs   = lam_obs.set_index("factor")[["lambda_ann","tstat"]].rename(
        columns={"lambda_ann":"λ_obs","tstat":"t_obs"})
    full_ = lam_full[lam_full["factor"].isin(fmb.index)].set_index("factor")[
        ["lambda_ann","tstat"]].rename(columns={"lambda_ann":"λ_gx","tstat":"t_gx"})
    tbl = fmb.join(obs, how="left").join(full_, how="left").reset_index()
    print(f"\n  ===== {label} =====")
    print(f"  {'Factor':<10} {'FMB λ(%/yr)':>12} {'t_fmb':>7}  "
          f"{'GX-obs λ':>10} {'t_obs':>7}  {'GX-full λ':>10} {'t_gx':>7}")
    print("  " + "-" * 76)
    for _, r in tbl.iterrows():
        sf = "**" if abs(r.get("t_fmb",0) or 0)>=1.65 else "  "
        so = "**" if abs(r.get("t_obs",0) or 0)>=1.65 else "  "
        sg = "**" if abs(r.get("t_gx", 0) or 0)>=1.65 else "  "
        print(f"  {r['factor']:<10} {r['λ_fmb']*100:>11.1f}%{sf}{r['t_fmb']:>+7.2f}  "
              f"{r['λ_obs']*100:>9.1f}%{so}{r['t_obs']:>+7.2f}  "
              f"{r['λ_gx']*100:>9.1f}%{sg}{r['t_gx']:>+7.2f}")
    fmb_priced = tbl[tbl["t_fmb"].abs()>=1.65]["factor"].tolist()
    gx_priced  = tbl[tbl["t_gx"].abs()>=1.65]["factor"].tolist()
    print(f"  FMB priced (|t|≥1.65): {fmb_priced}")
    print(f"  GX  priced (|t|≥1.65): {gx_priced}")


# ── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    man      = json.loads((MAN_DIR/"universe_manifest.json").read_text())
    IS_START = pd.Timestamp(man["split"]["in_sample"][0])
    IS_END   = pd.Timestamp(man["split"]["in_sample"][1])
    OOS_END  = pd.Timestamp(man["split"]["out_of_sample"][1])
    backbone = man["estimation_backbone"]["symbols"]

    print("Loading panel ...")
    panel = pd.read_parquet(DATA/"price_mcap_panel_weekly.parquet")
    panel["week"] = pd.to_datetime(panel["week"])

    print("Building characteristics ...")
    chars = build_characteristics(panel)
    chars = chars[chars["week"] >= IS_START]

    print("Adding fundamentals (FunC / TVLC) ...")
    chars = add_fundamentals(chars)
    fc_cov = chars.dropna(subset=["fees_to_mcap"]).groupby("week")["symbol"].count()
    tv_cov = chars.dropna(subset=["tvl_to_mcap"]).groupby("week")["symbol"].count()
    print(f"  FunC coverage: median {fc_cov.median():.0f} names/week, min {fc_cov.min():.0f}")
    print(f"  TVLC coverage: median {tv_cov.median():.0f} names/week, min {tv_cov.min():.0f}")

    print("Building network clusters ...")
    ret_long = pd.read_parquet(DATA/"returns_weekly.parquet")
    ret_long["week"] = pd.to_datetime(ret_long["week"])
    ret_wide = ret_long.pivot(index="week",columns="symbol",values="ret").sort_index()
    ret_wide.index = pd.to_datetime(ret_wide.index)
    clusters = build_clusters(ret_wide[ret_wide.index >= IS_START])
    chars = add_cluster_features(chars, clusters)

    print("Building CCA canonical factors ...")
    ref = pd.read_parquet(DATA/"reference_weekly.parquet")
    ref.index = pd.to_datetime(ref.index)
    cca_factors = build_cca_factors(ret_wide, ref, backbone, IS_START, IS_END)
    print(f"  CCA factors: {list(cca_factors.columns)}, weeks: {len(cca_factors)}")

    print("Loading Sparse PCA factors (script 06) ...")
    spc_factors = load_spc_factors()
    print(f"  SPC factors: {list(spc_factors.columns)}, weeks: {len(spc_factors)}")

    print("Building factor zoo ...")
    zoo = build_zoo(chars, cca_factors, spc_factors)
    zoo = zoo[zoo.index >= IS_START]
    obs_counts = zoo.notna().sum()
    print("  Obs per factor:")
    print(obs_counts.to_string())

    # ---- GX on IS window ----
    zoo_is = zoo.loc[IS_START:IS_END].copy()
    # Drop factors with sparse IS coverage
    min_obs = 30
    drop_is = obs_counts[obs_counts < min_obs].index.tolist()
    zoo_is_fit = zoo_is.drop(columns=[c for c in drop_is if c in zoo_is.columns], errors="ignore")
    zoo_is_fit = zoo_is_fit.apply(lambda c: c.fillna(c.mean()))
    rw_is = ret_wide.loc[IS_START:IS_END]

    print(f"\nGX IS ({IS_START.date()}→{IS_END.date()}, {len(zoo_is_fit)} weeks) "
          f"factors: {list(zoo_is_fit.columns)} ...")
    gx_is = giglio_xiu(rw_is, zoo_is_fit)
    print(f"  K_hidden = {gx_is['k_hidden']}")
    print_lambda_table("IS — FMB vs GX", gx_is["lam_fmb"], gx_is["lam_obs"], gx_is["lam_full"])

    # ---- GX on full window ----
    zoo_full = zoo.loc[IS_START:OOS_END].copy()
    zoo_full_fit = zoo_full.apply(lambda c: c.fillna(c.mean()))
    rw_full = ret_wide.loc[IS_START:OOS_END]

    print(f"\nGX Full ({IS_START.date()}→{OOS_END.date()}, {len(zoo_full_fit)} weeks) "
          f"factors: {list(zoo_full_fit.columns)} ...")
    gx_full = giglio_xiu(rw_full, zoo_full_fit)
    print(f"  K_hidden = {gx_full['k_hidden']}")
    print_lambda_table("Full — FMB vs GX", gx_full["lam_fmb"], gx_full["lam_obs"], gx_full["lam_full"])

    # ---- Save ----
    zoo.reset_index().to_parquet(DATA/"gx5y_full_factor_zoo.parquet", index=False)

    for label, gx in [("is", gx_is), ("full", gx_full)]:
        fmb_  = gx["lam_fmb"].copy();  fmb_["model"]  = f"{label}_fmb"
        obs_  = gx["lam_obs"].copy();   obs_["model"]  = f"{label}_gx_obs"
        full_ = gx["lam_full"].copy(); full_["model"]  = f"{label}_gx_full"
        pd.concat([fmb_, obs_, full_], ignore_index=True).to_parquet(
            DATA/f"gx5y_full_lambda_{label}.parquet", index=False)

    manifest = {
        "script": "09c_gx_pricing_full.py",
        "factors_is":   list(zoo_is_fit.columns),
        "factors_full": list(zoo_full_fit.columns),
        "k_hidden_is":  int(gx_is["k_hidden"]),
        "k_hidden_full":int(gx_full["k_hidden"]),
        "priced_is_t165":   gx_is["lam_full"][gx_is["lam_full"]["tstat"].abs()>=1.65]["factor"].tolist(),
        "priced_full_t165": gx_full["lam_full"][gx_full["lam_full"]["tstat"].abs()>=1.65]["factor"].tolist(),
        "lambda_is_full_gx":   gx_is["lam_full"].to_dict(orient="records"),
        "lambda_full_full_gx": gx_full["lam_full"].to_dict(orient="records"),
    }
    (MAN_DIR/"09c_gx_full_manifest.json").write_text(json.dumps(manifest, indent=2))
    print("\nSaved: gx5y_full_factor_zoo, gx5y_full_lambda_is/full, 09c_gx_full_manifest.json")
    print("done.")


if __name__ == "__main__":
    main()
