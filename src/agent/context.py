"""Builds a context bundle for the LLM agent from recent signals."""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from src.core.event_bus import bus
from src.core.models import Domain, Signal


def _signal_to_dict(s: Signal) -> Dict[str, Any]:
    return {
        "id": s.signal_id,
        "source": s.source,
        "domain": s.domain.value,
        "title": s.title,
        "severity": s.severity.value,
        "value": round(s.value, 4),
        "age_seconds": round(time.time() - s.ts),
        "context": s.context,
        "agent_note": s.agent_note,
    }


def build_context(max_signals: int = 30) -> Dict[str, Any]:
    """Assemble recent signals + system state for the LLM agent."""
    recent = bus.recent_signals(max_signals)
    escalations = bus.recent_escalations(5)

    # Group by domain for readability
    by_domain: Dict[str, List] = {}
    for s in recent:
        domain = s.domain.value
        by_domain.setdefault(domain, []).append(_signal_to_dict(s))

    # Severity summary
    severity_counts: Dict[str, int] = {}
    for s in recent:
        severity_counts[s.severity.value] = severity_counts.get(s.severity.value, 0) + 1

    active_sources = list({s.source for s in recent})
    high_severity = [_signal_to_dict(s) for s in recent
                     if s.severity.value in ("HIGH", "CRITICAL")]

    return {
        "timestamp": time.time(),
        "window_description": f"Last {max_signals} signals",
        "severity_summary": severity_counts,
        "active_sources": active_sources,
        "polling_rates": bus.polling_rates,
        "high_severity_signals": high_severity[:10],
        "signals_by_domain": by_domain,
        "recent_escalations": [
            {
                "trigger": e.trigger_signal.title,
                "modules_activated": e.activate_modules,
                "priority": e.priority,
                "rationale": e.rationale,
                "age_seconds": round(time.time() - e.ts),
            }
            for e in escalations
        ],
    }


def context_to_prompt(ctx: Dict[str, Any]) -> str:
    """Format context as a structured prompt section for the LLM."""
    lines = [
        "=== VORTEX ANALYTICA — CURRENT SYSTEM STATE ===",
        f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(ctx['timestamp']))}",
        f"Active sources: {', '.join(ctx['active_sources']) or 'none'}",
        f"Severity breakdown: {json.dumps(ctx['severity_summary'])}",
        "",
        "--- HIGH / CRITICAL SIGNALS (last 30 min) ---",
    ]

    for s in ctx["high_severity_signals"]:
        age_min = s["age_seconds"] // 60
        lines.append(
            f"[{s['severity']}] {s['title']}  "
            f"(source={s['source']}, domain={s['domain']}, {age_min}min ago)"
        )
        if s["context"]:
            top_ctx = {k: v for k, v in list(s["context"].items())[:4]}
            lines.append(f"  context: {json.dumps(top_ctx, ensure_ascii=False)}")

    lines.append("")
    lines.append("--- RECENT ESCALATIONS ---")
    for esc in ctx["recent_escalations"]:
        lines.append(
            f"  Triggered by: {esc['trigger']}  →  activated: {esc['modules_activated']}  "
            f"(priority={esc['priority']}, {esc['age_seconds']//60}min ago)"
        )

    lines.append("")
    lines.append("--- CURRENT POLLING RATES (seconds) ---")
    for src, interval in ctx["polling_rates"].items():
        lines.append(f"  {src}: {interval}s")

    return "\n".join(lines)
