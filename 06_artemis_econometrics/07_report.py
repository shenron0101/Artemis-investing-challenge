"""07 — Generate REPORT.md from the latest run artefacts.

The report is intentionally short and competition-facing: it shows the model
summary table, the per-feature Fama-MacBeth t-stats, and pointers to the
plotly diagnostics that ship with the run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MANIFEST_DIR, STAGE, TABLE_DIR

REPORT_PATH = STAGE / "REPORT.md"


def to_md_table(df: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub markdown table without tabulate."""
    if df is None or df.empty:
        return "_empty_"
    headers = list(df.columns)
    rows = [list(map(str, r)) for r in df.itertuples(index=False, name=None)]
    header_row = "| " + " | ".join(headers) + " |"
    sep_row = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_rows = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([header_row, sep_row, *body_rows])


def _maybe_read(path: Path) -> pd.DataFrame | None:
    if path.exists():
        return pd.read_parquet(path)
    return None


def fmt_summary(summary: pd.DataFrame) -> str:
    if summary is None or summary.empty:
        return "_no model summary table found_"
    cols = ["model", "ic_mean", "ic_ir", "ls_mean", "ls_sharpe_annual", "turnover_mean", "alpha", "t_alpha", "n"]
    cols = [c for c in cols if c in summary.columns]
    show = summary[cols].copy()
    if "n" in show.columns:
        show["n"] = show["n"].map(lambda v: str(int(v)) if pd.notna(v) else "—")
    for c in show.select_dtypes(include="float").columns:
        show[c] = show[c].map(lambda v: f"{v:+.4f}" if pd.notna(v) else "—")
    return to_md_table(show)


def fmt_betas(betas: pd.DataFrame) -> str:
    if betas is None or betas.empty:
        return "_no betas table_"
    show = betas.copy()
    for c in show.select_dtypes(include="float").columns:
        show[c] = show[c].map(lambda v: f"{v:+.4f}" if pd.notna(v) else "—")
    show.columns = [str(c) for c in show.columns]
    return to_md_table(show)


def fmt_fm_tstats(manifest: Path) -> str:
    if not manifest.exists():
        return "_no models manifest_"
    obj = json.loads(manifest.read_text())
    ts = obj.get("fm_t_stats") or {}
    if not ts:
        return "_no FM t-stats_"
    rows = pd.DataFrame({"feature": list(ts.keys()), "t_stat": list(ts.values())})
    rows["t_stat"] = rows["t_stat"].map(lambda v: f"{v:+.2f}" if v is not None else "—")
    return to_md_table(rows)


def fmt_diag_lines(manifest: Path) -> str:
    if not manifest.exists():
        return ""
    obj = json.loads(manifest.read_text())
    rows = []
    for key in ("cutoff_week", "n_train_weeks", "n_test_weeks"):
        if key in obj:
            rows.append(f"- **{key}**: {obj[key]}")
    return "\n".join(rows)


def main() -> None:
    summary = _maybe_read(TABLE_DIR / "model_summary.parquet")
    betas = _maybe_read(TABLE_DIR / "model_betas.parquet")
    models_manifest = MANIFEST_DIR / "05_models_manifest.json"

    text = f"""# Stage 06 — Artemis Econometrics: Run Report

## Setup

{fmt_diag_lines(models_manifest)}

## Model Comparison (out-of-sample)

{fmt_summary(summary)}

Reading the table:
- `ic_mean` — mean weekly Spearman correlation between predicted ranking and realized next-week return.
- `ic_ir` — IC mean divided by IC std (information ratio of the ranking signal).
- `ls_mean` — mean weekly Q5 minus Q1 log return.
- `ls_sharpe_annual` — annualised Sharpe of the long-short portfolio (√52).
- `turnover_mean` — average week-on-week churn fraction in the top quintile.
- `alpha` / `t_alpha` — intercept of long-short return regressed on equal-weight market return (no contemporaneous momentum control).

_`base_lasso` (ElasticNetCV) removed this iteration — degenerate (all-zero) coefficients on 36 weeks × 12 features; kept as a known limitation rather than tuned._

## Fama-MacBeth t-stats (base characteristics)

{fmt_fm_tstats(models_manifest)}

These t-stats use the time-series of weekly cross-sectional slopes on the training window. They tell us which Artemis-style characteristics actually drove the cross-section before adding latent / network adjustments.

## Coefficients across models

{fmt_betas(betas)}

## Figures

- `figures/06_backtest/01_cumulative_long_short.html` — cumulative Q5-Q1 trajectory by model.
- `figures/06_backtest/02_ic_distribution.html` — weekly IC distribution by model.

## Next Iteration Ideas

- Replace the rolling-correlation cluster with a Granger-style predictive link network and re-run the `plus_net` model.
- Swap the single-shot train/test split for a rolling (expanding) walk-forward fit when compute allows.
- Add a perp basis / funding-rate feature once that feed lands in `01_Data_Collection/data/clean/`.
- Repeat the comparison on `residual_ret` (latent-factor adjusted) as the target — this directly tests whether Artemis characteristics carry signal *beyond* common crypto risks.
"""
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {REPORT_PATH.relative_to(STAGE.parent)}")


if __name__ == "__main__":
    main()
