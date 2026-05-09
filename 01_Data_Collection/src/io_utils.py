from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)


def write_table(df: pd.DataFrame, base_path_no_ext: Path, *, write_csv: bool, write_parquet: bool) -> None:
    base_path_no_ext.parent.mkdir(parents=True, exist_ok=True)
    if write_csv:
        df.to_csv(base_path_no_ext.with_suffix(".csv"), index=False)
    if write_parquet:
        df.to_parquet(base_path_no_ext.with_suffix(".parquet"), index=False)
