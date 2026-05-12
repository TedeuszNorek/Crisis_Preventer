"""Binance Futures monitor — OI, funding rate, price momentum.

Publishes signals when anomalies detected via Z-score.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from typing import Deque, Dict, List

import aiohttp

from src.core.event_bus import bus
from src.core.models import Domain, RawEvent, Signal, Severity

logger = logging.getLogger(__name__)

FAPI_BASE = "https://fapi.binance.com/fapi/v1"

DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "AVAXUSDT", "DOGEUSDT",
]


def _zscore(history: Deque[float], value: float) -> float:
    if len(history) < 10:
        return 0.0
    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std = variance ** 0.5
    return (value - mean) / std if std > 0 else 0.0


class BinanceMonitor:
    def __init__(self, symbols: List[str] = DEFAULT_SYMBOLS, z_threshold: float = 2.5) -> None:
        self.symbols = symbols
        self.z_threshold = z_threshold
        self._oi_history: Dict[str, Deque[float]] = {s: deque(maxlen=60) for s in symbols}
        self._funding_history: Dict[str, Deque[float]] = {s: deque(maxlen=60) for s in symbols}
        self._price_history: Dict[str, Deque[float]] = {s: deque(maxlen=60) for s in symbols}

    async def _fetch(self, session: aiohttp.ClientSession, endpoint: str, params: dict = {}) -> dict | list:
        try:
            async with session.get(f"{FAPI_BASE}/{endpoint}", params=params,
                                   timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"[Binance] {endpoint} → HTTP {resp.status}")
        except Exception as exc:
            logger.error(f"[Binance] {endpoint} error: {exc}")
        return {}

    async def _fetch_all(self, session: aiohttp.ClientSession) -> None:
        # ── Funding rates ────────────────────────────────────────────────
        funding_data = await self._fetch(session, "premiumIndex")
        funding_map = {}
        if isinstance(funding_data, list):
            for item in funding_data:
                sym = item.get("symbol")
                if sym in self.symbols:
                    funding_map[sym] = float(item.get("lastFundingRate", 0)) * 100

        for sym in self.symbols:
            # ── Open Interest ────────────────────────────────────────────
            oi_data = await self._fetch(session, "openInterest", {"symbol": sym})
            oi = float(oi_data.get("openInterest", 0)) if oi_data else 0.0

            # ── Price ────────────────────────────────────────────────────
            ticker = await self._fetch(session, "ticker/price", {"symbol": sym})
            price = float(ticker.get("price", 0)) if ticker else 0.0

            funding = funding_map.get(sym, 0.0)
            ts = time.time()

            raw = RawEvent(
                source="binance",
                domain=Domain.CRYPTO,
                entity_id=sym,
                payload={"symbol": sym, "oi": oi, "funding": funding, "price": price},
                tags=["crypto", "futures"],
            )
            await bus.publish_raw(raw)

            # ── Anomaly detection ────────────────────────────────────────
            oi_z = _zscore(self._oi_history[sym], oi)
            fund_z = _zscore(self._funding_history[sym], funding)

            self._oi_history[sym].append(oi)
            self._funding_history[sym].append(funding)
            self._price_history[sym].append(price)

            anomalies = []
            if abs(oi_z) > self.z_threshold:
                anomalies.append(f"OI z={oi_z:.2f}")
            if abs(fund_z) > self.z_threshold:
                anomalies.append(f"Funding z={fund_z:.2f}")

            if anomalies:
                # Very high funding = crowded longs = potential squeeze
                severity = Severity.CRITICAL if (abs(oi_z) > 3.5 or abs(fund_z) > 3.5) else Severity.HIGH
                signal = Signal(
                    signal_id=f"binance_{sym}_{int(ts)}",
                    source="binance",
                    domain=Domain.CRYPTO,
                    title=f"[BINANCE] Anomaly {sym}: {', '.join(anomalies)}",
                    severity=severity,
                    value=oi_z,
                    context={
                        "symbol": sym, "oi": oi, "oi_zscore": round(oi_z, 2),
                        "funding_rate_pct": round(funding, 4), "funding_zscore": round(fund_z, 2),
                        "price": price,
                    },
                )
                await bus.publish_signal(signal)
                logger.info(f"[Binance] Signal: {signal.title}")

    async def run(self) -> None:
        logger.info(f"[Binance] Monitor started — {len(self.symbols)} symbols")
        async with aiohttp.ClientSession() as session:
            while True:
                interval = bus.polling_rates.get("binance", 30)
                try:
                    await self._fetch_all(session)
                except Exception as exc:
                    logger.error(f"[Binance] Cycle error: {exc}")
                await asyncio.sleep(interval)
