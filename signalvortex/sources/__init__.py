"""SignalVortex data sources."""

from signalvortex.sources.polygon.client import PolygonClient
from signalvortex.sources.binance.client import BinanceFuturesClient
from signalvortex.sources.binance.archive import load_daily_metrics, DailyMetric
from signalvortex.sources.fred.client import FredClient
from signalvortex.sources.ecb.client import EcbClient
from signalvortex.sources.coinalyze.client import CoinalyzeClient
from signalvortex.sources.getdome.client import GetDomeClient
from signalvortex.sources.finnhub.client import FinnhubClient
from signalvortex.sources.massive import MassiveClient
from signalvortex.sources.gamma import GammaClient

__all__ = [
    "PolygonClient",
    "BinanceFuturesClient",
    "load_daily_metrics",
    "DailyMetric",
    "FredClient",
    "EcbClient",
    "CoinalyzeClient",
    "GetDomeClient",
    "FinnhubClient",
    "MassiveClient",
    "GammaClient",
]


