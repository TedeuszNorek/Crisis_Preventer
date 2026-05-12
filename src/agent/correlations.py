"""Cross-domain correlation rules.

When signal X fires from source A → agent checks source B automatically.
These rules encode domain knowledge: what to look for next when something happens.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from src.core.models import Domain, Signal


@dataclass
class CorrelationRule:
    name: str
    description: str
    trigger: Callable[[Signal], bool]
    activate_sources: List[str]       # which sources to spin up / increase polling
    activate_sat_zones: List[str]     # which satellite zones to scan
    bump_polling: dict                # {source: new_interval_seconds}
    priority: int                     # 1=low … 5=critical
    rationale: str


RULES: List[CorrelationRule] = [

    # ── Maritime disruption ──────────────────────────────────────────────
    CorrelationRule(
        name="maritime_disruption",
        description="AIS vessel stopped or anomalous in strategic strait",
        trigger=lambda s: (
            s.source == "ais" and
            s.severity.value in ("HIGH", "CRITICAL") and
            any(z in str(s.context) for z in ["suez", "hormuz", "bab_el_mandeb", "taiwan_strait"])
        ),
        activate_sources=["polymarket", "deribit", "binance"],
        activate_sat_zones=["suez_port", "hormuz"],
        bump_polling={"ais": 15, "polymarket": 30, "binance": 15},
        priority=4,
        rationale="Vessel anomaly in strategic strait → check oil/commodity markets + prediction markets",
    ),

    # ── Crypto IV spike → look for macro driver ──────────────────────────
    CorrelationRule(
        name="iv_spike_macro_check",
        description="Deribit IV spike → find macro/news cause",
        trigger=lambda s: (
            s.source == "deribit" and
            s.severity.value in ("HIGH", "CRITICAL") and
            "SPIKE" in s.title
        ),
        activate_sources=["rss", "polymarket"],
        activate_sat_zones=[],
        bump_polling={"rss": 60, "polymarket": 30, "binance": 15},
        priority=3,
        rationale="Options IV spike usually driven by an event — scan news + prediction markets",
    ),

    # ── Binance OI/funding extreme → search for narrative ────────────────
    CorrelationRule(
        name="binance_extreme_funding",
        description="Extreme Binance funding rate → check if news-driven",
        trigger=lambda s: (
            s.source == "binance" and
            s.severity.value == "CRITICAL"
        ),
        activate_sources=["deribit", "polymarket", "rss"],
        activate_sat_zones=[],
        bump_polling={"binance": 10, "deribit": 20, "rss": 60},
        priority=4,
        rationale="Extreme funding + OI usually precedes large move — widen monitoring net",
    ),

    # ── News mentions war/conflict → maritime + commodity + prediction ────
    CorrelationRule(
        name="conflict_news",
        description="RSS picks up war/conflict/military keywords",
        trigger=lambda s: (
            s.source == "rss" and
            any(kw in s.context.get("keywords", []) for kw in ["war", "conflict", "blockade", "sanctions"])
        ),
        activate_sources=["ais", "polymarket", "deribit"],
        activate_sat_zones=["black_sea", "suez_port", "hormuz"],
        bump_polling={"ais": 20, "polymarket": 45, "rss": 90},
        priority=5,
        rationale="Conflict news → check shipping disruption (AIS) + market reaction (Deribit, Polymarket)",
    ),

    # ── Commodity news → satellite verification ──────────────────────────
    CorrelationRule(
        name="commodity_satellite",
        description="Commodity supply disruption news → verify with satellite",
        trigger=lambda s: (
            s.source == "rss" and
            any(kw in s.context.get("keywords", []) for kw in ["drought", "harvest", "wheat", "grain"])
        ),
        activate_sources=["polymarket"],
        activate_sat_zones=["ukraine_wheat"],
        bump_polling={"rss": 120},
        priority=3,
        rationale="Commodity news → check crop health via Copernicus NDVI",
    ),

    # ── Polymarket big prob shift → find cause ───────────────────────────
    CorrelationRule(
        name="polymarket_repricing",
        description="Prediction market rapid repricing → find the trigger",
        trigger=lambda s: (
            s.source == "polymarket" and
            s.value > 0.10 and
            s.severity.value in ("HIGH", "CRITICAL")
        ),
        activate_sources=["rss", "binance"],
        activate_sat_zones=[],
        bump_polling={"rss": 60, "polymarket": 30},
        priority=3,
        rationale="Prediction market repricing → scan RSS for the news driver + crypto reaction",
    ),

    # ── Port activity anomaly (satellite) → check shipping + markets ─────
    CorrelationRule(
        name="satellite_port_anomaly",
        description="Satellite shows low port activity",
        trigger=lambda s: (
            s.source == "copernicus" and
            "low port activity" in s.context.get("interpretation", "").lower()
        ),
        activate_sources=["ais", "polymarket"],
        activate_sat_zones=[],
        bump_polling={"ais": 15},
        priority=4,
        rationale="Satellite confirms port disruption → cross-check with AIS live data",
    ),
]


def matching_rules(signal: Signal) -> List[CorrelationRule]:
    return [r for r in RULES if r.trigger(signal)]
