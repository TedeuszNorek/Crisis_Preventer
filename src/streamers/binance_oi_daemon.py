import time
import requests
import logging
import subprocess
import os
import sys

# Dodajemy folder główny do sys.path, by móc importować detektora Z-Score z folderu src.alerts
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from src.alerts.zscore_anomaly import ZScoreAnomalyDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BinanceOI] %(message)s")

# Sledzone instrumenty Perpetual
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

def insert_global_alert(source, title, message):
    try:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "polymarket_anomalies.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS global_alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, source TEXT, title TEXT, message TEXT)")
        conn.execute("INSERT INTO global_alerts (timestamp, source, title, message) VALUES (?, ?, ?, ?)",
                     (time.strftime("%Y-%m-%dT%H:%M:%S"), source, title, message))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"DB insert failed: {e}")

def push_mac_notification(title, message):
    insert_global_alert("BINANCE_DAEMON", title, message)
    try:
        safe_msg = message.replace('"', '\\"')
        safe_title = title.replace('"', '\\"')
        subprocess.run(['osascript', '-e', f'display notification "{safe_msg}" with title "{safe_title}"'])
    except Exception as e:
        logging.error(f"Mac notification failed: {e}")

class BinanceMonitor:
    def __init__(self):
        # Inicjalizujemy osobne detektory 2-Sigmy dla każdego instrumentu
        self.detectors_oi = {sym: ZScoreAnomalyDetector(window_size=60, z_threshold=2.0) for sym in SYMBOLS}
        self.detectors_funding = {sym: ZScoreAnomalyDetector(window_size=60, z_threshold=2.5) for sym in SYMBOLS}

    def fetch_market_data(self):
        # Pobiera funding rate i OI na żywo z Binance Futures (Perp)
        try:
            # Endpoint dla Funding (Premium Index)
            funding_resp = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex", timeout=10)
            funding_data = funding_resp.json()
            
            # Pobieranie Open Interest dla wybranych rynków
            oi_data = {}
            for sym in SYMBOLS:
                oi_resp = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={sym}", timeout=5)
                oi_data[sym] = float(oi_resp.json().get('openInterest', 0))
                
            return funding_data, oi_data
        except Exception as e:
            logging.error(f"Failed to fetch from Binance: {e}")
            return None, None

    def run(self, interval=30):
        logging.info(f"Odpalam Monitor Anomalii Binance (OI & Funding) co {interval} sekund...")
        push_mac_notification("Binance Monitor Aktywny", "Sledzenie Open Interest i wskaźników Funding Rate na Perpetualach...")
        
        while True:
            funding_list, oi_dict = self.fetch_market_data()
            if not funding_list:
                time.sleep(10)
                continue
                
            # Wyszukaj interesujace instrumenty w paczce Funding
            for item in funding_list:
                sym = item.get('symbol')
                if sym in SYMBOLS:
                    # Funding Rate to czesto bardzo mały ułamek (np. 0.0001 = 0.01%)
                    funding_rate = float(item.get('lastFundingRate', 0)) * 100 
                    
                    # 1. Test Funding Rate
                    fund_signal = self.detectors_funding[sym].process_new_value(funding_rate, f"Funding_Rate_{sym}")
                    if fund_signal["anomaly"]:
                        logging.warning(f"🚨 FUNDING ANOMALY: {sym} osiągnął {funding_rate:.4f}% | Z-Score: {fund_signal['z_score']:.2f}")
                        push_mac_notification(f"🚨 Szok Funding na {sym}", f"Wskaźnik (opłata) dociągnął do {funding_rate:.4f}%! Wisi widmo Long Squeeze'a!")
                    
                    # 2. Test Open Interest
                    oi_val = oi_dict.get(sym, 0)
                    oi_signal = self.detectors_oi[sym].process_new_value(oi_val, f"OpenInterest_{sym}")
                    if oi_signal["anomaly"] and oi_signal["z_score"] > 0: # Tylko gwałtowny przyrost
                        logging.warning(f"🚨 OI MASSIVE JUMP: {sym} zyskał ogromne pozycje! Nowy OI: {oi_val:,.0f} | Z-Score: {oi_signal['z_score']:.2f}")
                        push_mac_notification(f"🐳 Skok OI na {sym}", f"Pojawił się masywny kapitał (Open Interest)! Pozycje skoczyły do {oi_val:,.0f} kontraktów!")

                    # Specjalny "Kill Switch Alert"
                    # Kiedy oba wybijają w tym samym oknie, mamy definitywną pułapkę nakręconą dźwignią
                    if fund_signal["anomaly"] and oi_signal["anomaly"] and fund_signal["z_score"] > 2.0 and oi_signal["z_score"] > 2.0:
                        push_mac_notification("⚡ EXTREME WARNING", f"{sym}: Gigantyczny wlew kapitału w same Longi z chciwą dźwignią. Uciekałbym!")
            time.sleep(interval)

if __name__ == "__main__":
    monitor = BinanceMonitor()
    # W celach demonstracyjnych ograniczamy do ułamek żeby nie zamrozić asystenta.
    # Użytkownik i tak to odpali u siebie.
    import threading
    t = threading.Thread(target=monitor.run, args=(30,))
    t.daemon = True
    t.start()
    time.sleep(2) # Czeka chwile by powiadomienie startowe wyskoczyło powiadamiając użytkownika
