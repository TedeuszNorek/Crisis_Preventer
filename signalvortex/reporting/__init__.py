"""Reporting helpers for anomaly insights."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

LOGGER = logging.getLogger(__name__)


def _one_liner(row: pd.Series) -> str:
    """Generate hypothesis one-liner for anomaly."""
    option_type = str(row.get("option_type", "")).upper()
    sentiment = row.get("sentiment_score", 0.0)
    ret1d = row.get("ret_1d", 0.0)
    voi = row.get("volume_oi_ratio", 0.0)

    if option_type == "CALL" and row.get("delta_bucket") == "OTM" and sentiment > 1 and abs(ret1d) < 0.01:
        return "possible long vol accumulation ahead of catalyst"
    if option_type == "PUT" and sentiment < -0.5 and ret1d < 0:
        return "hedging or downside positioning pressure"
    if voi >= 1.0:
        return "fresh institutional initiation (volume eclipses open interest)"
    return "idiosyncratic flow; monitor follow-through"


def build_insights(df: pd.DataFrame, max_total: int = 10) -> List[str]:
    """Build human-readable insights from anomaly data.

    Args:
        df: DataFrame with anomaly flags.
        max_total: Maximum number of insights to return.

    Returns:
        List of insight strings.
    """
    if df.empty:
        return []

    flagged = df[df["anomaly_flag"]].copy()
    if flagged.empty:
        return []

    flagged = flagged.sort_values("anomaly_score", ascending=False)
    insights: List[str] = []

    for symbol, bucket in flagged.groupby("symbol"):
        for _, row in bucket.head(3).iterrows():
            polymarket_note = ""
            pm_price = row.get("polymarket_price")
            if pm_price is not None and pm_price == pm_price:
                polymarket_note = f" Polymarket≈{pm_price:.2f}"

            exp_date = row.get("expiration")
            exp_str = exp_date.date() if hasattr(exp_date, "date") else str(exp_date)

            msg = (
                f"Vortex Insight — {symbol}: {row.get('delta_bucket','')} "
                f"{row.get('option_type','')} {exp_str} "
                f"{row.get('strike'):,.2f}; {row.get('explanation')}.{polymarket_note} "
                f"Hypothesis: {_one_liner(row)}."
            )
            insights.append(msg)
            if len(insights) >= max_total:
                return insights

    return insights


def save_outputs(
    df: pd.DataFrame,
    outdir: str = "data",
) -> Tuple[Path, Path]:
    """Save anomaly results to CSV and JSONL files.

    Args:
        df: DataFrame with anomaly data.
        outdir: Output directory.

    Returns:
        Tuple of (csv_path, json_path).
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d")
    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)

    csv_path = out_path / f"anomalies_{timestamp}.csv"
    json_path = out_path / f"anomalies_{timestamp}.jsonl"

    df.to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as fh:
        for _, row in df.iterrows():
            fh.write(json.dumps(row.to_dict(), default=str) + "\n")

    return csv_path, json_path


def send_webhook(
    insights: Iterable[str],
    webhook_url: Optional[str] = None,
) -> bool:
    """Send insights to webhook.

    Args:
        insights: List of insight strings.
        webhook_url: Webhook URL.

    Returns:
        True if successful, False otherwise.
    """
    if not webhook_url:
        LOGGER.warning("No webhook URL configured")
        return False

    payload = {"insights": list(insights)}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as exc:
        LOGGER.warning(f"Webhook delivery failed: {exc}")
        return False
