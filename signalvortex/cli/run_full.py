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

        except Exception as e:
            LOGGER.error(f"Crypto analysis failed: {e}")

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
