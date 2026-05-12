"""Collect Binance futures leverage metrics across multiple periods.

This module provides functions to fetch open interest and long/short ratios
from Binance public endpoints (no API keys required).
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from signalvortex.sources.binance.client import BinanceFuturesClient

LOGGER = logging.getLogger(__name__)

DEFAULT_PERIODS: tuple[str, ...] = ("5m", "15m", "1h", "4h", "1d")


def ms_to_iso(ms: int) -> str:
    """Convert milliseconds timestamp to ISO format."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def collect_leverage_metrics(
    symbol: str,
    periods: Sequence[str] = DEFAULT_PERIODS,
    limit: int = 50,
    client: Optional[BinanceFuturesClient] = None,
) -> List[Dict[str, Any]]:
    """Collect open interest and long/short ratios across multiple periods.

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT').
        periods: Time periods to collect (default: 5m, 15m, 1h, 4h, 1d).
        limit: Number of observations per period (max 500).
        client: Optional BinanceFuturesClient instance.

    Returns:
        List of metric records with symbol, period, timestamp, metric, value.
    """
    client = client or BinanceFuturesClient()
    rows: List[Dict[str, Any]] = []

    for period in periods:
        try:
            # Open Interest History
            oi_df = client.get_open_interest_hist(symbol, period=period, limit=limit)
            for _, item in oi_df.iterrows():
                ts_iso = item["timestamp"].isoformat() if hasattr(item["timestamp"], "isoformat") else str(item["timestamp"])
                rows.extend([
                    {
                        "symbol": symbol,
                        "period": period,
                        "timestamp": ts_iso,
                        "metric": "open_interest_contracts",
                        "value": float(item["sumOpenInterest"]),
                    },
                    {
                        "symbol": symbol,
                        "period": period,
                        "timestamp": ts_iso,
                        "metric": "open_interest_usdt",
                        "value": float(item["sumOpenInterestValue"]),
                    },
                ])
        except Exception as e:
            LOGGER.warning(f"Failed to get OI history for {symbol} {period}: {e}")

        try:
            # Long/Short Ratio
            ls_df = client.get_long_short_ratio(symbol, period=period, limit=limit)
            for _, item in ls_df.iterrows():
                ts_iso = item["timestamp"].isoformat() if hasattr(item["timestamp"], "isoformat") else str(item["timestamp"])
                rows.extend([
                    {
                        "symbol": symbol,
                        "period": period,
                        "timestamp": ts_iso,
                        "metric": "top_account_long_ratio",
                        "value": float(item["longAccount"]),
                    },
                    {
                        "symbol": symbol,
                        "period": period,
                        "timestamp": ts_iso,
                        "metric": "top_account_short_ratio",
                        "value": float(item["shortAccount"]),
                    },
                    {
                        "symbol": symbol,
                        "period": period,
                        "timestamp": ts_iso,
                        "metric": "top_account_long_short_ratio",
                        "value": float(item["longShortRatio"]),
                    },
                ])
        except Exception as e:
            LOGGER.warning(f"Failed to get L/S ratio for {symbol} {period}: {e}")

    rows.sort(key=lambda row: (row["period"], row["timestamp"], row["metric"]))
    return rows


def write_metrics_csv(
    rows: Iterable[Dict[str, Any]],
    output_path: Optional[str] = None,
) -> None:
    """Write metrics to CSV file or stdout.

    Args:
        rows: Metric records to write.
        output_path: Path to output file (None for stdout).
    """
    fieldnames = ["symbol", "period", "timestamp", "metric", "value"]
    rows_list = list(rows)

    if output_path:
        with open(output_path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows_list)
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_list)


def write_metrics_json(
    rows: Iterable[Dict[str, Any]],
    output_path: Optional[str] = None,
) -> None:
    """Write metrics to JSON file or stdout.

    Args:
        rows: Metric records to write.
        output_path: Path to output file (None for stdout).
    """
    payload = list(rows)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
    else:
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
