import asyncio
import aiohttp
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_URL = "http://localhost:8000/ingest"
DERIBIT_BASE_URL = "https://www.deribit.com/api/v2/public"
CURRENCY = "BTC"

async def fetch_deribit_iv(session):
    try:
        url = f"{DERIBIT_BASE_URL}/get_book_summary_by_currency"
        params = {"currency": CURRENCY, "kind": "option"}
        
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("result", [])
                
                # Calculate volume-weighted Implied Volatility for active options
                valid_options = [o for o in results if o.get("volume", 0) > 0 and o.get("mark_iv", 0) > 0]
                
                if not valid_options:
                    return None, 0
                
                total_volume = sum(o.get("volume", 0) for o in valid_options)
                
                if total_volume > 0:
                    weighted_iv = sum((o.get("mark_iv", 0) * o.get("volume", 0)) / total_volume for o in valid_options)
                    return weighted_iv / 100.0, total_volume # Mark IV is returned as percentage (e.g. 56.2)
                else:
                    return None, 0
            else:
                logging.error(f"Deribit API returned {resp.status}: {await resp.text()}")
    except Exception as e:
        logging.error(f"Error fetching Deribit API: {e}")
        
    return None, 0

async def process_deribit_options():
    async with aiohttp.ClientSession() as session:
        logging.info(f"Starting Deribit Options Streamer for {CURRENCY} (Public Endpoint)")
        
        while True:
            fetch_start_ts = time.time()
            avg_iv, total_volume = await fetch_deribit_iv(session)
            fetch_end_ts = time.time()
            
            if avg_iv is not None:
                payload = {
                    "ts_event": fetch_end_ts,
                    "source": "deribit_api",
                    "entity_type": "crypto_options_chain",
                    "entity_id": f"{CURRENCY}_OPTIONS",
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
                             logging.info(f"Ingested {CURRENCY} Options (Weighted IV: {avg_iv:.4f}, Vol: {total_volume}). Active alerts: {open_alerts}")
                         else:
                             logging.error(f"Failed to ingest event, API returned {resp.status}")
                except Exception as e:
                    logging.error(f"Error posting to Engine API: {e}")
            
            # Update options stats every 30 seconds
            await asyncio.sleep(30)

if __name__ == "__main__":
    try:
        asyncio.run(process_deribit_options())
    except KeyboardInterrupt:
        logging.info("Shutting down Deribit streamer.")
