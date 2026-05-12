"""Coinalyze regime detection and pattern analysis."""

from __future__ import annotations

import logging
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import pandas as pd

from signalvortex.sources.coinalyze import CoinalyzeClient

LOGGER = logging.getLogger(__name__)

ROLLING_WINDOW = 60  # days
OI_THRESHOLDS = (2.0, 3.0)
RATIO_THRESHOLDS = (2.0, 3.0)
FUTURE_HORIZONS = (3, 7)  # days


@dataclass
class RegimeRecord:
    """Single observation for regime analysis."""

    timestamp: int
    price: float
    oi: float
    ratio: float
    oi_change: Optional[float] = None
    ratio_change: Optional[float] = None
    price_return: Optional[float] = None
    future_returns: Dict[int, Optional[float]] = field(default_factory=dict)
    oi_multiple: Optional[float] = None
    ratio_multiple: Optional[float] = None

    def iso_date(self) -> str:
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc).strftime("%Y-%m-%d")


@dataclass
class RegimeEvent:
    """Detected regime event with future outcomes."""

    date: str
    metric: str  # 'oi' or 'ratio'
    direction: str  # 'up' or 'down'
    multiple: float
    change: float
    future_returns: Dict[int, Optional[float]]


@dataclass
class RegimeAnalysisResult:
    """Results of regime pattern analysis."""

    symbol: str
    sample_count: int
    start_date: str
    end_date: str
    oi_events: Dict[float, List[RegimeEvent]]
    ratio_up_events: Dict[float, List[RegimeEvent]]
    ratio_down_events: Dict[float, List[RegimeEvent]]
    summary: Dict[str, Dict]


def enrich_series(records: List[RegimeRecord]) -> None:
    """Compute changes, multiples, and future returns for records."""
    oi_window: deque[float] = deque(maxlen=ROLLING_WINDOW)
    ratio_window: deque[float] = deque(maxlen=ROLLING_WINDOW)

    for idx, record in enumerate(records):
        if idx == 0:
            continue

        prev = records[idx - 1]
        record.oi_change = (record.oi - prev.oi) / prev.oi if prev.oi else None
        record.ratio_change = record.ratio - prev.ratio
        record.price_return = (record.price - prev.price) / prev.price if prev.price else None

        if oi_window:
            avg = statistics.fmean(oi_window)
            if avg > 0 and record.oi_change is not None:
                record.oi_multiple = abs(record.oi_change) / avg

        if ratio_window:
            avg = statistics.fmean(ratio_window)
            if avg > 0 and record.ratio_change is not None:
                record.ratio_multiple = abs(record.ratio_change) / avg

        if record.oi_change is not None:
            oi_window.append(abs(record.oi_change))
        if record.ratio_change is not None:
            ratio_window.append(abs(record.ratio_change))

    # Compute future returns
    for idx, record in enumerate(records):
        for horizon in FUTURE_HORIZONS:
            target = idx + horizon
            if target < len(records):
                future_price = records[target].price
                record.future_returns[horizon] = (future_price - record.price) / record.price


def select_regime_events(
    records: List[RegimeRecord],
    *,
    metric: str,
    thresholds: Sequence[float],
    direction: str,
) -> Dict[float, List[RegimeEvent]]:
    """Select events where metric exceeds thresholds."""
    events: Dict[float, List[RegimeEvent]] = {thr: [] for thr in thresholds}

    for record in records:
        multiple = record.oi_multiple if metric == "oi" else record.ratio_multiple
        change = record.oi_change if metric == "oi" else record.ratio_change

        if multiple is None or change is None:
            continue

        if direction == "down" and change >= 0:
            continue
        if direction == "up" and change <= 0:
            continue

        for thr in thresholds:
            if multiple >= thr:
                events[thr].append(RegimeEvent(
                    date=record.iso_date(),
                    metric=metric,
                    direction=direction,
                    multiple=multiple,
                    change=change,
                    future_returns=record.future_returns.copy(),
                ))

    return events


def summarize_events(events: Dict[float, List[RegimeEvent]]) -> Dict[str, Dict]:
    """Compute summary statistics for regime events."""
    summary = {}

    for thr, event_list in events.items():
        if not event_list:
            summary[f"{thr}x"] = {"count": 0}
            continue

        stats = {"count": len(event_list)}

        for horizon in FUTURE_HORIZONS:
            returns = [
                e.future_returns.get(horizon)
                for e in event_list
                if e.future_returns.get(horizon) is not None
            ]
            if returns:
                positive_count = sum(1 for r in returns if r > 0)
                stats[f"{horizon}d_avg_return"] = statistics.fmean(returns)
                stats[f"{horizon}d_positive_prob"] = positive_count / len(returns)

        avg_change = statistics.fmean(e.change for e in event_list)
        stats["avg_change"] = avg_change
        summary[f"{thr}x"] = stats

    return summary


def analyze_coinalyze_patterns(
    symbol: str,
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    client: Optional[CoinalyzeClient] = None,
    api_key: Optional[str] = None,
) -> RegimeAnalysisResult:
    """Analyze OI and long/short ratio regimes.

    Args:
        symbol: Market symbol (e.g., 'BTCUSDT_PERP.A').
        start_date: Start of analysis period.
        end_date: End of analysis period.
        client: Optional CoinalyzeClient instance.
        api_key: API key (used if client not provided).

    Returns:
        RegimeAnalysisResult with detected events and statistics.
    """
    if client is None:
        if api_key is None:
            raise ValueError("Either client or api_key must be provided")
        client = CoinalyzeClient(api_key)

    start_date = start_date or datetime(2020, 1, 1, tzinfo=timezone.utc)
    end_date = end_date or datetime.now(timezone.utc)

    df = client.get_combined_dataframe(
        symbol,
        interval="daily",
        start_date=start_date.date(),
        end_date=end_date.date(),
    )

    if df.empty:
        return RegimeAnalysisResult(
            symbol=symbol,
            sample_count=0,
            start_date="",
            end_date="",
            oi_events={},
            ratio_up_events={},
            ratio_down_events={},
            summary={},
        )

    # Convert to RegimeRecords
    records = []
    for _, row in df.iterrows():
        records.append(RegimeRecord(
            timestamp=int(row["timestamp"].timestamp()),
            price=row["price"],
            oi=row["oi"],
            ratio=row["ratio"],
            future_returns={h: None for h in FUTURE_HORIZONS},
        ))

    enrich_series(records)

    oi_events = select_regime_events(records, metric="oi", thresholds=OI_THRESHOLDS, direction="down")
    ratio_up = select_regime_events(records, metric="ratio", thresholds=RATIO_THRESHOLDS, direction="up")
    ratio_down = select_regime_events(records, metric="ratio", thresholds=RATIO_THRESHOLDS, direction="down")

    return RegimeAnalysisResult(
        symbol=symbol,
        sample_count=len(records),
        start_date=records[0].iso_date() if records else "",
        end_date=records[-1].iso_date() if records else "",
        oi_events=oi_events,
        ratio_up_events=ratio_up,
        ratio_down_events=ratio_down,
        summary={
            "oi_collapse": summarize_events(oi_events),
            "ratio_long_bias": summarize_events(ratio_up),
            "ratio_short_bias": summarize_events(ratio_down),
        },
    )
