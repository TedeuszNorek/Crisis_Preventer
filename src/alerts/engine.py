import sqlite3
import json
import uuid
import uuid
from typing import Dict, Any, List
import os

class SignalEngine:
    def __init__(self, db_path: str = "alerts.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        self.signals: Dict[str, dict] = {}

    def _init_db(self):
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r") as f:
            self.conn.executescript(f.read())

    def load_signal_defs(self, defs: List[Dict[str, Any]]):
        for d in defs:
            self.signals[d['signal_id']] = d

    def apply_data_quality_gate(self, signal: dict, dq: dict) -> bool:
        gate = signal.get("data_quality_gate", {})
        if dq.get("timeliness_s", 0) > gate.get("timeliness", float('inf')): return False
        if dq.get("completeness", 0) < gate.get("completeness", 0): return False
        if dq.get("consistency", 0) < gate.get("consistency", 0): return False
        return True

    def calculate_drift_placeholder(self, metric: str, base_vals: List[float], curr_vals: List[float]) -> float:
        # Minimal mock implementation of KS/PSI for demonstration completeness
        if not base_vals or not curr_vals: return 0.0
        return abs(sum(curr_vals)/len(curr_vals) - sum(base_vals)/len(base_vals))

    def update_drift_metrics(self, signal: dict, entity: str, ts: float):
        hooks = signal.get("drift_hooks", {})
        cutoff = ts - hooks.get("baseline_window", 86400)
        for feature in hooks.get("monitored_features", []):
            base = [r[0] for r in self.conn.execute("SELECT value FROM feature_store WHERE entity_id=? AND feature=? AND timestamp < ?", (entity, feature, cutoff)).fetchall()]
            curr = [r[0] for r in self.conn.execute("SELECT value FROM feature_store WHERE entity_id=? AND feature=? AND timestamp >= ?", (entity, feature, cutoff)).fetchall()]
            
            for metric in hooks.get("metrics", []):
                val = self.calculate_drift_placeholder(metric, base, curr)
                is_drift = 1 if val > 0.1 else 0
                self.conn.execute("INSERT INTO drift_metrics (timestamp, signal_id, feature, metric, value, is_drifting) VALUES (?,?,?,?,?,?)", (ts, signal["signal_id"], feature, metric, val, is_drift))

    def apply_anti_flapping(self, signal: dict, entity: str, current_value: float, ts: float) -> str:
        rule = signal['rule']
        af = signal['anti_flapping']
        op = rule['operator']
        
        row = self.conn.execute("SELECT * FROM state_store WHERE signal_id=? AND entity_id=?", (signal['signal_id'], entity)).fetchone()
        if not row:
            self.conn.execute("INSERT INTO state_store (signal_id, entity_id, status) VALUES (?, ?, 'CLOSED')", (signal['signal_id'], entity))
            first_ts, last_alert, status = None, None, 'CLOSED'
        else:
            first_ts, last_alert, status = row['first_breach_ts'], row['last_alert_ts'], row['status']

        is_enter = (current_value > rule['enter_threshold']) if op in ['>', '>='] else (current_value < rule['enter_threshold'])
        is_exit = (current_value < rule['exit_threshold']) if op in ['>', '>='] else (current_value > rule['exit_threshold'])

        if is_enter:
            if first_ts is None:
                first_ts = ts
                self.conn.execute("UPDATE state_store SET first_breach_ts=? WHERE signal_id=? AND entity_id=?", (ts, signal['signal_id'], entity))
            if (ts - first_ts) >= af['for_duration']:
                if last_alert is None or (ts - last_alert) >= af['cooldown']:
                    self.conn.execute("UPDATE state_store SET last_alert_ts=?, status='OPEN' WHERE signal_id=? AND entity_id=?", (ts, signal['signal_id'], entity))
                    return 'OPEN'
        elif is_exit:
            if first_ts is not None:
                self.conn.execute("UPDATE state_store SET first_breach_ts=NULL WHERE signal_id=? AND entity_id=?", (signal['signal_id'], entity))
            if status == 'OPEN':
                self.conn.execute("UPDATE state_store SET status='CLOSED' WHERE signal_id=? AND entity_id=?", (signal['signal_id'], entity))
                return 'RESOLVE'
        
        return 'UPDATE' if status == 'OPEN' else 'NONE'

    def build_evidence_pack(self, signal: dict, event: dict, drift_note: str = None) -> str:
        pack = {k: event["features"].get(k) for k in signal.get("evidence_pack", [])}
        if drift_note: pack["_drift_warning"] = drift_note
        return json.dumps(pack)

    def manage_lifecycle(self, action: str, signal: dict, event: dict, ts: float, is_dq: bool = False):
        entity = event["entity_id"]
        dedupe = signal["dedupe_key"].replace("{entity_id}", entity)
        
        if is_dq:
            alert_id = f"DQ_{dedupe}_{int(ts)}"
            self.conn.execute("INSERT INTO alerts (alert_id, signal_id, entity_id, dedupe_key, status, severity, confidence, evidence_pack, data_issue, created_at, updated_at) VALUES (?,?,?,?,'OPEN','CRITICAL',1.0,?,1,?,?)",
                              (alert_id, signal["signal_id"], entity, dedupe, json.dumps(event.get("dq", {})), ts, ts))
            self.conn.execute("INSERT INTO alert_outcomes (alert_id, action, timestamp) VALUES (?, 'DATA_ISSUE', ?)", (alert_id, ts))
            return
            
        row = self.conn.execute("SELECT alert_id FROM alerts WHERE dedupe_key=? AND status='OPEN'", (dedupe,)).fetchone()
        
        drift = self.conn.execute("SELECT is_drifting FROM drift_metrics WHERE signal_id=? ORDER BY timestamp DESC LIMIT 1", (signal["signal_id"],)).fetchone()
        conf = signal["confidence"]
        drift_note = None

        if drift and drift[0]:
            action_drift = signal["drift_hooks"].get("action_on_drift")
            if action_drift == "pause": return
            elif action_drift == "degrade_mode":
                conf = max(0.0, conf - 0.2)
                drift_note = "Ten sygnał ma obniżoną wiarygodność – data drift detected."
            elif action_drift == "raise_threshold":
                signal['rule']['enter_threshold'] *= 1.5

        evidence = self.build_evidence_pack(signal, event, drift_note)

        if action == 'OPEN':
            if not row:
                alert_id = f"ALT_{uuid.uuid4().hex[:8]}"
                self.conn.execute("INSERT INTO alerts (alert_id, signal_id, entity_id, dedupe_key, status, severity, confidence, evidence_pack, created_at, updated_at) VALUES (?,?,?,?,'OPEN',?,?,?,?,?)", (alert_id, signal["signal_id"], entity, dedupe, signal["severity"], conf, evidence, ts, ts))
                self.conn.execute("INSERT INTO alert_outcomes (alert_id, action, timestamp) VALUES (?, 'OPEN', ?)", (alert_id, ts))
        elif action == 'UPDATE' and row:
            self.conn.execute("UPDATE alerts SET updated_at=?, evidence_pack=? WHERE alert_id=?", (ts, evidence, row[0]))
            self.conn.execute("INSERT INTO alert_outcomes (alert_id, action, timestamp) VALUES (?, 'UPDATE', ?)", (row[0], ts))
        elif action == 'RESOLVE' and row:
            self.conn.execute("UPDATE alerts SET status='RESOLVED', updated_at=? WHERE alert_id=?", (ts, row[0]))
            self.conn.execute("INSERT INTO alert_outcomes (alert_id, action, timestamp) VALUES (?, 'RESOLVE', ?)", (row[0], ts))

    def persist_results(self, signal: dict, event: dict, val: float, dq_passed: bool):
        self.conn.execute("INSERT INTO signal_evaluations (timestamp, signal_id, entity_id, val, dq_passed) VALUES (?,?,?,?,?)",
                          (event.get("ts_event", 0), signal["signal_id"], event["entity_id"], val, int(dq_passed)))

    def evaluate_signal(self, signal_id: str, event: dict):
        signal = self.signals[signal_id]
        ts = event["ts_event"]
        
        for k, v in event.get("features", {}).items():
            self.conn.execute("INSERT INTO feature_store (entity_id, feature, value, timestamp) VALUES (?,?,?,?)", (event["entity_id"], k, v, ts))

        val = event["features"].get(signal["compute"], 0.0)
        dq_pass = self.apply_data_quality_gate(signal, event.get("dq", {}))
        
        self.persist_results(signal, event, val, dq_pass)
        self.update_drift_metrics(signal, event["entity_id"], ts)

        if not dq_pass:
            self.manage_lifecycle("DATA_ISSUE", signal, event, ts, is_dq=True)
        else:
            action = self.apply_anti_flapping(signal, event["entity_id"], val, ts)
            if action in ["OPEN", "UPDATE", "RESOLVE"]:
                self.manage_lifecycle(action, signal, event, ts)
        
        self.conn.commit()
