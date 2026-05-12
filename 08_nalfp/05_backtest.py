"""05 — Walk-forward backtest of the NALFP weekly portfolio.

PnL accounting (weekly close-to-close, simple compounding):
    r_p(t+1) = Σ_i w_i(t) * r_i(t+1)

We compute three views:
 1) full sample (in-sample + OOS) — diagnostic only
 2) train sample (first TRAIN_WEEKS) — sanity check
 3) OOS sample — the headline number for the report

Costs. Crypto venues charge ~5 bps per trade; we model a one-sided cost of
10 bps applied to weekly turnover (= 0.5 * Σ |Δw|). This is intentionally
conservative for the size of this strategy (the median name has 30d ADV
> $1M so 10 bps slippage is fair).

Benchmarks. We compare against three alternatives that already exist in the
project:
    raam_v2  — equal-weight long-only ranking of the RAAM v2 composite
    plus_lat — Fama-MacBeth predictions from 06 (existing artifact)
    ew_long  — equal-weight top quintile by 4-week momentum (cheap baseline)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    DATA_DIR,
    MANIFEST_DIR,
    TRAIN_WEEKS,
    UPSTREAM_06,
    cs_zscore,
    load_characteristics,
    save_plotly,
    write_frame,
    write_json,
)

COST_BPS_ONE_SIDED = 10.0  # 10bps = 0.10% per leg of turnover
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_BLOCK_LEN = 4  # weeks — stationary block bootstrap for weekly returns


def sharpe_bootstrap_ci(net_returns: np.ndarray, n_draws: int = BOOTSTRAP_DRAWS,
                       block_len: int = BOOTSTRAP_BLOCK_LEN, ci: float = 0.95):
    """Stationary (overlapping) block bootstrap on weekly net returns.

    Returns (sharpe_mean, lo, hi) — annualised Sharpe with [lo, hi] symmetric CI.
    Handles n<block_len by falling back to iid resampling."""
    n = len(net_returns)
    if n < 4:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(0)
    sharpes = np.empty(n_draws)
    blocks = max(int(np.ceil(n / block_len)), 1)
    for k in range(n_draws):
        if n <= block_len:
            sample = rng.choice(net_returns, size=n, replace=True)
        else:
            starts = rng.integers(0, n - block_len + 1, size=blocks)
            sample = np.concatenate([net_returns[s:s + block_len] for s in starts])[:n]
        mu = sample.mean()
        sd = sample.std(ddof=1)
        sharpes[k] = (mu / sd * np.sqrt(52)) if sd > 0 else np.nan
    sharpes = sharpes[~np.isnan(sharpes)]
    alpha = (1 - ci) / 2
    lo, hi = np.quantile(sharpes, [alpha, 1 - alpha])
    return float(sharpes.mean()), float(lo), float(hi)


def load_returns_panel() -> pd.DataFrame:
    char = load_characteristics()
    # next-week realised return (already on the frame)
    return char[["week", "symbol", "fwd_ret_1w", "ret_1w", "mom_4w"]].copy()


def _turnover_series(w_long: pd.DataFrame) -> pd.Series:
    """0.5 * Σ |Δw| per week."""
    pivot = w_long.pivot(index="week", columns="symbol", values="w").fillna(0.0)
    delta = pivot.diff().abs().sum(axis=1) * 0.5
    delta.iloc[0] = 0.5 * pivot.iloc[0].abs().sum()
    return delta


def backtest_strategy(weights: pd.DataFrame, ret_panel: pd.DataFrame, name: str) -> pd.DataFrame:
    """Returns weekly P&L of a strategy.

    weights: long frame with cols [week, symbol, w]
    ret_panel: cols [week, symbol, fwd_ret_1w]"""
    df = weights.merge(ret_panel, on=["week", "symbol"], how="left")
    df["pnl_gross"] = df["w"] * df["fwd_ret_1w"]
    weekly = df.groupby("week").agg(
        pnl_gross=("pnl_gross", "sum"),
        gross_exposure=("w", lambda x: x.abs().sum()),
    ).reset_index()
    turnover = _turnover_series(weights[["week", "symbol", "w"]])
    weekly = weekly.merge(turnover.rename("turnover").reset_index(), on="week", how="left")
    weekly["cost"] = weekly["turnover"] * (COST_BPS_ONE_SIDED / 10000.0)
    weekly["pnl_net"] = weekly["pnl_gross"] - weekly["cost"]
    weekly["strategy"] = name
    return weekly


def metrics(weekly: pd.DataFrame, label: str, in_sample_cut: pd.Timestamp) -> dict:
    """Annualised metrics. We treat one weekly observation as 1/52 of a year."""
    out = {}
    for tag, mask in [("full", slice(None)), ("train", weekly["week"] < in_sample_cut),
                      ("oos", weekly["week"] >= in_sample_cut)]:
        sub = weekly.loc[mask] if isinstance(mask, pd.Series) else weekly.copy()
        if len(sub) == 0:
            continue
        net = sub["pnl_net"].values
        ann_ret = np.mean(net) * 52
        ann_vol = np.std(net, ddof=1) * np.sqrt(52) if len(net) > 1 else np.nan
        sharpe = ann_ret / ann_vol if ann_vol and ann_vol > 0 else np.nan
        cum = (1.0 + pd.Series(net)).cumprod()
        peak = cum.cummax()
        dd = (cum / peak - 1.0)
        out[tag] = {
            "weeks": int(len(net)),
            "ann_return": float(ann_ret),
            "ann_vol": float(ann_vol) if ann_vol else None,
            "sharpe": float(sharpe) if sharpe and not np.isnan(sharpe) else None,
            "max_dd": float(dd.min()) if len(dd) else None,
            "avg_turnover": float(sub["turnover"].mean()),
            "hit_rate": float((net > 0).mean()),
        }
    out["strategy"] = label
    return out


# --------------------------------------------------------------------------- #
# Benchmarks
# --------------------------------------------------------------------------- #


def build_ew_momentum(ret_panel: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight long-only top quintile by 4-week momentum."""
    weeks = sorted(ret_panel["week"].dropna().unique())
    rows: list[pd.DataFrame] = []
    for wk in weeks:
        block = ret_panel[(ret_panel["week"] == wk) & ret_panel["mom_4w"].notna()].copy()
        if len(block) < 10:
            continue
        block["rank"] = block["mom_4w"].rank()
        n_long = max(int(round(len(block) * 0.20)), 5)
        block["side"] = 0
        block.loc[block["rank"] > len(block) - n_long, "side"] = 1
        block = block[block["side"] == 1].copy()
        block["w"] = 1.0 / len(block)
        rows.append(block[["week", "symbol", "w"]])
    return pd.concat(rows, ignore_index=True)


def build_raam_v2() -> pd.DataFrame | None:
    """Try to read the RAAM v2 composite ranks from stage 04 artifacts.

    Falls back to None if unavailable, in which case we skip the benchmark."""
    path = Path(__file__).resolve().parents[1] / "04_factors" / "figures"
    candidate = path.parent / "RAAM_v2_composite.parquet"
    if candidate.exists():
        return pd.read_parquet(candidate)
    return None


def build_plus_lat() -> pd.DataFrame | None:
    """Stage-06 plus_lat predictions (top quintile long, bottom quintile short)."""
    path = UPSTREAM_06 / "model_predictions.parquet"
    if not path.exists():
        return None
    preds = pd.read_parquet(path)
    if "model" in preds.columns:
        preds = preds[preds["model"] == "plus_lat"].copy()
        target_col = "prediction"
    else:
        cols = preds.columns.tolist()
        target_col = None
        for cand in ["plus_lat", "fm_plus_lat", "fm_plus_latent", "y_hat", "yhat", "pred"]:
            if cand in cols:
                target_col = cand
                break
        if target_col is None:
            return None
    preds["week"] = pd.to_datetime(preds["week"])
    weeks = sorted(preds["week"].unique())
    rows: list[pd.DataFrame] = []
    for wk in weeks:
        block = preds[(preds["week"] == wk) & preds[target_col].notna()].copy()
        if len(block) < 10:
            continue
        block["rank"] = block[target_col].rank()
        n_long = max(int(round(len(block) * 0.20)), 5)
        n_short = n_long
        block["w"] = 0.0
        block.loc[block["rank"] > len(block) - n_long, "w"] = 1.0 / n_long
        block.loc[block["rank"] <= n_short, "w"] = -1.0 / n_short
        rows.append(block[["week", "symbol", "w"]])
    return pd.concat(rows, ignore_index=True)


# --------------------------------------------------------------------------- #
# Attribution: long-leg pnl, short-leg pnl, network vs ipca contribution
# --------------------------------------------------------------------------- #


def attribution(weights: pd.DataFrame, ret_panel: pd.DataFrame, blended: pd.DataFrame) -> pd.DataFrame:
    df = weights.merge(ret_panel[["week", "symbol", "fwd_ret_1w"]], on=["week", "symbol"], how="left")
    long_pnl = df[df["w"] > 0].groupby("week").apply(lambda x: (x["w"] * x["fwd_ret_1w"]).sum())
    short_pnl = df[df["w"] < 0].groupby("week").apply(lambda x: (x["w"] * x["fwd_ret_1w"]).sum())

    # Standalone stream attribution: supported when blended contains per-stream
    # z-score columns. In v3 (IC-weighted combination) those columns are absent
    # — skip gracefully and return long/short split only.
    has_stream_cols = "E_net_z" in blended.columns and "E_gx_z" in blended.columns
    standalone = pd.DataFrame()
    if has_stream_cols:
        bl = blended.copy()
        weeks = sorted(weights["week"].unique())
        rows: list[dict] = []
        for wk in weeks:
            block = bl[bl["week"] == wk].copy()
            actual_w = weights[weights["week"] == wk].set_index("symbol")["w"]
            if block.empty or actual_w.empty:
                continue
            ranks_net = block.set_index("symbol")["E_net_z"].rank()
            ranks_gx = block.set_index("symbol")["E_gx_z"].rank()
            rets = ret_panel[ret_panel["week"] == wk].set_index("symbol")["fwd_ret_1w"]
            if ranks_net.empty or ranks_gx.empty:
                continue
            n = len(ranks_net)
            n_long = max(int(round(n * 0.20)), 5)
            def _ls_pnl(rk: pd.Series) -> float:
                longs = rk[rk > n - n_long].index
                shorts = rk[rk <= n_long].index
                r_long = rets.reindex(longs).mean()
                r_short = rets.reindex(shorts).mean()
                return float((r_long if pd.notna(r_long) else 0) - (r_short if pd.notna(r_short) else 0))
            rows.append({
                "week": wk,
                "pnl_net_only": _ls_pnl(ranks_net),
                "pnl_gx_only": _ls_pnl(ranks_gx),
            })
        standalone = pd.DataFrame(rows)
    base = pd.DataFrame({
        "week": long_pnl.index,
        "pnl_long": long_pnl.values,
    }).merge(short_pnl.rename("pnl_short").reset_index(), on="week", how="left")
    if not standalone.empty:
        return base.merge(standalone, on="week", how="left")
    return base


def _figures(strategies: dict[str, pd.DataFrame], in_sample_cut: pd.Timestamp) -> None:
    import plotly.graph_objects as go

    fig = go.Figure()
    for name, weekly in strategies.items():
        cum = (1.0 + weekly["pnl_net"]).cumprod() - 1.0
        fig.add_trace(go.Scatter(x=weekly["week"], y=cum, mode="lines", name=name))
    cut_str = pd.Timestamp(in_sample_cut).isoformat()
    fig.add_shape(type="line", x0=cut_str, x1=cut_str, y0=0, y1=1,
                  yref="paper", line=dict(color="#777", dash="dash"))
    fig.add_annotation(x=cut_str, y=1.0, yref="paper",
                       text="train | OOS", showarrow=False, yshift=10)
    fig.update_layout(title="Cumulative net P&L — NALFP vs benchmarks", yaxis_title="cumulative return",
                      height=560)
    save_plotly(fig, "cumulative_pnl", "05_backtest")


def main() -> None:
    weights = pd.read_parquet(DATA_DIR / "weekly_weights.parquet")
    blended = pd.read_parquet(DATA_DIR / "blended_signals.parquet")
    ret_panel = load_returns_panel()

    weeks = sorted(weights["week"].unique())
    in_sample_cut = pd.Timestamp(weeks[TRAIN_WEEKS]) if len(weeks) > TRAIN_WEEKS else pd.Timestamp(weeks[-1])

    nalfp_weekly = backtest_strategy(weights[["week", "symbol", "w"]], ret_panel, "NALFP")

    # Ablation: NALFP without the cluster diversification cap
    nalfp_uncapped = None
    nocap_path = DATA_DIR / "weekly_weights_no_cluster_cap.parquet"
    if nocap_path.exists():
        nc = pd.read_parquet(nocap_path)
        nalfp_uncapped = backtest_strategy(nc[["week", "symbol", "w"]], ret_panel, "NALFP_no_cluster_cap")

    ew_w = build_ew_momentum(ret_panel)
    ew_weekly = backtest_strategy(ew_w, ret_panel, "EW_mom_long")

    raam = build_raam_v2()
    plus = build_plus_lat()

    strategies = {"NALFP": nalfp_weekly, "EW_mom_long": ew_weekly}
    if nalfp_uncapped is not None:
        strategies["NALFP_no_cluster_cap"] = nalfp_uncapped
    if raam is not None and {"week", "symbol", "w"}.issubset(raam.columns):
        strategies["RAAM_v2"] = backtest_strategy(raam[["week", "symbol", "w"]], ret_panel, "RAAM_v2")
    if plus is not None:
        strategies["plus_lat"] = backtest_strategy(plus, ret_panel, "plus_lat")

    metric_rows = []
    for name, weekly in strategies.items():
        m = metrics(weekly, name, in_sample_cut)
        oos = weekly.loc[weekly["week"] >= in_sample_cut, "pnl_net"].values
        if len(oos) >= 4:
            s_mean, s_lo, s_hi = sharpe_bootstrap_ci(oos)
            m["oos"]["sharpe_boot_mean"] = s_mean
            m["oos"]["sharpe_boot_lo95"] = s_lo
            m["oos"]["sharpe_boot_hi95"] = s_hi
        metric_rows.append(m)
    write_json(metric_rows, MANIFEST_DIR / "05_metrics.json")

    # Save weekly pnl per strategy
    all_weekly = pd.concat(strategies.values(), ignore_index=True)
    write_frame(all_weekly, DATA_DIR / "weekly_pnl")

    # Attribution
    attr = attribution(weights[["week", "symbol", "w"]], ret_panel, blended)
    write_frame(attr, DATA_DIR / "weekly_attribution")

    _figures(strategies, in_sample_cut)
    print("done.")


if __name__ == "__main__":
    main()
