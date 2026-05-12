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
from .feeds import FEEDS, KEYWORD_RULES, KeywordRule

logger = logging.getLogger(__name__)

_SEEN: Set[str] = set()          # deduplicate by article hash
_SEEN_MAX = 10_000

_SEVERITY_ORDER = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]


def _article_hash(entry: dict) -> str:
    key = (entry.get("link") or entry.get("title") or "")
    return hashlib.md5(key.encode()).hexdigest()


def _match_rules(text: str) -> List[KeywordRule]:
    """Return all KeywordRules whose keywords appear in text (one per category max)."""
    text_lower = text.lower()
    seen_categories: set = set()
    matched = []
    for rule in KEYWORD_RULES:
        if rule.category in seen_categories:
            continue
        if any(kw in text_lower for kw in rule.keywords):
            matched.append(rule)
            seen_categories.add(rule.category)
    return matched


def _severity_from_rules(rules: List[KeywordRule]) -> Severity:
    if not rules:
        return Severity.LOW
    return max((r.min_severity for r in rules), key=lambda s: _SEVERITY_ORDER.index(s))


def _instruments_from_rules(rules: List[KeywordRule]) -> List[str]:
    instruments: set = set()
    for rule in rules:
        instruments.update(rule.instruments)
    return sorted(instruments)


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

                    matched_rules = _match_rules(full_text)
                    severity = _severity_from_rules(matched_rules)
                    instruments = _instruments_from_rules(matched_rules)
                    categories = [r.category for r in matched_rules]

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
                            "categories": categories,
                            "instruments": instruments,
                        },
                        tags=feed_cfg["tags"] + categories,
                    )
                    await bus.publish_raw(raw)

                    if matched_rules:
                        signal = Signal(
                            signal_id=f"rss_{art_hash}",
                            source="rss",
                            domain=Domain.NEWS,
                            title=f"[NEWS] {title[:120]}",
                            severity=severity,
                            value=1.0,
                            context={
                                "categories": categories,
                                "instruments": instruments,
                                "feed_tags": feed_cfg["tags"],
                                "link": entry.get("link", ""),
                                "summary": summary[:300],
                            },
                        )
                        await bus.publish_signal(signal)

            logger.info(f"[RSS] Cycle done — {new_articles} new articles, next in {interval}s")
            await asyncio.sleep(interval)
