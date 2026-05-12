import asyncio
import aiohttp
import time
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MASSIVE_ACCESS_KEY = os.getenv("MASSIVE_ACCESS_KEY_ID")
if not MASSIVE_ACCESS_KEY:
    logging.warning("Missing MASSIVE_ACCESS_KEY_ID in .env, falling back to POLYGON_API_KEY if exists")
    MASSIVE_ACCESS_KEY = os.getenv("POLYGON_API_KEY")

if not MASSIVE_ACCESS_KEY:
    logging.error("No valid Massive/Polygon API Key provided.")
    exit(1)

API_URL = "http://localhost:8000/ingest"
# Using Polygon's endpoint format as standard for Massive API (ex-Polygon) options
POLYGON_BASE_URL = "https://api.polygon.io/v3/snapshot/options"

# We observe SPY options as the benchmark for equity market volatility
UNDERLYING = "SPY"

async def fetch_options_snapshot(session):
    headers = {"Authorization": f"Bearer {MASSIVE_ACCESS_KEY}"}
    
    try:
        url = f"{POLYGON_BASE_URL}/{UNDERLYING}"
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("results", [])
                
                # A simplistic proxy for Implied Volatility:
                # Average the IV of the 10 closest contracts available
                if not results:
                     return None, None
                
                total_volume = 0
                ivs = []
                for option in results:
                    total_volume += option.get("day", {}).get("volume", 0)
                    iv = option.get("implied_volatility")
                    if iv:
                        ivs.append(iv)
                
                avg_iv = sum(ivs) / len(ivs) if ivs else 0.0
                return avg_iv, total_volume
            else:
                logging.error(f"Polygon API returned {resp.status}: {await resp.text()}")
    except Exception as e:
        logging.error(f"Error fetching Polygon API: {e}")
        
    return None, None

async def process_options():
    async with aiohttp.ClientSession() as session:
        logging.info(f"Starting Polygon/Massive Options Streamer for {UNDERLYING}")
        
        while True:
            fetch_start_ts = time.time()
            avg_iv, total_volume = await fetch_options_snapshot(session)
            fetch_end_ts = time.time()
            
            if avg_iv is not None:
                payload = {
                    "ts_event": fetch_end_ts,
                    "source": "polygon_api",
                    "entity_type": "options_chain",
                    "entity_id": f"{UNDERLYING}_OPTIONS",
                    "features": {
                        "implied_volatility_avg": avg_iv,
                        "chain_volume": total_volume
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
                             logging.info(f"Ingested {UNDERLYING} Options (Avg IV: {avg_iv:.3f}, Vol: {total_volume}). Active alerts: {open_alerts}")
                         else:
                             logging.error(f"Failed to ingest event, API returned {resp.status}")
                except Exception as e:
                    logging.error(f"Error posting to Engine API: {e}")
            
            # Options snapshots update constantly. We poll every 5 mins to avoid hitting naive limits
            await asyncio.sleep(300)

if __name__ == "__main__":
    try:
        asyncio.run(process_options())
    except KeyboardInterrupt:
        logging.info("Shutting down Polygon streamer.")
