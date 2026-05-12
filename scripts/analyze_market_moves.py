"""Analyze largest options market movements from Binance (Crypto) and Polygon (Equities)."""
import sys
import os
import logging
from datetime import datetime, timezone
import pandas as pd
from typing import List, Dict, Any

# Ensure project root is in path
sys.path.insert(0, os.getcwd())

from signalvortex.core.config import Config
from signalvortex.sources.binance.options import BinanceOptionsClient
from signalvortex.sources.polygon.client import PolygonClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
LOGGER = logging.getLogger("MarketMoves")

def print_header(title: str):
    print(f"\n{'='*80}")
    print(f" {title}")
    print(f"{'='*80}")

def analyze_binance_moves():
    """Analyze Binance Crypto Options."""
    print_header("BINANCE CRYPTO OPTIONS (24h Moves)")
    
    try:
        client = BinanceOptionsClient()
        # Test connectivity
        client.ping()
        
        tickers = client.get_ticker()
        if tickers.empty:
            print("No ticker data received from Binance.")
            return

        # Ensure numeric columns
        cols = ['priceChangePercent', 'lastPrice', 'volume', 'amount']
        for c in cols:
            if c in tickers.columns:
                tickers[c] = pd.to_numeric(tickers[c], errors='coerce')

        # Filter for active contracts (Volume > 0) to reduce noise
        active_tickers = tickers[tickers['volume'] > 0].copy()
        if active_tickers.empty:
            print("No active options contracts (Volume > 0) found on Binance.")
            # Fallback to showing open interest if available (requires mark price, doing volume for now as per plan)
            return

        # 1. Top Price Gainers
        print("\n[Top 5 Gainers (24h %)]")
        top_gainers = active_tickers.nlargest(5, 'priceChangePercent')
        print(top_gainers[['symbol', 'lastPrice', 'priceChangePercent', 'volume']].to_string(index=False))

        # 2. Top Price Losers
        print("\n[Top 5 Losers (24h %)]")
        top_losers = active_tickers.nsmallest(5, 'priceChangePercent')
        print(top_losers[['symbol', 'lastPrice', 'priceChangePercent', 'volume']].to_string(index=False))

        # 3. Most Active (highest volume)
        print("\n[Top 5 Most Active by Volume]")
        most_active = active_tickers.nlargest(5, 'volume')
        print(most_active[['symbol', 'lastPrice', 'priceChangePercent', 'volume']].to_string(index=False))
        
        # Summary Stats
        total_vol = active_tickers['volume'].sum()
        btc_vol = active_tickers[active_tickers['symbol'].str.contains('BTC')]['volume'].sum()
        eth_vol = active_tickers[active_tickers['symbol'].str.contains('ETH')]['volume'].sum()
        
        print(f"\nTotal 24h Volume: {total_vol:.2f} contracts")
        print(f"BTC Volume: {btc_vol:.2f}")
        print(f"ETH Volume: {eth_vol:.2f}")

    except Exception as e:
        LOGGER.error(f"Error analyzing Binance data: {e}")

def analyze_polygon_moves(config: Config):
    """Analyze Polygon Equity Options."""
    print_header("POLYGON EQUITY OPTIONS (Snapshot Analysis)")
    
    if not config.polygon.api_key:
        print("[!] No Polygon API Key found. Skipping Polygon analysis.")
        return

    client = PolygonClient(api_key=config.polygon.api_key)
    
    # Target major ETFs/Stocks for a "market pulse"
    targets = ["SPY", "QQQ", "IWM", "NVDA", "TSLA"]
    
    today = datetime.now(timezone.utc).date()
    
    for ticker in targets:
        print(f"\n> Analyzing {ticker} Options...")
        try:
            # We don't have a direct "24h change" in snapshot without prev close, 
            # but we can look at High Volume and unusual Activity.
            # Fetching chain might be heavy, let's limit response if possible or just get near-term
            
            # Using fetch_option_chain which iterates snapshots. 
            # Warning: specific to near-term expiries might be better but client gets ALL for underlying.
            # We'll use a try/except block to handle large responses or rate limits.
            
            # Iterating manually to control limit
            snapshots = []
            count = 0
            max_items = 1000 # Limit to avoid fetching thousands of contracts for SPY
            
            # Using iter_option_snapshots directly to control the flow
            for snap in client.iter_option_snapshots(ticker, limit=250):
                snapshots.append(snap)
                count += 1
                if count >= max_items:
                    break
            
            if not snapshots:
                print(f"  No data found for {ticker}.")
                continue
                
            # Process snapshots
            data = []
            spot_price = None
            
            for s in snapshots:
                details = s.get('details', {})
                day = s.get('day', {})
                
                # Try to get spot
                if spot_price is None:
                    # Logic from client.py _extract_spot
                    und = s.get('underlying_asset', {})
                    if und.get('last_trade', {}).get('price'):
                         spot_price = und.get('last_trade', {}).get('price')

                if day.get('volume', 0) > 0:
                    row = {
                        'symbol': details.get('ticker'),
                        'expiry': details.get('expiration_date'),
                        'strike': details.get('strike_price'),
                        'type': details.get('contract_type'),
                        'volume': day.get('volume', 0),
                        'open_interest': s.get('open_interest', 0),
                        'iv': s.get('greeks', {}).get('implied_volatility'),
                        'last': day.get('close') or day.get('last_trade_price') # Fallback
                    }
                    data.append(row)
            
            if not data:
                print(f"  No active contracts (Volume > 0) found in first {max_items} snapshots.")
                continue
                
            df = pd.DataFrame(data)
            
            # Top by Volume
            top_vol = df.nlargest(5, 'volume')
            print(f"  [Top 5 by Volume]")
            print(top_vol[['symbol', 'type', 'expiry', 'strike', 'volume', 'iv']].to_string(index=False))
            
            # Highest IV (min volume filter to avoid garbage)
            high_iv = df[df['volume'] > 100].nlargest(5, 'iv')
            if not high_iv.empty:
                print(f"\n  [Top 5 High IV (Vol > 100)]")
                print(high_iv[['symbol', 'type', 'expiry', 'strike', 'iv', 'volume']].to_string(index=False))

        except Exception as e:
            LOGGER.error(f"  Error analyzing {ticker}: {e}")

def main():
    config = Config.load()
    
    print("Starting Options Market Analysis...")
    print(f"Time: {datetime.now(timezone.utc)}")
    
    analyze_binance_moves()
    analyze_polygon_moves(config)
    
    print_header("Analysis Complete")

if __name__ == "__main__":
    main()
