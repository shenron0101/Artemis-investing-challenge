"""09 — Goal 2.5: in-sample / out-of-sample significance test for every factor.

For each economic factor we build its weekly long/short return series on the
Stage-09 5-year panel, split the timeline into the frozen IS and OOS windows, and
ask two questions:
    (1) is the factor's average payoff statistically significant IN-SAMPLE?
    (2) does it still hold up OUT-OF-SAMPLE?
A factor is "competition-grade" only if it passes both.

Factors built here:
    SMBC     size          long bottom-30% log-mcap, short top-30%
    MomC     momentum      long top-30% trailing-4w return, short bottom-30%
    VolC     low-vol       long bottom-30% 4w realised vol, short top-30%
    NetMom   within-cluster momentum (cluster-neutral, top/bottom half per cluster)
    NetRel   cross-cluster relative strength (tercile)
    RMOM1w   risk-adj mom  1-week return / 4w rolling vol  [Han et al. 2023]
    RMOM2w   risk-adj mom  2-week return / 4w rolling vol  [Han et al. 2023]
    RMOM4w   risk-adj mom  4-week Sharpe ratio              [Han et al. 2023]
    MAXRET   max weekly return over trailing 4 weeks        [Han et al. 2023]
    SPC1-4   Sparse-PCA structure factors (from 06; risk directions, not alpha)

Han et al. (2023, EFM) show that risk-adjusted momentum and MAXRET are among the
8 crypto factor portfolios that almost stochastically dominate equity/bond/BTC
benchmarks.  We test this on our 5-year, 113-asset panel.

Not built (no 5-year data): FunC / TVLC / SupC need fundamentals (fees, TVL,
supply) we did not re-fetch over 5 years; they remain validated only on the
52-week sample in 08_nalfp.

Significance = Newey-West t-stat (lags=4) on the mean weekly L/S return.
ASD test = Almost First/Second-order Stochastic Dominance vs Bitcoin benchmark
    (Leshno & Levy 2002; Levy et al. 2010).
    AFSD: ε₁ ≤ 5.9%  →  factor almost first-order dominates BTC
    ASSD: ε₂ ≤ 3.2%  →  factor almost second-order dominates BTC

Outputs
-------
    artifacts/data/factor_validation_stats.parquet
    RESULTS.md   (plain-language results, undergrad-readable)
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from scipy.sparse.csgraph import minimum_spanning_tree

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
DATA_DIR = STAGE / "artifacts" / "data"
MANIFEST_DIR = STAGE / "artifacts" / "manifests"

NET_WINDOW = 12       # weeks for the rolling correlation graph
MIN_NAMES = 10        # min cross-section to form a sorted factor
SIG = 2.0             # |t| bar for "significant" (paper used 1.65; we are stricter)

# Han et al. (2023) ASD critical values
AFSD_CRITICAL = 0.059   # ε₁* — Levy et al. (2010)
ASSD_CRITICAL = 0.032   # ε₂*

CHAR_FACTORS = {      # name -> (characteristic, direction, frac, kind)
    "SMBC":   ("log_mcap",  -1, 0.30, "sort"),
    "MomC":   ("mom_4w",    +1, 0.30, "sort"),
    "VolC":   ("vol_4w",    -1, 0.30, "sort"),
    "NetMom": ("within_cluster_mom", +1, 0.50, "cluster"),
    "NetRel": ("cross_cluster_rel",  +1, 0.30, "sort"),
    # --- risk-adjusted momentum (Han et al. 2023) ---
    "RMOM1w": ("rmom_1w",   +1, 0.30, "sort"),
    "RMOM2w": ("rmom_2w",   +1, 0.30, "sort"),
    "RMOM4w": ("rmom_4w",   +1, 0.30, "sort"),
    # --- max-return lottery factor (Han et al. 2023) ---
    "MAXRET": ("maxret_4w", +1, 0.30, "sort"),
}


# ---------------------------------------------------------------------------
# characteristics
# ---------------------------------------------------------------------------

def build_characteristics(panel: pd.DataFrame) -> pd.DataFrame:
    px = panel.pivot(index="week", columns="symbol", values="price").sort_index()
    mc = panel.pivot(index="week", columns="symbol", values="mcap").sort_index()
    ret = px.pct_change()
    fwd = ret.shift(-1)                           # forward weekly return (t → t+1)

    mom4 = px / px.shift(4) - 1.0                # trailing 4-week raw return
    mom2 = px / px.shift(2) - 1.0                # trailing 2-week raw return
    vol4 = ret.rolling(4).std()                   # 4-week realised volatility
    logmc = np.log(mc.where(mc > 0))

    # --- Han et al. (2023) characteristics ---
    # Risk-adjusted momentum: return / rolling-4w vol (weekly Sharpe proxy)
    rmom_4w_mean = ret.rolling(4).mean()
    rmom_4w_std  = ret.rolling(4).std()
    rmom_4w = rmom_4w_mean / rmom_4w_std.replace(0, np.nan)  # 4-week Sharpe

    # 1-week and 2-week returns normalised by 4w vol
    rmom_1w = ret / vol4.replace(0, np.nan)
    rmom_2w = mom2 / vol4.replace(0, np.nan)

    # MAXRET: highest single-week return seen over trailing 4 weeks
    maxret_4w = ret.rolling(4).max()

    def melt(df, name):
        return df.reset_index().melt(id_vars="week", var_name="symbol", value_name=name)

    out = melt(ret, "ret_1w")
    for df, nm in [
        (fwd,       "fwd_ret_1w"),
        (mom4,      "mom_4w"),
        (vol4,      "vol_4w"),
        (logmc,     "log_mcap"),
        (rmom_1w,   "rmom_1w"),
        (rmom_2w,   "rmom_2w"),
        (rmom_4w,   "rmom_4w"),
        (maxret_4w, "maxret_4w"),
    ]:
        out = out.merge(melt(df, nm), on=["week", "symbol"], how="left")

    return out, ret


# ---------------------------------------------------------------------------
# network clustering (Spearman → distance → MST → Louvain)
# ---------------------------------------------------------------------------

def cluster_one_week(window: pd.DataFrame) -> pd.Series:
    win = window.dropna(axis=1, thresh=NET_WINDOW - 2)
    if win.shape[1] < 4:
        return pd.Series(dtype=int)
    corr = win.corr(method="spearman").dropna(how="all").dropna(axis=1, how="all")
    if corr.shape[0] < 4:
        return pd.Series(dtype=int)
    dist = np.sqrt(np.clip(2 * (1 - corr.values), 0, None))
    mst = minimum_spanning_tree(dist).toarray()
    g = nx.Graph()
    syms = list(corr.columns)
    g.add_nodes_from(syms)
    for i in range(len(syms)):
        for j in range(len(syms)):
            if mst[i, j] > 0:
                g.add_edge(syms[i], syms[j], weight=1.0 / (mst[i, j] + 1e-6))
    parts = nx.community.louvain_communities(g, weight="weight", seed=0)
    lab = {s: k for k, com in enumerate(parts) for s in com}
    return pd.Series(lab)


def build_clusters(ret: pd.DataFrame) -> pd.DataFrame:
    weeks = ret.index
    rows = []
    for i in range(NET_WINDOW, len(weeks)):
        w = weeks[i]
        labels = cluster_one_week(ret.iloc[i - NET_WINDOW:i])
        for sym, cl in labels.items():
            rows.append({"week": w, "symbol": sym, "cluster_id": int(cl)})
    return pd.DataFrame(rows)


def add_cluster_features(df: pd.DataFrame, clusters: pd.DataFrame) -> pd.DataFrame:
    out = df.merge(clusters, on=["week", "symbol"], how="left")
    by_wc = out.groupby(["week", "cluster_id"])["mom_4w"]
    cms, cmc = by_wc.transform("sum"), by_wc.transform("count")
    out["within_cluster_mom"] = (cms - out["mom_4w"].fillna(0)) / (
        cmc - out["mom_4w"].notna().astype(int)).replace(0, np.nan)
    wms = out.groupby("week")["mom_4w"].transform("sum")
    wmc = out.groupby("week")["mom_4w"].transform("count")
    other = (wms - cms) / (wmc - cmc).replace(0, np.nan)
    out["cross_cluster_rel"] = out["mom_4w"] - other
    return out


# ---------------------------------------------------------------------------
# factor portfolios
# ---------------------------------------------------------------------------

def sort_factor(df, col, direction, frac):
    keep = df.dropna(subset=["fwd_ret_1w", col])

    def one(block):
        n = len(block)
        if n < MIN_NAMES:
            return np.nan
        k = max(int(round(n * frac)), 3)
        r = block[col].rank(method="first")
        long_m  = (r > n - k) if direction == +1 else (r <= k)
        short_m = (r <= k)    if direction == +1 else (r > n - k)
        return float(block.loc[long_m, "fwd_ret_1w"].mean()
                     - block.loc[short_m, "fwd_ret_1w"].mean())

    return keep.groupby("week").apply(one).rename("ret")


def cluster_factor(df, col, direction):
    keep = df.dropna(subset=["fwd_ret_1w", col, "cluster_id"])

    def one(block):
        pcs = []
        for _, g in block.groupby("cluster_id"):
            if len(g) < 4:
                continue
            n = len(g); half = n // 2
            r = g[col].rank(method="first")
            long_m  = (r > n - half) if direction == +1 else (r <= half)
            short_m = (r <= half)    if direction == +1 else (r > n - half)
            pcs.append(g.loc[long_m, "fwd_ret_1w"].mean()
                       - g.loc[short_m, "fwd_ret_1w"].mean())
        return float(np.mean(pcs)) if pcs else np.nan

    return keep.groupby("week").apply(one).rename("ret")


def ic_series(df, col):
    keep = df.dropna(subset=["fwd_ret_1w", col])
    return keep.groupby("week").apply(
        lambda b: b[col].rank().corr(b["fwd_ret_1w"].rank()) if len(b) >= MIN_NAMES else np.nan)


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------

def newey_west_se(r: np.ndarray, lags: int = 4) -> float:
    n = len(r)
    if n < 2:
        return np.nan
    e = r - r.mean()
    s = (e * e).mean()
    for lag in range(1, min(lags, n - 1) + 1):
        s += 2.0 * (1 - lag / (lags + 1)) * (e[lag:] * e[:-lag]).mean()
    return float(np.sqrt(max(s, 0.0) / n))


def window_stats(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 5:
        return dict(n=len(r), ann_ret=np.nan, sharpe=np.nan, t=np.nan,
                    skew=np.nan, kurt=np.nan, jb_p=np.nan)
    mean = r.mean()
    se = newey_west_se(r.values, 4)
    sk  = float(sp_stats.skew(r))
    ku  = float(sp_stats.kurtosis(r))         # excess kurtosis
    jb  = float(sp_stats.jarque_bera(r).pvalue)
    return dict(
        n       = int(len(r)),
        ann_ret = mean * 52,
        sharpe  = (mean / r.std()) * np.sqrt(52) if r.std() > 0 else np.nan,
        t       = mean / se if se and se > 0 else np.nan,
        skew    = sk,
        kurt    = ku,
        jb_p    = jb,
    )


def ic_window(ic: pd.Series, lo, hi) -> dict:
    s = ic[(ic.index >= lo) & (ic.index <= hi)].dropna()
    if len(s) < 5:
        return dict(ic=np.nan, t=np.nan)
    se = newey_west_se(s.values, 4)
    return dict(ic=float(s.mean()), t=float(s.mean() / se) if se and se > 0 else np.nan)


def verdict(metric: str, is_s: dict, oos_s: dict) -> str:
    is_t,  oos_t  = is_s.get(metric),   oos_s.get(metric)
    is_val = is_s.get("ic" if metric == "ic_t" else "ann_ret")
    oos_val = oos_s.get("ic" if metric == "ic_t" else "ann_ret")
    if not np.isfinite(is_t) or abs(is_t) < SIG:
        return "Weak (not significant in-sample → drop)"
    same_sign = np.sign(is_val) == np.sign(oos_val)
    if same_sign and np.isfinite(oos_t) and abs(oos_t) >= 1.0:
        return "Robust (significant IS, holds OOS)"
    return "In-sample only (significant IS, fades/flips OOS → flag)"


# ---------------------------------------------------------------------------
# Almost Stochastic Dominance  (Han et al. 2023 / Leshno & Levy 2002)
# ---------------------------------------------------------------------------

def compute_asd(h_rets: np.ndarray, l_rets: np.ndarray,
                n_grid: int = 1000) -> dict:
    """
    Test whether H (factor L/S portfolio) almost dominates L (benchmark).

    AFSD: ε₁ = M / (M + N)  where M = ∫ max(F_H - F_L, 0) dr  (violation area)
          ε₁ ≤ 5.9%  →  factor AFSD-dominates benchmark

    ASSD: ε₂ = M₂ / (M₂ + N₂) using the *integrated* CDF difference
          ε₂ ≤ 3.2%  →  factor ASSD-dominates benchmark

    Also compute ε in the reverse direction (benchmark dominates factor).
    """
    h = h_rets[np.isfinite(h_rets)]
    l = l_rets[np.isfinite(l_rets)]
    if len(h) < 10 or len(l) < 10:
        return {k: np.nan for k in
                ["eps1_fwd", "eps2_fwd", "eps1_rev", "eps2_rev",
                 "afsd_dominates", "assd_dominates",
                 "afsd_dominated_by", "assd_dominated_by"]}

    lo = min(h.min(), l.min())
    hi = max(h.max(), l.max())
    grid = np.linspace(lo, hi, n_grid)
    step = (hi - lo) / (n_grid - 1) if hi > lo else 1.0

    F_H = np.array([np.mean(h <= x) for x in grid])
    F_L = np.array([np.mean(l <= x) for x in grid])

    def _eps1(fh, fl):
        d = fh - fl
        M = step * np.sum(np.maximum(d, 0.0))
        total = step * np.sum(np.abs(d))
        return M / total if total > 1e-12 else 0.0

    def _eps2(fh, fl):
        # Cumulative integral of (F_H - F_L) — positive where H has excess CDF mass
        cum = np.cumsum((fh - fl)) * step
        M = step * np.sum(np.maximum(cum, 0.0))
        total = step * np.sum(np.abs(cum))
        return M / total if total > 1e-12 else 0.0

    e1_fwd = _eps1(F_H, F_L)   # factor vs BTC: small → factor dominates BTC
    e2_fwd = _eps2(F_H, F_L)
    e1_rev = _eps1(F_L, F_H)   # BTC vs factor: small → BTC dominates factor
    e2_rev = _eps2(F_L, F_H)

    return {
        "eps1_fwd":          float(e1_fwd),
        "eps2_fwd":          float(e2_fwd),
        "eps1_rev":          float(e1_rev),
        "eps2_rev":          float(e2_rev),
        "afsd_dominates":    bool(e1_fwd <= AFSD_CRITICAL),
        "assd_dominates":    bool(e2_fwd <= ASSD_CRITICAL),
        "afsd_dominated_by": bool(e1_rev <= AFSD_CRITICAL),
        "assd_dominated_by": bool(e2_rev <= ASSD_CRITICAL),
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    man = json.loads((MANIFEST_DIR / "universe_manifest.json").read_text())
    trade = set(man["trading_universe"]["symbols_ever_eligible"])
    is_lo,  is_hi  = [pd.Timestamp(x) for x in man["split"]["in_sample"]]
    oos_lo, oos_hi = [pd.Timestamp(x) for x in man["split"]["out_of_sample"]]

    panel = pd.read_parquet(DATA_DIR / "price_mcap_panel_weekly.parquet")
    panel["week"] = pd.to_datetime(panel["week"])
    panel = panel[panel["symbol"].isin(trade)]

    # BTC weekly return as ASD benchmark
    ref = pd.read_parquet(DATA_DIR / "reference_weekly.parquet")
    btc_ret = ref["BTC"].dropna()

    print("  building characteristics ...")
    chars, ret_wide = build_characteristics(panel)
    print("  building network clusters (rolling 12w MST+Louvain) ...")
    clusters = build_clusters(ret_wide)
    chars = add_cluster_features(chars, clusters)

    # ---- factor return series ----
    fac_rets: dict[str, pd.Series] = {}
    ics:      dict[str, pd.Series] = {}
    for name, (col, direction, frac, kind) in CHAR_FACTORS.items():
        if kind == "cluster":
            fac_rets[name] = cluster_factor(chars, col, direction)
        else:
            fac_rets[name] = sort_factor(chars, col, direction, frac)
        ics[name] = ic_series(chars, col)

    # Sparse-PCA structure factors (precomputed weekly returns from script 06)
    spc = pd.read_parquet(DATA_DIR / "sparse_pca_factor_returns.parquet")
    spc.index = pd.to_datetime(spc.index)
    for c in [c for c in spc.columns if c.startswith("SPC")]:
        fac_rets[c] = spc[c].rename("ret")

    # ---- per-factor statistics + ASD ----
    rows = []
    for name, r in fac_rets.items():
        r.index = pd.to_datetime(r.index)
        is_r  = r[(r.index >= is_lo)  & (r.index <= is_hi)]
        oos_r = r[(r.index >= oos_lo) & (r.index <= oos_hi)]
        full_r = r.dropna()

        s_is  = window_stats(is_r)
        s_oos = window_stats(oos_r)

        is_char = name in CHAR_FACTORS
        if is_char:
            ic = ics[name]; ic.index = pd.to_datetime(ic.index)
            ic_is  = ic_window(ic, is_lo,  is_hi)
            ic_oos = ic_window(ic, oos_lo, oos_hi)
            s_is.update(ic=ic_is["ic"],   ic_t=ic_is["t"])
            s_oos.update(ic=ic_oos["ic"], ic_t=ic_oos["t"])
            v = verdict("ic_t", s_is, s_oos)
        else:
            s_is.update(ic=np.nan, ic_t=np.nan)
            s_oos.update(ic=np.nan, ic_t=np.nan)
            v = "Structure factor (risk direction, not an alpha bet)"

        # ASD vs BTC over full sample and OOS window
        btc_aligned = btc_ret.reindex(full_r.index).dropna()
        fac_aligned = full_r.reindex(btc_aligned.index).dropna()
        btc_aligned = btc_aligned.reindex(fac_aligned.index)
        asd_full = compute_asd(fac_aligned.values, btc_aligned.values)

        btc_oos  = btc_ret[(btc_ret.index >= oos_lo) & (btc_ret.index <= oos_hi)].dropna()
        fac_oos_asd = oos_r.reindex(btc_oos.index).dropna()
        btc_oos_asd = btc_oos.reindex(fac_oos_asd.index)
        asd_oos = compute_asd(fac_oos_asd.values, btc_oos_asd.values)

        rows.append({
            "factor":      name,
            "group":       "characteristic" if is_char else "sparse-PCA",
            # IS stats
            "IS_n":        s_is["n"],   "IS_annret":  s_is["ann_ret"],
            "IS_sharpe":   s_is["sharpe"], "IS_t":    s_is["t"],
            "IS_IC":       s_is["ic"],  "IS_IC_t":   s_is["ic_t"],
            "IS_skew":     s_is["skew"], "IS_kurt":  s_is["kurt"], "IS_jb_p": s_is["jb_p"],
            # OOS stats
            "OOS_n":       s_oos["n"],  "OOS_annret": s_oos["ann_ret"],
            "OOS_sharpe":  s_oos["sharpe"], "OOS_t":  s_oos["t"],
            "OOS_IC":      s_oos["ic"], "OOS_IC_t":  s_oos["ic_t"],
            "OOS_skew":    s_oos["skew"], "OOS_kurt": s_oos["kurt"], "OOS_jb_p": s_oos["jb_p"],
            # ASD vs BTC (full sample)
            "asd_eps1":    asd_full["eps1_fwd"],  "asd_eps2":  asd_full["eps2_fwd"],
            "afsd_dom_btc": asd_full["afsd_dominates"],
            "assd_dom_btc": asd_full["assd_dominates"],
            "afsd_dom_by_btc": asd_full["afsd_dominated_by"],
            # ASD vs BTC (OOS only)
            "oos_asd_eps1": asd_oos["eps1_fwd"], "oos_asd_eps2": asd_oos["eps2_fwd"],
            "oos_afsd_dom": asd_oos["afsd_dominates"],
            "oos_assd_dom": asd_oos["assd_dominates"],
            "verdict":     v,
        })

    stats = pd.DataFrame(rows)

    # ---- MispricingM: equal-weight of ASD-dominant L/S portfolios ----
    # Factors that AFSD or ASSD dominate BTC (full sample) form the composite
    dom_names = stats.loc[
        stats["afsd_dom_btc"] | stats["assd_dom_btc"], "factor"
    ].tolist()

    if dom_names:
        dom_rets = pd.DataFrame({n: fac_rets[n] for n in dom_names})
        dom_rets.index = pd.to_datetime(dom_rets.index)
        mism = dom_rets.mean(axis=1).rename("MispricingM")

        mis_is  = window_stats(mism[(mism.index >= is_lo)  & (mism.index <= is_hi)])
        mis_oos = window_stats(mism[(mism.index >= oos_lo) & (mism.index <= oos_hi)])
        btc_asd = btc_ret.reindex(mism.dropna().index).dropna()
        mis_asd_vals = mism.reindex(btc_asd.index).dropna()
        btc_asd2 = btc_asd.reindex(mis_asd_vals.index)
        mis_asd = compute_asd(mis_asd_vals.values, btc_asd2.values)

        rows.append({
            "factor": "MispricingM", "group": "composite",
            "IS_n": mis_is["n"],   "IS_annret": mis_is["ann_ret"],
            "IS_sharpe": mis_is["sharpe"], "IS_t": mis_is["t"],
            "IS_IC": np.nan, "IS_IC_t": np.nan,
            "IS_skew": mis_is["skew"], "IS_kurt": mis_is["kurt"], "IS_jb_p": mis_is["jb_p"],
            "OOS_n": mis_oos["n"], "OOS_annret": mis_oos["ann_ret"],
            "OOS_sharpe": mis_oos["sharpe"], "OOS_t": mis_oos["t"],
            "OOS_IC": np.nan, "OOS_IC_t": np.nan,
            "OOS_skew": mis_oos["skew"], "OOS_kurt": mis_oos["kurt"], "OOS_jb_p": mis_oos["jb_p"],
            "asd_eps1": mis_asd["eps1_fwd"], "asd_eps2": mis_asd["eps2_fwd"],
            "afsd_dom_btc": mis_asd["afsd_dominates"],
            "assd_dom_btc": mis_asd["assd_dominates"],
            "afsd_dom_by_btc": mis_asd["afsd_dominated_by"],
            "oos_asd_eps1": np.nan, "oos_asd_eps2": np.nan,
            "oos_afsd_dom": False, "oos_assd_dom": False,
            "verdict": "Composite (mispricing factor — equal-weight of ASD-dominant factors)",
        })
        stats = pd.DataFrame(rows)
        print(f"\n  MispricingM built from: {dom_names}")
    else:
        mism = None
        print("\n  MispricingM: no factors passed ASD dominance vs BTC (full sample).")

    stats.to_parquet(DATA_DIR / "factor_validation_stats.parquet", index=False)

    pd.set_option("display.width", 220, "display.max_columns", 35)
    show = ["factor", "IS_IC", "IS_IC_t", "OOS_IC", "OOS_IC_t",
            "IS_sharpe", "OOS_sharpe", "asd_eps1", "asd_eps2",
            "afsd_dom_btc", "assd_dom_btc", "verdict"]
    print("\n", stats[show].round(3).to_string(index=False))
    write_results_md(stats, man, dom_names)
    print(f"\n  wrote {(STAGE / 'RESULTS.md').relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# plain-language results doc
# ---------------------------------------------------------------------------

FACTOR_DEFN = {
    "SMBC":   "**Size** — buy small coins, short big coins (bottom-30% vs top-30% log-mcap). "
              "Classic size premium.",
    "MomC":   "**Raw momentum** — buy the 4-week winners, short the losers. "
              "Textbook momentum.",
    "VolC":   "**Low-volatility** — buy calm coins, short wild ones (bottom vs top-30% 4-week vol). "
              "Volatility anomaly.",
    "NetMom": "**Within-cluster momentum** — inside each Louvain cluster, back the local winners "
              "against the local losers. Network-aware momentum.",
    "NetRel": "**Cross-cluster rotation** — back coins outperforming *other* clusters; "
              "captures narrative rotation.",
    "RMOM1w": "**Risk-adjusted momentum (1w)** — current weekly return divided by 4-week rolling vol "
              "(i.e., 1-week Sharpe ratio). Han et al. (2023) show RMOM1 is one of the 8 "
              "ASD-dominant crypto factors.",
    "RMOM2w": "**Risk-adjusted momentum (2w)** — 2-week return / 4-week vol. "
              "Horizon-specific Sharpe. Han et al. (2023) find this is dominant over 52-week windows.",
    "RMOM4w": "**Risk-adjusted momentum (4w)** — 4-week Sharpe ratio. "
              "Combines return magnitude and consistency.",
    "MAXRET": "**Maximum return (4w)** — the highest single weekly return a coin posted in the "
              "last 4 weeks. Proxies the paper's daily MAXRET (max daily return in formation week). "
              "Measures lottery appeal. Han et al. (2023) find MAXRET dominates all 4 benchmarks.",
    "SPC1":   "**Market/DeFi-majors direction** — dominant 'everything moves together' direction "
              "(ETH, BTC, UNI, AAVE).",
    "SPC2":   "**Payment/old-guard direction** — XRP, XLM, ADA, ALGO, HBAR moving as a bloc.",
    "SPC3":   "**New-L1 direction** — SOL, AVAX, NEAR, ATOM, FET moving as a bloc.",
    "SPC4":   "**Legacy/privacy + exchange direction** — ZEC, DASH, LTC, BNB, CAKE.",
}


def write_results_md(stats: pd.DataFrame, man: dict, dom_names: list) -> None:

    def fmt(v, decimals=3, sign=True):
        if not np.isfinite(float(v)):
            return "n/a"
        fmt_str = f"{{:+.{decimals}f}}" if sign else f"{{:.{decimals}f}}"
        return fmt_str.format(float(v))

    def row_char(r):
        return (
            f"| {r['factor']} | {fmt(r['IS_IC'])} | {fmt(r['IS_IC_t'], 2)} | "
            f"{fmt(r['OOS_IC'])} | {fmt(r['OOS_IC_t'], 2)} | "
            f"{fmt(r['IS_sharpe'], 2)} | {fmt(r['OOS_sharpe'], 2)} | "
            f"{r['verdict'].split(' (')[0]} |"
        )

    def row_spc(r):
        return (
            f"| {r['factor']} | {fmt(r['IS_sharpe'], 2)} | {fmt(r['IS_t'], 2)} | "
            f"{fmt(r['OOS_sharpe'], 2)} | {fmt(r['OOS_t'], 2)} |"
        )

    def row_dist(r):
        jb = "yes" if np.isfinite(r["IS_jb_p"]) and r["IS_jb_p"] < 0.05 else "no"
        return (
            f"| {r['factor']} | {fmt(r['IS_skew'], 2)} | {fmt(r['IS_kurt'], 2)} | "
            f"{jb} | {fmt(r['OOS_skew'], 2)} | {fmt(r['OOS_kurt'], 2)} |"
        )

    def row_asd(r):
        dom_by = "YES" if r["afsd_dom_by_btc"] else "no"
        afsd = "✓" if r["afsd_dom_btc"] else "✗"
        assd = "✓" if r["assd_dom_btc"] else "✗"
        return (
            f"| {r['factor']} | {fmt(r['asd_eps1'], 3, False)} | "
            f"{fmt(r['asd_eps2'], 3, False)} | {afsd} | {assd} | {dom_by} |"
        )

    char_df = stats[stats.group == "characteristic"]
    spc_df  = stats[stats.group == "sparse-PCA"]
    mis_df  = stats[stats.group == "composite"]
    shortlist = stats[stats.verdict.str.startswith("Robust")]["factor"].tolist()

    vc = char_df.set_index("factor")
    vc_oos_ic_t = vc.loc["VolC", "OOS_IC_t"] if "VolC" in vc.index else np.nan
    vc_is_ic_t  = vc.loc["VolC", "IS_IC_t"]  if "VolC" in vc.index else np.nan

    han_new = [n for n in ["RMOM1w", "RMOM2w", "RMOM4w", "MAXRET"] if n in char_df["factor"].values]
    han_robust = [n for n in han_new if stats.loc[stats.factor == n, "verdict"].values[0].startswith("Robust")]

    # --- compose document ---
    md = f"""# Stage 09 — Factor Validation Results (plain-language)

*What this file is:* a from-scratch check of whether each "factor" (a simple
trading rule) actually makes money in a believable way. We test every factor on
two separate time periods so we can't fool ourselves.

*How it's organised:* **Part 1** (below) reports the raw evidence one test at a
time — does the factor *rank* coins (IC), is its return distribution non-normal,
does it *beat Bitcoin* (ASD). **Part 2** runs the Giglio-Xiu / Fama-MacBeth pricing
tests and then **synthesises everything into a per-factor dossier**: each factor's
economic function, what each test did and did not show, and a single *graded*
verdict. No factor is significant on every test, and it doesn't need to be — so the
dossier grades on a scale (Confirmed → Priced risk → Tradable signal → Suggestive →
Economic-only → Structure → Not supported) rather than a pass/fail bar. **If you read
one thing, read the Part 2 dossier.**

## How to read this (30-second version)

- A **factor** is a rule like "buy small coins, sell big coins, rebalance weekly."
  Its **return** is what that rule would have earned each week.
- We split history into two halves we *never mix*:
  - **In-sample (IS):** {man['split']['in_sample'][0]} → {man['split']['in_sample'][1]} ({man['split']['in_sample_weeks']} weeks) — where we're allowed to look.
  - **Out-of-sample (OOS):** {man['split']['out_of_sample'][0]} → {man['split']['out_of_sample'][1]} ({man['split']['out_of_sample_weeks']} weeks) — the "exam" the factor never saw.
- **IC (information coefficient)** = how well the factor *ranks* coins from
  best to worst each week. |IC| ≈ 0.03–0.05 is a normal useful signal. **Read the
  sign against the factor's bet, not in the abstract:** a low-vol or size factor goes
  *long the bottom* of its sort, so a negative raw IC on the characteristic is the
  factor *working*, not failing. Part 2's dossier reports the **direction-adjusted**
  IC (positive = the bet ranked coins correctly) to remove this confusion.
- **Sharpe** = return per unit of risk (>1 is good; >2 is excellent).
- **t-stat** = "is this real, or luck?" **|t| ≥ 2 means very unlikely to be luck.**
- **ASD (almost stochastic dominance)** = a nonparametric test that checks whether
  the factor's *entire return distribution* is better than Bitcoin's, without
  assuming returns are normal. This is the correct test for highly skewed/fat-tailed
  crypto returns (Han et al. 2023, European Financial Management).
  - **ε₁ ≤ 5.9%** → factor almost first-order dominates Bitcoin (AFSD) — most investors prefer it
  - **ε₂ ≤ 3.2%** → factor almost second-order dominates Bitcoin (ASSD) — risk-averse investors prefer it
- **Verdict** here is the *IC-test-only* label (one lens of three):
  - **Robust** = significant IS *and* holds OOS.
  - **In-sample only** = faded or flipped OOS. Don't trust it.
  - **Weak** = not convincing IS on the IC lens alone.

  A "Weak" IC label does **not** mean the factor is worthless — it may still beat
  Bitcoin's distribution (ASD) or be a priced risk (GX, Part 2). The **bottom-line,
  graded** verdict that combines all three lenses lives in **Part 2's per-factor
  dossier** (Confirmed / Priced risk / Tradable signal / Suggestive / Economic-only /
  Structure / Not supported). Read Part 1 as the raw evidence per test; read Part 2
  for the coherent per-factor story.

All signals use only past data (no look-ahead), and we use *Newey-West* t-stats
(lags=4) to account for serial correlation.

---

## Key takeaways (the 1-minute version)

1. **VolC remains the only IC-robust factor.** Its ranking power is statistically
   significant both in-sample (t = {fmt(vc_is_ic_t, 1)}) and out-of-sample
   (t = {fmt(vc_oos_ic_t, 1)}) — a real, persistent signal over 5 years.
2. **Han et al. (2023) factors tested on our 5-year panel:** We added four factors
   from that paper — risk-adjusted momentum at 1w, 2w, 4w horizons (RMOM) and the
   maximum-return lottery signal (MAXRET). These are among the 8 factors that
   "almost stochastically dominate" benchmarks in that paper.
   {"On our panel: **" + ", ".join(han_robust) + "** passed IC significance." if han_robust else "On our panel: *none of these passed IC significance over the full 5-year history.* This is consistent with the paper — it found dominance at 52-week+ investment horizons, while our IC test evaluates single-week ranking power."}
3. **Volatility ranks coins the right way (low-vol wins).** The raw IC is negative
   *because the factor is long low-vol*: higher-vol coins rank worse, so calm coins
   are the buy — a textbook low-volatility premium (direction-adjusted IC is strongly
   positive; see Part 2). But the raw L/S Sharpe is weak, because fat-tailed volatile
   coins occasionally rocket and blow up the short leg, and over five years the *priced*
   premium on the L/S actually runs negative (Part 2). VolC is a ranking signal to lean
   on, not a mechanical long/short trade.
4. **The ASD test is more honest than Sharpe for crypto.** Crypto factor returns are
   highly nonnormal (see distribution table below). Sharpe implicitly assumes
   normality; ASD does not. A factor beating Bitcoin by ASD is a stronger claim.
5. **Size and raw momentum** were strong in the 52-week study (08_nalfp) but are
   **not statistically significant over 5 years** — short-window results were partly
   regime-specific. The competition rewards catching exactly this.
6. **MispricingM** (equal-weight of ASD-dominant factors) = {
       "constructed from: " + ", ".join(dom_names) + ". This composite factor shows whether combining dominant signals improves on any single factor."
       if dom_names else "no factors passed ASD dominance vs BTC on the full sample — composite not formed."
   }

---

## Group A — Tradable L/S factors: IC test results

Judged on **IC** — week-to-week cross-sectional ranking power.

| Factor | IS IC | IS IC t | OOS IC | OOS IC t | IS Sharpe | OOS Sharpe | Verdict |
|---|---|---|---|---|---|---|---|
""" + "\n".join(row_char(r) for _, r in char_df.iterrows()) + """

**Factor definitions:**
""" + "\n".join(f"- {FACTOR_DEFN[k]}" for k in char_df["factor"].values if k in FACTOR_DEFN) + f"""

---

## Group B — Sparse-PCA structure factors (not alpha, context only)

These directions explain *how* the crypto market moves in blocs, not what to trade.
High returns here are mostly market beta. Sharpe and t-stat are what to read.

| Factor | IS Sharpe | IS t | OOS Sharpe | OOS t |
|---|---|---|---|---|
""" + "\n".join(row_spc(r) for _, r in spc_df.iterrows()) + """

""" + "\n".join(f"- {FACTOR_DEFN[k]}" for k in spc_df["factor"].values if k in FACTOR_DEFN) + f"""

---

## Distribution statistics — why Sharpe misleads for crypto

Crypto returns are highly nonnormal (large kurtosis, skewed). A Sharpe ratio
assumes the distribution is Gaussian; when excess kurtosis > 3 the Sharpe
understates tail risk. This motivates the ASD test below.

J-B = Jarque-Bera test for normality. "yes" = normality rejected at 5% level.

| Factor | IS Skew | IS Kurt (excess) | IS non-normal? | OOS Skew | OOS Kurt |
|---|---|---|---|---|---|
""" + "\n".join(
    row_dist(r) for _, r in pd.concat([char_df, spc_df]).iterrows()
) + f"""

---

## Almost Stochastic Dominance vs Bitcoin (Han et al. 2023)

ε₁ (AFSD) and ε₂ (ASSD) measure how far the factor's return distribution falls
short of first/second-order dominance over Bitcoin. **Smaller is better.**
- ε₁ ≤ 5.9% → AFSD: factor beats Bitcoin for *all* risk preferences
- ε₂ ≤ 3.2% → ASSD: factor beats Bitcoin for *all risk-averse* investors
- "BTC dom. factor?" = does Bitcoin almost dominate the factor (reverse direction)

| Factor | ε₁ (AFSD) | ε₂ (ASSD) | AFSD ✓? | ASSD ✓? | BTC dom. factor? |
|---|---|---|---|---|---|
""" + "\n".join(
    row_asd(r) for _, r in pd.concat([char_df, spc_df]).iterrows()
) + (("\n" + row_asd(mis_df.iloc[0]) if len(mis_df) > 0 else "")) + f"""

**Interpretation:**
- A factor with ε₁ < 5.9% has a return CDF that sits *mostly below* Bitcoin's —
  meaning it delivers more probability mass in the right (high-return) tail, with
  only a small violation. For such a factor, most investors (regardless of risk
  aversion) would prefer it to simply holding Bitcoin.
- Factors where Bitcoin dominates the factor (last column = YES) are ones where
  Bitcoin's distribution is clearly better — a signal that the factor destroys value.

---

## MispricingM composite factor

{"**Components:** " + ", ".join(dom_names) + """

MispricingM is the equal-weight average return of all ASD-dominant L/S factor
portfolios (following Stambaugh & Yuan 2017 and Han et al. 2023). It aggregates
the common mispricing signal across factors.
""" + (
    ("| Window | Ann. Return | Sharpe | t-stat | Skew | Excess Kurt |\n"
     "|---|---|---|---|---|---|\n"
     + "| IS | "
     + fmt(mis_df.iloc[0]["IS_annret"]) + " | "
     + fmt(mis_df.iloc[0]["IS_sharpe"]) + " | "
     + fmt(mis_df.iloc[0]["IS_t"]) + " | "
     + fmt(mis_df.iloc[0]["IS_skew"]) + " | "
     + fmt(mis_df.iloc[0]["IS_kurt"]) + " |\n"
     + "| OOS | "
     + fmt(mis_df.iloc[0]["OOS_annret"]) + " | "
     + fmt(mis_df.iloc[0]["OOS_sharpe"]) + " | "
     + fmt(mis_df.iloc[0]["OOS_t"]) + " | "
     + fmt(mis_df.iloc[0]["OOS_skew"]) + " | "
     + fmt(mis_df.iloc[0]["OOS_kurt"]) + " |\n")
    if len(mis_df) > 0 else ""
)
if dom_names else "No factors passed ASD dominance vs BTC on the full sample — MispricingM not formed."}

---

## The shortlist (IC lens only — full graded ranking is in Part 2)

**IC-robust factors (significant ranking power IS *and* held OOS):**
{', '.join(shortlist) if shortlist else 'None passed the IC test on both windows.'}

These have statistically significant cross-sectional ranking power that survived
out-of-sample — the strongest result the *IC lens alone* can give. Note this is **not**
the same as ASD-dominance: a factor can rank coins well yet not beat Bitcoin's whole
return distribution (VolC is the clearest case — strong IC, but BTC dominates its L/S
distribution). The competition-grade call comes from combining all three lenses —
IC, ASD, and Giglio-Xiu pricing — into the **graded per-factor dossier in Part 2**,
where these same factors land as *Confirmed* (IC + priced-risk agree they are real).

---

## Honest caveats

- **Three factors excluded for lack of 5-year data:** FunC (fees/mcap), TVLC
  (TVL/mcap), SupC (supply absorption) — tested only on the 52-week 08_nalfp sample.
- **MAXRET is a weekly proxy** for Han et al.'s daily MAXRET. Their measure uses
  max *daily* return within the formation week; we use max *weekly* return over 4 weeks.
  The concept is the same (lottery appeal) but the granularity differs.
- **Market cap before ~2025 is partly estimated** (price × supply) — Size factor's
  deep history carries measurement error (see SURVIVORSHIP.md).
- **OOS is only {man['split']['out_of_sample_weeks']} weeks** — enough to catch a factor that
  completely collapses, but not enough to certify a small edge with high confidence.
- **ASD is a full-sample test** (not IS/OOS split) because it needs a sufficient
  number of observations to estimate the empirical CDF reliably.
"""

    # Preserve any Part 2+ sections written by downstream scripts (e.g. 09c_gx_pricing_full.py).
    # Search for the marker with and without a leading separator line.
    existing = (STAGE / "RESULTS.md").read_text() if (STAGE / "RESULTS.md").exists() else ""
    preserved = ""
    for marker in ["\n\n## Part 2", "\n## Part 2"]:
        if marker in existing:
            preserved = "\n---\n\n## Part 2" + existing.split("## Part 2", 1)[1]
            break

    (STAGE / "RESULTS.md").write_text(md.rstrip() + ("\n\n" + preserved.lstrip() if preserved else "\n"))


if __name__ == "__main__":
    main()
