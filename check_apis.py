import os
import requests
from dotenv import load_dotenv

load_dotenv()

def check_deribit():
    url = "https://www.deribit.com/api/v2/public/get_time"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            print("✅ Deribit (Public): Connection OK")
        else:
            print(f"❌ Deribit (Public): Failed with status {resp.status_code}")
    except Exception as e:
        print(f"❌ Deribit (Public): Request failed - {e}")

def check_fred():
    key = os.getenv("FRED_API_KEY")
    url = f"https://api.stlouisfed.org/fred/series?series_id=GNPCA&api_key={key}&file_type=json"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            print("✅ FRED: Connection OK")
        else:
            print(f"❌ FRED: Failed with status {resp.status_code} - {resp.text[:50]}")
    except Exception as e:
        print(f"❌ FRED: Request failed - {e}")

def check_dome():
    key = os.getenv("DOME_API_KEY")
    url = "https://api.domeapi.io/v1/polymarket/orders?limit=1&market_slug=us-government-shutdown-by-october-1"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            print("✅ DomeAPI (Polymarket): Connection OK")
        else:
            print(f"❌ DomeAPI: Failed with status {resp.status_code} - {resp.text[:50]}")
    except Exception as e:
        print(f"❌ DomeAPI: Request failed - {e}")

def check_massive():
    key = os.getenv("MASSIVE_ACCESS_KEY_ID")
    url = "https://api.polygon.io/v3/snapshot/options/SPY"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            print("✅ Massive/Polygon: Connection OK")
        else:
            print(f"❌ Massive/Polygon: Failed with status {resp.status_code} - {resp.text[:50]}")
    except Exception as e:
        print(f"❌ Massive/Polygon: Request failed - {e}")

def check_binance():
    key = os.getenv("BINANCE_API_KEY")
    url = "https://api.binance.com/api/v3/ping"
    headers = {"X-MBX-APIKEY": key}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            print("✅ Binance: Connection OK")
        else:
            print(f"❌ Binance: Failed with status {resp.status_code} - {resp.text[:50]}")
    except Exception as e:
         print(f"❌ Binance: Request failed - {e}")

def check_sentinel():
    # Attempt OAuth for Sentinel Hub
    uid = os.getenv("SENTINEL_USER_ID")
    pwd = os.getenv("SENTINEL_SECRET")
    url = "https://services.sentinel-hub.com/oauth/token"
    # we just check token generation
    data = {"grant_type": "client_credentials"}
    try:
        resp = requests.post(url, auth=(uid, pwd), data=data, timeout=5)
        if resp.status_code == 200:
            print("✅ Sentinel Satellite: Connection OK")
        else:
            print(f"❌ Sentinel: Failed with status {resp.status_code} - {resp.text[:50]}")
    except Exception as e:
         print(f"❌ Sentinel: Request failed - {e}")


if __name__ == "__main__":
    print("--- Checking API Connections ---")
    check_deribit()
    check_fred()
    check_dome()
    check_massive()
    check_binance()
    check_sentinel()
    print("--------------------------------")
