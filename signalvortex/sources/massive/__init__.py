"""Massive.com market data client (Polygon-like endpoints)."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from signalvortex.core.http_client import BaseClient

LOGGER = logging.getLogger(__name__)


class MassiveClient(BaseClient):
    """Massive API client for market data.

    Provides access to:
    - Previous day bars
    - Real-time snapshots
    - Option chain snapshots
    - S3 flat-file data (optional)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.massive.com",
        s3_config: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize the Massive client.

        Args:
            api_key: Massive API key (Bearer token).
            base_url: API base URL.
            s3_config: Optional S3 configuration for flat-file access.
        """
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            api_key_header="Authorization",
            rate_limit=60,
        )
        self.s3_config = s3_config or {}
        self.coverage: Dict[str, Dict[str, bool]] = {}

    def _track(self, symbol: str, key: str, value: bool) -> None:
        """Track data coverage for symbol."""
        self.coverage.setdefault(symbol, {})[key] = value

    def get_coverage_report(self) -> Dict[str, Dict[str, bool]]:
        """Get coverage report for all queried symbols."""
        return self.coverage

    def get_prev_bar(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch previous day bar for a symbol.

        Args:
            symbol: Ticker symbol.

        Returns:
            Dict with OHLCV data or None.
        """
        try:
            payload = self.get(f"/v2/aggs/ticker/{symbol.upper()}/prev")
        except Exception as e:
            LOGGER.warning(f"Failed to fetch prev bar for {symbol}: {e}")
            self._track(symbol, "prev", False)
            return None

        results = payload.get("results") or []
        if not results:
            self._track(symbol, "prev", False)
            return None

        bar = results[0]
        self._track(symbol, "prev", True)
        return {
            "symbol": symbol.upper(),
            "prev_open": bar.get("o"),
            "prev_high": bar.get("h"),
            "prev_low": bar.get("l"),
            "prev_close": bar.get("c"),
            "prev_volume": bar.get("v"),
            "prev_timestamp": bar.get("t"),
        }

    def get_snapshot(self, symbols: List[str]) -> pd.DataFrame:
        """Fetch real-time snapshots for multiple symbols.

        Args:
            symbols: List of ticker symbols.

        Returns:
            DataFrame with snapshot data.
        """
        if not symbols:
            return pd.DataFrame(columns=["symbol", "snap_last", "snap_bid", "snap_ask", "snap_mid", "snap_ts"])

        try:
            payload = self.get("/v3/snapshot", params={"tickers": ",".join(symbols)})
        except Exception as e:
            LOGGER.warning(f"Failed to fetch snapshot: {e}")
            for symbol in symbols:
                self._track(symbol, "snapshot", False)
            return pd.DataFrame()

        results = payload.get("results") or payload.get("snapshots") or []
        rows: List[Dict[str, Any]] = []

        for entry in results:
            if not isinstance(entry, dict):
                continue

            symbol = (entry.get("ticker") or entry.get("symbol") or "").upper()
            if not symbol:
                continue

            best_bid = entry.get("bestBid")
            best_ask = entry.get("bestAsk")
            bid = best_bid.get("price") if isinstance(best_bid, dict) else best_bid
            ask = best_ask.get("price") if isinstance(best_ask, dict) else best_ask

            mid = None
            try:
                if bid is not None and ask is not None:
                    mid = (float(bid) + float(ask)) / 2.0
            except (TypeError, ValueError):
                mid = None

            rows.append({
                "symbol": symbol,
                "snap_last": entry.get("last") or entry.get("lastTrade", {}).get("price"),
                "snap_bid": bid,
                "snap_ask": ask,
                "snap_mid": mid,
                "snap_ts": entry.get("updated") or entry.get("timestamp"),
            })

        for symbol in symbols:
            self._track(symbol, "snapshot", any(row["symbol"] == symbol for row in rows))

        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def get_option_snapshot(self, symbol: str) -> pd.DataFrame:
        """Fetch option chain snapshot for a symbol.

        Args:
            symbol: Ticker symbol.

        Returns:
            DataFrame with option chain data.
        """
        try:
            payload = self.get(f"/v3/options/snapshot/chain/{symbol.upper()}")
        except Exception as e:
            LOGGER.warning(f"Failed to fetch option snapshot for {symbol}: {e}")
            self._track(symbol, "options", False)
            return pd.DataFrame()

        options = payload.get("options") or payload.get("results") or payload.get("chain") or []
        rows = []

        if options:
            self._track(symbol, "options", True)
        else:
            self._track(symbol, "options", False)

        for opt in options:
            if not isinstance(opt, dict):
                continue
            rows.append({
                "symbol": symbol.upper(),
                "option_symbol": opt.get("ticker") or opt.get("symbol") or opt.get("option_symbol"),
                "strike": opt.get("strike_price") or opt.get("strikePrice") or opt.get("strike"),
                "expiration": opt.get("expiration_date") or opt.get("expirationDate") or opt.get("expiration"),
                "option_type": opt.get("type") or opt.get("option_type"),
                "implied_vol": opt.get("implied_volatility") or opt.get("impliedVolatility"),
                "delta": opt.get("delta"),
                "gamma": opt.get("gamma"),
                "theta": opt.get("theta"),
                "vega": opt.get("vega"),
                "open_interest": opt.get("open_interest") or opt.get("openInterest"),
                "volume": opt.get("volume"),
                "underlying_price": opt.get("underlying_price") or opt.get("underlyingPrice"),
                "quote_date": opt.get("updated") or opt.get("quoteDate"),
            })

        return pd.DataFrame(rows) if rows else pd.DataFrame()
