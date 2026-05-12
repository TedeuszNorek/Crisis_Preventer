import requests
import json
from datetime import datetime

url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=1000"
headers = {"Accept": "application/json"}

def find_rigged_markets():
    print("Pobieranie 1000 najaktywnieszych wydarzeń z Polymarketu...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        events = response.json()
        
        anomalies = []
        for event in events:
            for m in event.get('markets', []):
                if m.get('closed', True):
                    continue
                
                vol24 = float(m.get('volume24hr', 0) or 0)
                vol_total = float(m.get('volume', 0) or 0)
                liq = float(m.get('liquidity', 0) or 0)
                price_change = abs(float(m.get('oneDayPriceChange', 0) or 0))
                
                if vol_total < 10000 or liq < 2000 or vol24 < 5000:
                    continue
                
                # Procent całego wolumenu zrobiony dzisiaj!
                vol_spike_ratio = vol24 / vol_total
                
                # Zastosujemy wzór na anomalię:
                # Duży % obrotu zrobiony OSTATNIEJ DOBY względem całości czasu życia
                # PLUS gigantyczny obrót w porównaniu do płynności (Ktoś skupuje wszystko co pływa)
                # MINUS zmiany w cenie (Ktoś dusi cenę, wkładając ogromny kapitał - manipulacja "Rigged")
                
                # Jeśli cena zmieniła się o mniej niż 2% (0.02) mimo kolosalnego obrotu
                if price_change < 0.05 and vol_spike_ratio > 0.15:
                    
                    # Wskaźnik wyciskania książki zleceń: 
                    # Np. volumen dobowy to 50 000, a płynność to 5 000. 
                    pressure_ratio = vol24 / liq if liq > 0 else 0
                    
                    if pressure_ratio > 2.0:
                        score = vol_spike_ratio * pressure_ratio * (1 - price_change)
                        anomalies.append({
                            'question': m.get('question'),
                            'vol24': vol24,
                            'total_vol': vol_total,
                            'liq': liq,
                            'price_change': price_change,
                            'score': score,
                            'vol_spike': vol_spike_ratio,
                            'bestAsk': m.get('bestAsk', "N/A"),
                            'prices': m.get('outcomePrices', "[]")
                        })
                        
        # Sortowanie po score malejąco by pokazać THE MOST RIGGED
        anomalies.sort(key=lambda x: x['score'], reverse=True)
        return anomalies
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    results = find_rigged_markets()
    print("\n🚨 TOP MOST RIGGED & MISPRICED MARKETS R.N. 🚨")
    print("Metryka: Gigantyczny wystrzał wolumenu ignorujący słabą płynność książki ze sztywną/blokowaną przez grubasa ceną.\n")
    
    for idx, r in enumerate(results[:15]):
        print(f"{idx+1}. {r['question']}")
        print(f"   ► Score Anomalii: {r['score']:.2f}")
        print(f"   ► Wolumen dzisiaj: ${r['vol24']:.0f} (to aż {r['vol_spike']*100:.1f}% CAŁEGO dotychczasowego obrotu!)")
        print(f"   ► Płynność bazy: ${r['liq']:.0f}")
        print(f"   ► Zmiana ceny (24h): {r['price_change']*100:.1f}%")
        print(f"   ► Aktualne Ceny (YES/NO): {r['prices']}")
        print("-" * 60)
