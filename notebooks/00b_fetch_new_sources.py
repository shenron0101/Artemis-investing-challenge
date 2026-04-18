import os
import json
import time
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

FRED_API_KEY = os.getenv("FRED_API_KEY")
BINANCE_KEY = os.getenv("BINANCE_API_KEY")

RAW_FRED = ROOT / "data" / "raw" / "fred"
RAW_LLAMA = ROOT / "data" / "raw" / "defillama"
RAW_BINANCE = ROOT / "data" / "raw" / "binance"
PROCESSED = ROOT / "data" / "processed"

for d in [RAW_FRED, RAW_LLAMA, RAW_BINANCE, PROCESSED]:
    d.mkdir(parents=True, exist_ok=True)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

# --- 1. DefiLlama Data ---
print("Fetching DefiLlama Protocols (TVL & metadata)...")
r = requests.get("https://api.llama.fi/protocols")
if r.status_code == 200:
    save_json(RAW_LLAMA / "protocols.json", r.json())

print("Fetching DefiLlama Stablecoins...")
r = requests.get("https://stablecoins.llama.fi/stablecoins")
if r.status_code == 200:
    save_json(RAW_LLAMA / "stablecoins.json", r.json())

# --- 2. FRED Macro Data ---
print("Fetching FRED Macro Data...")
if FRED_API_KEY:
    series_ids = {"FEDFUNDS": "policy_rate", "DGS2": "2y_yield", "BAMLH0A0HYM2": "high_yield_spread"}
    fred_data = []
    for sid, name in series_ids.items():
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={FRED_API_KEY}&file_type=json"
        r = requests.get(url)
        if r.status_code == 200:
            obs = r.json().get("observations", [])
            for o in obs:
                if o["value"] != ".":
                    fred_data.append({"date": o["date"], "metric": name, "value": float(o["value"])})
        time.sleep(1)
    
    if fred_data:
        df_fred = pd.DataFrame(fred_data)
        df_fred["date"] = pd.to_datetime(df_fred["date"]).dt.date
        df_fred.to_parquet(PROCESSED / "macro_regime_daily.parquet", index=False)
        save_json(RAW_FRED / "macro.json", fred_data)

# --- 3. Binance Derivatives Proxy ---
print("Fetching Binance Funding Rates...")
r = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex")
if r.status_code == 200:
    save_json(RAW_BINANCE / "premium_index.json", r.json())
r = requests.get("https://fapi.binance.com/fapi/v1/fundingRate")
if r.status_code == 200:
    save_json(RAW_BINANCE / "funding_rates.json", r.json())

print("Data fetch complete. Processed files saved.")

