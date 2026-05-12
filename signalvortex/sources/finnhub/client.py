"""Finnhub API client for sentiment, options, and insider trading data."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from signalvortex.core.http_client import BaseClient

LOGGER = logging.getLogger(__name__)


def _to_datetime(value: Any) -> Optional[datetime]:
    """Convert various formats to UTC datetime."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            from dateutil import parser as date_parser
            dt = date_parser.parse(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError, ImportError):
            return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return None


class FinnhubClient(BaseClient):
    """Finnhub API client for market sentiment and options data.

    Provides access to:
    - Option chains
    - Social sentiment
    - News sentiment
    - Insider transactions
    """

    def __init__(
        self,
        api_key: str,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
    ) -> None:
        """Initialize the Finnhub client.

        Args:
            api_key: Finnhub API key.
            max_retries: Maximum number of retries for failed requests.
            retry_backoff: Backoff multiplier for retries (in seconds).
        """
        super().__init__(
            base_url="https://finnhub.io/api/v1",
            api_key=api_key,
            api_key_param="token",
            rate_limit=60,  # Free tier: 60/min
        )
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

    def _with_retry(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function with retry logic."""
        attempt = 0
        while True:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise
                sleep_time = self.retry_backoff * attempt
                LOGGER.warning(f"Finnhub call failed ({exc}). Retrying in {sleep_time:.1f}s")
                time.sleep(sleep_time)

    def get_option_chain(self, symbol: str) -> pd.DataFrame:
        """Get option chain for a symbol.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            DataFrame with option contracts data.
        """
        try:
            payload = self._with_retry(
                self.get,
                "/stock/option-chain",
                params={"symbol": symbol.upper()},
            )
        except Exception as e:
            LOGGER.warning(f"Option chain unavailable for {symbol}: {e}")
            return pd.DataFrame()

        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            return pd.DataFrame()

        rows: List[Dict[str, Any]] = []
        spot = payload.get("lastTradePrice")

        for expiry in data:
            if not isinstance(expiry, dict):
                continue
            expiration = expiry.get("expirationDate")
            option_groups = expiry.get("options") or {}

            for opt_type in ("CALL", "PUT"):
                contracts = option_groups.get(opt_type) if isinstance(option_groups, dict) else None
                if not contracts:
                    continue

                for contract in contracts:
                    if not isinstance(contract, dict):
                        continue
                    rows.append({
                        "symbol": symbol.upper(),
                        "option_type": opt_type,
                        "expiration": contract.get("expirationDate") or expiration,
                        "strike": contract.get("strikePrice") or contract.get("strike"),
                        "volume": contract.get("volume"),
                        "open_interest": contract.get("openInterest"),
                        "implied_vol": contract.get("impliedVolatility"),
                        "delta": contract.get("delta"),
                        "gamma": contract.get("gamma"),
                        "theta": contract.get("theta"),
                        "vega": contract.get("vega"),
                        "last_trade_dt": _to_datetime(contract.get("lastTradeDateTime")),
                        "underlying_price": spot,
                    })

        df = pd.DataFrame(rows)
        if not df.empty and "last_trade_dt" in df.columns:
            df["quote_date"] = df["last_trade_dt"].dt.date
            df["quote_date"] = df["quote_date"].fillna(datetime.now(timezone.utc).date())

        return df

    def get_social_sentiment(
        self,
        symbol: str,
        days: int = 30,
    ) -> pd.DataFrame:
        """Get social media sentiment for a symbol.

        Args:
            symbol: Stock ticker symbol.
            days: Number of days to look back.

        Returns:
            DataFrame with sentiment data.
        """
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=days)

        try:
            payload = self._with_retry(
                self.get,
                "/stock/social-sentiment",
                params={
                    "symbol": symbol.upper(),
                    "from": start_dt.strftime("%Y-%m-%d"),
                    "to": end_dt.strftime("%Y-%m-%d"),
                },
            )
        except Exception as e:
            LOGGER.info(f"Social sentiment unavailable for {symbol}: {e}")
            return pd.DataFrame()

        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["symbol"] = symbol.upper()
        if "atTime" in df.columns:
            df["date"] = df["atTime"].apply(lambda x: _to_datetime(x).date() if _to_datetime(x) else None)

        return df

    def get_news_sentiment(self, symbol: str) -> pd.DataFrame:
        """Get news sentiment for a symbol.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            DataFrame with news sentiment scores.
        """
        try:
            payload = self._with_retry(
                self.get,
                "/news-sentiment",
                params={"symbol": symbol.upper()},
            )
        except Exception as e:
            LOGGER.info(f"News sentiment unavailable for {symbol}: {e}")
            return pd.DataFrame()

        if not isinstance(payload, dict):
            return pd.DataFrame()

        company_news = payload.get("companyNewsScore")
        if company_news is None:
            return pd.DataFrame()

        df = pd.DataFrame([company_news])
        df["symbol"] = symbol.upper()
        df["date"] = datetime.now(timezone.utc).date()

        return df

    def get_insider_transactions(
        self,
        symbol: str,
        days: int = 365,
    ) -> pd.DataFrame:
        """Get insider trading transactions.

        Args:
            symbol: Stock ticker symbol.
            days: Number of days to look back.

        Returns:
            DataFrame with insider transactions.
        """
        start_dt = datetime.now(timezone.utc) - timedelta(days=days)

        try:
            payload = self._with_retry(
                self.get,
                "/stock/insider-transactions",
                params={
                    "symbol": symbol.upper(),
                    "from": start_dt.strftime("%Y-%m-%d"),
                    "to": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                },
            )
        except Exception as e:
            LOGGER.info(f"Insider data unavailable for {symbol}: {e}")
            return pd.DataFrame()

        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["symbol"] = symbol.upper()
        if "transactionDate" in df.columns:
            df["transaction_date"] = df["transactionDate"].apply(
                lambda x: _to_datetime(x).date() if _to_datetime(x) else None
            )

        return df
