import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data.harvester import SVDataHarvester
from src.data.data_models import DataModels

# Mock data
mock_events = [
    {
        "id": "mock_event_1",
        "umaResolutionStatuses": ["PROPOSED"],
        "endDate": "2026-05-11T00:00:00Z",
        "markets": [
            {
                "id": "mock_market_1",
                "closed": False,
                "active": True,
                "volume24hr": 6000,
                "volume": 20000,
                "liquidity": 6000,
                "oneDayPriceChange": 0.01,
                "outcomePrices": "[\"0.96\", \"0.04\"]"
            }
        ]
    },
    {
        "id": "mock_event_2",
        "umaResolutionStatuses": [],
        "endDate": "2026-06-11T00:00:00Z",
        "markets": [
            {
                "id": "mock_market_2",
                "closed": False,
                "active": True,
                "volume24hr": 8000,
                "volume": 12000,
                "liquidity": 3000,
                "oneDayPriceChange": 0.02,
                "outcomePrices": "[\"0.50\", \"0.50\"]"
            }
        ]
    }
]

def test_harvester():
    # Upewnijmy się że nie łączymy się z zewnętrznym api
    h = SVDataHarvester()
    # Nadpiszmy metodę tak, żeby zwracała testowe dane
    h.fetch_markets = lambda: mock_events
    
    # Process
    h.process_and_store(mock_events)
    
    # Verify DB
    db = DataModels()
    conn = db._get_connection()
    
    # Check snapshots
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM market_snapshots")
    snapshots = cursor.fetchall()
    print(f"Snapshots found: {len(snapshots)}")
    
    # Check anomalies
    cursor.execute("SELECT * FROM anomaly_events")
    anomalies = cursor.fetchall()
    print(f"Anomalies found: {len(anomalies)}")
    
    for a in anomalies:
        print(f"Anomaly Event ID: {a['event_id']}, Type: {a['type']}, Proof: {a['proof']}")

if __name__ == "__main__":
    test_harvester()
