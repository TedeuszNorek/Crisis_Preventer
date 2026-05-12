"""Central async event bus connecting all sources to the agent and UI."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Callable, Deque, Dict, List, Optional

from .models import EscalationDecision, RawEvent, Signal

logger = logging.getLogger(__name__)

# Max events kept in memory for context window
_MAX_HISTORY = 500


class EventBus:
    def __init__(self) -> None:
        self._raw_queue: asyncio.Queue[RawEvent] = asyncio.Queue()
        self._signal_queue: asyncio.Queue[Signal] = asyncio.Queue()
        self._escalation_queue: asyncio.Queue[EscalationDecision] = asyncio.Queue()

        self._signal_history: Deque[Signal] = deque(maxlen=_MAX_HISTORY)
        self._escalation_history: Deque[EscalationDecision] = deque(maxlen=50)

        self._signal_subscribers: List[Callable] = []
        self._escalation_subscribers: List[Callable] = []

        # Per-source polling rates (seconds); agent can modify these
        self.polling_rates: Dict[str, int] = {
            "binance": 30,
            "deribit": 60,
            "polymarket": 120,
            "ais": 30,
            "rss": 300,
            "copernicus": 3600,
        }

    # ── Publishing ──────────────────────────────────────────────────────────

    async def publish_raw(self, event: RawEvent) -> None:
        await self._raw_queue.put(event)

    async def publish_signal(self, signal: Signal) -> None:
        self._signal_history.append(signal)
        await self._signal_queue.put(signal)
        for cb in self._signal_subscribers:
            try:
                await cb(signal)
            except Exception as exc:
                logger.error(f"Signal subscriber error: {exc}")

    async def publish_escalation(self, decision: EscalationDecision) -> None:
        self._escalation_history.append(decision)
        await self._escalation_queue.put(decision)
        for cb in self._escalation_subscribers:
            try:
                await cb(decision)
            except Exception as exc:
                logger.error(f"Escalation subscriber error: {exc}")

    # ── Subscriptions ────────────────────────────────────────────────────────

    def on_signal(self, cb: Callable) -> None:
        self._signal_subscribers.append(cb)

    def on_escalation(self, cb: Callable) -> None:
        self._escalation_subscribers.append(cb)

    # ── Queries ──────────────────────────────────────────────────────────────

    def recent_signals(self, n: int = 20) -> List[Signal]:
        return list(self._signal_history)[-n:]

    def recent_escalations(self, n: int = 5) -> List[EscalationDecision]:
        return list(self._escalation_history)[-n:]

    def set_polling_rate(self, source: str, seconds: int) -> None:
        old = self.polling_rates.get(source, "?")
        self.polling_rates[source] = seconds
        logger.info(f"[EventBus] Polling rate {source}: {old}s → {seconds}s")

    # ── Queues (for consumers) ───────────────────────────────────────────────

    async def next_raw(self) -> RawEvent:
        return await self._raw_queue.get()

    async def next_signal(self) -> Signal:
        return await self._signal_queue.get()

    async def next_escalation(self) -> EscalationDecision:
        return await self._escalation_queue.get()


# Global singleton
bus = EventBus()
