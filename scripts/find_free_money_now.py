import requests
import json
from datetime import datetime, timezone

url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=1000"
headers = {"Accept": "application/json"}

def find_free_money():
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        events = response.json()
        
        today = datetime.now(timezone.utc).date()
        anomalies = []
        
        for event in events:
            # Check for UMA resolutions
            uma_status = str(event.get('umaResolutionStatuses', '[]')).lower()
            is_proposed = 'proposed' in uma_status
            
            end_date_str = event.get('endDate')
            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).date() if end_date_str else None
            except:
                end_date = None
                
            is_expired = end_date and end_date < today
            
            # If nothing blatantly dead, we skip unless it's just pure high probability
            for m in event.get('markets', []):
                if m.get('closed', True) or not m.get('active', False):
                    continue
                    
                liq = float(m.get('liquidity', 0) or 0)
                if liq < 5000:
                    continue
                    
                prices_str = m.get('outcomePrices', "[]")
                outcomes_str = m.get('outcomes', "[]")
                
                try:
                    prices = json.loads(prices_str)
                    outcomes = json.loads(outcomes_str)
                except:
                    continue
                    
                for i, p_str in enumerate(prices):
                    try:
                        price = float(p_str)
                    except:
                        continue
                        
                    # Szukamy pewniaków > 92% i < 99.5% by było z czego wycisnąć marżę
                    if 0.92 <= price <= 0.995:
                        outcome_to_buy = outcomes[i] if len(outcomes) > i else "YES"
                        free_premium = ((1.0 / price) - 1.0) * 100
                        
                        # Add reasons for this being "free money"
                        reasons = []
                        if is_proposed:
                            reasons.append("Wstępnie zatwierdzone przez UMA (PROPOSED)!")
                        if is_expired:
                            reasons.append(f"Wydarzenie już wygasło w dacie kalendarzowej ({end_date_str})")
                        if not reasons:
                            # Not technically "dead" unless we know it's logically resolved but let's keep the best pure premiums
                            reasons.append("Ekstremalnie wysoka pewność przy wciąż otwartym rynku.")
                            
                        # Boost score based on conditions
                        anomalies.append({
                            'question': m.get('question'),
                            'outcome': outcome_to_buy,
                            'price': price,
                            'premium': free_premium,
                            'liquidity': liq,
                            'reasons': " | ".join(reasons)
                        })
                            
        # Sort by premium potential
        anomalies.sort(key=lambda x: x['premium'], reverse=True)
        return anomalies
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    print("💵 SZUKANIE KASY LEŻĄCEJ NA ZIEMI (Wolne Premie & Martwe Rynki) 💵")
    results = find_free_money()
    
    if not results:
        print("Nie ma nic na asfalcie w tym momencie.")
    
    added_questions = set()
    counter = 0
    
    for r in results:
        if r['question'] in added_questions:
            continue
        added_questions.add(r['question'])
        counter += 1
        
        print(f"{counter}. [{r['price']:.3f} $] {r['question']}")
        print(f"   ► Akcja: BUY {r['outcome']}")
        print(f"   ► Darmowa Premia: {r['premium']:.2f}% (Tyle leży na ziemi!)")
        print(f"   ► Płynność bazy: ${r['liquidity']:.0f}")
        print(f"   ► DLACZEGO TO PEWNIAK: {r['reasons']}")
        print("-" * 60)
        
        if counter >= 10:
            break
