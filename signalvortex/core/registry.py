"""Analytics Registry — rejestracja i zarządzanie modułami analitycznymi.

Wzorzec Registry umożliwia:
- Dynamiczną rejestrację modułów
- Discovery dostępnych analiz
- Ujednolicony interfejs wywołań
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

LOGGER = logging.getLogger(__name__)


class AnalyticsCategory(Enum):
    """Kategorie modułów analitycznych."""
    VOLATILITY = "volatility"
    CRYPTO = "crypto"
    MACRO = "macro"
    SENTIMENT = "sentiment"
    ANOMALY = "anomaly"


@dataclass
class AnalyticsModule:
    """Metadane modułu analitycznego."""
    name: str
    category: AnalyticsCategory
    func: Callable
    description: str
    requires_api_keys: List[str]


class AnalyticsRegistry:
    """Rejestr modułów analitycznych.
    
    Wzorzec: Registry + Service Locator
    
    Example:
        registry = AnalyticsRegistry()
        
        @registry.register("iv_surface", AnalyticsCategory.VOLATILITY)
        def build_iv_surface(...):
            ...
        
        # Later
        result = registry.run("iv_surface", **kwargs)
    """
    
    _modules: Dict[str, AnalyticsModule] = {}
    
    @classmethod
    def register(
        cls,
        name: str,
        category: AnalyticsCategory,
        description: str = "",
        requires_api_keys: Optional[List[str]] = None,
    ) -> Callable:
        """Dekorator rejestrujący moduł analityczny.
        
        Args:
            name: Unikalna nazwa modułu.
            category: Kategoria analizy.
            description: Opis modułu.
            requires_api_keys: Lista wymaganych kluczy API.
        """
        def decorator(func: Callable) -> Callable:
            cls._modules[name] = AnalyticsModule(
                name=name,
                category=category,
                func=func,
                description=description or func.__doc__ or "",
                requires_api_keys=requires_api_keys or [],
            )
            return func
        return decorator
    
    @classmethod
    def get(cls, name: str) -> Optional[AnalyticsModule]:
        """Pobiera moduł po nazwie."""
        return cls._modules.get(name)
    
    @classmethod
    def list_modules(cls, category: Optional[AnalyticsCategory] = None) -> List[AnalyticsModule]:
        """Lista modułów, opcjonalnie filtrowana po kategorii."""
        modules = list(cls._modules.values())
        if category:
            modules = [m for m in modules if m.category == category]
        return modules
    
    @classmethod
    def run(cls, name: str, **kwargs) -> Any:
        """Uruchamia moduł analityczny.
        
        Args:
            name: Nazwa modułu.
            **kwargs: Argumenty dla modułu.
        
        Returns:
            Wynik analizy.
        
        Raises:
            ValueError: Jeśli moduł nie istnieje.
        """
        module = cls.get(name)
        if not module:
            available = ", ".join(cls._modules.keys())
            raise ValueError(f"Unknown analytics module '{name}'. Available: {available}")
        
        LOGGER.info(f"Running analytics: {name}")
        return module.func(**kwargs)
    
    @classmethod
    def check_requirements(cls, name: str, config: Any) -> List[str]:
        """Sprawdza brakujące klucze API dla modułu.
        
        Returns:
            Lista brakujących kluczy.
        """
        module = cls.get(name)
        if not module:
            return []
        
        missing = []
        for key in module.requires_api_keys:
            if not getattr(config, key, None):
                missing.append(key)
        
        return missing


# Pre-register analytics modules
def _register_builtin_analytics() -> None:
    """Rejestruje wbudowane moduły analityczne."""
    from signalvortex.analytics.volatility import build_iv_surface, detect_anomalies
    from signalvortex.analytics.leadlag import analyze_oi_price_leadlag
    from signalvortex.analytics.monetary import collect_monetary_aggregates
    from signalvortex.analytics.coinalyze import run_backtest, analyze_coinalyze_patterns
    from signalvortex.analytics.anomaly import flag_anomalies
    
    AnalyticsRegistry.register(
        "iv_surface",
        AnalyticsCategory.VOLATILITY,
        "Build implied volatility surface with SVI fitting",
        ["polygon_api_key"],
    )(build_iv_surface)
    
    AnalyticsRegistry.register(
        "vol_anomalies",
        AnalyticsCategory.VOLATILITY,
        "Detect IV surface anomalies",
        ["polygon_api_key"],
    )(detect_anomalies)
    
    AnalyticsRegistry.register(
        "oi_leadlag",
        AnalyticsCategory.CRYPTO,
        "Analyze OI vs price lead-lag",
        [],
    )(analyze_oi_price_leadlag)
    
    AnalyticsRegistry.register(
        "monetary",
        AnalyticsCategory.MACRO,
        "Collect M2/M3 monetary aggregates",
        ["fred_api_key"],
    )(collect_monetary_aggregates)
    
    AnalyticsRegistry.register(
        "coinalyze_patterns",
        AnalyticsCategory.CRYPTO,
        "Analyze Coinalyze OI/L-S patterns",
        ["coinalyze_api_key"],
    )(analyze_coinalyze_patterns)
    
    AnalyticsRegistry.register(
        "coinalyze_backtest",
        AnalyticsCategory.CRYPTO,
        "Backtest leverage strategies",
        ["coinalyze_api_key"],
    )(run_backtest)
    
    AnalyticsRegistry.register(
        "option_anomalies",
        AnalyticsCategory.ANOMALY,
        "Flag option flow anomalies (ML + heuristics)",
        [],
    )(flag_anomalies)


try:
    _register_builtin_analytics()
except ImportError:
    pass
