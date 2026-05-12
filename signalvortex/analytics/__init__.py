"""SignalVortex analytics modules."""

from signalvortex.analytics.volatility import build_iv_surface, detect_anomalies
from signalvortex.analytics.leadlag import analyze_oi_price_leadlag
from signalvortex.analytics.monetary import collect_monetary_aggregates, compute_growth
from signalvortex.analytics.coinalyze import run_backtest, analyze_coinalyze_patterns
from signalvortex.analytics.features import make_option_features
from signalvortex.analytics.features.sentiment import merge_sentiment
from signalvortex.analytics.anomaly import flag_anomalies
from signalvortex.analytics.crypto import (
    analyze_funding_rates,
    analyze_taker_pressure,
    get_funding_summary,
    get_pressure_summary,
)

__all__ = [
    "build_iv_surface",
    "detect_anomalies",
    "analyze_oi_price_leadlag",
    "collect_monetary_aggregates",
    "compute_growth",
    "run_backtest",
    "analyze_coinalyze_patterns",
    "make_option_features",
    "merge_sentiment",
    "flag_anomalies",
    # Crypto
    "analyze_funding_rates",
    "analyze_taker_pressure",
    "get_funding_summary",
    "get_pressure_summary",
]


