"""Main async runner — starts all sources + agent concurrently.

Usage:
  python -m src.runner                   # all modules
  python -m src.runner --modules rss,binance,deribit
  python -m src.runner --mock            # mock mode (no real APIs needed)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def _run_all(modules: set[str], mock: bool) -> None:
    tasks = []

    # ── Agent orchestrator ────────────────────────────────────────────────
    provider = os.getenv("LLM_PROVIDER", "claude")
    key_map = {
        "claude": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
        "openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY",
        "local": None,
    }
    required_key = key_map.get(provider)
    if required_key is None or os.getenv(required_key):
        try:
            from src.agent.orchestrator import orchestrator
            tasks.append(asyncio.create_task(orchestrator.run(), name="agent"))
            logger.info(f"[Runner] Agent orchestrator: ON ({provider})")
        except Exception as exc:
            logger.warning(f"[Runner] Agent failed to init: {exc}")
    else:
        logger.warning(f"[Runner] {required_key} not set — agent disabled")

    # ── RSS ───────────────────────────────────────────────────────────────
    if "rss" in modules:
        from src.sources.rss.harvester import run_rss_harvester
        tasks.append(asyncio.create_task(run_rss_harvester(), name="rss"))
        logger.info("[Runner] RSS harvester: ON")

    # ── Binance ───────────────────────────────────────────────────────────
    if "binance" in modules:
        from src.sources.binance.client import BinanceMonitor
        tasks.append(asyncio.create_task(BinanceMonitor().run(), name="binance"))
        logger.info("[Runner] Binance monitor: ON")

    # ── Deribit ───────────────────────────────────────────────────────────
    if "deribit" in modules:
        from src.sources.deribit.client import DeribitMonitor
        tasks.append(asyncio.create_task(DeribitMonitor().run(), name="deribit"))
        logger.info("[Runner] Deribit monitor: ON")

    # ── Polymarket ────────────────────────────────────────────────────────
    if "polymarket" in modules:
        from src.sources.polymarket.client import PolymarketMonitor
        tasks.append(asyncio.create_task(PolymarketMonitor().run(), name="polymarket"))
        logger.info("[Runner] Polymarket monitor: ON")

    # ── AIS maritime ─────────────────────────────────────────────────────
    if "ais" in modules:
        from src.sources.ais.client import make_ais_monitor
        ais = make_ais_monitor()
        if ais:
            tasks.append(asyncio.create_task(ais.run(), name="ais"))
            logger.info("[Runner] AIS maritime: ON")
        else:
            logger.warning("[Runner] AIS: AISSTREAM_API_KEY not set — skipped")

    # ── FastAPI (signal ingestion + feed endpoint) ────────────────────────
    tasks.append(asyncio.create_task(_run_api(), name="api"))
    logger.info("[Runner] FastAPI: ON → http://localhost:8000")

    logger.info(f"[Runner] {len(tasks)} tasks running — Ctrl+C to stop\n")

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("[Runner] Shutting down...")


async def _run_api() -> None:
    import uvicorn
    # Import app with feed endpoint added
    from src.api.server import app
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Vortex Analytica runner")
    parser.add_argument(
        "--modules", default="rss,binance,deribit,polymarket,ais",
        help="Comma-separated list of modules to run",
    )
    parser.add_argument("--mock", action="store_true", help="Mock mode — no real API calls")
    args = parser.parse_args()

    modules = set(args.modules.split(","))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _shutdown(sig, frame):
        logger.info(f"[Runner] Signal {sig} received — stopping")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        loop.run_until_complete(_run_all(modules, args.mock))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
