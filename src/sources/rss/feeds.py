"""RSS feed list and keyword routing rules.

Each KeywordRule defines a semantic category: what words belong to it,
which financial instruments it affects, and the minimum severity it warrants.
The harvester uses these rules as the single source of truth — no severity
logic or keyword lists live anywhere else.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from src.core.models import Severity


@dataclass(frozen=True)
class KeywordRule:
    category: str           # semantic label used downstream by correlation rules
    keywords: List[str]     # any match → rule fires (case-insensitive substring)
    instruments: List[str]  # financial instruments to correlate
    min_severity: Severity  # floor severity for signals from this category


KEYWORD_RULES: List[KeywordRule] = [

    KeywordRule(
        category="conflict",
        keywords=[
            "war", "warfare", "invasion", "airstrike", "air strike",
            "missile strike", "military offensive", "armed conflict",
            "combat", "troops deployed", "military operation",
            "naval blockade", "escalation",
        ],
        instruments=["OIL_FUTURES", "GOLD", "AIS_GLOBAL", "BTC"],
        min_severity=Severity.HIGH,
    ),

    KeywordRule(
        category="supply_disruption",
        keywords=[
            "blockade", "sanctions", "embargo", "trade ban",
            "export ban", "supply halt", "production shutdown",
            "pipeline disruption", "refinery attack",
        ],
        instruments=["OIL_FUTURES", "GOLD", "AIS_GLOBAL", "SHIPPING_INDEX", "RUB_USD"],
        min_severity=Severity.HIGH,
    ),

    KeywordRule(
        category="maritime",
        keywords=[
            "strait", "suez", "hormuz", "malacca", "bab el-mandeb",
            "taiwan strait", "tanker", "vessel detained", "port closure",
            "shipping lane", "piracy", "hijack", "seized ship",
        ],
        instruments=["AIS_GLOBAL", "OIL_FUTURES", "SHIPPING_INDEX"],
        min_severity=Severity.MEDIUM,
    ),

    KeywordRule(
        category="monetary_policy",
        keywords=[
            "rate hike", "rate cut", "interest rate", "central bank",
            "fed funds", "federal reserve", "ecb rate", "monetary policy",
            "quantitative easing", "quantitative tightening", "balance sheet",
            "inflation target", "rate decision",
        ],
        instruments=["BTC", "GOLD", "DXY", "SP500"],
        min_severity=Severity.MEDIUM,
    ),

    KeywordRule(
        category="commodity_supply",
        keywords=[
            "drought", "harvest failure", "crop failure", "food crisis",
            "wheat supply", "grain shortage", "corn harvest",
            "agricultural disruption", "ndvi", "yield forecast",
        ],
        instruments=["WHEAT_FUTURES", "CORN_FUTURES", "COPERNICUS_NDVI"],
        min_severity=Severity.MEDIUM,
    ),

    KeywordRule(
        category="crypto_stress",
        keywords=[
            "exchange hack", "protocol exploit", "defi hack",
            "liquidation cascade", "exchange bankruptcy", "exchange insolvency",
            "stablecoin depeg", "rug pull", "bridge exploit",
        ],
        instruments=["BTC", "ETH", "DERIBIT_IV", "POLYMARKET_CRYPTO"],
        min_severity=Severity.HIGH,
    ),

    KeywordRule(
        category="political_risk",
        keywords=[
            "election result", "referendum", "snap election", "coup",
            "regime change", "political crisis", "government collapse",
            "state of emergency", "martial law",
        ],
        instruments=["BTC", "GOLD", "POLYMARKET_POLITICS"],
        min_severity=Severity.MEDIUM,
    ),

]

# ── Flat lookup (derived) — for code that needs keyword → instruments ─────────
# Generated from KEYWORD_RULES; do not edit manually.
KEYWORD_INSTRUMENT_MAP: Dict[str, List[str]] = {
    kw: rule.instruments
    for rule in KEYWORD_RULES
    for kw in rule.keywords
}

# ── RSS feed list ──────────────────────────────────────────────────────────────
FEEDS: List[Dict] = [
    # Macro / geopolitical
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",            "tags": ["macro", "geopolitical", "global"]},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "tags": ["macro", "geopolitical", "global"]},
    {"url": "https://www.reuters.com/rssFeed/worldNews",              "tags": ["macro", "geopolitical", "markets"]},

    # Energy / commodities
    {"url": "https://oilprice.com/rss/main",                          "tags": ["energy", "oil", "commodities", "maritime"]},
    {"url": "https://feeds.feedburner.com/eia-electricity",           "tags": ["energy", "macro"]},

    # Shipping / maritime
    {"url": "https://www.hellenicshippingnews.com/feed/",             "tags": ["maritime", "shipping", "ports"]},
    {"url": "https://splash247.com/feed/",                            "tags": ["maritime", "shipping"]},
    {"url": "https://www.tradewindsnews.com/rss",                     "tags": ["maritime", "shipping"]},

    # Financial markets
    {"url": "https://feeds.bloomberg.com/markets/news.rss",           "tags": ["markets", "macro", "crypto"]},
    {"url": "https://www.investing.com/rss/news.rss",                 "tags": ["markets", "macro"]},

    # Crypto
    {"url": "https://cointelegraph.com/rss",                          "tags": ["crypto", "defi", "markets"]},
    {"url": "https://decrypt.co/feed",                                "tags": ["crypto", "markets"]},

    # Conflict / defense
    {"url": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml", "tags": ["conflict", "defense", "geopolitical"]},
    {"url": "https://www.janes.com/feeds/news",                       "tags": ["conflict", "defense", "maritime"]},

    # Polish institutional (macro PL)
    {"url": "https://www.nbp.pl/rss/rss.aspx",                        "tags": ["macro", "poland", "central_bank"]},
    {"url": "https://www.knf.gov.pl/rss.xml",                         "tags": ["macro", "poland", "regulation"]},
]
