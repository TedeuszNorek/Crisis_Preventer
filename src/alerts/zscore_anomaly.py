import collections
import statistics
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [AnomalyDetector] %(message)s")

class ZScoreAnomalyDetector:
    """
    Moduł do wykrywania anomalii "2-Sigma" (ruch o ponad 2 odchylenia standardowe).
    Przechowuje historię wartości danego aktywa z zachowaniem okna czasowego.
    """
    def __init__(self, window_size: int = 100, z_threshold: float = 2.0):
        # Kolejka przechowująca ostatnie 'N' wartości dla obliczenia tła (baseline)
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.history = collections.deque(maxlen=window_size)
    
    def process_new_value(self, value: float, entity_name: str) -> dict:
        """
        Przetwarza nową wartość (np. Implied Volatility z Deribit lub 'yes_prob' z Polymarketu).
        Zwraca słownik z sygnałem, jeśli ruch przekroczył 2-Sigma.
        """
        # Jeśli nie mamy jeszcze odpowiedniej próbki, tylko dodajemy do historii
        if len(self.history) < max(self.window_size // 4, 10):
            self.history.append(value)
            return {"anomaly": False, "z_score": 0.0}
            
        # Obliczanie średniej i odchylenia standardowego (StdDev, powszechnie d/sigma)
        mean = statistics.mean(self.history)
        stdev = statistics.stdev(self.history) if len(self.history) > 1 else 0.0
        
        # Ochrona przed dzieleniem przez 0, gdy rynek zamarznie
        if stdev == 0.0:
            stdev = 0.0001
            
        # Wyliczenie wskaźnika Z-Score
        z_score = (value - mean) / stdev
        
        # Jeśli ruch odchyla się o ponad X odchyleń (często +2.0 w górę)
        is_anomaly = abs(z_score) > self.z_threshold
        
        if is_anomaly:
            logging.warning(f"🚨 ANOMALIA 2-SIGMA: {entity_name} | Wartość: {value:.4f} | Rynkowa Średnia: {mean:.4f} | Z-Score: {z_score:.2f}")
            signal = {
                "anomaly": True,
                "z_score": z_score,
                "value": value,
                "mean": mean,
                "stdev": stdev
            }
        else:
            signal = {"anomaly": False, "z_score": z_score}
            
        # Dodajemy wartość do okna tylko po weryfikacji, żeby ekstremalne szoki
        # nie wypaczyły natychmiast średniej kroczącej (tzw. robust statistics).
        # Alternatywnie możemy dodawać wszystko, by średnia goniła szok.
        self.history.append(value)
        
        return signal

# === Przykład użycia / Projekt logiki ===
if __name__ == "__main__":
    # Projekt dla Polymarketu (prawdopodobieństwo wybuchu wojny o 0.02)
    poly_detector = ZScoreAnomalyDetector(window_size=50, z_threshold=2.0)
    
    # Symulacja: Prawdopodobieństwo jest stabilne na poziomie 3% (0.03) +- szum
    poly_detector.history.extend([0.03, 0.031, 0.029, 0.032, 0.028, 0.03, 0.031] * 5)
    
    print("\n--- TEST POLYMARKET: Nagły wzrost ---")
    # Nagle wielki gracz kupuje za 1 mln USD, prob skacze na 0.15 (+15%)
    sys_alert = poly_detector.process_new_value(0.15, "Polymarket_War_YesProb")
    
    print(f"\n--- TEST DERIBIT: Skok Opcji: Implied Volatility ---")
    deribit_detector = ZScoreAnomalyDetector(window_size=100, z_threshold=2.0)
    deribit_detector.history.extend([60.0, 61.0, 59.5, 60.2, 58.0, 60.5] * 10)
    # Publikacja danych makro spłaszczona przez rynek, brak reakcji
    sys_alert_2 = deribit_detector.process_new_value(61.5, "Deribit_BTC_Put_IV") 
    print(f"Normalny szum (61.5): Anomalia - {sys_alert_2['anomaly']}")
    
    # Czarny Łabędź - VIX wybija i IV opcji na krypto skacze do 95%
    sys_alert_3 = deribit_detector.process_new_value(95.0, "Deribit_BTC_Put_IV")
