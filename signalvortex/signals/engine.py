
import json
import sqlite3
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

@dataclass
class SignalResult:
    triggered: bool
    hysteresis_state: str
    dq_passed: bool
    dq_score: float
    raw_value: Optional[float]

class SignalEngine:
    def __init__(self, db_path: str, signals_dir: str):
        self.db_path = db_path
        self.signals = self.load_signal_defs(signals_dir)
        self.init_db()
        
        # In-memory state for hysteresis/debounce (in prod, use Redis)
        # Key: {signal_id}_{entity_id} -> {start_ts: datetime, last_trigger: datetime, state: str}
        self.state_store = {}

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            with open(Path(__file__).parent / "schema.sql") as f:
                conn.executescript(f.read())

    def load_signal_defs(self, signals_dir: str) -> Dict[str, Any]:
        defs = {}
        path = Path(signals_dir)
        if not path.exists():
            return {}
            
        for f in path.glob("*.json"):
            if f.name == "schema.json": continue
            try:
                data = json.loads(f.read_text())
                if isinstance(data, list):
                    for s in data:
                        defs[s["signal_id"]] = s
                else:
                    defs[data["signal_id"]] = data
            except Exception as e:
                LOGGER.error(f"Failed to load {f}: {e}")
        return defs

    def evaluate_signal(self, signal_id: str, event: Dict[str, Any]) -> Optional[str]:
        """Evaluate a signal and return Alert ID if triggered."""
        s_def = self.signals.get(signal_id)
        if not s_def:
            LOGGER.error(f"Unknown signal: {signal_id}")
            return None

        # 1. Data Quality Gate
        passed_dq, dq_score = self.apply_data_quality_gate(s_def, event.get("dq", {}))
        if not passed_dq:
            self._log_evaluation(s_def, event, triggered=False, dq_passed=False, dq_score=dq_score)
            return "DATA_ISSUE"  # In real impl, route to ops

        # 2. Rule Evaluation & Anti-flapping
        triggered, raw_val, hysteresis_state = self.apply_anti_flapping(s_def, event)
        
        self._log_evaluation(s_def, event, triggered, dq_passed=True, dq_score=dq_score, raw_value=raw_val, state=hysteresis_state)

        # 3. Lifecycle Management
        if triggered:
            return self.manage_lifecycle(s_def, event, raw_val)
        
        return None

    def apply_data_quality_gate(self, s_def: Dict[str, Any], dq_metrics: Dict[str, Any]) -> (bool, float):
        gate = s_def["data_quality_gate"]
        
        # Inputs
        t = dq_metrics.get("timeliness_s", 9999)
        c = dq_metrics.get("completeness", 0.0)
        cons = dq_metrics.get("consistency", 0.0)

        # Gate Checks
        if t > gate["min_timeliness_s"]: return False, 0.0
        if c < gate["min_completeness"]: return False, 0.0
        if cons < gate["min_consistency"]: return False, 0.0

        # Simple score
        score = ( (1.0/(t+1)) + c + cons ) / 3.0
        return True, min(score, 1.0)

    def apply_anti_flapping(self, s_def: Dict[str, Any], event: Dict[str, Any]) -> (bool, Optional[float], str):
        rule = s_def["rule"]
        feat_val = event["features"].get(rule["feature"])
        if feat_val is None:
            return False, None, "MISSING_FEATURE"

        key = f"{s_def['signal_id']}_{event['entity_id']}"
        state = self.state_store.get(key, {"state": "IDLE"})
        now = datetime.fromisoformat(event["ts_event"].replace("Z", "+00:00"))

        # Threshold Logic
        enter = s_def["anti_flapping"]["hysteresis"]["enter_threshold"]
        exit_ = s_def["anti_flapping"]["hysteresis"]["exit_threshold"]
        op = rule["operator"]

        # Helper to check condition
        def check(val, threshold, operator):
            if operator == ">": return val > threshold
            if operator == "<": return val < threshold
            if operator == ">=": return val >= threshold
            if operator == "<=": return val <= threshold
            return False

        is_enter = check(feat_val, enter, op)
        is_exit = not check(feat_val, exit_, op) # Inverse of maintaining condition

        # State Machine
        # IDLE -> ARMED (if condition met) -> TRIGGERED (if held for duration) -> COOLDOWN
        
        current_state = state.get("state", "IDLE")
        
        if current_state == "COOLDOWN":
            last_trig = state.get("last_trigger")
            if last_trig and (now - last_trig).total_seconds() < s_def["anti_flapping"]["cooldown_s"]:
                return False, feat_val, "COOLDOWN"
            current_state = "IDLE"

        if current_state == "IDLE":
            if is_enter:
                state = {"state": "ARMED", "start_ts": now}
                self.state_store[key] = state
                return False, feat_val, "ARMED"
            
        elif current_state == "ARMED":
            if is_enter:
                # Check duration
                start = state["start_ts"]
                if (now - start).total_seconds() >= s_def["anti_flapping"]["for_duration_s"]:
                    state = {"state": "TRIGGERED", "last_trigger": now}
                    self.state_store[key] = state
                    return True, feat_val, "TRIGGERED"
                return False, feat_val, "ARMED (WAITING)"
            else:
                # Condition lost before duration met
                self.state_store[key] = {"state": "IDLE"}
                return False, feat_val, "IDLE (RESET)"

        elif current_state == "TRIGGERED":
            # In triggered state, we might want to keep alerting or wait for exit
            # For this simple impl, we go to cooldown immediately after one shot
            # Or we could implement "Active" state. 
            # User req: "No alert state toggling without satisfying all 3 conditions"
            # Let's assume single-shot alert then cooldown.
            state = {"state": "COOLDOWN", "last_trigger": now}
            self.state_store[key] = state
            
        return False, feat_val, current_state

    def manage_lifecycle(self, s_def: Dict[str, Any], event: Dict[str, Any], raw_val: float) -> str:
        # Dedupe key construction
        dedupe_template = s_def["dedupe_key"]
        dedupe_key = dedupe_template.format(**event, signal_id=s_def["signal_id"])
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check for existing open alert
            cursor.execute(
                "SELECT alert_id FROM alerts WHERE dedupe_key = ? AND status = 'OPEN'",
                (dedupe_key,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                cursor.execute(
                    "UPDATE alerts SET last_updated_at = ? WHERE alert_id = ?",
                    (datetime.now().isoformat(), existing[0])
                )
                return existing[0]
            else:
                # Create new
                alert_id = str(uuid.uuid4())
                evidence = self.build_evidence_pack(s_def, event)
                cursor.execute(
                    """INSERT INTO alerts 
                       (alert_id, dedupe_key, signal_id, entity_id, severity, status, opened_at, last_updated_at, evidence_pack_json)
                       VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?)""",
                    (alert_id, dedupe_key, s_def["signal_id"], event["entity_id"], 
                     s_def["severity"], datetime.now().isoformat(), datetime.now().isoformat(), json.dumps(evidence))
                )
                return alert_id

    def build_evidence_pack(self, s_def: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
        pack = {}
        for field in s_def["evidence_pack"]:
            if field in event["features"]:
                pack[field] = event["features"][field]
        return pack

    def _log_evaluation(self, s_def, event, triggered, dq_passed, dq_score, raw_value=None, state=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO signal_evaluations 
                   (ts_event, ts_processed, signal_id, entity_id, raw_value, is_triggered, hysteresis_state, data_quality_score, dq_passed, features_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event["ts_event"], datetime.now().isoformat(), s_def["signal_id"], event["entity_id"],
                 raw_value, triggered, state, dq_score, dq_passed, json.dumps(event.get("features", {})))
            )

    def update_drift_metrics(self):
        # Placeholder for drift computation (hooks)
        pass
