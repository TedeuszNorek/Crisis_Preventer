import asyncio
import aiohttp
import json
import logging
import re
import math
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

KALSHI_URL = "https://api.kalshi.com/trade-api/v2/markets?status=open&limit=1000"
POLY_URL = "https://gamma-api.polymarket.com/events?active=true&limit=100&offset=0"
DERIBIT_URL = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option"
BINANCE_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"

def norm_dist(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def risk_neutral_prob(S, K, IV, t, r=0.0):
    if t <= 0 or IV <= 0: return 0
    sigma = IV
    d2 = (math.log(S / K) + (r - 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
    return norm_dist(d2)

def parse_deribit_expiry(expiry_str):
    try:
        return datetime.strptime(expiry_str, "%d%b%y").replace(tzinfo=timezone.utc)
    except:
        return datetime.max.replace(tzinfo=timezone.utc)

def parse_btc_strike(title):
    title = title.lower()
    if 'bitcoin' not in title and 'btc' not in title:
        return None
    m = re.search(r'\$?([0-9]{2,3}),?([0-9]{3})', title)
    if m:
        return float(m.group(1) + m.group(2))
    m = re.search(r'\$?([0-9]{2,3})k', title)
    if m:
        return float(m.group(1)) * 1000
    return None

async def fetch_json(session, url):
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logging.error(f"Failed to fetch {url}: {resp.status}")
                return None
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

async def main():
    async with aiohttp.ClientSession() as session:
        logging.info("Fetching Kalshi markets...")
        kalshi_data = await fetch_json(session, KALSHI_URL)
        kalshi_markets = kalshi_data.get("markets", []) if kalshi_data else []

        logging.info("Fetching Polymarket markets...")
        poly_events = await fetch_json(session, POLY_URL) or []

        logging.info("Fetching Binance BTC Price...")
        binance_data = await fetch_json(session, BINANCE_URL)
        btc_price = float(binance_data['price']) if binance_data else 0.0

        logging.info("Fetching Deribit options...")
        deribit_data = await fetch_json(session, DERIBIT_URL)
        deribit_options = deribit_data.get("result", []) if deribit_data else []

        if not btc_price or not deribit_options:
            logging.error("Failed to fetch essential crypto data.")
            return

        # 1. Kalshi vs Polymarket general overlaps (from original script)
        print("\n" + "="*80)
        print(" KALSHI vs POLYMARKET OVERLAPS ")
        print("="*80)
        
        keywords = ["fed", "rate", "bitcoin", "btc", "eth", "ethereum", "election", "trump", "biden", "harris", "debt"]
        overlaps = []
        for k_market in kalshi_markets:
            k_title = k_market.get("title", "")
            k_yes_price = k_market.get("yes_ask", 0) / 100.0
            
            for p_event in poly_events:
                p_title = p_event.get("title", "")
                
                common_words = set(re.sub(r'[^a-z0-9\s]', '', k_title.lower()).split()) & set(re.sub(r'[^a-z0-9\s]', '', p_title.lower()).split())
                important_overlap = [w for w in common_words if w in keywords]
                
                if len(important_overlap) >= 1 or len(common_words) >= 4:
                    p_markets = p_event.get("markets", [])
                    if p_markets:
                        p_market = p_markets[0]
                        p_yes_price = float(p_market.get("outcomePrices", ["0", "0"])[0])
                        overlaps.append({
                            "k_title": k_title,
                            "p_title": p_title,
                            "diff": abs(k_yes_price - p_yes_price),
                            "k_price": k_yes_price,
                            "p_price": p_yes_price
                        })
        
        overlaps.sort(key=lambda x: x["diff"], reverse=True)
        for o in overlaps[:10]:
            print(f"{o['k_title'][:34]:<35} | {o['p_title'][:34]:<35} | K: {o['k_price']:.2f} | P: {o['p_price']:.2f} | DIFF: {o['diff']:.2f}")


        # 2. Polymarket BTC vs Deribit Options Arbitrage
        print("\n" + "="*100)
        print(f" POLYMARKET BTC vs DERIBIT OPTIONS ARBITRAGE (BTC Spot: ${btc_price:,.2f})")
        print("="*100)
        print(f"{'POLYMARKET EVENT':<55} | {'STRIKE':<8} | {'POLY %':<6} | {'DERIBIT %':<9} | {'DIFF'}")
        print("-" * 100)
        
        now = datetime.now(timezone.utc)
        btc_arbitrage = []

        for event in poly_events:
            title = event.get('title', '')
            strike = parse_btc_strike(title)
            if not strike: continue
            
            end_date_str = event.get('endDate')
            if not end_date_str: continue
            
            try:
                poly_end = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except:
                continue

            p_markets = event.get("markets", [])
            if not p_markets: continue
            p_yes_price = float(p_markets[0].get("outcomePrices", ["0", "0"])[0])
            if p_yes_price == 0: continue

            # Find closest Deribit Option
            best_option = None
            min_days_diff = 999
            
            for opt in deribit_options:
                parts = opt['instrument_name'].split('-')
                if len(parts) < 4: continue
                if parts[3] != 'C': continue # we want Calls for "above" questions
                if float(parts[2]) != strike: continue
                
                exp_dt = parse_deribit_expiry(parts[1])
                days_diff = abs((exp_dt - poly_end).days)
                
                if days_diff < min_days_diff:
                    min_days_diff = days_diff
                    best_option = opt

            if best_option and min_days_diff <= 14: # Allow 2 week mismatch max
                exp_dt = parse_deribit_expiry(best_option['instrument_name'].split('-')[1])
                t = (exp_dt - now).total_seconds() / (365.25 * 24 * 3600)
                iv = float(best_option.get('mark_iv', 0)) / 100.0
                
                deribit_prob = risk_neutral_prob(btc_price, strike, iv, t)
                
                diff = abs(p_yes_price - deribit_prob)
                btc_arbitrage.append({
                    "title": title,
                    "strike": strike,
                    "poly_prob": p_yes_price,
                    "deribit_prob": deribit_prob,
                    "diff": diff,
                    "deribit_expiry": exp_dt.strftime("%Y-%m-%d"),
                    "poly_expiry": poly_end.strftime("%Y-%m-%d")
                })

        btc_arbitrage.sort(key=lambda x: x['diff'], reverse=True)
        for a in btc_arbitrage:
            print(f"{a['title'][:54]:<55} | ${a['strike']:<7.0f} | {a['poly_prob']:.2f}   | {a['deribit_prob']:.2f}      | {a['diff']:.2f}")

        print("="*100)

if __name__ == "__main__":
    asyncio.run(main())
