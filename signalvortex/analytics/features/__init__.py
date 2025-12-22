"""Feature engineering for option chains."""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

np.seterr(invalid="ignore")
warnings.filterwarnings("ignore", "Mean of empty slice", RuntimeWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning, module=r"numpy\.lib\._nanfunctions_impl")


def _calc_returns(equity_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate returns and volatility for equity data."""
    if equity_df.empty:
        return equity_df
    df = equity_df.sort_values(["symbol", "date"]).copy()
    df["ret_1d"] = df.groupby("symbol")["close"].pct_change()
    df["ret_5d"] = df.groupby("symbol")["close"].pct_change(5)
    df["ret_1d_filled"] = df["ret_1d"].fillna(0.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        df["vol_of_underlying"] = (
            df.groupby("symbol")["ret_1d_filled"]
            .rolling(window=20, min_periods=5)
            .std()
            .reset_index(level=0, drop=True)
        )
    df.drop(columns="ret_1d_filled", inplace=True)
    return df


def _bucket_moneyness(moneyness: float) -> str:
    """Categorize moneyness into buckets."""
    if moneyness < 0.02:
        return "ATM"
    if moneyness < 0.07:
        return "NEAR"
    if moneyness < 0.15:
        return "MID"
    return "DEEP"


def _infer_delta_bucket(row: pd.Series) -> str:
    """Infer delta bucket from delta or moneyness."""
    delta = row.get("delta")
    if pd.notna(delta):
        val = abs(float(delta))
        if val >= 0.6:
            return "ITM"
        if val >= 0.3:
            return "MID"
        return "OTM"
    spot = row.get("underlying_price")
    strike = row.get("strike")
    option_type = str(row.get("option_type", "")).upper()
    if spot and strike:
        if option_type == "CALL":
            return "ITM" if strike <= spot else "OTM"
        if option_type == "PUT":
            return "ITM" if strike >= spot else "OTM"
    return "MID"


def make_option_features(
    option_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    volume_lookback: int = 20,
) -> pd.DataFrame:
    """Merge option chain snapshot with equity context and derived signals.

    Args:
        option_df: Option chain data.
        equity_df: Equity OHLCV data.
        volume_lookback: Volume lookback period.

    Returns:
        DataFrame with engineered features.
    """
    if option_df is None or option_df.empty:
        return pd.DataFrame()

    latest_equity = pd.DataFrame()
    if equity_df is not None and not equity_df.empty:
        equity_df = _calc_returns(equity_df)
        latest_equity = (
            equity_df.sort_values("date").groupby("symbol").tail(1).set_index("symbol")
        )

    df = option_df.copy()
    df["symbol"] = df["symbol"].str.upper()
    df["volume"] = pd.to_numeric(df.get("volume"), errors="coerce").fillna(0.0)
    df["open_interest"] = pd.to_numeric(df.get("open_interest"), errors="coerce").fillna(0.0)
    df["implied_vol"] = pd.to_numeric(df.get("implied_vol"), errors="coerce").fillna(np.nan)
    df["strike"] = pd.to_numeric(df.get("strike"), errors="coerce")

    spot_fallback = pd.to_numeric(df.get("underlyingPrice"), errors="coerce")
    df["underlying_price"] = (
        df["symbol"].map(latest_equity["close"]) if not latest_equity.empty else np.nan
    )
    if spot_fallback is not None:
        df["underlying_price"] = df["underlying_price"].fillna(spot_fallback)

    quote_raw = df["quote_date"] if "quote_date" in df else pd.Series(pd.Timestamp.utcnow(), index=df.index)
    quote_series = pd.to_datetime(quote_raw, utc=True, errors="coerce")
    df["quote_date"] = quote_series.dt.tz_convert(None)
    exp_raw = df.get("expiration")
    exp_series = pd.to_datetime(exp_raw, utc=True, errors="coerce")
    df["expiration"] = exp_series.dt.tz_convert(None)
    df = df.dropna(subset=["underlying_price", "expiration", "strike", "option_type", "quote_date"])

    df["maturity_days"] = (df["expiration"].dt.tz_localize(None) - df["quote_date"]).dt.days
    df = df[df["maturity_days"] > 0]
    df["moneyness"] = (df["strike"] - df["underlying_price"]) / df["underlying_price"]
    df["abs_moneyness"] = df["moneyness"].abs()
    df["moneyness_bucket"] = df["abs_moneyness"].apply(_bucket_moneyness)
    df["volume_oi_ratio"] = df["volume"] / df["open_interest"].clip(lower=1)

    baseline = (
        df.groupby(["symbol", "option_type", "moneyness_bucket"])["volume"]
        .transform("median")
        .replace(0, np.nan)
        .fillna(df["volume"].median())
        .clip(lower=1)
    )
    df["unusual_volume"] = df["volume"] / baseline

    df["delta_bucket"] = df.apply(_infer_delta_bucket, axis=1)
    df["iv_zscore"] = df.groupby(["symbol", "expiration"])["implied_vol"].transform(
        lambda s: (s - s.mean()) / max(s.std(ddof=0), 1e-6)
    )

    if not latest_equity.empty:
        context_cols = latest_equity[["ret_1d", "ret_5d", "vol_of_underlying"]]
        df = df.merge(
            context_cols, left_on="symbol", right_index=True, how="left", suffixes=("", "_ctx")
        )
        df["ret_1d"] = df["ret_1d"].fillna(0.0)
        df["ret_5d"] = df["ret_5d"].fillna(0.0)
        df["vol_of_underlying"] = df["vol_of_underlying"].fillna(df["vol_of_underlying"].median())
    else:
        df["ret_1d"] = 0.0
        df["ret_5d"] = 0.0
        df["vol_of_underlying"] = 0.0

    # Skew proxy per expiry
    df["skew_proxy"] = np.nan
    for (symbol, exp), bucket in df.groupby(["symbol", "expiration"]):
        spot = bucket["underlying_price"].iloc[0]
        calls = bucket[(bucket["option_type"].str.upper() == "CALL") & (bucket["strike"] > spot)]
        puts = bucket[(bucket["option_type"].str.upper() == "PUT") & (bucket["strike"] < spot)]
        call_iv = calls["implied_vol"].median()
        put_iv = puts["implied_vol"].median()
        skew = np.nan
        if pd.notna(call_iv) and pd.notna(put_iv):
            skew = call_iv - put_iv
        df.loc[bucket.index, "skew_proxy"] = skew

    df["context_missing"] = latest_equity.empty
    return df
