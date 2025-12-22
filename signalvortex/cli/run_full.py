"""Unified SignalVortex analysis CLI."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from signalvortex.core.config import Config

LOGGER = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="SignalVortex: Multi-source market analytics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  signalvortex --symbol AAPL --crypto BTCUSDT
  signalvortex --symbol AAPL --no-crypto --output data/
  signalvortex --crypto BTCUSDT --no-options --macro
        """,
    )

    # Symbol inputs
    parser.add_argument(
        "--symbol",
        help="Equity symbol for options analysis (e.g., AAPL)",
    )
    parser.add_argument(
        "--crypto",
        help="Crypto symbol for futures analysis (e.g., BTCUSDT)",
    )

    # Module toggles
    parser.add_argument(
        "--no-options",
        action="store_true",
        help="Skip equity options analysis",
    )
    parser.add_argument(
        "--no-crypto",
        action="store_true",
        help="Skip crypto futures analysis",
    )
    parser.add_argument(
        "--macro",
        action="store_true",
        help="Include monetary aggregates (M2/M3) analysis",
    )

    # Options-specific
    parser.add_argument(
        "--date",
        help="Valuation date for options (YYYY-MM-DD, default: today)",
    )
    parser.add_argument(
        "--strike-points",
        type=int,
        default=40,
        help="Number of strike grid points for IV surface (default: 40)",
    )
    parser.add_argument(
        "--maturity-points",
        type=int,
        default=40,
        help="Number of maturity grid points for IV surface (default: 40)",
    )

    # Crypto-specific
    parser.add_argument(
        "--interval",
        default="5m",
        help="Time interval for crypto analysis (default: 5m)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="Number of data points for lead-lag analysis (default: 300)",
    )
    parser.add_argument(
        "--funding",
        action="store_true",
        help="Include funding rate analysis (requires Coinalyze API)",
    )
    parser.add_argument(
        "--taker-pressure",
        action="store_true",
        help="Include taker buy/sell pressure analysis",
    )
    parser.add_argument(
        "--correlation",
        nargs="*",
        metavar="SYMBOL",
        help="Cross-asset correlation analysis (e.g., --correlation BTCUSDT ETHUSDT SOLUSDT)",
    )
    parser.add_argument(
        "--liquidation",
        action="store_true",
        help="Include liquidation cascade risk analysis",
    )
    parser.add_argument(
        "--multi-tf",
        action="store_true",
        help="Multi-timeframe confluence analysis (5m, 1h, 4h)",
    )
    parser.add_argument(
        "--binance-options",
        action="store_true",
        help="Binance Options analysis (IV, Greeks, P/C ratio) - uses --crypto symbol",
    )
    parser.add_argument(
        "--binance-funding",
        action="store_true",
        help="Binance native funding rate (alternative to Coinalyze)",
    )

    # Output
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output directory for results (default: ./data)",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip generating plots",
    )

    # General
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main entry point for SignalVortex CLI."""
    args = parse_args(argv)
    setup_logging(args.verbose)

    LOGGER.info("SignalVortex starting...")

    # Load configuration
    config = Config.load()
    missing = config.validate()
    if missing:
        LOGGER.warning(f"Missing API keys: {', '.join(missing)}")

    output_dir = args.output or config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {}

    # === Options Analysis ===
    if args.symbol and not args.no_options:
        if not config.polygon.api_key:
            LOGGER.error("POLYGON_API_KEY required for options analysis")
        else:
            LOGGER.info(f"Analyzing options for {args.symbol}...")
            try:
                from signalvortex.sources.polygon import PolygonClient
                from signalvortex.analytics.volatility import build_iv_surface, detect_anomalies

                client = PolygonClient(config.polygon.api_key)
                df, spot = client.fetch_option_chain(args.symbol, valuation_date=args.date)
                LOGGER.info(f"Fetched {len(df)} options (spot={spot:.2f})")

                strike_grid, maturity_grid, iv_grid, skew_grid, term_grid = build_iv_surface(
                    df,
                    strike_points=args.strike_points,
                    maturity_points=args.maturity_points,
                )

                LOGGER.info(f"IV range: {iv_grid.min():.4f} - {iv_grid.max():.4f}")

                anomalies = detect_anomalies(df, strike_grid, maturity_grid, iv_grid)
                if not anomalies.empty:
                    anomaly_path = output_dir / f"{args.symbol}_anomalies_{timestamp}.csv"
                    anomalies.to_csv(anomaly_path, index=False)
                    LOGGER.info(f"Found {len(anomalies)} anomalies, saved to {anomaly_path}")

                results["options"] = {
                    "symbol": args.symbol,
                    "spot": spot,
                    "options_count": len(df),
                    "anomalies_count": len(anomalies),
                    "iv_min": float(iv_grid.min()),
                    "iv_max": float(iv_grid.max()),
                }

                if not args.no_plot:
                    from signalvortex.analytics.volatility import plot_surface
                    plot_path = output_dir / f"{args.symbol}_surface_{timestamp}.png"
                    plot_surface(
                        strike_grid, maturity_grid, iv_grid,
                        title=f"{args.symbol} IV Surface ({args.date or 'latest'})",
                        save_path=str(plot_path),
                    )

            except Exception as e:
                LOGGER.error(f"Options analysis failed: {e}")

    # === Crypto Analysis ===
    if args.crypto and not args.no_crypto:
        LOGGER.info(f"Analyzing crypto futures for {args.crypto}...")
        try:
            from signalvortex.sources.binance import BinanceFuturesClient
            from signalvortex.analytics.leadlag import analyze_oi_price_leadlag

            client = BinanceFuturesClient()
            result = analyze_oi_price_leadlag(
                args.crypto,
                interval=args.interval,
                limit=args.limit,
                client=client,
            )

            LOGGER.info(f"Lead-lag analysis ({result.sample_count} samples):")
            LOGGER.info(f"  OI correlation: {result.oi_correlation:.4f}")
            LOGGER.info(f"  L/S ratio correlation: {result.ratio_correlation:.4f}")
            LOGGER.info(f"  OI top quartile return: {result.oi_top_quartile_return:.4%}")
            LOGGER.info(f"  OI bottom quartile return: {result.oi_bottom_quartile_return:.4%}")

            results["crypto"] = {
                "symbol": args.crypto,
                "oi_correlation": result.oi_correlation,
                "ratio_correlation": result.ratio_correlation,
                "sample_count": result.sample_count,
            }

            # Taker Pressure Analysis
            if args.taker_pressure:
                LOGGER.info(f"Analyzing taker pressure for {args.crypto}...")
                from signalvortex.analytics.crypto import analyze_taker_pressure, get_pressure_summary
                pressure = analyze_taker_pressure(args.crypto, interval=args.interval, client=client)
                summary = get_pressure_summary(pressure)
                LOGGER.info(f"  Current ratio: {summary['current_buy_sell_ratio']}")
                LOGGER.info(f"  Signal: {summary['signal']}")
                LOGGER.info(f"  {summary['interpretation']}")
                results["taker_pressure"] = summary

        except Exception as e:
            LOGGER.error(f"Crypto analysis failed: {e}")

    # === Funding Rate Analysis ===
    if args.crypto and getattr(args, 'funding', False):
        if not config.coinalyze.api_key:
            LOGGER.error("COINALYZE_API_KEY required for funding analysis")
        else:
            LOGGER.info(f"Analyzing funding rates for {args.crypto}...")
            try:
                from signalvortex.analytics.crypto import analyze_funding_rates, get_funding_summary
                # Convert symbol format: BTCUSDT -> BTCUSDT_PERP.A
                coinalyze_symbol = f"{args.crypto}_PERP.A" if not args.crypto.endswith(".A") else args.crypto
                funding = analyze_funding_rates(coinalyze_symbol, api_key=config.coinalyze.api_key)
                summary = get_funding_summary(funding)
                LOGGER.info(f"  Current rate: {summary['current_funding_rate']}")
                LOGGER.info(f"  Signal: {summary['signal']}")
                LOGGER.info(f"  {summary['interpretation']}")
                results["funding"] = summary
            except Exception as e:
                LOGGER.error(f"Funding analysis failed: {e}")

    # === Cross-Asset Correlation Analysis ===
    if getattr(args, 'correlation', None) is not None:
        symbols = args.correlation if args.correlation else ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        if len(symbols) < 2:
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        LOGGER.info(f"Analyzing cross-asset correlation for {', '.join(symbols)}...")
        try:
            from signalvortex.analytics.crypto import analyze_cross_asset_correlation, get_correlation_summary
            correlation_result = analyze_cross_asset_correlation(symbols, interval=args.interval)
            summary = get_correlation_summary(correlation_result)
            LOGGER.info(f"  Regime: {summary['regime']}")
            for pair, corr in summary.get('current_correlations', {}).items():
                LOGGER.info(f"  {pair}: {corr}")
            if summary['breakdowns']:
                LOGGER.info(f"  ⚠️ {len(summary['breakdowns'])} correlation breakdown(s) detected")
            LOGGER.info(f"  {summary['interpretation']}")
            results["correlation"] = summary
        except Exception as e:
            LOGGER.error(f"Correlation analysis failed: {e}")

    # === Liquidation Cascade Risk Analysis ===
    if args.crypto and getattr(args, 'liquidation', False):
        LOGGER.info(f"Analyzing liquidation cascade risk for {args.crypto}...")
        try:
            from signalvortex.analytics.crypto import analyze_liquidation_risk, get_liquidation_summary
            liq_result = analyze_liquidation_risk(
                args.crypto,
                interval=args.interval,
                coinalyze_api_key=config.coinalyze.api_key if config.coinalyze.api_key else None,
            )
            summary = get_liquidation_summary(liq_result)
            LOGGER.info(f"  Risk Score: {summary['risk_score']} ({summary['risk_level']})")
            LOGGER.info(f"  Direction: {summary['direction']}")
            LOGGER.info(f"  OI Change 24h: {summary['oi_change_24h']}")
            LOGGER.info(f"  {summary['interpretation']}")
            results["liquidation"] = summary
        except Exception as e:
            LOGGER.error(f"Liquidation analysis failed: {e}")

    # === Multi-Timeframe Confluence Analysis ===
    if args.crypto and getattr(args, 'multi_tf', False):
        LOGGER.info(f"Analyzing multi-timeframe confluence for {args.crypto}...")
        try:
            from signalvortex.analytics.crypto import analyze_multi_timeframe, get_confluence_summary
            confluence_result = analyze_multi_timeframe(args.crypto, timeframes=["5m", "1h", "4h"])
            summary = get_confluence_summary(confluence_result)
            
            LOGGER.info(f"  Confluence Score: {summary['confluence_score']} ({summary['confluence_strength']})")
            LOGGER.info(f"  Overall Bias: {summary['overall_bias'].upper()}")
            LOGGER.info(f"  Aligned TFs: {summary['aligned_timeframes']}")
            for tf, details in summary.get('timeframes', {}).items():
                emoji = "🟢" if details['bias'] == 'bullish' else "🔴" if details['bias'] == 'bearish' else "⚪"
                LOGGER.info(f"    {tf}: {emoji} {details['bias']} ({details['strength']:.2f})")
            LOGGER.info(f"  {summary['interpretation']}")
            results["confluence"] = summary
        except Exception as e:
            LOGGER.error(f"Multi-TF confluence analysis failed: {e}")

    # === Binance Native Funding Rate ===
    if args.crypto and getattr(args, 'binance_funding', False):
        LOGGER.info(f"Fetching Binance native funding rate for {args.crypto}...")
        try:
            from signalvortex.sources.binance import BinanceFuturesClient
            fc = BinanceFuturesClient()
            fr = fc.get_funding_rate(args.crypto)
            fr_hist = fc.get_funding_rate_hist(args.crypto, limit=30)
            
            current_rate = float(fr.get("lastFundingRate", 0))
            avg_rate = fr_hist["fundingRate"].mean() if not fr_hist.empty else current_rate
            
            LOGGER.info(f"  Current Rate: {current_rate:.4%} (per 8h)")
            LOGGER.info(f"  30-day Avg: {avg_rate:.4%}")
            LOGGER.info(f"  APR: {current_rate * 3 * 365:.1%}")
            
            signal = "neutral"
            if current_rate > 0.0005:
                signal = "overleveraged_longs"
                LOGGER.info("  ⚠️ HIGH FUNDING: Longs paying premium")
            elif current_rate < -0.0003:
                signal = "overleveraged_shorts"
                LOGGER.info("  ⚠️ NEGATIVE FUNDING: Shorts paying premium")
            else:
                LOGGER.info("  ✅ NEUTRAL: Balanced funding")
            
            results["binance_funding"] = {
                "symbol": args.crypto,
                "current_rate": f"{current_rate:.4%}",
                "avg_30d": f"{avg_rate:.4%}",
                "apr": f"{current_rate * 3 * 365:.1%}",
                "signal": signal,
            }
        except Exception as e:
            LOGGER.error(f"Binance funding rate failed: {e}")

    # === Binance Options Analysis ===
    if args.crypto and getattr(args, 'binance_options', False):
        # Extract base asset from symbol (BTCUSDT -> BTC)
        underlying = args.crypto.upper().replace("USDT", "").replace("USD", "")
        LOGGER.info(f"Analyzing Binance Options for {underlying}...")
        try:
            from signalvortex.sources.binance import BinanceOptionsClient
            oc = BinanceOptionsClient()
            
            # Index price
            idx = oc.get_underlying_index(f"{underlying}USDT")
            index_price = float(idx.get("indexPrice", 0))
            LOGGER.info(f"  Index Price: ${index_price:,.2f}")
            
            # Put/Call ratio
            pc_ratio = oc.get_put_call_ratio(f"{underlying}USDT")
            LOGGER.info(f"  Put/Call Ratio: {pc_ratio.get('put_call_ratio', 0):.2f}")
            LOGGER.info(f"  Calls: {pc_ratio.get('call_count', 0)} contracts")
            LOGGER.info(f"  Puts: {pc_ratio.get('put_count', 0)} contracts")
            
            # IV by expiry
            iv_df = oc.get_iv_by_expiry(f"{underlying}USDT")
            if not iv_df.empty:
                LOGGER.info("  IV by Expiry:")
                for _, row in iv_df.head(5).iterrows():
                    LOGGER.info(f"    {row['expiry']}: {row['avg_iv']:.1%} ({row['contract_count']} contracts)")
            
            # Option chain sample
            chain = oc.get_option_chain(f"{underlying}USDT")
            chain_count = len(chain) if not chain.empty else 0
            LOGGER.info(f"  Option Chain: {chain_count} contracts")
            
            results["binance_options"] = {
                "underlying": underlying,
                "index_price": index_price,
                "put_call_ratio": pc_ratio.get("put_call_ratio", 0),
                "call_count": pc_ratio.get("call_count", 0),
                "put_count": pc_ratio.get("put_count", 0),
                "chain_count": chain_count,
            }
        except Exception as e:
            LOGGER.error(f"Binance options analysis failed: {e}")

    # === Macro Analysis ===
    if args.macro:
        if not config.fred.api_key:
            LOGGER.error("FRED_API_KEY required for macro analysis")
        else:
            LOGGER.info("Collecting monetary aggregates...")
            try:
                from signalvortex.analytics.monetary import collect_monetary_aggregates, compute_growth

                df = collect_monetary_aggregates(config.fred.api_key)
                df = compute_growth(df)

                if not df.empty:
                    macro_path = output_dir / f"monetary_aggregates_{timestamp}.csv"
                    df.to_csv(macro_path, index=False)
                    LOGGER.info(f"Saved {len(df)} observations to {macro_path}")

                    # Log latest growth rates
                    from signalvortex.analytics.monetary.collector import get_latest_growth_rates
                    rates = get_latest_growth_rates(df)
                    for key, rate in rates.items():
                        LOGGER.info(f"  {key}: {rate:.2%} MoM")

                    results["macro"] = rates

            except Exception as e:
                LOGGER.error(f"Macro analysis failed: {e}")

    # === Summary ===
    if results:
        import json
        summary_path = output_dir / f"signalvortex_summary_{timestamp}.json"
        with open(summary_path, "w") as f:
            json.dump(results, f, indent=2)
        LOGGER.info(f"Summary saved to {summary_path}")
    else:
        LOGGER.warning("No analysis performed. Use --help to see available options.")

    LOGGER.info("SignalVortex complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
