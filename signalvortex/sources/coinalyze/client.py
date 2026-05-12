"""Coinalyze API client for open interest and long/short ratio data."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from signalvortex.core.http_client import BaseClient

LOGGER = logging.getLogger(__name__)


class CoinalyzeClient(BaseClient):
    """Coinalyze API client for futures market data.

    Provides access to:
    - Open interest history
    - Long/short ratio history
    - OHLCV data
    - Funding rates
    """

    def __init__(self, api_key: str) -> None:
        """Initialize the Coinalyze client.

        Args:
            api_key: Coinalyze API key.
        """
        super().__init__(
            base_url="https://api.coinalyze.net/v1",
            api_key=api_key,
            api_key_param="api_key",
            rate_limit=30,
        )

    def _comma_separated(self, symbols: Sequence[str]) -> str:
        """Join symbols with commas."""
        if not symbols:
            raise ValueError("At least one symbol must be provided.")
        return ",".join(symbols)

    def get_exchanges(self) -> List[Dict[str, Any]]:
        """Get list of supported exchanges."""
        return self.get("/exchanges")

    def get_future_markets(self) -> List[Dict[str, Any]]:
        """Get list of available futures markets."""
        return self.get("/future-markets")

    def get_open_interest_history(
        self,
        symbols: Sequence[str],
        *,
        interval: str = "daily",
        start: Optional[int] = None,
        end: Optional[int] = None,
        convert_to_usd: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get historical open interest data.

        Args:
            symbols: List of market symbols (e.g., ['BTCUSDT_PERP.A']).
            interval: Time interval (daily, 1h, 4h, etc.).
            start: Start timestamp (Unix seconds).
            end: End timestamp (Unix seconds).
            convert_to_usd: Convert OI values to USD.

        Returns:
            List of dicts with symbol and history data.
        """
        params: Dict[str, Any] = {
            "symbols": self._comma_separated(symbols),
            "interval": interval,
            "convert_to_usd": "true" if convert_to_usd else "false",
        }
        if start:
            params["from"] = start
        if end:
            params["to"] = end

        return self.get("/open-interest-history", params=params)

    def get_long_short_ratio_history(
        self,
        symbols: Sequence[str],
        *,
        interval: str = "daily",
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get historical long/short ratio data.

        Args:
            symbols: List of market symbols.
            interval: Time interval.
            start: Start timestamp.
            end: End timestamp.

        Returns:
            List of dicts with symbol and history data.
        """
        params: Dict[str, Any] = {
            "symbols": self._comma_separated(symbols),
            "interval": interval,
        }
        if start:
            params["from"] = start
        if end:
            params["to"] = end

        return self.get("/long-short-ratio-history", params=params)

    def get_ohlcv_history(
        self,
        symbols: Sequence[str],
        *,
        interval: str = "daily",
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get OHLCV (candlestick) data.

        Args:
            symbols: List of market symbols.
            interval: Time interval.
            start: Start timestamp.
            end: End timestamp.

        Returns:
            List of dicts with symbol and history data.
        """
        params: Dict[str, Any] = {
            "symbols": self._comma_separated(symbols),
            "interval": interval,
        }
        if start:
            params["from"] = start
        if end:
            params["to"] = end

        return self.get("/ohlcv-history", params=params)

    def get_funding_rate_history(
        self,
        symbols: Sequence[str],
        *,
        interval: str = "daily",
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get historical funding rates.

        Args:
            symbols: List of market symbols.
            interval: Time interval.
            start: Start timestamp.
            end: End timestamp.

        Returns:
            List of dicts with symbol and history data.
        """
        params: Dict[str, Any] = {
            "symbols": self._comma_separated(symbols),
            "interval": interval,
        }
        if start:
            params["from"] = start
        if end:
            params["to"] = end

        return self.get("/funding-rate-history", params=params)

    def get_combined_dataframe(
        self,
        symbol: str,
        *,
        interval: str = "daily",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Fetch OI, L/S ratio, and OHLCV and merge into a single DataFrame.

        Args:
            symbol: Market symbol (e.g., 'BTCUSDT_PERP.A').
            interval: Time interval.
            start_date: Start date.
            end_date: End date.

        Returns:
            DataFrame with timestamp, price, oi, ratio columns.
        """
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp()) if start_date else None
        end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp()) if end_date else None

        try:
            oi_data = self.get_open_interest_history([symbol], interval=interval, start=start_ts, end=end_ts)
            ratio_data = self.get_long_short_ratio_history([symbol], interval=interval, start=start_ts, end=end_ts)
            ohlcv_data = self.get_ohlcv_history([symbol], interval=interval, start=start_ts, end=end_ts)
        except Exception as e:
            LOGGER.error(f"Failed to fetch Coinalyze data for {symbol}: {e}")
            return pd.DataFrame()

        if not oi_data or not ratio_data or not ohlcv_data:
            return pd.DataFrame()

        oi_history = oi_data[0].get("history", [])
        ratio_history = ratio_data[0].get("history", [])
        ohlcv_history = ohlcv_data[0].get("history", [])

        oi_map = {item["t"]: item["c"] for item in oi_history}
        ratio_map = {item["t"]: item.get("r") or (item["l"] / item["s"] if item.get("s") else None) for item in ratio_history}
        price_map = {item["t"]: item["c"] for item in ohlcv_history}

        timestamps = sorted(set(oi_map) & set(ratio_map) & set(price_map))

        records = []
        for ts in timestamps:
            records.append({
                "timestamp": datetime.fromtimestamp(ts),
                "price": price_map[ts],
                "oi": oi_map[ts],
                "ratio": ratio_map[ts],
            })

        return pd.DataFrame(records)
