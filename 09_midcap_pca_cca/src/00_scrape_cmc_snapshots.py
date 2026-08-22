#!/usr/bin/env python3
"""Scrape CoinMarketCap weekly historical snapshot pages for point-in-time rankings.

Uses Playwright with playwright-stealth and anti-bot countermeasures:
- Stealth mode to hide automation fingerprints
- Randomised User-Agent rotation via fake-useragent
- Auto-scroll to force lazy-loading of all table rows
- Jittered inter-request delays

Output: data/clean/cmc_rankings_weekly.parquet
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from utils.data_io import (
    clean_dir,
    ensure_dir,
    get_logger,
    load_settings,
    raw_dir,
    write_parquet,
)

PROJ_ROOT = Path(__file__).resolve().parent.parent


def generate_snapshot_dates(start_date: str, end_date: str | None = None) -> list[str]:
    start = datetime.strptime(start_date, "%Y%m%d")
    if end_date is None:
        end = datetime.utcnow()
    else:
        end = datetime.strptime(end_date, "%Y%m%d")
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=7)
    return dates


def parse_numeric(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = re.sub(r"[$,\s%]", "", str(value))
    cleaned = re.sub(r"[*]", "", cleaned)
    cleaned = re.sub(r"\s+[A-Za-z]+$", "", cleaned)
    if cleaned in ("", "--", "N/A", "NaN", "-"):
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        match = re.match(r"[-+]?[\d.]+", cleaned)
        if match:
            try:
                return float(match.group())
            except (ValueError, TypeError):
                return None
        return None


async def scrape_snapshot(
    page: Any,
    date_str: str,
    logger: Any,
) -> list[dict[str, Any]]:
    url = f"https://coinmarketcap.com/historical/{date_str}/"
    logger.info("Navigating to %s", url)

    try:
        await page.goto(url, wait_until="networkidle", timeout=60000)
    except Exception as exc:
        logger.warning("Failed to load page for %s: %s", date_str, exc)
        return []

    for _ in range(10):
        prev_height = await page.evaluate("document.body.scrollHeight")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == prev_height:
            break

    rows = await page.query_selector_all("table tbody tr")
    if not rows:
        rows = await page.query_selector_all('div[data-role="table"] tr')
    if not rows:
        rows = await page.query_selector_all("table.cmc-table tbody tr")

    results: list[dict[str, Any]] = []
    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) < 6:
            continue

        try:
            rank_text = await cells[0].inner_text()
            name_text = await cells[1].inner_text()
            symbol_text = await cells[2].inner_text()
            mcap_text = await cells[3].inner_text()
            price_text = await cells[4].inner_text()
            circ_supply_text = (
                await cells[5].inner_text() if len(cells) > 5 else None
            )
            vol_text = (
                await cells[6].inner_text() if len(cells) > 6 else None
            )
            change_7d_text = (
                await cells[9].inner_text() if len(cells) > 9 else None
            )
        except Exception:
            continue

        rank = parse_numeric(rank_text)
        if rank is None:
            continue

        results.append(
            {
                "snapshot_date": date_str,
                "rank": int(rank),
                "name": name_text.strip() if name_text else None,
                "symbol": symbol_text.strip() if symbol_text else None,
                "market_cap_usd": parse_numeric(mcap_text),
                "price_usd": parse_numeric(price_text),
                "volume_24h_usd": parse_numeric(vol_text),
                "circulating_supply": parse_numeric(circ_supply_text),
                "change_7d_pct": parse_numeric(change_7d_text),
            }
        )

    return results


async def scrape_all_snapshots(
    dates: list[str],
    headless: bool,
    min_delay: float,
    max_delay: float,
    min_rows: int,
    logger: Any,
) -> list[dict[str, Any]]:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
    from fake_useragent import UserAgent

    ua = UserAgent()
    stealth = Stealth()
    all_rows: list[dict[str, Any]] = []
    failed_dates: list[str] = []
    low_row_dates: list[str] = []

    async with stealth.use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context = await browser.new_context(
            user_agent=ua.random,
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        for i, date_str in enumerate(dates):
            cache_path = raw_dir() / "cmc_snapshots" / f"{date_str}.json"
            if cache_path.exists():
                logger.info("[%d/%d] Cache hit for %s", i + 1, len(dates), date_str)
                try:
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                    all_rows.extend(cached)
                except Exception:
                    logger.warning("Failed to read cache for %s", date_str)
                continue

            snapshot_rows = await scrape_snapshot(page, date_str, logger)
            if not snapshot_rows:
                failed_dates.append(date_str)
                logger.warning("No rows scraped for %s", date_str)
            elif len(snapshot_rows) < min_rows:
                low_row_dates.append(date_str)
                logger.warning(
                    "Low row count for %s: %d (min=%d)",
                    date_str,
                    len(snapshot_rows),
                    min_rows,
                )
                all_rows.extend(snapshot_rows)
                ensure_dir(cache_path.parent)
                cache_path.write_text(
                    json.dumps(snapshot_rows, default=str), encoding="utf-8"
                )
            else:
                logger.info(
                    "[%d/%d] Scraped %s: %d rows",
                    i + 1,
                    len(dates),
                    date_str,
                    len(snapshot_rows),
                )
                all_rows.extend(snapshot_rows)
                ensure_dir(cache_path.parent)
                cache_path.write_text(
                    json.dumps(snapshot_rows, default=str), encoding="utf-8"
                )

            delay = random.uniform(min_delay, max_delay)
            logger.info("Sleeping %.1fs", delay)
            await asyncio.sleep(delay)

        await browser.close()

    logger.info(
        "Scraping complete. Total=%d, Failed=%d, LowRow=%d",
        len(all_rows),
        len(failed_dates),
        len(low_row_dates),
    )
    if failed_dates:
        logger.warning("Failed dates: %s", failed_dates)
    if low_row_dates:
        logger.warning("Low-row dates: %s", low_row_dates)

    return all_rows


def main() -> None:
    import asyncio as _asyncio

    logger = get_logger("cmc_scraper")
    settings = load_settings()
    cmc_cfg = settings.get("cmc", {})
    paths_cfg = settings.get("paths", {})

    start_date = cmc_cfg.get("start_date", "20210103")
    dates = generate_snapshot_dates(start_date)

    headless = cmc_cfg.get("headless", True)
    min_delay = float(cmc_cfg.get("min_delay", 3.0))
    max_delay = float(cmc_cfg.get("max_delay", 7.0))
    min_rows = int(cmc_cfg.get("min_rows_per_snapshot", 80))

    logger.info("Total snapshot dates to scrape: %d", len(dates))

    all_rows = _asyncio.run(
        scrape_all_snapshots(dates, headless, min_delay, max_delay, min_rows, logger)
    )

    if not all_rows:
        logger.error("No data scraped. Exiting.")
        sys.exit(1)

    df = pd.DataFrame(all_rows)
    for col in ["market_cap_usd", "price_usd", "volume_24h_usd", "circulating_supply", "change_7d_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.drop_duplicates(subset=["snapshot_date", "symbol"], keep="first")
    df = df.sort_values(["snapshot_date", "rank"]).reset_index(drop=True)

    out_path = clean_dir() / "cmc_rankings_weekly.parquet"
    ensure_dir(out_path.parent)
    write_parquet(df, out_path)
    logger.info("Wrote %d rows to %s", len(df), out_path)

    summary = (
        df.groupby("snapshot_date")
        .agg(n_rows=("rank", "count"), rank_max=("rank", "max"))
        .reset_index()
    )
    logger.info("Per-snapshot summary:\n%s", summary.to_string(index=False))


if __name__ == "__main__":
    main()