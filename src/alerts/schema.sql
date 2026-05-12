-- file: src/alerts/schema.sql
CREATE TABLE IF NOT EXISTS signal_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    signal_id TEXT,
    entity_id TEXT,
    val REAL,
    dq_passed INTEGER
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    signal_id TEXT,
    entity_id TEXT,
    dedupe_key TEXT,
    status TEXT,
    severity TEXT,
    confidence REAL,
    evidence_pack TEXT,
    data_issue INTEGER DEFAULT 0,
    created_at REAL,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS drift_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    signal_id TEXT,
    feature TEXT,
    metric TEXT,
    value REAL,
    is_drifting INTEGER
);

CREATE TABLE IF NOT EXISTS alert_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT,
    action TEXT,
    timestamp REAL
);

CREATE TABLE IF NOT EXISTS state_store (
    signal_id TEXT,
    entity_id TEXT,
    first_breach_ts REAL,
    last_alert_ts REAL,
    status TEXT,
    PRIMARY KEY (signal_id, entity_id)
);

CREATE TABLE IF NOT EXISTS feature_store (
    entity_id TEXT,
    feature TEXT,
    value REAL,
    timestamp REAL
);
