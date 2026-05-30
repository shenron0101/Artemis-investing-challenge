"""09 — Stage 1 / Task 4: freeze the tiered universe to a manifest.

Consumes the coverage tables (01, 02) and the reconstructed panel (03) and
writes one authoritative manifest describing the two universes Goal 1 defines:

    * estimation_backbone  — coins with deep, continuous history. Used as the
      *balanced* matrix for the Sparse PCA / CCA latent-factor estimation
      (Goal 2). Frozen membership; common-start so the matrix is rectangular.

    * trading_universe      — point-in-time, market-cap-ranked, entry/exit
      allowed. NOT a fixed survivor set: a coin is eligible in week t once it
      has >= MIN_TRAIL_WEEKS of trailing price (enough to compute momentum /
      vol / size characteristics). This is what avoids survivorship bias.

The manifest records inclusion rules, per-coin coverage, the chosen
in-sample / out-of-sample split, and the data-source / mcap-tier provenance, so
the whole universe is reproducible and auditable.

Output
------
    artifacts/manifests/universe_manifest.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
DATA_DIR = STAGE / "artifacts" / "data"
MANIFEST_DIR = STAGE / "artifacts" / "manifests"

# commodity-backed tokens (track gold, not crypto risk) — excluded from a crypto
# factor universe even though they are neither stable nor wrapped.
COMMODITY_PROXIES = {"PAXG", "XAUT"}

# ---- inclusion rules (the knobs that define the universes) ----
BACKBONE_MIN_YEARS = 5.0     # deep-history threshold for the estimation backbone
BACKBONE_MIN_WEEKS = 200     # success-criterion floor on weekly observations
MIN_TRAIL_WEEKS = 12         # trailing history a coin needs before it can trade
OOS_FRACTION = 0.30          # fraction of the common-start span reserved for OOS


def _jsonable(v):
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d")
    if pd.isna(v):
        return None
    return v


def main() -> None:
    cov = pd.read_parquet(DATA_DIR / "universe_coverage_full.parquet")
    panel = pd.read_parquet(DATA_DIR / "price_mcap_panel_weekly.parquet")
    panel["week"] = pd.to_datetime(panel["week"])

    # weekly-obs count per coin actually present in the reconstructed panel
    obs = panel.groupby("symbol")["week"].nunique().rename("panel_weeks")
    first_wk = panel.groupby("symbol")["week"].min().rename("panel_first_week")
    cov = cov.merge(obs, left_on="symbol", right_index=True, how="left")
    cov = cov.merge(first_wk, left_on="symbol", right_index=True, how="left")

    cov["is_commodity"] = cov["symbol"].isin(COMMODITY_PROXIES)
    eligible = cov[(~cov["is_stable_or_wrapped"]) & (~cov["is_commodity"])
                   & cov["binance_pair"].notna()].copy()

    # ---- estimation backbone: deep + continuous + enough weekly obs ----
    backbone = eligible[(eligible["years_history"] >= BACKBONE_MIN_YEARS)
                        & (eligible["panel_weeks"] >= BACKBONE_MIN_WEEKS)].copy()
    backbone_syms = sorted(backbone["symbol"].tolist())

    # common start where ALL backbone coins are simultaneously live (balanced matrix)
    common_start = panel[panel["symbol"].isin(backbone_syms)].groupby("symbol")["week"].min().max()
    last_week = panel["week"].max()
    bal = panel[(panel["symbol"].isin(backbone_syms)) & (panel["week"] >= common_start)]
    n_common_weeks = int(bal["week"].nunique())

    # ---- in-sample / out-of-sample split from the common-start span ----
    weeks_sorted = sorted(bal["week"].unique())
    split_idx = int(len(weeks_sorted) * (1 - OOS_FRACTION))
    is_end = pd.Timestamp(weeks_sorted[split_idx - 1])
    oos_start = pd.Timestamp(weeks_sorted[split_idx])

    # ---- trading universe membership (point-in-time, mcap-ranked) ----
    # eligible-in-week-t = has >= MIN_TRAIL_WEEKS trailing obs by week t.
    trade_syms = sorted(eligible["symbol"].tolist())
    wk_counts = (panel[panel["symbol"].isin(trade_syms)]
                 .sort_values("week")
                 .assign(n=lambda d: d.groupby("symbol").cumcount() + 1))
    live_by_week = (wk_counts[wk_counts["n"] >= MIN_TRAIL_WEEKS]
                    .groupby("week")["symbol"].nunique())

    tier_counts = eligible["mcap_tier"].value_counts().to_dict()

    manifest = {
        "stage": "09_nalfp_add",
        "built": pd.Timestamp.utcnow().tz_localize(None).strftime("%Y-%m-%d %H:%M UTC"),
        "candidate_pool": {
            "source": "Coins.md (CoinGecko snapshot 2026-05-08)",
            "n_total": int(len(cov)),
            "n_factor_eligible": int((~cov["is_stable_or_wrapped"]).sum()),
            "n_with_binance_pair": int(eligible.shape[0]),
        },
        "data_sources": {
            "price": "Binance daily klines (USDT>FDUSD>BUSD>USDC priority), 5y, gap-free",
            "market_cap": {
                "real_recent": "CoinGecko market_chart, last 365d (exact, covers OOS)",
                "real_full": "CoinMetrics CapMrktCurUSD where free (tier 1)",
                "estimated_deep": "price x growth-anchored circulating supply (tiers 2-3)",
            },
            "mcap_tier_counts": tier_counts,
        },
        "inclusion_rules": {
            "exclude": "stablecoins / wrapped / bridged + commodity proxies (PAXG, XAUT)",
            "commodity_proxies_excluded": sorted(COMMODITY_PROXIES),
            "backbone_min_years": BACKBONE_MIN_YEARS,
            "backbone_min_weeks": BACKBONE_MIN_WEEKS,
            "trading_min_trailing_weeks": MIN_TRAIL_WEEKS,
            "oos_fraction": OOS_FRACTION,
        },
        "estimation_backbone": {
            "n": len(backbone_syms),
            "symbols": backbone_syms,
            "common_start": _jsonable(common_start),
            "last_week": _jsonable(last_week),
            "balanced_weeks": n_common_weeks,
            "note": "balanced, frozen membership; rectangular matrix for Sparse PCA / CCA",
        },
        "split": {
            "common_start": _jsonable(common_start),
            "in_sample": [_jsonable(common_start), _jsonable(is_end)],
            "out_of_sample": [_jsonable(oos_start), _jsonable(last_week)],
            "in_sample_weeks": split_idx,
            "out_of_sample_weeks": len(weeks_sorted) - split_idx,
            "rationale": ("common_start is the earliest week all backbone coins are "
                          "simultaneously live; OOS is the most recent "
                          f"{int(OOS_FRACTION*100)}% of that balanced span."),
        },
        "trading_universe": {
            "n_ever_eligible": len(trade_syms),
            "symbols_ever_eligible": trade_syms,
            "members_at_last_week": int(live_by_week.get(last_week, 0)),
            "members_min": int(live_by_week.min()) if len(live_by_week) else 0,
            "members_max": int(live_by_week.max()) if len(live_by_week) else 0,
            "note": ("point-in-time, entry/exit allowed; eligible in week t once a "
                     "coin has >= trading_min_trailing_weeks of price history"),
        },
    }

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    out = MANIFEST_DIR / "universe_manifest.json"
    out.write_text(json.dumps(manifest, indent=2))
    print(f"  wrote {out.relative_to(ROOT)}")

    # also freeze the per-coin coverage actually used (audit trail)
    keep = ["symbol", "coin_name", "cohort", "binance_pair", "years_history",
            "pct_missing", "panel_weeks", "panel_first_week", "mcap_tier",
            "cm_mcap_available", "has_5y"]
    audit = cov[[c for c in keep if c in cov.columns]].sort_values("years_history", ascending=False)
    audit.to_csv(DATA_DIR / "universe_membership.csv", index=False)

    print("\n  ===== UNIVERSE MANIFEST SUMMARY =====")
    print(f"  estimation backbone : {len(backbone_syms)} coins, "
          f"{n_common_weeks} balanced weeks from {_jsonable(common_start)}")
    print(f"  IS / OOS split      : IS {_jsonable(common_start)}..{_jsonable(is_end)} "
          f"({split_idx}w)  |  OOS {_jsonable(oos_start)}..{_jsonable(last_week)} "
          f"({len(weeks_sorted)-split_idx}w)")
    print(f"  trading universe    : {len(trade_syms)} ever-eligible, "
          f"{manifest['trading_universe']['members_min']}–"
          f"{manifest['trading_universe']['members_max']} live per week")
    print(f"  backbone symbols    : {', '.join(backbone_syms)}")
    crit = n_common_weeks >= BACKBONE_MIN_WEEKS
    print(f"\n  success criterion (>= {BACKBONE_MIN_WEEKS} weekly obs for backbone): "
          f"{'PASS' if crit else 'FAIL'} ({n_common_weeks})")


if __name__ == "__main__":
    main()
