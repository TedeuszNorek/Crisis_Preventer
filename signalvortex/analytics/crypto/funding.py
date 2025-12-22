"""Funding rate analysis for detecting leverage extremes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from signalvortex.sources.coinalyze.client import CoinalyzeClient

LOGGER = logging.getLogger(__name__)

# Funding rate thresholds (annualized)
FUNDING_EXTREME_HIGH = 0.001  # 0.1% per 8h = ~137% APR (overleveraged longs)
FUNDING_EXTREME_LOW = -0.0005  # -0.05% per 8h (overleveraged shorts)
FUNDING_NEUTRAL_RANGE = (-0.0002, 0.0003)  # Normal range


@dataclass
class FundingSignal:
    """Funding rate signal."""
    timestamp: datetime
    symbol: str
    funding_rate: float
    funding_zscore: float
    signal: str  # 'overleveraged_longs', 'overleveraged_shorts', 'neutral'
    strength: float  # 0-1


@dataclass
class FundingAnalysisResult:
    """Results of funding rate analysis."""
    symbol: str
    current_rate: float
    avg_rate_7d: float
    avg_rate_30d: float
    zscore: float
    signal: str
    extreme_events: List[FundingSignal]
    df: pd.DataFrame


def analyze_funding_rates(
    symbol: str,
    *,
    lookback_days: int = 90,
    client: Optional[CoinalyzeClient] = None,
    api_key: Optional[str] = None,
) -> FundingAnalysisResult:
    """Analyze funding rate patterns and detect extremes.
    
    Args:
        symbol: Market symbol (e.g., 'BTCUSDT_PERP.A').
        lookback_days: Number of days to analyze.
        client: Optional CoinalyzeClient.
        api_key: API key if client not provided.
    
    Returns:
        FundingAnalysisResult with signals and statistics.
    """
    if client is None:
        if api_key is None:
            raise ValueError("Either client or api_key must be provided")
        client = CoinalyzeClient(api_key)
    
    end_ts = int(datetime.now(timezone.utc).timestamp())
    start_ts = end_ts - (lookback_days * 86400)
    
    try:
        funding_data = client.get_funding_rate_history(
            [symbol], interval="daily", start=start_ts, end=end_ts
        )
    except Exception as e:
        LOGGER.error(f"Failed to fetch funding rates for {symbol}: {e}")
        return FundingAnalysisResult(
            symbol=symbol,
            current_rate=0.0,
            avg_rate_7d=0.0,
            avg_rate_30d=0.0,
            zscore=0.0,
            signal="error",
            extreme_events=[],
            df=pd.DataFrame(),
        )
    
    if not funding_data or not funding_data[0].get("history"):
        return FundingAnalysisResult(
            symbol=symbol,
            current_rate=0.0,
            avg_rate_7d=0.0,
            avg_rate_30d=0.0,
            zscore=0.0,
            signal="no_data",
            extreme_events=[],
            df=pd.DataFrame(),
        )
    
    history = funding_data[0]["history"]
    df = pd.DataFrame(history)
    df["timestamp"] = pd.to_datetime(df["t"], unit="s")
    df["funding_rate"] = df["c"].astype(float)
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    # Compute rolling statistics
    df["funding_7d_avg"] = df["funding_rate"].rolling(7, min_periods=1).mean()
    df["funding_30d_avg"] = df["funding_rate"].rolling(30, min_periods=1).mean()
    df["funding_30d_std"] = df["funding_rate"].rolling(30, min_periods=7).std()
    df["funding_zscore"] = (df["funding_rate"] - df["funding_30d_avg"]) / df["funding_30d_std"].clip(lower=1e-6)
    
    # Classify signals using ADAPTIVE z-score thresholds (not static)
    def classify_signal(row) -> str:
        zscore = row["funding_zscore"]
        rate = row["funding_rate"]
        
        # Use z-score for adaptive thresholds
        if zscore > 2.0:  # 2σ above mean = extreme
            return "overleveraged_longs"
        elif zscore < -1.5:  # 1.5σ below mean = extreme shorts
            return "overleveraged_shorts"
        elif -0.5 <= zscore <= 0.5:  # Within 0.5σ = neutral
            return "neutral"
        elif zscore > 0:
            return "slight_long_bias"
        else:
            return "slight_short_bias"
    
    df["signal"] = df.apply(classify_signal, axis=1)
    
    # Find extreme events
    extreme_events = []
    for _, row in df[df["signal"].isin(["overleveraged_longs", "overleveraged_shorts"])].iterrows():
        strength = min(abs(row["funding_zscore"]) / 3, 1.0)  # Normalize to 0-1
        extreme_events.append(FundingSignal(
            timestamp=row["timestamp"].to_pydatetime(),
            symbol=symbol,
            funding_rate=row["funding_rate"],
            funding_zscore=row["funding_zscore"],
            signal=row["signal"],
            strength=strength,
        ))
    
    # Current state
    latest = df.iloc[-1]
    
    return FundingAnalysisResult(
        symbol=symbol,
        current_rate=latest["funding_rate"],
        avg_rate_7d=latest["funding_7d_avg"],
        avg_rate_30d=latest["funding_30d_avg"],
        zscore=latest["funding_zscore"],
        signal=latest["signal"],
        extreme_events=extreme_events[-10:],  # Last 10 extremes
        df=df,
    )


def get_funding_summary(result: FundingAnalysisResult) -> Dict[str, any]:
    """Get a summary dict for reporting."""
    return {
        "symbol": result.symbol,
        "current_funding_rate": f"{result.current_rate:.4%}",
        "avg_7d": f"{result.avg_rate_7d:.4%}",
        "avg_30d": f"{result.avg_rate_30d:.4%}",
        "zscore": round(result.zscore, 2),
        "signal": result.signal,
        "extreme_count_last_90d": len(result.extreme_events),
        "interpretation": _interpret_signal(result),
    }


def _interpret_signal(result: FundingAnalysisResult) -> str:
    """Human-readable interpretation."""
    if result.signal == "overleveraged_longs":
        return "HIGH FUNDING: Longs paying premium. Consider short or wait for correction."
    elif result.signal == "overleveraged_shorts":
        return "NEGATIVE FUNDING: Shorts paying premium. Potential long squeeze setup."
    elif result.signal == "neutral":
        return "NEUTRAL: Market balanced, no clear directional bias from funding."
    elif result.signal == "slight_long_bias":
        return "SLIGHT LONG BIAS: Moderate bullish sentiment in derivatives."
    elif result.signal == "slight_short_bias":
        return "SLIGHT SHORT BIAS: Moderate bearish sentiment in derivatives."
    else:
        return "UNKNOWN: Unable to classify funding regime."
