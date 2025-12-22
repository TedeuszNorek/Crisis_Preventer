"""Binance Futures API client for open interest and long/short ratios."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from signalvortex.core.http_client import BaseClient

LOGGER = logging.getLogger(__name__)


class BinanceFuturesClient(BaseClient):
    """Binance Futures public API client.

    Provides access to open interest, long/short ratios, and klines
    without requiring API keys.
    """

    def __init__(self) -> None:
        """Initialize the Binance Futures client."""
        super().__init__(
            base_url="https://fapi.binance.com",
            rate_limit=60,  # Generous limit for public endpoints
        )

    def ping(self) -> Dict[str, Any]:
        """Test connectivity to the API."""
        return self.get("/fapi/v1/ping")

    def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> pd.DataFrame:
        """Get kline/candlestick data.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT').
            interval: Kline interval (1m, 5m, 1h, 1d, etc.).
            limit: Number of klines to return (max 1500).
            start_time: Start time in milliseconds.
            end_time: End time in milliseconds.

        Returns:
            DataFrame with OHLCV data.
        """
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, 1500),
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        data = self.get("/fapi/v1/klines", params=params)

        df = pd.DataFrame(
            data,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_buy_volume",
                "taker_buy_quote_volume",
                "ignore",
            ],
        )

        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        return df

    def get_open_interest(self, symbol: str) -> Dict[str, Any]:
        """Get current open interest for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT').

        Returns:
            Dict with openInterest, symbol, and time.
        """
        return self.get("/fapi/v1/openInterest", params={"symbol": symbol.upper()})

    def get_open_interest_hist(
        self,
        symbol: str,
        period: str = "5m",
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> pd.DataFrame:
        """Get historical open interest.

        Args:
            symbol: Trading pair.
            period: Period (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d).
            limit: Number of records (max 500).
            start_time: Start time in milliseconds.
            end_time: End time in milliseconds.

        Returns:
            DataFrame with timestamp, sumOpenInterest, sumOpenInterestValue.
        """
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "period": period,
            "limit": min(limit, 500),
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        data = self.get("/futures/data/openInterestHist", params=params)
        df = pd.DataFrame(data)

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df["sumOpenInterest"] = df["sumOpenInterest"].astype(float)
            df["sumOpenInterestValue"] = df["sumOpenInterestValue"].astype(float)

        return df

    def get_long_short_ratio(
        self,
        symbol: str,
        period: str = "5m",
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> pd.DataFrame:
        """Get long/short ratio for top traders.

        Args:
            symbol: Trading pair.
            period: Period (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d).
            limit: Number of records.
            start_time: Start time in milliseconds.
            end_time: End time in milliseconds.

        Returns:
            DataFrame with timestamp, longShortRatio, longAccount, shortAccount.
        """
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "period": period,
            "limit": min(limit, 500),
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        data = self.get("/futures/data/topLongShortAccountRatio", params=params)
        df = pd.DataFrame(data)

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ["longShortRatio", "longAccount", "shortAccount"]:
                df[col] = df[col].astype(float)

        return df

    def get_taker_buy_sell_volume(
        self,
        symbol: str,
        period: str = "5m",
        limit: int = 500,
    ) -> pd.DataFrame:
        """Get taker buy/sell volume ratio.

        Args:
            symbol: Trading pair.
            period: Period.
            limit: Number of records.

        Returns:
            DataFrame with buy/sell volumes and ratios.
        """
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "period": period,
            "limit": min(limit, 500),
        }

        data = self.get("/futures/data/takerlongshortRatio", params=params)
        df = pd.DataFrame(data)

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ["buySellRatio", "buyVol", "sellVol"]:
                if col in df.columns:
                    df[col] = df[col].astype(float)

        return df

    def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get current funding rate for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT').

        Returns:
            Dict with symbol, markPrice, fundingRate, fundingTime, etc.
        """
        data = self.get("/fapi/v1/premiumIndex", params={"symbol": symbol.upper()})
        return data

    def get_funding_rate_hist(
        self,
        symbol: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> pd.DataFrame:
        """Get historical funding rates.

        Args:
            symbol: Trading pair.
            limit: Number of records (max 1000).
            start_time: Start time in milliseconds.
            end_time: End time in milliseconds.

        Returns:
            DataFrame with fundingTime, fundingRate.
        """
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "limit": min(limit, 1000),
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        data = self.get("/fapi/v1/fundingRate", params=params)
        df = pd.DataFrame(data)

        if not df.empty:
            df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms")
            df["fundingRate"] = df["fundingRate"].astype(float)
            df = df.rename(columns={"fundingTime": "timestamp"})

        return df

    def get_mark_price(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """Get mark price and funding rate for symbol(s).

        Args:
            symbol: Optional trading pair. If None, returns all symbols.

        Returns:
            DataFrame with mark price, index price, funding rate.
        """
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()

        data = self.get("/fapi/v1/premiumIndex", params=params or None)

        if isinstance(data, dict):
            data = [data]

        df = pd.DataFrame(data)

        if not df.empty:
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            for col in ["markPrice", "indexPrice", "lastFundingRate"]:
                if col in df.columns:
                    df[col] = df[col].astype(float)

        return df

