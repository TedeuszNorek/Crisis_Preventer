import asyncio
import aiohttp
import time
import logging
import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

FRED_API_KEY = os.getenv("FRED_API_KEY")
if not FRED_API_KEY:
    logging.error("Missing FRED_API_KEY in .env")
    exit(1)

API_URL = "http://localhost:8000/ingest"
FRED_BASE_URL = "https://api.stlouisfed.org/fred"
SERIES = "M2SL"  # US M2 Money Supply

async def fetch_fred_m2():
    params = {
        "series_id": SERIES,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 13 # need a year's worth for YoY
    }
    try:
        url = f"{FRED_BASE_URL}/series/observations"
        # Blocking request but fine for low freq
        resp = requests.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            obs = data.get("observations", [])
            valid_obs = [float(o["value"]) for o in obs if o["value"] != "."]
            
            if len(valid_obs) >= 13:
                current_val = valid_obs[0]
                year_ago_val = valid_obs[12]
                yoy_growth = (current_val - year_ago_val) / year_ago_val
                return yoy_growth
            else:
                logging.warning(f"Not enough valid observations for {SERIES} to calculate YoY growth.")
        else:
            logging.error(f"FRED API returned {resp.status_code}: {resp.text}")
    except Exception as e:
        logging.error(f"Error fetching FRED API: {e}")
    return None

async def process_fred():
    async with aiohttp.ClientSession() as session:
        logging.info(f"Starting FRED Macro Streamer (M2SL YoY Growth)")
        
        while True:
            fetch_start_ts = time.time()
            yoy_growth = await fetch_fred_m2()
            fetch_end_ts = time.time()
            
            if yoy_growth is not None:
                payload = {
                    "ts_event": fetch_end_ts,
                    "source": "fred_api",
                    "entity_type": "macro_indicator",
                    "entity_id": "USA_M2_YOY",
                    "features": {
                        "m2_yoy_growth": yoy_growth
                    },
                    "dq": {
                        "timeliness_s": fetch_end_ts - fetch_start_ts,
                        "completeness": 1.0, 
                        "consistency": 1.0
                    }
                }
                
                try:
                    async with session.post(API_URL, json=payload) as resp:
                         if resp.status == 200:
                             res_json = await resp.json()
                             open_alerts = len(res_json.get("active_alerts", []))
                             logging.info(f"Ingested FRED Macro data (M2 YoY Growth: {yoy_growth:.4f}). Active alerts: {open_alerts}")
                         else:
                             logging.error(f"Failed to ingest event, API returned {resp.status}")
                except Exception as e:
                    logging.error(f"Error posting to Engine API: {e}")
            
            # Macro indicators update slowly (usually weekly/monthly). Polling hourly is more than enough.
            # However, for demonstration purposes, we will poll every 60 seconds.
            await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(process_fred())
    except KeyboardInterrupt:
        logging.info("Shutting down FRED streamer.")
