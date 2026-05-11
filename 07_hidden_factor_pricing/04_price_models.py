"""04 - Estimate baseline and latent-adjusted pricing models."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, MANIFEST_DIR, TABLE_DIR, write_frame, write_json

PANEL_PATH = DATA_DIR / "weekly_asset_panel.parquet"
FACTOR_PATH = DATA_DIR / "observed_factor_returns.parquet"
OBSERVED_FACTORS = ["crypto_market", "crypto_smb", "crypto_mom", "crypto_tvl_orth"]
N_LATENT = 3


def _ols(y: np.ndarray, x: np.ndarray, *, intercept: bool = True) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(y) & np.isfinite(x).all(axis=1)
    y = y[mask]
    x = x[mask]
    if intercept:
        x = np.column_stack([np.ones(len(x)), x])
    if len(y) <= x.shape[1]:
        return np.full(x.shape[1], np.nan), mask
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    return beta, mask


def _normal_pvalue(t_stat: float) -> float:
    if not np.isfinite(t_stat):
        return float("nan")
    return float(math.erfc(abs(t_stat) / math.sqrt(2.0)))


def build_return_matrix(panel: pd.DataFrame) -> pd.DataFrame:
    return panel.pivot_table(index="week", columns="symbol", values="ret_1w", aggfunc="last").sort_index()


def estimate_time_series_betas(returns: pd.DataFrame, factors: pd.DataFrame, factor_cols: list[str], *, prefix: str) -> pd.DataFrame:
    fac = factors.set_index("week")[factor_cols].sort_index()
    rows = []
    for symbol in returns.columns:
        joined = pd.concat([returns[symbol].rename("ret"), fac], axis=1).dropna()
        if len(joined) < max(12, len(factor_cols) + 8):
            continue
        beta, _ = _ols(joined["ret"].to_numpy(), joined[factor_cols].to_numpy(), intercept=True)
        if np.isnan(beta).any():
            continue
        row = {"symbol": symbol, f"{prefix}_alpha": beta[0], f"{prefix}_n_obs": int(len(joined))}
        row.update({f"{prefix}_beta_{name}": beta[i + 1] for i, name in enumerate(factor_cols)})
        rows.append(row)
    return pd.DataFrame(rows)


def extract_latent_factors(returns: pd.DataFrame, n_latent: int = N_LATENT) -> pd.DataFrame:
    min_obs = max(16, int(len(returns) * 0.40))
    wide = returns.dropna(axis=1, thresh=min_obs).copy()
    demeaned = wide - wide.mean(axis=0)
    filled = demeaned.fillna(0.0)
    max_k = min(n_latent, filled.shape[0] - 1, filled.shape[1] - 1)
    if max_k < 1:
        return pd.DataFrame({"week": returns.index})
    u, s, _ = np.linalg.svd(filled.to_numpy(), full_matrices=False)
    scores = u[:, :max_k] * s[:max_k]
    out = pd.DataFrame(scores, index=filled.index, columns=[f"latent_{i}" for i in range(1, max_k + 1)])
    return out.reset_index().rename(columns={"index": "week"})


def _cross_sectional_gammas(returns: pd.DataFrame, exposures: pd.DataFrame, exposure_cols: list[str]) -> pd.DataFrame:
    exp = exposures.set_index("symbol")[exposure_cols]
    rows = []
    for week, ret_row in returns.iterrows():
        y = ret_row.rename("ret").dropna()
        common = y.index.intersection(exp.index)
        if len(common) < len(exposure_cols) + 6:
            continue
        x = exp.loc[common]
        valid = x.notna().all(axis=1)
        common = common[valid.to_numpy()]
        if len(common) < len(exposure_cols) + 6:
            continue
        beta, _ = _ols(y.loc[common].to_numpy(), exp.loc[common].to_numpy(), intercept=True)
        if np.isnan(beta).any():
            continue
        row = {"week": week, "intercept": beta[0], "n_assets": int(len(common))}
        row.update({col: beta[i + 1] for i, col in enumerate(exposure_cols)})
        rows.append(row)
    return pd.DataFrame(rows).sort_values("week")


def summarize_gammas(gammas: pd.DataFrame, exposure_cols: list[str], model: str) -> pd.DataFrame:
    rows = []
    for col in exposure_cols:
        s = gammas[col].dropna()
        if len(s) == 0:
            mean = se = t_stat = p_value = float("nan")
        else:
            mean = float(s.mean())
            se = float(s.std(ddof=1) / math.sqrt(len(s))) if len(s) > 1 else float("nan")
            t_stat = mean / se if se and np.isfinite(se) and se > 0 else float("nan")
            p_value = _normal_pvalue(t_stat)
        factor_name = col.split("_beta_", 1)[-1]
        rows.append(
            {
                "model": model,
                "factor": factor_name,
                "exposure_column": col,
                "lambda_weekly": mean,
                "lambda_annualized_linear": mean * 52 if np.isfinite(mean) else float("nan"),
                "std_error": se,
                "t_stat": t_stat,
                "p_value_normal": p_value,
                "n_weeks": int(len(s)),
                "avg_assets_per_week": float(gammas["n_assets"].mean()) if "n_assets" in gammas else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def build_survival_table(premia: pd.DataFrame) -> pd.DataFrame:
    base = premia.loc[premia["model"].eq("fama_macbeth")].set_index("factor")
    adj = premia.loc[premia["model"].eq("latent_adjusted")].set_index("factor")
    common = [f for f in base.index.intersection(adj.index) if not f.startswith("latent_")]
    rows = []
    for factor in common:
        b = base.loc[factor]
        a = adj.loc[factor]
        same_sign = np.sign(b["lambda_weekly"]) == np.sign(a["lambda_weekly"])
        survives = bool(same_sign and abs(a["t_stat"]) >= 1.65)
        rows.append(
            {
                "factor": factor,
                "fmb_lambda_weekly": b["lambda_weekly"],
                "fmb_t_stat": b["t_stat"],
                "latent_adjusted_lambda_weekly": a["lambda_weekly"],
                "latent_adjusted_t_stat": a["t_stat"],
                "lambda_delta": a["lambda_weekly"] - b["lambda_weekly"],
                "same_sign": bool(same_sign),
                "survives_latent_controls_10pct_rule": survives,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"Run 01_build_panel.py first: missing {PANEL_PATH}")
    if not FACTOR_PATH.exists():
        raise FileNotFoundError(f"Run 02_observed_factors.py first: missing {FACTOR_PATH}")
    panel = pd.read_parquet(PANEL_PATH)
    factors = pd.read_parquet(FACTOR_PATH)
    factor_cols = [col for col in OBSERVED_FACTORS if col in factors.columns and factors[col].notna().sum() >= 12]
    if len(factor_cols) < 2:
        raise ValueError(f"Need at least two usable observed factors, got {factor_cols}")

    returns = build_return_matrix(panel)
    observed_betas = estimate_time_series_betas(returns, factors, factor_cols, prefix="observed")
    observed_exposure_cols = [f"observed_beta_{col}" for col in factor_cols]
    gammas_fmb = _cross_sectional_gammas(returns, observed_betas, observed_exposure_cols)
    premia_fmb = summarize_gammas(gammas_fmb, observed_exposure_cols, "fama_macbeth")

    latent = extract_latent_factors(returns, N_LATENT)
    latent_cols = [col for col in latent.columns if col.startswith("latent_")]
    latent_betas = estimate_time_series_betas(returns, latent, latent_cols, prefix="latent") if latent_cols else pd.DataFrame()
    if not latent_betas.empty:
        exposures = observed_betas.merge(latent_betas, on="symbol", how="inner")
    else:
        exposures = observed_betas.copy()
    latent_exposure_cols = [f"latent_beta_{col}" for col in latent_cols]
    adjusted_cols = observed_exposure_cols + latent_exposure_cols
    gammas_adjusted = _cross_sectional_gammas(returns, exposures, adjusted_cols)
    premia_adjusted = summarize_gammas(gammas_adjusted, adjusted_cols, "latent_adjusted")

    premia = pd.concat([premia_fmb, premia_adjusted], ignore_index=True)
    survival = build_survival_table(premia)
    gamma_out = pd.concat(
        [
            gammas_fmb.assign(model="fama_macbeth"),
            gammas_adjusted.assign(model="latent_adjusted"),
        ],
        ignore_index=True,
        sort=False,
    )

    write_frame(observed_betas, TABLE_DIR / "04_observed_asset_betas")
    if not latent_betas.empty:
        write_frame(latent_betas, TABLE_DIR / "04_latent_asset_betas")
    write_frame(latent, DATA_DIR / "latent_factor_returns")
    write_frame(gamma_out, TABLE_DIR / "04_weekly_cross_sectional_gammas")
    write_frame(premia, TABLE_DIR / "04_factor_premia")
    write_frame(survival, TABLE_DIR / "04_factor_survival")
    write_json(
        {
            "observed_factor_columns": factor_cols,
            "latent_factor_columns": latent_cols,
            "symbols_with_observed_betas": int(len(observed_betas)),
            "symbols_with_latent_betas": int(len(latent_betas)) if not latent_betas.empty else 0,
            "fmb_weeks": int(len(gammas_fmb)),
            "latent_adjusted_weeks": int(len(gammas_adjusted)),
            "method_note": "Fama-MacBeth two-pass estimates are compared with a PCA latent-control extension. This is a transparent repo-native approximation, not a full Giglio-Xiu three-pass/bootstrap implementation.",
        },
        MANIFEST_DIR / "04_price_models_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
