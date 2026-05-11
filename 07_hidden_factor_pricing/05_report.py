"""05 - Generate Stage 06 markdown report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MANIFEST_DIR, ROOT, STAGE, TABLE_DIR

REPORT_PATH = STAGE / "REPORT.md"


def _num(value: float, digits: int = 3) -> str:
    return "n/a" if pd.isna(value) else f"{value:.{digits}f}"


def _pct(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2%}"


def _link(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _premia_table(premia: pd.DataFrame) -> str:
    rows = ["| Model | Factor | Weekly lambda | t-stat | p-value |", "|---|---:|---:|---:|---:|"]
    shown = premia.loc[~premia["factor"].astype(str).str.startswith("latent_")].copy()
    shown = shown.sort_values(["factor", "model"])
    for row in shown.itertuples(index=False):
        rows.append(
            f"| {row.model} | `{row.factor}` | {_pct(row.lambda_weekly)} | {_num(row.t_stat)} | {_num(row.p_value_normal)} |"
        )
    return "\n".join(rows)


def _survival_lines(survival: pd.DataFrame) -> str:
    if survival.empty:
        return "- No observed factors had enough overlap for the survival comparison."
    lines = []
    for row in survival.sort_values("factor").itertuples(index=False):
        verdict = "survives" if row.survives_latent_controls_10pct_rule else "does not survive"
        lines.append(
            f"- `{row.factor}` {verdict}: FMB t={_num(row.fmb_t_stat)}, latent-adjusted t={_num(row.latent_adjusted_t_stat)}, delta={_pct(row.lambda_delta)}."
        )
    return "\n".join(lines)


def main() -> None:
    panel_manifest = json.loads((MANIFEST_DIR / "01_panel_manifest.json").read_text(encoding="utf-8"))
    factor_manifest = json.loads((MANIFEST_DIR / "02_observed_factors_manifest.json").read_text(encoding="utf-8"))
    input_manifest = json.loads((MANIFEST_DIR / "03_external_inputs_manifest.json").read_text(encoding="utf-8"))
    model_manifest = json.loads((MANIFEST_DIR / "04_price_models_manifest.json").read_text(encoding="utf-8"))
    premia = pd.read_parquet(TABLE_DIR / "04_factor_premia.parquet")
    survival = pd.read_parquet(TABLE_DIR / "04_factor_survival.parquet")

    text = f"""# Stage 06 - Hidden Factor Pricing

This stage implements a repo-native version of `Crypto Pricing with Hidden Factors`.
It compares observed crypto factors against the same factors after PCA latent-return controls are added to the Fama-MacBeth cross-section.

## Data Window
- Rows: {panel_manifest["rows"]:,}
- Symbols: {panel_manifest["symbols"]:,}
- Weeks: {panel_manifest["weeks"]:,}
- Dates: {panel_manifest["start_week"]} to {panel_manifest["end_week"]}
- Scope: raw weekly crypto returns from clean repo data; no risk-free, Kenneth French, CVX, Fear & Greed, Altseason, or hack-loss series are bundled.

## Observed Factors
- Columns: {", ".join(f"`{col}`" for col in factor_manifest["factor_columns"])}
- Market is value-weighted by lagged market cap.
- SMB is small-minus-big by lagged market cap.
- Momentum is winner-minus-loser using prior five-week cumulative return.
- TVL is high-minus-low by lagged TVL / market cap and is also market-orthogonalized as `crypto_tvl_orth`.

## External Inputs
Default regime inputs are repo-native proxies: {", ".join(f"`{col}`" for col in input_manifest["native_proxy_columns"])}.
Paper-parity CSVs can be added under `06_hidden_factor_pricing/inputs/`; loaded files are tracked in `{_link(MANIFEST_DIR / "03_external_inputs_manifest.json")}`.

## Scope of This Test
This is an **in-sample asset-pricing inference test**, not a predictive backtest. Following Giglio & Xiu, the latent factor SVD is fit on the full panel and the same panel is priced — appropriate for testing whether observed factor premia survive latent controls, not for trading. The t-stats below cannot be read as out-of-sample alpha.

## Pricing Results
{_premia_table(premia)}

## Latent-Control Survival
{_survival_lines(survival)}

The survival rule is intentionally simple: the latent-adjusted premium must keep the Fama-MacBeth sign and have |t| >= 1.65. This is a diagnostic threshold, not a claim of strict paper parity.

_Caveat: latent factors are extracted from the full sample; survival here means in-sample robustness, not predictive survival._

## Links Back To Artemis
- `04_factors/04_RAAM_v2_composite.py` remains the cross-sectional signal layer for M/V/C/T plus F/S/G. Stage 06 tests whether broad crypto factor premia remain visible once latent return structure is included.
- `05_btc_direction/04_train_eval.py` remains the supervised BTC-direction layer. Stage 06 is inference-first and does not feed that classifier automatically.

## Outputs
- Weekly panel: `{_link(TABLE_DIR.parent / "data" / "weekly_asset_panel.parquet")}`
- Observed factors: `{_link(TABLE_DIR.parent / "data" / "observed_factor_returns.parquet")}`
- Factor premia: `{_link(TABLE_DIR / "04_factor_premia.parquet")}`
- Survival table: `{_link(TABLE_DIR / "04_factor_survival.parquet")}`

## Method Note
{model_manifest["method_note"]}
"""
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    print("done.")


if __name__ == "__main__":
    main()
