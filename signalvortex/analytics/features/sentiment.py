"""Sentiment and insider enrichment utilities."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

import numpy as np
import pandas as pd


def _zscore(series: pd.Series) -> pd.Series:
    """Calculate z-score for a series."""
    std = series.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - series.mean()) / std


def _prepare_social(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare social sentiment data."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    grouped = (
        df.groupby(["symbol", df["date"].dt.date])
        .agg(
            reddit_score=("redditScore", "sum"),
            reddit_volume=("redditMentions", "sum"),
            stocktwits_score=("stocktwitsScore", "sum"),
            stocktwits_volume=("stocktwitsMentions", "sum"),
        )
        .reset_index()
    )
    grouped.rename(columns={"date": "quote_date"}, inplace=True)
    return grouped


def _prepare_news(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare news sentiment data."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["quote_date"] = pd.to_datetime(df["date"]).dt.date
    score_cols = [c for c in df.columns if "score" in c.lower() or c in {"buzz"}]
    if "news_score" not in df:
        if "score" in df:
            df["news_score"] = df["score"]
        elif score_cols:
            df["news_score"] = df[score_cols].mean(axis=1)
        else:
            df["news_score"] = 0.0
    return df[["symbol", "quote_date", "news_score"]]


def _prepare_insiders(df: pd.DataFrame, window_days: int = 30) -> pd.DataFrame:
    """Prepare insider transaction data."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["symbol", "insider_net_shares_30d", "insider_trades_30d"])
    df = df.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    cutoff = df["transaction_date"].max() - timedelta(days=window_days)
    df = df[df["transaction_date"] >= cutoff]
    df["net_shares"] = pd.to_numeric(df.get("change"), errors="coerce").fillna(0.0)
    summary = (
        df.groupby("symbol")
        .agg(
            insider_net_shares_30d=("net_shares", "sum"),
            insider_trades_30d=("transaction_date", "count"),
        )
        .reset_index()
    )
    return summary


def merge_sentiment(
    option_features: pd.DataFrame,
    social_df: pd.DataFrame,
    news_df: pd.DataFrame,
    insider_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge sentiment data into option features.

    Args:
        option_features: DataFrame with option features.
        social_df: Social sentiment data (Reddit, StockTwits).
        news_df: News sentiment data.
        insider_df: Insider transaction data.

    Returns:
        DataFrame with sentiment features merged.
    """
    if option_features.empty:
        return option_features

    df = option_features.copy()
    df["quote_day"] = df["quote_date"].dt.date

    social = _prepare_social(social_df)
    news = _prepare_news(news_df)
    insiders = _prepare_insiders(insider_df)

    if not social.empty:
        social["reddit_z"] = social.groupby("symbol")["reddit_score"].transform(_zscore)
        social["stocktwits_z"] = social.groupby("symbol")["stocktwits_score"].transform(_zscore)
        df = df.merge(
            social,
            left_on=["symbol", "quote_day"],
            right_on=["symbol", "quote_date"],
            how="left",
            suffixes=("", "_social"),
        )
    else:
        df["reddit_z"] = 0.0
        df["stocktwits_z"] = 0.0

    if not news.empty:
        news["news_z"] = news.groupby("symbol")["news_score"].transform(_zscore)
        df = df.merge(
            news[["symbol", "quote_date", "news_z"]],
            left_on=["symbol", "quote_day"],
            right_on=["symbol", "quote_date"],
            how="left",
            suffixes=("", "_news"),
        )
    else:
        df["news_z"] = 0.0

    df["reddit_z"] = df.get("reddit_z", 0).fillna(0.0)
    df["stocktwits_z"] = df.get("stocktwits_z", 0).fillna(0.0)
    df["news_z"] = df.get("news_z", 0).fillna(0.0)

    df["sentiment_score"] = (
        0.4 * df["reddit_z"] + 0.3 * df["stocktwits_z"] + 0.3 * df["news_z"]
    )

    if not insiders.empty:
        df = df.merge(insiders, on="symbol", how="left")
    else:
        df["insider_net_shares_30d"] = 0.0
        df["insider_trades_30d"] = 0

    df["insider_net_shares_30d"] = df["insider_net_shares_30d"].fillna(0.0)
    df["insider_trades_30d"] = df["insider_trades_30d"].fillna(0)
    df.drop(columns=[col for col in df.columns if col.endswith("_social") or col.endswith("_news")], inplace=True, errors="ignore")
    return df
