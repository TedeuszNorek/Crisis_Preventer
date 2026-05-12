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
    """Compute MoM and YoY percentage change for monetary aggregates.

    Args:
        df: DataFrame with columns: date, region, aggregate, value.

    Returns:
        DataFrame with added 'pct_change' (MoM) and 'yoy_change' columns.
    """
    if df.empty:
        return df

    df = df.copy()
    df["pct_change"] = None
    df["yoy_change"] = None

    # Sort to ensure correct time diff
    df.sort_values(["region", "aggregate", "date"], inplace=True)

    # Vectorized calculation per group
    for (region, aggregate), group_idx in df.groupby(["region", "aggregate"]).groups.items():
        # Get the group slice
        group = df.loc[group_idx]
        
        # Calculate MoM (1 period) and YoY (12 periods)
        # Assuming monthly data. If data has gaps, this matches by index position (lag),
        # which is standard for simple series. For strict date-based, we'd need to resample.
        mom = group["value"].pct_change(periods=1)
        yoy = group["value"].pct_change(periods=12)
        
        df.loc[group_idx, "pct_change"] = mom
        df.loc[group_idx, "yoy_change"] = yoy

    return df


def get_latest_growth_rates(df: pd.DataFrame) -> dict:
    """Get the most recent growth rates for each aggregate.

    Args:
        df: DataFrame with pct_change and yoy_change columns.

    Returns:
        Dict mapping keys to values:
        - '{region}_{aggregate}_mom': latest MoM change
        - '{region}_{aggregate}_yoy': latest YoY change
    """
    if df.empty or "pct_change" not in df.columns:
        return {}

    result = {}
    for (region, aggregate), group in df.groupby(["region", "aggregate"]):
        # Get latest available data point
        latest = group.sort_values("date").tail(1)
        if not latest.empty:
            mom = latest["pct_change"].iloc[0]
            yoy = latest["yoy_change"].iloc[0]
            
            base_key = f"{region}_{aggregate}"
            
            # Handle NaN if series is too short for YoY
            if pd.notna(mom):
                result[f"{base_key}_mom"] = float(mom)
            if pd.notna(yoy):
                result[f"{base_key}_yoy"] = float(yoy)

    return result
