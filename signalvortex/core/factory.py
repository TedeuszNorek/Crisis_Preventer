"""Source Factory — centralna fabryka klientów API.

Wzorzec Factory umożliwia:
- Lazy loading klientów
- Centralne zarządzanie konfiguracją
- Cache'owanie instancji (Singleton per source)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from signalvortex.core.http_client import BaseClient

LOGGER = logging.getLogger(__name__)

# Registry mapująca nazwy źródeł na klasy klientów
_SOURCE_REGISTRY: Dict[str, Type] = {}


def register_source(name: str):
    """Dekorator rejestrujący źródło danych.
    
    Example:
        @register_source("polygon")
        class PolygonClient(BaseClient):
            ...
    """
    def decorator(cls: Type) -> Type:
        _SOURCE_REGISTRY[name.lower()] = cls
        return cls
    return decorator


class SourceFactory:
    """Fabryka klientów API z cache'owaniem instancji.
    
    Wzorzec: Factory + Singleton (per source type)
    
    Example:
        factory = SourceFactory(config)
        polygon = factory.get("polygon")
        binance = factory.get("binance")
    """
    
    _instances: Dict[str, Any] = {}
    
    def __init__(self, config: Optional[Any] = None) -> None:
        """Inicjalizuje fabrykę z konfiguracją.
        
        Args:
            config: Obiekt Config lub None (użyje domyślnej).
        """
        self._config = config
        self._cache: Dict[str, Any] = {}
    
    @classmethod
    def register(cls, name: str, client_class: Type) -> None:
        """Ręczna rejestracja źródła.
        
        Args:
            name: Nazwa źródła (np. 'polygon').
            client_class: Klasa klienta.
        """
        _SOURCE_REGISTRY[name.lower()] = client_class
    
    @classmethod
    def available_sources(cls) -> list[str]:
        """Zwraca listę dostępnych źródeł."""
        return list(_SOURCE_REGISTRY.keys())
    
    def get(self, source_name: str, **kwargs) -> Any:
        """Pobiera lub tworzy instancję klienta.
        
        Args:
            source_name: Nazwa źródła (np. 'polygon', 'binance').
            **kwargs: Dodatkowe argumenty dla konstruktora.
        
        Returns:
            Instancja klienta.
        
        Raises:
            ValueError: Jeśli źródło nie jest zarejestrowane.
        """
        name = source_name.lower()
        
        # Cache hit
        cache_key = f"{name}:{hash(frozenset(kwargs.items()))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Lookup
        if name not in _SOURCE_REGISTRY:
            available = ", ".join(self.available_sources())
            raise ValueError(f"Unknown source '{name}'. Available: {available}")
        
        client_class = _SOURCE_REGISTRY[name]
        
        # Resolve API key from config
        api_key = self._resolve_api_key(name, kwargs)
        if api_key:
            kwargs.setdefault("api_key", api_key)
        
        # Create instance
        try:
            instance = client_class(**kwargs)
            self._cache[cache_key] = instance
            LOGGER.debug(f"Created {name} client")
            return instance
        except Exception as e:
            LOGGER.error(f"Failed to create {name} client: {e}")
            raise
    
    def _resolve_api_key(self, source_name: str, kwargs: Dict) -> Optional[str]:
        """Resolve API key from config for source."""
        if "api_key" in kwargs:
            return None  # Already provided
        
        if self._config is None:
            return None
        
        # Map source names to config attributes
        key_mapping = {
            "polygon": "polygon_api_key",
            "binance": "binance_api_key",
            "fred": "fred_api_key",
            "ecb": None,  # No key required
            "coinalyze": "coinalyze_api_key",
            "finnhub": "finnhub_api_key",
            "getdome": "getdome_api_key",
            "massive": "massive_api_key",
            "gamma": None,  # No key required
        }
        
        attr = key_mapping.get(source_name)
        if attr and hasattr(self._config, attr):
            return getattr(self._config, attr)
        
        return None
    
    def __getattr__(self, name: str) -> Any:
        """Umożliwia dostęp przez atrybut: factory.polygon."""
        if name.startswith("_"):
            raise AttributeError(name)
        return self.get(name)


# Pre-register all sources
def _register_builtin_sources() -> None:
    """Rejestruje wbudowane źródła."""
    from signalvortex.sources.polygon.client import PolygonClient
    from signalvortex.sources.binance.client import BinanceFuturesClient
    from signalvortex.sources.fred.client import FredClient
    from signalvortex.sources.ecb.client import EcbClient
    from signalvortex.sources.coinalyze.client import CoinalyzeClient
    from signalvortex.sources.finnhub.client import FinnhubClient
    from signalvortex.sources.getdome.client import GetDomeClient
    from signalvortex.sources.massive import MassiveClient
    from signalvortex.sources.gamma import GammaClient
    
    SourceFactory.register("polygon", PolygonClient)
    SourceFactory.register("binance", BinanceFuturesClient)
    SourceFactory.register("fred", FredClient)
    SourceFactory.register("ecb", EcbClient)
    SourceFactory.register("coinalyze", CoinalyzeClient)
    SourceFactory.register("finnhub", FinnhubClient)
    SourceFactory.register("getdome", GetDomeClient)
    SourceFactory.register("massive", MassiveClient)
    SourceFactory.register("gamma", GammaClient)


# Lazy registration on first import
try:
    _register_builtin_sources()
except ImportError:
    pass  # Sources not yet available
