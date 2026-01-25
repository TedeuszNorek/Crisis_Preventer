"""Polygon.io API client for options data."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, Optional

import pandas as pd

from signalvortex.core.http_client import BaseClient

LOGGER = logging.getLogger(__name__)


def _parse_iso_date(value: str) -> date:
    """Parse ISO date string to date object."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.date()


def _extract_spot(snapshot_payload: Dict[str, Any]) -> Optional[float]:
    """Extract spot price from snapshot payload."""
    underlying = snapshot_payload.get("underlying_asset")
    if not isinstance(underlying, dict):
        return None
    for key in ("last_trade", "last_quote"):
        payload = underlying.get(key)
        if isinstance(payload, dict):
            for price_key in ("price", "midpoint", "bid", "ask"):
                price = payload.get(price_key)
                if isinstance(price, (int, float)) and price > 0:
                    return float(price)
    return None


class PolygonClient(BaseClient):
    """Polygon.io API client for options snapshots and IV surface construction."""

    def __init__(self, api_key: str) -> None:
        """Initialize the Polygon client.

        Args:
            api_key: Polygon.io API key.
        """
        super().__init__(
            base_url="https://api.polygon.io",
            api_key=api_key,
            api_key_param="apiKey",
            rate_limit=5,  # Free tier: 5 req/min
        )

    def iter_option_snapshots(
        self,
        underlying: str,
        *,
        valuation_date: Optional[str] = None,
        limit: int = 500,
    ) -> Iterable[Dict[str, Any]]:
        """Yield option snapshots for the requested underlying.

        Args:
            underlying: Ticker symbol (e.g., 'AAPL').
            valuation_date: Optional date in YYYY-MM-DD format.
            limit: Results per page.

        Yields:
            Option snapshot dictionaries.
        """
        params: Dict[str, Any] = {"limit": limit}
        if valuation_date:
            params["date"] = valuation_date

        next_url: Optional[str] = None
        while True:
            if next_url:
                # Handle pagination
                import requests

                if "apiKey=" in next_url:
                    resp = requests.get(next_url, timeout=60)
                else:
                    resp = requests.get(next_url, params={"apiKey": self.api_key}, timeout=60)
                resp.raise_for_status()
                payload = resp.json()
            else:
                payload = self.get(f"/v3/snapshot/options/{underlying.upper()}", params=params)

            results = payload.get("results") or []
            if not isinstance(results, list):
                break

            for item in results:
                if isinstance(item, dict):
                    yield item

            next_url = payload.get("next_url")
            if not next_url:
                break

    def fetch_option_chain(
        self,
        underlying: str,
        *,
        valuation_date: Optional[str] = None,
    ) -> tuple[pd.DataFrame, float]:
        """Download all option snapshots and return a DataFrame.

        Args:
            underlying: Ticker symbol.
            valuation_date: Optional date in YYYY-MM-DD format.

        Returns:
            Tuple of (DataFrame with option data, spot price).

        Raises:
            RuntimeError: If no data or spot price cannot be inferred.
        """
        import numpy as np

        records: list[Dict[str, Any]] = []
        inferred_spot: Optional[float] = None
        valuation_dt: Optional[date] = (
            datetime.fromisoformat(valuation_date).date() if valuation_date else None
        )

        for snapshot in self.iter_option_snapshots(underlying, valuation_date=valuation_date):
            if inferred_spot is None:
                inferred_spot = _extract_spot(snapshot)

            details = snapshot.get("details")
            greeks = snapshot.get("greeks")
            if not isinstance(details, dict) or not isinstance(greeks, dict):
                continue

            strike = details.get("strike_price")
            expiration = details.get("expiration_date")
            option_type = details.get("contract_type")
            iv = greeks.get("implied_volatility")

            if not isinstance(strike, (int, float)) or strike <= 0:
                continue
            if not isinstance(iv, (int, float)) or iv <= 0:
                continue
            if not isinstance(expiration, str):
                continue

            exp_date = _parse_iso_date(expiration)
            if valuation_dt is None:
                valuation_dt = _parse_iso_date(
                    snapshot.get("day", {}).get("date") or exp_date.isoformat()
                )

            maturity_days = (exp_date - valuation_dt).days
            if maturity_days <= 0:
                continue

            maturity_years = maturity_days / 365.0
            records.append(
                {
                    "option_symbol": snapshot.get("details", {}).get("ticker", ""),
                    "strike": float(strike),
                    "expiration": exp_date,
                    "maturity_days": maturity_days,
                    "maturity_years": maturity_years,
                    "option_type": option_type,
                    "implied_vol": float(iv),
                }
            )

        if not records:
            raise RuntimeError("No option data returned; verify the symbol/date or API entitlements.")
        if inferred_spot is None:
            raise RuntimeError("Failed to infer the underlying spot price from the snapshot payload.")

        df = pd.DataFrame(records)
        df["spot"] = inferred_spot
        df["moneyness"] = df["strike"] / inferred_spot
        df["log_moneyness"] = np.log(df["moneyness"])
        df.sort_values(["maturity_days", "strike"], inplace=True)

        return df, inferred_spot

    def get_ticker_details(self, ticker: str) -> Dict[str, Any]:
        """Get details for a ticker symbol.

        Args:
            ticker: Ticker symbol.

        Returns:
            Ticker details dictionary.
        """
        return self.get(f"/v3/reference/tickers/{ticker.upper()}")

    def get_aggregates(
        self,
        ticker: str,
        multiplier: int,
        timespan: str,
        from_date: str,
        to_date: str,
        limit: int = 5000,
    ) -> pd.DataFrame:
        """Get aggregate bars (candles) for a ticker.

        Args:
            ticker: Ticker symbol (e.g., 'AAPL').
            multiplier: Size of the timespan multiplier (e.g., 1).
            timespan: Size of the time window (minute, hour, day, etc.).
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            limit: Max results.

        Returns:
            DataFrame with timestamp, open, high, low, close, volume.
        """
        path = f"/v2/aggs/ticker/{ticker.upper()}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
        params = {"limit": limit, "sort": "asc", "adjusted": "true"}
        
        data = self.get(path, params=params)
        results = data.get("results", [])
        
        if not results:
            return pd.DataFrame()
            
        df = pd.DataFrame(results)
        # Polygon returns 't' (Unix MS), 'o', 'h', 'l', 'c', 'v', 'n' (transactions), 'vw' (weighted avg)
        # Rename for consistency
        cols_map = {
            "t": "timestamp",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume"
        }
        df.rename(columns=cols_map, inplace=True)
        
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            
        return df
