"""Anomaly detection using IsolationForest and heuristics."""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


ANOMALY_FEATURES = [
    "unusual_volume",
    "volume_oi_ratio",
    "iv_zscore",
    "moneyness",
    "sentiment_score",
    "ret_1d",
    "vol_of_underlying",
]


def _run_isolation_forest(df: pd.DataFrame) -> pd.Series:
    """Run IsolationForest anomaly detection."""
    model = IsolationForest(
        contamination=0.02,
        n_estimators=400,
        random_state=7,
        n_jobs=-1,
    )
    features = df[ANOMALY_FEATURES].fillna(0.0)
    model.fit(features)
    anomaly_score = -model.decision_function(features)
    flags = model.predict(features) == -1
    df["ml_anomaly_score"] = anomaly_score
    return pd.Series(flags, index=df.index)


def _heuristic_flags(df: pd.DataFrame) -> pd.Series:
    """Apply rule-based heuristics for anomaly detection."""
    otm = df["delta_bucket"].str.upper() == "OTM"
    rule_volume = (df["unusual_volume"] >= 5) & (df["volume_oi_ratio"] >= 0.7) & otm
    rule_iv = (df["iv_zscore"].abs() >= 2.5) & (df["ret_1d"].abs() < 0.01)
    return rule_volume | rule_iv


def _build_explanation(row: pd.Series) -> str:
    """Build human-readable explanation for anomaly."""
    candidates = {
        "vol": row.get("unusual_volume"),
        "voi": row.get("volume_oi_ratio"),
        "ivz": row.get("iv_zscore"),
        "sent": row.get("sentiment_score"),
        "ret1d": row.get("ret_1d"),
    }
    parts = []
    for key, value in sorted(
        candidates.items(),
        key=lambda item: abs(item[1]) if item[1] is not None else 0,
        reverse=True,
    ):
        if value is None or np.isnan(value):
            continue
        if key == "vol":
            parts.append(f"unusualVol x{value:.1f}")
        elif key == "voi":
            parts.append(f"V/OI {value:.2f}")
        elif key == "ivz":
            parts.append(f"IV z {value:.2f}")
        elif key == "sent":
            parts.append(f"sent z {value:.2f}")
        elif key == "ret1d":
            parts.append(f"Δ1d {value:.2%}")
        if len(parts) >= 3:
            break
    return ", ".join(parts)


def flag_anomalies(df: pd.DataFrame, method: str = "hybrid") -> pd.DataFrame:
    """Flag anomalies in option data.

    Args:
        df: DataFrame with option features.
        method: Detection method - 'heuristic', 'ml', or 'hybrid'.

    Returns:
        DataFrame with anomaly_flag, anomaly_score, and explanation columns.
    """
    if df.empty:
        return df

    df = df.copy()
    method = method.lower()
    heuristics = _heuristic_flags(df)
    ml_flags = pd.Series(False, index=df.index)

    if method in {"ml", "hybrid"}:
        try:
            ml_flags = _run_isolation_forest(df)
        except ValueError:
            ml_flags = pd.Series(False, index=df.index)

    if method == "heuristic":
        df["anomaly_flag"] = heuristics
        df["anomaly_score"] = np.where(heuristics, 1.0, 0.0)
    elif method == "ml":
        df["anomaly_flag"] = ml_flags
        df["anomaly_score"] = df.get("ml_anomaly_score", 0.0)
    else:
        combined = heuristics | ml_flags
        df["anomaly_flag"] = combined
        df["anomaly_score"] = np.where(combined, df.get("ml_anomaly_score", 1.0), 0.0)

    df["explanation"] = df.apply(
        lambda row: _build_explanation(row) if row.get("anomaly_flag") else "",
        axis=1,
    )
    return df
