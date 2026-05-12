import asyncio
import json
import logging
import sqlite3
import random
from datetime import datetime

import websockets

from bots.pricing_engine import Polymarket15mPricingEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")

class Polymarket15mBot:
    def __init__(self, db_path="data/paper_trades.db"):
        self.engine = Polymarket15mPricingEngine(max_candles=20)
        self.db_path = db_path
        self._init_db()
        
        self.target_spread = 0.03  # 3% opłacalnego rozjazdu 
        self.active_position = 0
        self.total_pnl = 0.0

        # Wirtualne ceny do zasymulowania Polymarketu. W prod, to jest WebSocket Poly
        self.poly_prob = 0.50

    def _init_db(self):
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute('''CREATE TABLE IF NOT EXISTS pm_15m_trades
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         timestamp TEXT,
                         action TEXT, 
                         signal_reason TEXT,
                         rsi REAL,
                         mom_1h REAL,
                         fair_value REAL,
                         pm_price REAL,
                         spread REAL,
                         size REAL)''')
        conn.commit()
        conn.close()

    def log_trade(self, action, signal_reason, rsi, mom_1h, fair_value, pm_price, spread, size):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''INSERT INTO pm_15m_trades 
                        (timestamp, action, signal_reason, rsi, mom_1h, fair_value, pm_price, spread, size) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (datetime.now().isoformat(), action, signal_reason, float(rsi), float(mom_1h), 
                      float(fair_value), float(pm_price), float(spread), float(size)))
        conn.commit()
        conn.close()

    async def connect_binance_klines(self):
        """Nasłuchuje Binance Kline (15m interval) - używamy streamingu."""
        url = "wss://stream.binance.com:9443/ws/btcusdt@kline_15m"
        
        logging.info("Rozpoczynam nasłuch Binance WebSocket 15M (Real-Time)")
        
        async for websocket in websockets.connect(url):
            try:
                async for message in websocket:
                    data = json.loads(message)
                    kline = data['k']
                    close_price = float(kline['c'])
                    is_closed = kline['x']
                    
                    # 1. Jeżeli świeca fizycznie zamknęła się, wpychamy do silnika na twardo
                    if is_closed:
                        self.engine.process_kline(close_price, is_closed=True)
                        logging.info(f"📊 Świeca 15m zamknięta na {close_price}")
                        
                    # 2. Obliczamy bieżące parametry "Fair Value" w locie!
                    fair_value, reason, rsi, mom_1h = self.engine.calculate_fair_value(close_price)
                    
                    if reason != "WAIT_FOR_DATA":
                        await self.evaluate_trade(fair_value, reason, rsi, mom_1h)
                        
            except websockets.exceptions.ConnectionClosed:
                logging.warning("Binance WS rozłączony. Reconnecting...")
                await asyncio.sleep(2)

    async def mock_polymarket_stream(self):
        """Mockowany Polymarket - spóźnia się względem prawdy o 10% powoli."""
        while True:
            await asyncio.sleep(0.5)
            # Normalnie tutaj aktualizujemy self.poly_prob z feedu WSS Polymarket 
            # na cele Paper Trading udajemy, że Polymarket krąży wokół 0.50
            jump = random.uniform(-0.02, 0.02)
            self.poly_prob = max(0.01, min(0.99, self.poly_prob + jump))

    async def evaluate_trade(self, fair_value, reason, rsi, mom_1h):
        # Sprawdzamy czy mamy Spread
        spread = fair_value - self.poly_prob
        
        # Jeśli różnica między wyliczonym a Polymarketem wynosi > target_spread
        # Kupujemy paczkę "YES" (lub gramy spadki, jeśli fair value jest bliskie zera)
        if spread > self.target_spread and reason != "NEUTRAL":
            logging.info(f"🚨 SPREAD ALERT! Edge: {(spread*100):.2f}% | Reason: {reason} | RSI: {rsi:.1f}")
            logging.info(f"🎯 KUPUJĘ 'YES' na Polymarket za {self.poly_prob:.3f} (Fair: {fair_value:.3f})")
            
            # Zapraszamy do bazy do późniejszej analityki Paper
            self.log_trade("BUY", reason, rsi, mom_1h, fair_value, self.poly_prob, spread, 100)
            
            # Żeby nie uderzać co sekundę logiem dodaje backoff:
            await asyncio.sleep(10)
            
        elif spread < -self.target_spread and reason != "NEUTRAL":
            logging.info(f"🚨 REVERSE SPREAD ALERT! Edge: {(spread*100):.2f}% | Reason: {reason} | RSI: {rsi:.1f}")
            logging.info(f"🎯 KUPUJĘ 'NO' na Polymarket (PM wycenia wyżej niż powinno)!")
            self.log_trade("SELL", reason, rsi, mom_1h, fair_value, self.poly_prob, spread, 100)
            await asyncio.sleep(10)

    async def run(self):
        logging.info("💪 Uruchamiam Pricing Engine & Paper Trader (Mean Reversion)")
        
        # AbyPricing engine działał, musimy go najpierw 'zapalić' danymi klines
        # Seed engine with random mock data for instant testing
        logging.info("🌱 Seeding engine with past 16 candles to enable instant live calculation...")
        for i in range(16):
            self.engine.process_kline(65000 + random.uniform(-100, 100))
            
        await asyncio.gather(
            self.connect_binance_klines(),
            self.mock_polymarket_stream()
        )

if __name__ == "__main__":
    bot = Polymarket15mBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logging.info("Bot Stopped.")
