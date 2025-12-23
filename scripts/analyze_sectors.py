import asyncio
import os
import logging
import sys
import numpy as np
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
from dotenv import load_dotenv

sys.path.append(os.getcwd())
from signalvortex.sources.aisstream import AISStreamClient
from signalvortex.sources.marinesia import MarinesiaClient

try:
    from sklearn.cluster import DBSCAN
except ImportError:
    print("scikit-learn is required.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ship Type mapping (Simplified)
# https://gpsd.gitlab.io/gpsd/AIVDM.html#_type_5_static_and_voyage_related_data
SHIP_TYPE_MAP = {
    30: "Fishing",
    35: "Military",
    50: "Pilot",
    51: "SAR",
    52: "Tug",
    60: "Passenger", 61: "Passenger", 62: "Passenger", 63: "Passenger", 64: "Passenger",
    70: "Cargo", 71: "Cargo", 72: "Cargo", 73: "Cargo", 74: "Cargo",
    79: "Cargo",
    80: "Tanker", 81: "Tanker", 82: "Tanker", 83: "Tanker", 84: "Tanker",
    89: "Tanker",
    90: "Other",
}

def get_ship_sector(type_code: int) -> str:
    # Handle ranges
    if 30 <= type_code <= 33: return "Fishing"
    if 70 <= type_code <= 79: return "Cargo"
    if 80 <= type_code <= 89: return "Tanker"
    if 60 <= type_code <= 69: return "Passenger"
    if 36 <= type_code <= 39: return "Pleasure"
    return SHIP_TYPE_MAP.get(type_code, "Unknown")

PORTS = {
    "Rotterdam": (51.95, 4.0),
    "Amsterdam": (52.4, 4.6),
    "Hamburg": (53.55, 9.8),
    "Antwerp": (51.27, 4.3),
    "Singapore": (1.28, 103.85),
    "LA/Long Beach": (33.74, -118.28),
    "New York/NJ": (40.66, -74.05),
}

BOTTLENECKS = {
    "Strait of Hormuz": (26.5667, 56.2500),
    "Strait of Malacca": (1.4300, 102.8900),
    "Suez Canal": (29.9300, 32.5500),
    "Panama Canal": (9.0800, -79.6800),
    "Bab al-Mandab": (12.5833, 43.3333),
    "Bosphorus": (41.0000, 29.0000),
}

async def collect_sector_data(duration_seconds: int = 120):
    load_dotenv("signalvortex/env")
    ais_key = os.getenv("AISSTREAM_API_KEY")
    marinesia_key = os.getenv("MARINESIA_API_KEY")
    
    if not ais_key:
        logger.error("No AISStream API Key found.")
        return

    client = AISStreamClient(api_key=ais_key)
    marinesia = MarinesiaClient(api_key=marinesia_key) if marinesia_key else None
    
    # Europe + Atlantic box (expanded cover preferred for bottlenecks, but keeping this for now)
    # Ideally should process global stream or multiple boxes.
    # For bottlenecks like Malacca/Panama, this box [-40, 40] is probably too small or wrong region.
    # Expanding box to cover most of Northern Hemisphere trade routes.
    # Map: Logic: 30N-70N covers Europe. Hormuz is ~26N. Panama is ~9N. Singapore ~1N.
    # We need a bigger box or multiple subscriptions.
    # Let's try a very wide global band: -10 to 75 Lat, -180 to 180 Lon. 
    bounding_boxes = [[[-10.0, -170.0], [75.0, 170.0]]]
    
    # Include ShipStaticData
    filters = ["PositionReport", "ShipStaticData"]
    
    data_points = [] # (lat, lon, mmsi, speed)
    ship_static_info = {} # mmsi -> type_code
    
    logger.info(f"Collecting data (Global Band) for {duration_seconds}s...")
    start_time = datetime.now()
    
    try:
        async for message in client.connect_and_listen(bounding_boxes, message_types_filter=filters):
            if datetime.now() - start_time > timedelta(seconds=duration_seconds):
                break

            if message.MessageType == "ShipStaticData":
                try:
                    content = message.Message['ShipStaticData']
                    mmsi = str(content['UserID'])
                    ship_type = content.get('Type', 0)
                    ship_static_info[mmsi] = ship_type
                except KeyError:
                    pass

            elif message.MessageType == "PositionReport":
                try:
                    content = message.Message['PositionReport']
                    lat = content['Latitude']
                    lon = content['Longitude']
                    mmsi = str(content['UserID'])
                    speed = content.get('Sog', 0) # Speed over ground
                    data_points.append({'lat': lat, 'lon': lon, 'mmsi': mmsi, 'speed': speed})
                except KeyError:
                    pass
            
            if len(data_points) % 500 == 0:
                print(f"Points: {len(data_points)} | Known Ships: {len(ship_static_info)}", end='\r')

    except Exception as e:
        logger.error(f"Stream error: {e}")

    print(f"\nCollected {len(data_points)} positions. Cache size: {len(ship_static_info)}")
    
    # Enrichment Phase (Optional)
    if marinesia:
        unknown_mmsis = {d['mmsi'] for d in data_points if ship_static_info.get(d['mmsi'], 0) == 0}
        logger.info(f"Enriching data... Found {len(unknown_mmsis)} unknown ships.")
        to_lookup = list(unknown_mmsis)[:20] 
        success_count = 0
        for mmsi in to_lookup:
            details = marinesia.get_vessel(mmsi)
            if details:
                t = details.get('vessel_type_code', 0)
                if t:
                    ship_static_info[mmsi] = t
                    success_count += 1
            await asyncio.sleep(0.2)
        logger.info(f"Enriched {success_count} ships via Marinesia.")
    
    # Analysis
    analyze_sectors_and_congestion(data_points, ship_static_info)

def analyze_sectors_and_congestion(data_points, ship_info):
    if not data_points:
        return

    # Prepare for Clustering
    coords = np.array([(d['lat'], d['lon']) for d in data_points])
    # Epsilon 5km approx (0.05 degrees roughly)
    eps = 0.05 
    min_samples = 5
    
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(coords)
    labels = db.labels_
    
    clusters = {}
    
    unique_labels = set(labels)
    for k in unique_labels:
        if k == -1: continue
        
        mask = (labels == k)
        cluster_points = [data_points[i] for i in range(len(data_points)) if mask[i]]
        
        # Calculate center
        lats = [p['lat'] for p in cluster_points]
        lons = [p['lon'] for p in cluster_points]
        center = (np.mean(lats), np.mean(lons))
        
        # Sector breakdown
        sectors = {"Cargo": 0, "Tanker": 0, "Fishing": 0, "Passenger": 0, "Other": 0, "Unknown": 0}
        speeds = []
        
        for p in cluster_points:
            mmsi = p['mmsi']
            type_code = ship_info.get(mmsi, 0)
            sector = get_ship_sector(type_code)
            if sector not in sectors: sector = "Other"
            sectors[sector] += 1
            speeds.append(p['speed'])
            
        # Congestion: Avg speed
        avg_speed = np.mean(speeds)
        is_congested = avg_speed < 1.0 # Waiting / Anchored
        
        clusters[k] = {
            'center': center,
            'count': len(cluster_points),
            'sectors': sectors,
            'avg_speed': avg_speed,
            'is_cong_candidate': is_congested
        }
        
    # Sort by count
    sorted_ids = sorted(clusters.keys(), key=lambda k: clusters[k]['count'], reverse=True)
    
    print("\n=== Cluster Sector Analysis ===")
    print(f"{'Rank':<5} {'Lat, Lon':<20} {'Count':<6} {'Primary Sector':<15} {'Avg Spd':<8} {'Detail'}")
    print("-" * 80)
    
    for i, cid in enumerate(sorted_ids[:30]): # Top 30
        c = clusters[cid]
        # Find dominant sector
        dom_sector = max(c['sectors'], key=c['sectors'].get)
        dom_pct = (c['sectors'][dom_sector] / c['count']) * 100
        
        detail = f"{dom_sector} ({dom_pct:.0f}%)"
        if c['sectors']['Tanker'] > 5 and c['sectors']['Cargo'] > 5:
            detail += " [Mixed]"
        if c['is_cong_candidate']:
            detail += " [Stationary]"
            
        print(f"{i+1:<5} {c['center'][0]:.3f}, {c['center'][1]:.3f}   {c['count']:<6} {dom_sector:<15} {c['avg_speed']:.1f} kn    {detail}")

    print("\n=== Port Congestion Estimator (Delta) ===")
    
    def check_zone(name, lat, lon, radius=0.5):
        # Find nearest cluster
        nearest = None
        min_dist = 999
        
        for cid, c in clusters.items():
            dist = np.sqrt((c['center'][0]-lat)**2 + (c['center'][1]-lon)**2)
            if dist < min_dist:
                min_dist = dist
                nearest = c
        
        if nearest and min_dist < radius:
            return nearest
        return None

    for name, (plat, plon) in PORTS.items():
        cluster = check_zone(name, plat, plon)
        if cluster:
            status = "! Congested" if cluster['is_cong_candidate'] else "OK Flowing"
            print(f"{name:<15}: {status:<12} | Ships: {cluster['count']:<4} | Avg Spd: {cluster['avg_speed']:.1f} kn | Comp: {cluster['sectors']}")
        else:
            print(f"{name:<15}: - No Major Activity Detected")

    print("\n=== Global Bottleneck Monitor ===")
    for name, (blat, blon) in BOTTLENECKS.items():
        # Radius 1.0 degree approx 100km for wider choke points
        cluster = check_zone(name, blat, blon, radius=1.0)
        
        if cluster:
            activity = "High" if cluster['count'] > 50 else "Moderate"
            print(f"{name:<20}: Traffic: {activity:<8} | Ships: {cluster['count']:<4} | Avg Spd: {cluster['avg_speed']:.1f} kn")
            # Highlight interesting ship types for bottlenecks (e.g. Tankers in Hormuz)
            if name == "Strait of Hormuz" or name == "Bab al-Mandab":
                print(f"    -> Tankers: {cluster['sectors']['Tanker']} | Cargo: {cluster['sectors']['Cargo']}")
        else:
            print(f"{name:<20}: Low/No Data (Check Coverage)")

if __name__ == "__main__":
    duration = 120
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print("Invalid duration argument. Using default 120s.")
    
    asyncio.run(collect_sector_data(duration))
