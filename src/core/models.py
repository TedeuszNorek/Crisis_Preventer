"""Unified event and signal models shared across all sources."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Domain(str, Enum):
    CRYPTO = "crypto"
    MARITIME = "maritime"
    MACRO = "macro"
    NEWS = "news"
    SATELLITE = "satellite"
    PREDICTION = "prediction"


@dataclass
class RawEvent:
    source: str
    domain: Domain
    entity_id: str
    payload: Dict[str, Any]
    ts: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)


@dataclass
class Signal:
    signal_id: str
    source: str
    domain: Domain
    title: str
    severity: Severity
    value: float
    context: Dict[str, Any]
    ts: float = field(default_factory=time.time)
    related_signals: List[str] = field(default_factory=list)
    agent_note: Optional[str] = None


@dataclass
class EscalationDecision:
    trigger_signal: Signal
    activate_modules: List[str]
    rationale: str
    priority: int          # 1=low … 5=critical
    agent_commentary: str
    ts: float = field(default_factory=time.time)


@dataclass
class Incident:
    """A focused intelligence picture assembled by the agent for one event."""
    incident_id: str
    title: str
    severity: str           # "HIGH" | "CRITICAL"
    commentary: str         # agent-written synthesis
    instruments: List[str]  # tickers/zones to watch (e.g. OIL, AIS_SUEZ)
    zone: Optional[str]     # geographic zone if identified (e.g. "hormuz")
    timeline: List[Dict[str, Any]]  # [{ts, source, title, severity}]
    ts: float = field(default_factory=time.time)
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "severity": self.severity,
            "commentary": self.commentary,
            "instruments": self.instruments,
            "zone": self.zone,
            "timeline": self.timeline,
            "ts": self.ts,
            "active": self.active,
        }
