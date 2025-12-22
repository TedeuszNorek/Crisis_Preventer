"""Helpers for downloading Binance futures metrics from the public archive."""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Generator, List, Optional
import xml.etree.ElementTree as ET

import requests

LOGGER = logging.getLogger(__name__)

S3_BASE = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
METRICS_PREFIX = "data/futures/um/daily/metrics"


@dataclass(frozen=True)
class DailyMetric:
    """Daily metrics from Binance futures archive."""

    date: date
    open_interest: float
    open_interest_value: float
    top_trader_account_ratio: float
    top_trader_position_ratio: float
    taker_volume_ratio: float


def _iter_s3_keys(prefix: str) -> Generator[str, None, None]:
    """Yield object keys under the given prefix from the Binance S3 bucket."""
    marker: Optional[str] = None
    while True:
        params: Dict[str, str] = {"delimiter": "/", "prefix": prefix}
        if marker:
            params["marker"] = marker

        resp = requests.get(S3_BASE, params=params, timeout=60)
        resp.raise_for_status()

        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        root = ET.fromstring(resp.content)
        keys = [
            node.text
            for node in root.findall("s3:Contents/s3:Key", ns)
            if node.text is not None
        ]

        for key in keys:
            if key.endswith("/"):
                continue
            yield key

        truncated = root.find("s3:IsTruncated", ns)
        if truncated is not None and truncated.text != "true":
            break

        next_marker = root.find("s3:NextMarker", ns)
        if next_marker is not None and next_marker.text:
            marker = next_marker.text
        elif keys:
            marker = keys[-1]
        else:
            break


def _download_zip(key: str) -> zipfile.ZipFile:
    """Download and open a ZIP file from S3."""
    url = f"{S3_BASE}/{key}"
    resp = requests.get(url, timeout=120)
    if resp.status_code == 404:
        raise FileNotFoundError(key)
    resp.raise_for_status()
    return zipfile.ZipFile(io.BytesIO(resp.content))


def _to_float(raw: Optional[str]) -> Optional[float]:
    """Safely convert string to float."""
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _download_metric(key: str) -> DailyMetric:
    """Download and parse a single metrics file."""
    last_row: Optional[Dict[str, str]] = None
    with _download_zip(key) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as fh:
            reader = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8"))
            for last_row in reader:
                pass

    if not last_row:
        raise ValueError(f"Empty metrics file for {key}")

    timestamp = datetime.strptime(last_row["create_time"], "%Y-%m-%d %H:%M:%S")
    oi = _to_float(last_row.get("sum_open_interest"))
    top_account_ratio = _to_float(last_row.get("count_toptrader_long_short_ratio"))

    if oi is None or top_account_ratio is None:
        raise ValueError(f"Incomplete metrics in {key}")

    return DailyMetric(
        date=timestamp.date(),
        open_interest=oi,
        open_interest_value=_to_float(last_row.get("sum_open_interest_value")) or 0.0,
        top_trader_account_ratio=top_account_ratio,
        top_trader_position_ratio=_to_float(last_row.get("sum_toptrader_long_short_ratio")) or 0.0,
        taker_volume_ratio=_to_float(last_row.get("sum_taker_long_short_vol_ratio")) or 0.0,
    )


def load_daily_metrics(
    symbol: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> List[DailyMetric]:
    """Load daily metrics from Binance archive.

    Args:
        symbol: Futures symbol (e.g., 'BTCUSDT').
        start: Optional start date filter.
        end: Optional end date filter.

    Returns:
        List of DailyMetric objects sorted by date.
    """
    prefix = f"{METRICS_PREFIX}/{symbol}/"
    metrics: List[DailyMetric] = []

    for key in _iter_s3_keys(prefix):
        if not key.endswith(".zip") or key.endswith(".zip.CHECKSUM"):
            continue

        filename = key.split("/")[-1]
        token = f"{symbol}-metrics-"
        if token not in filename:
            continue

        date_str = filename.replace(token, "").replace(".zip", "")
        try:
            key_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        if start and key_date < start:
            continue
        if end and key_date > end:
            continue

        try:
            metric = _download_metric(key)
            metrics.append(metric)
            LOGGER.debug(f"Loaded metrics for {symbol} on {key_date}")
        except (FileNotFoundError, ValueError) as e:
            LOGGER.warning(f"Failed to load {key}: {e}")
            continue

    metrics.sort(key=lambda item: item.date)
    return metrics
