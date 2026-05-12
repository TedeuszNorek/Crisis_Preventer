"""Backtest leverage stress strategies using Coinalyze data."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from signalvortex.sources.coinalyze import CoinalyzeClient

LOGGER = logging.getLogger(__name__)


@dataclass
class Bar:
    """Single bar with OHLCV and derivatives data."""

    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    oi: float
    ls_ratio: float
    funding: float
    oi_pct: Optional[float] = None
    oi_z: Optional[float] = None
    volume_z: Optional[float] = None
    funding_z: Optional[float] = None
    ls_delta: Optional[float] = None
    ls_z: Optional[float] = None
    ma20: Optional[float] = None

    def date(self) -> str:
        return datetime.fromtimestamp(self.ts, tz=timezone.utc).strftime("%Y-%m-%d")


@dataclass
class BacktestResult:
    """Results of a backtest strategy."""

    name: str
    trade_count: int
    win_rate: float
    avg_return: float
    best_return: float
    worst_return: float
    total_return: float
    returns: List[float]


def rolling_stats(values: List[float], window: int) -> Optional[tuple[float, float]]:
    """Compute rolling mean and std dev."""
    if len(values) < window:
        return None
    window_vals = values[-window:]
    mean = sum(window_vals) / window
    var = sum((x - mean) ** 2 for x in window_vals) / window
    std = math.sqrt(var) if var > 0 else None
    if std is None or std == 0:
        return mean, 0.0001  # Avoid division by zero
    return mean, std


def load_bars(
    client: CoinalyzeClient,
    symbol: str,
    start_ts: int,
    end_ts: int,
) -> List[Bar]:
    """Load OHLCV, OI, L/S ratio, and funding rate data."""
    try:
        oi_data = client.get_open_interest_history(
            [symbol], interval="daily", start=start_ts, end=end_ts, convert_to_usd=True
        )[0]["history"]
        ls_data = client.get_long_short_ratio_history(
            [symbol], interval="daily", start=start_ts, end=end_ts
        )[0]["history"]
        ohlcv_data = client.get_ohlcv_history(
            [symbol], interval="daily", start=start_ts, end=end_ts
        )[0]["history"]
        funding_data = client.get_funding_rate_history(
            [symbol], interval="daily", start=start_ts, end=end_ts
        )[0]["history"]
    except Exception as e:
        LOGGER.error(f"Failed to load data for {symbol}: {e}")
        return []

    oi_map = {item["t"]: item["c"] for item in oi_data}
    ls_map = {item["t"]: item.get("r") or 0 for item in ls_data}
    funding_map = {item["t"]: item.get("c") or 0 for item in funding_data}

    bars: List[Bar] = []
    for item in ohlcv_data:
        ts = item["t"]
        if ts not in oi_map or ts not in ls_map or ts not in funding_map:
            continue
        bars.append(
            Bar(
                ts=ts,
                open=item["o"],
                high=item["h"],
                low=item["l"],
                close=item["c"],
                volume=item["v"],
                oi=oi_map[ts],
                ls_ratio=ls_map[ts],
                funding=funding_map[ts],
            )
        )
    bars.sort(key=lambda bar: bar.ts)
    return bars


def enrich_features(bars: List[Bar]) -> None:
    """Add derived features to bars."""
    oi_changes: List[float] = []
    volume_vals: List[float] = []
    funding_vals: List[float] = []
    ls_changes: List[float] = []
    closes: List[float] = []

    for idx, bar in enumerate(bars):
        if idx > 0:
            prev = bars[idx - 1]
            if prev.oi:
                bar.oi_pct = (bar.oi - prev.oi) / prev.oi
                oi_changes.append(bar.oi_pct)
            bar.ls_delta = bar.ls_ratio - prev.ls_ratio
            ls_changes.append(bar.ls_delta)

        volume_vals.append(bar.volume)
        funding_vals.append(bar.funding)
        closes.append(bar.close)

        if len(oi_changes) >= 60:
            stats = rolling_stats(oi_changes, 60)
            if stats and bar.oi_pct is not None:
                mean, std = stats
                bar.oi_z = (bar.oi_pct - mean) / std

        if len(volume_vals) >= 20:
            stats = rolling_stats(volume_vals, 20)
            if stats:
                mean, std = stats
                bar.volume_z = (bar.volume - mean) / std

        if len(funding_vals) >= 20:
            stats = rolling_stats(funding_vals, 20)
            if stats:
                mean, std = stats
                bar.funding_z = (bar.funding - mean) / std

        if len(ls_changes) >= 30:
            stats = rolling_stats(ls_changes, 30)
            if stats and bar.ls_delta is not None:
                mean, std = stats
                bar.ls_z = (bar.ls_delta - mean) / std

        if len(closes) >= 20:
            bar.ma20 = sum(closes[-20:]) / 20


def simulate_long_trade(bar_idx: int, bars: List[Bar], tp_pct: float = 0.02, sl_pct: float = 0.01, max_hold: int = 3) -> Optional[float]:
    """Simulate a long trade with take profit and stop loss."""
    entry_idx = bar_idx + 1
    if entry_idx >= len(bars):
        return None

    entry_price = bars[entry_idx].open
    tp = entry_price * (1 + tp_pct)
    sl = entry_price * (1 - sl_pct)
    exit_price = bars[min(entry_idx + max_hold, len(bars) - 1)].close

    for idx in range(entry_idx, min(entry_idx + max_hold, len(bars) - 1) + 1):
        high = bars[idx].high
        low = bars[idx].low
        if high >= tp:
            exit_price = tp
            break
        if low <= sl:
            exit_price = sl
            break

    return (exit_price - entry_price) / entry_price


def simulate_short_trade(bar_idx: int, bars: List[Bar], tp_pct: float = 0.01, sl_pct: float = 0.01, max_hold: int = 7) -> Optional[float]:
    """Simulate a short trade with take profit and stop loss."""
    entry_idx = bar_idx + 1
    if entry_idx >= len(bars):
        return None

    entry_price = bars[entry_idx].open
    tp = entry_price * (1 - tp_pct)
    sl = entry_price * (1 + sl_pct)
    exit_price = bars[min(entry_idx + max_hold, len(bars) - 1)].close

    for idx in range(entry_idx, min(entry_idx + max_hold, len(bars) - 1) + 1):
        high = bars[idx].high
        low = bars[idx].low
        if low <= tp:
            exit_price = tp
            break
        if high >= sl:
            exit_price = sl
            break

    return (entry_price - exit_price) / entry_price


def run_backtest(
    symbol: str,
    start_date: datetime,
    end_date: Optional[datetime] = None,
    client: Optional[CoinalyzeClient] = None,
    api_key: Optional[str] = None,
) -> Dict[str, BacktestResult]:
    """Run leverage stress backtest strategies.

    Strategies:
    - Leverage Flush Bounce: Long after extreme OI collapse with high volume and negative funding
    - Euphoria Fade: Short when crowd is extremely long with rising OI and high funding

    Args:
        symbol: Market symbol (e.g., 'BTCUSDT_PERP.A').
        start_date: Backtest start date.
        end_date: Backtest end date (default: now).
        client: Optional CoinalyzeClient instance.
        api_key: API key (used if client not provided).

    Returns:
        Dict with strategy names as keys and BacktestResult as values.
    """
    if client is None:
        if api_key is None:
            raise ValueError("Either client or api_key must be provided")
        client = CoinalyzeClient(api_key)

    end_date = end_date or datetime.now(timezone.utc)
    start_ts = int(start_date.timestamp())
    end_ts = int(end_date.timestamp())

    bars = load_bars(client, symbol, start_ts, end_ts)
    if not bars:
        LOGGER.warning(f"No data for {symbol}")
        return {}

    enrich_features(bars)

    bounce_returns: List[float] = []
    fade_returns: List[float] = []

    for idx, bar in enumerate(bars):
        # Strategy A: Leverage Flush Bounce (Long)
        if (
            bar.oi_z is not None
            and bar.oi_pct is not None
            and bar.volume_z is not None
            and bar.funding is not None
        ):
            if (
                bar.oi_z <= -2
                and bar.oi_pct <= -0.11
                and bar.volume_z > 1
                and (bar.funding < 0 or (bar.funding_z is not None and bar.funding_z < -1))
            ):
                pnl = simulate_long_trade(idx, bars)
                if pnl is not None:
                    bounce_returns.append(pnl)

        # Strategy B: Euphoria Fade (Short)
        if (
            bar.ls_z is not None
            and bar.oi_z is not None
            and bar.ma20 is not None
            and bar.funding is not None
        ):
            if (
                bar.ls_z >= 2
                and bar.oi_z >= 1
                and bar.close > bar.ma20
                and bar.funding > 0.0005
            ):
                pnl = simulate_short_trade(idx, bars)
                if pnl is not None:
                    fade_returns.append(pnl)

    def create_result(name: str, returns: List[float]) -> BacktestResult:
        if not returns:
            return BacktestResult(
                name=name,
                trade_count=0,
                win_rate=0.0,
                avg_return=0.0,
                best_return=0.0,
                worst_return=0.0,
                total_return=0.0,
                returns=[],
            )
        wins = sum(1 for r in returns if r > 0)
        return BacktestResult(
            name=name,
            trade_count=len(returns),
            win_rate=wins / len(returns),
            avg_return=sum(returns) / len(returns),
            best_return=max(returns),
            worst_return=min(returns),
            total_return=sum(returns),
            returns=returns,
        )

    return {
        "leverage_flush_bounce": create_result("Leverage Flush Bounce (Long)", bounce_returns),
        "euphoria_fade": create_result("Euphoria Fade (Short)", fade_returns),
    }
