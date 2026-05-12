"""Liquidation cascade detector.

Combines OI, Funding Rate, and Price momentum to predict cascade liquidations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from signalvortex.sources.binance.client import BinanceFuturesClient
from signalvortex.sources.coinalyze.client import CoinalyzeClient

LOGGER = logging.getLogger(__name__)

# Risk thresholds
OI_SPIKE_THRESHOLD = 0.10  # 10% OI increase = high leverage buildup
FUNDING_EXTREME_THRESHOLD = 0.0008  # 0.08% per 8h = overleveraged
PRICE_MOMENTUM_THRESHOLD = 0.03  # 3% move
CASCADE_RISK_THRESHOLD = 0.6  # 60% risk score = warning


@dataclass
class CascadeRiskSignal:
    """Liquidation cascade risk signal."""
    timestamp: datetime
    symbol: str
    risk_score: float  # 0-1
    risk_level: str  # 'low', 'medium', 'high', 'extreme'
    oi_factor: float
    funding_factor: float
    momentum_factor: float
    direction: str  # 'long_cascade' or 'short_cascade'
    interpretation: str


@dataclass
class LiquidationAnalysisResult:
    """Results of liquidation cascade analysis."""
    symbol: str
    current_risk: CascadeRiskSignal
    historical_signals: List[CascadeRiskSignal]
    oi_change_24h: float
    funding_rate: float
    price_change_24h: float
    df: pd.DataFrame


def fetch_cascade_data(
    symbol: str,
    interval: str = "1h",
    limit: int = 168,  # 7 days
    binance_client: Optional[BinanceFuturesClient] = None,
) -> pd.DataFrame:
    """Fetch OI, price, and calculate metrics for cascade analysis.
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT').
        interval: Time interval.
        limit: Number of data points.
        binance_client: Optional BinanceFuturesClient.
    
    Returns:
        DataFrame with OI, price, and derived metrics.
    """
    client = binance_client or BinanceFuturesClient()
    
    try:
        # Fetch klines for price
        klines_df = client.get_klines(symbol, interval=interval, limit=limit)
        
        # Fetch OI history
        period = interval if interval in ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"] else "1h"
        oi_df = client.get_open_interest_hist(symbol, period=period, limit=limit)
        
        # Fetch L/S ratio
        ls_df = client.get_long_short_ratio(symbol, period=period, limit=limit)
        
    except Exception as e:
        LOGGER.error(f"Failed to fetch cascade data for {symbol}: {e}")
        return pd.DataFrame()
    
    if klines_df.empty or oi_df.empty:
        return pd.DataFrame()
    
    # Merge datasets
    df = klines_df.copy()
    df = df.set_index("open_time")
    
    oi_df = oi_df.set_index("timestamp")
    df["oi"] = oi_df["sumOpenInterestValue"].reindex(df.index, method="ffill")
    
    if not ls_df.empty:
        ls_df = ls_df.set_index("timestamp")
        df["long_ratio"] = ls_df["longAccount"].reindex(df.index, method="ffill")
        df["short_ratio"] = ls_df["shortAccount"].reindex(df.index, method="ffill")
    
    df = df.reset_index()
    
    # Compute derived metrics
    df["oi_change"] = df["oi"].pct_change()
    df["oi_change_24h"] = df["oi"].pct_change(24)  # Assuming 1h interval
    df["price_change"] = df["close"].pct_change()
    df["price_change_24h"] = df["close"].pct_change(24)
    df["price_momentum"] = df["close"].pct_change(6)  # 6h momentum
    
    # Volatility
    df["volatility"] = df["price_change"].rolling(24).std()
    
    # OI z-score
    df["oi_mean"] = df["oi_change"].rolling(72).mean()
    df["oi_std"] = df["oi_change"].rolling(72).std()
    df["oi_zscore"] = (df["oi_change"] - df["oi_mean"]) / df["oi_std"].clip(lower=1e-6)
    
    return df.dropna()


def compute_cascade_risk(
    row: pd.Series,
    funding_rate: float = 0.0,
) -> CascadeRiskSignal:
    """Compute cascade risk score for a single observation.
    
    Args:
        row: DataFrame row with OI, price metrics.
        funding_rate: Current funding rate.
    
    Returns:
        CascadeRiskSignal with risk assessment.
    """
    timestamp = row.get("open_time", datetime.now(timezone.utc))
    if hasattr(timestamp, "to_pydatetime"):
        timestamp = timestamp.to_pydatetime()
    
    # Factor 1: OI buildup - use z-score instead of static threshold
    oi_zscore = row.get("oi_zscore", 0)
    oi_factor = min(abs(oi_zscore) / 3, 1.0)  # 3σ = max risk
    
    # Factor 2: Funding rate - use relative magnitude  
    funding_abs = abs(funding_rate)
    # Adaptive: compare to typical funding (0.01% = neutral, 0.1% = extreme)
    funding_factor = min(funding_abs / 0.001, 1.0)
    
    # Factor 3: Price momentum - use z-score logic
    price_momentum = row.get("price_momentum", 0)
    volatility = row.get("volatility", 0.01)
    momentum_zscore = price_momentum / max(volatility, 0.005)  # Normalize by volatility
    momentum_factor = min(abs(momentum_zscore) / 3, 1.0)
    
    # Determine direction
    long_ratio = row.get("long_ratio", 0.5)
    if long_ratio > 0.55 or funding_rate > 0:
        # Crowd is long, risk of long cascade (price drop)
        direction = "long_cascade"
        # Higher risk if momentum is negative (moving against longs)
        if price_momentum < 0:
            momentum_factor *= 1.5
    else:
        # Crowd is short, risk of short cascade (price spike)
        direction = "short_cascade"
        if price_momentum > 0:
            momentum_factor *= 1.5
    
    # Combined risk score (weighted)
    risk_score = min(
        0.4 * oi_factor + 0.35 * funding_factor + 0.25 * momentum_factor,
        1.0
    )
    
    # Risk level classification
    if risk_score >= 0.8:
        risk_level = "extreme"
    elif risk_score >= 0.6:
        risk_level = "high"
    elif risk_score >= 0.4:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    # Interpretation
    interpretation = _generate_interpretation(
        risk_level, direction, oi_factor, funding_factor, momentum_factor
    )
    
    return CascadeRiskSignal(
        timestamp=timestamp,
        symbol=row.get("symbol", "UNKNOWN"),
        risk_score=risk_score,
        risk_level=risk_level,
        oi_factor=oi_factor,
        funding_factor=funding_factor,
        momentum_factor=momentum_factor,
        direction=direction,
        interpretation=interpretation,
    )


def _generate_interpretation(
    risk_level: str,
    direction: str,
    oi_factor: float,
    funding_factor: float,
    momentum_factor: float,
) -> str:
    """Generate human-readable interpretation."""
    if risk_level == "extreme":
        return f"🚨 EXTREME RISK: {direction.replace('_', ' ').upper()} imminent. High OI buildup + extreme funding."
    elif risk_level == "high":
        return f"⚠️ HIGH RISK: {direction.replace('_', ' ').title()} likely. Consider reducing exposure."
    elif risk_level == "medium":
        if funding_factor > 0.5:
            return f"📊 MEDIUM RISK: Elevated funding rate suggests positioning imbalance."
        elif oi_factor > 0.5:
            return f"📊 MEDIUM RISK: OI buildup indicates leveraged positioning."
        else:
            return f"📊 MEDIUM RISK: Monitor for cascade triggers."
    else:
        return "✅ LOW RISK: No significant cascade risk detected."


def analyze_liquidation_risk(
    symbol: str,
    *,
    interval: str = "1h",
    limit: int = 168,
    funding_rate: Optional[float] = None,
    binance_client: Optional[BinanceFuturesClient] = None,
    coinalyze_client: Optional[CoinalyzeClient] = None,
    coinalyze_api_key: Optional[str] = None,
) -> LiquidationAnalysisResult:
    """Analyze liquidation cascade risk for a symbol.
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT').
        interval: Time interval.
        limit: Number of data points.
        funding_rate: Current funding rate (if known).
        binance_client: Optional BinanceFuturesClient.
        coinalyze_client: Optional CoinalyzeClient for funding data.
        coinalyze_api_key: API key for Coinalyze if client not provided.
    
    Returns:
        LiquidationAnalysisResult with current and historical risk signals.
    """
    binance_client = binance_client or BinanceFuturesClient()
    
    # Fetch main data
    df = fetch_cascade_data(symbol, interval, limit, binance_client)
    
    if df.empty:
        return LiquidationAnalysisResult(
            symbol=symbol,
            current_risk=CascadeRiskSignal(
                timestamp=datetime.now(timezone.utc),
                symbol=symbol,
                risk_score=0.0,
                risk_level="unknown",
                oi_factor=0.0,
                funding_factor=0.0,
                momentum_factor=0.0,
                direction="unknown",
                interpretation="Insufficient data for analysis.",
            ),
            historical_signals=[],
            oi_change_24h=0.0,
            funding_rate=0.0,
            price_change_24h=0.0,
            df=pd.DataFrame(),
        )
    
    # Try to get funding rate from Coinalyze if not provided
    if funding_rate is None and (coinalyze_client or coinalyze_api_key):
        try:
            if coinalyze_client is None:
                coinalyze_client = CoinalyzeClient(coinalyze_api_key)
            
            coinalyze_symbol = f"{symbol}_PERP.A"
            end_ts = int(datetime.now(timezone.utc).timestamp())
            start_ts = end_ts - 86400  # Last 24h
            
            funding_data = coinalyze_client.get_funding_rate_history(
                [coinalyze_symbol], interval="daily", start=start_ts, end=end_ts
            )
            
            if funding_data and funding_data[0].get("history"):
                funding_rate = funding_data[0]["history"][-1].get("c", 0)
        except Exception as e:
            LOGGER.warning(f"Could not fetch funding rate: {e}")
            funding_rate = 0.0
    
    funding_rate = funding_rate or 0.0
    
    # Add symbol to df for processing
    df["symbol"] = symbol
    
    # Compute current risk
    latest_row = df.iloc[-1]
    current_risk = compute_cascade_risk(latest_row, funding_rate)
    
    # Compute historical signals (last 24)
    historical_signals = []
    for _, row in df.tail(24).iterrows():
        signal = compute_cascade_risk(row, funding_rate)
        if signal.risk_level in ["high", "extreme"]:
            historical_signals.append(signal)
    
    return LiquidationAnalysisResult(
        symbol=symbol,
        current_risk=current_risk,
        historical_signals=historical_signals,
        oi_change_24h=latest_row.get("oi_change_24h", 0),
        funding_rate=funding_rate,
        price_change_24h=latest_row.get("price_change_24h", 0),
        df=df,
    )


def get_liquidation_summary(result: LiquidationAnalysisResult) -> Dict:
    """Get summary dict for reporting."""
    return {
        "symbol": result.symbol,
        "risk_score": round(result.current_risk.risk_score, 3),
        "risk_level": result.current_risk.risk_level,
        "direction": result.current_risk.direction,
        "factors": {
            "oi_factor": round(result.current_risk.oi_factor, 3),
            "funding_factor": round(result.current_risk.funding_factor, 3),
            "momentum_factor": round(result.current_risk.momentum_factor, 3),
        },
        "oi_change_24h": f"{result.oi_change_24h:.2%}",
        "funding_rate": f"{result.funding_rate:.4%}",
        "price_change_24h": f"{result.price_change_24h:.2%}",
        "high_risk_signals_24h": len(result.historical_signals),
        "interpretation": result.current_risk.interpretation,
    }
