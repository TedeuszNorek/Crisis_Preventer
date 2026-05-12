"""Curated RSS feed list with domain tags for routing."""
from typing import Dict, List

# Each entry: (url, tags)
# Tags drive correlation rules in the agent
FEEDS: List[Dict] = [
    # ── Macro / geopolitical ─────────────────────────────────────────────
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",       "tags": ["macro", "geopolitical", "global"]},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "tags": ["macro", "geopolitical", "global"]},
    {"url": "https://www.reuters.com/rssFeed/worldNews",          "tags": ["macro", "geopolitical", "markets"]},

    # ── Energy / commodities ─────────────────────────────────────────────
    {"url": "https://oilprice.com/rss/main",                      "tags": ["energy", "oil", "commodities", "maritime"]},
    {"url": "https://feeds.feedburner.com/eia-electricity",       "tags": ["energy", "macro"]},

    # ── Shipping / maritime ──────────────────────────────────────────────
    {"url": "https://www.hellenicshippingnews.com/feed/",         "tags": ["maritime", "shipping", "ports"]},
    {"url": "https://splash247.com/feed/",                        "tags": ["maritime", "shipping"]},
    {"url": "https://www.tradewindsnews.com/rss",                 "tags": ["maritime", "shipping"]},

    # ── Financial markets ────────────────────────────────────────────────
    {"url": "https://feeds.bloomberg.com/markets/news.rss",       "tags": ["markets", "macro", "crypto"]},
    {"url": "https://www.investing.com/rss/news.rss",             "tags": ["markets", "macro"]},

    # ── Crypto ───────────────────────────────────────────────────────────
    {"url": "https://cointelegraph.com/rss",                      "tags": ["crypto", "defi", "markets"]},
    {"url": "https://decrypt.co/feed",                            "tags": ["crypto", "markets"]},

    # ── Conflict / defense ───────────────────────────────────────────────
    {"url": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml", "tags": ["conflict", "defense", "geopolitical"]},
    {"url": "https://www.janes.com/feeds/news",                   "tags": ["conflict", "defense", "maritime"]},

    # ── Polish institutional (macro PL) ──────────────────────────────────
    {"url": "https://www.nbp.pl/rss/rss.aspx",                   "tags": ["macro", "poland", "central_bank"]},
    {"url": "https://www.knf.gov.pl/rss.xml",                    "tags": ["macro", "poland", "regulation"]},
]

# Keywords → which financial instruments to correlate
KEYWORD_INSTRUMENT_MAP: Dict[str, List[str]] = {
    "strait":       ["AIS_GLOBAL", "OIL_FUTURES", "BTC"],
    "port":         ["AIS_GLOBAL", "SHIPPING_INDEX"],
    "blockade":     ["AIS_GLOBAL", "OIL_FUTURES", "GOLD"],
    "sanctions":    ["RUB_USD", "OIL_FUTURES", "WHEAT_FUTURES"],
    "drought":      ["WHEAT_FUTURES", "CORN_FUTURES", "COPERNICUS_NDVI"],
    "harvest":      ["WHEAT_FUTURES", "COPERNICUS_NDVI"],
    "central bank": ["BTC", "GOLD", "DXY"],
    "rate hike":    ["BTC", "GOLD", "DXY", "SP500"],
    "rate cut":     ["BTC", "GOLD", "SP500"],
    "war":          ["OIL_FUTURES", "GOLD", "AIS_GLOBAL", "BTC"],
    "conflict":     ["OIL_FUTURES", "GOLD", "AIS_GLOBAL"],
    "election":     ["BTC", "POLYMARKET_POLITICS"],
    "crypto":       ["BTC", "ETH", "DERIBIT_IV"],
    "bitcoin":      ["BTC", "DERIBIT_IV", "POLYMARKET_CRYPTO"],
    "hack":         ["BTC", "ETH", "POLYMARKET_CRYPTO"],
    "liquidation":  ["BTC", "ETH", "DERIBIT_IV"],
}
