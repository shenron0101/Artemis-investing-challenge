from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from clients import (
    ArtemisClient,
    BinanceClient,
    CoinGeckoClient,
    DefiLlamaClient,
    DefiLlamaStablecoinsClient,
)
from logging_utils import get_logger
from pipeline import DataCollectionPipeline, PipelineSettings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect large-cap + top-100-below-large data")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Path to 01_Data_Collection root",
    )
    parser.add_argument(
        "--coins-file",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "Coins.md",
        help="Path to Coins.md",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "settings.yaml",
        help="Path to settings yaml",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")

    root = args.root.resolve()
    settings = PipelineSettings.from_yaml(args.settings.resolve())
    logger = get_logger(root / "data" / "logs" / "pipeline.log")

    cg_key = os.getenv("COINGECKO_API_KEY")
    cg_base_url = os.getenv("COINGECKO_BASE_URL", "https://pro-api.coingecko.com/api/v3")

    artemis_key = os.getenv("ARTEMIS_API_KEY")
    artemis_base_url = os.getenv("ARTEMIS_BASE_URL", "https://data-svc.artemisxyz.com")

    binance_base_url = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")

    cg_client = CoinGeckoClient(
        api_key=cg_key,
        base_url=cg_base_url,
        sleep_seconds=float(settings.cfg["coingecko"]["request_sleep_seconds"]),
    )

    binance_client = BinanceClient(
        base_url=binance_base_url,
        sleep_seconds=0.2,
    )

    artemis_client = None
    if artemis_key:
        artemis_client = ArtemisClient(
            api_key=artemis_key,
            base_url=artemis_base_url,
            sleep_seconds=float(settings.cfg["artemis"]["request_sleep_seconds"]),
        )
    else:
        logger.warning("ARTEMIS_API_KEY not set. Artemis pulls will be skipped.")

    defillama_client = None
    defillama_stable_client = None
    if settings.cfg.get("defillama", {}).get("enabled", True):
        sleep_s = float(settings.cfg.get("defillama", {}).get("request_sleep_seconds", 0.4))
        defillama_client = DefiLlamaClient(
            base_url=os.getenv("DEFILLAMA_BASE_URL", "https://api.llama.fi"),
            sleep_seconds=sleep_s,
        )
        if settings.cfg.get("defillama", {}).get("pull_stablecoins", False):
            defillama_stable_client = DefiLlamaStablecoinsClient(
                base_url=os.getenv("DEFILLAMA_STABLECOINS_BASE_URL", "https://stablecoins.llama.fi"),
                sleep_seconds=sleep_s,
            )

    pipeline = DataCollectionPipeline(
        root=root,
        settings=settings,
        logger=logger,
        coingecko_client=cg_client,
        binance_client=binance_client,
        artemis_client=artemis_client,
        defillama_client=defillama_client,
        defillama_stable_client=defillama_stable_client,
    )

    pipeline.run(args.coins_file.resolve())


if __name__ == "__main__":
    main()
