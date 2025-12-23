import asyncio
import os
import logging
from dotenv import load_dotenv
from signalvortex.sources.aisstream import AISStreamClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Try loading from multiple potential locations
    potential_paths = [
        ".env",
        "signalvortex/env", 
        "signalvortex/.env",
        "../.env"
    ]
    
    env_loaded = False
    for path in potential_paths:
        if os.path.exists(path):
            logger.info(f"Loading env from: {path}")
            load_dotenv(dotenv_path=path)
            env_loaded = True
            
    if not env_loaded:
        logger.warning("No .env file found in common locations. Relying on system environment variables.")

    api_key = os.getenv("AISSTREAM_API_KEY")
    
    if not api_key:
        logger.error("AISSTREAM_API_KEY not found in environment variables.")
        logger.info(f"Current Keys: {[k for k in os.environ.keys() if 'AIS' in k]}")
        return

    client = AISStreamClient(api_key=api_key)

    # Example bounding box (approx. Rotterdam port area for high traffic probability)
    # Latitude: 51.90 - 52.00, Longitude: 4.00 - 4.50
    # Format: [[lat1, lon1], [lat2, lon2]]
    # AISStream expects: [[[lat1, lon1], [lat2, lon2]]]
    # Actually checking docs again: 
    # [[[lat min, lon min], [lat max, lon max]]] might be safer or just 2 corners.
    # Docs example: [[[25.835302, -80.207729], [25.602700, -79.879297]]]
    
    bounding_boxes = [[
        [51.0, 3.0], 
        [53.0, 5.0]
    ]]

    try:
        logger.info("Connecting to AISStream...")
        async for message in client.connect_and_listen(bounding_boxes):
            print(f"SUCCESS: Received message type: {message.MessageType}")
            print(f"SUCCESS: Metadata: {message.MetaData}")
            logger.info(f"Received message type: {message.MessageType}")
            logger.info(f"Metadata: {message.MetaData}")
            # Just print one and exit for test
            break
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"FAILURE: {e}")

if __name__ == "__main__":
    asyncio.run(main())
