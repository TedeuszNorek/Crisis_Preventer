"""Unified configuration for SignalVortex."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class PolygonConfig:
    """Polygon.io API configuration."""

    api_key: str = field(default_factory=lambda: os.getenv("POLYGON_API_KEY", ""))
    base_url: str = "https://api.polygon.io"


@dataclass
class FinnhubConfig:
    """Finnhub API configuration."""

    api_key: str = field(default_factory=lambda: os.getenv("FINNHUB_API_KEY", ""))
    base_url: str = "https://finnhub.io/api/v1"


@dataclass
class BinanceConfig:
    """Binance API configuration."""

    api_key: str = field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("BINANCE_API_SECRET", ""))
    futures_base_url: str = "https://fapi.binance.com"
    spot_base_url: str = "https://api.binance.com"


@dataclass
class CoinalyzeConfig:
    """Coinalyze API configuration."""

    api_key: str = field(default_factory=lambda: os.getenv("COINALYZE_API_KEY", ""))
    base_url: str = "https://api.coinalyze.net/v1"


@dataclass
class FredConfig:
    """FRED API configuration."""

    api_key: str = field(default_factory=lambda: os.getenv("FRED_API_KEY", ""))
    base_url: str = "https://api.stlouisfed.org/fred"


@dataclass
class EcbConfig:
    """ECB Statistical Data Warehouse configuration."""

    base_url: str = "https://data-api.ecb.europa.eu/service/data"


@dataclass
class GetDomeConfig:
    """GetDome API configuration."""

    api_key: str = field(default_factory=lambda: os.getenv("GETDOME_API_KEY", ""))
    polymarket_tokens: str = field(default_factory=lambda: os.getenv("GETDOME_POLYMARKET_TOKENS", ""))


@dataclass
class MassiveConfig:
    """Massive.com API configuration."""

    api_key: str = field(default_factory=lambda: os.getenv("MASSIVE_API_KEY", ""))
    base_url: str = "https://api.massive.com"
    s3_endpoint: Optional[str] = field(default_factory=lambda: os.getenv("MASSIVE_S3_ENDPOINT"))
    s3_bucket: Optional[str] = field(default_factory=lambda: os.getenv("MASSIVE_S3_BUCKET"))


@dataclass
class Config:
    """Unified SignalVortex configuration."""

    polygon: PolygonConfig = field(default_factory=PolygonConfig)
    finnhub: FinnhubConfig = field(default_factory=FinnhubConfig)
    binance: BinanceConfig = field(default_factory=BinanceConfig)
    coinalyze: CoinalyzeConfig = field(default_factory=CoinalyzeConfig)
    fred: FredConfig = field(default_factory=FredConfig)
    ecb: EcbConfig = field(default_factory=EcbConfig)
    getdome: GetDomeConfig = field(default_factory=GetDomeConfig)
    massive: MassiveConfig = field(default_factory=MassiveConfig)

    # Output settings
    output_dir: Path = field(
        default_factory=lambda: Path(os.getenv("SIGNALVORTEX_OUTPUT_DIR", "./data"))
    )
    webhook_url: Optional[str] = field(
        default_factory=lambda: os.getenv("SIGNALVORTEX_WEBHOOK_URL")
    )

    @classmethod
    def load(cls, env_file: Optional[Path] = None) -> Config:
        """Load configuration from environment variables.

        Args:
            env_file: Optional path to .env file. If None, looks for .env in cwd.

        Returns:
            Populated Config instance.
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        return cls()

    def validate(self) -> list[str]:
        """Check for missing required API keys.

        Returns:
            List of missing key names.
        """
        missing = []
        if not self.polygon.api_key:
            missing.append("POLYGON_API_KEY")
        if not self.finnhub.api_key:
            missing.append("FINNHUB_API_KEY")
        if not self.fred.api_key:
            missing.append("FRED_API_KEY")
        return missing

    def has_binance_private(self) -> bool:
        """Check if Binance private API is configured."""
        return bool(self.binance.api_key and self.binance.api_secret)

    def has_coinalyze(self) -> bool:
        """Check if Coinalyze API is configured."""
        return bool(self.coinalyze.api_key)

    def has_getdome(self) -> bool:
        """Check if GetDome API is configured."""
        return bool(self.getdome.api_key)

    def has_massive(self) -> bool:
        """Check if Massive.com API is configured."""
        return bool(self.massive.api_key)
