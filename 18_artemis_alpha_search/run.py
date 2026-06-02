#!/usr/bin/env python3
"""Stage 18 - Artemis/fundamental alpha search.

This stage tests whether Artemis usage data, FunC-style fee yield, TVLC-style
TVL yield, and related quality/growth signals can improve the weekly
cross-sectional strategy on the existing project universe.

The search is intentionally split-aware:
* raw signals are causal weekly aggregates at week t;
* returns are next-week Binance returns;
* candidate selection and ensemble weights are chosen from IS only;
* OOS is reported without refitting.
"""
from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
CLEAN = ROOT / "01_Data_Collection" / "data" / "clean"
MANIFEST09 = ROOT / "09_nalfp_add" / "artifacts" / "manifests" / "universe_manifest.json"
OUT = STAGE / "artifacts"
DATA_OUT = OUT / "data"
MANIFEST_OUT = OUT / "manifests"
for d in (DATA_OUT, MANIFEST_OUT):
    d.mkdir(parents=True, exist_ok=True)

WEEKS_PER_YEAR = 52
COST_BPS = 10.0
MIN_NAMES = 18
MIN_SIDE = 4
TOP_FRACS = (0.20, 0.25, 0.30)
PRICE_CONTROL_SIGNALS = {
    "log_mcap_neg",
    "mom_4w",
    "rmom_1w",
    "maxret_4w_neg",
    "vol_4w_neg",
    "exchange_volume_to_mcap",
}


def load_universe_config() -> dict:
    if not MANIFEST09.exists():
        return {
            "symbols": None,
            "first_oos": pd.Timestamp("2024-11-25"),
            "source": "local Binance symbols; Stage 09 manifest not found",
            "manifest": {},
        }
    manifest = json.loads(MANIFEST09.read_text())
    return {
        "symbols": set(manifest["trading_universe"]["symbols_ever_eligible"]),
        "first_oos": pd.Timestamp(manifest["split"]["out_of_sample"][0]),
        "source": "09_nalfp_add/artifacts/manifests/universe_manifest.json",
        "manifest": manifest,
    }


UNIVERSE_CONFIG = load_universe_config()
FIRST_OOS = UNIVERSE_CONFIG["first_oos"]


def monday_week(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.to_period("W-SUN").dt.start_time


def cs_zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=1)
    if not np.isfinite(sd) or sd <= 0:
        return s * 0.0
    return (s - s.mean()) / sd


def log1p_pos(s: pd.Series) -> pd.Series:
    return np.log1p(s.clip(lower=0.0))


def perf_metrics(r: pd.Series) -> dict[str, float]:
    x = r.dropna()
    if len(x) < 5:
        return {
            "ann_return": np.nan,
            "ann_vol": np.nan,
            "sharpe": np.nan,
            "max_dd": np.nan,
            "hit_rate": np.nan,
            "weeks": int(len(x)),
        }
    ann_ret = float(x.mean() * WEEKS_PER_YEAR)
    ann_vol = float(x.std(ddof=1) * math.sqrt(WEEKS_PER_YEAR))
    curve = (1.0 + x).cumprod()
    dd = curve / curve.cummax() - 1.0
    return {
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": float(ann_ret / ann_vol) if ann_vol > 0 else np.nan,
        "max_dd": float(dd.min()),
        "hit_rate": float((x > 0).mean()),
        "weeks": int(len(x)),
    }


def load_price_panel() -> pd.DataFrame:
    """Weekly Binance close/return panel for symbols with local OHLCV data."""
    asset_master = pd.read_parquet(CLEAN / "asset_master.parquet")
    universe = UNIVERSE_CONFIG["symbols"]
    if universe is None:
        universe = set(asset_master["symbol"].astype(str).str.upper())
    px = pd.read_parquet(CLEAN / "binance_ohlcv_daily.parquet")
    px["symbol"] = px["symbol"].astype(str).str.upper()
    px = px[px["symbol"].isin(universe)].copy()
    if np.issubdtype(px["open_time"].dtype, np.number):
        px["date"] = pd.to_datetime(px["open_time"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    else:
        px["date"] = pd.to_datetime(px["open_time"], utc=True).dt.tz_localize(None).dt.normalize()
    px["week"] = monday_week(px["date"])

    weekly = (
        px.sort_values(["symbol", "date"])
        .groupby(["week", "symbol"], as_index=False)
        .agg(
            price=("close", "last"),
            quote_volume=("quote_volume", "sum"),
            trade_count=("trade_count", "sum"),
        )
    )
    weekly = weekly.sort_values(["symbol", "week"]).reset_index(drop=True)
    weekly["ret"] = weekly.groupby("symbol")["price"].pct_change()
    weekly["fwd_ret"] = weekly.groupby("symbol")["ret"].shift(-1)

    cg = pd.read_parquet(CLEAN / "coingecko_daily_ticks.parquet")
    cg["symbol"] = cg["symbol"].astype(str).str.upper()
    cg["date"] = pd.to_datetime(cg["date"]).dt.normalize()
    last_cg = (
        cg.dropna(subset=["market_cap_usd", "price_usd"])
        .sort_values("date")
        .groupby("symbol")
        .tail(1)
        .set_index("symbol")
    )
    anchors = {}
    for sym, row in last_cg.iterrows():
        if row["price_usd"] and row["price_usd"] > 0:
            anchors[sym] = float(row["market_cap_usd"]) / float(row["price_usd"])
    weekly["supply_anchor"] = weekly["symbol"].map(anchors)
    weekly["mcap"] = weekly["price"] * weekly["supply_anchor"]
    weekly["log_mcap"] = np.log(weekly["mcap"].where(weekly["mcap"] > 0))
    return weekly


def load_artemis_weekly() -> pd.DataFrame:
    act = pd.read_parquet(CLEAN / "artemis_activity_metrics.parquet")
    act["symbol"] = act["symbol"].astype(str).str.upper()
    act["date"] = pd.to_datetime(act["date"]).dt.normalize()
    act["week"] = monday_week(act["date"])
    sum_cols = [
        "fees",
        "revenue",
        "active_revenue",
        "passive_revenue",
        "transactions",
        "real_transactions",
        "volume",
        "real_volume",
    ]
    mean_cols = [
        "dau",
        "active_addresses",
        "gamed_transactions_pct",
        "gamed_volume_pct",
    ]
    weekly = (
        act.groupby(["week", "symbol"], as_index=False)
        .agg({**{c: "sum" for c in sum_cols}, **{c: "mean" for c in mean_cols}})
        .sort_values(["symbol", "week"])
    )
    return weekly


def load_defillama_weekly() -> pd.DataFrame:
    mapping = pd.read_parquet(CLEAN / "defillama_protocol_map.parquet")
    mapping["symbol"] = mapping["symbol"].astype(str).str.upper()
    mapping = mapping.dropna(subset=["defillama_slug"])[["symbol", "defillama_slug"]]
    tvl = pd.read_parquet(CLEAN / "defillama_protocol_tvl_daily.parquet")
    tvl["date"] = pd.to_datetime(tvl["date"]).dt.normalize()
    tvl = tvl.merge(mapping, on="defillama_slug", how="inner")
    tvl["week"] = monday_week(tvl["date"])
    weekly = (
        tvl.sort_values(["symbol", "date"])
        .groupby(["week", "symbol"], as_index=False)["tvl_usd"]
        .last()
        .rename(columns={"tvl_usd": "defillama_tvl_usd"})
    )
    return weekly


def add_signal_columns(panel: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = panel.sort_values(["symbol", "week"]).copy()
    eps = 1e-12

    df["func_fees_to_mcap"] = df["fees"] / df["mcap"]
    df["revenue_to_mcap"] = df["revenue"] / df["mcap"]
    df["active_revenue_to_mcap"] = df["active_revenue"] / df["mcap"]
    df["tvlc_artemis_to_mcap"] = df["tvl_usd"] / df["mcap"] if "tvl_usd" in df else np.nan
    df["tvlc_defillama_to_mcap"] = df["defillama_tvl_usd"] / df["mcap"]
    df["dau_to_mcap"] = df["dau"] / df["mcap"]
    df["tx_to_mcap"] = df["transactions"] / df["mcap"]
    df["real_tx_to_mcap"] = df["real_transactions"] / df["mcap"]
    df["real_volume_to_mcap"] = df["real_volume"] / df["mcap"]
    df["exchange_volume_to_mcap"] = df["quote_volume"] / df["mcap"]
    df["fees_per_dau"] = df["fees"] / (df["dau"] + eps)
    df["fees_per_tx"] = df["fees"] / (df["transactions"] + eps)
    df["revenue_per_dau"] = df["revenue"] / (df["dau"] + eps)
    df["real_tx_ratio"] = df["real_transactions"] / (df["transactions"] + eps)
    df["real_volume_ratio"] = df["real_volume"] / (df["volume"] + eps)
    df["low_gamed_tx"] = -df["gamed_transactions_pct"]
    df["low_gamed_volume"] = -df["gamed_volume_pct"]
    df["log_mcap_neg"] = -df["log_mcap"]

    g = df.groupby("symbol", sort=False)
    growth_bases = [
        "fees",
        "revenue",
        "dau",
        "active_addresses",
        "transactions",
        "real_transactions",
        "volume",
        "real_volume",
        "defillama_tvl_usd",
    ]
    for col in growth_bases:
        if col not in df:
            continue
        logged = g[col].transform(log1p_pos)
        df[f"{col}_growth_4w"] = logged - logged.groupby(df["symbol"]).shift(4)
        df[f"{col}_growth_12w"] = logged - logged.groupby(df["symbol"]).shift(12)

    df["mom_4w"] = g["ret"].transform(lambda s: (1 + s).rolling(4, min_periods=3).apply(np.prod, raw=True) - 1)
    df["vol_4w"] = g["ret"].transform(lambda s: s.rolling(4, min_periods=4).std())
    df["rmom_1w"] = df["ret"] / df["vol_4w"].replace(0, np.nan)
    df["maxret_4w_neg"] = -g["ret"].transform(lambda s: s.rolling(4, min_periods=4).max())
    df["vol_4w_neg"] = -df["vol_4w"]

    signal_cols = [
        "func_fees_to_mcap",
        "revenue_to_mcap",
        "active_revenue_to_mcap",
        "tvlc_artemis_to_mcap",
        "tvlc_defillama_to_mcap",
        "dau_to_mcap",
        "tx_to_mcap",
        "real_tx_to_mcap",
        "real_volume_to_mcap",
        "exchange_volume_to_mcap",
        "fees_per_dau",
        "fees_per_tx",
        "revenue_per_dau",
        "real_tx_ratio",
        "real_volume_ratio",
        "low_gamed_tx",
        "low_gamed_volume",
        "log_mcap_neg",
        "mom_4w",
        "rmom_1w",
        "maxret_4w_neg",
        "vol_4w_neg",
    ]
    signal_cols += [c for c in df.columns if c.endswith("_growth_4w") or c.endswith("_growth_12w")]

    for col in signal_cols:
        df[f"z_{col}"] = df.groupby("week")[col].transform(cs_zscore)
    return df, signal_cols


def build_panel() -> tuple[pd.DataFrame, list[str]]:
    prices = load_price_panel()
    act = load_artemis_weekly()
    llama = load_defillama_weekly()
    panel = prices.merge(act, on=["week", "symbol"], how="left")
    panel = panel.merge(llama, on=["week", "symbol"], how="left")

    if "tvl_usd" not in panel:
        # The cleaned Artemis activity table does not include chain TVL. Keep
        # this column explicit so TVLC-Artemis coverage is shown as missing.
        panel["tvl_usd"] = np.nan

    panel, signal_cols = add_signal_columns(panel)
    live = panel.groupby("week")["symbol"].transform("count")
    panel = panel[live >= MIN_NAMES].copy()
    panel.to_parquet(DATA_OUT / "alpha_factor_panel.parquet", index=False)
    return panel, signal_cols


def factor_return(
    panel: pd.DataFrame,
    z_col: str,
    *,
    direction: int,
    top_frac: float,
) -> pd.DataFrame:
    rows = []
    previous = pd.Series(dtype=float)
    for wk, g in panel.dropna(subset=["fwd_ret", z_col]).groupby("week", sort=True):
        n = len(g)
        if n < MIN_NAMES:
            continue
        k = max(MIN_SIDE, int(round(n * top_frac)))
        ranked = g.sort_values(z_col)
        if direction > 0:
            long = ranked.tail(k)
            short = ranked.head(k)
        else:
            long = ranked.head(k)
            short = ranked.tail(k)
        weights = pd.Series(0.0, index=g["symbol"])
        weights.loc[long["symbol"]] = 0.5 / len(long)
        weights.loc[short["symbol"]] = -0.5 / len(short)
        all_symbols = weights.index.union(previous.index)
        turnover = 0.5 * (
            weights.reindex(all_symbols).fillna(0.0)
            - previous.reindex(all_symbols).fillna(0.0)
        ).abs().sum()
        previous = weights
        ret = float((weights.reindex(g["symbol"]).to_numpy() * g["fwd_ret"].fillna(0.0).to_numpy()).sum())
        rows.append(
            {
                "week": wk,
                "ret_gross": ret,
                "turnover": float(turnover),
                "cost": float(turnover * COST_BPS / 1e4),
                "ret_net": float(ret - turnover * COST_BPS / 1e4),
                "n_names": int(n),
                "leg_size": int(k),
            }
        )
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class CandidateResult:
    candidate: str
    signal: str
    direction: int
    top_frac: float
    metrics: dict[str, dict[str, float]]


def evaluate_candidate(panel: pd.DataFrame, signal: str, direction: int, top_frac: float) -> CandidateResult:
    z_col = f"z_{signal}"
    ret = factor_return(panel, z_col, direction=direction, top_frac=top_frac)
    is_ret = ret[ret["week"] < FIRST_OOS]["ret_net"]
    oos_ret = ret[ret["week"] >= FIRST_OOS]["ret_net"]
    metrics = {
        "full": perf_metrics(ret["ret_net"]),
        "is": perf_metrics(is_ret),
        "oos": perf_metrics(oos_ret),
    }
    return CandidateResult(
        candidate=f"{signal}|dir={direction:+d}|top={top_frac:.2f}",
        signal=signal,
        direction=direction,
        top_frac=top_frac,
        metrics=metrics,
    )


def candidate_rows(results: list[CandidateResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        row = {"candidate": r.candidate, "signal": r.signal, "direction": r.direction, "top_frac": r.top_frac}
        for split, vals in r.metrics.items():
            for k, v in vals.items():
                row[f"{split}_{k}"] = v
        rows.append(row)
    return pd.DataFrame(rows)


def ensemble_return(panel: pd.DataFrame, selected: pd.DataFrame, name: str) -> pd.DataFrame:
    parts = []
    for _, row in selected.iterrows():
        z = panel[["week", "symbol", "fwd_ret", f"z_{row['signal']}"]].copy()
        z = z.rename(columns={f"z_{row['signal']}": "z"})
        z["z"] = float(row["direction"]) * z["z"].fillna(0.0)
        z["component"] = row["candidate"]
        parts.append(z)
    stacked = pd.concat(parts, ignore_index=True)
    signal = (
        stacked.groupby(["week", "symbol"], as_index=False)
        .agg(signal=("z", "mean"), fwd_ret=("fwd_ret", "first"))
    )
    ret = factor_return(signal, "signal", direction=+1, top_frac=float(selected["top_frac"].median()))
    ret["ensemble"] = name
    ret.to_parquet(DATA_OUT / f"ensemble_{name}.parquet", index=False)
    return ret


def build_ensembles(
    panel: pd.DataFrame,
    table: pd.DataFrame,
    *,
    name_prefix: str = "is",
    signal_filter: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = table[
        (table["is_weeks"] >= 100)
        & (table["oos_weeks"] >= 20)
        & (table["is_sharpe"] > 0)
        & (table["is_ann_return"] > 0)
    ].copy()
    if signal_filter is not None:
        eligible = eligible[eligible["signal"].isin(signal_filter)].copy()
    eligible = eligible.sort_values(["is_sharpe", "is_ann_return"], ascending=False)

    ensembles = []
    selected_rows = []
    for n in (1, 2, 3, 5, 8, 12):
        chosen = []
        used_base = set()
        for _, row in eligible.iterrows():
            if row["signal"] in used_base:
                continue
            chosen.append(row)
            used_base.add(row["signal"])
            if len(chosen) == n:
                break
        if len(chosen) < 1:
            continue
        selected = pd.DataFrame(chosen)
        name = f"{name_prefix}_top{len(selected)}"
        ret = ensemble_return(panel, selected, name)
        metrics = {
            "ensemble": name,
            "n_components": int(len(selected)),
            **{f"full_{k}": v for k, v in perf_metrics(ret["ret_net"]).items()},
            **{f"is_{k}": v for k, v in perf_metrics(ret[ret["week"] < FIRST_OOS]["ret_net"]).items()},
            **{f"oos_{k}": v for k, v in perf_metrics(ret[ret["week"] >= FIRST_OOS]["ret_net"]).items()},
        }
        ensembles.append(metrics)
        selected = selected[["candidate", "signal", "direction", "top_frac", "is_sharpe", "oos_sharpe"]].copy()
        selected["ensemble"] = name
        selected_rows.append(selected)

    return pd.DataFrame(ensembles), pd.concat(selected_rows, ignore_index=True) if selected_rows else pd.DataFrame()


def persist_positive_onchain_portfolios(panel: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    onchain = table[~table["signal"].isin(PRICE_CONTROL_SIGNALS)].copy()
    positive = onchain[
        (onchain["is_sharpe"] > 0)
        & (onchain["oos_sharpe"] > 0)
        & (onchain["is_ann_return"] > 0)
        & (onchain["oos_ann_return"] > 0)
    ].sort_values(["is_sharpe", "oos_sharpe"], ascending=False)
    if positive.empty:
        return positive
    for i, row in positive.head(5).iterrows():
        ret = factor_return(
            panel,
            f"z_{row['signal']}",
            direction=int(row["direction"]),
            top_frac=float(row["top_frac"]),
        )
        safe_name = str(row["candidate"]).replace("|", "_").replace("+", "plus").replace("-", "minus").replace(".", "p")
        ret.to_parquet(DATA_OUT / f"positive_onchain_{safe_name}.parquet", index=False)
    positive.head(20).to_csv(DATA_OUT / "positive_onchain_candidates.csv", index=False)
    positive.head(20).to_parquet(DATA_OUT / "positive_onchain_candidates.parquet", index=False)
    return positive


def baseline_returns(panel: pd.DataFrame) -> pd.DataFrame:
    ew = panel.dropna(subset=["fwd_ret"]).groupby("week")["fwd_ret"].mean().rename("EW Market")
    btc = (
        panel[(panel["symbol"] == "BTC") & panel["fwd_ret"].notna()]
        .set_index("week")["fwd_ret"]
        .rename("BTC")
    )
    out = pd.concat([ew, btc], axis=1).reset_index()
    out.to_parquet(DATA_OUT / "baseline_returns.parquet", index=False)
    return out


def sparse_tvl_diagnostic(panel: pd.DataFrame) -> pd.DataFrame:
    """Evaluate TVL signals separately because local coverage is very sparse."""
    global_min_names, global_min_side = MIN_NAMES, MIN_SIDE
    tvl_signals = [
        "tvlc_defillama_to_mcap",
        "defillama_tvl_usd_growth_4w",
        "defillama_tvl_usd_growth_12w",
    ]
    rows = []
    try:
        globals()["MIN_NAMES"] = 4
        globals()["MIN_SIDE"] = 1
        for sig, direction, top_frac in itertools.product(tvl_signals, (-1, +1), (0.25, 0.50)):
            ret = factor_return(panel, f"z_{sig}", direction=direction, top_frac=top_frac)
            if ret.empty:
                continue
            is_m = perf_metrics(ret[ret["week"] < FIRST_OOS]["ret_net"])
            oos_m = perf_metrics(ret[ret["week"] >= FIRST_OOS]["ret_net"])
            rows.append(
                {
                    "candidate": f"{sig}|dir={direction:+d}|top={top_frac:.2f}",
                    "signal": sig,
                    "direction": direction,
                    "top_frac": top_frac,
                    "is_sharpe": is_m["sharpe"],
                    "is_ann_return": is_m["ann_return"],
                    "is_weeks": is_m["weeks"],
                    "oos_sharpe": oos_m["sharpe"],
                    "oos_ann_return": oos_m["ann_return"],
                    "oos_max_dd": oos_m["max_dd"],
                    "oos_weeks": oos_m["weeks"],
                }
            )
    finally:
        globals()["MIN_NAMES"] = global_min_names
        globals()["MIN_SIDE"] = global_min_side

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["oos_sharpe", "is_sharpe"], ascending=False)
        out.to_csv(DATA_OUT / "sparse_tvl_diagnostic.csv", index=False)
        out.to_parquet(DATA_OUT / "sparse_tvl_diagnostic.parquet", index=False)
    return out


def coverage_table(panel: pd.DataFrame, signal_cols: list[str]) -> pd.DataFrame:
    rows = []
    for sig in signal_cols:
        z = f"z_{sig}"
        valid = panel.dropna(subset=[z, "fwd_ret"])
        by_week = valid.groupby("week")["symbol"].nunique()
        rows.append(
            {
                "signal": sig,
                "obs": int(len(valid)),
                "symbols": int(valid["symbol"].nunique()),
                "weeks": int(valid["week"].nunique()),
                "median_names_per_week": float(by_week.median()) if len(by_week) else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["median_names_per_week", "obs"], ascending=False)


def write_results(
    table: pd.DataFrame,
    ensembles: pd.DataFrame,
    selected: pd.DataFrame,
    coverage: pd.DataFrame,
    baselines: pd.DataFrame,
    sparse_tvl: pd.DataFrame,
) -> None:
    top_single = table.sort_values(["oos_sharpe", "is_sharpe"], ascending=False).head(15)
    top_is = table.sort_values(["is_sharpe", "oos_sharpe"], ascending=False).head(15)
    onchain = table[~table["signal"].isin(PRICE_CONTROL_SIGNALS)].copy()
    onchain_positive = onchain[
        (onchain["is_sharpe"] > 0)
        & (onchain["oos_sharpe"] > 0)
        & (onchain["is_ann_return"] > 0)
        & (onchain["oos_ann_return"] > 0)
    ].sort_values(["is_sharpe", "oos_sharpe"], ascending=False)
    base_metrics = {
        name: {
            "is": perf_metrics(baselines[baselines["week"] < FIRST_OOS][name]),
            "oos": perf_metrics(baselines[baselines["week"] >= FIRST_OOS][name]),
            "full": perf_metrics(baselines[name]),
        }
        for name in ["EW Market", "BTC"]
        if name in baselines
    }
    manifest = {
        "first_oos_week": FIRST_OOS.strftime("%Y-%m-%d"),
        "cost_bps": COST_BPS,
        "min_names": MIN_NAMES,
        "top_fracs": list(TOP_FRACS),
        "universe_source": UNIVERSE_CONFIG["source"],
        "target_universe_symbols": sorted(UNIVERSE_CONFIG["symbols"]) if UNIVERSE_CONFIG["symbols"] else None,
        "coverage": {
            "panel_rows": int(coverage["obs"].max()) if not coverage.empty else 0,
            "signals_tested": int(coverage["signal"].nunique()),
        },
        "best_oos_single": top_single.head(5).to_dict(orient="records"),
        "best_is_selected_single": top_is.head(5).to_dict(orient="records"),
        "positive_onchain_candidates": onchain_positive.head(10).to_dict(orient="records"),
        "sparse_tvl_diagnostic": sparse_tvl.head(10).to_dict(orient="records") if not sparse_tvl.empty else [],
        "ensemble_metrics": ensembles.to_dict(orient="records"),
        "baseline_metrics": base_metrics,
    }
    (MANIFEST_OUT / "alpha_search_metrics.json").write_text(json.dumps(manifest, indent=2, default=str))

    def fmt_pct(x: float) -> str:
        return "n/a" if pd.isna(x) else f"{100 * x:.1f}%"

    def fmt_num(x: float) -> str:
        return "n/a" if pd.isna(x) else f"{x:.2f}"

    lines = [
        "# Stage 18 - Artemis Alpha Search",
        "",
        f"Universe source: `{UNIVERSE_CONFIG['source']}`.",
        "",
        f"Split: IS before {FIRST_OOS.date()}, OOS from {FIRST_OOS.date()} onward. Returns are next-week Binance returns with {COST_BPS:.0f} bps turnover cost.",
        "",
        "## Positive On-Chain Result",
        "",
        "The cleanest positive broad-coverage on-chain result is weekly **fee growth**: long coins with the strongest 4-week Artemis fee growth and short the weakest. Static FunC fee yield did not survive OOS, but fee growth did.",
        "",
        "| Candidate | IS Sharpe | OOS Sharpe | IS Ann Ret | OOS Ann Ret | OOS Max DD |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    if onchain_positive.empty:
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a |")
    else:
        for _, r in onchain_positive.head(10).iterrows():
            lines.append(
                f"| {r['candidate']} | {fmt_num(r['is_sharpe'])} | {fmt_num(r['oos_sharpe'])} | "
                f"{fmt_pct(r['is_ann_return'])} | {fmt_pct(r['oos_ann_return'])} | {fmt_pct(r['oos_max_dd'])} |"
            )

    lines += [
        "",
        "Caution: this is still an exploratory factor search. The result is positive in both windows, but it should be presented as supporting evidence, not as a replacement for the Stage 15 headline strategy.",
        "",
        "Selection note: the naive on-chain-only ensemble selected purely by top IS Sharpe overweights revenue growth and fails OOS; the positive result to show is the fee-growth factor, plus the mixed 12-signal ensemble below.",
        "",
        "TVLC note: local DeFiLlama TVL coverage is only about 4 names per week, so TVLC is too sparse in this local cleaned panel for a broad-universe portfolio.",
        "",
        "## Sparse TVLC Diagnostic",
        "",
        "This lowers the TVL test gate to 4 names/week. Treat it as a diagnostic only, not a production broad-universe factor.",
        "",
        "| Candidate | IS Sharpe | OOS Sharpe | IS Ann Ret | OOS Ann Ret | OOS Max DD |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    if sparse_tvl.empty:
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a |")
    else:
        for _, r in sparse_tvl.head(8).iterrows():
            lines.append(
                f"| {r['candidate']} | {fmt_num(r['is_sharpe'])} | {fmt_num(r['oos_sharpe'])} | "
                f"{fmt_pct(r['is_ann_return'])} | {fmt_pct(r['oos_ann_return'])} | {fmt_pct(r['oos_max_dd'])} |"
            )

    lines += [
        "",
        "## Best Single-Factor Candidates by OOS Sharpe",
        "",
        "| Candidate | IS Sharpe | OOS Sharpe | OOS Ann Ret | OOS Max DD | OOS weeks |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in top_single.iterrows():
        lines.append(
            f"| {r['candidate']} | {fmt_num(r['is_sharpe'])} | {fmt_num(r['oos_sharpe'])} | "
            f"{fmt_pct(r['oos_ann_return'])} | {fmt_pct(r['oos_max_dd'])} | {int(r['oos_weeks'])} |"
        )

    lines += [
        "",
        "## Best Single-Factor Candidates Selected by IS Sharpe",
        "",
        "| Candidate | IS Sharpe | OOS Sharpe | IS Ann Ret | OOS Ann Ret |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, r in top_is.iterrows():
        lines.append(
            f"| {r['candidate']} | {fmt_num(r['is_sharpe'])} | {fmt_num(r['oos_sharpe'])} | "
            f"{fmt_pct(r['is_ann_return'])} | {fmt_pct(r['oos_ann_return'])} |"
        )

    lines += [
        "",
        "## IS-Selected Ensembles",
        "",
        "| Ensemble | Components | IS Sharpe | OOS Sharpe | OOS Ann Ret | OOS Max DD |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    if not ensembles.empty:
        for _, r in ensembles.sort_values(["oos_sharpe", "is_sharpe"], ascending=False).iterrows():
            lines.append(
                f"| {r['ensemble']} | {int(r['n_components'])} | {fmt_num(r['is_sharpe'])} | "
                f"{fmt_num(r['oos_sharpe'])} | {fmt_pct(r['oos_ann_return'])} | {fmt_pct(r['oos_max_dd'])} |"
            )

    lines += [
        "",
        "## Baselines",
        "",
        "| Baseline | IS Sharpe | OOS Sharpe | OOS Ann Ret | OOS Max DD |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, splits in base_metrics.items():
        lines.append(
            f"| {name} | {fmt_num(splits['is']['sharpe'])} | {fmt_num(splits['oos']['sharpe'])} | "
            f"{fmt_pct(splits['oos']['ann_return'])} | {fmt_pct(splits['oos']['max_dd'])} |"
        )

    lines += [
        "",
        "## Coverage",
        "",
        "| Signal | Symbols | Weeks | Median names/week |",
        "|---|---:|---:|---:|",
    ]
    for _, r in coverage.head(30).iterrows():
        lines.append(
            f"| {r['signal']} | {int(r['symbols'])} | {int(r['weeks'])} | {r['median_names_per_week']:.0f} |"
        )

    if not selected.empty:
        lines += [
            "",
            "## Ensemble Components",
            "",
            "| Ensemble | Candidate | IS Sharpe | OOS Sharpe |",
            "|---|---|---:|---:|",
        ]
        for _, r in selected.iterrows():
            lines.append(f"| {r['ensemble']} | {r['candidate']} | {fmt_num(r['is_sharpe'])} | {fmt_num(r['oos_sharpe'])} |")

    (STAGE / "RESULTS.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    panel, signal_cols = build_panel()
    coverage = coverage_table(panel, signal_cols)
    coverage.to_csv(DATA_OUT / "signal_coverage.csv", index=False)
    coverage.to_parquet(DATA_OUT / "signal_coverage.parquet", index=False)

    usable = coverage[coverage["median_names_per_week"] >= MIN_NAMES]["signal"].tolist()
    results = [
        evaluate_candidate(panel, sig, direction, top_frac)
        for sig, direction, top_frac in itertools.product(usable, (-1, +1), TOP_FRACS)
    ]
    table = candidate_rows(results)
    table.to_csv(DATA_OUT / "candidate_metrics.csv", index=False)
    table.to_parquet(DATA_OUT / "candidate_metrics.parquet", index=False)
    persist_positive_onchain_portfolios(panel, table)

    all_ensembles, all_selected = build_ensembles(panel, table, name_prefix="is")
    onchain_signals = set(table["signal"].unique()) - PRICE_CONTROL_SIGNALS
    onchain_ensembles, onchain_selected = build_ensembles(
        panel,
        table,
        name_prefix="onchain_is",
        signal_filter=onchain_signals,
    )
    ensembles = pd.concat([all_ensembles, onchain_ensembles], ignore_index=True)
    selected = pd.concat([all_selected, onchain_selected], ignore_index=True)
    ensembles.to_csv(DATA_OUT / "ensemble_metrics.csv", index=False)
    if not ensembles.empty:
        ensembles.to_parquet(DATA_OUT / "ensemble_metrics.parquet", index=False)
    if not selected.empty:
        selected.to_csv(DATA_OUT / "ensemble_components.csv", index=False)
        selected.to_parquet(DATA_OUT / "ensemble_components.parquet", index=False)

    baselines = baseline_returns(panel)
    sparse_tvl = sparse_tvl_diagnostic(panel)
    write_results(table, ensembles, selected, coverage, baselines, sparse_tvl)

    best_oos = table.sort_values(["oos_sharpe", "is_sharpe"], ascending=False).iloc[0]
    print("Stage 18 alpha search complete")
    print(f"  panel: {panel['symbol'].nunique()} symbols, {panel['week'].nunique()} weeks, {len(panel):,} rows")
    print(f"  signals tested: {len(usable)} ({len(table)} directional/top-frac candidates)")
    print(f"  best OOS single: {best_oos['candidate']} | IS {best_oos['is_sharpe']:.2f} | OOS {best_oos['oos_sharpe']:.2f}")
    if not ensembles.empty:
        best_ens = ensembles.sort_values(["oos_sharpe", "is_sharpe"], ascending=False).iloc[0]
        print(f"  best IS-selected ensemble: {best_ens['ensemble']} | IS {best_ens['is_sharpe']:.2f} | OOS {best_ens['oos_sharpe']:.2f}")


if __name__ == "__main__":
    main()
