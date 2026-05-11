
-- Signal Evaluations: Log every check
CREATE TABLE IF NOT EXISTS signal_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_event TEXT NOT NULL,         -- When the event happened
    ts_processed TEXT NOT NULL,     -- When we processed it
    signal_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    raw_value REAL,
    is_triggered BOOLEAN NOT NULL,
    hysteresis_state TEXT,          -- 'ARMED' (waiting for duration), 'TRIGGERED', 'COOLDOWN'
    data_quality_score REAL,
    dq_passed BOOLEAN NOT NULL,
    features_json TEXT              -- Snapshot of features used
);

-- Alerts: Lifecycle management
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT UNIQUE NOT NULL,  -- UUID or deterministic hash
    dedupe_key TEXT NOT NULL,       -- To prevent duplicates
    signal_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    severity INTEGER NOT NULL,
    status TEXT NOT NULL,           -- 'OPEN', 'RESOLVED'
    opened_at TEXT NOT NULL,
    last_updated_at TEXT NOT NULL,
    resolved_at TEXT,
    evidence_pack_json TEXT,        -- Snapshot of evidence
    drift_warning BOOLEAN DEFAULT 0
);

-- Drift Metrics: Monitoring feature drift
CREATE TABLE IF NOT EXISTS drift_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_calculated TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    metric_name TEXT NOT NULL,      -- 'KS', 'PSI', etc.
    metric_value REAL NOT NULL,
    drift_detected BOOLEAN NOT NULL,
    baseline_window_start TEXT,
    baseline_window_end TEXT
);

-- Alert Outcomes: Feedback loop (optional future use)
CREATE TABLE IF NOT EXISTS alert_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT NOT NULL,
    outcome_type TEXT NOT NULL,     -- 'TP', 'FP'
    ts_observed TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY(alert_id) REFERENCES alerts(alert_id)
);

CREATE INDEX IF NOT EXISTS idx_evals_signal_entity ON signal_evaluations(signal_id, entity_id);
CREATE INDEX IF NOT EXISTS idx_alerts_dedupe ON alerts(dedupe_key, status);
CREATE INDEX IF NOT EXISTS idx_drift_signal ON drift_metrics(signal_id, feature_name);
