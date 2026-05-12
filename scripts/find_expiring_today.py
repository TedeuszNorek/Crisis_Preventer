import requests
import json
from datetime import datetime, timezone

url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=1000"
headers = {"Accept": "application/json"}

def find_expiring_today():
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        events = response.json()
        
        today = datetime.now(timezone.utc).date()
        found = []
        
        for event in events:
            # endDate is typically like "2026-04-07T04:00:00Z"
            end_date_str = event.get('endDate')
            if not end_date_str:
                continue
                
            try:
                # Naive parsing to date
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).date()
            except:
                continue
                
            if 0 <= (end_date - today).days <= 7:
                for m in event.get('markets', []):
                    # Zgodnie z wyciągniętą lekcją: trzeba sprawdzać both 'closed' and 'active'
                    if m.get('closed', True) or not m.get('active', False):
                        continue
                        
                    prices_str = m.get('outcomePrices', "[]")
                    outcomes_str = m.get('outcomes', "[]")
                    try:
                        prices = json.loads(prices_str)
                        outcomes = json.loads(outcomes_str)
                    except:
                        continue
                        
                    liq = float(m.get('liquidity', 0) or 0)
                    if liq < 500:
                        continue
                        
                    for i, p_str in enumerate(prices):
                        try:
                            price = float(p_str)
                        except:
                            continue
                            
                        # Interesują nas 90% - 99.5% dające premię ryzyka risk-free
                        if 0.90 <= price <= 0.995:
                            outcome_to_buy = outcomes[i] if len(outcomes) > i else "YES"
                            free_premium = ((1.0 / price) - 1.0) * 100
                            found.append({
                                'question': m.get('question'),
                                'outcome': outcome_to_buy,
                                'price': price,
                                'premium': free_premium,
                                'liquidity': liq,
                                'endDate': end_date_str
                            })
                            
        found.sort(key=lambda x: x['premium'], reverse=True)
        return found
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    results = find_expiring_today()
    print("⏳ DARMOWE PREMIE (90-99.5%) WYGASAJĄCE W TYM TYGODNIU ⏳\n")
    if not results:
        print("Brak takich zakładów w top 1000 eventów na ten tydzień (wszystkie 90+ już zeszły do 1.0 lub nie istnieją).")
    for r in results:
        print(f"[{r['price']:.3f}]$ {r['question']}")
        print(f"   ► Akcja: BUY {r['outcome']}")
        print(f"   ► Darmowa Premia: {r['premium']:.2f}% (Płatna w tym tygodniu!)")
        print(f"   ► Koniec (Date): {r['endDate']}")
        print(f"   ► Płynność: ${r['liquidity']:.0f}")
        print("-" * 60)
