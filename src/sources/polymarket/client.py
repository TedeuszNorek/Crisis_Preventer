"""Polymarket monitor — prediction market probabilities and anomalies.

Correlates prediction market moves with RSS news and macro events.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List

import aiohttp

from src.core.event_bus import bus
from src.core.models import Domain, RawEvent, Signal, Severity

logger = logging.getLogger(__name__)

GAMMA_API = "https://gamma-api.polymarket.com"

# Topic tags for routing
MARKET_TOPIC_KEYWORDS = {
    "war": ["war", "conflict", "attack", "military", "invasion"],
    "election": ["election", "president", "vote", "winner", "candidate"],
    "crypto": ["bitcoin", "btc", "ethereum", "crypto", "halving"],
    "macro": ["fed", "rate", "inflation", "recession", "gdp"],
    "energy": ["oil", "gas", "opec", "energy", "barrel"],
    "maritime": ["ship", "port", "canal", "strait", "tanker"],
}


def _tag_market(title: str) -> List[str]:
    title_lower = title.lower()
    return [topic for topic, keywords in MARKET_TOPIC_KEYWORDS.items()
            if any(kw in title_lower for kw in keywords)]


class PolymarketMonitor:
    def __init__(self) -> None:
        self._prob_history: Dict[str, List[float]] = {}

    async def _fetch_active_markets(self, session: aiohttp.ClientSession) -> list:
        try:
            url = f"{GAMMA_API}/events"
            params = {"active": "true", "closed": "false", "limit": 200}
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as exc:
            logger.error(f"[Polymarket] Fetch error: {exc}")
        return []

    def _detect_prob_shift(self, market_id: str, prob: float) -> float:
        """Returns shift from previous value; 0 if no history."""
        history = self._prob_history.setdefault(market_id, [])
        if not history:
            history.append(prob)
            return 0.0
        shift = abs(prob - history[-1])
        history.append(prob)
        if len(history) > 30:
            history.pop(0)
        return shift

    async def _process_event(self, event: dict) -> None:
        event_id = event.get("id", "unknown")
        event_title = event.get("title", "")
        topic_tags = _tag_market(event_title)

        for market in event.get("markets", []):
            if market.get("closed") or not market.get("active"):
                continue

            market_id = market.get("id", "unknown")
            liq = float(market.get("liquidity", 0) or 0)
            if liq < 5000:
                continue

            try:
                prices = __import__("json").loads(market.get("outcomePrices", "[0,0]"))
                prob_yes = float(prices[0]) if prices else 0.0
            except Exception:
                prob_yes = 0.0

            shift = self._detect_prob_shift(market_id, prob_yes)
            ts = time.time()

            raw = RawEvent(
                source="polymarket",
                domain=Domain.PREDICTION,
                entity_id=market_id,
                payload={
                    "event_id": event_id, "event_title": event_title,
                    "market_id": market_id, "question": market.get("question", ""),
                    "prob_yes": prob_yes, "liquidity": liq,
                    "prob_shift": shift, "topic_tags": topic_tags,
                },
                tags=["prediction"] + topic_tags,
            )
            await bus.publish_raw(raw)

            # Big probability shifts = market is repricing an event
            if shift > 0.05 and liq > 20000:
                severity = Severity.CRITICAL if shift > 0.15 else (
                    Severity.HIGH if shift > 0.10 else Severity.MEDIUM)
                signal = Signal(
                    signal_id=f"polymarket_{market_id}_{int(ts)}",
                    source="polymarket",
                    domain=Domain.PREDICTION,
                    title=f"[PM] Prob shift +{shift:.0%} — {market.get('question', '')[:100]}",
                    severity=severity,
                    value=shift,
                    context={
                        "question": market.get("question", ""),
                        "event_title": event_title,
                        "prob_yes": round(prob_yes, 3),
                        "prob_shift": round(shift, 3),
                        "liquidity": round(liq),
                        "topic_tags": topic_tags,
                    },
                )
                await bus.publish_signal(signal)
                logger.info(f"[Polymarket] Signal: {signal.title}")

            # Free money: near-certain resolution but not yet resolved
            for price in [prob_yes, 1 - prob_yes]:
                if 0.93 <= price <= 0.998 and liq >= 10000:
                    signal = Signal(
                        signal_id=f"polymarket_fm_{market_id}_{int(ts)}",
                        source="polymarket",
                        domain=Domain.PREDICTION,
                        title=f"[PM] HIGH-CERTAINTY PREMIUM — {market.get('question', '')[:80]}",
                        severity=Severity.HIGH,
                        value=price,
                        context={
                            "question": market.get("question", ""),
                            "price": round(price, 3),
                            "implied_edge_pct": round((1 / price - 1) * 100, 2),
                            "liquidity": round(liq),
                        },
                    )
                    await bus.publish_signal(signal)
                    break

    async def run(self) -> None:
        logger.info("[Polymarket] Monitor started")
        async with aiohttp.ClientSession() as session:
            while True:
                interval = bus.polling_rates.get("polymarket", 120)
                try:
                    events = await self._fetch_active_markets(session)
                    for event in events:
                        await self._process_event(event)
                    logger.info(f"[Polymarket] Processed {len(events)} events")
                except Exception as exc:
                    logger.error(f"[Polymarket] Cycle error: {exc}")
                await asyncio.sleep(interval)
