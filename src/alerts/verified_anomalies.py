import json
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

class AnomalyNotifier:
    def __init__(self, webhook_url=None):
        self.webhook_url = webhook_url
        self.history_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", "seen_dead_markets.json")
        self._ensure_history_exists()

    def _ensure_history_exists(self):
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w') as f:
                json.dump([], f)

    def load_seen(self):
        with open(self.history_file, 'r') as f:
            return set(json.load(f))

    def mark_seen(self, market_id):
        seen = self.load_seen()
        seen.add(market_id)
        with open(self.history_file, 'w') as f:
            json.dump(list(seen), f)

    def notify(self, market, ground_truth_proof, free_premium_pct, outcome_to_buy):
        """
        Zgłasza rynki które są 100% potwierdzone na świecie, ale u buka wciąż da się z nich zdrapać darmową prowizję.
        """
        seen = self.load_seen()
        market_id = market.get('id', market.get('question', 'unknown_market'))
        
        if market_id in seen:
            return  # Już poinformowaliśmy o tym rynku
            
        logging.info("=" * 80)
        logging.info("🚨 ZNALEZIONO DARMOWĄ PREMIĘ ('DEAD MARKET ARBITRAGE') 🚨")
        logging.info("=" * 80)
        logging.info(f"❓ RYNEK: {market.get('question')}")
        logging.info(f"🟢 GROUND TRUTH (RZECZYWISTOŚĆ): {ground_truth_proof}")
        logging.info(f"💰 STATUS: Nierozstrzygnięte na Polymarkecie!")
        logging.info(f"🛒 AKCJA: Kup {outcome_to_buy} po {market.get('price_found')} na Polymarkecie")
        logging.info(f"💎 CZYSTY ZYSK WIESIE: {free_premium_pct:.2f}% bez ryzyka.")
        logging.info(f"🌊 PŁYNNOŚĆ: ${float(market.get('liquidity', 0)):.0f}")
        logging.info("=" * 80)
        
        self.mark_seen(market_id)
