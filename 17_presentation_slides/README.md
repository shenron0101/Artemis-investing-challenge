# Stage 17 — Presentation Deck

A 13-slide PowerPoint deck for the Artemis Track 1 submission, told as a narrative
(problem → thesis → evidence → result → honesty → close) rather than a restatement
of the report. Audience: quant judges, ~10–15 min.

## Deliverables
- `16_reports/Artemis_Track1_Presentation.pptx` — the editable PowerPoint deck
- `16_reports/Artemis_Track1_Presentation.pdf` — flattened PDF (rendered from the pptx)

## Files here
- `build_pptx.py` — generates the `.pptx` (native, editable shapes + embedded charts)
- `assets/make_charts.py` — regenerates the quantitative charts from Stage 15 `metrics.json`
- `assets/figures/` — charts used by the deck

## Rebuild the deck
```bash
../.venv/bin/python assets/make_charts.py   # (re)generate charts — optional
../.venv/bin/python build_pptx.py           # writes 16_reports/Artemis_Track1_Presentation.pptx
```
`build_pptx.py` uses `python-pptx`; conceptual slides (problem cards, thesis pillars,
validation gates, architecture flow) are native shapes so they stay editable in
PowerPoint / Keynote / Google Slides.

## Refresh the companion PDF (optional)
```bash
libreoffice --headless --convert-to pdf --outdir ../16_reports \
  ../16_reports/Artemis_Track1_Presentation.pptx
```

## Charts
`make_charts.py` reads `15_factor_ensemble_strategy/artifacts/manifests/metrics.json`
(full/IS/OOS, ablation baselines, sensitivity grid). The IS/OOS factor-dashboard images
(`*_is_oos.png`, `mispr_cumulative.png`) are copied from the committed Stage 12 figures.

## Note on figures
The report references a cumulative-returns curve, book-allocation, and XGBoost-regime
figures produced by `15_/14_` `run.py` that were never committed. A faithful re-run is
blocked in this environment (missing `~/.hermes/.env` API keys for Artemis/FRED, and the
Stage 08 `network_panel.parquet` that Stage 14 consumes). Rather than fabricate a return
series, the hero slide uses a metrics-based OOS comparison (Sharpe + return + drawdown,
all from `metrics.json`) plus the committed MispricingM dashboard. If the keys / Stage 08
panel become available, re-running the pipeline would let us swap in the true equity curve.
