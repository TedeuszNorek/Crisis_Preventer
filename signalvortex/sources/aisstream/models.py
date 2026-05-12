from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any, Dict
import json

@dataclass
class SubscriptionMessage:
    APIKey: str
    BoundingBoxes: List[List[List[float]]]
    FiltersShipMMSI: Optional[List[str]] = None
    FilterMessageTypes: Optional[List[str]] = None

    def to_json(self) -> str:
        data = asdict(self)
        if self.FiltersShipMMSI is None:
            del data["FiltersShipMMSI"]
        if self.FilterMessageTypes is None:
            del data["FilterMessageTypes"]
        return json.dumps(data)

@dataclass
class AISMessage:
    MessageType: str
    MetaData: Dict[str, Any]
    Message: Dict[str, Any]
