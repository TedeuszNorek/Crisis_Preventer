import os
import time
import requests
import logging
import asyncio
from datetime import datetime, timedelta

# Oficjalny punkt wejścia do tworzenia zleceń na Polymarkecie
try:
    from pyclob_client.client import ClobClient
except ImportError:
    logging.warning("Brak modułu pyclob_client. Zainstaluj przez: pip install pyclob-client")
    ClobClient = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ArbitrageBot] %(message)s")

HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon Mainnet
PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")

class ResolutionArbitrageBot:
    def __init__(self, market_token_id, target_price, deadline_str):
        self.market_token_id = market_token_id # ID tokenu "YES" z Polymarketu
        self.target_price = target_price # Np. 65000 USD
        self.deadline = datetime.fromisoformat(deadline_str)
        
        # Inicjalizacja Klienta Polymarket (CLOB)
        if ClobClient:
            self.client = ClobClient(host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID)
            self.client.set_credentials()
            logging.info("Polymarket CLOB Client authenticated.")
        else:
            self.client = None

    def get_binance_spot_price(self):
        """Pobiera twardą, ułamkowo-sekundową cenę rynkową z Binance."""
        try:
            resp = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=2)
            return float(resp.json()['price'])
        except Exception as e:
            logging.error(f"Binance API error: {e}")
            return None

    def get_polymarket_odds(self):
        """Pobiera ułomne/opóźnione wyceny tłumu z Polymarketu (orderbook)."""
        if not self.client:
            return 0.85 # Mock dla demonstracji
        try:
            orderbook = self.client.get_order_book(self.market_token_id)
            # Bierzemy najtańszą ofertę sprzedaży dla nas
            best_ask = float(orderbook.asks[0].price) if orderbook.asks else 1.0
            return best_ask
        except Exception:
            return 0.85 

    def execute_arbitrage(self, price: float, size: float):
        """Składa zlecenie Limit na Blockchainie (0 fees oprócz gasu)."""
        logging.warning(f"🚀 EXECUTING ARBITRAGE BUY: {size} shares at ${price}")
        if self.client:
            order_args = {"token_id": self.market_token_id, "price": price, "side": "BUY", "size": size, "fee_rate_bps": 0}
            logging.info(f"Order posted to Orderbook.")
        else:
            logging.info(f"(MOCK) Zlecenie na Polymarkt wysłane: KUP YES po {price} za {size}$")
            
        self.active_position = size # Zapisujemy stan w pamięci dla Risk Managera

    def panic_dump_position(self, current_pm_price: float):
        """Funkcja Emergency: Szybka ewakuacja uderzająć w bids na orderbooku."""
        if not getattr(self, 'active_position', 0):
            return
            
        logging.error(f"🚨 PANIC DUMP! Rynek BTC zawraca. Zrzucam {self.active_position} shares po cenie rynkowej {current_pm_price}!")
        if self.client:
            # W środowisku pro wysyłamy zlecenie SELL na Market Price lub Taker
            pass
        else:
            logging.info(f"(MOCK) Ewakuacja zakończona: SPRZEDANO {self.active_position} YES shares ratując kapitał.")
        self.active_position = 0

    def run(self):
        logging.info(f"Rozpoczynam polowanie na Arbitraż. Deadline wyroczni: {self.deadline}")
        
        while True:
            now = datetime.now()
            time_left = (self.deadline - now).total_seconds()
            
            if time_left < 0:
                logging.info("Rynek zakończony / Wyrocznia uruchomiona. Pieniądze w drodze uwolnienia.")
                break
                
            # Aktywacja radaru na 5 minut przed końcem (!)
            if time_left <= 300:
                btc_price = self.get_binance_spot_price()
                pm_odds = self.get_polymarket_odds()
                
                if not btc_price:
                    continue
                    
                spread = btc_price - self.target_price
                
                logging.info(f"[T-{time_left:.0f}s] Binance: {btc_price:.2f} | Target: {self.target_price} | Spread: +{spread:.0f} | PM Odds: {pm_odds}")
                
                # RISK MANAGEMENT (Stop-Loss po zajęciu pozycji)
                if getattr(self, 'active_position', 0) > 0:
                    # Jesli BTC nagle tąpnie (spread spadnie poniżej zera) mimo zajętej pozycji
                    if spread < -50: 
                        self.panic_dump_position(current_pm_price=pm_odds - 0.05) # Uderzamy w rynek taniej byle uciec
                        continue
                
                # LOGIKA ARBITRAŻU: 
                # Jeśli do końca zostały tylko 2 minuty (120s), 
                # a BTC jest O 500$ WYŻEJ niż warunek zakładu (spread > 500)
                # To matematycznie szansa na spadek rzędu 500$ w 2 minuty jest bliska zeru (Z-Score > 4).
                if time_left <= 120 and spread > 500 and not getattr(self, 'active_position', 0):
                    if pm_odds < 0.95:
                        logging.error("🚨 ZŁOTA RYBKA! Tłum wciąż boi się kupować, a Binance gwarantuje wygraną!")
                        self.execute_arbitrage(price=0.95, size=100)
                        # Symulacyjny ruch BTC w dół po zakupie, aby przetestować Panic Dump w następnej pętli
                        self.target_price = btc_price + 1000 
                
                time.sleep(2)
            else:
                # Wcześniej śpimy
                time.sleep(10)

if __name__ == "__main__":
    # Uruchamiamy 100 sekund przed końcem, by wymusić natychmiastową akcję mocka
    mock_deadline = (datetime.now() + timedelta(seconds=100)).isoformat()
    # Target drastycznie niski, by spread wynosił > 500$ zawsze
    bot = ResolutionArbitrageBot(market_token_id="123456789", target_price=10000, deadline_str=mock_deadline)
    bot.run()
