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


async def _on_incident(incident) -> None:
    await _broadcast({"type": "incident", "data": incident.to_dict()})


bus.on_signal(_on_signal)
bus.on_escalation(_on_escalation)
bus.on_incident(_on_incident)


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


@app.get("/incidents")
def get_incidents(limit: int = 20) -> List[dict]:
    """Incidents assembled by the agent — each represents one focused intelligence picture."""
    try:
        from src.agent.orchestrator import orchestrator
        return orchestrator.get_incidents(limit)
    except Exception:
        return []


@app.get("/incidents/current")
def get_current_incident() -> dict:
    """Most recent active incident (the one shown in the lens)."""
    try:
        from src.agent.orchestrator import orchestrator
        incidents = orchestrator.get_incidents(1)
        return incidents[0] if incidents else {}
    except Exception:
        return {}


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
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Vortex Analytica</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#07070f;color:#e0e0e0;font-family:'Courier New',monospace;height:100vh;display:flex;flex-direction:column;overflow:hidden}
    header{padding:10px 20px;border-bottom:1px solid #1a1a2e;display:flex;align-items:center;gap:12px;flex-shrink:0}
    h1{font-size:15px;color:#7c6af7;letter-spacing:3px}
    #status{font-size:11px;color:#4b5563;margin-left:auto}
    .dot{width:7px;height:7px;border-radius:50%;background:#22c55e;animation:blink 1.5s infinite;display:inline-block}
    /* Lens */
    #lens{display:none;height:52vh;flex-shrink:0;border-bottom:1px solid #1a1a2e;position:relative}
    #lens.active{display:flex}
    #map-panel{flex:0 0 44%;background:#08080f}
    #map{width:100%;height:100%}
    #card{flex:1;padding:14px 18px;overflow-y:auto;background:#0a0a14;display:flex;flex-direction:column;gap:10px}
    #card-header{display:flex;align-items:flex-start;gap:8px}
    .sv{font-size:10px;font-weight:bold;padding:2px 7px;border-radius:3px;flex-shrink:0;margin-top:2px}
    #card-title{font-size:13px;color:#e5e7eb;line-height:1.5;flex:1}
    #close-btn{background:none;border:none;color:#374151;cursor:pointer;font-size:17px;padding:0 4px;flex-shrink:0}
    #close-btn:hover{color:#9ca3af}
    #card-commentary{font-size:12px;color:#d1d5db;line-height:1.6;padding:9px 11px;background:#0e0e1a;border-radius:3px;border-left:3px solid #7c6af7}
    .section-lbl{font-size:9px;color:#374151;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
    #watch{display:flex;flex-wrap:wrap;gap:5px}
    .itag{font-size:10px;padding:2px 7px;background:#12122a;border:1px solid #2d2d5e;border-radius:3px;color:#a5b4fc}
    #timeline{display:flex;flex-direction:column;gap:3px}
    .tl{display:flex;gap:8px;font-size:10px;align-items:baseline}
    .tl-t{color:#374151;flex-shrink:0;width:38px}
    .tl-s{color:#6d5fd4;flex-shrink:0;width:68px;overflow:hidden}
    .tl-x{color:#6b7280}
    /* Pending badge */
    #pending{display:none;position:absolute;top:10px;right:18px;background:#7f1d1d;color:#fca5a5;border:1px solid #ef4444;font-size:10px;font-weight:bold;padding:4px 10px;border-radius:3px;cursor:pointer;animation:blink .9s infinite;z-index:999}
    #pending.show{display:block}
    /* Feed */
    #feed-wrap{flex:1;overflow-y:auto;padding:8px 18px}
    .entry{border-left:3px solid #1a1a2e;padding:5px 10px;margin-bottom:5px;background:#0c0c16;border-radius:0 3px 3px 0}
    .entry.CRITICAL{border-color:#ef4444}
    .entry.HIGH{border-color:#f97316}
    .entry.MEDIUM{border-color:#eab308}
    .entry.INFO{border-color:#3b82f6}
    .entry.signal{border-color:#1f2937;opacity:.75}
    .e-top{display:flex;gap:7px;align-items:center;margin-bottom:1px}
    .e-time{font-size:9px;color:#374151}
    .badge{font-size:9px;font-weight:bold;padding:1px 5px;border-radius:2px}
    .badge.CRITICAL{background:#7f1d1d;color:#fca5a5}
    .badge.HIGH{background:#7c2d12;color:#fed7aa}
    .badge.MEDIUM{background:#713f12;color:#fef08a}
    .badge.INFO{background:#1e3a5f;color:#93c5fd}
    .badge.signal{background:#1a1a2e;color:#4b5563}
    .e-text{font-size:11px;color:#d1d5db;line-height:1.4}
    .e-tags{font-size:9px;color:#2d3748;margin-top:1px}
    @keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
    .leaflet-container{background:#07070f}
  </style>
</head>
<body>
<header>
  <span class="dot"></span>
  <h1>VORTEX ANALYTICA</h1>
  <span id="status">Connecting…</span>
</header>

<div id="lens">
  <div id="map-panel"><div id="map"></div></div>
  <div id="card">
    <div id="card-header">
      <span id="sev-badge" class="sv"></span>
      <span id="card-title"></span>
      <button id="close-btn" onclick="closeLens()">×</button>
    </div>
    <div id="card-commentary"></div>
    <div>
      <div class="section-lbl">Instruments to watch</div>
      <div id="watch"></div>
    </div>
    <div>
      <div class="section-lbl">Timeline</div>
      <div id="timeline"></div>
    </div>
  </div>
  <div id="pending" onclick="switchPending()">NEW CRITICAL ↑</div>
</div>

<div id="feed-wrap"><div id="feed"></div></div>

<script>
const C={CRITICAL:'#ef4444',HIGH:'#f97316',MEDIUM:'#eab308',INFO:'#3b82f6'};
const BG={CRITICAL:'#7f1d1d',HIGH:'#7c2d12',MEDIUM:'#713f12',INFO:'#1e3a5f'};
const FG={CRITICAL:'#fca5a5',HIGH:'#fed7aa',MEDIUM:'#fef08a',INFO:'#93c5fd'};
const ZONES={
  hormuz:       {lat:26.5, lng:56.5, label:'Strait of Hormuz'},
  suez_port:    {lat:30.0, lng:32.5, label:'Suez Canal'},
  malacca:      {lat:1.5,  lng:103.8,label:'Strait of Malacca'},
  taiwan_strait:{lat:24.0, lng:119.5,label:'Taiwan Strait'},
  black_sea:    {lat:43.0, lng:34.0, label:'Black Sea'},
  odessa_port:  {lat:46.5, lng:30.7, label:'Odessa'},
  novorossiysk: {lat:44.7, lng:37.8, label:'Novorossiysk'},
  gdansk_port:  {lat:54.4, lng:18.7, label:'Gdańsk'},
  ukraine_wheat:{lat:49.0, lng:32.0, label:'Ukraine (wheat)'},
};

let map=null, zoneMarker=null, activeInc=null, pendingInc=null, evCount=0;

function initMap(){
  map=L.map('map',{zoomControl:false,attributionControl:false}).setView([20,15],2);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{maxZoom:10}).addTo(map);
}

function pulseIcon(color){
  return L.divIcon({
    html:`<div style="width:18px;height:18px;border-radius:50%;background:${color};animation:ripple 1.4s infinite;opacity:.9"></div>
          <style>@keyframes ripple{0%{box-shadow:0 0 0 0 ${color}88}70%{box-shadow:0 0 0 14px transparent}100%{box-shadow:0 0 0 0 transparent}}</style>`,
    iconSize:[18,18],iconAnchor:[9,9],className:''
  });
}

function openLens(inc){
  activeInc=inc; pendingInc=null;
  document.getElementById('pending').classList.remove('show');
  const sev=inc.severity;
  const badge=document.getElementById('sev-badge');
  badge.textContent=sev; badge.style.background=BG[sev]||'#1a1a2e'; badge.style.color=FG[sev]||'#9ca3af';
  document.getElementById('card-title').textContent=inc.title;
  document.getElementById('card-commentary').textContent=inc.commentary;
  document.getElementById('watch').innerHTML=(inc.instruments||[]).map(i=>`<span class="itag">${i}</span>`).join('');
  document.getElementById('timeline').innerHTML=(inc.timeline||[]).map(t=>{
    const d=new Date(t.ts*1000);
    const hm=d.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'});
    return `<div class="tl"><span class="tl-t">${hm}</span><span class="tl-s">${t.source}</span><span class="tl-x">${(t.title||'').slice(0,90)}</span></div>`;
  }).join('');
  const lens=document.getElementById('lens');
  lens.classList.add('active');
  if(!map){initMap();}
  setTimeout(()=>map.invalidateSize(),60);
  if(zoneMarker){map.removeLayer(zoneMarker);zoneMarker=null;}
  const z=ZONES[inc.zone];
  if(z){
    map.flyTo([z.lat,z.lng],6,{duration:1.5});
    zoneMarker=L.marker([z.lat,z.lng],{icon:pulseIcon(C[sev]||'#7c6af7')}).addTo(map)
               .bindPopup(`<b>${z.label}</b><br/>${sev}`).openPopup();
  } else {
    map.flyTo([20,15],2,{duration:1});
  }
}

function closeLens(){
  document.getElementById('lens').classList.remove('active');
  if(zoneMarker&&map){map.removeLayer(zoneMarker);zoneMarker=null;}
  activeInc=null; pendingInc=null;
  document.getElementById('pending').classList.remove('show');
}

function switchPending(){if(pendingInc)openLens(pendingInc);}

function addEntry(sev,text,tags){
  const feed=document.getElementById('feed');
  const el=document.createElement('div');
  el.className=`entry ${sev}`;
  const t=new Date().toLocaleTimeString('en-GB');
  el.innerHTML=`<div class="e-top"><span class="e-time">${t}</span><span class="badge ${sev}">${sev}</span></div>
    <div class="e-text">${text}</div>
    ${tags?.length?`<div class="e-tags">${tags.join(' · ')}</div>`:''}`;
  feed.insertBefore(el,feed.firstChild);
  if(feed.children.length>300)feed.removeChild(feed.lastChild);
  evCount++;
  document.getElementById('status').textContent=`${evCount} events · ${new Date().toLocaleTimeString('en-GB')}`;
}

const ws=new WebSocket(`ws://${location.host}/ws/feed`);
ws.onopen=()=>{document.getElementById('status').textContent='Live';};
ws.onclose=()=>{document.getElementById('status').textContent='Disconnected — reload';};
ws.onmessage=(e)=>{
  const msg=JSON.parse(e.data);
  if(msg.type==='signal'){
    const s=msg.data;
    addEntry(s.severity,s.title,[s.source,s.domain]);
  } else if(msg.type==='escalation'){
    const d=msg.data;
    addEntry('HIGH',`Escalation: ${d.trigger} → [${d.modules.join(', ')}]`,[d.rationale?.slice(0,60)]);
  } else if(msg.type==='feed'){
    const f=msg.data;
    addEntry(f.severity,f.text,f.instruments);
  } else if(msg.type==='incident'){
    const inc=msg.data;
    if(['HIGH','CRITICAL'].includes(inc.severity)){
      if(activeInc) document.getElementById('pending').classList.add('show'), pendingInc=inc;
      else openLens(inc);
    }
    addEntry(inc.severity,`\u{1F52D} ${inc.title}`,inc.instruments);
  }
};
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML
