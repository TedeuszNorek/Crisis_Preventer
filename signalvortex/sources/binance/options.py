"""Binance Options API client for European-style crypto options."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from signalvortex.core.http_client import BaseClient

LOGGER = logging.getLogger(__name__)


class BinanceOptionsClient(BaseClient):
    """Binance European Options API client.

    Provides access to options data including:
    - Option chains with Greeks
    - Open interest
    - Mark prices
    - Historical klines
    - Ticker data

    Note: Binance Options are available for BTC, ETH, and select assets.
    API Base: https://eapi.binance.com
    """

    def __init__(self) -> None:
        """Initialize the Binance Options client."""
        super().__init__(
            base_url="https://eapi.binance.com",
            rate_limit=60,
        )

    def ping(self) -> Dict[str, Any]:
        """Test connectivity to the API."""
        return self.get("/eapi/v1/ping")

    def get_time(self) -> Dict[str, Any]:
        """Get server time."""
        return self.get("/eapi/v1/time")

    def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange info including available options contracts.

        Returns:
            Dict with timezone, serverTime, optionContracts, optionAssets, etc.
        """
        return self.get("/eapi/v1/exchangeInfo")

    def get_underlying_index(self, underlying: str = "BTCUSDT") -> Dict[str, Any]:
        """Get underlying index price.

        Args:
            underlying: Underlying symbol (e.g., 'BTCUSDT').

        Returns:
            Dict with indexPrice and time.
        """
        return self.get("/eapi/v1/index", params={"underlying": underlying.upper()})

    def get_mark_price(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """Get option mark price(s).

        Args:
            symbol: Optional option symbol. If None, returns all.

        Returns:
            DataFrame with symbol, markPrice, bidIV, askIV, markIV, delta, theta, gamma, vega.
        """
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()

        data = self.get("/eapi/v1/mark", params=params or None)

        if isinstance(data, dict):
            data = [data]

        df = pd.DataFrame(data)

        if not df.empty:
            numeric_cols = ["markPrice", "bidIV", "askIV", "markIV", "delta", "theta", "gamma", "vega", "riskFreeInterest"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def get_ticker(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """Get 24hr ticker statistics.

        Args:
            symbol: Optional option symbol.

        Returns:
            DataFrame with price, volume, and other ticker data.
        """
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()

        data = self.get("/eapi/v1/ticker", params=params or None)

        if isinstance(data, dict):
            data = [data]

        df = pd.DataFrame(data)

        if not df.empty:
            numeric_cols = ["priceChange", "priceChangePercent", "lastPrice", "lastQty",
                           "open", "high", "low", "volume", "amount", "bidPrice", "askPrice"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def get_open_interest(self, underlying: str, expiration: Optional[str] = None) -> pd.DataFrame:
        """Get option open interest.

        Args:
            underlying: Underlying symbol (e.g., 'BTCUSDT').
            expiration: Optional expiration date (e.g., '240329').

        Returns:
            DataFrame with sumOpenInterest, sumOpenInterestUsd by option type.
        """
        params = {"underlyingAsset": underlying.upper().replace("USDT", "")}
        if expiration:
            params["expiration"] = expiration

        data = self.get("/eapi/v1/openInterest", params=params)

        if isinstance(data, dict):
            data = [data]

        df = pd.DataFrame(data)

        if not df.empty:
            for col in ["sumOpenInterest", "sumOpenInterestUsd"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def get_option_chain(
        self,
        underlying: str = "BTCUSDT",
        expiration: Optional[str] = None,
    ) -> pd.DataFrame:
        """Get full option chain with mark prices and Greeks.

        Args:
            underlying: Underlying symbol.
            expiration: Optional expiration filter.

        Returns:
            DataFrame with complete option chain data.
        """
        # First get exchange info to find available contracts
        try:
            info = self.get_exchange_info()
        except Exception as e:
            LOGGER.error(f"Failed to get exchange info: {e}")
            return pd.DataFrame()

        contracts = info.get("optionSymbols", [])
        if not contracts:
            return pd.DataFrame()

        # Filter by underlying
        underlying_base = underlying.upper().replace("USDT", "")
        filtered = [c for c in contracts if c.get("underlying", "").startswith(underlying_base)]

        if expiration:
            filtered = [c for c in filtered if c.get("expiryDate", "").startswith(expiration)]

        if not filtered:
            LOGGER.warning(f"No option contracts found for {underlying}")
            return pd.DataFrame()

        # Get mark prices for all symbols
        symbols = [c.get("symbol") for c in filtered if c.get("symbol")]

        # Fetch mark prices in batches
        all_marks = []
        for symbol in symbols[:50]:  # Limit to avoid rate limits
            try:
                mark_df = self.get_mark_price(symbol)
                if not mark_df.empty:
                    all_marks.append(mark_df.iloc[0].to_dict())
            except Exception as e:
                LOGGER.debug(f"Failed to get mark for {symbol}: {e}")

        if not all_marks:
            # Try bulk request
            try:
                mark_df = self.get_mark_price()
                if not mark_df.empty:
                    mark_df = mark_df[mark_df["symbol"].str.contains(underlying_base)]
                    return mark_df
            except Exception:
                pass
            return pd.DataFrame()

        df = pd.DataFrame(all_marks)

        # Parse symbol to extract strike, expiry, type
        if not df.empty and "symbol" in df.columns:
            df["underlying"] = underlying
            df["parsed"] = df["symbol"].apply(self._parse_option_symbol)
            df["strike"] = df["parsed"].apply(lambda x: x.get("strike"))
            df["expiry"] = df["parsed"].apply(lambda x: x.get("expiry"))
            df["option_type"] = df["parsed"].apply(lambda x: x.get("type"))
            df.drop(columns=["parsed"], inplace=True)

        return df

    def _parse_option_symbol(self, symbol: str) -> Dict[str, Any]:
        """Parse Binance option symbol to extract components.

        Example: BTC-240329-70000-C -> {underlying: BTC, expiry: 240329, strike: 70000, type: C}
        """
        try:
            parts = symbol.split("-")
            if len(parts) >= 4:
                return {
                    "underlying": parts[0],
                    "expiry": parts[1],
                    "strike": float(parts[2]),
                    "type": "CALL" if parts[3] == "C" else "PUT",
                }
        except Exception:
            pass
        return {}

    def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> pd.DataFrame:
        """Get option kline/candlestick data.

        Args:
            symbol: Option symbol (e.g., 'BTC-240329-70000-C').
            interval: Kline interval (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w).
            limit: Number of klines (max 1500).
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

        data = self.get("/eapi/v1/klines", params=params)

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(
            data,
            columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "amount", "trades", "taker_buy_vol", "taker_buy_amount", "ignore"
            ][:len(data[0])] if data else []
        )

        if not df.empty:
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            if "close_time" in df.columns:
                df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def get_historical_trades(
        self,
        symbol: str,
        limit: int = 500,
        from_id: Optional[int] = None,
    ) -> pd.DataFrame:
        """Get historical trades for an option.

        Args:
            symbol: Option symbol.
            limit: Number of trades (max 500).
            from_id: Trade ID to start from.

        Returns:
            DataFrame with trade history.
        """
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "limit": min(limit, 500),
        }
        if from_id:
            params["fromId"] = from_id

        data = self.get("/eapi/v1/historicalTrades", params=params)
        df = pd.DataFrame(data)

        if not df.empty:
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            for col in ["price", "qty"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def get_iv_by_expiry(self, underlying: str = "BTCUSDT") -> pd.DataFrame:
        """Get implied volatility grouped by expiry.

        Args:
            underlying: Underlying symbol.

        Returns:
            DataFrame with IV curve data per expiry.
        """
        chain = self.get_option_chain(underlying)
        if chain.empty:
            return pd.DataFrame()

        # Group by expiry and calculate average IV
        if "expiry" in chain.columns and "markIV" in chain.columns:
            iv_by_expiry = chain.groupby("expiry").agg({
                "markIV": ["mean", "min", "max"],
                "symbol": "count"
            }).reset_index()
            iv_by_expiry.columns = ["expiry", "avg_iv", "min_iv", "max_iv", "contract_count"]
            return iv_by_expiry

        return pd.DataFrame()

    def get_put_call_ratio(self, underlying: str = "BTCUSDT") -> Dict[str, float]:
        """Calculate put/call ratio from open interest.

        Args:
            underlying: Underlying symbol.

        Returns:
            Dict with put_oi, call_oi, put_call_ratio.
        """
        oi_df = self.get_open_interest(underlying)

        if oi_df.empty:
            return {"put_oi": 0.0, "call_oi": 0.0, "put_call_ratio": 0.0}

        call_oi = oi_df[oi_df["symbol"].str.endswith("-C")]["sumOpenInterestUsd"].sum() if "symbol" in oi_df.columns else 0
        put_oi = oi_df[oi_df["symbol"].str.endswith("-P")]["sumOpenInterestUsd"].sum() if "symbol" in oi_df.columns else 0

        ratio = put_oi / call_oi if call_oi > 0 else 0.0

        return {
            "call_oi_usd": call_oi,
            "put_oi_usd": put_oi,
            "put_call_ratio": ratio,
        }
