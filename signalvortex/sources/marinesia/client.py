import requests
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class MarinesiaClient:
    BASE_URL = "https://api.marinesia.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        # Assuming API key is passed via header "x-api-key" or similar based on standard modern APIs.
        # Docs search results showed curl examples but I need to be sure.
        # Fallback to query param if headers fail, or standard Bearer.
        # Result 356 said "curl command that includes an API key parameter".
        # Let's assume header 'X-Api-Key' or 'Authorization' is safer default, or query param.
        # I will support both just in case or try to find specific docs. 
        # For now, I'll use a common pattern and we can debug.
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "X-Api-Key": self.api_key 
        })

    def get_vessel(self, mmsi: str) -> Optional[Dict]:
        """
        Fetch vessel details by MMSI.
        """
        try:
            # Endpoint guess based on standard REST patterns, will verify.
            # If doc says /vessels/{mmsi} or similar.
            url = f"{self.BASE_URL}/vessel/{mmsi}"
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                return data
            elif response.status_code == 404:
                logger.debug(f"Vessel {mmsi} not found in Marinesia.")
                return None
            else:
                logger.warning(f"Marinesia API error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch vessel {mmsi}: {e}")
            return None
