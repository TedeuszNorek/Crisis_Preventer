"""Detect RSI Divergence (Bullish) across Crypto and Stocks."""
import sys
import os
import logging
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple

# Ensure project root is in path
sys.path.insert(0, os.getcwd())

from signalvortex.core.config import Config
from signalvortex.sources.binance.client import BinanceFuturesClient
from signalvortex.sources.polygon.client import PolygonClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
LOGGER = logging.getLogger("RSIDivergence")


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    # Use exponential moving average for smoother RSI (Wilder's Smoothing)
    # Note: Standard Pandas rolling is simple avg. For strictly standard RSI we need EMA.
    # Let's use Wilder's matching TradingView:
    # U = delta > 0 ? delta : 0
    # D = delta < 0 ? -delta : 0
    # Smoothed U = (Prev U * (n-1) + Curr U) / n
    
    # Fast implementation using Pandas ewm
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def detect_bullish_divergence(df: pd.DataFrame, window: int = 5) -> List[Dict[str, Any]]:
    """Detect Bullish Divergence in Price vs RSI.
    
    Bullish Divergence:
    - Price makes Lower Low (LL)
    - RSI makes Higher Low (HL)
    
    Args:
        df: DataFrame with 'close' and 'rsi' columns.
        window: Window to check for local minima (pivots).
    
    Returns:
        List of divergence events.
    """
    if 'rsi' not in df.columns or len(df) < window * 2:
        return []

    # Find local minima
    # A point is a local minimum if it is lower than 'window' neighbors on both sides
    # For scanned assets, we only care about RECENT divergence (last ~20 candles)
    
    # Simple pivot detection
    # We will look for 2 most recent bottoms in the last N candles
    
    # Limit scan to last 50 candles for performance and relevance
    recent = df.iloc[-50:].copy().reset_index()
    
    minima_indices = []
    
    # 1. Identify pivots (simple lowest point in window)
    # We'll stick to a simpler "ZigZag" style or just strict local minima
    for i in range(window, len(recent) - window):
        is_low = True
        curr_low = recent['low'].iloc[i] # Using Low price for Price divergence
        curr_rsi = recent['rsi'].iloc[i]
        
        # Check neighbors
        for k in range(1, window + 1):
            if recent['low'].iloc[i-k] <= curr_low or recent['low'].iloc[i+k] <= curr_low:
                is_low = False
                break
        
        if is_low:
            minima_indices.append(i)
            
    if len(minima_indices) < 2:
        return []

    divergences = []
    
    # Check the last 2 minima
    # If standard divergence logic: 
    # Current Pivot (P2) is later than Previous Pivot (P1)
    
    # We want the MOST RECENT one to be relevant
    last_idx = minima_indices[-1]
    
    # Ensure the last pivot is actually somewhat recent (e.g. within last 10 candles)
    if len(recent) - last_idx > 15:
        return [] # Too old
        
    p2_idx = last_idx
    p2_price = recent['low'].iloc[p2_idx]
    p2_rsi = recent['rsi'].iloc[p2_idx]
    p2_time = recent['timestamp'].iloc[p2_idx] if 'timestamp' in recent.columns else p2_idx
    
    # Look at previous pivots
    for p1_idx in reversed(minima_indices[:-1]):
        p1_price = recent['low'].iloc[p1_idx]
        p1_rsi = recent['rsi'].iloc[p1_idx]
        
        # Bullish Divergence Logic:
        # Price: P2 < P1 (Lower Low)
        # RSI: P2 > P1 (Higher Low)
        
        if p2_price < p1_price and p2_rsi > p1_rsi:
            # Found one!
            div = {
                "type": "Bullish",
                "time": p2_time,
                "price_low_1": p1_price,
                "price_low_2": p2_price,
                "rsi_low_1": p1_rsi,
                "rsi_low_2": p2_rsi,
                "rsi_current": recent['rsi'].iloc[-1]
            }
            divergences.append(div)
            break # Just find the most recent matching pair
            
    return divergences

def print_section(title: str):
    print(f"\n{'-'*60}")
    print(f"{title}")
    print(f"{'-'*60}")

def analyze_crypto(symbols: List[str] = None):
    # If no symbols provided, fetch Top 30 by Volume
    client = BinanceFuturesClient()
    
    if not symbols:
        print_section("FETCHING TOP 30 VOLUME PAIRS")
        try:
            tickers = client.get_24hr_ticker()
            if not tickers.empty:
                # Filter for USDT pairs, exclude stablecoins/unusuals
                mask = tickers['symbol'].str.endswith('USDT') & \
                       ~tickers['symbol'].str.contains('USDC') & \
                       ~tickers['symbol'].str.contains('BUSD')
                
                # Top 30 by Quote Volume (Dollar Volume)
                top_tickers = tickers[mask].nlargest(30, 'quoteVolume')
                symbols = top_tickers['symbol'].tolist()
                print(f"Scanning: {', '.join(symbols[:5])} ... and {len(symbols)-5} more.")
            else:
                symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT"]
        except Exception as e:
             LOGGER.error(f"Failed to fetch top tickers: {e}")
             symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    
    # Check 1h (Intraday) & 4h (Swing)
    timeframes = ["1h", "4h"]
    
    for tf in timeframes:
        print_section(f"CHECKING CRYPTO (BINANCE FUTURES - {tf}) - PRE-PUMP SCAN")
        
        for s in symbols:
            try:
                df = client.get_klines(s, interval=tf, limit=200)
                if df.empty:
                    continue
                    
                df['rsi'] = calculate_rsi(df['close'])
                divs = detect_bullish_divergence(df)
                
                if divs:
                    d = divs[0] # Most recent
                    # Calculate % Move since signal
                    # Signal time is when the pivot happened. 
                    # We want to know if price is significantly higher NOW vs then.
                    
                    signal_price = d['price_low_2']
                    current_price = df['close'].iloc[-1]
                    
                    pct_change = ((current_price - signal_price) / signal_price) * 100
                    
                    # PRE-PUMP FILTER:
                    # We want tokens that haven't pumped > 3% since the divergence low.
                    pump_threshold = 3.0 
                    
                    status = "PRE-PUMP" if pct_change < pump_threshold else f"ALREADY MOVED (+{pct_change:.1f}%)"
                    
                    if pct_change < pump_threshold:
                         print(f"[!] {s:<10} | {status} | Time: {d['time']}")
                         print(f"    Values: Lows({d['price_low_1']:.4f} -> {d['price_low_2']:.4f})")
                         print(f"    Price: {signal_price:.4f} -> {current_price:.4f} (+{pct_change:.2f}%)")
                         print(f"    RSI: {d['rsi_low_1']:.1f} -> {d['rsi_low_2']:.1f} (Curr: {d['rsi_current']:.1f})")
                    else:
                         # Optional: Verbose log for things that moved
                         # print(f"    {s:<10} | {status}")
                         pass
                else:
                    pass

            except Exception as e:
                LOGGER.error(f"Error checking {s}: {e}")

def fetch_alpha_vantage_daily(symbol: str, api_key: str) -> pd.DataFrame:
    """Fetch daily time series from Alpha Vantage."""
    import requests
    import time
    
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "apikey": api_key,
        "outputsize": "compact" # 100 data points
    }
    
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        
        # Check for error or rate limit
        if "Note" in data:
            print(f"    [!] Alpha Vantage API Limit reached for {symbol}. Waiting 60s...")
            time.sleep(60) 
            # Retry once
            resp = requests.get(url, params=params)
            data = resp.json()
            
        time_series = data.get("Time Series (Daily)", {})
        if not time_series:
            return pd.DataFrame()
            
        # Parse
        records = []
        for date_str, values in time_series.items():
            records.append({
                "timestamp": pd.to_datetime(date_str),
                "open": float(values.get("1. open", 0)),
                "high": float(values.get("2. high", 0)),
                "low": float(values.get("3. low", 0)),
                "close": float(values.get("4. close", 0)),
                "volume": float(values.get("5. volume", 0))
            })
            
        df = pd.DataFrame(records)
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df
        
    except Exception as e:
        LOGGER.error(f"Failed to fetch {symbol} from Alpha Vantage: {e}")
        return pd.DataFrame()

def analyze_stocks(symbols: List[str], config: Config):
    import time
    print_section("CHECKING STOCKS")
    
    use_alpha = False
    api_key = None
    
    if config.polygon.api_key:
        print(f"Using Polygon API (Key: {config.polygon.api_key[:4]}...)")
        client = PolygonClient(config.polygon.api_key)
        api_key = config.polygon.api_key
    elif config.alpha_vantage.api_key:
        print(f"Using Alpha Vantage API (Key: {config.alpha_vantage.api_key[:4]}...)")
        use_alpha = True
        api_key = config.alpha_vantage.api_key
    else:
        print("Skipping Stocks: No Polygon or Alpha Vantage API Key.")
        return

    today = datetime.now()
    start_date = (today - timedelta(days=365)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    
    for i, s in enumerate(symbols):
        try:
            df = pd.DataFrame()
            
            if use_alpha:
                # Alpha Vantage Rate Limit: 5 calls per minute
                if i > 0 and i % 5 == 0:
                    print("    (Pausing 65s for Alpha Vantage Rate Limit...)")
                    time.sleep(65)
                
                df = fetch_alpha_vantage_daily(s, api_key)
            else:
                # Polygon
                try:
                    df = client.get_aggregates(s, 1, "day", start_date, end_date)
                except Exception as e:
                    if "401" in str(e):
                         print("    [!] Polygon Key Invalid (401). Switch to Alpha Vantage if available.")
                         # Fallback logic if we were using Polygon but it failed
                         if config.alpha_vantage.api_key:
                             print("    -> Switching to Alpha Vantage...")
                             use_alpha = True
                             api_key = config.alpha_vantage.api_key
                             df = fetch_alpha_vantage_daily(s, api_key)
                         else:
                             return
                    else:
                        LOGGER.error(f"Error checking {s} with Polygon: {e}")
                        continue

            if df.empty:
                print(f"    No data for {s}")
                continue
                
            df['rsi'] = calculate_rsi(df['close'])
            divs = detect_bullish_divergence(df)
            
            current_rsi = df['rsi'].iloc[-1]
            status_msg = f"RSI: {current_rsi:.1f}"
            
            if divs:
                d = divs[0]
                print(f"[!] {s:<10} | BULLISH DIVERGANCE DETECTED | Time: {d['time'].strftime('%Y-%m-%d')}")
                print(f"    Values: Lows(${d['price_low_1']:.2f} -> ${d['price_low_2']:.2f}) RSI({d['rsi_low_1']:.1f} -> {d['rsi_low_2']:.1f})")
                print(f"    Current RSI: {current_rsi:.1f}")
            else:
                # Optional: Verbose mode
                # print(f"    {s:<10} | No Signal ({status_msg})")
                pass
                
        except Exception as e:
            LOGGER.error(f"Error checking {s}: {e}")

def main():
    config = Config.load()
    print("DIVERGENCE SCANNER ACTIVATED")
    print(f"Time: {datetime.now(timezone.utc)}")
    
    # Empty list triggers Top 30 fetch in analyze_crypto
    crypto_list = []
    stock_list = ["SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAPL", "MSFT", "AMD", "GOOGL", "AMZN", "META", "COIN", "MSTR"]
    
    analyze_crypto(crypto_list)
    analyze_stocks(stock_list, config)
    
    print("\nScan Complete.")

if __name__ == "__main__":
    main()
