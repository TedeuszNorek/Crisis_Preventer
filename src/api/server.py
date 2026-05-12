"""FastAPI server — signal ingestion + live feed WebSocket + dashboard."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.core.event_bus import bus
from src.core.models import Domain, RawEvent, Signal, Severity

logger = logging.getLogger(__name__)

app = FastAPI(title="Vortex Analytica API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── WebSocket feed connections ────────────────────────────────────────────────

_ws_clients: List[WebSocket] = []


async def _broadcast(data: dict) -> None:
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


# Subscribe to signal bus — broadcast to all WebSocket clients
async def _on_signal(signal: Signal) -> None:
    await _broadcast({
        "type": "signal",
        "data": {
            "id": signal.signal_id,
            "source": signal.source,
            "domain": signal.domain.value,
            "title": signal.title,
            "severity": signal.severity.value,
            "value": round(signal.value, 4),
            "context": signal.context,
            "ts": signal.ts,
        },
    })


async def _on_escalation(decision) -> None:
    await _broadcast({
        "type": "escalation",
        "data": {
            "trigger": decision.trigger_signal.title,
            "modules": decision.activate_modules,
            "priority": decision.priority,
            "rationale": decision.rationale,
            "commentary": decision.agent_commentary,
            "ts": decision.ts,
        },
    })


bus.on_signal(_on_signal)
bus.on_escalation(_on_escalation)


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "up", "ts": time.time()}


@app.get("/feed")
def get_feed(limit: int = 50) -> List[dict]:
    """Live analyst feed ('bieżaczka') — agent-written entries."""
    try:
        from src.agent.orchestrator import orchestrator
        return orchestrator.get_feed(limit)
    except Exception:
        return []


@app.get("/signals")
def get_signals(limit: int = 50) -> List[dict]:
    """Recent signals from all sources."""
    signals = bus.recent_signals(limit)
    return [
        {
            "id": s.signal_id, "source": s.source, "domain": s.domain.value,
            "title": s.title, "severity": s.severity.value,
            "value": round(s.value, 4), "context": s.context, "ts": s.ts,
        }
        for s in reversed(signals)
    ]


@app.get("/escalations")
def get_escalations() -> List[dict]:
    return [
        {
            "trigger": e.trigger_signal.title,
            "modules": e.activate_modules,
            "priority": e.priority,
            "rationale": e.rationale,
            "commentary": e.agent_commentary,
            "ts": e.ts,
        }
        for e in bus.recent_escalations(20)
    ]


@app.get("/polling-rates")
def get_polling_rates() -> dict:
    return bus.polling_rates


@app.post("/polling-rates/{source}")
def set_polling_rate(source: str, seconds: int) -> dict:
    bus.set_polling_rate(source, seconds)
    return {"source": source, "new_interval": seconds}


# ── Ingest endpoint (legacy compatibility) ────────────────────────────────────

class IngestPayload(BaseModel):
    ts_event: float
    source: str
    entity_type: str
    entity_id: str
    features: Dict[str, float]
    dq: Dict[str, float] = {}


@app.post("/ingest")
async def ingest(payload: IngestPayload) -> dict:
    raw = RawEvent(
        source=payload.source,
        domain=Domain.CRYPTO,
        entity_id=payload.entity_id,
        payload=payload.features,
        ts=payload.ts_event,
    )
    await bus.publish_raw(raw)
    return {"status": "ok"}


# ── WebSocket live feed ───────────────────────────────────────────────────────

@app.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws_clients.append(websocket)
    logger.info(f"[WS] Client connected. Total: {len(_ws_clients)}")
    try:
        # Send recent signals on connect
        for s in bus.recent_signals(20):
            await websocket.send_text(json.dumps({
                "type": "signal",
                "data": {"title": s.title, "severity": s.severity.value,
                         "source": s.source, "ts": s.ts},
            }))
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        _ws_clients.remove(websocket)
        logger.info(f"[WS] Client disconnected. Total: {len(_ws_clients)}")


# ── Dashboard UI ──────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <title>Vortex Analytica — Live Feed</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0a0a0f; color: #e0e0e0; font-family: 'Courier New', monospace; }
    header { padding: 16px 24px; border-bottom: 1px solid #1e1e2e;
             display: flex; align-items: center; gap: 12px; }
    header h1 { font-size: 18px; color: #7c6af7; letter-spacing: 2px; }
    #status { font-size: 12px; color: #555; margin-left: auto; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e;
           animation: pulse 1.5s infinite; display: inline-block; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
    #feed { padding: 16px 24px; max-height: calc(100vh - 60px); overflow-y: auto; }
    .entry { border-left: 3px solid #333; padding: 8px 12px; margin-bottom: 8px;
             background: #0f0f1a; border-radius: 0 4px 4px 0; }
    .entry.CRITICAL { border-color: #ef4444; }
    .entry.HIGH     { border-color: #f97316; }
    .entry.MEDIUM   { border-color: #eab308; }
    .entry.INFO     { border-color: #3b82f6; }
    .entry.signal   { border-color: #6b7280; opacity: .8; }
    .time   { font-size: 10px; color: #555; }
    .badge  { display: inline-block; padding: 1px 6px; border-radius: 3px;
              font-size: 10px; font-weight: bold; margin-right: 6px; }
    .badge.CRITICAL { background: #7f1d1d; color: #fca5a5; }
    .badge.HIGH     { background: #7c2d12; color: #fed7aa; }
    .badge.MEDIUM   { background: #713f12; color: #fef08a; }
    .badge.INFO     { background: #1e3a5f; color: #93c5fd; }
    .badge.signal   { background: #1f2937; color: #9ca3af; }
    .text { font-size: 13px; line-height: 1.5; margin-top: 2px; }
    .tags { font-size: 10px; color: #4b5563; margin-top: 3px; }
  </style>
</head>
<body>
<header>
  <span class="dot"></span>
  <h1>⚡ VORTEX ANALYTICA</h1>
  <span id="status">Connecting...</span>
</header>
<div id="feed"></div>
<script>
const feed = document.getElementById('feed');
const status = document.getElementById('status');
let count = 0;

function addEntry(sev, text, tags, source) {
  const d = document.createElement('div');
  d.className = `entry ${sev}`;
  const time = new Date().toLocaleTimeString('pl-PL');
  d.innerHTML = `
    <div class="time">${time}</div>
    <span class="badge ${sev}">${sev}</span>
    <span class="text">${text}</span>
    ${tags?.length ? `<div class="tags">${tags.join(' · ')}</div>` : ''}
  `;
  feed.insertBefore(d, feed.firstChild);
  if (feed.children.length > 200) feed.removeChild(feed.lastChild);
  count++;
  status.textContent = `${count} events | ${new Date().toLocaleTimeString()}`;
}

const ws = new WebSocket(`ws://${location.host}/ws/feed`);
ws.onopen = () => { status.textContent = 'Connected'; };
ws.onclose = () => { status.textContent = 'Disconnected — reload'; };

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'signal') {
    const s = msg.data;
    addEntry(s.severity, s.title, [s.source, s.domain], s.source);
  } else if (msg.type === 'escalation') {
    const d = msg.data;
    addEntry('HIGH',
      `🔭 Escalation P${d.priority}: ${d.trigger} → [${d.modules.join(', ')}]`,
      [d.rationale?.slice(0,60)], 'agent'
    );
  } else if (msg.type === 'feed') {
    const f = msg.data;
    addEntry(f.severity, f.text, f.instruments, 'agent');
  }
};
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML
