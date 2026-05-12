import asyncio
import aiohttp
import time
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DOME_API_KEY = os.getenv("DOME_API_KEY")
if not DOME_API_KEY:
    logging.error("Missing DOME_API_KEY in .env")
    exit(1)

API_URL = "http://localhost:8000/ingest"
DOME_ENDPOINT = "https://api.domeapi.io/v1/polymarket/orders"

# Example market tracking
MARKET_SLUG = "us-government-shutdown-by-october-1"

async def fetch_probability(session):
    headers = {"Authorization": f"Bearer {DOME_API_KEY}"}
    params = {"limit": 10, "market_slug": MARKET_SLUG}
    
    try:
        async with session.get(DOME_ENDPOINT, headers=headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                # DomeAPI returns: {"orders": [...], "pagination": {...}}
                if data and "orders" in data and len(data["orders"]) > 0:
                    orders = data["orders"]
                    
                    # Estimate probability using recent trades or orders
                    # We will use the average price of recent "BUY" orders for "Yes"
                    yes_prices = [float(o.get("price", 0)) for o in orders if o.get("side") == "BUY" and o.get("token_label") == "Yes"]
                    
                    if yes_prices:
                        return sum(yes_prices) / len(yes_prices)
                        
                logging.warning(f"No valid BUY orders for Yes found. Using last known or waiting. Snippet: {str(data)[:200]}")
                return None
            else:
                logging.error(f"DomeAPI returned {resp.status}: {await resp.text()}")
                return None
    except Exception as e:
        logging.error(f"Error fetching DomeAPI: {e}")
        return None

async def process_polymarket():
    async with aiohttp.ClientSession() as session:
        logging.info(f"Starting Polymarket Streamer (DomeAPI) for {MARKET_SLUG}")
        
        while True:
            fetch_start_ts = time.time()
            prob = await fetch_probability(session)
            fetch_end_ts = time.time()
            
            if prob is not None:
                # Build Signal Engine Payload
                payload = {
                    "ts_event": fetch_end_ts,
                    "source": "polymarket_dome",
                    "entity_type": "prediction_market",
                    "entity_id": MARKET_SLUG,
                    "features": {
                        "yes_prob": prob,
                        "implied_volatility_est": 0.0 # Placeholder
                    },
                    "dq": {
                        "timeliness_s": fetch_end_ts - fetch_start_ts, # Network latency proxy
                        "completeness": 1.0, 
                        "consistency": 1.0
                    }
                }
                
                try:
                    async with session.post(API_URL, json=payload) as resp:
                         if resp.status == 200:
                             res_json = await resp.json()
                             open_alerts = len(res_json.get("active_alerts", []))
                             logging.info(f"Ingested Polymarket data for {MARKET_SLUG} (Yes Prob: {prob:.4f}). Active alerts: {open_alerts}")
                         else:
                             logging.error(f"Failed to ingest event, API returned {resp.status}")
                except Exception as e:
                    logging.error(f"Error posting to Engine API: {e}")
            
            # Rate limiting / Polling interval
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(process_polymarket())
    except KeyboardInterrupt:
        logging.info("Shutting down Polymarket streamer.")
