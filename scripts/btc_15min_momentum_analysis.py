#!/usr/bin/env python3
"""
BTC 15-Minute Momentum Analysis for Polymarket Edge
====================================================
Analizuje historyczne dane BTC z Binance, aby odpowiedzieć na pytanie:
"Jakie jest prawdopodobieństwo, że BTC zamknie 15-minutową świecę WYŻEJ
 niż ją otworzył, w zależności od panującego momentum/trendu?"

Metryki momentum:
1. Trend krótkoterminowy (EMA 12 vs EMA 26 na 15min)
2. RSI (14 okresów na 15min)  
3. Momentum cenowe (% zmiana w ostatnich N świecach)
4. Seria (streak) - ile ostatnich świec z rzędu było byczych/niedźwiedzich
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
import os

# ─── CONFIG ───────────────────────────────────────────────────────
SYMBOL = "BTCUSDT"
INTERVAL = "15m"
# Pobieramy ~90 dni danych (8640 świec 15min)
DAYS_BACK = 90
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reports")

# ─── BINANCE DATA FETCHER ────────────────────────────────────────
def fetch_binance_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Pobiera dane klines z Binance API (publiczne, bez klucza)."""
    url = "https://api.binance.com/api/v3/klines"
    all_data = []
    
    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    current = start_ts
    batch = 0
    while current < end_ts:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current,
            "limit": 1000  # max per request
        }
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            break
            
        all_data.extend(data)
        current = data[-1][0] + 1  # next ms after last candle
        batch += 1
        
        if batch % 3 == 0:
            print(f"  📥 Pobrano {len(all_data)} świec ({batch} batchy)...")
        
        time.sleep(0.15)  # rate limit courtesy
    
    df = pd.DataFrame(all_data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ])
    
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[col] = df[col].astype(float)
    
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    
    return df

# ─── INDICATORS ───────────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Dodaje wskaźniki momentum do DataFrame."""
    
    # 1. Bullish candle (close > open)
    df["bullish"] = (df["close"] > df["open"]).astype(int)
    
    # 2. Candle return (%)
    df["candle_return_pct"] = ((df["close"] - df["open"]) / df["open"]) * 100
    
    # 3. EMA 12 i EMA 26
    df["ema12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema26"] = df["close"].ewm(span=26, adjust=False).mean()
    df["ema_trend"] = np.where(df["ema12"] > df["ema26"], "BULL", "BEAR")
    
    # 4. RSI (14 okresów)
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))
    
    # RSI buckets
    df["rsi_zone"] = pd.cut(df["rsi"], 
                            bins=[0, 30, 45, 55, 70, 100],
                            labels=["OVERSOLD<30", "WEAK_30-45", "NEUTRAL_45-55", "STRONG_55-70", "OVERBOUGHT>70"])
    
    # 5. Momentum: % zmiana w ostatnich 4 świecach (=1h lookback)
    df["momentum_1h"] = df["close"].pct_change(periods=4) * 100
    df["momentum_4h"] = df["close"].pct_change(periods=16) * 100
    
    # Momentum buckets
    df["mom_1h_zone"] = pd.cut(df["momentum_1h"],
                               bins=[-np.inf, -1.0, -0.3, 0.3, 1.0, np.inf],
                               labels=["STRONG_DOWN", "MILD_DOWN", "FLAT", "MILD_UP", "STRONG_UP"])
    
    df["mom_4h_zone"] = pd.cut(df["momentum_4h"],
                               bins=[-np.inf, -2.0, -0.5, 0.5, 2.0, np.inf],
                               labels=["STRONG_DOWN", "MILD_DOWN", "FLAT", "MILD_UP", "STRONG_UP"])
    
    # 6. Streak (ile z rzędu byczych/niedźwiedzich)
    streak = []
    current_streak = 0
    for i, row in df.iterrows():
        if i == 0:
            current_streak = 1 if row["bullish"] else -1
        else:
            if row["bullish"] and current_streak > 0:
                current_streak += 1
            elif not row["bullish"] and current_streak < 0:
                current_streak -= 1
            else:
                current_streak = 1 if row["bullish"] else -1
        streak.append(current_streak)
    df["streak"] = streak
    
    # Streak bucket (poprzednia świeca, bo streak bieżącej jest znany post-factum)
    df["prev_streak"] = df["streak"].shift(1)
    df["streak_zone"] = pd.cut(df["prev_streak"],
                               bins=[-np.inf, -3, -1, 0, 1, 3, np.inf],
                               labels=["BEAR_STREAK_3+", "BEAR_STREAK_1-2", "NEUTRAL_BEAR", 
                                       "NEUTRAL_BULL", "BULL_STREAK_1-2", "BULL_STREAK_3+"])
    
    # 7. Volatility (ATR-like: high-low range as % of open)
    df["range_pct"] = ((df["high"] - df["low"]) / df["open"]) * 100
    df["avg_range"] = df["range_pct"].rolling(window=20).mean()
    df["vol_regime"] = np.where(df["range_pct"] > df["avg_range"] * 1.5, "HIGH_VOL",
                       np.where(df["range_pct"] < df["avg_range"] * 0.5, "LOW_VOL", "NORMAL_VOL"))
    
    # 8. Hour of day (UTC)
    df["hour_utc"] = df["open_time"].dt.hour
    df["session"] = pd.cut(df["hour_utc"],
                           bins=[-1, 6, 12, 18, 24],
                           labels=["ASIA_0-6", "EU_6-12", "US_12-18", "LATE_18-24"])
    
    return df

# ─── ANALYSIS ─────────────────────────────────────────────────────
def analyze_conditional_probability(df: pd.DataFrame, group_col: str, target: str = "bullish") -> pd.DataFrame:
    """Liczy P(bullish | grupa) dla danej kolumny grupującej."""
    # Następna świeca jest bycza?
    df["next_bullish"] = df[target].shift(-1)
    
    valid = df.dropna(subset=[group_col, "next_bullish"])
    
    result = valid.groupby(group_col).agg(
        count=("next_bullish", "count"),
        bullish_next=("next_bullish", "sum"),
    )
    result["P_bull_next_15m"] = (result["bullish_next"] / result["count"] * 100).round(2)
    result["P_bear_next_15m"] = (100 - result["P_bull_next_15m"]).round(2)
    result["edge_vs_50"] = (result["P_bull_next_15m"] - 50).round(2)
    
    return result.sort_values("P_bull_next_15m", ascending=False)

def run_full_analysis(df: pd.DataFrame) -> dict:
    """Przeprowadza pełną analizę rozkładu prawdopodobieństw."""
    results = {}
    
    # Bazowe prawdopodobieństwo (unconditional)
    total = len(df) - 1  # -1 bo patrzymy na "następną" świecę
    bullish_total = df["bullish"].iloc[:-1].sum()
    base_prob = bullish_total / total * 100
    results["baseline"] = {
        "total_candles": total,
        "bullish_candles": int(bullish_total),
        "P_bullish_unconditional": round(base_prob, 2)
    }
    
    # Warunkowe prawdopodobieństwa
    analyses = {
        "by_ema_trend": "ema_trend",
        "by_rsi_zone": "rsi_zone",
        "by_momentum_1h": "mom_1h_zone",
        "by_momentum_4h": "mom_4h_zone",
        "by_streak": "streak_zone",
        "by_volatility": "vol_regime",
        "by_session": "session",
    }
    
    for name, col in analyses.items():
        try:
            res = analyze_conditional_probability(df, col)
            results[name] = res.to_dict(orient="index")
        except Exception as e:
            results[name] = {"error": str(e)}
    
    return results

def format_report(results: dict, df: pd.DataFrame) -> str:
    """Generuje czytelny raport tekstowy."""
    lines = []
    lines.append("=" * 80)
    lines.append("📊 BTC 15-MIN MOMENTUM → POLYMARKET EDGE ANALYSIS")
    lines.append(f"   Data range: {df['open_time'].min()} → {df['open_time'].max()}")
    lines.append(f"   Total candles analyzed: {results['baseline']['total_candles']}")
    lines.append("=" * 80)
    
    # Baseline
    b = results["baseline"]
    lines.append(f"\n🎯 BAZOWE PRAWDOPODOBIEŃSTWO (bez filtrów):")
    lines.append(f"   P(BTC zamknie 15min WYŻEJ) = {b['P_bullish_unconditional']:.2f}%")
    lines.append(f"   P(BTC zamknie 15min NIŻEJ) = {100 - b['P_bullish_unconditional']:.2f}%")
    lines.append(f"   Świece bycze: {b['bullish_candles']} / {b['total_candles']}")
    
    # Warunkowe
    section_names = {
        "by_ema_trend": "📈 TREND (EMA12 vs EMA26)",
        "by_rsi_zone": "💪 RSI ZONE (14-period)",
        "by_momentum_1h": "🚀 MOMENTUM 1H (% zmiana ostatnie 4 świece)",
        "by_momentum_4h": "🔥 MOMENTUM 4H (% zmiana ostatnie 16 świec)",
        "by_streak": "🎰 SERIA (ile świec z rzędu bycze/niedźwiedzie)",
        "by_volatility": "⚡ REŻIM ZMIENNOŚCI (Range vs Avg Range)",
        "by_session": "🕐 SESJA HANDLOWA (UTC)",
    }
    
    for key, title in section_names.items():
        lines.append(f"\n{'─' * 80}")
        lines.append(f"{title}")
        lines.append(f"{'─' * 80}")
        
        data = results.get(key, {})
        if "error" in data:
            lines.append(f"   ⚠️ Error: {data['error']}")
            continue
        
        lines.append(f"   {'Warunek':<25} {'N':>6} {'P(UP)':>8} {'P(DOWN)':>8} {'Edge vs 50%':>12}")
        lines.append(f"   {'─'*25} {'─'*6} {'─'*8} {'─'*8} {'─'*12}")
        
        for zone, vals in data.items():
            zone_str = str(zone)[:25]
            n = vals["count"]
            p_bull = vals["P_bull_next_15m"]
            p_bear = vals["P_bear_next_15m"]
            edge = vals["edge_vs_50"]
            
            # Emoji indicator
            if edge > 2:
                indicator = "🟢"
            elif edge < -2:
                indicator = "🔴"
            else:
                indicator = "⚪"
            
            lines.append(f"   {zone_str:<25} {n:>6} {p_bull:>7.2f}% {p_bear:>7.2f}% {edge:>+10.2f}% {indicator}")
    
    # Podsumowanie kluczowych edge'y
    lines.append(f"\n{'=' * 80}")
    lines.append("🏆 KLUCZOWE WNIOSKI DLA POLYMARKET 15-MIN BTC:")
    lines.append("=" * 80)
    
    # Znajdź najsilniejsze edge'e
    all_edges = []
    for key, data in results.items():
        if key == "baseline" or not isinstance(data, dict):
            continue
        for zone, vals in data.items():
            if isinstance(vals, dict) and "edge_vs_50" in vals and vals["count"] > 50:
                all_edges.append({
                    "category": key.replace("by_", ""),
                    "zone": zone,
                    "edge": vals["edge_vs_50"],
                    "prob": vals["P_bull_next_15m"],
                    "count": vals["count"]
                })
    
    all_edges.sort(key=lambda x: abs(x["edge"]), reverse=True)
    
    lines.append("\n   TOP 10 najsilniejszych warunkowych odchyleń (min 50 obserwacji):")
    for i, e in enumerate(all_edges[:10], 1):
        direction = "BULL" if e["edge"] > 0 else "BEAR"
        lines.append(f"   {i:>2}. [{e['category']}/{e['zone']}] → P(UP)={e['prob']:.1f}% "
                     f"(edge: {e['edge']:+.2f}%, N={e['count']}) {'🟢' if direction=='BULL' else '🔴'}")
    
    lines.append(f"\n   ⚠️  UWAGA: Edge poniżej ±1.5% jest prawdopodobnie w granicach szumu statystycznego.")
    lines.append(f"   ⚠️  Aby edge był tradeable na Polymarket, musi pokryć spread CLOB + gas fees.")
    lines.append(f"   💡 Optymalny target: warunki z edge > 3% i N > 200 obserwacji.\n")
    
    return "\n".join(lines)


# ─── MAIN ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔄 Pobieram historyczne dane BTC/USDT 15min z Binance...")
    print(f"   Zakres: ostatnie {DAYS_BACK} dni")
    
    df = fetch_binance_klines(SYMBOL, INTERVAL, DAYS_BACK)
    print(f"✅ Pobrano {len(df)} świec 15-minutowych")
    print(f"   Od: {df['open_time'].min()}")
    print(f"   Do: {df['open_time'].max()}")
    
    print("\n🔧 Obliczam wskaźniki momentum...")
    df = add_indicators(df)
    
    print("📊 Przeprowadzam analizę warunkowych prawdopodobieństw...")
    results = run_full_analysis(df)
    
    report = format_report(results, df)
    print(report)
    
    # Zapisz raport
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    report_path = os.path.join(OUTPUT_DIR, f"btc_15min_momentum_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"💾 Raport zapisany: {report_path}")
    
    # Zapisz surowe dane z wskaźnikami do CSV
    csv_path = os.path.join(OUTPUT_DIR, f"btc_15min_data_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
    df.to_csv(csv_path, index=False)
    print(f"💾 Dane CSV: {csv_path}")
    
    # Zapisz JSON z wynikami
    json_path = os.path.join(OUTPUT_DIR, f"btc_15min_probs_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"💾 JSON: {json_path}")
