"""05 — Trading simulation for model direction signals."""
# %% Imports
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MANIFEST_DIR, TABLE_DIR, save_plotly, write_frame, write_json

PRED_PATH = TABLE_DIR / "04_predictions.parquet"
TRAIN_EVAL_PATH = MANIFEST_DIR / "04_train_eval_manifest.json"
FEE_BPS = 10.0


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float((equity / peak - 1.0).min())


def _performance(date: pd.Series, returns: pd.Series, equity: pd.Series, position: pd.Series) -> dict[str, float]:
    clean = returns.dropna()
    n = len(clean)
    if n == 0:
        return {}
    days = max((pd.to_datetime(date).max() - pd.to_datetime(date).min()).days, 1)
    ending = float(equity.iloc[-1])
    ann_return = ending ** (365.0 / days) - 1.0 if ending > 0 else -1.0
    ann_vol = float(clean.std() * np.sqrt(365)) if n > 1 else float("nan")
    sharpe = float(clean.mean() / clean.std() * np.sqrt(365)) if n > 1 and clean.std() > 0 else float("nan")
    return {
        "observations": int(n),
        "total_return": ending - 1.0,
        "annualized_return": ann_return,
        "annualized_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": _max_drawdown(equity),
        "mean_daily_return": float(clean.mean()),
        "hit_rate": float((clean > 0).mean()),
        "avg_abs_position": float(position.abs().mean()),
        "avg_daily_turnover": float(position.diff().abs().fillna(position.abs()).mean()),
    }


def simulate_signal(rows: pd.DataFrame, *, mode: str, fee_bps: float) -> pd.DataFrame:
    out = rows.sort_values("date").copy()
    if mode == "long_short":
        out["position"] = np.where(out["y_pred"].astype(int).eq(1), 1.0, -1.0)
    elif mode == "long_flat":
        out["position"] = np.where(out["y_pred"].astype(int).eq(1), 1.0, 0.0)
    else:
        raise ValueError(f"Unknown mode: {mode}")
    out["turnover"] = out["position"].diff().abs().fillna(out["position"].abs())
    out["cost"] = out["turnover"] * fee_bps / 10_000.0
    out["strategy_return"] = out["position"] * out["target_return_1d_simple"] - out["cost"]
    out["equity"] = (1.0 + out["strategy_return"]).cumprod()
    out["mode"] = mode
    return out


def main() -> None:
    if not PRED_PATH.exists():
        raise FileNotFoundError(f"Run 04_train_eval.py first: missing {PRED_PATH}")
    preds = pd.read_parquet(PRED_PATH)
    test = preds.loc[preds["split"].eq("test")].copy()
    if test.empty:
        raise ValueError("No test predictions found.")

    simulations: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    for model_id, rows in test.groupby("model_id", sort=False):
        for mode in ("long_short", "long_flat"):
            sim = simulate_signal(rows, mode=mode, fee_bps=FEE_BPS)
            simulations.append(sim)
            summary_rows.append({"model_id": model_id, "mode": mode, **_performance(sim["date"], sim["strategy_return"], sim["equity"], sim["position"])})

    benchmark = test.drop_duplicates("date").sort_values("date").copy()
    benchmark["position"] = 1.0
    benchmark["turnover"] = 0.0
    benchmark["cost"] = 0.0
    benchmark["strategy_return"] = benchmark["target_return_1d_simple"]
    benchmark["equity"] = (1.0 + benchmark["strategy_return"]).cumprod()
    benchmark["mode"] = "buy_hold"
    benchmark["model_id"] = "benchmark__buy_hold"
    simulations.append(benchmark)
    summary_rows.append(
        {"model_id": "benchmark__buy_hold", "mode": "buy_hold", **_performance(benchmark["date"], benchmark["strategy_return"], benchmark["equity"], benchmark["position"])}
    )

    equity = pd.concat(simulations, ignore_index=True)
    summary = pd.DataFrame(summary_rows).sort_values(["sharpe", "annualized_return"], ascending=False)
    write_frame(equity, TABLE_DIR / "05_equity_curves")
    write_frame(summary, TABLE_DIR / "05_trading_summary")

    top_ids = summary.loc[~summary["model_id"].eq("benchmark__buy_hold")].head(5)[["model_id", "mode"]]
    plot_keys = {tuple(row) for row in top_ids.to_numpy()}
    plot = equity.loc[
        equity.apply(lambda r: (r["model_id"], r["mode"]) in plot_keys or r["model_id"] == "benchmark__buy_hold", axis=1)
    ].copy()
    plot["strategy"] = plot["model_id"] + " / " + plot["mode"]
    fig = px.line(
        plot,
        x="date",
        y="equity",
        color="strategy",
        title="BTC next-day direction trading simulation — test period",
        labels={"equity": "equity multiple"},
    )
    save_plotly(fig, "01_test_equity_curves", Path(__file__).stem)

    champion = None
    if TRAIN_EVAL_PATH.exists():
        champion = json.loads(TRAIN_EVAL_PATH.read_text(encoding="utf-8")).get("champion_by_validation_balanced_accuracy")
    write_json(
        {
            "fee_bps_per_unit_turnover": FEE_BPS,
            "execution_assumption": "Signals are formed at close t and earn close-to-close return t to t+1.",
            "champion_classifier_from_validation": champion,
            "best_test_strategy": summary.iloc[0].to_dict(),
        },
        MANIFEST_DIR / "05_trading_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
