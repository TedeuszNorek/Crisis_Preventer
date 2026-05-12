"""Deribit options monitor — implied volatility, options chain, gamma exposure.

Publishes signals when IV spikes or unusual options flow detected.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Deque, Dict

import aiohttp

from src.core.event_bus import bus
from src.core.models import Domain, RawEvent, Signal, Severity

logger = logging.getLogger(__name__)

DERIBIT_BASE = "https://www.deribit.com/api/v2/public"
CURRENCIES = ["BTC", "ETH"]


def _zscore(history: Deque[float], value: float) -> float:
    if len(history) < 10:
        return 0.0
    mean = sum(history) / len(history)
    std = (sum((x - mean) ** 2 for x in history) / len(history)) ** 0.5
    return (value - mean) / std if std > 0 else 0.0


class DeribitMonitor:
    def __init__(self) -> None:
        self._iv_history: Dict[str, Deque[float]] = {c: deque(maxlen=60) for c in CURRENCIES}
        self._vol_history: Dict[str, Deque[float]] = {c: deque(maxlen=60) for c in CURRENCIES}

    async def _fetch_chain(self, session: aiohttp.ClientSession, currency: str) -> dict:
        try:
            url = f"{DERIBIT_BASE}/get_book_summary_by_currency"
            params = {"currency": currency, "kind": "option"}
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as exc:
            logger.error(f"[Deribit] {currency} error: {exc}")
        return {}

    def _compute_wiv(self, results: list) -> tuple[float, float]:
        """Compute volume-weighted implied volatility."""
        valid = [o for o in results if o.get("volume", 0) > 0 and o.get("mark_iv", 0) > 0]
        if not valid:
            return 0.0, 0.0
        total_vol = sum(o["volume"] for o in valid)
        wiv = sum(o["mark_iv"] * o["volume"] / total_vol for o in valid) / 100.0
        return wiv, total_vol

    def _gamma_flip_estimate(self, results: list, spot: float) -> float:
        """Rough estimate of gamma-weighted strike = 'gamma flip' zone."""
        if not results or spot == 0:
            return 0.0
        call_gamma = sum(o.get("gamma", 0) * o.get("open_interest", 0)
                         for o in results if o.get("instrument_name", "").endswith("C"))
        put_gamma = sum(o.get("gamma", 0) * o.get("open_interest", 0)
                        for o in results if o.get("instrument_name", "").endswith("P"))
        return call_gamma - put_gamma

    async def _process_currency(self, session: aiohttp.ClientSession, currency: str) -> None:
        data = await self._fetch_chain(session, currency)
        results = data.get("result", [])
        if not results:
            return

        wiv, total_vol = self._compute_wiv(results)
        ts = time.time()

        raw = RawEvent(
            source="deribit",
            domain=Domain.CRYPTO,
            entity_id=f"{currency}_OPTIONS",
            payload={"currency": currency, "wiv": wiv, "chain_volume": total_vol},
            tags=["crypto", "options", "volatility"],
        )
        await bus.publish_raw(raw)

        iv_z = _zscore(self._iv_history[currency], wiv)
        vol_z = _zscore(self._vol_history[currency], total_vol)

        self._iv_history[currency].append(wiv)
        self._vol_history[currency].append(total_vol)

        if abs(iv_z) > 2.5 or abs(vol_z) > 3.0:
            direction = "SPIKE" if wiv > (sum(self._iv_history[currency]) / max(len(self._iv_history[currency]), 1)) else "CRUSH"
            severity = Severity.CRITICAL if abs(iv_z) > 4.0 else Severity.HIGH
            signal = Signal(
                signal_id=f"deribit_{currency}_{int(ts)}",
                source="deribit",
                domain=Domain.CRYPTO,
                title=f"[DERIBIT] IV {direction} {currency} — IV={wiv:.1%} z={iv_z:.2f}",
                severity=severity,
                value=wiv,
                context={
                    "currency": currency,
                    "implied_volatility": round(wiv, 4),
                    "iv_zscore": round(iv_z, 2),
                    "chain_volume": round(total_vol, 2),
                    "vol_zscore": round(vol_z, 2),
                    "direction": direction,
                },
            )
            await bus.publish_signal(signal)
            logger.info(f"[Deribit] Signal: {signal.title}")

    async def run(self) -> None:
        logger.info("[Deribit] Monitor started")
        async with aiohttp.ClientSession() as session:
            while True:
                interval = bus.polling_rates.get("deribit", 60)
                for currency in CURRENCIES:
                    try:
                        await self._process_currency(session, currency)
                    except Exception as exc:
                        logger.error(f"[Deribit] {currency} error: {exc}")
                await asyncio.sleep(interval)
