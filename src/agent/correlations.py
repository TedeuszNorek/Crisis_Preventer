"""Cross-domain correlation rules.

When signal X fires from source A → the agent activates source B automatically.
These rules encode domain knowledge: given what just happened, what should we
look at next?

Trigger functions are named (not lambdas) so stack traces are readable.
RSS triggers match on `categories` from KeywordRule — not raw keyword strings.
All rules require a minimum severity to avoid spurious activations on low-noise signals.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from src.core.models import Domain, Signal, Severity

_HIGH_PLUS = {Severity.HIGH, Severity.CRITICAL}

# Oil/energy choke points: anomaly here → oil derivatives + conflict odds
_OIL_ZONES = {"hormuz", "bab_el_mandeb", "suez"}
# Trade/semiconductor choke points: anomaly here → macro risk-off + supply chain
_TRADE_ZONES = {"taiwan_strait", "malacca", "baltic"}


@dataclass
class CorrelationRule:
    name: str
    description: str
    trigger: Callable[[Signal], bool]
    activate_sources: List[str]       # sources to spin up / increase polling
    activate_sat_zones: List[str]     # satellite zones to scan
    bump_polling: dict                # {source: new_interval_seconds}
    priority: int                     # 1=low … 5=critical
    rationale: str


# ── Trigger functions ────────────────────────────────────────────────────────

def _is_oil_zone_ais_anomaly(s: Signal) -> bool:
    return (
        s.source == "ais"
        and s.severity in _HIGH_PLUS
        and any(z in str(s.context) for z in _OIL_ZONES)
    )


def _is_trade_zone_ais_anomaly(s: Signal) -> bool:
    return (
        s.source == "ais"
        and s.severity in _HIGH_PLUS
        and any(z in str(s.context) for z in _TRADE_ZONES)
    )


def _is_iv_spike(s: Signal) -> bool:
    return (
        s.source == "deribit"
        and s.severity in _HIGH_PLUS
        and "SPIKE" in s.title
    )


def _is_extreme_binance_funding(s: Signal) -> bool:
    return (
        s.source == "binance"
        and s.severity == Severity.CRITICAL
    )


def _is_political_risk_news(s: Signal) -> bool:
    return (
        s.source == "rss"
        and s.severity in _HIGH_PLUS
        and "political_risk" in s.context.get("categories", [])
    )


def _is_crypto_stress_news(s: Signal) -> bool:
    return (
        s.source == "rss"
        and s.severity in _HIGH_PLUS
        and "crypto_stress" in s.context.get("categories", [])
    )


def _is_monetary_shock_news(s: Signal) -> bool:
    return (
        s.source == "rss"
        and s.severity in _HIGH_PLUS
        and "monetary_policy" in s.context.get("categories", [])
    )


def _is_conflict_news(s: Signal) -> bool:
    return (
        s.source == "rss"
        and s.severity in _HIGH_PLUS
        and "conflict" in s.context.get("categories", [])
    )


def _is_supply_disruption_news(s: Signal) -> bool:
    return (
        s.source == "rss"
        and s.severity in _HIGH_PLUS
        and "supply_disruption" in s.context.get("categories", [])
    )


def _is_commodity_stress_news(s: Signal) -> bool:
    return (
        s.source == "rss"
        and "commodity_supply" in s.context.get("categories", [])
    )


def _is_polymarket_repricing(s: Signal) -> bool:
    return (
        s.source == "polymarket"
        and s.severity in _HIGH_PLUS
        and s.value > 0.10
    )


def _is_satellite_port_anomaly(s: Signal) -> bool:
    return (
        s.source == "copernicus"
        and "low port activity" in s.context.get("interpretation", "").lower()
    )


# ── Rules ────────────────────────────────────────────────────────────────────

RULES: List[CorrelationRule] = [

    CorrelationRule(
        name="ais_oil_choke_point",
        description="Vessel anomaly in Hormuz / Bab el-Mandeb / Suez — oil supply chain at risk",
        trigger=_is_oil_zone_ais_anomaly,
        activate_sources=["deribit", "polymarket"],
        activate_sat_zones=["hormuz", "suez_port"],
        bump_polling={"ais": 10, "deribit": 20, "polymarket": 30},
        priority=5,
        rationale="Oil choke point disruption → check oil proxy (Deribit IV) + conflict odds (Polymarket)",
    ),

    CorrelationRule(
        name="ais_trade_choke_point",
        description="Vessel anomaly in Taiwan Strait / Malacca / Baltic — global trade + semiconductors",
        trigger=_is_trade_zone_ais_anomaly,
        activate_sources=["binance", "polymarket"],
        activate_sat_zones=[],
        bump_polling={"ais": 15, "binance": 15, "polymarket": 30},
        priority=4,
        rationale="Trade choke point disruption → check macro risk-off (Binance funding) + conflict odds",
    ),

    CorrelationRule(
        name="iv_spike_macro_check",
        description="Deribit IV spike — find the macro driver",
        trigger=_is_iv_spike,
        activate_sources=["rss", "polymarket"],
        activate_sat_zones=[],
        bump_polling={"rss": 60, "polymarket": 30, "binance": 15},
        priority=3,
        rationale="Options IV spike usually driven by a news event — scan feeds + prediction markets",
    ),

    CorrelationRule(
        name="binance_extreme_funding",
        description="Extreme Binance funding rate — check if news-driven",
        trigger=_is_extreme_binance_funding,
        activate_sources=["deribit", "polymarket", "rss"],
        activate_sat_zones=[],
        bump_polling={"binance": 10, "deribit": 20, "rss": 60},
        priority=4,
        rationale="Extreme OI + funding usually precedes a large move — widen the monitoring net",
    ),

    CorrelationRule(
        name="conflict_news",
        description="HIGH+ RSS signal in 'conflict' category",
        trigger=_is_conflict_news,
        activate_sources=["ais", "polymarket", "deribit"],
        activate_sat_zones=["black_sea", "suez_port", "hormuz"],
        bump_polling={"ais": 20, "polymarket": 45, "rss": 90},
        priority=5,
        rationale="Conflict-category news → check shipping disruption (AIS) + market reaction",
    ),

    CorrelationRule(
        name="supply_disruption_news",
        description="HIGH+ RSS signal in 'supply_disruption' category",
        trigger=_is_supply_disruption_news,
        activate_sources=["ais", "deribit", "polymarket"],
        activate_sat_zones=["hormuz", "suez_port"],
        bump_polling={"ais": 20, "deribit": 30, "rss": 90},
        priority=4,
        rationale="Supply disruption news → check shipping lanes + derivatives for market pricing",
    ),

    CorrelationRule(
        name="commodity_satellite",
        description="Commodity supply stress in news → verify with satellite NDVI",
        trigger=_is_commodity_stress_news,
        activate_sources=["polymarket"],
        activate_sat_zones=["ukraine_wheat"],
        bump_polling={"rss": 120},
        priority=3,
        rationale="Commodity stress news → check crop health via Copernicus NDVI",
    ),

    CorrelationRule(
        name="polymarket_repricing",
        description="Prediction market rapid repricing >10% — find the trigger",
        trigger=_is_polymarket_repricing,
        activate_sources=["rss", "binance"],
        activate_sat_zones=[],
        bump_polling={"rss": 60, "polymarket": 30},
        priority=3,
        rationale="Prediction market repricing → scan RSS for the news driver + crypto reaction",
    ),

    CorrelationRule(
        name="satellite_port_anomaly",
        description="Satellite shows low port activity — cross-check with AIS",
        trigger=_is_satellite_port_anomaly,
        activate_sources=["ais", "polymarket"],
        activate_sat_zones=[],
        bump_polling={"ais": 15},
        priority=4,
        rationale="Satellite confirms port disruption → cross-check with AIS live vessel data",
    ),

    CorrelationRule(
        name="political_risk_news",
        description="HIGH+ RSS signal in 'political_risk' category (coup, election, state of emergency)",
        trigger=_is_political_risk_news,
        activate_sources=["polymarket", "binance"],
        activate_sat_zones=[],
        bump_polling={"polymarket": 30, "binance": 20, "rss": 90},
        priority=4,
        rationale="Political shock → check prediction markets (fastest repricing) + crypto risk-off",
    ),

    CorrelationRule(
        name="crypto_stress_news",
        description="HIGH+ RSS signal in 'crypto_stress' category (exploit, depeg, exchange collapse)",
        trigger=_is_crypto_stress_news,
        activate_sources=["deribit", "polymarket", "binance"],
        activate_sat_zones=[],
        bump_polling={"binance": 10, "deribit": 15, "polymarket": 30},
        priority=4,
        rationale="Crypto stress event → check IV spike (Deribit), liquidation cascade (Binance), odds (Polymarket)",
    ),

    CorrelationRule(
        name="monetary_shock_news",
        description="HIGH+ RSS signal in 'monetary_policy' category (surprise rate decision, emergency CB meeting)",
        trigger=_is_monetary_shock_news,
        activate_sources=["binance", "deribit", "polymarket"],
        activate_sat_zones=[],
        bump_polling={"binance": 15, "deribit": 20, "polymarket": 45},
        priority=3,
        rationale="Monetary shock → check crypto funding reaction (Binance) + vol repricing (Deribit)",
    ),

]


def matching_rules(signal: Signal) -> List[CorrelationRule]:
    return [r for r in RULES if r.trigger(signal)]
