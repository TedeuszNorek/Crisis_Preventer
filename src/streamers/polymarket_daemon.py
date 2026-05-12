import time
import sqlite3
import requests
import logging
import subprocess
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PolyDaemon] %(message)s")

DB_PATH = "polymarket_anomalies.db"

def insert_global_alert(source, title, message):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS global_alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, source TEXT, title TEXT, message TEXT)")
        conn.execute("INSERT INTO global_alerts (timestamp, source, title, message) VALUES (?, ?, ?, ?)",
                     (datetime.now().isoformat(), source, title, message))
        conn.commit()
        conn.close()
    except Exception:
        pass

def push_mac_notification(title, message):
    insert_global_alert("POLYMARKET_DAEMON", title, message)
    try:
        # Escape double quotes for osascript
        safe_msg = message.replace('"', '\\"')
        safe_title = title.replace('"', '\\"')
        subprocess.run(['osascript', '-e', f'display notification "{safe_msg}" with title "{safe_title}"'])
    except Exception as e:
        logging.error(f"Mac notification failed: {e}")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS anomalies
                 (timestamp TEXT, event_slug TEXT, question TEXT, anomaly_type TEXT, 
                  details TEXT, severity REAL)''')
    
    # Store previous volume/odds to calculate spikes
    c.execute('''CREATE TABLE IF NOT EXISTS market_state
                 (market_id TEXT PRIMARY KEY, last_vol REAL, last_prob REAL, last_updated TEXT)''')
    conn.commit()
    return conn

def scan_markets(conn):
    url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=100"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        events = resp.json()
    except Exception as e:
        logging.error(f"Failed to fetch matching events: {e}")
        return

    c = conn.cursor()
    
    for event in events:
        slug = event.get('slug', 'unknown-slug')
        title = event.get('title', '')
        
        # Check volume spikes and odds imbalances
        for m in event.get('markets', []):
            if not m.get('active') or m.get('closed'):
                continue
            
            mid = m.get('id')
            prob = 0.0
            try:
                # We just take the first outcome prob (usually "Yes")
                prices = json.loads(m.get('outcomePrices', '[]'))
                if prices: prob = float(prices[0])
            except:
                pass
                
            vol = float(m.get('volume', 0))
            
            # Fetch previous state
            c.execute("SELECT last_vol, last_prob FROM market_state WHERE market_id=?", (mid,))
            row = c.fetchone()
            
            if row:
                prev_vol, prev_prob = row
                
                # Condition 1: Volume Spike > $10,000 in 30s
                vol_delta = vol - prev_vol
                if vol_delta > 10000:
                    logging.warning(f"🚨 VOLUME SPIKE: ${vol_delta:.2f} on {title}")
                    push_mac_notification("Polymarket Whale Alert 🐳", f"+${vol_delta:,.0f} volume jump on: {title}...")
                    c.execute("INSERT INTO anomalies VALUES (?, ?, ?, ?, ?, ?)",
                              (datetime.now().isoformat(), slug, title, "VOLUME_SPIKE", f"+${vol_delta}", 0.8))
                
                # Condition 2: Probability/Spread Anomaly (e.g. jumps > 5% in 30s)
                prob_delta = prob - prev_prob
                if abs(prob_delta) > 0.05:
                    dir_str = "JUMP" if prob_delta > 0 else "DUMP"
                    logging.warning(f"🚨 ODDS {dir_str}: {prob_delta*100:.1f}% on {title} (Now: {prob*100:.1f}%)")
                    push_mac_notification("🚨 Polymarket Odds Shock", f"Odds {dir_str} by {prob_delta*100:.1f}% to {prob*100:.1f}% on: {title}...")
                    c.execute("INSERT INTO anomalies VALUES (?, ?, ?, ?, ?, ?)",
                              (datetime.now().isoformat(), slug, title, "ODDS_SHOCK", f"{prob_delta*100:.1f}%", abs(prob_delta)*10))
            
            # Update state
            c.execute("REPLACE INTO market_state VALUES (?, ?, ?, ?)", 
                      (mid, vol, prob, datetime.now().isoformat()))
            
    conn.commit()

def run_daemon(interval=30):
    logging.info(f"Starting Polymarket Anomaly Daemon (Interval: {interval}s)")
    push_mac_notification("System Uzbrojony", "Demon Polymarket nasłuchuje szans arbitrażowych w tle...")
    conn = init_db()
    # Pętla non-stop co X sekund
    while True:
        try:
            scan_markets(conn)
        except Exception as e:
            logging.error(f"Skanowanie przerwane: {e}")
        time.sleep(interval)

if __name__ == "__main__":
    import json
    run_daemon()
