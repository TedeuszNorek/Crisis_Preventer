"""Real RSS harvester with keyword routing and sentiment tagging."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Dict, List, Optional, Set

import aiohttp
import feedparser

from src.core.event_bus import bus
from src.core.models import Domain, RawEvent, Signal, Severity
from .feeds import FEEDS, KEYWORD_INSTRUMENT_MAP

logger = logging.getLogger(__name__)

_SEEN: Set[str] = set()          # deduplicate by article hash
_SEEN_MAX = 10_000


def _article_hash(entry: dict) -> str:
    key = (entry.get("link") or entry.get("title") or "")
    return hashlib.md5(key.encode()).hexdigest()


def _keywords_in_text(text: str) -> List[str]:
    text_lower = text.lower()
    return [kw for kw in KEYWORD_INSTRUMENT_MAP if kw in text_lower]


def _severity_from_keywords(keywords: List[str]) -> Severity:
    high_risk = {"war", "blockade", "sanctions", "conflict", "hack", "liquidation"}
    medium_risk = {"strait", "port", "rate hike", "rate cut", "election", "drought"}
    if any(k in high_risk for k in keywords):
        return Severity.HIGH
    if any(k in medium_risk for k in keywords):
        return Severity.MEDIUM
    return Severity.LOW


async def _fetch_feed(session: aiohttp.ClientSession, feed_cfg: Dict) -> List[Dict]:
    url = feed_cfg["url"]
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            text = await resp.text()
        parsed = feedparser.parse(text)
        return parsed.entries
    except Exception as exc:
        logger.warning(f"[RSS] {url} failed: {exc}")
        return []


async def run_rss_harvester() -> None:
    """Long-running loop; respects bus.polling_rates['rss']."""
    logger.info("[RSS] Harvester started")
    async with aiohttp.ClientSession() as session:
        while True:
            interval = bus.polling_rates.get("rss", 300)
            new_articles = 0

            for feed_cfg in FEEDS:
                entries = await _fetch_feed(session, feed_cfg)
                for entry in entries:
                    art_hash = _article_hash(entry)
                    if art_hash in _SEEN:
                        continue

                    if len(_SEEN) >= _SEEN_MAX:
                        _SEEN.clear()
                    _SEEN.add(art_hash)
                    new_articles += 1

                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    full_text = f"{title} {summary}"
                    keywords = _keywords_in_text(full_text)
                    severity = _severity_from_keywords(keywords)

                    instruments = []
                    for kw in keywords:
                        instruments.extend(KEYWORD_INSTRUMENT_MAP.get(kw, []))
                    instruments = list(set(instruments))

                    raw = RawEvent(
                        source="rss",
                        domain=Domain.NEWS,
                        entity_id=art_hash,
                        payload={
                            "title": title,
                            "summary": summary[:500],
                            "link": entry.get("link", ""),
                            "published": entry.get("published", ""),
                            "feed_tags": feed_cfg["tags"],
                            "keywords": keywords,
                            "instruments": instruments,
                        },
                        tags=feed_cfg["tags"] + keywords,
                    )
                    await bus.publish_raw(raw)

                    if severity in (Severity.HIGH, Severity.CRITICAL) or keywords:
                        signal = Signal(
                            signal_id=f"rss_{art_hash}",
                            source="rss",
                            domain=Domain.NEWS,
                            title=f"[NEWS] {title[:120]}",
                            severity=severity,
                            value=1.0,
                            context={
                                "keywords": keywords,
                                "instruments": instruments,
                                "feed_tags": feed_cfg["tags"],
                                "link": entry.get("link", ""),
                                "summary": summary[:300],
                            },
                        )
                        await bus.publish_signal(signal)

            logger.info(f"[RSS] Cycle done — {new_articles} new articles, next in {interval}s")
            await asyncio.sleep(interval)
