import asyncio
import json
import logging
import websockets
from typing import AsyncGenerator, List, Optional
from .models import SubscriptionMessage, AISMessage

logger = logging.getLogger(__name__)

class AISStreamClient:
    URL = "wss://stream.aisstream.io/v0/stream"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.ship_cache: Dict[str, Dict[str, Any]] = {}

    async def connect_and_listen(
        self,
        bounding_boxes: List[List[List[float]]],
        ship_mmsi_filter: Optional[List[str]] = None,
        message_types_filter: Optional[List[str]] = None
    ) -> AsyncGenerator[AISMessage, None]:
        """
        Connects to AISStream, sends subscription, and yields messages.
        """
        sub_msg = SubscriptionMessage(
            APIKey=self.api_key,
            BoundingBoxes=bounding_boxes,
            FiltersShipMMSI=ship_mmsi_filter,
            FilterMessageTypes=message_types_filter
        )

        async for websocket in websockets.connect(self.URL):
            try:
                await websocket.send(sub_msg.to_json())
                logger.info("Subscribed to AISStream")
                
                async for message_str in websocket:
                    try:
                        data = json.loads(message_str)
                        ais_msg = AISMessage(**data)
                        
                        # Cache static data logic
                        if ais_msg.MessageType == "ShipStaticData":
                            content = ais_msg.Message.get("ShipStaticData", {})
                            mmsi = str(content.get("UserID"))
                            if mmsi:
                                self.ship_cache[mmsi] = content
                        
                        yield ais_msg
                    except json.JSONDecodeError:
                        logger.error("Failed to decode JSON message")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
            except websockets.ConnectionClosed:
                logger.warning("Connection closed, reconnecting...")
                continue
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                # Optional: Add backoff here
                await asyncio.sleep(5) 
