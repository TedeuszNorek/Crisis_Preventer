"""AIS maritime stream client using aisstream.io WebSocket API.

Tracks ship movements globally. Agent activates regional bounding boxes
when geopolitical or commodity signals suggest disruption.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import websockets

from src.core.event_bus import bus
from src.core.models import Domain, RawEvent, Signal, Severity

logger = logging.getLogger(__name__)

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"

# Predefined monitoring zones — agent picks relevant ones
ZONES: Dict[str, List[List[List[float]]]] = {
    "suez":          [[[29.0, 31.5], [32.5, 32.5]]],   # Suez Canal
    "hormuz":        [[[25.5, 56.0], [27.0, 57.5]]],   # Strait of Hormuz
    "malacca":       [[[-1.5, 103.0], [6.0, 104.5]]],  # Strait of Malacca
    "bab_el_mandeb": [[[11.5, 43.0], [13.0, 44.5]]],  # Bab-el-Mandeb
    "black_sea":     [[[41.0, 28.0], [46.5, 37.5]]],   # Black Sea
    "baltic":        [[[54.0, 10.0], [65.0, 30.0]]],   # Baltic Sea
    "taiwan_strait": [[[22.0, 118.5], [26.0, 122.0]]], # Taiwan Strait
    "global":        [[[-90.0, -180.0], [90.0, 180.0]]],
}

# Ship type codes that are strategically interesting
STRATEGIC_SHIP_TYPES = {
    70: "Cargo", 71: "Cargo", 72: "Cargo", 73: "Cargo",
    80: "Tanker", 81: "Tanker", 82: "Tanker", 83: "Tanker", 84: "Tanker",
    89: "Tanker",
    35: "Military",
    55: "Law Enforcement",
}


@dataclass
class ShipEvent:
    mmsi: str
    name: str
    ship_type: int
    lat: float
    lon: float
    speed: float
    course: float
    zone: str
    ts: float


class AISMonitor:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._active_zones: List[str] = ["suez", "hormuz", "malacca", "bab_el_mandeb"]
        self._ship_cache: Dict[str, dict] = {}
        self._speed_history: Dict[str, List[float]] = {}

    def activate_zone(self, zone: str) -> None:
        if zone not in self._active_zones and zone in ZONES:
            self._active_zones.append(zone)
            logger.info(f"[AIS] Zone activated: {zone}")

    def deactivate_zone(self, zone: str) -> None:
        if zone in self._active_zones:
            self._active_zones.remove(zone)
            logger.info(f"[AIS] Zone deactivated: {zone}")

    def _get_bounding_boxes(self) -> List[List[List[float]]]:
        boxes = []
        for zone in self._active_zones:
            boxes.extend(ZONES.get(zone, []))
        return boxes or ZONES["global"]

    def _detect_anomaly(self, mmsi: str, speed: float, ship_type: int) -> Optional[str]:
        history = self._speed_history.setdefault(mmsi, [])
        history.append(speed)
        if len(history) > 10:
            history.pop(0)

        if len(history) >= 3:
            avg = sum(history[:-1]) / (len(history) - 1)
            # Stopped or very slow when normally moving
            if avg > 4.0 and speed < 0.5:
                return "vessel_stopped"
            # Sudden speed anomaly (e.g. evasive maneuver)
            if avg > 0.5 and speed > avg * 3:
                return "speed_spike"

        # Tanker in a conflict zone
        if ship_type in STRATEGIC_SHIP_TYPES and STRATEGIC_SHIP_TYPES[ship_type] == "Tanker":
            if any(z in ("hormuz", "bab_el_mandeb", "black_sea") for z in self._active_zones):
                return "strategic_tanker"

        return None

    async def _process_message(self, data: dict, zone: str) -> None:
        msg_type = data.get("MessageType", "")
        msg = data.get("Message", {})

        if msg_type == "ShipStaticData":
            content = msg.get("ShipStaticData", {})
            mmsi = str(content.get("UserID", ""))
            if mmsi:
                self._ship_cache[mmsi] = content
            return

        if msg_type not in ("PositionReport", "ExtendedClassBPositionReport"):
            return

        pos = msg.get("PositionReport") or msg.get("ExtendedClassBPositionReport", {})
        mmsi = str(pos.get("UserID", ""))
        lat = pos.get("Latitude", 0.0)
        lon = pos.get("Longitude", 0.0)
        speed = pos.get("Sog", 0.0)        # Speed over ground (knots)
        course = pos.get("Cog", 0.0)

        static = self._ship_cache.get(mmsi, {})
        ship_type = static.get("Type", 0)
        name = static.get("Name", mmsi)

        anomaly = self._detect_anomaly(mmsi, speed, ship_type)

        raw = RawEvent(
            source="ais",
            domain=Domain.MARITIME,
            entity_id=mmsi,
            payload={
                "mmsi": mmsi, "name": name, "type": ship_type,
                "lat": lat, "lon": lon, "speed": speed, "course": course,
                "zone": zone, "anomaly": anomaly,
            },
            tags=[zone, STRATEGIC_SHIP_TYPES.get(ship_type, "unknown")],
        )
        await bus.publish_raw(raw)

        if anomaly:
            severity = Severity.HIGH if anomaly == "vessel_stopped" else Severity.MEDIUM
            signal = Signal(
                signal_id=f"ais_{mmsi}_{int(time.time())}",
                source="ais",
                domain=Domain.MARITIME,
                title=f"[AIS] {anomaly.upper()} — {name} in {zone.upper()}",
                severity=severity,
                value=speed,
                context={
                    "mmsi": mmsi, "name": name, "zone": zone,
                    "speed": speed, "lat": lat, "lon": lon,
                    "ship_type": STRATEGIC_SHIP_TYPES.get(ship_type, "unknown"),
                    "anomaly": anomaly,
                },
            )
            await bus.publish_signal(signal)

    async def run(self) -> None:
        logger.info(f"[AIS] Connecting — zones: {self._active_zones}")
        while True:
            try:
                bboxes = self._get_bounding_boxes()
                sub = json.dumps({
                    "APIKey": self.api_key,
                    "BoundingBoxes": bboxes,
                    "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
                })
                async with websockets.connect(AISSTREAM_URL, ping_interval=20) as ws:
                    await ws.send(sub)
                    logger.info("[AIS] Subscribed")
                    async for message in ws:
                        data = json.loads(message)
                        zone = self._active_zones[0] if self._active_zones else "global"
                        await self._process_message(data, zone)
            except Exception as exc:
                logger.error(f"[AIS] Connection error: {exc} — retry in 15s")
                await asyncio.sleep(15)


def make_ais_monitor() -> Optional[AISMonitor]:
    key = os.getenv("AISSTREAM_API_KEY")
    if not key:
        logger.warning("[AIS] AISSTREAM_API_KEY not set — AIS disabled")
        return None
    return AISMonitor(key)
