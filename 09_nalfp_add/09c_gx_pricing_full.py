"""09c — Full GX pricing on the 5-year panel.

Extends 09_gx_pricing.py with:
  FunC    fees / mcap (Artemis FEES, from 09b)
  TVLC    TVL  / mcap (Artemis CHAIN_TVL + DeFiLlama, from 09b)
  CCA1–3  macro-spanned crypto directions from CCA (IS-fitted, walk-forward)
  RMOM1w  1-week risk-adjusted momentum (Han et al. 2023)
  RMOM2w  2-week risk-adjusted momentum (Han et al. 2023)
  RMOM4w  4-week Sharpe ratio           (Han et al. 2023)
  MAXRET  max weekly return trailing 4w (Han et al. 2023, proxy)

Full factor list:
  RC, SMBC, MomC, VolC, NetMom, NetRel, FunC, TVLC,
  RMOM1w, RMOM2w, RMOM4w, MAXRET,
  SPC1–4, CCA1–3

Two GX fits: IS (2021-05-10→2024-11-11) and Full (→2026-05-25).

Also rewrites RESULTS.md Part 2 from the computed results (reads Part 1's
factor_validation_stats.parquet) so both parts share a unified master table
and a coherent narrative.

Outputs
-------
  artifacts/data/gx5y_full_factor_zoo.parquet
  artifacts/data/gx5y_full_lambda_is.parquet
  artifacts/data/gx5y_full_lambda_full.parquet
  artifacts/manifests/09c_gx_full_manifest.json
  09_nalfp_add/RESULTS.md  (Part 2 + master table, preserves Part 1)
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
    px    = panel.pivot(index="week", columns="symbol", values="price").sort_index()
    mc    = panel.pivot(index="week", columns="symbol", values="mcap").sort_index()
    ret   = px.pct_change()
    fwd   = ret.shift(-1)
    mom4  = px.pct_change(4)
    mom2  = px.pct_change(2)
    vol4  = ret.rolling(4).std()
    logmc = np.log(mc.clip(lower=1))

    # Han et al. (2023) risk-adjusted momentum and max-return characteristics
    rmom_4w = ret.rolling(4).mean() / vol4.replace(0, np.nan)   # 4-week Sharpe
    rmom_1w = ret / vol4.replace(0, np.nan)                      # 1-week ret / 4w vol
    rmom_2w = mom2 / vol4.replace(0, np.nan)                     # 2-week ret / 4w vol
    maxret  = ret.rolling(4).max()                               # max weekly ret, 4w trailing

    rows = []
    for df, nm in [
        (fwd,     "fwd_ret_1w"),
        (mom4,    "mom_4w"),
        (vol4,    "vol_4w"),
        (logmc,   "log_mcap"),
        (mc,      "mcap"),
        (rmom_1w, "rmom_1w"),
        (rmom_2w, "rmom_2w"),
        (rmom_4w, "rmom_4w"),
        (maxret,  "maxret_4w"),
    ]:
        m = df.stack(future_stack=True).reset_index()
        m.columns = ["week", "symbol", nm]
        rows.append(m)
    chars = rows[0]
    for m in rows[1:]:
        chars = chars.merge(m, on=["week", "symbol"], how="outer")
    chars["week"] = pd.to_datetime(chars["week"])
    return chars.sort_values(["week", "symbol"]).reset_index(drop=True)


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
        "SMBC":   sort_factor(df, "log_mcap",           -1),
        "MomC":   sort_factor(df, "mom_4w",             +1),
        "VolC":   sort_factor(df, "vol_4w",             -1),
        "NetMom": cluster_factor(df, "within_cluster_mom", +1),
        "NetRel": sort_factor(df, "cross_cluster_rel",  +1),
        "FunC":   sort_factor(df, "fees_to_mcap",       +1),
        "TVLC":   sort_factor(df, "tvl_to_mcap",        +1),
        # Han et al. (2023) risk-adjusted momentum + lottery factor
        "RMOM1w": sort_factor(df, "rmom_1w",            +1),
        "RMOM2w": sort_factor(df, "rmom_2w",            +1),
        "RMOM4w": sort_factor(df, "rmom_4w",            +1),
        "MAXRET": sort_factor(df, "maxret_4w",          +1),
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


# ── RESULTS.md Part 2 writer ────────────────────────────────────────────────

# Short descriptions for the pricing table
FACTOR_WHAT = {
    "RC":     "Crypto market (value-weighted)",
    "SMBC":   "Small minus big (size)",
    "MomC":   "4-week raw momentum",
    "VolC":   "Low-vol minus high-vol",
    "NetMom": "Within-cluster momentum",
    "NetRel": "Cross-cluster rotation",
    "FunC":   "High fees/mcap minus low",
    "TVLC":   "High TVL/mcap minus low",
    "RMOM1w": "1-week risk-adj momentum (Han '23)",
    "RMOM2w": "2-week risk-adj momentum (Han '23)",
    "RMOM4w": "4-week Sharpe momentum  (Han '23)",
    "MAXRET": "Max weekly return, 4w trailing (Han '23)",
    "SPC1":   "Sparse-PCA: DeFi-majors direction",
    "SPC2":   "Sparse-PCA: Payment/old-guard direction",
    "SPC3":   "Sparse-PCA: Alt-L1 direction",
    "SPC4":   "Sparse-PCA: Legacy/exchange direction",
    "CCA1":   "Macro-spanned direction 1",
    "CCA2":   "Macro-spanned direction 2",
    "CCA3":   "Macro-spanned direction 3",
    "MispricingM": "Equal-weight ASSD-dominant composite",
}

# Sign of the long leg, used to turn the raw characteristic IC (char rank vs
# forward return) into a *direction-adjusted* IC where positive always means
# "the factor's bet ranked coins correctly". Without this, low-vol/size factors
# (long the bottom of the sort) look like they have "backwards" IC when they are
# actually working. None = no weekly characteristic IC (price/structure factor).
FACTOR_DIR = {
    "SMBC": -1, "MomC": +1, "VolC": -1, "NetMom": +1, "NetRel": +1,
    "RMOM1w": +1, "RMOM2w": +1, "RMOM4w": +1, "MAXRET": +1,
}

# Per-factor economic function: the mechanism, why a premium *should* exist, and
# the sign we expect a priori. This is the "why should this work at all" half of
# every dossier entry — it stands on its own even when the statistics are thin.
FACTOR_ECON = {
    "RC": "The crypto market portfolio itself. Its premium is plain compensation for "
          "bearing systematic crypto risk — the equity-premium analogue. We expect "
          "λ>0 over the long run, but it is **not alpha**: every long-only holder "
          "already earns it. We include it so the cross-sectional factors are priced "
          "*net of* market beta.",
    "SMBC": "**Size.** Small caps should out-earn large caps as payment for illiquidity, "
            "thinner information coverage, and higher fundamental risk (the Fama-French "
            "SMB analogue). Expected long-small/short-big premium >0 in risk-on regimes; "
            "it can invert during flights to quality, when capital crowds into BTC/ETH.",
    "MomC": "**Momentum.** Investors under-react to news, so recent 4-week winners keep "
            "winning (Jegadeesh-Titman; Liu-Tsyvinski 2022). Expected premium >0, but "
            "raw momentum is regime-fragile and crashes hard at trend reversals.",
    "VolC": "**Low-volatility / betting-against-beta.** Leverage-constrained and "
            "lottery-seeking investors over-pay for high-vol names, leaving calm coins "
            "cheap (Frazzini-Pedersen 2014). Prediction: low-vol coins out-rank high-vol "
            "ones, so the *long-low/short-high* bet should earn a positive premium.",
    "NetMom": "**Within-cluster momentum.** Inside a tight correlation community, the coin "
              "out-trending its peers tends to keep leading. Ranking *within* the cluster "
              "strips out market beta and isolates idiosyncratic trend (Liu-Tsyvinski 2018). "
              "Expected premium >0.",
    "NetRel": "**Cross-cluster rotation.** Capital rotates between narratives; coins pulling "
              "ahead of the *other* clusters are riding the rotation in, laggards are "
              "rotating out. Expected premium >0 whenever narrative cycling is active.",
    "FunC": "**Crypto 'value' / cash yield** = fees per dollar of market cap. Protocols "
            "throwing off real cash should be cheap relative to fundamentals (the E/P "
            "analogue). Expected premium >0 — but only ~half the universe earns fees, so "
            "this is structurally under-powered.",
    "TVLC": "**DeFi engagement** = TVL per dollar of market cap. The bull thesis is "
            "usage-backed value; the competing 'TVL Irrelevance' view (Hartmann 2025) says "
            "it is already in prices. Sign is genuinely ambiguous a priori — this factor is "
            "a clean test of *whether TVL is priced at all*.",
    "RMOM1w": "**Risk-adjusted momentum (1w).** Trend scaled by recent volatility "
              "(Han et al. 2023). Dividing by risk strips the vol-driven noise that makes "
              "raw momentum crash, so it should rank more cleanly than MomC. Expected >0.",
    "RMOM2w": "**Risk-adjusted momentum (2w).** Two-week return over 4-week vol "
              "(Han et al. 2023). Same logic as RMOM1w at a slightly slower horizon.",
    "RMOM4w": "**Risk-adjusted momentum (4w)** = a 4-week Sharpe ratio (Han et al. 2023). "
              "Rewards trend that is both large *and* consistent.",
    "MAXRET": "**Lottery / max-return** (Han et al. 2023; Bali et al. 2011). Coins with an "
              "extreme recent up-week attract lottery demand and get over-priced, so the "
              "*correct* bet is to **short** the lottery — we expect high-max-return names "
              "to under-perform (a reversal/over-pricing signal, not a buy-the-winner one).",
    "SPC1": "Sparse-PCA risk **direction**, not an alpha bet — the dominant 'everything moves "
            "together' axis (BTC/ETH/DeFi majors). Describes *how* the market co-moves.",
    "SPC2": "Sparse-PCA risk **direction** — the payment/old-guard bloc (XRP, XLM, ADA, "
            "ALGO, HBAR). Context for diversification, not a tradable premium.",
    "SPC3": "Sparse-PCA risk **direction** — the alt-L1 bloc (SOL, AVAX, NEAR, ATOM, FET). "
            "Context for diversification, not a tradable premium.",
    "SPC4": "Sparse-PCA risk **direction** — the legacy/privacy + exchange bloc. "
            "Context for diversification, not a tradable premium.",
    "CCA1": "Macro-spanned **direction** — the slice of crypto returns explained by macro "
            "(rates, DXY, risk appetite). Risk context, not alpha by construction.",
    "CCA2": "Macro-spanned **direction** (2nd canonical axis). Risk context, not alpha.",
    "CCA3": "Macro-spanned **direction** (3rd canonical axis). Risk context, not alpha.",
    "MispricingM": "**Composite mispricing factor** — equal-weight of the L/S sleeves that "
                   "almost-stochastically dominate BTC (Stambaugh-Yuan 2017; Han et al. 2023). "
                   "Aggregates the common mispricing signal that no single thin factor proves "
                   "on its own.",
}

# Factors that are risk *directions* (structure), not alpha candidates.
STRUCTURE_FACTORS = {"SPC1", "SPC2", "SPC3", "SPC4", "CCA1", "CCA2", "CCA3"}


def _fmt(v, decimals=2, sign=True, pct=False):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    if pct:
        return f"{v*100:+.1f}%" if sign else f"{v*100:.1f}%"
    fmt = f"{{:+.{decimals}f}}" if sign else f"{{:.{decimals}f}}"
    return fmt.format(float(v))


# Graded confidence tiers. The whole point: a single |t|≥2 bar throws away
# factors that are economically real but only semi-significant on a 264-week
# sample, and it hides *which kind* of evidence backs a factor. We grade on the
# coherent combination of (i) weekly ranking power (IC), (ii) distributional
# dominance over BTC (ASD), and (iii) priced-risk evidence (GX/FMB λ).
GRADE_ORDER = [
    "Confirmed", "Priced risk", "Tradable signal",
    "Suggestive", "Economic-only", "Structure", "Not supported",
]
GRADE_BLURB = {
    "Confirmed":      "every test registers it as a strong, real factor",
    "Priced risk":    "compensated systematic exposure, but no week-to-week edge",
    "Tradable signal": "ranks the cross-section, though not a priced *risk*",
    "Suggestive":     "economic story intact + partial/semi-significant evidence",
    "Economic-only":  "sound rationale, but the data here can't confirm it",
    "Structure":      "a risk *direction* (how the market moves), not an alpha bet",
    "Not supported":  "fails its own prediction on this sample",
}


def _signed_ic(fname, p1, key):
    """Direction-adjusted IC t-stat: positive => the factor's bet ranked correctly."""
    raw = p1.get(key, np.nan)
    d = FACTOR_DIR.get(fname)
    if d is None or not np.isfinite(raw):
        return np.nan
    return raw * d


def grade_factor(fname, p1, full_lk):
    """Return (grade, evidence_dict) synthesizing IC + ASD + GX pricing.

    evidence_dict carries the already-signed/interpreted numbers the dossier
    prose and the master table both reuse, so they can never disagree."""
    tf = full_lk.get(fname, {}).get("tstat", np.nan)
    lam = full_lk.get(fname, {}).get("lambda_ann", np.nan)
    priced   = np.isfinite(tf) and abs(tf) >= 1.65
    borderline = np.isfinite(tf) and 1.3 <= abs(tf) < 1.65

    ic_is  = _signed_ic(fname, p1, "IS_IC_t")     # >0 means bet ranked correctly
    ic_oos = _signed_ic(fname, p1, "OOS_IC_t")
    has_ic = np.isfinite(ic_is)
    # "rank power" = correct-direction IC, significant IS and still positive OOS
    rank_strong = has_ic and ic_is >= 1.65 and np.isfinite(ic_oos) and ic_oos >= 1.0
    rank_semi   = has_ic and ((ic_is >= 1.3) or (ic_is >= 1.0 and np.isfinite(ic_oos) and ic_oos >= 1.0))
    # ranking that predicts the *opposite* of the long leg (reversal/lottery)
    rank_reversal = has_ic and ic_is <= -1.65 and np.isfinite(ic_oos) and ic_oos <= -1.0

    assd = bool(p1.get("assd_dom_btc"))
    afsd = bool(p1.get("afsd_dom_btc"))
    dom_by_btc = bool(p1.get("afsd_dom_by_btc"))

    # Do the weekly-ranking lens and the priced-risk lens point the same way?
    # ic_sign = +1 if longing the signal ranks correctly, -1 if it reverses.
    # lam_sign = sign of the priced premium on the (long-the-signal) factor.
    ic_sign  = 1 if rank_strong else (-1 if rank_reversal else 0)
    lam_sign = int(np.sign(lam)) if (priced and np.isfinite(lam)) else 0
    lens_agree    = bool(ic_sign and lam_sign and ic_sign == lam_sign)
    lens_conflict = bool(ic_sign and lam_sign and ic_sign != lam_sign)

    ev = dict(tf=tf, lam=lam, priced=priced, borderline=borderline,
              ic_is=ic_is, ic_oos=ic_oos, has_ic=has_ic,
              rank_strong=rank_strong, rank_semi=rank_semi, rank_reversal=rank_reversal,
              assd=assd, afsd=afsd, dom_by_btc=dom_by_btc,
              lens_agree=lens_agree, lens_conflict=lens_conflict)

    if fname == "RC":
        return "Priced risk", ev          # special-cased to market-beta prose
    if fname in STRUCTURE_FACTORS:
        return "Structure", ev
    if (rank_strong or rank_reversal) and priced:
        return "Confirmed", ev
    if priced and not (rank_strong or rank_reversal):
        return "Priced risk", ev
    if (rank_strong or rank_reversal) and not priced:
        return "Tradable signal", ev
    if assd or rank_semi or borderline:
        return "Suggestive", ev
    if dom_by_btc or (has_ic and ic_is <= -1.65 and not rank_reversal):
        return "Not supported", ev
    if not has_ic:                         # fundamentals: no weekly IC available
        return "Economic-only", ev
    return "Not supported", ev


def _tests_prose(fname, ev, p1):
    """One short paragraph reporting what each test actually said, interpreted."""
    bits = []
    # Weekly ranking (IC)
    if ev["has_ic"]:
        ic_is, ic_oos = ev["ic_is"], ev["ic_oos"]
        ic_line = (f"Weekly ranking (direction-adjusted IC): IS t={_fmt(ic_is)}, "
                   f"OOS t={_fmt(ic_oos)}")
        if ev["rank_strong"]:
            ic_line += " — significant in-sample and still pointing the right way out-of-sample."
        elif ev["rank_reversal"]:
            ic_line += (" — *significant but reversed*: high-signal names underperform in both "
                        "windows, so the tradable bet is to short them.")
        elif np.isfinite(ic_is) and abs(ic_is) >= 1.65:
            # significant in-sample but the OOS window doesn't confirm it
            dirtxt = ("significant in-sample in the expected direction" if ic_is > 0
                      else "significant in-sample but in *reverse* — a short-the-signal direction")
            ic_line += (f" — {dirtxt}, yet it does **not** survive out-of-sample; "
                        "reads as regime-specific, not a stable edge.")
        elif ev["rank_semi"]:
            ic_line += " — only marginal, but the correct sign carries into the OOS window."
        else:
            ic_line += " — no reliable weekly ranking power either way."
        bits.append(ic_line)
    else:
        bits.append("Weekly ranking: no 5-year IC (price/fundamental/structure factor — "
                    "judged on pricing, not on weekly rank).")
    # ASD vs BTC
    if np.isfinite(p1.get("asd_eps2", np.nan)):
        if ev["assd"]:
            bits.append(f"Distribution vs Bitcoin: **ASSD-dominant** (ε₂={_fmt(p1['asd_eps2'],3,False)} ≤ 0.032) "
                        "— risk-averse investors prefer its whole return distribution to simply holding BTC.")
        elif ev["dom_by_btc"]:
            bits.append(f"Distribution vs Bitcoin: **dominated by BTC** (ε₁ reverse small) — its return "
                        "distribution is worse than just holding Bitcoin.")
        else:
            bits.append(f"Distribution vs Bitcoin: neither dominates (ε₁={_fmt(p1.get('asd_eps1'),3,False)}, "
                        f"ε₂={_fmt(p1.get('asd_eps2'),3,False)}).")
    # Pricing (GX / FMB)
    if np.isfinite(ev["tf"]):
        if ev["priced"]:
            bits.append(f"Priced risk (Giglio-Xiu, hidden-factor robust): **λ={_fmt(ev['lam'],pct=True)}/yr, "
                        f"t={_fmt(ev['tf'])}** — a genuinely compensated exposure.")
        elif ev["borderline"]:
            bits.append(f"Priced risk: borderline (λ={_fmt(ev['lam'],pct=True)}/yr, t={_fmt(ev['tf'])}) — "
                        "suggestive but under the |t|≥1.65 bar.")
        else:
            bits.append(f"Priced risk: not priced once hidden factors are controlled (t={_fmt(ev['tf'])}).")
    return " ".join(bits)


def factor_dossier(order, p1, full_lk) -> str:
    """The centrepiece: one coherent entry per factor — economic function, what
    the tests say, and a graded verdict — sorted strongest-evidence first."""
    graded = []
    for f in order:
        if f not in p1 and f not in full_lk:
            continue
        grade, ev = grade_factor(f, p1.get(f, {}), full_lk)
        graded.append((GRADE_ORDER.index(grade), f, grade, ev))
    graded.sort(key=lambda x: (x[0], -abs(x[3]["tf"]) if np.isfinite(x[3]["tf"]) else 0))

    out = []
    for _, f, grade, ev in graded:
        what = FACTOR_WHAT.get(f, f)
        econ = FACTOR_ECON.get(f, "")
        tests = _tests_prose(f, ev, p1.get(f, {}))
        vsuffix = ""
        if ev["lens_agree"]:
            vsuffix = (" The weekly ranking and the multi-year priced-risk premium point the "
                       "**same way** — a clean signal you can both rank on and hold.")
        elif ev["lens_conflict"]:
            vsuffix = (" The two lenses **disagree in sign**: the short-term ranking edge and the "
                       "long-run priced-risk premium are *not the same trade* — rank on the weekly "
                       "signal, but respect that the multi-year L/S premium runs the other way.")
        out.append(
            f"#### {f} — {what}  ·  *{grade}*\n\n"
            f"- **Economic function.** {econ}\n"
            f"- **What the tests say.** {tests}\n"
            f"- **Verdict — {grade}:** {GRADE_BLURB[grade]}.{vsuffix}"
        )
    return "\n\n".join(out)


def write_results_part2(gx_full_results: dict, gx_is_results: dict,
                        factors_full: list, factors_is: list) -> None:
    """Rewrite RESULTS.md Part 2 from computed GX results + Part 1 stats."""
    results_path = STAGE / "RESULTS.md"
    p1_stats_path = DATA / "factor_validation_stats.parquet"

    # ---- load Part 1 stats ----
    p1 = {}
    if p1_stats_path.exists():
        df1 = pd.read_parquet(p1_stats_path)
        for _, row in df1.iterrows():
            p1[row["factor"]] = row.to_dict()

    # ---- build GX full-sample lookup (factor → {lambda_ann, tstat}) ----
    def _lookup(lam_df, model_key):
        if lam_df is None or lam_df.empty:
            return {}
        return {r["factor"]: r for _, r in lam_df.iterrows()}

    fmb_lk  = _lookup(gx_full_results["lam_fmb"],  "fmb")
    obs_lk  = _lookup(gx_full_results["lam_obs"],  "obs")
    full_lk = _lookup(gx_full_results["lam_full"], "full")

    fmb_is_lk  = _lookup(gx_is_results["lam_fmb"],  "fmb")
    full_is_lk = _lookup(gx_is_results["lam_full"], "full")

    # ---- helper: gx row ----
    def gx_row(fname):
        fmb  = fmb_lk.get(fname,  {})
        obs  = obs_lk.get(fname,  {})
        full = full_lk.get(fname, {})
        lf   = full.get("lambda_ann", np.nan)
        tf   = full.get("tstat",      np.nan)
        lo   = obs.get("lambda_ann",  np.nan)
        to_  = obs.get("tstat",       np.nan)
        lfmb = fmb.get("lambda_ann",  np.nan)
        tfmb = fmb.get("tstat",       np.nan)
        bold = lambda t: f"**{_fmt(t)}**" if np.isfinite(t) and abs(t) >= 1.65 else _fmt(t)
        priced = "**Priced**" if np.isfinite(tf) and abs(tf) >= 1.65 else (
                 "Borderline" if np.isfinite(tf) and abs(tf) >= 1.3 else "No")
        what = FACTOR_WHAT.get(fname, fname)
        return (f"| {fname} | {what} | {_fmt(lfmb, pct=True)} | {bold(tfmb)} | "
                f"{_fmt(lo, pct=True)} | {bold(to_)} | {_fmt(lf, pct=True)} | "
                f"{bold(tf)} | {priced} |")

    priced_full = [f for f in factors_full
                   if abs((full_lk.get(f, {}).get("tstat", 0) or 0)) >= 1.65]
    priced_is   = [f for f in factors_is
                   if abs((full_is_lk.get(f, {}).get("tstat", 0) or 0)) >= 1.65]

    k_full = int(gx_full_results["k_hidden"])
    k_is   = int(gx_is_results["k_hidden"])
    n_full = len(factors_full)

    # ---- master summary table ----
    all_factors_ordered = [
        "RC", "VolC", "MAXRET", "TVLC", "SMBC", "MomC",
        "NetMom", "NetRel", "RMOM1w", "RMOM2w", "RMOM4w",
        "FunC", "SPC1", "SPC2", "SPC3", "SPC4",
        "CCA1", "CCA2", "CCA3", "MispricingM",
    ]

    def master_row(fname):
        p = p1.get(fname, {})
        full = full_lk.get(fname, {})
        tf   = full.get("tstat", np.nan)
        ic_t_is  = p.get("IS_IC_t",  np.nan)
        ic_t_oos = p.get("OOS_IC_t", np.nan)
        asd_e1   = p.get("asd_eps1", np.nan)
        asd_e2   = p.get("asd_eps2", np.nan)
        afsd = "✓" if p.get("afsd_dom_btc") else ("✗" if fname in p1 else "—")
        assd = "✓" if p.get("assd_dom_btc") else ("✗" if fname in p1 else "—")
        verd = p.get("verdict", "—").split(" (")[0] if fname in p1 else "—"

        ic_is_s  = _fmt(ic_t_is)  if np.isfinite(ic_t_is)  else "—"
        ic_oos_s = _fmt(ic_t_oos) if np.isfinite(ic_t_oos) else "—"
        tf_s     = _fmt(tf)       if np.isfinite(tf)        else "—"
        e1_s     = _fmt(asd_e1, 3, False) if np.isfinite(asd_e1) else "—"
        e2_s     = _fmt(asd_e2, 3, False) if np.isfinite(asd_e2) else "—"

        # overall conclusion — same graded call the dossier uses, so the
        # summary table and the prose can never drift apart.
        grade, _ = grade_factor(fname, p, full_lk)
        conclusion = f"**{grade}**" if grade == "Confirmed" else grade

        return (f"| {fname} | {ic_is_s} | {ic_oos_s} | {afsd} | {assd} | "
                f"{e1_s} | {e2_s} | {tf_s} | {conclusion} |")

    # ---- shortlist grouped by graded tier (single source of truth) ----
    by_grade: dict[str, list] = {g: [] for g in GRADE_ORDER}
    for f in all_factors_ordered:
        if f not in p1 and f not in full_lk:
            continue
        g, _ = grade_factor(f, p1.get(f, {}), full_lk)
        by_grade[g].append(f)
    shortlist_by_grade = "\n".join(
        f"- **{g}** ({GRADE_BLURB[g]}): {', '.join(by_grade[g])}"
        for g in GRADE_ORDER if by_grade[g]
    )

    # ---- compose Part 2 markdown ----
    part2 = f"""## Part 2 — Economic significance: Giglio-Xiu + Fama-MacBeth pricing (5-year panel)

*What this section adds:* Part 1 tested whether each factor **ranks coins correctly** week-to-week
(IC test) and whether its return distribution **beats Bitcoin** (ASD test). Part 2 asks a
fundamentally different question: **is a factor a priced source of systematic risk?** A factor is
"priced" if assets that load heavily on it earn systematically higher or lower returns across
the full 5-year cross-section — regardless of weekly noise.

We now test **all factors** — including the four new Han et al. (2023) factors (RMOM1w, RMOM2w,
RMOM4w, MAXRET) — through the same GX pricing engine. This is the first time both Part 1 and
Part 2 cover the same factor universe, enabling the master comparison table at the end.

We run **three pricing methods** side by side:
- **FMB (Fama-MacBeth 1973)** — week-by-week cross-sectional OLS, average λ_t, Newey-West SE.
  Conservative and standard but noisy when factors > assets/week.
- **GX obs-only** — single cross-section on mean returns, heteroskedasticity-robust SE.
  More stable than FMB but ignores hidden risk factors.
- **GX full (Giglio-Xiu 2021)** — adds a third pass: Bai-Ng selects K_hidden latent factors
  from residuals, re-estimates betas on observed + hidden, re-prices. The most credible number
  because it removes contamination from unobserved systematic forces.

**How to read the table:**
- **λ (%/yr)** = annualised risk premium. Positive = assets exposed to this factor earn more.
- **t-stat**: **bold** = |t| ≥ 1.65 (statistically meaningful). Plain = not significant.

### Full-sample results — {n_full} factors, K_hidden = {k_full}

Full factor set: RC + SMBC + MomC + VolC + NetMom + NetRel (original 6) ·
FunC + TVLC (fundamentals) · RMOM1w + RMOM2w + RMOM4w + MAXRET (Han et al. 2023) ·
SPC1–4 (Sparse PCA) · CCA1–3 (macro-spanned).

| Factor | What it is | FMB λ | t_fmb | GX-obs λ | t_obs | GX-full λ | t_gx | Verdict |
|---|---|---|---|---|---|---|---|---|
""" + "\n".join(gx_row(f) for f in factors_full) + f"""

The bold t-stats above are *inputs*, not verdicts. The dossier below reads them
together with the IC and ASD evidence from Part 1 so each factor gets one coherent
story instead of being scattered across five tables.

---

### Per-factor dossier — economic function · what the tests say · graded verdict

We grade on a deliberately **non-binary** scale. A 264-week crypto panel cannot
deliver |t|≥2 everywhere, and a factor can be real along one axis (it ranks coins,
or it dominates BTC's distribution, or it is a priced risk) while silent along the
others. Collapsing all of that to "significant / not significant" throws away most
of what we actually learned, so we keep the **economic function** of every factor in
view alongside whatever the statistics could and could not show.

| Grade | What it means |
|---|---|
""" + "\n".join(f"| **{g}** | {GRADE_BLURB[g]} |" for g in GRADE_ORDER) + f"""

Each entry answers three independent questions — does it **rank** coins week-to-week
(IC, Part 1), does its **return distribution beat Bitcoin** (ASD, Part 1), and is it a
**priced source of risk** (GX/FMB λ, above)? — and weighs them against the factor's
standalone economic rationale. Sorted strongest-evidence first.

""" + factor_dossier(all_factors_ordered, p1, full_lk) + f"""

### IS-only stability check (K_hidden = {k_is})

IS window factors: {factors_is}. Priced at |t|≥1.65: {priced_is}.
The IS window uses {k_is} hidden factors (vs {k_full} full-sample) because the shorter window
leaves more unexplained residual variance. Use the full-sample results as primary evidence.

---

### Master comparison — all factors across all three tests

This is the unified view combining Part 1 (IC + ASD) and Part 2 (GX pricing).
Each factor is judged on: IC ranking power (IS and OOS t-stats), ASD vs Bitcoin
(AFSD/ASSD flags and ε values), and GX-full pricing (t-stat).

| Factor | IC IS t | IC OOS t | AFSD? | ASSD? | ε₁ | ε₂ | GX t_gx | Conclusion |
|---|---|---|---|---|---|---|---|---|
""" + "\n".join(master_row(f) for f in all_factors_ordered
                if f in p1 or f in full_lk) + f"""

**Legend.** IC IS/OOS t = Newey-West t-stat on the mean IC (here shown *direction-raw*;
the dossier reports the direction-adjusted version). AFSD ✓ = ε₁ ≤ 5.9%, ASSD ✓ = ε₂ ≤ 3.2%
(almost first/second-order dominance over Bitcoin). GX t_gx = Giglio-Xiu full-model t
(|t|≥1.65 = priced). The **Conclusion** column is the dossier grade — the same call used in
the prose above, so the two can never disagree.

**The shortlist by grade.** Reading down the grades:
{shortlist_by_grade}

*Confirmed* factors are backed from two independent angles and are the defensible core.
*Priced risk* and *Tradable signal* factors are real but one-dimensional — useful, with a
named limitation. *Suggestive* factors have an intact economic story and partial evidence:
exactly the semi-significant cases a single |t|≥2 bar would have silently discarded.
"""

    # ---- write to RESULTS.md (preserve Part 1) ----
    existing = results_path.read_text() if results_path.exists() else ""
    # Strip any existing Part 2
    for marker in ["\n---\n\n## Part 2", "\n\n## Part 2", "\n## Part 2"]:
        if marker in existing:
            existing = existing.split("## Part 2")[0].rstrip()
            break

    results_path.write_text(existing.rstrip() + "\n\n---\n\n" + part2 + "\n")
    print(f"  Wrote Part 2 → {results_path.relative_to(STAGE.parent)}")


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
    # Leakage-free gap fill: forward-fill interior gaps from PAST observations
    # only; the column mean is used solely for unavoidable leading NaNs (no prior
    # value exists to carry forward). The previous fillna(c.mean()) used the
    # whole-window mean — including future weeks — to patch past gaps, which is
    # mild look-ahead for sparse factors (TVLC, FunC).
    zoo_is_fit = zoo_is_fit.apply(lambda c: c.ffill().fillna(c.mean()))
    rw_is = ret_wide.loc[IS_START:IS_END]

    print(f"\nGX IS ({IS_START.date()}→{IS_END.date()}, {len(zoo_is_fit)} weeks) "
          f"factors: {list(zoo_is_fit.columns)} ...")
    gx_is = giglio_xiu(rw_is, zoo_is_fit)
    print(f"  K_hidden = {gx_is['k_hidden']}")
    print_lambda_table("IS — FMB vs GX", gx_is["lam_fmb"], gx_is["lam_obs"], gx_is["lam_full"])

    # ---- GX on full window ----
    zoo_full = zoo.loc[IS_START:OOS_END].copy()
    # Leakage-free gap fill (see IS block above): ffill past obs, mean only for
    # leading NaNs.
    zoo_full_fit = zoo_full.apply(lambda c: c.ffill().fillna(c.mean()))
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

    # ---- rewrite RESULTS.md Part 2 with integrated narrative + master table ----
    print("\nWriting integrated RESULTS.md Part 2 ...")
    write_results_part2(gx_full, gx_is,
                        list(zoo_full_fit.columns), list(zoo_is_fit.columns))
    print("done.")


if __name__ == "__main__":
    main()
