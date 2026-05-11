"""06 — Evaluate ranking quality of each model.

For every model in 05_models.py we compute, on the OOS weeks:
    Information Coefficient    — weekly Spearman ρ(prediction, fwd_ret_1w)
    Quintile spread (Q5 - Q1)  — top-minus-bottom weekly return
    Long-short Sharpe          — annualised Sharpe of the Q5-Q1 portfolio
    Turnover                   — fraction of names changing top quintile week-on-week
    Alpha vs market            — intercept of Q5-Q1 returns regressed on equal-weight
                                 universe return

Outputs go to artifacts/tables/ and a couple of plotly figures land in figures/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    DATA_DIR,
    MANIFEST_DIR,
    TABLE_DIR,
    save_plotly,
    write_frame,
    write_json,
)

INPUT_PREDICTIONS = DATA_DIR / "model_predictions.parquet"

QUINTILE_BINS = 5
WEEKS_PER_YEAR = 52
STEM = Path(__file__).stem


def spearman_per_week(df: pd.DataFrame) -> pd.DataFrame:
    """Weekly Spearman correlation of prediction vs realized fwd return."""
    rows = []
    for (model, week), grp in df.groupby(["model", "week"]):
        g = grp.dropna(subset=["prediction", "fwd_ret_1w"])
        if len(g) < 5:
            continue
        rho = g["prediction"].rank().corr(g["fwd_ret_1w"].rank())
        rows.append({"model": model, "week": week, "ic": rho, "n": len(g)})
    return pd.DataFrame(rows)


def assign_quintiles(df: pd.DataFrame) -> pd.DataFrame:
    out_rows = []
    for (model, week), grp in df.groupby(["model", "week"]):
        g = grp.dropna(subset=["prediction"]).copy()
        if len(g) < QUINTILE_BINS:
            continue
        try:
            g["quintile"] = pd.qcut(g["prediction"], QUINTILE_BINS, labels=False, duplicates="drop")
        except ValueError:
            continue
        out_rows.append(g)
    if not out_rows:
        return pd.DataFrame(columns=df.columns.tolist() + ["quintile"])
    return pd.concat(out_rows, ignore_index=True)


def quintile_returns(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.dropna(subset=["quintile", "fwd_ret_1w"])
        .groupby(["model", "week", "quintile"], as_index=False)["fwd_ret_1w"]
        .mean()
    )


def long_short(df_q: pd.DataFrame) -> pd.DataFrame:
    """For each (model, week) compute Q5 - Q1 return."""
    pivot = df_q.pivot_table(index=["model", "week"], columns="quintile", values="fwd_ret_1w")
    if pivot.empty:
        return pd.DataFrame(columns=["model", "week", "ls_ret"])
    top_label = pivot.columns.max()
    bot_label = pivot.columns.min()
    ls = (pivot[top_label] - pivot[bot_label]).rename("ls_ret").reset_index()
    return ls


def turnover_per_model(df_q: pd.DataFrame) -> pd.DataFrame:
    """Top-quintile turnover = |members_t Δ members_{t-1}| / |members_{t-1}|."""
    rows = []
    for model, grp in df_q.groupby("model"):
        top_q = grp["quintile"].max()
        weekly_sets = (
            grp.loc[grp["quintile"].eq(top_q)]
            .groupby("week")["symbol"]
            .apply(set)
            .sort_index()
        )
        prev = None
        for week, members in weekly_sets.items():
            if prev is not None and len(prev) > 0:
                turn = len(members.symmetric_difference(prev)) / (2 * len(prev))
                rows.append({"model": model, "week": week, "turnover": turn})
            prev = members
    return pd.DataFrame(rows)


def market_factors(predictions: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight universe return per week."""
    rel = predictions.drop_duplicates(["week", "symbol"]).copy()
    market = (
        rel.groupby("week", as_index=False)["fwd_ret_1w"]
        .mean()
        .rename(columns={"fwd_ret_1w": "mkt_ret"})
    )
    return market


def alpha_test(ls: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """Regress LS returns on market per model; report alpha and t-stat."""
    rows = []
    for model, grp in ls.groupby("model"):
        merged = grp.merge(factors, on="week", how="left").dropna(subset=["ls_ret"])
        merged = merged.replace([np.inf, -np.inf], np.nan).dropna(subset=["mkt_ret"])
        if len(merged) < 10:
            rows.append({"model": model, "alpha": np.nan, "t_alpha": np.nan, "beta_mkt": np.nan, "n": len(merged)})
            continue
        x = merged[["mkt_ret"]].to_numpy(dtype=float)
        y = merged["ls_ret"].to_numpy(dtype=float)
        x1 = np.hstack([np.ones((x.shape[0], 1)), x])
        beta, residuals, rank, _ = np.linalg.lstsq(x1, y, rcond=None)
        resid = y - x1 @ beta
        dof = max(1, len(y) - x1.shape[1])
        sigma2 = (resid @ resid) / dof
        try:
            cov = sigma2 * np.linalg.inv(x1.T @ x1)
            se_alpha = float(np.sqrt(cov[0, 0]))
        except np.linalg.LinAlgError:
            se_alpha = np.nan
        rows.append(
            {
                "model": model,
                "alpha": float(beta[0]),
                "t_alpha": float(beta[0] / se_alpha) if se_alpha and not np.isnan(se_alpha) else np.nan,
                "beta_mkt": float(beta[1]),
                "n": len(merged),
            }
        )
    return pd.DataFrame(rows)


def summarize_models(ic: pd.DataFrame, ls: pd.DataFrame, turn: pd.DataFrame, alpha: pd.DataFrame) -> pd.DataFrame:
    ic_summary = ic.groupby("model").agg(
        ic_mean=("ic", "mean"),
        ic_std=("ic", "std"),
        ic_n=("ic", "count"),
    )
    ic_summary["ic_ir"] = ic_summary["ic_mean"] / ic_summary["ic_std"].replace(0, np.nan)

    ls_summary = ls.groupby("model").agg(
        ls_mean=("ls_ret", "mean"),
        ls_std=("ls_ret", "std"),
        ls_n=("ls_ret", "count"),
    )
    ls_summary["ls_sharpe_annual"] = (
        ls_summary["ls_mean"] / ls_summary["ls_std"].replace(0, np.nan) * np.sqrt(WEEKS_PER_YEAR)
    )

    turn_summary = (
        turn.groupby("model")["turnover"].mean().rename("turnover_mean").to_frame()
        if not turn.empty
        else pd.DataFrame(columns=["turnover_mean"])
    )

    alpha_summary = alpha.set_index("model") if not alpha.empty else pd.DataFrame()

    summary = ic_summary.join(ls_summary, how="outer").join(turn_summary, how="outer").join(alpha_summary, how="outer")
    return summary.reset_index().sort_values("ic_mean", ascending=False)


def plot_cumulative_ls(ls: pd.DataFrame) -> None:
    if ls.empty:
        return
    ls = ls.sort_values(["model", "week"]).copy()
    ls["cum_ret"] = ls.groupby("model")["ls_ret"].cumsum()
    fig = px.line(
        ls,
        x="week",
        y="cum_ret",
        color="model",
        title="Cumulative long-short (Q5-Q1) weekly log returns by model",
        color_discrete_sequence=px.colors.qualitative.Dark24,
    )
    fig.add_hline(y=0, line_dash="dot", line_color="grey")
    save_plotly(fig, "01_cumulative_long_short", STEM)


def plot_ic_distribution(ic: pd.DataFrame) -> None:
    if ic.empty:
        return
    fig = px.box(
        ic,
        x="model",
        y="ic",
        color="model",
        title="Weekly Spearman IC distribution by model",
        color_discrete_sequence=px.colors.qualitative.Dark24,
    )
    fig.add_hline(y=0, line_dash="dot", line_color="grey")
    save_plotly(fig, "02_ic_distribution", STEM)


def main() -> None:
    pred = pd.read_parquet(INPUT_PREDICTIONS)
    ic = spearman_per_week(pred)
    quint = assign_quintiles(pred)
    q_ret = quintile_returns(quint)
    ls = long_short(q_ret)
    turn = turnover_per_model(quint)
    factors = market_factors(pred)
    alpha = alpha_test(ls, factors)

    summary = summarize_models(ic, ls, turn, alpha)

    write_frame(ic, TABLE_DIR / "weekly_ic")
    write_frame(ls, TABLE_DIR / "long_short_weekly")
    write_frame(turn, TABLE_DIR / "turnover_weekly")
    write_frame(alpha, TABLE_DIR / "alpha_test")
    write_frame(summary, TABLE_DIR / "model_summary")
    write_json(
        {
            "models": summary["model"].tolist(),
            "n_test_weeks": int(ic["week"].nunique()) if not ic.empty else 0,
            "quintile_bins": QUINTILE_BINS,
        },
        MANIFEST_DIR / "06_backtest_manifest.json",
    )

    plot_cumulative_ls(ls)
    plot_ic_distribution(ic)
    print("done.")


if __name__ == "__main__":
    main()
