import asyncio
import websockets
import json
import aiohttp
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BINANCE_WS_URL = "wss://fstream.binance.com/ws/btcusdt@markPrice"
API_URL = "http://localhost:8000/ingest"

async def process_messages():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                logging.info(f"Connecting to Binance WebSocket at {BINANCE_WS_URL}...")
                async with websockets.connect(BINANCE_WS_URL) as ws:
                    logging.info("Connected.")
                    while True:
                        message = await ws.recv()
                        data = json.loads(message)
                        
                        # Example Binance markPrice payload:
                        # {
                        #   "e": "markPriceUpdate",
                        #   "E": 1562305380000,
                        #   "s": "BTCUSDT",
                        #   "p": "11794.15000000",
                        #   "i": "11784.62659091",
                        #   "P": "11784.25641265",
                        #   "r": "0.00038167",
                        #   "T": 1562306400000
                        # }
                        
                        event_ts = data.get("E", int(time.time() * 1000)) / 1000.0
                        local_ts = time.time()
                        
                        try:
                            price = float(data.get("p", 0))
                            funding_rate = float(data.get("r", 0))
                        except (ValueError, TypeError):
                            continue # skip malformed messages
                        
                        # Fake Data Quality metric (e.g. latency)
                        latency = max(0.001, local_ts - event_ts)
                        
                        payload = {
                            "ts_event": event_ts,
                            "source": "binance_ws",
                            "entity_type": "instrument",
                            "entity_id": data.get("s", "BTCUSDT"),
                            "features": {
                                "price": price,
                                "funding_rate": funding_rate
                            },
                            "dq": {
                                "timeliness_s": latency,
                                "completeness": 1.0 if "p" in data and "r" in data else 0.5,
                                "consistency": 1.0 # assume strong consistency format
                            }
                        }
                        
                        try:
                            async with session.post(API_URL, json=payload) as resp:
                                if resp.status == 200:
                                    res_json = await resp.json()
                                    open_alerts = len(res_json.get("active_alerts", []))
                                    logging.info(f"Ingested tick for BTCUSDT (Price: {price}, Funding: {funding_rate:.6f}). Active alerts: {open_alerts}")
                                else:
                                    logging.error(f"Failed to ingest event, API returned {resp.status}")
                        except Exception as e:
                            logging.error(f"Error posting to API: {e}")
                            
            except websockets.exceptions.ConnectionClosed:
                logging.warning("WebSocket connection closed. Reconnecting in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                logging.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(process_messages())
    except KeyboardInterrupt:
        logging.info("Shutting down streamer.")
