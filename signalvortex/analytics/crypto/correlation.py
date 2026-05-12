"""Cross-asset correlation matrix analysis.

Detects regime shifts through correlation breakdowns between crypto assets
and macro indicators.
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

# Thresholds
CORRELATION_BREAKDOWN_THRESHOLD = 0.15  # 15% drop in correlation = significant
ROLLING_WINDOW_SHORT = 24  # 24 periods for short-term correlation
ROLLING_WINDOW_LONG = 168  # 168 periods (7 days at 1h) for baseline


@dataclass
class CorrelationBreakdown:
    """Detected correlation breakdown event."""
    timestamp: datetime
    pair: Tuple[str, str]
    baseline_correlation: float
    current_correlation: float
    change: float
    severity: str  # 'minor', 'moderate', 'severe'


@dataclass
class CorrelationMatrixResult:
    """Results of cross-asset correlation analysis."""
    symbols: List[str]
    current_matrix: pd.DataFrame
    baseline_matrix: pd.DataFrame
    breakdowns: List[CorrelationBreakdown]
    regime: str  # 'correlated', 'decorrelating', 'divergent'
    returns_df: pd.DataFrame


def fetch_multi_asset_data(
    symbols: List[str],
    interval: str = "1h",
    limit: int = 500,
    client: Optional[BinanceFuturesClient] = None,
) -> pd.DataFrame:
    """Fetch OHLCV data for multiple symbols and align timestamps.
    
    Args:
        symbols: List of trading pairs (e.g., ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']).
        interval: Time interval.
        limit: Number of data points.
        client: Optional BinanceFuturesClient.
    
    Returns:
        DataFrame with aligned close prices for all symbols.
    """
    client = client or BinanceFuturesClient()
    
    dfs = {}
    for symbol in symbols:
        try:
            df = client.get_klines(symbol, interval=interval, limit=limit)
            if not df.empty:
                df = df.set_index("open_time")[["close"]].rename(columns={"close": symbol})
                dfs[symbol] = df
        except Exception as e:
            LOGGER.warning(f"Failed to fetch data for {symbol}: {e}")
    
    if not dfs:
        return pd.DataFrame()
    
    # Merge all DataFrames on timestamp
    combined = pd.concat(dfs.values(), axis=1, join="inner")
    return combined


def compute_returns(prices_df: pd.DataFrame) -> pd.DataFrame:
    """Compute log returns from prices."""
    return np.log(prices_df / prices_df.shift(1)).dropna()


def compute_correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
    """Compute correlation matrix from returns."""
    return returns_df.corr()


def compute_rolling_correlation(
    returns_df: pd.DataFrame,
    window: int,
) -> Dict[Tuple[str, str], pd.Series]:
    """Compute rolling correlations for all pairs."""
    correlations = {}
    symbols = returns_df.columns.tolist()
    
    for i, sym1 in enumerate(symbols):
        for sym2 in symbols[i+1:]:
            pair = (sym1, sym2)
            correlations[pair] = returns_df[sym1].rolling(window).corr(returns_df[sym2])
    
    return correlations


def detect_breakdowns(
    rolling_short: Dict[Tuple[str, str], pd.Series],
    rolling_long: Dict[Tuple[str, str], pd.Series],
    threshold: float = CORRELATION_BREAKDOWN_THRESHOLD,
) -> List[CorrelationBreakdown]:
    """Detect correlation breakdowns where short-term diverges from baseline."""
    breakdowns = []
    
    for pair in rolling_short.keys():
        short_corr = rolling_short[pair].iloc[-1] if not rolling_short[pair].empty else np.nan
        long_corr = rolling_long[pair].iloc[-1] if not rolling_long[pair].empty else np.nan
        
        if pd.isna(short_corr) or pd.isna(long_corr):
            continue
        
        change = short_corr - long_corr
        
        if abs(change) >= threshold:
            severity = "minor"
            if abs(change) >= threshold * 2:
                severity = "moderate"
            if abs(change) >= threshold * 3:
                severity = "severe"
            
            breakdowns.append(CorrelationBreakdown(
                timestamp=datetime.now(timezone.utc),
                pair=pair,
                baseline_correlation=long_corr,
                current_correlation=short_corr,
                change=change,
                severity=severity,
            ))
    
    return breakdowns


def classify_regime(
    current_matrix: pd.DataFrame,
    baseline_matrix: pd.DataFrame,
    breakdowns: List[CorrelationBreakdown],
) -> str:
    """Classify current correlation regime."""
    if not breakdowns:
        avg_corr = current_matrix.values[np.triu_indices_from(current_matrix.values, k=1)].mean()
        if avg_corr > 0.7:
            return "highly_correlated"
        elif avg_corr > 0.4:
            return "moderately_correlated"
        else:
            return "low_correlation"
    
    severe_count = sum(1 for b in breakdowns if b.severity == "severe")
    moderate_count = sum(1 for b in breakdowns if b.severity == "moderate")
    
    if severe_count >= 2 or (severe_count >= 1 and moderate_count >= 2):
        return "regime_shift"
    elif severe_count >= 1 or moderate_count >= 2:
        return "decorrelating"
    else:
        return "minor_divergence"


def analyze_cross_asset_correlation(
    symbols: List[str],
    *,
    interval: str = "1h",
    limit: int = 500,
    client: Optional[BinanceFuturesClient] = None,
) -> CorrelationMatrixResult:
    """Analyze cross-asset correlations and detect regime shifts.
    
    Args:
        symbols: List of trading pairs (e.g., ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']).
        interval: Time interval.
        limit: Number of data points.
        client: Optional BinanceFuturesClient.
    
    Returns:
        CorrelationMatrixResult with matrices, breakdowns, and regime classification.
    """
    client = client or BinanceFuturesClient()
    
    # Fetch and prepare data
    prices_df = fetch_multi_asset_data(symbols, interval, limit, client)
    
    if prices_df.empty or len(prices_df) < ROLLING_WINDOW_LONG:
        return CorrelationMatrixResult(
            symbols=symbols,
            current_matrix=pd.DataFrame(),
            baseline_matrix=pd.DataFrame(),
            breakdowns=[],
            regime="insufficient_data",
            returns_df=pd.DataFrame(),
        )
    
    returns_df = compute_returns(prices_df)
    
    # Compute correlation matrices
    current_matrix = compute_correlation_matrix(returns_df.tail(ROLLING_WINDOW_SHORT))
    baseline_matrix = compute_correlation_matrix(returns_df)
    
    # Rolling correlations
    rolling_short = compute_rolling_correlation(returns_df, ROLLING_WINDOW_SHORT)
    rolling_long = compute_rolling_correlation(returns_df, ROLLING_WINDOW_LONG)
    
    # Detect breakdowns
    breakdowns = detect_breakdowns(rolling_short, rolling_long)
    
    # Classify regime
    regime = classify_regime(current_matrix, baseline_matrix, breakdowns)
    
    return CorrelationMatrixResult(
        symbols=symbols,
        current_matrix=current_matrix,
        baseline_matrix=baseline_matrix,
        breakdowns=breakdowns,
        regime=regime,
        returns_df=returns_df,
    )


def get_correlation_summary(result: CorrelationMatrixResult) -> Dict:
    """Get summary dict for reporting."""
    breakdown_list = []
    for b in result.breakdowns:
        breakdown_list.append({
            "pair": f"{b.pair[0]}-{b.pair[1]}",
            "baseline": round(b.baseline_correlation, 3),
            "current": round(b.current_correlation, 3),
            "change": round(b.change, 3),
            "severity": b.severity,
        })
    
    # Extract key correlations
    key_correlations = {}
    if not result.current_matrix.empty:
        symbols = result.current_matrix.columns.tolist()
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i+1:]:
                key_correlations[f"{sym1}-{sym2}"] = round(result.current_matrix.loc[sym1, sym2], 3)
    
    return {
        "symbols": result.symbols,
        "regime": result.regime,
        "current_correlations": key_correlations,
        "breakdowns": breakdown_list,
        "interpretation": _interpret_regime(result),
    }


def _interpret_regime(result: CorrelationMatrixResult) -> str:
    """Human-readable interpretation."""
    regime = result.regime
    
    if regime == "regime_shift":
        return "⚠️ REGIME SHIFT: Major correlation breakdown detected. Risk models may need recalibration."
    elif regime == "decorrelating":
        return "📉 DECORRELATING: Assets diverging from historical patterns. Monitor for opportunities."
    elif regime == "highly_correlated":
        return "📊 HIGH CORRELATION: Assets moving together. Diversification limited."
    elif regime == "moderately_correlated":
        return "📈 MODERATE CORRELATION: Normal market conditions."
    elif regime == "low_correlation":
        return "🔀 LOW CORRELATION: Assets moving independently. Good diversification."
    else:
        return "ℹ️ Insufficient data for regime classification."
