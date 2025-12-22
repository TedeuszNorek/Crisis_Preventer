"""Gamma (Polymarket) API client."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

import requests

LOGGER = logging.getLogger(__name__)


class GammaClient:
    """Read-only client for the Gamma (Polymarket) API.

    Provides access to prediction market data.
    """

    def __init__(
        self,
        *,
        base_url: str = "https://gamma-api.polymarket.com",
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initialize the Gamma client.

        Args:
            base_url: API base URL.
            timeout: Request timeout in seconds.
            session: Optional requests session.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make API request."""
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list):
            return {"markets": payload}
        if not isinstance(payload, dict):
            raise ValueError("Unexpected Gamma API response format")
        return payload

    def iter_markets(self, **filters: Any) -> Iterable[Dict[str, Any]]:
        """Iterate over markets with optional filters.

        Args:
            **filters: Query filters.

        Yields:
            Market dictionaries.
        """
        cursor: Optional[str] = None
        while True:
            params = {**filters}
            if cursor:
                params["cursor"] = cursor

            payload = self._request("/markets", params=params or None)
            markets = payload.get("markets") or payload.get("data") or payload
            if isinstance(markets, dict):
                markets = markets.get("markets") or markets.get("data") or []

            if not isinstance(markets, list):
                LOGGER.warning("Gamma API returned unexpected markets payload")
                break

            for market in markets:
                if isinstance(market, dict):
                    yield market

            cursor = payload.get("next_cursor") or payload.get("nextCursor")
            if not cursor:
                break

    def list_markets(self, **filters: Any) -> List[Dict[str, Any]]:
        """List all markets with optional filters.

        Args:
            **filters: Query filters.

        Returns:
            List of market dictionaries.
        """
        return list(self.iter_markets(**filters))

    def get_market(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific market by ID.

        Args:
            market_id: Market identifier.

        Returns:
            Market dictionary or None.
        """
        try:
            return self._request(f"/markets/{market_id}")
        except Exception as e:
            LOGGER.warning(f"Failed to fetch market {market_id}: {e}")
            return None
