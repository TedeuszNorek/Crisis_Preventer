"""Crypto analytics module."""

from signalvortex.analytics.crypto.funding import (
    analyze_funding_rates,
    get_funding_summary,
    FundingAnalysisResult,
    FundingSignal,
)
from signalvortex.analytics.crypto.taker_pressure import (
    analyze_taker_pressure,
    get_pressure_summary,
    TakerPressureResult,
    TakerPressureSignal,
)
from signalvortex.analytics.crypto.correlation import (
    analyze_cross_asset_correlation,
    get_correlation_summary,
    CorrelationMatrixResult,
    CorrelationBreakdown,
)
from signalvortex.analytics.crypto.liquidation import (
    analyze_liquidation_risk,
    get_liquidation_summary,
    LiquidationAnalysisResult,
    CascadeRiskSignal,
)
from signalvortex.analytics.crypto.confluence import (
    analyze_multi_timeframe,
    get_confluence_summary,
    ConfluenceResult,
    TimeframeSignal,
)

__all__ = [
    # Funding
    "analyze_funding_rates",
    "get_funding_summary",
    "FundingAnalysisResult",
    "FundingSignal",
    # Taker Pressure
    "analyze_taker_pressure",
    "get_pressure_summary",
    "TakerPressureResult",
    "TakerPressureSignal",
    # Correlation
    "analyze_cross_asset_correlation",
    "get_correlation_summary",
    "CorrelationMatrixResult",
    "CorrelationBreakdown",
    # Liquidation
    "analyze_liquidation_risk",
    "get_liquidation_summary",
    "LiquidationAnalysisResult",
    "CascadeRiskSignal",
    # Confluence
    "analyze_multi_timeframe",
    "get_confluence_summary",
    "ConfluenceResult",
    "TimeframeSignal",
]


