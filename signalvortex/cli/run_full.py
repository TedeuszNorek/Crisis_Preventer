"""Unified SignalVortex analysis CLI.

Refactored to use CryptoService for centralized logic and error handling.
"""

from __future__ import annotations

import argparse
import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, Dict, Any

from signalvortex.core.config import Config
from signalvortex.services.crypto_service import CryptoService
from signalvortex.core.errors import SignalVortexError

LOGGER = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Silence third-party libs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="SignalVortex: Multi-source market analytics (ML-enhanced)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Symbol inputs
    parser.add_argument("--symbol", help="Equity symbol (e.g. AAPL)")
    parser.add_argument("--crypto", help="Crypto symbol (e.g. BTCUSDT)")
    
    # Analysis Flags
    parser.add_argument("--regime", action="store_true", help="ML Regime Classification")
    parser.add_argument("--binance-funding", action="store_true", help="Binance Native Funding")
    parser.add_argument("--binance-options", action="store_true", help="Binance Options (IV, PCR)")
    parser.add_argument("--taker-pressure", action="store_true", help="Taker Pressure Analysis")
    parser.add_argument("--liquidation", action="store_true", help="Liquidation Risk Analysis")
    parser.add_argument("--multi-tf", action="store_true", help="Multi-TF Confluence")
    parser.add_argument("--correlation", nargs="*", help="Correlation Matrix")
    parser.add_argument("--macro", action="store_true", help="Macro Analysis (M2/M3)")
    parser.add_argument("--funding", action="store_true", help="Coinalyze Funding (Legacy)")

    # Output
    parser.add_argument("--output", "-o", type=Path, help="Output dir")
    parser.add_argument("--no-plot", action="store_true", help="Skip plotting")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    # Options specifics
    parser.add_argument("--strike-points", type=int, default=40)
    parser.add_argument("--maturity-points", type=int, default=40)
    parser.add_argument("--date", help="Valuation date")

    return parser.parse_args(argv)


def run_crypto_analysis(args: argparse.Namespace, results: Dict[str, Any]) -> None:
    """Run crypto analysis using Service Layer."""
    if not (args.crypto or args.correlation):
        return

    LOGGER.info("Initializing Crypto Service...")
    try:
        service = CryptoService()
    except Exception as e:
        LOGGER.error(f"Failed to initialize CryptoService: {e}")
        return

    if args.crypto:
        symbol = args.crypto.upper()
        
        # Lead-Lag (Default)
        results["crypto_lead_lag"] = service.analyze_lead_lag(symbol)

        # ML Regime
        if args.regime:
            results["regime"] = service.analyze_regime(symbol)

        # Funding
        if args.binance_funding:
            results["binance_funding"] = service.analyze_funding(symbol)

        # Options
        if args.binance_options:
            results["binance_options"] = service.analyze_options(symbol)

        # Liquidation
        if args.liquidation:
            results["liquidation"] = service.analyze_liquidation(symbol)

        # Taker Pressure
        if args.taker_pressure:
            results["taker_pressure"] = service.analyze_taker_pressure(symbol)

        # Multi-TF
        if args.multi_tf:
            results["confluence"] = service.analyze_confluence(symbol)

    # Correlation
    if args.correlation:
        symbols = args.correlation if len(args.correlation) > 1 else ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        results["correlation"] = service.analyze_correlations(symbols)


def run_equity_options(args: argparse.Namespace, config: Config, output_dir: Path, results: Dict[str, Any]) -> None:
    """Run equity options analysis (Legacy implementation)."""
    if not args.symbol:
        return

    if not config.polygon.api_key:
        LOGGER.error("POLYGON_API_KEY required for options analysis")
        return

    LOGGER.info(f"Analyzing equity options for {args.symbol}...")
    try:
        from signalvortex.sources.polygon import PolygonClient
        from signalvortex.analytics.volatility import build_iv_surface, detect_anomalies
        
        client = PolygonClient(config.polygon.api_key)
        df, spot = client.fetch_option_chain(args.symbol, valuation_date=args.date)
        LOGGER.info(f"Fetched {len(df)} contracts (Spot: {spot:.2f})")

        strike_grid, maturity_grid, iv_grid, _, _ = build_iv_surface(
            df, strike_points=args.strike_points, maturity_points=args.maturity_points
        )
        
        anomalies = detect_anomalies(df, strike_grid, maturity_grid, iv_grid)
        results["equity_options"] = {
            "symbol": args.symbol,
            "spot": spot,
            "anomalies": len(anomalies)
        }
        
        if not args.no_plot:
            from signalvortex.analytics.volatility import plot_surface
            plot_path = output_dir / f"{args.symbol}_surface.png"
            plot_surface(strike_grid, maturity_grid, iv_grid, title=f"{args.symbol} IV", save_path=str(plot_path))
            
    except Exception as e:
        LOGGER.error(f"Equity options failed: {e}")


def run_macro_analysis(args: argparse.Namespace, config: Config, output_dir: Path, results: Dict[str, Any]) -> None:
    """Run macro analysis."""
    if not args.macro:
        return

    if not config.fred.api_key:
        LOGGER.error("FRED_API_KEY required for macro")
        return

    LOGGER.info("Running Macro Analysis...")
    try:
        from signalvortex.analytics.monetary import collect_monetary_aggregates, compute_growth, get_latest_growth_rates
        df = collect_monetary_aggregates(config.fred.api_key)
        df = compute_growth(df)
        results["macro"] = get_latest_growth_rates(df)
        df.to_csv(output_dir / "macro_data.csv", index=False)
    except Exception as e:
        LOGGER.error(f"Macro analysis failed: {e}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main entry point."""
    args = parse_args(argv)
    setup_logging(args.verbose)
    
    LOGGER.info("SignalVortex Starting (Refactored Core)...")
    
    config = Config.load()
    output_dir = args.output or Path("./data")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}

    # Run Analysis Modules
    run_crypto_analysis(args, results)
    run_equity_options(args, config, output_dir, results)
    run_macro_analysis(args, config, output_dir, results)

    # Save Summary
    if results:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_path = output_dir / f"signalvortex_summary_{timestamp}.json"
        with open(summary_path, "w") as f:
            json.dump(results, f, indent=2)
        LOGGER.info(f"Results saved to {summary_path}")
    else:
        LOGGER.warning("No results generated.")

    LOGGER.info("Done.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
