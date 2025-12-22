"""Coinalyze regime detection, pattern analysis, and backtesting."""

from signalvortex.analytics.coinalyze.backtest import (
    run_backtest,
    BacktestResult,
    Bar,
    load_bars,
    enrich_features,
)

from signalvortex.analytics.coinalyze.patterns import (
    analyze_coinalyze_patterns,
    RegimeAnalysisResult,
    RegimeRecord,
    RegimeEvent,
)

__all__ = [
    # Backtest
    "run_backtest",
    "BacktestResult",
    "Bar",
    "load_bars",
    "enrich_features",
    # Patterns
    "analyze_coinalyze_patterns",
    "RegimeAnalysisResult",
    "RegimeRecord",
    "RegimeEvent",
]
