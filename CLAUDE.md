# Artemis Track 1 — Claude Code Project Instructions

## Memory rule
After any major push (new stage, significant result change, new methodology, or report update), **update `MEMORY.md`** with what changed. This is the canonical project state file — keep it current.

## Key files
- `MEMORY.md` — current project state, results, and pipeline status
- `AGENTS.md` — full context reference (methodology, factors, data sources, stage-by-stage detail)
- `16_reports/Artemis_Track1_Research_Report.md` — final competition report
- `17_presentation_slides/` — HTML presentation deck (in progress)

## Production pipeline (run order)
```
09_nalfp_add/03_reconstruct_mcap_panel.py
09_nalfp_add/05_returns_and_reference.py
09_nalfp_add/06_sparse_pca.py
09_nalfp_add/09c_gx_pricing_full.py   ← use this, NOT 09_gx_pricing.py (deprecated)
09_nalfp_add/08_factor_validation.py
10_behavioral_gx/01_behavioral_gx_search.py
15_factor_ensemble_strategy/run.py
```

## Critical conventions
- `09_gx_pricing.py` is **deprecated** — wrong standard errors. Always use `09c_gx_pricing_full.py`.
- Stablecoins, wrapped assets, and bridged duplicates are excluded from the universe.
- The behavioral factor search (Stage 10) requires both Bonferroni AND Benjamini-Hochberg correction to pass.
- Market cap before ~2025 is reconstructed — drift clamped to −3%/yr to +50%/yr per-day.
- For full methodology context, read `agents.md` before making changes.
