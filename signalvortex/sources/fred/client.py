"""FRED API client for US monetary aggregates."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from signalvortex.core.http_client import BaseClient

LOGGER = logging.getLogger(__name__)


class FredClient(BaseClient):
    """Federal Reserve Economic Data (FRED) API client.

    Provides access to US monetary aggregates (M2, etc.) and other
    economic time series.
    """

    def __init__(self, api_key: str) -> None:
        """Initialize the FRED client.

        Args:
            api_key: FRED API key.
        """
        super().__init__(
            base_url="https://api.stlouisfed.org/fred",
            api_key=api_key,
            api_key_param="api_key",
            rate_limit=120,  # FRED allows 120 requests per minute
        )

    def get_series_observations(
        self,
        series_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Get observations for a FRED series.

        Args:
            series_id: FRED series identifier (e.g., 'M2SL' for M2).
            start_date: Optional start date.
            end_date: Optional end date.

        Returns:
            DataFrame with date and value columns.
        """
        params: Dict[str, Any] = {
            "series_id": series_id,
            "file_type": "json",
        }
        if start_date:
            params["observation_start"] = start_date.isoformat()
        if end_date:
            params["observation_end"] = end_date.isoformat()

        data = self.get("/series/observations", params=params)
        observations = data.get("observations", [])

        records = []
        for obs in observations:
            raw_value = obs.get("value")
            if raw_value in (None, ".", ""):
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue

            records.append({
                "date": obs.get("date"),
                "value": value,
                "series_id": series_id,
            })

        df = pd.DataFrame(records)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def get_m2(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Get US M2 monetary aggregate.

        Args:
            start_date: Optional start date.
            end_date: Optional end date.

        Returns:
            DataFrame with M2 data.
        """
        df = self.get_series_observations("M2SL", start_date, end_date)
        df["region"] = "USA"
        df["aggregate"] = "M2"
        return df

    def get_series_info(self, series_id: str) -> Dict[str, Any]:
        """Get metadata for a FRED series.

        Args:
            series_id: FRED series identifier.

        Returns:
            Series metadata dictionary.
        """
        params = {"series_id": series_id, "file_type": "json"}
        return self.get("/series", params=params)
