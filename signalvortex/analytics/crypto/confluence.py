"""Multi-timeframe confluence analysis.

Analyzes signals across multiple timeframes (5m, 1h, 4h) to compute
confluence scores and identify high-confidence setups.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from signalvortex.sources.binance.client import BinanceFuturesClient

LOGGER = logging.getLogger(__name__)

# Timeframes to analyze
DEFAULT_TIMEFRAMES = ["5m", "1h", "4h"]

# Signal weights by timeframe (higher TF = more weight)
TIMEFRAME_WEIGHTS = {
    "5m": 0.2,
    "15m": 0.25,
    "1h": 0.35,
    "4h": 0.5,
    "1d": 0.6,
}


@dataclass
class TimeframeSignal:
    """Signal for a single timeframe."""
    timeframe: str
    bias: str  # 'bullish', 'bearish', 'neutral'
    strength: float  # -1 to +1
    
    # Component signals
    oi_signal: float  # -1 to +1
    ls_signal: float  # -1 to +1
    momentum_signal: float  # -1 to +1
    volume_signal: float  # -1 to +1
    
    # Raw data
    oi_change: float
    ls_ratio: float
    price_change: float
    volume_change: float


@dataclass
class ConfluenceResult:
    """Multi-timeframe confluence analysis result."""
    symbol: str
    timeframe_signals: Dict[str, TimeframeSignal]
    confluence_score: float  # -1 to +1
    confluence_strength: str  # 'strong', 'moderate', 'weak', 'mixed'
    overall_bias: str  # 'bullish', 'bearish', 'neutral'
    aligned_timeframes: int
    total_timeframes: int
    interpretation: str


def fetch_timeframe_data(
    symbol: str,
    timeframe: str,
    limit: int = 100,
    client: Optional[BinanceFuturesClient] = None,
) -> pd.DataFrame:
    """Fetch OI, L/S, and price data for a single timeframe."""
    client = client or BinanceFuturesClient()
    
    try:
        klines = client.get_klines(symbol, interval=timeframe, limit=limit)
        
        # Map timeframe to period for OI/LS endpoints
        period_map = {"5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
        period = period_map.get(timeframe, "1h")
        
        oi_df = client.get_open_interest_hist(symbol, period=period, limit=limit)
        ls_df = client.get_long_short_ratio(symbol, period=period, limit=limit)
        
    except Exception as e:
        LOGGER.warning(f"Failed to fetch {timeframe} data for {symbol}: {e}")
        return pd.DataFrame()
    
    if klines.empty:
        return pd.DataFrame()
    
    df = klines.copy()
    df = df.set_index("open_time")
    
    # Merge OI
    if not oi_df.empty:
        oi_df = oi_df.set_index("timestamp")
        df["oi"] = oi_df["sumOpenInterestValue"].reindex(df.index, method="ffill")
    else:
        df["oi"] = np.nan
    
    # Merge L/S ratio
    if not ls_df.empty:
        ls_df = ls_df.set_index("timestamp")
        df["long_ratio"] = ls_df["longAccount"].reindex(df.index, method="ffill")
        df["short_ratio"] = ls_df["shortAccount"].reindex(df.index, method="ffill")
        df["ls_ratio"] = ls_df["longShortRatio"].reindex(df.index, method="ffill")
    else:
        df["long_ratio"] = 0.5
        df["short_ratio"] = 0.5
        df["ls_ratio"] = 1.0
    
    df = df.reset_index()
    
    # Compute changes
    df["price_change"] = df["close"].pct_change()
    df["oi_change"] = df["oi"].pct_change()
    df["volume_change"] = df["volume"].pct_change()
    
    # Compute momentum (rate of change)
    lookback = min(6, len(df) // 4)
    df["momentum"] = df["close"].pct_change(lookback)
    
    return df.dropna()


def compute_timeframe_signal(
    df: pd.DataFrame,
    timeframe: str,
) -> Optional[TimeframeSignal]:
    """Compute signal for a single timeframe from data."""
    if df.empty or len(df) < 5:
        return None
    
    latest = df.iloc[-1]
    recent = df.tail(6)
    
    # 1. OI Signal: Rising OI = confirming trend, Falling OI = exhaustion
    oi_change = latest.get("oi_change", 0)
    price_change = latest.get("price_change", 0)
    
    # OI signal based on OI-price relationship
    if oi_change > 0.02 and price_change > 0:
        oi_signal = 0.8  # Bullish: rising OI + rising price
    elif oi_change > 0.02 and price_change < 0:
        oi_signal = -0.8  # Bearish: rising OI + falling price
    elif oi_change < -0.02 and price_change > 0:
        oi_signal = 0.3  # Weakly bullish: falling OI + rising price (short squeeze)
    elif oi_change < -0.02 and price_change < 0:
        oi_signal = -0.3  # Weakly bearish: falling OI + falling price (long liquidation)
    else:
        oi_signal = 0.0
    
    # 2. L/S Ratio Signal: Contrarian - extreme long = bearish, extreme short = bullish
    ls_ratio = latest.get("ls_ratio", 1.0)
    if ls_ratio > 1.5:
        ls_signal = -0.6  # Too many longs, bearish
    elif ls_ratio > 1.2:
        ls_signal = -0.3
    elif ls_ratio < 0.7:
        ls_signal = 0.6  # Too many shorts, bullish
    elif ls_ratio < 0.85:
        ls_signal = 0.3
    else:
        ls_signal = 0.0
    
    # 3. Momentum Signal: Trend-following
    momentum = latest.get("momentum", 0)
    if momentum > 0.03:
        momentum_signal = 0.8
    elif momentum > 0.01:
        momentum_signal = 0.4
    elif momentum < -0.03:
        momentum_signal = -0.8
    elif momentum < -0.01:
        momentum_signal = -0.4
    else:
        momentum_signal = 0.0
    
    # 4. Volume Signal: Rising volume = confirmation
    volume_change = recent["volume_change"].mean()
    if volume_change > 0.2:
        volume_signal = 0.5 * np.sign(price_change) if price_change != 0 else 0
    else:
        volume_signal = 0.0
    
    # Combine signals
    strength = (
        0.30 * oi_signal +
        0.25 * ls_signal +
        0.30 * momentum_signal +
        0.15 * volume_signal
    )
    
    # Classify bias
    if strength > 0.3:
        bias = "bullish"
    elif strength < -0.3:
        bias = "bearish"
    else:
        bias = "neutral"
    
    return TimeframeSignal(
        timeframe=timeframe,
        bias=bias,
        strength=strength,
        oi_signal=oi_signal,
        ls_signal=ls_signal,
        momentum_signal=momentum_signal,
        volume_signal=volume_signal,
        oi_change=oi_change,
        ls_ratio=ls_ratio,
        price_change=price_change,
        volume_change=volume_change,
    )


def compute_confluence(
    signals: Dict[str, TimeframeSignal],
) -> Tuple[float, str, str, int]:
    """Compute confluence score from multiple timeframe signals.
    
    Returns:
        Tuple of (score, strength, bias, aligned_count)
    """
    if not signals:
        return 0.0, "no_data", "neutral", 0
    
    # Weighted average of signals
    total_weight = 0.0
    weighted_sum = 0.0
    
    for tf, signal in signals.items():
        weight = TIMEFRAME_WEIGHTS.get(tf, 0.3)
        weighted_sum += weight * signal.strength
        total_weight += weight
    
    if total_weight == 0:
        return 0.0, "no_data", "neutral", 0
    
    confluence_score = weighted_sum / total_weight
    
    # Count aligned timeframes
    bullish_count = sum(1 for s in signals.values() if s.bias == "bullish")
    bearish_count = sum(1 for s in signals.values() if s.bias == "bearish")
    total = len(signals)
    
    aligned_count = max(bullish_count, bearish_count)
    
    # Determine overall bias
    if confluence_score > 0.3:
        overall_bias = "bullish"
    elif confluence_score < -0.3:
        overall_bias = "bearish"
    else:
        overall_bias = "neutral"
    
    # Determine confluence strength
    alignment_ratio = aligned_count / total if total > 0 else 0
    
    if alignment_ratio >= 0.8 and abs(confluence_score) > 0.4:
        confluence_strength = "strong"
    elif alignment_ratio >= 0.6 and abs(confluence_score) > 0.2:
        confluence_strength = "moderate"
    elif alignment_ratio >= 0.4:
        confluence_strength = "weak"
    else:
        confluence_strength = "mixed"
    
    return confluence_score, confluence_strength, overall_bias, aligned_count


def analyze_multi_timeframe(
    symbol: str,
    timeframes: Optional[List[str]] = None,
    client: Optional[BinanceFuturesClient] = None,
) -> ConfluenceResult:
    """Analyze symbol across multiple timeframes for confluence.
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT').
        timeframes: List of timeframes to analyze.
        client: Optional BinanceFuturesClient.
    
    Returns:
        ConfluenceResult with all timeframe signals and confluence score.
    """
    timeframes = timeframes or DEFAULT_TIMEFRAMES
    client = client or BinanceFuturesClient()
    
    signals = {}
    
    for tf in timeframes:
        LOGGER.debug(f"Fetching {tf} data for {symbol}...")
        df = fetch_timeframe_data(symbol, tf, limit=100, client=client)
        
        if not df.empty:
            signal = compute_timeframe_signal(df, tf)
            if signal:
                signals[tf] = signal
    
    # Compute confluence
    score, strength, bias, aligned = compute_confluence(signals)
    
    # Generate interpretation
    interpretation = _generate_interpretation(signals, score, strength, bias, aligned, len(timeframes))
    
    return ConfluenceResult(
        symbol=symbol,
        timeframe_signals=signals,
        confluence_score=score,
        confluence_strength=strength,
        overall_bias=bias,
        aligned_timeframes=aligned,
        total_timeframes=len(timeframes),
        interpretation=interpretation,
    )


def _generate_interpretation(
    signals: Dict[str, TimeframeSignal],
    score: float,
    strength: str,
    bias: str,
    aligned: int,
    total: int,
) -> str:
    """Generate human-readable interpretation."""
    if not signals:
        return "⚠️ Insufficient data for multi-timeframe analysis."
    
    tf_summary = []
    for tf, sig in sorted(signals.items(), key=lambda x: TIMEFRAME_WEIGHTS.get(x[0], 0)):
        emoji = "🟢" if sig.bias == "bullish" else "🔴" if sig.bias == "bearish" else "⚪"
        tf_summary.append(f"{tf}:{emoji}")
    
    tf_str = " | ".join(tf_summary)
    
    if strength == "strong":
        action = "High-confidence setup" if bias != "neutral" else "Strong neutrality"
        return f"🎯 {action}: {tf_str} → {bias.upper()} ({score:.2f})"
    elif strength == "moderate":
        return f"📊 Moderate confluence: {tf_str} → {bias.upper()} ({score:.2f})"
    elif strength == "weak":
        return f"📉 Weak confluence: {tf_str} → {bias.upper()} ({score:.2f}). Wait for alignment."
    else:
        return f"⚠️ Mixed signals: {tf_str}. No clear direction. Avoid trading."


def get_confluence_summary(result: ConfluenceResult) -> Dict:
    """Get summary dict for reporting."""
    tf_details = {}
    for tf, sig in result.timeframe_signals.items():
        tf_details[tf] = {
            "bias": sig.bias,
            "strength": round(sig.strength, 3),
            "oi_change": f"{sig.oi_change:.2%}",
            "ls_ratio": round(sig.ls_ratio, 2),
            "momentum": f"{sig.price_change:.2%}",
        }
    
    return {
        "symbol": result.symbol,
        "confluence_score": round(result.confluence_score, 3),
        "confluence_strength": result.confluence_strength,
        "overall_bias": result.overall_bias,
        "aligned_timeframes": f"{result.aligned_timeframes}/{result.total_timeframes}",
        "timeframes": tf_details,
        "interpretation": result.interpretation,
    }
