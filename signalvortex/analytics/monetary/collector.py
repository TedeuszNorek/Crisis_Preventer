"""Collect and analyze monetary aggregates (M2/M3) from FRED and ECB."""

from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

import pandas as pd

from signalvortex.sources.fred import FredClient
from signalvortex.sources.ecb import EcbClient

LOGGER = logging.getLogger(__name__)


def collect_monetary_aggregates(
    fred_api_key: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    """Collect monetary aggregates from FRED (USA) and ECB (Euro Area).

    Args:
        fred_api_key: FRED API key.
        start_date: Optional start date for data.
        end_date: Optional end date for data.

    Returns:
        DataFrame with columns: date, region, aggregate, value.
    """
    frames: List[pd.DataFrame] = []

    # USA M2 from FRED
    try:
        fred = FredClient(fred_api_key)
        usa_m2 = fred.get_m2(start_date, end_date)
        if not usa_m2.empty:
            frames.append(usa_m2)
            LOGGER.info(f"Fetched {len(usa_m2)} USA M2 observations")
    except Exception as e:
        LOGGER.warning(f"Failed to fetch FRED data: {e}")

    # Euro Area M2/M3 from ECB
    try:
        ecb = EcbClient()
        eu_m2 = ecb.get_m2(start_date, end_date)
        if not eu_m2.empty:
            frames.append(eu_m2)
            LOGGER.info(f"Fetched {len(eu_m2)} EU M2 observations")

        eu_m3 = ecb.get_m3(start_date, end_date)
        if not eu_m3.empty:
            frames.append(eu_m3)
            LOGGER.info(f"Fetched {len(eu_m3)} EU M3 observations")
    except Exception as e:
        LOGGER.warning(f"Failed to fetch ECB data: {e}")

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df.sort_values(["region", "aggregate", "date"], inplace=True)
    return df


def compute_growth(df: pd.DataFrame) -> pd.DataFrame:
    """Compute month-over-month percentage change for monetary aggregates.

    Args:
        df: DataFrame with columns: date, region, aggregate, value.

    Returns:
        DataFrame with added 'pct_change' column.
    """
    if df.empty:
        return df

    df = df.copy()
    df["pct_change"] = None

    for (region, aggregate), group in df.groupby(["region", "aggregate"]):
        group = group.sort_values("date")
        indices = group.index
        values = group["value"].values

        for i in range(1, len(values)):
            if values[i - 1] != 0:
                pct = (values[i] - values[i - 1]) / values[i - 1]
                df.loc[indices[i], "pct_change"] = pct

    return df


def get_latest_growth_rates(df: pd.DataFrame) -> dict:
    """Get the most recent growth rate for each aggregate.

    Args:
        df: DataFrame with pct_change column.

    Returns:
        Dict mapping 'region_aggregate' to latest pct_change.
    """
    if df.empty or "pct_change" not in df.columns:
        return {}

    result = {}
    for (region, aggregate), group in df.groupby(["region", "aggregate"]):
        latest = group.dropna(subset=["pct_change"]).sort_values("date").tail(1)
        if not latest.empty:
            key = f"{region}_{aggregate}"
            result[key] = float(latest["pct_change"].iloc[0])

    return result
