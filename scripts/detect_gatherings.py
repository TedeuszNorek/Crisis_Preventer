import asyncio
import os
import logging
import sys
import numpy as np
from datetime import datetime, timedelta
from typing import List, Tuple
from dotenv import load_dotenv

# Ensure we can import signalvortex
sys.path.append(os.getcwd())

from signalvortex.sources.aisstream import AISStreamClient
try:
    from sklearn.cluster import DBSCAN
except ImportError:
    print("scikit-learn is required. Please run: pip install scikit-learn numpy")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def collect_data(duration_seconds: int) -> List[Tuple[float, float, str]]:
    load_dotenv()
    # Try multiple paths for .env if needed, similar to test script
    if not os.getenv("AISSTREAM_API_KEY"):
         load_dotenv("signalvortex/env")

    api_key = os.getenv("AISSTREAM_API_KEY")
    if not api_key:
        logger.error("No API Key found.")
        return []

    client = AISStreamClient(api_key=api_key)
    
    # Global bounding box (whole world) to find all gatherings
    # However, for the free key or to avoid huge data, maybe we limit? 
    # The user asked for "unnatural gatherings", likely implies globally or a large region.
    # The API might disconnect if we can't process fast enough (300/s). 
    # Let's try a very large box covering Europe/Atlantic or just global if safe.
    # Docs say: "process on average 300 messages a second (if subscribed to the entire world)"
    # A simple python script might lag. Let's pick a large but interesting region: Europe + Atlantic
    # Lat: 30 to 70, Lon: -40 to 40
    bounding_boxes = [[
        [30.0, -40.0], 
        [70.0, 40.0]
    ]]
    
    data_points = []
    
    logger.info(f"Collecting AIS data for {duration_seconds} seconds...")
    start_time = datetime.now()
    
    try:
        async for message in client.connect_and_listen(bounding_boxes):
            if datetime.now() - start_time > timedelta(seconds=duration_seconds):
                break
                
            if message.MessageType == "PositionReport":
                try:
                    lat = message.Message['PositionReport']['Latitude']
                    lon = message.Message['PositionReport']['Longitude']
                    mmsi = str(message.Message['PositionReport']['UserID'])
                    data_points.append((lat, lon, mmsi))
                except KeyError:
                    pass
            
            # Print status every 100 messages
            if len(data_points) % 100 == 0 and len(data_points) > 0:
                print(f"Collected {len(data_points)} positions...", end='\r')
                
    except Exception as e:
        logger.error(f"Collection stream ended or failed: {e}")

    print(f"\nCollection complete. Total points: {len(data_points)}")
    return data_points

def analyze_clusters(data: List[Tuple[float, float, str]]):
    if not data:
        print("No data to analyze.")
        return

    coords = np.array([(d[0], d[1]) for d in data])
    
    # DBSCAN parameters:
    # eps: The maximum distance between two samples for one to be considered as in the neighborhood of the other.
    # 0.1 degrees is roughly 11km. 0.05 is ~5.5km.
    # min_samples: The number of samples (or total weight) in a neighborhood for a point to be considered as a core point.
    # Let's say a "gathering" is at least 5 ships within ~5km.
    eps = 0.05
    min_samples = 5
    
    logger.info(f"Clustering with eps={eps} (approx 5km), min_samples={min_samples}...")
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(coords)
    
    labels = db.labels_
    
    # Number of clusters in labels, ignoring noise if present.
    n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise_ = list(labels).count(-1)

    print("-" * 40)
    print(f"Estimated number of clusters: {n_clusters_}")
    print(f"Noise points: {n_noise_}")
    print("-" * 40)

    unique_labels = set(labels)
    clusters = []
    
    for k in unique_labels:
        if k == -1:
            continue
            
        class_member_mask = (labels == k)
        xy = coords[class_member_mask]
        
        center_lat = np.mean(xy[:, 0])
        center_lon = np.mean(xy[:, 1])
        count = len(xy)
        
        clusters.append({
            'id': k,
            'center': (center_lat, center_lon),
            'count': count
        })
    
    # Sort by count descending
    clusters.sort(key=lambda x: x['count'], reverse=True)
    
    print(f"{'Cluster ID':<12} {'Center (Lat, Lon)':<25} {'Ship Count':<10}")
    print("-" * 50)
    for c in clusters:
        print(f"{c['id']:<12} {c['center'][0]:.4f}, {c['center'][1]:.4f}       {c['count']:<10}")
        
    print("-" * 50)
    print("Check these coordinates on a map to see if they correspond to ports or open ocean.")

if __name__ == "__main__":
    # Run for 60 seconds
    data = asyncio.run(collect_data(60))
    analyze_clusters(data)
