import collections
import pandas as pd
import numpy as np

class Polymarket15mPricingEngine:
    def __init__(self, max_candles=20):
        # Kolejka na zamknięte na sztywno świeczki
        self.klines = collections.deque(maxlen=max_candles)
        self.base_prob_up = 0.50

    def process_kline(self, close_val, is_closed=True):
        """Dodaje zarchwiozwaną świecę do pamięci."""
        if is_closed:
            self.klines.append(close_val)

    def calculate_fair_value(self, current_close):
        """
        Liczy real-time na podstawie historycznych i obecnego zamknięcia.
        Zwraca: (fair_value_yes, reason, rsi, momentum_1h)
        """
        temp_closes = list(self.klines)
        if len(temp_closes) < 16:
            return 0.50, "WAIT_FOR_DATA", 50.0, 0.0
            
        closes = temp_closes + [current_close]
        
        df = pd.DataFrame({'close': closes})
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = (-delta.clip(upper=0))
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]
        
        mom_1h = ((closes[-1] - closes[-5]) / closes[-5]) * 100
        
        fair_value_up = self.base_prob_up
        reason = "NEUTRAL"
        
        # Hierarchia sygnałów ze zbudowanego statystycznie modelu Edge!
        # Uważaj, sprawdzamy najpierw najsilniejsze sygnały RSI, potem Momentum.
        
        if current_rsi < 30:
            fair_value_up = 0.581
            reason = "RSI_OVERSOLD"
        elif mom_1h < -0.6:  # Zaniżony próg Dumpu, aby łapać w trakcie trwania świecy
            fair_value_up = 0.575
            reason = "MOMENTUM_1H_DUMP"
            
        elif current_rsi > 70:
            fair_value_up = 0.444
            reason = "RSI_OVERBOUGHT"
        elif mom_1h > 0.6:  # Zaniżony próg Pumpy
            fair_value_up = 0.425
            reason = "MOMENTUM_1H_PUMP"
            
        return fair_value_up, reason, current_rsi, mom_1h
