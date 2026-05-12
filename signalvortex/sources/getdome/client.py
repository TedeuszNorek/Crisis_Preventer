"""GetDome API client for Polymarket overlay data."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from signalvortex.core.http_client import BaseClient

LOGGER = logging.getLogger(__name__)


class GetDomeClient(BaseClient):
    """GetDome API client for Polymarket prediction market data.

    Provides access to prediction market prices and can be used
    to overlay market sentiment on equity/crypto analysis.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.domeapi.io/v1",
    ) -> None:
        """Initialize the GetDome client.

        Args:
            api_key: GetDome API key (Bearer token).
            base_url: API base URL.
        """
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            api_key_header="Authorization",
            rate_limit=60,
        )

    def get_market_price(
        self,
        token_id: str,
        *,
        at_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch the latest price for a Polymarket market.

        Args:
            token_id: Polymarket token ID.
            at_time: Optional timestamp for historical price.

        Returns:
            Market price payload.
        """
        params: Dict[str, Any] = {}
        if at_time is not None:
            params["at_time"] = at_time

        return self.get(f"/polymarket/market-price/{token_id}", params=params or None)

    def get_market_history(
        self,
        token_id: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch historical prices for a Polymarket market.

        Args:
            token_id: Polymarket token ID.
            start: Start date (ISO format).
            end: End date (ISO format).

        Returns:
            Historical price data.
        """
        params: Dict[str, Any] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        return self.get(f"/polymarket/market-history/{token_id}", params=params or None)

    def parse_polymarket_tokens(self, token_config: str) -> Dict[str, str]:
        """Parse GETDOME_POLYMARKET_TOKENS configuration.

        Args:
            token_config: Comma-separated TOKEN=id pairs (e.g., "TMC=token1,SLDP=token2").

        Returns:
            Dict mapping symbol to token ID.
        """
        if not token_config:
            return {}

        result = {}
        for pair in token_config.split(","):
            if "=" in pair:
                symbol, token_id = pair.strip().split("=", 1)
                result[symbol.strip()] = token_id.strip()

        return result
