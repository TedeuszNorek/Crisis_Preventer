import requests
import json
from datetime import datetime

url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=100"
headers = {"Accept": "application/json"}

def find_anomalies():
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        events = response.json()
        
        found = []
        for event in events:
            markets = event.get('markets', [])
            for m in markets:
                if m.get('closed', True):
                    continue
                
                prices_str = m.get('outcomePrices', "[]")
                outcomes_str = m.get('outcomes', "[]")
                
                try:
                    prices = json.loads(prices_str)
                    outcomes = json.loads(outcomes_str)
                except Exception:
                    continue
                
                for i, p_str in enumerate(prices):
                    try:
                        p = float(p_str)
                    except:
                        continue
                        
                    # Let's find "free money" - probability > 96%
                    if 0.93 <= p <= 0.99:
                        outcome_name = outcomes[i] if len(outcomes) > i else "YES"
                        found.append({
                            "question": m.get('question'),
                            "outcome": outcome_name,
                            "price": p,
                            "liquidity": m.get('liquidity', "0"),
                            "volume": m.get('volume', "0")
                        })
        return found
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    results = find_anomalies()
    print(f"Znaleziono {len(results)} rynków z P > 93%:")
    results.sort(key=lambda x: x['price'], reverse=True)
    
    for r in results:
        liq = float(r['liquidity'])
        if liq > 500:
            print(f"[{r['price']:.3f}] {r['question'][:80]}... -> KUP: {r['outcome']} | Płynność: ${liq:.0f}")
