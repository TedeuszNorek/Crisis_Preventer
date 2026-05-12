import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import urllib.request
import json
import sys
import time
import asyncio
import httpx
import pandas as pd
from datetime import datetime, timezone

# Import bazy danych
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.api.users_db import get_user_status
from src.alerts.gamma_squeeze import calculate_squeeze_metrics

app = FastAPI(title="SignalVortex TWA API")

# Allow CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache for on-chain metrics
ONCHAIN_CACHE = {
    "data": None,
    "last_updated": 0,
    "ttl": 3600  # 1 hour
}

def fetch_onchain_metrics(btc_price, price_change_24h):
    global ONCHAIN_CACHE
    now = time.time()
    
    if ONCHAIN_CACHE["data"] and (now - ONCHAIN_CACHE["last_updated"] < ONCHAIN_CACHE["ttl"]):
        return ONCHAIN_CACHE["data"]
    
    # Smart Mock / Live Integration Placeholder
    # Directionally accurate mock based on BTC price action
    # SOPR > 1 means people are in profit.
    # Miner Netflow > 0 means miners are sending to exchanges.
    
    sopr_base = 1.02 if price_change_24h > 0 else 0.98
    # Add some "noise" or trend-based logic
    sopr = sopr_base + (price_change_24h / 500.0) 
    
    # Miner netflow: higher price usually leads to some miner selling
    miner_flow = 150 + (price_change_24h * 10) # Mock BTC amount
    
    onchain_data = {
        "sopr": round(sopr, 4),
        "minerNetflow": round(miner_flow, 2),
        "healthScore": 75 if price_change_24h > -2 else 45,
        "interpretation": {
            "sopr": "Profit taking elevated" if sopr > 1.05 else "Healthy re-accumulation" if sopr > 0.99 else "Capitulation phase",
            "miner": "Miner distribution" if miner_flow > 500 else "Stable accumulation"
        }
    }
    
    ONCHAIN_CACHE["data"] = onchain_data
    ONCHAIN_CACHE["last_updated"] = now
    return onchain_data

def parse_deribit_expiry(expiry_str):
    try:
        return datetime.strptime(expiry_str, "%d%b%y")
    except:
        return datetime.max

async def fetch_json(client, url):
    response = await client.get(url, timeout=10.0)
    response.raise_for_status()
    return response.json()

def calculate_max_pain(strikes_data):
    """
    Simple Max Pain calculation for a set of strikes.
    strikes_data: list of dicts with 'strike', 'type', 'oi'
    """
    if not strikes_data:
        return 0
    
    unique_strikes = sorted(list(set(s['strike'] for s in strikes_data)))
    min_pain = float('inf')
    max_pain_strike = 0
    
    for test_price in unique_strikes:
        current_pain = 0
        for s in strikes_data:
            if s['type'] == 'CALL':
                current_pain += max(0, test_price - s['strike']) * s['oi']
            else:
                current_pain += max(0, s['strike'] - test_price) * s['oi']
        
        if current_pain < min_pain:
            min_pain = current_pain
            max_pain_strike = test_price
            
    return max_pain_strike

@app.get("/api/options-summary")
async def get_options_summary():
    """
    Fetches real-time market data from Deribit (options) and Binance (spot + futures + depth).
    Returns both FREE and PRO tier data in one payload with < 800ms latency goal.
    """
    result = {}
    
    async with httpx.AsyncClient(headers={'User-Agent': 'SignalVortex-Terminal/1.0'}) as client:
        # Define tasks for parallel execution
        tasks = [
            fetch_json(client, "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option"),
            fetch_json(client, "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"),
            fetch_json(client, "https://fapi.binance.com/fapi/v1/open_interest?symbol=BTCUSDT"),
            fetch_json(client, "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT"),
            fetch_json(client, "https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=1h&limit=1"),
            fetch_json(client, "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=100") # For OBI
        ]
        
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            deribit_data = responses[0] if not isinstance(responses[0], Exception) else {"result": []}
            binance_spot = responses[1] if not isinstance(responses[1], Exception) else {}
            futures_oi = responses[2] if not isinstance(responses[2], Exception) else {}
            binance_funding = responses[3] if not isinstance(responses[3], Exception) else {}
            ls_data = responses[4] if not isinstance(responses[4], Exception) else []
            binance_depth = responses[5] if not isinstance(responses[5], Exception) else {"bids": [], "asks": []}
        except Exception as e:
            print(f"Async gather error: {e}")
            return {"error": "Failed to fetch market data"}

    # === BINANCE SPOT PROCESSING ===
    btc_price = float(binance_spot.get('lastPrice', 0))
    price_change_24h = float(binance_spot.get('priceChangePercent', 0))
    result.update({
        "btcPrice": btc_price,
        "priceChange24h": price_change_24h,
        "spotVolume": float(binance_spot.get('volume', 0)),
        "spotVolumeUsd": float(binance_spot.get('quoteVolume', 0)),
        "high24h": float(binance_spot.get('highPrice', 0)),
        "low24h": float(binance_spot.get('lowPrice', 0)),
    })

    # === ORDERBOOK IMBALANCE (OBI) ===
    try:
        # Calculate OBI within 1.5% of spot
        bids = binance_depth.get('bids', [])
        asks = binance_depth.get('asks', [])
        
        range_pct = 0.015
        lower_bound = btc_price * (1 - range_pct)
        upper_bound = btc_price * (1 + range_pct)
        
        bid_vol = sum(float(b[1]) for b in bids if float(b[0]) >= lower_bound)
        ask_vol = sum(float(a[1]) for a in asks if float(a[0]) <= upper_bound)
        
        obi = (bid_vol - ask_vol) / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0
        result["obi"] = round(obi, 4)
    except:
        result["obi"] = 0

    # === DERIBIT OPTIONS PROCESSING ===
    try:
        data = deribit_data.get('result', [])
        now = datetime.now(timezone.utc)
        
        call_oi = 0
        put_oi = 0
        strikes = []
        expiries_data = {}
        total_gamma = 0
        
        # Initial state for options data
        result.update({
            "putCallRatioOi": 0,
            "callOi": 0,
            "putOi": 0,
            "netGamma": 0,
            "gexProfile": [],
            "expiries": [],
            "whaleStrikes": [],
            "marketRegime": "INITIALIZING..."
        })

        for item in data:
            instrument = item['instrument_name']
            parts = instrument.split('-')
            if len(parts) < 4: continue
            
            expiry_str = parts[1]
            strike = float(parts[2])
            option_type = parts[3]
            oi = item.get('open_interest', 0)
            vol = item.get('volume', 0)
            
            greeks = item.get('greeks', {})
            gamma = greeks.get('gamma', 0)
            
            # Gamma Exposure calculation (simplified MM model)
            item_gamma = gamma * oi * btc_price * 0.01 # Nominal Gamma for 1% move
            
            if strike not in gex_profile:
                gex_profile[strike] = 0
            
            if option_type == 'C':
                call_oi += oi
                total_gamma += item_gamma
                gex_profile[strike] += item_gamma
            else:
                put_oi += oi
                total_gamma -= item_gamma
                gex_profile[strike] -= item_gamma
            
            # Grouping and Metadata
            if expiry_str not in expiries_data:
                try:
                    expiry_dt = parse_deribit_expiry(expiry_str)
                    if expiry_dt.tzinfo is None:
                        expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                    dte = (expiry_dt - now).days
                    
                    expiries_data[expiry_str] = {
                        'oi': 0, 'vol': 0, 'call_oi': 0, 'put_oi': 0, 
                        'strikes': [], 'dte': dte,
                        'isExotic': expiry_str.endswith('24') or expiry_str.endswith('25')
                    }
                except:
                    continue
                
            exp_info = expiries_data[expiry_str]
            exp_info['oi'] += oi
            exp_info['vol'] += vol
            exp_info['strikes'].append({'strike': strike, 'type': 'CALL' if option_type == 'C' else 'PUT', 'oi': oi})
            if option_type == 'C': exp_info['call_oi'] += oi
            else: exp_info['put_oi'] += oi
            
            strikes.append({
                'strike': strike, 'type': 'CALL' if option_type == 'C' else 'PUT',
                'expiry': expiry_str, 'oi': oi, 'vol': vol, 'gamma': gamma
            })

        # Format GEX Profile for frontend
        sorted_gex = sorted(gex_profile.items())
        gex_list = [{"strike": s, "gex": round(g, 2)} for s, g in sorted_gex]
        
        # Calculate Gamma Flip Price (where net gamma crosses zero)
        gamma_flip = btc_price # Default to current price for safety
        if len(sorted_gex) > 2:
            for i in range(len(sorted_gex) - 1):
                s1, g1 = sorted_gex[i]
                s2, g2 = sorted_gex[i+1]
                if (g1 <= 0 and g2 > 0) or (g1 >= 0 and g2 < 0):
                    # Linear interpolation for zero crossing
                    if abs(g2 - g1) > 0:
                        gamma_flip = s1 - g1 * (s2 - s1) / (g2 - g1)
                        break
        
        # Calculate estimate of Delta Hedging Sensitivity
        # approx: total_gamma (in BTC per 1% move)
        hedge_sensitivity = abs(total_gamma) # Nominally in BTC
        
        # Filter for relevant range (±20% of spot)
        gex_list = [g for g in gex_list if btc_price * 0.8 <= g['strike'] <= btc_price * 1.2]

        # Expiries list with institutional flags
        expiries_list = []
        for date, info in expiries_data.items():
            if info['oi'] > 100:
                mp = calculate_max_pain(info['strikes'])
                expiries_list.append({
                    "date": date, "oi": info['oi'], "vol": info['vol'],
                    "call_oi": info['call_oi'], "put_oi": info['put_oi'],
                    "max_pain": mp, "dte": info['dte'], "isExotic": info['isExotic'],
                    "optionVelocity": round(info['vol'] / info['oi'], 2) if info['oi'] > 0 else 0
                })
        
        try:
            expiries_list.sort(key=lambda x: parse_deribit_expiry(x['date']))
        except:
            pass

        # Calculate Gamma Squeeze Risk
        squeeze_metrics = calculate_squeeze_metrics(
            btc_price, 
            [{"strike": s, "gex": g} for s, g in sorted_gex], 
            total_gamma, 
            gamma_flip
        )

        result.update({
            "putCallRatioOi": round(put_oi / call_oi, 2) if call_oi > 0 else 0,
            "callOi": round(call_oi, 2),
            "putOi": round(put_oi, 2),
            "netGamma": round(total_gamma, 2),
            "gammaFlip": round(gamma_flip, 1),
            "hedgeSensitivity": round(hedge_sensitivity, 2),
            "gexProfile": gex_list,
            "expiries": expiries_list[:8],
            "whaleStrikes": sorted(strikes, key=lambda x: x['oi'], reverse=True)[:15],
            "marketRegime": "RE-STABILIZING" if total_gamma > 0 else "ACCELERATING RISK",
            "squeezeMetrics": squeeze_metrics
        })
    except Exception as e:
        print(f"Deribit processing error: {e}")

    # === FINALIZE BINANCE FUTURES ===
    result["futuresOI"] = float(futures_oi.get('openInterest', 0))
    result["fundingRate"] = float(binance_funding.get('lastFundingRate', 0))
    if ls_data and len(ls_data) > 0:
        result["longRatio"] = float(ls_data[0].get('longAccount', 0.5))
        result["shortRatio"] = float(ls_data[0].get('shortAccount', 0.5))

    # On-chain
    try:
        result["onchain"] = fetch_onchain_metrics(btc_price, price_change_24h)
    except:
        result["onchain"] = {}

    return result

@app.get("/api/user-status")
def get_status(tg_id: int):
    try:
        status = get_user_status(tg_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

ui_dir = os.path.join(os.path.dirname(__file__), "..", "ui", "tma")
if os.path.exists(ui_dir):
    app.mount("/", StaticFiles(directory=ui_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
