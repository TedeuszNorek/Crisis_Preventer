import requests
import time
import random

API_URL = "http://localhost:8000"

def send_event(event):
    resp = requests.post(f"{API_URL}/ingest", json=event)
    return resp.json()

def main():
    print("Testing SignalVortex API...")
    
    # Wait for API to be up
    for _ in range(5):
        try:
            requests.get(f"{API_URL}/health")
            print("API is up!")
            break
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    else:
        print("API did not start in time. Exiting.")
        return

    # Scenario: Funding Rate Spike
    # Enter threshold: 0.002, Duration: 300s
    print("\n--- Scenario: Funding Rate Spike ---")
    base_ts = time.time()
    
    # Event 1: Exceed threshold, but for_duration not met
    print("1. Sending event exceeding threshold (0.003), but no alert yet (needs 300s)")
    resp1 = send_event({
        "ts_event": base_ts,
        "source": "binance",
        "entity_type": "instrument",
        "entity_id": "BTCUSDT_PERP",
        "features": {"funding_rate": 0.003, "price": 60000},
        "dq": {"timeliness_s": 2, "completeness": 1.0, "consistency": 1.0}
    })
    print(f"Active Alerts Count: {len(resp1['active_alerts'])}")
    
    # Event 2: Exceed threshold 301 seconds later -> Triggers Alert OPEN
    print("\n2. Sending event exceeding threshold 301s later (duration met) -> SHOULD ALERT")
    resp2 = send_event({
               "ts_event": base_ts + 301,
        "source": "binance",
        "entity_type": "instrument",
        "entity_id": "BTCUSDT_PERP",
        "features": {"funding_rate": 0.004, "price": 60500},
        "dq": {"timeliness_s": 2, "completeness": 1.0, "consistency": 1.0}
    })
    
    print(f"Active Alerts Count: {len(resp2['active_alerts'])}")
    if resp2['active_alerts']:
        print(f"Alert details: {resp2['active_alerts'][0]}")
        
    # Event 3: Data Quality Issue
    print("\n--- Scenario: Data Quality Failure ---")
    resp3 = send_event({
        "ts_event": base_ts + 400,
        "source": "binance",
        "entity_type": "instrument",
        "entity_id": "ETHUSDT_PERP",
        "features": {"funding_rate": 0.001, "price": 3000},
        "dq": {"timeliness_s": 9999, "completeness": 0.5, "consistency": 0.5} # bad DQ
    })
    print("Sent event with terrible DQ.")
    # Fetch alerts directly to find the DATA_ISSUE alert
    alerts = requests.get(f"{API_URL}/alerts").json()
    data_issues = [a for a in alerts if a['data_issue'] == 1]
    print(f"Found DATA_ISSUE alerts: {len(data_issues)}")
    if data_issues:
        print(f"Data Issue Details: {data_issues[0]}")
        
    print("\nCompleted tests.")

if __name__ == "__main__":
    main()
