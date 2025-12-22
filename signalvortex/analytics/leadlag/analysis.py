"""Analyze whether open interest or long/short imbalance leads price moves."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from signalvortex.sources.binance import BinanceFuturesClient

LOGGER = logging.getLogger(__name__)


@dataclass
class Sample:
    """Single observation for lead-lag analysis."""

    timestamp: int
    delta_oi: float
    delta_ratio: float
    future_return: float


@dataclass
class LeadLagResult:
    """Results of lead-lag analysis."""

    oi_correlation: float
    ratio_correlation: float
    oi_top_quartile_return: float
    oi_bottom_quartile_return: float
    ratio_top_quartile_return: float
    ratio_bottom_quartile_return: float
    sample_count: int


def compute_correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Compute Pearson correlation between two sequences.

    Args:
        xs: First sequence.
        ys: Second sequence.

    Returns:
        Pearson correlation coefficient (0.0 if undefined).
    """
    if len(xs) < 2 or len(ys) < 2:
        return 0.0

    x_arr = np.array(xs)
    y_arr = np.array(ys)

    x_mean = np.mean(x_arr)
    y_mean = np.mean(y_arr)

    numerator = np.sum((x_arr - x_mean) * (y_arr - y_mean))
    denominator = np.sqrt(np.sum((x_arr - x_mean) ** 2) * np.sum((y_arr - y_mean) ** 2))

    if denominator == 0:
        return 0.0
    return numerator / denominator


def compute_quartile_returns(
    samples: Sequence[Sample],
    field: str,
) -> tuple[float, float]:
    """Compute average returns for top and bottom quartiles.

    Args:
        samples: List of samples.
        field: Field to use for quartile split ('delta_oi' or 'delta_ratio').

    Returns:
        Tuple of (top_quartile_return, bottom_quartile_return).
    """
    if len(samples) < 4:
        return 0.0, 0.0

    values = [getattr(s, field) for s in samples]
    returns = [s.future_return for s in samples]

    threshold_high = np.percentile(values, 75)
    threshold_low = np.percentile(values, 25)

    top_returns = [r for v, r in zip(values, returns) if v >= threshold_high]
    bottom_returns = [r for v, r in zip(values, returns) if v <= threshold_low]

    top_avg = np.mean(top_returns) if top_returns else 0.0
    bottom_avg = np.mean(bottom_returns) if bottom_returns else 0.0

    return float(top_avg), float(bottom_avg)


def collect_samples(
    client: BinanceFuturesClient,
    symbol: str,
    interval: str = "5m",
    limit: int = 300,
) -> List[Sample]:
    """Collect samples for lead-lag analysis from Binance API.

    Args:
        client: Binance Futures client.
        symbol: Trading pair (e.g., 'BTCUSDT').
        interval: Kline interval.
        limit: Number of samples to collect.

    Returns:
        List of samples with deltas and future returns.
    """
    # Get klines, OI history, and long/short ratio
    klines = client.get_klines(symbol, interval=interval, limit=limit + 1)
    oi_hist = client.get_open_interest_hist(symbol, period=interval, limit=limit)
    ls_ratio = client.get_long_short_ratio(symbol, period=interval, limit=limit)

    if klines.empty or oi_hist.empty or ls_ratio.empty:
        LOGGER.warning(f"Insufficient data for {symbol}")
        return []

    # Merge data on timestamp
    oi_hist = oi_hist.set_index("timestamp")
    ls_ratio = ls_ratio.set_index("timestamp")
    klines = klines.set_index("open_time")

    # Align timestamps
    common_index = oi_hist.index.intersection(ls_ratio.index).intersection(klines.index)
    if len(common_index) < 10:
        LOGGER.warning(f"Not enough aligned data points for {symbol}")
        return []

    samples = []
    sorted_index = sorted(common_index)

    for i in range(len(sorted_index) - 1):
        ts = sorted_index[i]
        next_ts = sorted_index[i + 1]

        try:
            oi_current = oi_hist.loc[ts, "sumOpenInterestValue"]
            oi_prev = oi_hist.loc[sorted_index[i - 1], "sumOpenInterestValue"] if i > 0 else oi_current
            delta_oi = (oi_current - oi_prev) / oi_prev if oi_prev != 0 else 0

            ratio_current = ls_ratio.loc[ts, "longShortRatio"]
            ratio_prev = ls_ratio.loc[sorted_index[i - 1], "longShortRatio"] if i > 0 else ratio_current
            delta_ratio = ratio_current - ratio_prev

            price_current = klines.loc[ts, "close"]
            price_next = klines.loc[next_ts, "close"]
            future_return = (price_next - price_current) / price_current

            samples.append(Sample(
                timestamp=int(ts.timestamp() * 1000),
                delta_oi=float(delta_oi),
                delta_ratio=float(delta_ratio),
                future_return=float(future_return),
            ))
        except (KeyError, ZeroDivisionError):
            continue

    return samples


def analyze_oi_price_leadlag(
    symbol: str,
    interval: str = "5m",
    limit: int = 300,
    client: Optional[BinanceFuturesClient] = None,
) -> LeadLagResult:
    """Analyze whether OI or long/short ratio changes lead price movements.

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT').
        interval: Time interval for analysis.
        limit: Number of data points.
        client: Optional BinanceFuturesClient instance.

    Returns:
        LeadLagResult with correlations and quartile returns.
    """
    if client is None:
        client = BinanceFuturesClient()

    samples = collect_samples(client, symbol, interval, limit)

    if len(samples) < 10:
        LOGGER.warning(f"Insufficient samples for lead-lag analysis: {len(samples)}")
        return LeadLagResult(
            oi_correlation=0.0,
            ratio_correlation=0.0,
            oi_top_quartile_return=0.0,
            oi_bottom_quartile_return=0.0,
            ratio_top_quartile_return=0.0,
            ratio_bottom_quartile_return=0.0,
            sample_count=len(samples),
        )

    oi_corr = compute_correlation(
        [s.delta_oi for s in samples],
        [s.future_return for s in samples],
    )
    ratio_corr = compute_correlation(
        [s.delta_ratio for s in samples],
        [s.future_return for s in samples],
    )

    oi_top, oi_bottom = compute_quartile_returns(samples, "delta_oi")
    ratio_top, ratio_bottom = compute_quartile_returns(samples, "delta_ratio")

    return LeadLagResult(
        oi_correlation=oi_corr,
        ratio_correlation=ratio_corr,
        oi_top_quartile_return=oi_top,
        oi_bottom_quartile_return=oi_bottom,
        ratio_top_quartile_return=ratio_top,
        ratio_bottom_quartile_return=ratio_bottom,
        sample_count=len(samples),
    )
