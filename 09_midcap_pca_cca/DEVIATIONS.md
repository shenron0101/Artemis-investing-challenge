# Deviations from Implementation Plan

1. **CMC scraping replaced by Artemis API**: CoinMarketCap historical pages use virtual scrolling (React), rendering only ~38 fully-populated table rows at a time. CMC also has aggressive Cloudflare protection. Per the plan's fallback provision, we switched from CMC scraping to using the **Artemis API** (`pip install artemis-xyz`) which provides point-in-time daily MARKET_CAP, PRICE, CIRCULATING_SUPPLY_NATIVE, and 24H_VOLUME for 1,013 assets. This is actually superior to CMC because it provides true daily historical data (not just weekly snapshots), is survivorship-bias-free, and doesn't require browser scraping.

2. **CoinGecko `/coins/markets` endpoint used for current top-200**: Still used for initial universe construction but supplemented by Artemis historical data.

3. **playwright-stealth API change**: The `stealth_async` import from `playwright_stealth` v2 no longer exists. Updated to use `Stealth().use_async(async_playwright())` pattern. (Now moot since CMC scraping is replaced.)

4. **Playwright chromium not installable on Ubuntu 26.04**: Used `channel="chrome"` to leverage the system-installed Google Chrome. (Now moot since CMC scraping is replaced.)

5. **CMC table column indices**: CMC historical pages use indices [0]=Rank, [1]=Name, [2]=Symbol, [3]=Market Cap, [4]=Price, [5]=Circulating Supply, [6]=Volume, [7]=%1h, [8]=%24h, [9]=%7d. Changed from the assumed [0,2,3,4,5,6,7,8] mapping. (Now moot since CMC scraping is replaced.)