import pytest
import sqlite3
import json
import os
from src.alerts.engine import SignalEngine

@pytest.fixture
def engine():
    eng = SignalEngine(":memory:")
    # Load signal definitions
    signals_file = os.path.join(os.path.dirname(__file__), "../src/alerts/signals/signals.json")
    with open(signals_file, "r") as f:
        eng.load_signal_defs(json.load(f))
    return eng

def mk_event(ts, eid, feat_name, feat_val, dq=None):
    if not dq: dq = {"timeliness_s": 1, "completeness": 1.0, "consistency": 1.0}
    return {"ts_event": ts, "entity_id": eid, "features": {feat_name: feat_val}, "dq": dq}

@pytest.mark.parametrize("sig_id,feat,val_trigger,val_near,val_exit", [
    ("market_funding_spike_v1", "funding_rate", 0.005, 0.0019, 0.0001),
    ("oi_shock_v1", "oi_change_1h", 0.20, 0.14, 0.01),
    ("news_sentiment_crash_v1", "sentiment_score", -0.90, -0.79, -0.30),
    ("ais_dark_vessel_v1", "time_since_ping", 15000, 14000, 1000),
    ("satellite_buildup_v1", "pixel_delta", 0.30, 0.24, 0.05)
])
class TestSignals:
    
    def test_normal_trigger_and_resolve(self, engine, sig_id, feat, val_trigger, val_near, val_exit):
        sig = engine.signals[sig_id]
        dur = sig["anti_flapping"]["for_duration"]
        
        # Initial enter breach
        engine.evaluate_signal(sig_id, mk_event(1000, "ENT_1", feat, val_trigger))
        
        # Wait until for_duration met
        engine.evaluate_signal(sig_id, mk_event(1000 + dur + 1, "ENT_1", feat, val_trigger))
        
        res = engine.conn.execute("SELECT status, evidence_pack FROM alerts WHERE signal_id=? ORDER BY created_at DESC", (sig_id,)).fetchone()
        assert res is not None, f"Signal {sig_id} failed to trigger"
        assert res["status"] == "OPEN", f"Signal {sig_id} failed to trigger"
        
        # Resolution
        engine.evaluate_signal(sig_id, mk_event(1000 + dur + 10, "ENT_1", feat, val_exit))
        res = engine.conn.execute("SELECT status FROM alerts WHERE signal_id=? ORDER BY updated_at DESC", (sig_id,)).fetchone()
        assert res["status"] == "RESOLVED", f"Signal {sig_id} failed to resolve"

    def test_near_threshold_anti_flapping(self, engine, sig_id, feat, val_trigger, val_near, val_exit):
        sig = engine.signals[sig_id]
        
        # Evaluate near threshold - should not emit OPEN
        engine.evaluate_signal(sig_id, mk_event(2000, "ENT_2", feat, val_near))
        res = engine.conn.execute("SELECT count(*) FROM alerts WHERE signal_id=? AND entity_id=?", (sig_id, "ENT_2")).fetchone()
        assert res[0] == 0, f"Signal {sig_id} flapped on near_threshold"

    def test_dq_failure(self, engine, sig_id, feat, val_trigger, val_near, val_exit):
        # Inject bad DQ payload
        dq_bad = {"timeliness_s": 999999, "completeness": 0.1, "consistency": 0.1}
        engine.evaluate_signal(sig_id, mk_event(3000, "ENT_3", feat, val_trigger, dq_bad))
        
        alerts = engine.conn.execute("SELECT data_issue, alert_id FROM alerts WHERE entity_id=?", ("ENT_3",)).fetchall()
        assert len(alerts) == 1
        assert alerts[0]["data_issue"] == 1
        assert alerts[0]["alert_id"].startswith("DQ_")
