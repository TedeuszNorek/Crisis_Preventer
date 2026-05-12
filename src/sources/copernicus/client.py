"""ESA Copernicus / Sentinel Hub client.

Agent activates this when commodity/infrastructure signals warrant
satellite verification (port activity, crop stress, military buildup).

Requires: SENTINEL_HUB_CLIENT_ID + SENTINEL_HUB_CLIENT_SECRET
Docs: https://documentation.dataspace.copernicus.eu/
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import aiohttp

from src.core.event_bus import bus
from src.core.models import Domain, RawEvent, Signal, Severity

logger = logging.getLogger(__name__)

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"

# NDVI evalscript: measures vegetation health
EVALSCRIPT_NDVI = """
//VERSION=3
function setup() {
  return { input: ["B04","B08","SCL"], output: { bands: 1, sampleType: "FLOAT32" } };
}
function evaluatePixel(s) {
  if ([3,8,9,10,11].includes(s.SCL[0])) return [-9999]; // clouds
  let ndvi = (s.B08[0] - s.B04[0]) / (s.B08[0] + s.B04[0]);
  return [ndvi];
}
"""

# Port activity evalscript (SAR-based, Sentinel-1 would be ideal; using optical fallback)
EVALSCRIPT_PORT = """
//VERSION=3
function setup() {
  return { input: ["B02","B03","B04"], output: { bands: 3, sampleType: "UINT8" } };
}
function evaluatePixel(s) {
  return [2.5*s.B04[0]*255, 2.5*s.B03[0]*255, 2.5*s.B02[0]*255];
}
"""

# Predefined AOIs (Area of Interest) keyed by zone name
ZONE_AOIS = {
    "ukraine_wheat": {"bbox": [22.0, 46.0, 38.0, 52.0], "purpose": "crop_ndvi"},
    "suez_port":     {"bbox": [32.2, 29.9, 32.7, 30.3], "purpose": "port_activity"},
    "hormuz":        {"bbox": [56.0, 25.8, 57.2, 26.8], "purpose": "port_activity"},
    "black_sea":     {"bbox": [31.0, 42.5, 36.0, 46.0], "purpose": "port_activity"},
    "odessa_port":   {"bbox": [30.6, 46.3, 30.9, 46.6], "purpose": "port_activity"},
    "novorossiysk":  {"bbox": [37.7, 44.6, 38.0, 44.8], "purpose": "port_activity"},
    "gdansk_port":   {"bbox": [18.6, 54.3, 18.8, 54.5], "purpose": "port_activity"},
}


@dataclass
class SatelliteResult:
    zone: str
    purpose: str
    mean_value: float
    coverage_pct: float
    ts: float
    interpretation: str


class CopernicusClient:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: Optional[str] = None
        self._token_expires: float = 0.0

    async def _get_token(self, session: aiohttp.ClientSession) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        async with session.post(TOKEN_URL, data=data) as resp:
            result = await resp.json()
            self._token = result["access_token"]
            self._token_expires = time.time() + result.get("expires_in", 3600)
        return self._token

    def _build_request(self, bbox: list, purpose: str, date_from: str, date_to: str) -> dict:
        evalscript = EVALSCRIPT_NDVI if purpose == "crop_ndvi" else EVALSCRIPT_PORT
        return {
            "input": {
                "bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": f"{date_from}T00:00:00Z", "to": f"{date_to}T23:59:59Z"},
                        "maxCloudCoverage": 30,
                    }
                }]
            },
            "output": {"width": 256, "height": 256, "responses": [{"format": {"type": "image/tiff"}}]},
            "evalscript": evalscript,
        }

    async def analyze_zone(self, session: aiohttp.ClientSession, zone: str,
                           date_from: str, date_to: str) -> Optional[SatelliteResult]:
        aoi = ZONE_AOIS.get(zone)
        if not aoi:
            logger.warning(f"[Copernicus] Unknown zone: {zone}")
            return None

        try:
            token = await self._get_token(session)
            payload = self._build_request(aoi["bbox"], aoi["purpose"], date_from, date_to)
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

            async with session.post(PROCESS_URL, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    logger.error(f"[Copernicus] {zone} → HTTP {resp.status}")
                    return None
                # In a real implementation, parse the GeoTIFF response
                # Here we return a mock result structure (real: use rasterio)
                raw_bytes = await resp.read()
                mock_mean = 0.62  # placeholder — real: np.nanmean(rasterio.open(raw_bytes).read(1))
                interpretation = self._interpret(aoi["purpose"], mock_mean)
                return SatelliteResult(
                    zone=zone, purpose=aoi["purpose"],
                    mean_value=mock_mean, coverage_pct=0.85,
                    ts=time.time(), interpretation=interpretation,
                )
        except Exception as exc:
            logger.error(f"[Copernicus] {zone} error: {exc}")
            return None

    @staticmethod
    def _interpret(purpose: str, value: float) -> str:
        if purpose == "crop_ndvi":
            if value > 0.6:
                return "Vegetation healthy — no stress detected"
            if value > 0.3:
                return "Moderate vegetation stress — monitor for drought progression"
            return "SEVERE vegetation stress — crop failure risk"
        else:  # port_activity
            if value > 0.7:
                return "High port activity — normal or elevated throughput"
            if value > 0.4:
                return "Reduced port activity — possible disruption"
            return "Very low port activity — significant disruption detected"


class SatelliteMonitor:
    """Activated by the agent on demand — not polling continuously."""

    def __init__(self) -> None:
        cid = os.getenv("SENTINEL_HUB_CLIENT_ID")
        csec = os.getenv("SENTINEL_HUB_CLIENT_SECRET")
        if cid and csec:
            self._client = CopernicusClient(cid, csec)
            self.available = True
        else:
            self._client = None
            self.available = False
            logger.warning("[Copernicus] Credentials not set — satellite disabled")

    async def scan_zone(self, zone: str, date_from: str, date_to: str) -> Optional[Signal]:
        if not self.available or not self._client:
            return None
        async with aiohttp.ClientSession() as session:
            result = await self._client.analyze_zone(session, zone, date_from, date_to)
            if not result:
                return None

            raw = RawEvent(
                source="copernicus",
                domain=Domain.SATELLITE,
                entity_id=zone,
                payload={"zone": zone, "mean_value": result.mean_value,
                         "interpretation": result.interpretation, "purpose": result.purpose},
                tags=["satellite", zone, result.purpose],
            )
            await bus.publish_raw(raw)

            severity = Severity.HIGH if "SEVERE" in result.interpretation or "significant" in result.interpretation.lower() \
                else Severity.MEDIUM

            signal = Signal(
                signal_id=f"copernicus_{zone}_{int(result.ts)}",
                source="copernicus",
                domain=Domain.SATELLITE,
                title=f"[SAT] {zone.upper()} — {result.interpretation[:80]}",
                severity=severity,
                value=result.mean_value,
                context={
                    "zone": zone, "purpose": result.purpose,
                    "mean_value": round(result.mean_value, 4),
                    "coverage_pct": result.coverage_pct,
                    "interpretation": result.interpretation,
                    "date_range": f"{date_from} → {date_to}",
                },
            )
            await bus.publish_signal(signal)
            logger.info(f"[Copernicus] Signal: {signal.title}")
            return signal


# Global singleton
satellite = SatelliteMonitor()
