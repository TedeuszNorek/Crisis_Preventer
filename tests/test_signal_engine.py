
import pytest
import sqlite3
import os
import json
from datetime import datetime
from signalvortex.signals.engine import SignalEngine

# Mock Signal Definition (Override loading for isolation)
MOCK_SIGNAL = {
    "signal_id": "TEST_SIGNAL",
    "rule": {
        "feature": "val",
        "operator": ">",
        "base_threshold": 100
    },
    "anti_flapping": {
        "hysteresis": { "enter_threshold": 100, "exit_threshold": 50 },
        "for_duration_s": 0,
        "cooldown_s": 60
    },
    "data_quality_gate": {
        "min_timeliness_s": 10,
        "min_completeness": 0.9,
        "min_consistency": 0.9
    },
    "dedupe_key": "{signal_id}_{entity_id}",
    "severity": 3,
    "evidence_pack": ["val"]
}

@pytest.fixture
def engine(tmp_path):
    db_path = tmp_path / "signals.db"
    signals_dir = tmp_path / "signals"
    signals_dir.mkdir()
    
    # Save mock signal
    (signals_dir / "test.json").write_text(json.dumps(MOCK_SIGNAL))
    
    eng = SignalEngine(str(db_path), str(signals_dir))
    return eng

def test_normal_trigger(engine):
    event = {
        "ts_event": datetime.now().isoformat(),
        "entity_id": "TEST_ENTITY",
        "features": {"val": 150},
        "dq": {"timeliness_s": 1, "completeness": 1.0, "consistency": 1.0}
    }
    
    alert_id = engine.evaluate_signal("TEST_SIGNAL", event)
    assert alert_id is not None
    assert "DATA_ISSUE" not in alert_id

    # Check DB
    with sqlite3.connect(engine.db_path) as conn:
        row = conn.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()
        assert row is not None
        assert row[3] == "TEST_SIGNAL" # signal_id column

def test_near_threshold_no_flap(engine):
    # Threshold is 100. Value: 99. Should NOT trigger.
    event = {
        "ts_event": datetime.now().isoformat(),
        "entity_id": "TEST_ENTITY",
        "features": {"val": 99},
        "dq": {"timeliness_s": 1, "completeness": 1.0, "consistency": 1.0}
    }
    
    alert_id = engine.evaluate_signal("TEST_SIGNAL", event)
    assert alert_id is None

def test_data_quality_failure(engine):
    # Value is high enough (150 > 100), but DQ is bad (completeness 0.5 < 0.9)
    event = {
        "ts_event": datetime.now().isoformat(),
        "entity_id": "TEST_ENTITY",
        "features": {"val": 150},
        "dq": {"timeliness_s": 1, "completeness": 0.5, "consistency": 1.0}
    }
    
    alert_id = engine.evaluate_signal("TEST_SIGNAL", event)
    assert alert_id == "DATA_ISSUE"

def test_hysteresis_duration(engine, tmp_path):
    # Update signal to have duration 60s
    MOCK_SIGNAL["anti_flapping"]["for_duration_s"] = 60
    signals_dir = tmp_path / "signals_h"
    signals_dir.mkdir()
    (signals_dir / "test.json").write_text(json.dumps(MOCK_SIGNAL))
    
    eng = SignalEngine(str(tmp_path/"db_h.db"), str(signals_dir))
    
    # 1. First event: Enter threshold -> ARMED
    ts1 = datetime(2023, 1, 1, 12, 0, 0)
    event1 = {
        "ts_event": ts1.isoformat(),
        "entity_id": "E1",
        "features": {"val": 150},
        "dq": {"timeliness_s": 1, "completeness": 1.0, "consistency": 1.0}
    }
    assert eng.evaluate_signal("TEST_SIGNAL", event1) is None # ARMED, not triggered
    
    # 2. Second event: 30s later -> Still ARMED
    ts2 = datetime(2023, 1, 1, 12, 0, 30)
    event2 = {**event1, "ts_event": ts2.isoformat()}
    assert eng.evaluate_signal("TEST_SIGNAL", event2) is None
    
    # 3. Third event: 61s later -> TRIGGERED
    ts3 = datetime(2023, 1, 1, 12, 1, 1)
    event3 = {**event1, "ts_event": ts3.isoformat()}
    alert_id = eng.evaluate_signal("TEST_SIGNAL", event3)
    assert alert_id is not None
