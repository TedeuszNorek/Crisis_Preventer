"""Advanced Binance Options sentiment check using Volume (Flow)."""
import sys
import os
import pandas as pd
sys.path.insert(0, os.getcwd())

from signalvortex.sources.binance.options import BinanceOptionsClient

def analyze_options_allocation():
    try:
        client = BinanceOptionsClient()
    except Exception as e:
        print(f"Error initializing client: {e}")
        return

    print("=" * 60)
    print("BINANCE OPTIONS SENTIMENT (24h VOLUME FLOW)")
    print("=" * 60)
    
    try:
        tickers = client.get_ticker()
        
        if tickers.empty:
            print("No ticker data received.")
            return

        # Filters and Copy to avoid SettingWithCopyWarning
        btc_tickers = tickers[tickers['symbol'].str.contains('BTC')].copy()
        
        # Ensure numeric
        cols = ['volume', 'lastPrice', 'amount']
        for c in cols:
            if c in btc_tickers.columns:
                btc_tickers[c] = pd.to_numeric(btc_tickers[c], errors='coerce')
        
        # Split Puts/Calls
        calls = btc_tickers[btc_tickers['symbol'].str.endswith('-C')]
        puts = btc_tickers[btc_tickers['symbol'].str.endswith('-P')]
        
        # 2. 24h Volume (Sentiment/Flow)
        # Volume is in contracts.
        call_vol = calls['volume'].sum()
        put_vol = puts['volume'].sum()
        total_vol = call_vol + put_vol
        
        vol_pcr = put_vol / call_vol if call_vol > 0 else 0.0
        
        print(f"\n[24h Volume (Activity) - FLOW SENTIMENT]")
        print(f"   Total Volume: {total_vol:.2f} contracts")
        print(f"   Call Volume: {call_vol:.2f} ({(call_vol/total_vol)*100:.1f}%)")
        print(f"   Put Volume:  {put_vol:.2f} ({(put_vol/total_vol)*100:.1f}%)")
        print(f"   Volume PCR: {vol_pcr:.2f}")

        print(f"\n   -> Interpretation:")
        if vol_pcr > 0.85:
            print("      ! BEARISH FLOW: Hedging/Protection dominant.")
        elif vol_pcr < 0.60:
            print("      ! BULLISH FLOW: Aggressive upside speculation.")
        else:
            print("      = NEUTRAL FLOW: Balanced activity.")

        # 3. Largest Volume Strikes (Activity Clusters)
        print(f"\n[Top 5 Strikes by Volume]:")
        top_vol = btc_tickers.nlargest(5, 'volume')
        for _, row in top_vol.iterrows():
            print(f"   {row['symbol']}: {row['volume']:.2f} contracts")

        print("\n(Note: Open Interest data currently requires client update. This is Flow data.)")

    except Exception as e:
        print(f"Error analyzing volume: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_options_allocation()
