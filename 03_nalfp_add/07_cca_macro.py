"""03 — Goal 2 / step 3: CCA between crypto returns and a macro reference basket.

Canonical Correlation Analysis finds the linear combinations of crypto returns
and of the macro basket (BTC, SPX, DXY, UST10Y, VIX) that co-move most strongly.
It answers the economic question Goal 2 poses: *how much of the crypto
cross-section is spanned by traditional macro risk, and how much is
crypto-idiosyncratic?*

We report:
  * canonical correlations rho_1..rho_m (strength of each crypto<->macro link);
  * the macro variate each crypto canonical direction couples to (interpretation);
  * the macro-spanned share of crypto variance two ways:
      - per-coin OLS R^2 on the macro basket (intuitive redundancy);
      - the CCA redundancy index Rd(X|Y).

Outputs
-------
    cca_canonical.parquet     canonical correlations + macro-side weights
    cca_macro_spanned.parquet per-coin macro R^2 (spanned vs idiosyncratic)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cross_decomposition import CCA

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
DATA_DIR = STAGE / "artifacts" / "data"
MANIFEST_DIR = STAGE / "artifacts" / "manifests"


def zscore(df: pd.DataFrame) -> pd.DataFrame:
    return (df - df.mean()) / df.std(ddof=0).replace(0, np.nan)


def main() -> None:
    man = json.loads((MANIFEST_DIR / "universe_manifest.json").read_text())
    backbone = man["estimation_backbone"]["symbols"]
    common_start = pd.Timestamp(man["estimation_backbone"]["common_start"])

    rl = pd.read_parquet(DATA_DIR / "returns_weekly.parquet")
    rl["week"] = pd.to_datetime(rl["week"])
    ref = pd.read_parquet(DATA_DIR / "reference_weekly.parquet")
    # BTC is the crypto market proxy on the reference side; keep it out of the
    # crypto matrix to avoid having the same series on both sides of the CCA.
    crypto_cols = [c for c in backbone if c not in ref.columns]
    crypto = (rl.pivot(index="week", columns="symbol", values="ret")
                .loc[lambda d: d.index >= common_start, crypto_cols]
                .dropna(axis=1, how="any"))

    # align on weeks with complete data on both sides
    df = crypto.join(ref, how="inner").dropna()
    X = df[crypto.columns]
    Y = df[ref.columns]
    Xz, Yz = zscore(X).dropna(axis=1), zscore(Y).dropna(axis=1)
    df2 = Xz.join(Yz, how="inner").dropna()
    Xz, Yz = df2[Xz.columns], df2[Yz.columns]
    print(f"  CCA on {len(df2)} aligned weeks: {Xz.shape[1]} crypto coins vs "
          f"{Yz.shape[1]} macro tickers ({', '.join(Yz.columns)})")

    m = min(Xz.shape[1], Yz.shape[1])
    cca = CCA(n_components=m, max_iter=1000)
    Xc, Yc = cca.fit_transform(Xz.values, Yz.values)
    rhos = [float(np.corrcoef(Xc[:, i], Yc[:, i])[0, 1]) for i in range(m)]

    # macro-side weights per canonical dim -> name which macro driver each couples to
    y_w = pd.DataFrame(cca.y_weights_, index=Yz.columns,
                       columns=[f"CC{i+1}" for i in range(m)])
    rows = []
    for i in range(m):
        top = y_w[f"CC{i+1}"].abs().sort_values(ascending=False)
        drv = ", ".join(f"{k}{'+' if y_w.loc[k, f'CC{i+1}']>0 else '−'}" for k in top.head(3).index)
        rows.append({"component": f"CC{i+1}", "canonical_corr": rhos[i], "macro_drivers": drv})
    canon = pd.DataFrame(rows)
    canon.to_parquet(DATA_DIR / "cca_canonical.parquet", index=False)
    print("\n  ===== canonical correlations (crypto <-> macro) =====")
    for r in rows:
        print(f"   {r['component']}: rho={r['canonical_corr']:+.3f}   driven by {r['macro_drivers']}")

    # ---- macro-spanned share of crypto variance: per-coin OLS R^2 on macro ----
    Ym = Yz.values
    Ym1 = np.column_stack([np.ones(len(Ym)), Ym])
    r2 = {}
    for c in Xz.columns:
        y = Xz[c].values
        beta, *_ = np.linalg.lstsq(Ym1, y, rcond=None)
        sse = np.sum((y - Ym1 @ beta) ** 2)
        r2[c] = 1 - sse / np.sum((y - y.mean()) ** 2)
    r2s = pd.Series(r2).sort_values(ascending=False)
    span = pd.DataFrame({"macro_R2": r2s, "idiosyncratic": 1 - r2s})
    span.to_parquet(DATA_DIR / "cca_macro_spanned.parquet")

    print("\n  ===== macro-spanned vs idiosyncratic (per-coin R^2 on macro basket) =====")
    print(f"  macro-spanned share of crypto variance: median={r2s.median()*100:.1f}%, "
          f"mean={r2s.mean()*100:.1f}%")
    print(f"  most macro-spanned : {', '.join(f'{k} {v*100:.0f}%' for k,v in r2s.head(4).items())}")
    print(f"  most idiosyncratic : {', '.join(f'{k} {v*100:.0f}%' for k,v in r2s.tail(4).items())}")
    print(f"  => ~{(1-r2s.mean())*100:.0f}% of the average coin's variance is crypto-idiosyncratic "
          f"(the alpha space the factor model should target)")


if __name__ == "__main__":
    main()
