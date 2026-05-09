from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

SECTION_LARGE = re.compile(r"^#\s*1\.\s*All Large-Cap", re.IGNORECASE)
SECTION_MID_STRICT = re.compile(r"^##\s*2\.1\s*Strict Mid-Caps", re.IGNORECASE)
SECTION_BELOW_LARGE = re.compile(r"^##\s*2\.2\s*Additional Next-Largest", re.IGNORECASE)


def _is_separator_row(parts: list[str]) -> bool:
    return all(set(p.replace(":", "").strip()) <= {"-"} for p in parts)


def load_universe_from_markdown(coins_md_path: Path) -> pd.DataFrame:
    if not coins_md_path.exists():
        raise FileNotFoundError(f"Coins markdown not found: {coins_md_path}")

    current_cohort: str | None = None
    rows: list[dict[str, object]] = []

    lines = coins_md_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if SECTION_LARGE.search(line):
            current_cohort = "large_cap"
            continue
        if SECTION_MID_STRICT.search(line):
            current_cohort = "mid_cap_strict"
            continue
        if SECTION_BELOW_LARGE.search(line):
            current_cohort = "below_large_top100_ext"
            continue

        if not line.strip().startswith("|"):
            continue
        if current_cohort is None:
            continue

        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 3:
            continue
        if _is_separator_row(parts):
            continue

        if current_cohort == "large_cap":
            if not parts[0].isdigit():
                continue
            rows.append(
                {
                    "overall_rank": int(parts[0]),
                    "cohort_rank": int(parts[0]),
                    "coin_name": parts[1],
                    "symbol": parts[2].upper(),
                    "cohort": current_cohort,
                }
            )
        else:
            if len(parts) < 4 or not parts[0].isdigit() or not parts[1].isdigit():
                continue
            rows.append(
                {
                    "overall_rank": int(parts[0]),
                    "cohort_rank": int(parts[1]),
                    "coin_name": parts[2],
                    "symbol": parts[3].upper(),
                    "cohort": current_cohort,
                }
            )

    if not rows:
        raise ValueError("No coin rows parsed from Coins.md")

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["symbol", "coin_name", "cohort"]).sort_values(
        by=["overall_rank", "cohort_rank"]
    )
    return df.reset_index(drop=True)
