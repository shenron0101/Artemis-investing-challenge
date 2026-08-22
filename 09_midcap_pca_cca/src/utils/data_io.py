from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_settings(config_path: Path | None = None) -> dict[str, Any]:
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent.parent / "config" / "settings.yaml"
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def data_dir() -> Path:
    return project_root() / "data"


def raw_dir() -> Path:
    return project_root() / "data" / "raw"


def clean_dir() -> Path:
    return project_root() / "data" / "clean"


def features_dir() -> Path:
    return project_root() / "data" / "features"


def artifacts_dir() -> Path:
    return project_root() / "artifacts"


def manifests_dir() -> Path:
    return project_root() / "artifacts" / "manifests"


def figures_dir() -> Path:
    return project_root() / "artifacts" / "figures"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def stable_hash(data: str, length: int = 12) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:length]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    df.to_parquet(path, engine="pyarrow", index=False)


def read_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path, engine="pyarrow")


def write_manifest(manifest: dict[str, Any], name: str) -> None:
    path = manifests_dir() / name
    ensure_dir(path.parent)
    write_json(path, manifest)


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    return logger