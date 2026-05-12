"""LLM Orchestrator — the brain of Vortex Analytica.

Watches the event bus, applies correlation rules, and uses an LLM
to decide when to escalate, which modules to activate, and what to
write in the live feed.

Supports: Claude, DeepSeek, OpenAI, OpenRouter, local (Ollama/vLLM).
Set LLM_PROVIDER and LLM_MODEL in .env to switch.

Tool use schema:
  - activate_module(name, reason, poll_seconds)
  - scan_satellite(zone, reason, date_from, date_to)
  - write_feed_entry(severity, text, instruments)
  - no_action(reason)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.event_bus import bus
from src.core.models import EscalationDecision, Incident, Signal, Severity
from src.sources.copernicus.client import satellite
from .context import build_context, context_to_prompt
from .correlations import matching_rules
from .llm import LLMClient

logger = logging.getLogger(__name__)

# Maps instrument tags → geographic zone names (used by the lens map)
_INSTRUMENT_ZONE_MAP: Dict[str, str] = {
    "AIS_HORMUZ": "hormuz",
    "AIS_SUEZ": "suez_port",
    "AIS_MALACCA": "malacca",
    "AIS_TAIWAN": "taiwan_strait",
    "AIS_BLACK_SEA": "black_sea",
    "AIS_BALTIC": "gdansk_port",
    "AIS_GLOBAL": "",
    "OIL": "hormuz",
    "OIL_FUTURES": "hormuz",
    "WHEAT": "ukraine_wheat",
}

# ── Claude tool definitions ──────────────────────────────────────────────────

TOOLS = [
    {
        "name": "activate_module",
        "description": (
            "Activate or increase polling of a monitoring module because a signal warrants it. "
            "Use when correlation rules or your analysis suggest a cross-domain check is needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "enum": ["binance", "deribit", "polymarket", "ais", "rss", "copernicus"],
                    "description": "Module to activate or boost",
                },
                "reason": {"type": "string", "description": "Why this module is needed right now"},
                "poll_seconds": {
                    "type": "integer",
                    "description": "New polling interval in seconds (lower = more frequent)",
                    "minimum": 5, "maximum": 3600,
                },
            },
            "required": ["module", "reason", "poll_seconds"],
        },
    },
    {
        "name": "scan_satellite",
        "description": (
            "Trigger a Copernicus satellite scan of a specific geographic zone. "
            "Use only for HIGH or CRITICAL events where physical verification adds value "
            "(port disruption, crop failure, military buildup)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "enum": ["ukraine_wheat", "suez_port", "hormuz", "black_sea",
                             "odessa_port", "novorossiysk", "gdansk_port", "taiwan_strait"],
                },
                "reason": {"type": "string"},
                "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["zone", "reason", "date_from", "date_to"],
        },
    },
    {
        "name": "write_feed_entry",
        "description": (
            "Write an entry to the live analyst feed ('bieżaczka'). "
            "Write in Polish. Be concise (1-3 sentences). Focus on WHAT happened, "
            "WHY it matters, and WHAT to watch next. Skip trivial signals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["INFO", "MEDIUM", "HIGH", "CRITICAL"],
                },
                "text": {
                    "type": "string",
                    "description": "Feed entry in Polish, max 300 chars",
                },
                "instruments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Related instruments/tickers (e.g. BTC, OIL, AIS_SUEZ)",
                },
            },
            "required": ["severity", "text"],
        },
    },
    {
        "name": "no_action",
        "description": "Signal does not warrant escalation or a feed entry.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
            },
            "required": ["reason"],
        },
    },
]

SYSTEM_PROMPT = """You are Vortex Analytica — an autonomous real-time signal analysis system.

Your job:
1. Evaluate incoming signals from multiple sources (crypto, AIS ships, RSS news, satellite, prediction markets).
2. Decide which modules to activate or boost (cross-domain correlation).
3. Write a live feed entry ONLY when something is genuinely significant.
4. Trigger a satellite scan ONLY when there is a concrete geographic reason.

Rules:
- Do NOT write a feed entry for every signal — filter the noise. Threshold: MEDIUM+ severity with a clear market or geopolitical implication.
- Connect signals across domains (e.g. AIS anomaly in Hormuz + Deribit IV spike = oil supply crunch).
- Think like a senior analyst, not an alert aggregator.
- write_feed_entry text should be concise (1-3 sentences), in English.
- For CRITICAL signals: always write_feed_entry AND at least one activate_module."""


class FeedEntry:
    def __init__(self, severity: str, text: str, instruments: List[str], ts: float) -> None:
        self.severity = severity
        self.text = text
        self.instruments = instruments
        self.ts = ts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "text": self.text,
            "instruments": self.instruments,
            "timestamp": self.ts,
            "time_str": datetime.fromtimestamp(self.ts, tz=timezone.utc).strftime("%H:%M:%S UTC"),
        }


class VortexOrchestrator:
    def __init__(self) -> None:
        self._llm = LLMClient()
        self._feed: List[FeedEntry] = []
        self._incidents: List[Incident] = []
        self._last_agent_run: float = 0.0
        self._agent_cooldown = 45  # seconds between full LLM calls (cost control)
        self._pending_signals: List[Signal] = []
        self._last_evaluated_signals: List[Signal] = []
        self._active_modules: Dict[str, bool] = {
            "binance": True, "deribit": True, "polymarket": True,
            "ais": True, "rss": True, "copernicus": False,
        }

    # ── Signal intake ────────────────────────────────────────────────────────

    async def on_signal(self, signal: Signal) -> None:
        self._pending_signals.append(signal)

        # Immediate rule-based escalation (no LLM needed for speed)
        rules = matching_rules(signal)
        for rule in rules:
            for src in rule.activate_sources:
                bus.set_polling_rate(src, rule.bump_polling.get(src, bus.polling_rates.get(src, 60)))

            if rule.activate_sat_zones and signal.severity in (Severity.HIGH, Severity.CRITICAL):
                for zone in rule.activate_sat_zones:
                    asyncio.create_task(self._satellite_scan(zone, rule.rationale))

            decision = EscalationDecision(
                trigger_signal=signal,
                activate_modules=rule.activate_sources + rule.activate_sat_zones,
                rationale=rule.rationale,
                priority=rule.priority,
                agent_commentary=f"Rule: {rule.name}",
            )
            await bus.publish_escalation(decision)
            logger.info(f"[Agent/Rule] {rule.name} → {rule.activate_sources}")

        # Queue for LLM evaluation if high-enough severity
        if signal.severity in (Severity.HIGH, Severity.CRITICAL):
            await self._maybe_run_llm()

    # ── LLM evaluation ───────────────────────────────────────────────────────

    async def _maybe_run_llm(self) -> None:
        now = time.time()
        if now - self._last_agent_run < self._agent_cooldown:
            return
        if not self._pending_signals:
            return
        self._last_agent_run = now
        signals_to_process = self._pending_signals.copy()
        self._pending_signals.clear()
        self._last_evaluated_signals = signals_to_process
        asyncio.create_task(self._llm_evaluate(signals_to_process))

    async def _llm_evaluate(self, signals: List[Signal]) -> None:
        ctx = build_context(30)
        ctx_text = context_to_prompt(ctx)

        # Append the triggering signals
        signal_text = "\n".join(
            f"  [{s.severity.value}] {s.title} — {json.dumps(s.context, ensure_ascii=False)[:200]}"
            for s in signals[:5]
        )
        user_msg = (
            f"{ctx_text}\n\n"
            f"--- NOWE SYGNAŁY DO OCENY ---\n{signal_text}\n\n"
            "Oceń sygnały. Zdecyduj: write_feed_entry jeśli warte uwagi, "
            "activate_module jeśli potrzeba cross-domain check, scan_satellite jeśli uzasadnione geograficznie, "
            "no_action jeśli szum."
        )

        try:
            response = await self._llm.call(
                system=SYSTEM_PROMPT,
                user=user_msg,
                tools=TOOLS,
                max_tokens=1024,
            )
            await self._handle_tool_calls(response)
        except Exception as exc:
            logger.error(f"[Agent/LLM] Error: {exc}")

    def _detect_zone(self, instruments: List[str]) -> Optional[str]:
        for inst in instruments:
            zone = _INSTRUMENT_ZONE_MAP.get(inst.upper())
            if zone:
                return zone
        return None

    def _build_incident(self, inp: Dict[str, Any]) -> Incident:
        instruments = inp.get("instruments", [])
        recent = bus.recent_signals(15)
        timeline = [
            {"ts": s.ts, "source": s.source, "title": s.title, "severity": s.severity.value}
            for s in (recent + self._last_evaluated_signals)[-12:]
        ]
        seen: set = set()
        unique_timeline = []
        for item in sorted(timeline, key=lambda x: x["ts"]):
            key = item["title"]
            if key not in seen:
                seen.add(key)
                unique_timeline.append(item)
        return Incident(
            incident_id=str(uuid.uuid4())[:8],
            title=inp["text"][:100],
            severity=inp["severity"],
            commentary=inp["text"],
            instruments=instruments,
            zone=self._detect_zone(instruments),
            timeline=unique_timeline[-8:],
        )

    async def _handle_tool_calls(self, response: Any) -> None:
        for block in response.tool_calls:
            name = block["name"]
            inp = block["input"]

            if name == "write_feed_entry":
                entry = FeedEntry(
                    severity=inp["severity"],
                    text=inp["text"],
                    instruments=inp.get("instruments", []),
                    ts=time.time(),
                )
                self._feed.append(entry)
                if len(self._feed) > 200:
                    self._feed.pop(0)
                logger.info(f"[Feed] [{entry.severity}] {entry.text[:100]}")

                if inp["severity"] in ("HIGH", "CRITICAL"):
                    incident = self._build_incident(inp)
                    self._incidents.append(incident)
                    if len(self._incidents) > 50:
                        self._incidents.pop(0)
                    await bus.publish_incident(incident)
                    logger.info(f"[Lens] Incident created: {incident.incident_id} zone={incident.zone}")

            elif name == "activate_module":
                module = inp["module"]
                new_interval = inp["poll_seconds"]
                bus.set_polling_rate(module, new_interval)
                self._active_modules[module] = True
                logger.info(f"[Agent/LLM] activate_module: {module} → {new_interval}s — {inp['reason'][:80]}")

            elif name == "scan_satellite":
                asyncio.create_task(
                    self._satellite_scan(inp["zone"], inp["reason"],
                                        inp.get("date_from"), inp.get("date_to"))
                )

            elif name == "no_action":
                logger.debug(f"[Agent/LLM] no_action: {inp.get('reason', '')[:80]}")

    async def _satellite_scan(self, zone: str, reason: str,
                              date_from: Optional[str] = None,
                              date_to: Optional[str] = None) -> None:
        if not satellite.available:
            logger.info(f"[Agent] Satellite scan requested ({zone}) but credentials not set")
            return
        today = datetime.utcnow().strftime("%Y-%m-%d")
        week_ago = datetime.utcnow().strftime("%Y-%m-%d")  # simplified; real: subtract 7 days
        result = await satellite.scan_zone(zone, date_from or week_ago, date_to or today)
        if result:
            logger.info(f"[Agent] Satellite scan {zone}: {result.title}")

    # ── Feed + Incident API ───────────────────────────────────────────────────

    def get_feed(self, limit: int = 50) -> List[Dict]:
        return [e.to_dict() for e in reversed(self._feed[-limit:])]

    def get_incidents(self, limit: int = 20) -> List[Dict]:
        return [i.to_dict() for i in reversed(self._incidents[-limit:])]

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        logger.info("[Agent] Orchestrator started")
        bus.on_signal(self.on_signal)

        # Periodic LLM check even if no HIGH signals (every 5 min)
        while True:
            await asyncio.sleep(300)
            if self._pending_signals:
                await self._maybe_run_llm()


# Global singleton
orchestrator = VortexOrchestrator()
