"""ECB Statistical Data Warehouse client for Euro Area monetary aggregates."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from signalvortex.core.http_client import BaseClient

LOGGER = logging.getLogger(__name__)


# ECB SDMX series keys for monetary aggregates
ECB_SERIES = {
    "M2": {
        "dataflow": "BSI",
        "series_key": "M.U2.Y.V.M20.X.1.U2.2300.Z01.E",
    },
    "M3": {
        "dataflow": "BSI",
        "series_key": "M.U2.Y.V.M30.X.1.U2.2300.Z01.E",
    },
}


class EcbClient(BaseClient):
    """ECB Statistical Data Warehouse API client.

    Provides access to Euro Area monetary aggregates (M2, M3) via SDMX.
    No API key required.
    """

    def __init__(self) -> None:
        """Initialize the ECB client."""
        super().__init__(
            base_url="https://data-api.ecb.europa.eu/service/data",
            rate_limit=30,  # Conservative limit
        )

    def get_series(
        self,
        aggregate: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Get a monetary aggregate series.

        Args:
            aggregate: Aggregate type ('M2' or 'M3').
            start_date: Optional start date.
            end_date: Optional end date.

        Returns:
            DataFrame with date and value columns.

        Raises:
            ValueError: If aggregate type is not supported.
        """
        if aggregate not in ECB_SERIES:
            raise ValueError(f"Unknown aggregate: {aggregate}. Supported: {list(ECB_SERIES.keys())}")

        config = ECB_SERIES[aggregate]
        dataflow = config["dataflow"]
        series_key = config["series_key"]

        params: Dict[str, str] = {"detail": "dataonly", "format": "json"}
        if start_date:
            params["startPeriod"] = start_date.strftime("%Y-%m")
        if end_date:
            params["endPeriod"] = end_date.strftime("%Y-%m")

        headers = {"Accept": "application/json"}
        url = f"/{dataflow}/{series_key}"

        # Use session directly for custom headers
        if self.rate_limiter:
            self.rate_limiter.wait_if_needed()

        response = self.session.get(
            f"{self.base_url}{url}",
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        return self._parse_sdmx_response(payload, aggregate)

    def _parse_sdmx_response(
        self,
        payload: Dict[str, Any],
        aggregate: str,
    ) -> pd.DataFrame:
        """Parse ECB SDMX JSON response.

        Args:
            payload: JSON response from ECB API.
            aggregate: Aggregate type for labeling.

        Returns:
            DataFrame with parsed data.
        """
        datasets = payload.get("dataSets", [])
        if not datasets:
            return pd.DataFrame()

        series_data = datasets[0].get("series", {})
        if not series_data:
            return pd.DataFrame()

        # Extract time dimension
        observation_dimensions = (
            payload.get("structure", {})
            .get("dimensions", {})
            .get("observation", [])
        )
        time_dimension = next(
            (dim for dim in observation_dimensions if dim.get("id") == "TIME_PERIOD"),
            None,
        )
        if not time_dimension:
            return pd.DataFrame()

        time_values = time_dimension.get("values", [])

        records = []
        for series_entry in series_data.values():
            observations = series_entry.get("observations", {})
            for index_str, observation in observations.items():
                try:
                    time_idx = int(index_str)
                except (TypeError, ValueError):
                    continue

                if time_idx >= len(time_values):
                    continue

                time_code = time_values[time_idx].get("id")
                if not time_code:
                    continue

                raw_value = observation[0] if observation else None
                if raw_value in (None, ".", ""):
                    continue

                try:
                    value = float(raw_value)
                except (TypeError, ValueError):
                    continue

                records.append({
                    "date": f"{time_code}-01",
                    "value": value,
                    "region": "EU",
                    "aggregate": aggregate,
                })

        df = pd.DataFrame(records)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df.sort_values("date", inplace=True)

        return df

    def get_m2(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Get Euro Area M2 monetary aggregate.

        Args:
            start_date: Optional start date.
            end_date: Optional end date.

        Returns:
            DataFrame with M2 data.
        """
        return self.get_series("M2", start_date, end_date)

    def get_m3(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Get Euro Area M3 monetary aggregate.

        Args:
            start_date: Optional start date.
            end_date: Optional end date.

        Returns:
            DataFrame with M3 data.
        """
        return self.get_series("M3", start_date, end_date)
