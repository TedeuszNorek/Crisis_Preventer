from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Dict, Any, List
import json
import os
import asyncio
from src.alerts.engine import SignalEngine
import time

app = FastAPI(title="SignalVortex API", description="Production-grade signal engine ingress")

# Initialize Engine
DB_PATH = os.getenv("DB_PATH", "data/alerts.db")
os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

engine = SignalEngine(DB_PATH)
signals_file = os.path.join(os.path.dirname(__file__), "alerts/signals/signals.json")
with open(signals_file, "r") as f:
    engine.load_signal_defs(json.load(f))

class DataQuality(BaseModel):
    timeliness_s: float
    completeness: float
    consistency: float

class EventPayload(BaseModel):
    ts_event: float
    source: str
    entity_type: str
    entity_id: str
    features: Dict[str, float]
    dq: DataQuality

@app.post("/ingest")
async def ingest_event(event: EventPayload):
    """
    Ingests an event and evaluates it against all loaded signals.
    """
    event_dict = event.model_dump()
    for sig_id in engine.signals:
        engine.evaluate_signal(sig_id, event_dict)
    
    alerts = engine.conn.execute("SELECT * FROM alerts WHERE status='OPEN'").fetchall()
    return {"status": "processed", "active_alerts": [dict(a) for a in alerts]}

@app.get("/alerts")
def get_alerts():
    """
    Returns all OPEN alerts.
    """
    alerts = engine.conn.execute("SELECT * FROM alerts WHERE status='OPEN'").fetchall()
    return [dict(a) for a in alerts]

@app.get("/evaluations")
def get_evaluations():
    """
    Returns recent evaluations.
    """
    evals = engine.conn.execute("SELECT * FROM signal_evaluations ORDER BY timestamp DESC LIMIT 20").fetchall()
    return [dict(e) for e in evals]

@app.get("/health")
def health():
    return {"status": "up", "loaded_signals": len(engine.signals)}
