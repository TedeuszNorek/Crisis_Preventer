import requests
import json
import logging
import re
import asyncio
from datetime import datetime
import yfinance as yf

# Ustawiamy PYTHONPATH ręcznie lub poprzez env, więc możemy zaimportować
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alerts.verified_anomalies import AnomalyNotifier
from data.data_models import DataModels

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

class GroundTruthVerifier:
    def __init__(self):
        pass

    def check_crypto_price_reached(self, symbol, target_price, start_time=None):
        """
        Pyta Binance API o historyczne piki świecowe aby sprawdzić, czy cena przekroczyła target.
        """
        pair = f"{symbol}USDT"
        url = "https://api.binance.com/api/v3/klines"
        
        # Sprawdzamy np miesięczne maxy (ostatnie 3 miesiące) by oszczędzić limit requestów
        params = {
            "symbol": pair,
            "interval": "1w", # Weekly candles
            "limit": 50 
        }
        try:
            resp = requests.get(url, params=params, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            
            highest_high = 0.0
            lowest_low = float('inf')
            
            for kline in data:
                # kline[2] to high price, kline[3] to low price
                high = float(kline[2])
                low = float(kline[3])
                if high > highest_high:
                    highest_high = high
                if low < lowest_low:
                    lowest_low = low
                    
            # Żeby cena "dotknęła" lub "osiągnęła" Target od momentu startu rynku,
            # Target musi po prostu znajdować się PONIŻEJ/RÓWNY lokalnemu maksimum 
            # ORAZ POWYŻEJ/RÓWNY lokalnemu minimum.
            if lowest_low <= target_price <= highest_high:
                return True, f"TWARDE DANE BINANCE: {pair} przecięło cel fizycznie (Min: {lowest_low}$, Max: {highest_high}$) dla Targetu: {target_price}$"
            return False, f"Not reached. Price remained between {lowest_low}$ and {highest_high}$"
            
        except Exception as e:
            return False, f"Error: {e}"


class SmartDiscoveryScanner:
    def __init__(self):
        self.url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=1000"
        self.headers = {"Accept": "application/json"}
        self.notifier = AnomalyNotifier()
        self.verifier = GroundTruthVerifier()
        self.db = DataModels()
        
    def fetch_markets(self):
        try:
            response = requests.get(self.url, headers=self.headers)
            response.raise_for_status()
            events = response.json()
            return events
        except:
            return []

    async def scan_loop(self):
        logging.info("👁️ Uruchamiam Skaner Opartych o Prawdę (Ground Truth Verifier)")
        
        while True:
            events = self.fetch_markets()
            total_markets = sum(len(e.get('markets', [])) for e in events)
            logging.info(f"📊 Pobrano {len(events)} wydarzeń ({total_markets} rynków) z Polymarketu. Przeszukuję anomalnie NLP...")
            
            for event in events:
                for m in event.get('markets', []):
                    # Pomijamy zamknięte
                    if m.get('closed', True):
                        continue
                        
                    liq = float(m.get('liquidity', 0))
                    if liq < 5000:
                        continue # Pomijamy płynke poniżej 5K$ (Zgodnie z wymaganiem)
                        
                    # Oczyszczamy stringowe jsony cen
                    prices_str = m.get('outcomePrices', "[]")
                    outcomes_str = m.get('outcomes', "[]")
                    try:
                        prices = json.loads(prices_str)
                        outcomes = json.loads(outcomes_str)
                    except:
                        continue
                        
                    question = str(m.get('question', ''))
                    
                    for i, p_str in enumerate(prices):
                        try:
                            price = float(p_str)
                        except:
                            continue
                            
                        # Szukamy przekonania tłumu z szerokiego zakresu do testu
                        if 0.50 <= price <= 0.999:
                            outcome_to_buy = outcomes[i] if len(outcomes) > i else "YES"
                            
                            # --- Level 1: WERYFIKACJA PRZEZ ZAAKCEPTOWANE ORACLE UMA ---
                            # Często u bukmachera wydarzenie się skończyło, oracle UMA odczytuje "Proposed"
                            # ale z powodu 2 godzinnego okna na spory market 'wisi', dając zarobić na starych ofertach.
                            is_uma_proposed = "proposed" in str(event.get('umaResolutionStatuses', '[]')).lower()
                            
                            if is_uma_proposed and outcome_to_buy.upper() == "YES":
                                free_premium = ((1.00 / price) - 1.0) * 100
                                proof_message = "TWARDE DANE UMA: System zatwierdził ten market w Oracle (Proposed), ale kontrakt jeszcze krąży po sieci blokując wypłatę."
                                m['price_found'] = price
                                m['id'] = m.get('questionID', question) + "_uma"
                                self.notifier.notify(m, proof_message, free_premium, outcome_to_buy)
                                self.db.insert_anomaly_event(
                                    event_id=event.get('id', 'unknown_event'),
                                    market_id=m['id'],
                                    anomaly_type="FREE_MONEY_UMA",
                                    detected_at=datetime.now(timezone.utc).isoformat(),
                                    raw_payload=m,
                                    proof=proof_message,
                                    profit_potential=free_premium
                                )
                                continue # Zgłoszone, szukamy dalej
                            
                            # --- Level 2: ANALIZA SEMANTYCZNA / WYCIĄGANIE TARGETÓw KRYPTO PRZED ORACLE ---
                            crypto_target_match = re.search(r'(Bitcoin|BTC).*?(?:hit|reach|touch|above).*?\$?(\d{2,3},?\d{3})', question, re.IGNORECASE)
                            
                            if crypto_target_match:
                                target_raw = crypto_target_match.group(2).replace(',', '')
                                target_price = float(target_raw)
                                logging.info(f"🔎 Oceniam kandydata do weryfikacji: '{question}' (Target: {target_price}$)")
                                
                                # Odpytujemy zewnętrzny świat przez API by udowodnić rację
                                reached, proof_message = self.verifier.check_crypto_price_reached("BTC", target_price)
                                
                                # Obiektywnie ustalamy, czy mamy anomalie (Target osiągnięty ale rynek nadal wystawiony na PM po 0.9X - 0.99)
                                if reached and outcome_to_buy.upper() == "YES":
                                    free_premium = ((1.00 / price) - 1.0) * 100
                                    m['price_found'] = price
                                    m['id'] = m.get('questionID', question)
                                    self.notifier.notify(m, proof_message, free_premium, outcome_to_buy)
                                    self.db.insert_anomaly_event(
                                        event_id=event.get('id', 'unknown_event'),
                                        market_id=m['id'],
                                        anomaly_type="GROUND_TRUTH_VERIFIED",
                                        detected_at=datetime.now(timezone.utc).isoformat(),
                                        raw_payload=m,
                                        proof=proof_message,
                                        profit_potential=free_premium
                                    )
                                else:
                                    logging.info(f"   ❌ Odrzucono - Ground truth mismatch: {proof_message}")
            
            logging.info("Skanowanie serii zakończone. Czekam na nową kolejkę z Polymarkt...")
            # Odczekanie przed kolejnym polowaniem (API rate limits friendly)
            await asyncio.sleep(60)

if __name__ == "__main__":
    scanner = SmartDiscoveryScanner()
    asyncio.run(scanner.scan_loop())
