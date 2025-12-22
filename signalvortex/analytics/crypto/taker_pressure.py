"""Taker buy/sell pressure analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

from signalvortex.sources.binance.client import BinanceFuturesClient

LOGGER = logging.getLogger(__name__)

# Thresholds
PRESSURE_EXTREME_THRESHOLD = 1.5  # 60/40 buy/sell split
DIVERGENCE_THRESHOLD = 0.02  # 2% price move


@dataclass
class TakerPressureSignal:
    """Taker pressure signal."""
    timestamp: datetime
    buy_sell_ratio: float
    price_change: float
    signal_type: str  # 'momentum_confirmation', 'bearish_divergence', 'bullish_divergence'
    strength: float


@dataclass
class TakerPressureResult:
    """Results of taker pressure analysis."""
    symbol: str
    current_ratio: float
    avg_ratio_1h: float
    avg_ratio_4h: float
    pressure_zscore: float
    current_signal: str
    divergences: List[TakerPressureSignal]
    df: pd.DataFrame


def analyze_taker_pressure(
    symbol: str,
    *,
    interval: str = "5m",
    limit: int = 500,
    client: Optional[BinanceFuturesClient] = None,
) -> TakerPressureResult:
    """Analyze taker buy/sell volume pressure.
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT').
        interval: Time interval.
        limit: Number of data points.
        client: Optional BinanceFuturesClient.
    
    Returns:
        TakerPressureResult with analysis.
    """
    client = client or BinanceFuturesClient()
    
    try:
        taker_df = client.get_taker_buy_sell_volume(symbol, period=interval, limit=limit)
        klines_df = client.get_klines(symbol, interval=interval, limit=limit)
    except Exception as e:
        LOGGER.error(f"Failed to fetch taker data for {symbol}: {e}")
        return TakerPressureResult(
            symbol=symbol,
            current_ratio=1.0,
            avg_ratio_1h=1.0,
            avg_ratio_4h=1.0,
            pressure_zscore=0.0,
            current_signal="error",
            divergences=[],
            df=pd.DataFrame(),
        )
    
    if taker_df.empty or klines_df.empty:
        return TakerPressureResult(
            symbol=symbol,
            current_ratio=1.0,
            avg_ratio_1h=1.0,
            avg_ratio_4h=1.0,
            pressure_zscore=0.0,
            current_signal="no_data",
            divergences=[],
            df=pd.DataFrame(),
        )
    
    # Merge datasets
    df = taker_df.copy()
    df["close"] = klines_df["close"].values[:len(df)] if len(klines_df) >= len(df) else np.nan
    df["price_change"] = df["close"].pct_change()
    
    # Compute rolling statistics
    periods_1h = max(1, 60 // _interval_to_minutes(interval))
    periods_4h = max(1, 240 // _interval_to_minutes(interval))
    
    df["ratio_1h_avg"] = df["buySellRatio"].rolling(periods_1h, min_periods=1).mean()
    df["ratio_4h_avg"] = df["buySellRatio"].rolling(periods_4h, min_periods=1).mean()
    df["ratio_std"] = df["buySellRatio"].rolling(periods_4h, min_periods=periods_1h).std()
    df["ratio_zscore"] = (df["buySellRatio"] - df["ratio_4h_avg"]) / df["ratio_std"].clip(lower=0.01)
    
    # Detect divergences
    divergences = []
    for i in range(periods_1h, len(df)):
        row = df.iloc[i]
        ratio = row["buySellRatio"]
        price_chg = row["price_change"]
        
        if pd.isna(price_chg):
            continue
        
        signal_type = None
        
        # Use z-score for adaptive thresholds instead of static PRESSURE_EXTREME_THRESHOLD
        zscore = row["ratio_zscore"]
        
        # Bearish divergence: price up but sellers dominant (z < -1.5)
        if price_chg > 0.01 and zscore < -1.5:
            signal_type = "bearish_divergence"
        # Bullish divergence: price down but buyers dominant (z > 1.5)
        elif price_chg < -0.01 and zscore > 1.5:
            signal_type = "bullish_divergence"
        # Momentum confirmation: price and pressure aligned at extremes
        elif price_chg > 0.01 and zscore > 1.5:
            signal_type = "momentum_confirmation"
        elif price_chg < -0.01 and zscore < -1.5:
            signal_type = "momentum_confirmation"
        
        if signal_type:
            divergences.append(TakerPressureSignal(
                timestamp=row["timestamp"].to_pydatetime() if hasattr(row["timestamp"], "to_pydatetime") else row["timestamp"],
                buy_sell_ratio=ratio,
                price_change=price_chg,
                signal_type=signal_type,
                strength=min(abs(zscore) / 2, 1.0),
            ))
    
    # Current state
    latest = df.iloc[-1]
    current_signal = _classify_pressure(latest["buySellRatio"], latest.get("price_change", 0))
    
    return TakerPressureResult(
        symbol=symbol,
        current_ratio=latest["buySellRatio"],
        avg_ratio_1h=latest["ratio_1h_avg"],
        avg_ratio_4h=latest["ratio_4h_avg"],
        pressure_zscore=latest["ratio_zscore"] if pd.notna(latest["ratio_zscore"]) else 0.0,
        current_signal=current_signal,
        divergences=divergences[-20:],  # Last 20 signals
        df=df,
    )


def _interval_to_minutes(interval: str) -> int:
    """Convert interval string to minutes."""
    mapping = {
        "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
        "1h": 60, "2h": 120, "4h": 240, "6h": 360, "12h": 720, "1d": 1440,
    }
    return mapping.get(interval, 5)


def _classify_pressure(ratio: float, price_change: float, zscore: float = 0.0) -> str:
    """Classify current pressure state using z-score."""
    # Use z-score for adaptive classification
    if zscore > 1.5:  # 1.5σ above mean = extreme buyers
        if price_change > 0:
            return "strong_buy_momentum"
        else:
            return "buy_pressure_accumulation"
    elif zscore < -1.5:  # 1.5σ below mean = extreme sellers
        if price_change < 0:
            return "strong_sell_momentum"
        else:
            return "sell_pressure_accumulation"
    else:
        return "balanced"


def get_pressure_summary(result: TakerPressureResult) -> Dict[str, any]:
    """Get summary dict for reporting."""
    divergence_counts = {}
    for d in result.divergences:
        divergence_counts[d.signal_type] = divergence_counts.get(d.signal_type, 0) + 1
    
    return {
        "symbol": result.symbol,
        "current_buy_sell_ratio": round(result.current_ratio, 3),
        "avg_1h": round(result.avg_ratio_1h, 3),
        "avg_4h": round(result.avg_ratio_4h, 3),
        "zscore": round(result.pressure_zscore, 2),
        "signal": result.current_signal,
        "divergences": divergence_counts,
        "interpretation": _interpret_pressure(result),
    }


def _interpret_pressure(result: TakerPressureResult) -> str:
    """Human-readable interpretation."""
    ratio = result.current_ratio
    signal = result.current_signal
    
    if signal == "strong_buy_momentum":
        return f"BULLISH: Aggressive buying (ratio {ratio:.2f}). Trend likely to continue."
    elif signal == "buy_pressure_accumulation":
        return f"ACCUMULATION: Buyers active despite price weakness. Potential reversal setup."
    elif signal == "strong_sell_momentum":
        return f"BEARISH: Aggressive selling (ratio {ratio:.2f}). Trend likely to continue."
    elif signal == "sell_pressure_accumulation":
        return f"DISTRIBUTION: Sellers active despite price strength. Potential top forming."
    else:
        return "BALANCED: No clear directional bias from taker flow."
