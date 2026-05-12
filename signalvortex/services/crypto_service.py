"""Crypto analysis service.

Centralizes logic for crypto market analysis, handling data fetching,
processing, and error handling.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

import pandas as pd

from signalvortex.core.errors import AnalysisError, DataSourceError
from signalvortex.core.decorators import safe_execute
from signalvortex.sources.binance.client import BinanceFuturesClient
from signalvortex.sources.binance.options import BinanceOptionsClient
from signalvortex.analytics.ml.regime import analyze_regime, get_regime_summary
from signalvortex.analytics.crypto.funding import analyze_funding_rates, get_funding_summary
from signalvortex.analytics.crypto.taker_pressure import analyze_taker_pressure, get_pressure_summary
from signalvortex.analytics.crypto.liquidation import analyze_liquidation_risk, get_liquidation_summary
from signalvortex.analytics.crypto.confluence import analyze_multi_timeframe, get_confluence_summary
from signalvortex.analytics.crypto.correlation import analyze_cross_asset_correlation, get_correlation_summary
from signalvortex.analytics.leadlag import analyze_oi_price_leadlag

LOGGER = logging.getLogger(__name__)


class CryptoService:
    """Service for cryptocurrency market analysis."""

    def __init__(self):
        """Initialize service with clients."""
        try:
            self.futures_client = BinanceFuturesClient()
            self.options_client = BinanceOptionsClient()
        except Exception as e:
            LOGGER.error(f"Failed to initialize clients: {e}")
            raise DataSourceError("Failed to connect to exchange APIs", original_error=e)

    @safe_execute(default_return={}, log_level=logging.ERROR)
    def analyze_regime(self, symbol: str) -> Dict[str, Any]:
        """Run GMM regime classification."""
        LOGGER.info(f"Analyzing market regime for {symbol}...")
        
        # Fetch data
        try:
            klines = self.futures_client.get_klines(symbol, interval="1h", limit=200)
            oi_hist = self.futures_client.get_open_interest_hist(symbol, period="1h", limit=200)
            ls_hist = self.futures_client.get_long_short_ratio(symbol, period="1h", limit=200)
            fr_hist = self.futures_client.get_funding_rate_hist(symbol, limit=30)
        except Exception as e:
            raise DataSourceError(f"Failed to fetch regime data for {symbol}", e)

        if klines.empty:
            LOGGER.warning(f"No kline data for regime analysis of {symbol}")
            return {}

        # Merge data
        df = klines.copy()
        df = df.set_index("open_time")
        
        if not oi_hist.empty:
            oi_hist = oi_hist.set_index("timestamp")
            df["oi"] = oi_hist["sumOpenInterestValue"].reindex(df.index, method="ffill")
            df["oi_change"] = df["oi"].pct_change()
        
        if not ls_hist.empty:
            ls_hist = ls_hist.set_index("timestamp")
            df["ls_ratio"] = ls_hist["longShortRatio"].reindex(df.index, method="ffill")
        
        if not fr_hist.empty:
            last_funding = fr_hist["fundingRate"].iloc[-1]
            df["funding_rate"] = last_funding
        
        df["momentum"] = df["close"].pct_change(6)
        df = df.reset_index()
        
        result = analyze_regime(df, n_regimes=3)
        summary = get_regime_summary(result)
        
        LOGGER.info(f"  Regime: {summary['current_regime']} ({summary['confidence']:.0%})")
        return summary

    @safe_execute(default_return={}, log_level=logging.ERROR)
    def analyze_funding(self, symbol: str) -> Dict[str, Any]:
        """Analyze Binance native funding rate."""
        LOGGER.info(f"Analyzing funding rate for {symbol}...")
        try:
            fr = self.futures_client.get_funding_rate(symbol)
            fr_hist = self.futures_client.get_funding_rate_hist(symbol, limit=60)
            
            if fr_hist.empty:
                return {}
                
            current_rate = float(fr.get("lastFundingRate", 0))
            avg_rate = fr_hist["fundingRate"].mean()
            z_score = (current_rate - avg_rate) / fr_hist["fundingRate"].std() if fr_hist["fundingRate"].std() != 0 else 0
            
            signal = "neutral"
            if z_score > 2.0:
                signal = "overleveraged_longs"
            elif z_score < -2.0:
                signal = "overleveraged_shorts"
                
            summary = {
                "symbol": symbol,
                "current_rate": f"{current_rate:.4%}",
                "z_score": round(z_score, 2),
                "signal": signal,
                "apr": f"{current_rate * 3 * 365:.1%}"
            }
            
            LOGGER.info(f"  Funding: {summary['current_rate']} (Z: {summary['z_score']}) -> {signal}")
            return summary
        except Exception as e:
            raise DataSourceError(f"Funding analysis failed for {symbol}", e)

    @safe_execute(default_return={}, log_level=logging.ERROR)
    def analyze_options(self, symbol: str) -> Dict[str, Any]:
        """Analyze Binance Options (IV, PCR)."""
        underlying = symbol.replace("USDT", "").replace("USD", "")
        LOGGER.info(f"Analyzing options for {underlying}...")
        
        try:
            # Check availability
            idx = self.options_client.get_underlying_index(f"{underlying}USDT")
            if not idx:
                LOGGER.info("  No options data available.")
                return {}
                
            pc_ratio = self.options_client.get_put_call_ratio(f"{underlying}USDT")
            chain = self.options_client.get_option_chain(f"{underlying}USDT")
            
            summary = {
                "underlying": underlying,
                "index_price": float(idx.get("indexPrice", 0)),
                "put_call_ratio": pc_ratio.get("put_call_ratio", 0),
                "call_count": pc_ratio.get("call_count", 0),
                "put_count": pc_ratio.get("put_count", 0),
                "chain_size": len(chain)
            }
            
            LOGGER.info(f"  Options: PCR {summary['put_call_ratio']:.2f}, Chain: {summary['chain_size']}")
            return summary
        except Exception as e:
            LOGGER.warning(f"Options analysis failed: {e}")
            return {}

    @safe_execute(default_return={}, log_level=logging.ERROR)
    def analyze_liquidation(self, symbol: str) -> Dict[str, Any]:
        """Run liquidation cascade detection."""
        LOGGER.info(f"Analyzing liquidation risk for {symbol}...")
        result = analyze_liquidation_risk(symbol, binance_client=self.futures_client)
        summary = get_liquidation_summary(result)
        LOGGER.info(f"  Liq Risk: {summary['risk_level']} ({summary['risk_score']})")
        return summary

    @safe_execute(default_return={}, log_level=logging.ERROR)
    def analyze_taker_pressure(self, symbol: str) -> Dict[str, Any]:
        """Run taker pressure analysis."""
        LOGGER.info(f"Analyzing taker pressure for {symbol}...")
        result = analyze_taker_pressure(symbol, client=self.futures_client)
        summary = get_pressure_summary(result)
        LOGGER.info(f"  Pressure: {summary['signal']} (Z: {summary['zscore']})")
        return summary

    @safe_execute(default_return={}, log_level=logging.ERROR)
    def analyze_confluence(self, symbol: str) -> Dict[str, Any]:
        """Run multi-TF confluence analysis."""
        LOGGER.info(f"Analyzing confluence for {symbol}...")
        result = analyze_multi_timeframe(symbol, client=self.futures_client)
        summary = get_confluence_summary(result)
        LOGGER.info(f"  Confluence: {summary['overall_bias']} ({summary['confluence_score']})")
        return summary

    @safe_execute(default_return={}, log_level=logging.ERROR)
    def analyze_lead_lag(self, symbol: str) -> Dict[str, Any]:
        """Run lead-lag analysis."""
        LOGGER.info(f"Analyzing lead-lag for {symbol}...")
        result = analyze_oi_price_leadlag(symbol, client=self.futures_client)
        summary = {
             "symbol": symbol,
             "oi_correlation": result.oi_correlation,
             "ratio_correlation": result.ratio_correlation,
             "sample_count": result.sample_count,
        }
        LOGGER.info(f"  Lead-Lag: OI Corr {summary['oi_correlation']:.4f}")
        return summary
    
    @safe_execute(default_return={}, log_level=logging.ERROR)
    def analyze_correlations(self, symbols: List[str]) -> Dict[str, Any]:
        """Run correlation matrix analysis."""
        LOGGER.info(f"Analyzing correlations for {len(symbols)} symbols...")
        result = analyze_cross_asset_correlation(symbols, client=self.futures_client)
        return get_correlation_summary(result)
