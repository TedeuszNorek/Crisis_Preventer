import asyncio
import json
import logging
import requests
import websockets
import sqlite3
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")

class LiveMVPBot:
    def __init__(self):
        self.btc_price = 0.0
        self.live_markets = [] # Przechowuje słownik z ID rynków i ich celami [Target BTC price]
        self._init_paper_db()
        
    def _init_paper_db(self):
        conn = sqlite3.connect("paper_trades.db")
        conn.execute('''CREATE TABLE IF NOT EXISTS trades 
                      (id INTEGER PRIMARY KEY, timestamp TEXT, market TEXT, pm_price REAL, spread_usd REAL, binance_ref REAL)''')
        conn.commit()
        conn.close()
        
    def fetch_active_btc_markets(self):
        """Łączy się z Polymarket API i szuka aktywnych rynków o BTC."""
        logging.info("Trwa mapowanie prawdziwych, aktywnych rynków BTC na Polymarket...")
        try:
            # Używamy bezpośrednio endpointu markets, który wystawia clobTokenIds zamiast zagmatwanych events
            resp = requests.get("https://gamma-api.polymarket.com/markets?limit=1000&active=true&closed=false", timeout=10)
            markets_payload = resp.json()
            
            for m in markets_payload:
                if m.get('closed'): continue
                
                title = m.get('question', '')
                clob_str = m.get('clobTokenIds', '[]')
                try:
                    tokens = json.loads(clob_str)
                    if tokens and len(tokens) > 0:
                        yes_token = tokens[0]  # Zawsze pierwszy token (np. Yes, Up, itd.)
                        end_date_str = m.get('endDateIso', '')
                        
                        # Próba wyciagniecia Target Price
                        target_price = 0
                        match = re.search(r'\$?(\d{2,3}(?:,\d{3})*)', title) 
                        if match:
                            num_str = match.group(1).replace(',', '')
                            if int(num_str) > 20000: # To pewnie cena BTC
                                target_price = int(num_str)
                        
                        self.live_markets.append({
                            'title': title,
                            'token_id': yes_token,
                            'end_date': end_date_str,
                            'target': target_price
                        })
                        logging.info(f"📍 ZNALEZIONO RYNEK: {title[:50]}... | ID: {yes_token[:8]}")
                        
                        if len(self.live_markets) >= 3:
                            break # Ograniczamy do 3 rynków dla demonstracji
                except Exception as parse_e:
                    pass
            
            if not self.live_markets:
                logging.warning("Nie znaleziono aktywnych rynków BTC w publicznych eventach. Spróbuję ponownie.")
                
        except Exception as e:
            logging.error(f"Błąd przy szukaniu rynków: {e}")

    async def stream_binance(self):
        """Nasłuchuje WSS z Binance 100x na sekundę."""
        uri = "wss://stream.binance.com:9443/ws/btcusdt@trade"
        while True:
            try:
                async with websockets.connect(uri) as ws:
                    logging.info("✅ Podłączono strumień wyroczni Binance rynkowego BTC (Real-Time)")
                    async for msg in ws:
                        data = json.loads(msg)
                        self.btc_price = float(data['p']) # p = price
            except Exception as e:
                logging.error(f"Binance WS rozłączony: {e}. Próbuję ponownie za 2s...")
                await asyncio.sleep(2)

    async def scan_polymarket_orderbooks(self):
        """Pętla asynchroniczna zaciągająca Księgę Zleceń CLOB z opóźnionego Polymarketu."""
        await asyncio.sleep(3) # Czekamy aż Binance złapie pierwszą cenę
        
        while True:
            for market in self.live_markets[:3]: # Skanujemy max 3 na raz dla MVP
                token_id = market['token_id']
                try:
                    # CLOB API Polymarketu dla konkretnego żetonu "YES"
                    # Zapytanie synchroniczne w tle (Dla MVP uproszczone przez requests, idealnie aiohttp)
                    resp = await asyncio.to_thread(requests.get, f"https://clob.polymarket.com/book?token_id={token_id}", timeout=2)
                    
                    if resp.status_code == 200:
                        book = resp.json()
                        asks = book.get('asks', [])
                        
                        if asks and self.btc_price > 0:
                            best_ask = float(asks[0]['price'])
                            # Dystans BTC do wykonania (Jeśli target znaleziony w nazwie)
                            dist_str = f"Diff: ${self.btc_price - market['target']:.0f}" if market['target'] > 0 else "N/A"
                            
                            # PROSTY, OCZEKIWANY FORMAT: 
                            # [Instrument] | [Cena wejścia PM] | [Czas Do Końca] | [Odniesienie Binance]
                            days_left = "Unknown"
                            if market['end_date']:
                                end_dt = datetime.fromisoformat(market['end_date'].replace('Z', '+00:00'))
                                delta = end_dt - datetime.now(end_dt.tzinfo)
                                days_left = f"{delta.days} Dni"

                            log_msg = f"[ {market['title'][:45]} ] | Wymagane wejście (PM): ${best_ask:.3f} | Żywe Binance: ${self.btc_price:.2f}"
                            
                            # Z-Score MVP Mispricing Logic (Jeśli BTC > celu a PM Odds < 0.90)
                            if market['target'] > 0 and self.btc_price > market['target'] + 500 and best_ask < 0.90:
                                logging.warning(f"🚨 TWARDA OKAZJA (MARKET LAG!): {log_msg}")
                                # Zapisujemy wirtualna transakcje (Paper Trade) bo rynek sie ociąga
                                try:
                                    conn = sqlite3.connect("paper_trades.db")
                                    conn.execute("INSERT INTO trades (timestamp, market, pm_price, spread_usd, binance_ref) VALUES (?, ?, ?, ?, ?)",
                                                 (datetime.now().isoformat(), market['title'], best_ask, self.btc_price - market['target'], self.btc_price))
                                    conn.commit()
                                    conn.close()
                                    logging.info("💾 Pomyślnie zapisano Wirtualną Transakcję (Paper Trade) do bazy!")
                                except Exception as e:
                                    logging.error(f"Failed paper trade db insert: {e}")
                            else:
                                # Zawsze drukuj rynki by udowodnić działanie strumienia
                                logging.info(f"📊 LIVE: {log_msg}")
                                
                except Exception as e:
                    pass # Ciche pomijanie błędów przy agresywnym przepytywaniu
            
            await asyncio.sleep(5) # Pętla pobiera API księgi PM co 5 sekund by nie zarżnąć rate-limitów

    async def run_live(self):
        self.fetch_active_btc_markets()
        logging.info("Rozpoczynam Strumieniowanie Asynchroniczne SILNIKA NA ŻYWO...")
        await asyncio.gather(
            self.stream_binance(),
            self.scan_polymarket_orderbooks()
        )

if __name__ == "__main__":
    bot = LiveMVPBot()
    asyncio.run(bot.run_live())
