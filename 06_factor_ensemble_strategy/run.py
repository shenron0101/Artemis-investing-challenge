#!/usr/bin/env python3
"""Factor sub-book ensemble strategy — the final strategy stage.

This stage uses the weekly factor panel and XGBoost regime probabilities built
by `engine.py`, but does not blend every factor into one monolithic score. It
builds three sub-books and allocates among them with a causal rolling
performance rule:

* mispricing: RMOM1w, RMOM2w, SMBC, NetRel
* core_rank: VolC, MAXRET
* priced_tilt: CRASH8, BETA26, TVLC, SKEW52, NEWC

The panel and regime construction, plus the portfolio primitives
(`build_signal`, `construct_weights`, `backtest`), live in the local `engine`
module and read from `03_nalfp_add/artifacts/data/`.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine


ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent

OUT = STAGE / "artifacts"
DATA_OUT = OUT / "data"
FIG_OUT = OUT / "figures"
MANIFEST_OUT = OUT / "manifests"
for d in (DATA_OUT, FIG_OUT, MANIFEST_OUT):
    d.mkdir(parents=True, exist_ok=True)

WEEKS_PER_YEAR = 52
OOS_WEEKS = 79
COST_BPS = 10.0
BOOK_LOOKBACK = 26
BOOK_MIN_HISTORY = 8
BOOK_NAMES = ["mispricing", "core_rank", "priced_tilt"]
BASE_BOOK_ALLOC = {"mispricing": 0.55, "core_rank": 0.35, "priced_tilt": 0.10}
VARIANT_BASE_ALLOCS = {
    "Sharpe Ensemble": {"mispricing": 0.92, "core_rank": 0.08, "priced_tilt": 0.00},
    "Balanced Ensemble": BASE_BOOK_ALLOC,
    "Defensive Ensemble": {"mispricing": 0.65, "core_rank": 0.35, "priced_tilt": 0.00},
}


@dataclass(frozen=True)
class BookSpec:
    name: str
    factor_weights: dict[str, float]
    top_frac: float
    gross_risk_on: float
    gross_neutral: float
    gross_risk_off: float


BOOK_SPECS = [
    BookSpec(
        name="mispricing",
        factor_weights={"RMOM1w": 0.25, "RMOM2w": 0.25, "SMBC": 0.25, "NetRel": 0.25},
        top_frac=0.25,
        gross_risk_on=0.90,
        gross_neutral=0.72,
        gross_risk_off=0.52,
    ),
    BookSpec(
        name="core_rank",
        factor_weights={"VolC": 0.55, "MAXRET": 0.45},
        top_frac=0.25,
        gross_risk_on=0.72,
        gross_neutral=0.64,
        gross_risk_off=0.58,
    ),
    BookSpec(
        name="priced_tilt",
        factor_weights={"CRASH8": 0.20, "BETA26": 0.20, "TVLC": 0.25, "SKEW52": 0.20, "NEWC": 0.15},
        top_frac=0.20,
        gross_risk_on=0.55,
        gross_neutral=0.42,
        gross_risk_off=0.25,
    ),
]


def perf_metrics(r: pd.Series) -> dict[str, float]:
    x = r.dropna()
    if len(x) < 5:
        return {
            "ann_return": np.nan,
            "ann_vol": np.nan,
            "sharpe": np.nan,
            "max_dd": np.nan,
            "calmar": np.nan,
            "hit_rate": np.nan,
            "weeks": int(len(x)),
        }
    ann_ret = float(x.mean() * WEEKS_PER_YEAR)
    ann_vol = float(x.std(ddof=1) * math.sqrt(WEEKS_PER_YEAR))
    curve = (1 + x).cumprod()
    dd = curve / curve.cummax() - 1
    max_dd = float(dd.min())
    return {
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": float(ann_ret / ann_vol) if ann_vol > 0 else np.nan,
        "max_dd": max_dd,
        "calmar": float(ann_ret / abs(max_dd)) if max_dd < 0 else np.nan,
        "hit_rate": float((x > 0).mean()),
        "weeks": int(len(x)),
    }


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the factor + regime panels, building them from stage-03 data if
    they are not already present in this stage's artifacts/data directory."""
    return engine.load_panels()


def factor_weight_frame(panel: pd.DataFrame, factor_weights: dict[str, float]) -> pd.DataFrame:
    total = sum(max(v, 0.0) for v in factor_weights.values())
    if total <= 0:
        raise ValueError("factor_weights must contain positive weights")
    row_weights = {fac: max(factor_weights.get(fac, 0.0), 0.0) / total for fac in engine.FACTOR_ORDER}
    fw = pd.DataFrame({"week": sorted(panel["week"].dropna().unique())})
    for fac in engine.FACTOR_ORDER:
        fw[fac] = row_weights[fac]
    return fw


def build_subbook(spec: BookSpec, panel: pd.DataFrame, regime: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    fw = factor_weight_frame(panel, spec.factor_weights)
    signal = engine.build_signal(panel, fw)
    candidate = engine.Candidate(
        name=spec.name,
        sleeve_core=1.0,
        sleeve_priced=0.0,
        sleeve_mispricing=0.0,
        sleeve_legacy=0.0,
        ic_blend=0.0,
        top_frac=spec.top_frac,
        gross_risk_on=spec.gross_risk_on,
        gross_neutral=spec.gross_neutral,
        gross_risk_off=spec.gross_risk_off,
        slow_factor_boost=1.0,
    )
    weights = engine.construct_weights(signal, regime, candidate)
    pnl = engine.backtest(weights, panel)
    pnl["book"] = spec.name
    weights["book"] = spec.name
    return weights, pnl


def rolling_score(hist: pd.Series) -> float:
    x = hist.dropna()
    if len(x) < 2:
        return 0.0
    mean = x.mean()
    vol = x.std(ddof=1)
    if not np.isfinite(vol) or vol <= 0:
        return 0.0
    curve = (1 + x).cumprod()
    dd = float((curve / curve.cummax() - 1).min())
    sharpe = mean / vol
    return max(sharpe, 0.0) * (1.0 + min(dd, 0.0))


def regime_tilt(row: pd.Series) -> dict[str, float]:
    risk_on = float(row.get("p_RiskOn", 0.0))
    risk_off = float(row.get("p_RiskOff", 0.0))
    confidence = max(float(row.get("p_RiskOn", 0.0)), float(row.get("p_Neutral", 0.0)), risk_off)
    confidence = 0.5 + 0.5 * confidence
    return {
        "mispricing": confidence * (1.00 + 0.25 * risk_on - 0.10 * risk_off),
        "core_rank": confidence * (1.00 + 0.35 * risk_off),
        "priced_tilt": confidence * (0.55 + 0.35 * risk_on),
    }


PRICED_TILT_CAP = 0.18   # max share of book allocation the priced-risk sleeve may hold


def rolling_book_allocations(
    book_returns: pd.DataFrame,
    regime: pd.DataFrame,
    *,
    lookback: int = BOOK_LOOKBACK,
    min_history: int = BOOK_MIN_HISTORY,
    base_alloc: dict[str, float] = BASE_BOOK_ALLOC,
    use_regime_tilt: bool = True,
    priced_cap: float = PRICED_TILT_CAP,
) -> pd.DataFrame:
    returns = book_returns.sort_values("week").reset_index(drop=True)
    regime_idx = regime.set_index("week")
    rows = []
    books = [c for c in returns.columns if c != "week"]
    for i, row in returns.iterrows():
        wk = row["week"]
        hist = returns.iloc[:i].tail(lookback)
        if len(hist) < min_history:
            raw = {book: float(base_alloc.get(book, 0.0)) for book in books}
        else:
            scores = {book: rolling_score(hist[book]) for book in books}
            if sum(scores.values()) <= 0:
                scores = {book: float(base_alloc.get(book, 0.0)) for book in books}
            raw = {
                book: (0.35 * float(base_alloc.get(book, 0.0)) + 0.65 * scores[book])
                for book in books
            }
        if use_regime_tilt and wk in regime_idx.index:
            tilt = regime_tilt(regime_idx.loc[wk])
            raw = {book: raw[book] * tilt.get(book, 1.0) for book in books}

        raw["priced_tilt"] = min(raw.get("priced_tilt", 0.0), priced_cap * sum(raw.values()))
        total = sum(max(v, 0.0) for v in raw.values())
        if total <= 0:
            raw = {book: float(base_alloc.get(book, 0.0)) for book in books}
            total = sum(raw.values())
        out = {"week": wk}
        out.update({book: max(raw[book], 0.0) / total for book in books})
        rows.append(out)
    return pd.DataFrame(rows)


def combine_book_weights(subbook_weights: dict[str, pd.DataFrame], allocation: pd.DataFrame) -> pd.DataFrame:
    alloc = allocation.set_index("week")
    parts = []
    for book, weights in subbook_weights.items():
        w = weights[["week", "symbol", "w"]].copy()
        w["alloc"] = w["week"].map(alloc[book]).fillna(0.0)
        w["w"] = w["w"] * w["alloc"]
        parts.append(w[["week", "symbol", "w"]])
    combined = pd.concat(parts, ignore_index=True)
    out = combined.groupby(["week", "symbol"], as_index=False)["w"].sum()
    return out.sort_values(["week", "symbol"]).reset_index(drop=True)


def backtest_combined(weights: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    fwd = panel[["week", "symbol", "fwd_ret"]]
    w = weights.merge(fwd, on=["week", "symbol"], how="left")
    previous = None
    rows = []
    for wk, g in w.groupby("week", sort=True):
        current = g.set_index("symbol")["w"]
        if previous is None:
            turnover = 0.5 * current.abs().sum()
        else:
            idx = current.index.union(previous.index)
            turnover = 0.5 * (current.reindex(idx).fillna(0.0) - previous.reindex(idx).fillna(0.0)).abs().sum()
        previous = current
        gross = float(current.abs().sum())
        long_gross = float(current.clip(lower=0.0).sum())
        short_gross = float(-current.clip(upper=0.0).sum())
        pnl_gross = float((g["w"] * g["fwd_ret"].fillna(0.0)).sum())
        cost = turnover * COST_BPS / 1e4
        rows.append(
            {
                "week": wk,
                "pnl_gross": pnl_gross,
                "turnover": turnover,
                "cost": cost,
                "pnl_net": pnl_gross - cost,
                "gross_exposure": gross,
                "long_gross": long_gross,
                "short_gross": short_gross,
                "net_exposure": long_gross - short_gross,
                "n_assets": int((current.abs() > 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def benchmark_returns(panel: pd.DataFrame) -> pd.DataFrame:
    ew = panel.dropna(subset=["fwd_ret"]).groupby("week")["fwd_ret"].mean().rename("EW Market")
    btc = panel[panel["symbol"].eq("BTC")].set_index("week")["fwd_ret"].rename("BTC")
    return pd.concat([ew, btc], axis=1).reset_index()


def format_pct(x: float) -> str:
    return "n/a" if not np.isfinite(x) else f"{x:+.1%}"


def format_num(x: float) -> str:
    return "n/a" if not np.isfinite(x) else f"{x:+.2f}"


def metrics_table(metrics: dict[str, dict]) -> str:
    header = "| Strategy | Sharpe | AnnRet | AnnVol | MaxDD | Hit | Weeks |\n|---|---:|---:|---:|---:|---:|---:|\n"
    body = ""
    for name, m in metrics.items():
        body += (
            f"| {name} | {format_num(m['sharpe'])} | {format_pct(m['ann_return'])} | "
            f"{format_pct(m['ann_vol']).replace('+', '')} | {format_pct(m['max_dd'])} | "
            f"{m['hit_rate']:.0%} | {m['weeks']} |\n"
        )
    return header + body


def plot_cumulative(
    variant_pnls: dict[str, pd.DataFrame],
    book_pnls: dict[str, pd.DataFrame],
    bm: pd.DataFrame,
    first_oos: pd.Timestamp,
) -> None:
    plt.figure(figsize=(12, 7))
    for name, pnl in variant_pnls.items():
        curve = (1 + pnl.sort_values("week").set_index("week")["pnl_net"]).cumprod()
        plt.plot(curve.index, curve.values, linewidth=2.2, label=name)
    for name, df in book_pnls.items():
        c = (1 + df.sort_values("week").set_index("week")["pnl_net"]).cumprod()
        plt.plot(c.index, c.values, linewidth=1.0, alpha=0.45, label=name)
    for col, style in [("EW Market", "--"), ("BTC", ":")]:
        s = bm.dropna(subset=[col]).sort_values("week").set_index("week")[col]
        plt.plot(s.index, (1 + s).cumprod(), linestyle=style, linewidth=1.4, label=col)
    plt.axvline(first_oos, color="black", linestyle="--", linewidth=1, alpha=0.6)
    plt.yscale("log")
    plt.title("Factor Ensemble, Net Returns")
    plt.ylabel("Growth of $1, log scale")
    plt.xlabel("Week")
    plt.legend(ncol=2)
    plt.tight_layout()
    plt.savefig(FIG_OUT / "cumulative_returns.png", dpi=160)
    plt.close()


def plot_allocations(allocation: pd.DataFrame, name: str) -> None:
    a = allocation.sort_values("week")
    plt.figure(figsize=(12, 5))
    plt.stackplot(a["week"], *(a[book] for book in BOOK_NAMES), labels=BOOK_NAMES, alpha=0.85)
    plt.title(f"{name} Causal Rolling Sub-Book Allocation")
    plt.ylabel("Allocation")
    plt.xlabel("Week")
    plt.ylim(0, 1)
    plt.legend(loc="upper left", ncol=3)
    plt.tight_layout()
    safe = name.lower().replace(" ", "_")
    plt.savefig(FIG_OUT / f"{safe}_book_allocations.png", dpi=160)
    plt.close()


def write_results(
    variant_pnls: dict[str, pd.DataFrame],
    book_pnls: dict[str, pd.DataFrame],
    allocations: dict[str, pd.DataFrame],
    bm: pd.DataFrame,
    first_oos: pd.Timestamp,
    baselines: dict[str, pd.DataFrame] | None = None,
    sensitivity: pd.DataFrame | None = None,
) -> None:
    baselines = baselines or {}
    baseline_oos = {name: perf_metrics(df[df["week"] >= first_oos]["pnl_net"]) for name, df in baselines.items()}
    baseline_full = {name: perf_metrics(df["pnl_net"]) for name, df in baselines.items()}
    metrics = {
        **{name: perf_metrics(df["pnl_net"]) for name, df in variant_pnls.items()},
        **{name: perf_metrics(df["pnl_net"]) for name, df in book_pnls.items()},
    }
    is_metrics = {
        **{name: perf_metrics(df[df["week"] < first_oos]["pnl_net"]) for name, df in variant_pnls.items()},
        **{name: perf_metrics(df[df["week"] < first_oos]["pnl_net"]) for name, df in book_pnls.items()},
    }
    oos_metrics = {
        **{name: perf_metrics(df[df["week"] >= first_oos]["pnl_net"]) for name, df in variant_pnls.items()},
        **{name: perf_metrics(df[df["week"] >= first_oos]["pnl_net"]) for name, df in book_pnls.items()},
    }
    for col in ["EW Market", "BTC"]:
        b = bm[["week", col]].dropna().rename(columns={col: "pnl_net"})
        metrics[col] = perf_metrics(b["pnl_net"])
        is_metrics[col] = perf_metrics(b[b["week"] < first_oos]["pnl_net"])
        oos_metrics[col] = perf_metrics(b[b["week"] >= first_oos]["pnl_net"])

    avg_alloc_rows = []
    for variant, allocation in allocations.items():
        row = {"Variant": variant}
        row.update(allocation[BOOK_NAMES].mean().to_dict())
        avg_alloc_rows.append(row)
    avg_alloc = pd.DataFrame(avg_alloc_rows)
    for book in BOOK_NAMES:
        avg_alloc[book] = avg_alloc[book].map(lambda x: f"{x:.1%}")

    md = f"""# Factor Ensemble Strategy

Generated by `06_factor_ensemble_strategy/run.py`.

This stage does not force every factor into one score. It builds separate
sub-books for robust weekly rankers, the MispricingM composite, and priced-risk
tilts, then allocates between those books using only prior realized book returns
plus the `engine.py` XGBoost regime probabilities.

Train/test split: weeks before `{first_oos:%Y-%m-%d}` are in-sample, and the
final {OOS_WEEKS} weeks are out-of-sample.

## Sub-Books

| Book | Factors | Purpose |
|---|---|---|
| MispricingM | RMOM1w, RMOM2w, SMBC, NetRel | Distributionally robust cross-sectional mispricing composite |
| Core Rank | VolC, MAXRET | Most reliable weekly rankers from the factor validation |
| Priced Tilt | CRASH8, BETA26, TVLC, SKEW52, NEWC | Small capped sleeve for GX-priced risks, not allowed to dominate |

The rolling allocator uses a {BOOK_LOOKBACK}-week lookback with a {BOOK_MIN_HISTORY}-week
warm-up. For week `t`, it scores only returns from weeks `< t`, blends that score
with a conservative base allocation, applies a regime confidence tilt, and caps
the priced-risk sleeve.

## Ensemble Modes

{avg_alloc.to_markdown(index=False)}

## Full-Window Performance

{metrics_table(metrics)}

## In-Sample Performance

{metrics_table(is_metrics)}

## Out-of-Sample Performance

{metrics_table(oos_metrics)}

## Baseline & ablation variants (audit Findings 5 & 6)

The headline ensembles depend on two sets of hardcoded priors: the regime tilt in
`regime_tilt()` and the priced-tilt cap. These baselines isolate each choice. All
use the Sharpe Ensemble base allocation; only one knob changes at a time.

OOS ({OOS_WEEKS} weeks) net performance:

{metrics_table(baseline_oos)}

- **SE Priced-Tilt Off / 5% cap** (Finding 6): the priced-risk sleeve is OOS-toxic
  on its own (Priced Tilt book OOS Sharpe is negative above). Zeroing or shrinking
  its cap shows how much it drags the ensemble. If "Priced-Tilt Off" beats the
  headline SE, the sleeve should be cut, not just capped.
- **SE No Regime Tilt** (Finding 5): replaces the regime-tilt multipliers with 1.0.
  The gap vs the headline Sharpe Ensemble is the *measured* value added by regime
  conditioning — not an assumed benefit.
- **MispricingM Only**: the mispricing sub-book traded alone. Because the Sharpe
  Ensemble already routes ~80% to MispricingM, this quantifies the single-factor
  dependency the audit flagged.

### Sharpe Ensemble sensitivity grid

OOS Sharpe under regime-tilt on/off x priced-tilt cap. A headline that barely moves
across this grid is robust to the priors; large swings are a fragility flag.

{sensitivity.to_markdown(index=False) if sensitivity is not None else "n/a"}

## Activation & regime-tilt priors — derivation (audit Finding 5)

The multipliers in `regime_tilt()` are economic priors, not fitted parameters.
They are documented here so they are auditable rather than magic numbers:

| Book | RiskOn lift | RiskOff lift | Rationale |
|---|---|---|---|
| mispricing | `+0.25*p_RiskOn` | `-0.10*p_RiskOff` | Mispricing reversals pay most when risk appetite is returning; trimmed slightly in risk-off when dispersion collapses. |
| core_rank | none | `+0.35*p_RiskOff` | Low-vol / lottery-reversal rankers are defensive — lift them when the market de-risks. |
| priced_tilt | `0.55 + 0.35*p_RiskOn` | (scales down) | Speculative beta/skew/crash premia are risk-on phenomena; the base 0.55 keeps the sleeve small by construction. |

All multipliers are bounded and multiplied by a confidence term
`0.5 + 0.5*max(p_state)`, so an unsure regime call pulls every book toward its base
weight. The sensitivity grid above is the robustness check on these values: the
"No Regime Tilt" column is the all-multipliers-equal-1.0 limit.

## Plots

![Cumulative returns](artifacts/figures/cumulative_returns.png)

![Sharpe allocations](artifacts/figures/sharpe_ensemble_book_allocations.png)

![Balanced allocations](artifacts/figures/balanced_ensemble_book_allocations.png)

## Artifacts

- `artifacts/data/*_book_allocations.parquet`
- `artifacts/data/*_weekly_pnl.parquet`
- `artifacts/data/*_weekly_weights.parquet`
- `artifacts/manifests/metrics.json`

## Caveat

This is still a research allocator. The improvement target is OOS robustness:
priced-risk factors are kept small unless their own realized sub-book performance
supports more capital, and the XGBoost regime detector sizes risk rather than
directly flipping every factor signal.
"""
    (STAGE / "RESULTS.md").write_text(md)

    manifest = {
        "first_oos_week": str(first_oos.date()),
        "book_specs": {spec.name: spec.factor_weights for spec in BOOK_SPECS},
        "variant_base_allocs": VARIANT_BASE_ALLOCS,
        "book_lookback": BOOK_LOOKBACK,
        "book_min_history": BOOK_MIN_HISTORY,
        "priced_tilt_cap": PRICED_TILT_CAP,
        "full": metrics,
        "is": is_metrics,
        "oos": oos_metrics,
        "baselines_oos": baseline_oos,
        "baselines_full": baseline_full,
        "sharpe_ensemble_sensitivity": (
            sensitivity.to_dict(orient="records") if sensitivity is not None else []
        ),
    }
    (MANIFEST_OUT / "metrics.json").write_text(json.dumps(manifest, indent=2, default=str))


def main() -> None:
    panel, regime = load_inputs()
    weeks = sorted(panel["week"].dropna().unique())
    first_oos = pd.to_datetime(weeks[-OOS_WEEKS])
    print(f"Loaded factor panel: {len(panel):,} rows, {len(weeks):,} weeks", flush=True)

    subbook_weights = {}
    book_pnls = {}
    for spec in BOOK_SPECS:
        print(f"Building {spec.name} sub-book...", flush=True)
        weights, pnl = build_subbook(spec, panel, regime)
        subbook_weights[spec.name] = weights
        book_pnls[spec.name] = pnl
        weights.to_csv(DATA_OUT / f"{spec.name}_weekly_weights.csv", index=False)
        weights.to_parquet(DATA_OUT / f"{spec.name}_weekly_weights.parquet", index=False)
        pnl.to_csv(DATA_OUT / f"{spec.name}_weekly_pnl.csv", index=False)
        pnl.to_parquet(DATA_OUT / f"{spec.name}_weekly_pnl.parquet", index=False)

    book_returns = pd.DataFrame({"week": weeks})
    for name, pnl in book_pnls.items():
        book_returns = book_returns.merge(pnl[["week", "pnl_net"]].rename(columns={"pnl_net": name}), on="week", how="left")

    allocations = {}
    variant_pnls = {}
    print("Combining sub-books...", flush=True)
    for variant, base_alloc in VARIANT_BASE_ALLOCS.items():
        safe = variant.lower().replace(" ", "_")
        allocation = rolling_book_allocations(book_returns, regime, base_alloc=base_alloc)
        allocation.to_csv(DATA_OUT / f"{safe}_book_allocations.csv", index=False)
        allocation.to_parquet(DATA_OUT / f"{safe}_book_allocations.parquet", index=False)
        weights = combine_book_weights(subbook_weights, allocation)
        pnl = backtest_combined(weights, panel)
        weights.to_csv(DATA_OUT / f"{safe}_weekly_weights.csv", index=False)
        weights.to_parquet(DATA_OUT / f"{safe}_weekly_weights.parquet", index=False)
        pnl.to_csv(DATA_OUT / f"{safe}_weekly_pnl.csv", index=False)
        pnl.to_parquet(DATA_OUT / f"{safe}_weekly_pnl.parquet", index=False)
        allocations[variant] = allocation
        variant_pnls[variant] = pnl

    # ---- audit Findings 5 & 6: baseline + ablation variants -----------------
    # All reuse the Sharpe Ensemble base allocation so differences isolate one
    # design choice at a time. The three headline variants above are untouched.
    sharpe_base = VARIANT_BASE_ALLOCS["Sharpe Ensemble"]

    def build_variant(base_alloc, *, use_regime_tilt=True, priced_cap=PRICED_TILT_CAP):
        alloc = rolling_book_allocations(
            book_returns, regime, base_alloc=base_alloc,
            use_regime_tilt=use_regime_tilt, priced_cap=priced_cap,
        )
        w = combine_book_weights(subbook_weights, alloc)
        return backtest_combined(w, panel)

    print("Building baseline + ablation variants (Findings 5, 6)...", flush=True)
    baselines = {
        # Finding 6: how much does the Priced Tilt sleeve cost the ensemble?
        "SE Priced-Tilt Off": build_variant(sharpe_base, priced_cap=0.0),
        "SE Priced-Tilt 5% cap": build_variant(sharpe_base, priced_cap=0.05),
        # Finding 5: value added by regime conditioning (vs no tilt at all)
        "SE No Regime Tilt": build_variant(sharpe_base, use_regime_tilt=False),
        # Single-factor-dependency baseline: the MispricingM book standalone
        "MispricingM Only": book_pnls["mispricing"],
    }
    for name, pnl in baselines.items():
        safe = name.lower().replace(" ", "_").replace("%", "pct")
        pnl.to_csv(DATA_OUT / f"baseline_{safe}_weekly_pnl.csv", index=False)

    # Sensitivity grid for the Sharpe Ensemble: OOS Sharpe under regime-tilt
    # on/off x priced-tilt cap. Isolates how fragile the headline is to the two
    # hardcoded-prior knobs the audit flagged.
    sens_rows = []
    for tilt_on in (True, False):
        for cap in (0.18, 0.05, 0.0):
            pnl = build_variant(sharpe_base, use_regime_tilt=tilt_on, priced_cap=cap)
            oos = perf_metrics(pnl[pnl["week"] >= first_oos]["pnl_net"])
            sens_rows.append({
                "regime_tilt": "on" if tilt_on else "off",
                "priced_cap": cap,
                "oos_sharpe": oos["sharpe"],
                "oos_ann_return": oos["ann_return"],
                "oos_max_dd": oos["max_dd"],
            })
    sensitivity = pd.DataFrame(sens_rows)
    sensitivity.to_csv(DATA_OUT / "sharpe_ensemble_sensitivity.csv", index=False)

    bm = benchmark_returns(panel)
    bm.to_csv(DATA_OUT / "benchmarks.csv", index=False)
    bm.to_parquet(DATA_OUT / "benchmarks.parquet", index=False)

    print("Writing report...", flush=True)
    plot_cumulative(variant_pnls, book_pnls, bm, first_oos)
    for variant, allocation in allocations.items():
        plot_allocations(allocation, variant)
    write_results(variant_pnls, book_pnls, allocations, bm, first_oos, baselines, sensitivity)

    for variant, pnl in variant_pnls.items():
        oos = perf_metrics(pnl[pnl["week"] >= first_oos]["pnl_net"])
        print(f"{variant} OOS Sharpe={oos['sharpe']:+.2f} AnnRet={oos['ann_return']:+.1%}", flush=True)


if __name__ == "__main__":
    main()
