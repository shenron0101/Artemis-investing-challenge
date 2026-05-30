"""09 — Goal 2 / step 2: Sparse PCA latent factors (interpretable).

Replaces the v3 dense PCA-on-residuals hidden factors (which were unpriced and
uninterpretable) with **Sparse PCA**, whose loadings are mostly zero — so each
latent factor loads on a handful of coins and can be *named*.

Two passes:
  (A) Full-sample on the balanced backbone (interpretation). Standardised weekly
      returns -> SparsePCA -> sparse loadings -> name each factor by its top
      loaders -> adjusted explained variance.
  (B) Rolling 2-year window over the point-in-time universe (the fix for the
      "only 33 coins" limit). At each week we fit on whatever coins are live
      through the trailing window (up to ~45), giving an OOS factor-return series
      and a record of N-per-window.

Outputs
-------
    sparse_pca_loadings.parquet        full-sample backbone loadings (coin x factor)
    sparse_pca_factor_returns.parquet  rolling factor returns + n_coins per week
    figures/sparse_pca_loadings.png
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import SparsePCA

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
DATA_DIR = STAGE / "artifacts" / "data"
FIG_DIR = STAGE / "figures"
MANIFEST_DIR = STAGE / "artifacts" / "manifests"

K = 4                # number of sparse components
ALPHA = 1.2          # sparsity penalty (higher -> fewer nonzero loadings)
ROLL_WIN = 104       # rolling window length (weeks ~ 2y)
MIN_COIN_OBS = 104   # a coin must have full-window data to enter that fit


def standardize(X: pd.DataFrame) -> pd.DataFrame:
    return (X - X.mean()) / X.std(ddof=0).replace(0, np.nan)


def adjusted_evr(Xz: np.ndarray, comps: np.ndarray) -> np.ndarray:
    """Cumulative adjusted explained variance for (non-orthogonal) SPCA comps."""
    sst = np.sum(Xz**2)
    out = []
    for k in range(1, comps.shape[0] + 1):
        W = comps[:k].T                       # features x k loadings
        Z = Xz @ W                            # scores
        B, *_ = np.linalg.lstsq(Z, Xz, rcond=None)
        sse = np.sum((Xz - Z @ B) ** 2)
        out.append(1 - sse / sst)
    return np.array(out)


def sign_normalize(comps: np.ndarray) -> np.ndarray:
    for k in range(comps.shape[0]):
        j = np.argmax(np.abs(comps[k]))
        if comps[k, j] < 0:
            comps[k] *= -1
    return comps


def fit_spca(returns_wide: pd.DataFrame, k: int = K, alpha: float = ALPHA):
    Xz = standardize(returns_wide).dropna(axis=1, how="any")
    Xz = Xz.dropna(axis=0, how="any")
    model = SparsePCA(n_components=k, alpha=alpha, ridge_alpha=0.01,
                      max_iter=300, random_state=0)
    model.fit(Xz.values)
    comps = sign_normalize(model.components_.copy())
    evr = adjusted_evr(Xz.values, comps)
    loadings = pd.DataFrame(comps.T, index=Xz.columns,
                            columns=[f"SPC{i+1}" for i in range(k)])
    return loadings, evr, Xz


def name_factor(load: pd.Series, top: int = 5) -> str:
    nz = load[load.abs() > 1e-6].sort_values(key=np.abs, ascending=False).head(top)
    parts = [f"{s}{'+' if v > 0 else '−'}" for s, v in nz.items()]
    return ", ".join(parts) if len(parts) else "(empty)"


def main() -> None:
    man = json.loads((MANIFEST_DIR / "universe_manifest.json").read_text())
    backbone = man["estimation_backbone"]["symbols"]
    common_start = pd.Timestamp(man["estimation_backbone"]["common_start"])

    rl = pd.read_parquet(DATA_DIR / "returns_weekly.parquet")
    rl["week"] = pd.to_datetime(rl["week"])
    wide = rl.pivot(index="week", columns="symbol", values="ret").sort_index()

    # ---------- (A) full-sample backbone interpretation ----------
    bb = wide.loc[wide.index >= common_start, [c for c in backbone if c in wide.columns]]
    loadings, evr, Xz = fit_spca(bb)
    loadings.to_parquet(DATA_DIR / "sparse_pca_loadings.parquet")

    print(f"  ===== (A) Full-sample Sparse PCA on {Xz.shape[1]} backbone coins, "
          f"{Xz.shape[0]} weeks (K={K}, alpha={ALPHA}) =====")
    print(f"  cumulative adjusted explained variance: "
          f"{', '.join(f'{e*100:.1f}%' for e in evr)}")
    nnz = (loadings.abs() > 1e-6).sum()
    for c in loadings.columns:
        print(f"\n  {c}  ({int(nnz[c])}/{len(loadings)} nonzero loadings)")
        print(f"     top loaders: {name_factor(loadings[c])}")

    # ---------- (B) rolling estimation over the point-in-time universe ----------
    weeks = wide.index
    start_i = ROLL_WIN
    fac_rows = []
    n_coins_log = []
    for i in range(start_i, len(weeks)):
        win = wide.iloc[i - ROLL_WIN:i]                       # trailing window (excl. week i)
        avail = win.columns[win.notna().sum() == ROLL_WIN]    # full-window coins only
        if len(avail) < 10:
            continue
        try:
            load_t, _, _ = fit_spca(win[avail], k=K, alpha=ALPHA)
        except Exception:
            continue
        nxt = wide.iloc[i][avail]                             # week-i realised returns
        valid = nxt.dropna().index
        if len(valid) < 10:
            continue
        # factor return_t = loadings . next-week cross-section (demeaned)
        x = (nxt[valid] - nxt[valid].mean())
        fr = {f"SPC{k+1}": float(load_t.loc[valid, f"SPC{k+1}"] @ x) for k in range(K)}
        fr["week"] = weeks[i]
        fr["n_coins"] = int(len(avail))
        fac_rows.append(fr)
        n_coins_log.append(len(avail))

    fac = pd.DataFrame(fac_rows).set_index("week").sort_index()
    fac.to_parquet(DATA_DIR / "sparse_pca_factor_returns.parquet")
    print(f"\n  ===== (B) Rolling Sparse PCA ({ROLL_WIN}-week window) =====")
    print(f"  {len(fac)} weeks of factor returns; coins per window: "
          f"min={min(n_coins_log)}, median={int(np.median(n_coins_log))}, max={max(n_coins_log)}")
    print(f"  -> rolling uses up to {max(n_coins_log)} coins vs {len(backbone)} in the fixed backbone")

    _plot(loadings)


def _plot(loadings: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    L = loadings.loc[(loadings.abs() > 1e-6).any(axis=1)]
    fig, ax = plt.subplots(figsize=(7, max(5, len(L) * 0.28)))
    im = ax.imshow(L.values, cmap="RdBu_r", vmin=-np.abs(L.values).max(),
                   vmax=np.abs(L.values).max(), aspect="auto")
    ax.set_xticks(range(L.shape[1])); ax.set_xticklabels(L.columns)
    ax.set_yticks(range(len(L))); ax.set_yticklabels(L.index, fontsize=7)
    ax.set_title("Sparse PCA loadings (backbone, full sample)")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / "sparse_pca_loadings.png", dpi=130)
    plt.close(fig)
    print(f"  wrote {(FIG_DIR / 'sparse_pca_loadings.png').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
