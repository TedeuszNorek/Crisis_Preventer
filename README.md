# SignalVortex

**Multi-source market analytics platform** — zunifikowana platforma analizy rynków łącząca:

- 🎯 **Equity Options**: IV surface (SVI), anomaly detection, feature engineering
- 📈 **Crypto Futures**: Open interest, long/short ratios, lead-lag analysis
- 💰 **Monetary Aggregates**: M2/M3 growth correlation (FRED, ECB)
- 🔮 **Prediction Markets**: Polymarket overlay

## 🚀 Quick Start

```bash
cd signalvortex
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.template .env  # Uzupełnij API keys
signalvortex --symbol AAPL --crypto BTCUSDT --macro
```

## 📁 Architektura

```
signalvortex/
├── core/                    # Wzorce projektowe
│   ├── config.py           # Zunifikowana konfiguracja
│   ├── http_client.py      # Base HTTP client (retries, rate limiting)
│   ├── factory.py          # Factory Pattern — tworzenie klientów
│   └── registry.py         # Registry Pattern — moduły analityczne
│
├── sources/                 # 9 providerów danych
│   ├── polygon/            # Options snapshots, IV
│   ├── binance/            # Futures OI, L/S ratios, archive
│   ├── fred/               # US M2
│   ├── ecb/                # Euro M2/M3
│   ├── finnhub/            # Sentiment, insider, options
│   ├── coinalyze/          # OI history, patterns
│   ├── getdome/            # Polymarket overlay
│   ├── massive/            # OHLC fallback
│   └── gamma/              # Polymarket direct
│
├── analytics/               # 7 modułów analitycznych
│   ├── volatility/         # IV surface, SVI fitting
│   ├── leadlag/            # OI vs price correlation
│   ├── monetary/           # M2/M3 growth rates
│   ├── coinalyze/          # Regime patterns, backtest
│   ├── features/           # Feature engineering
│   └── anomaly/            # IsolationForest + heuristics
│
├── reporting/              # Insights, webhooks
└── cli/                    # Entry points
```

## 🔧 Wzorce Projektowe

### Factory Pattern — `SourceFactory`

```python
from signalvortex.core import SourceFactory, Config

config = Config.from_env()
factory = SourceFactory(config)

# Tworzenie klientów przez fabrykę
polygon = factory.get("polygon")
binance = factory.get("binance")

# Dostępne źródła
print(factory.available_sources())
# ['polygon', 'binance', 'fred', 'ecb', 'coinalyze', 'finnhub', 'getdome', 'massive', 'gamma']
```

### Registry Pattern — `AnalyticsRegistry`

```python
from signalvortex.core import AnalyticsRegistry, AnalyticsCategory

# Lista modułów
modules = AnalyticsRegistry.list_modules()
# ['iv_surface', 'vol_anomalies', 'oi_leadlag', 'monetary', ...]

# Uruchomienie analizy
result = AnalyticsRegistry.run("iv_surface", symbol="AAPL", config=config)
```

## 📊 Moduły Analityczne

| Moduł | Kategoria | Opis | API Keys |
|-------|-----------|------|----------|
| `iv_surface` | Volatility | IV surface z SVI fitting | Polygon |
| `vol_anomalies` | Volatility | Wykrywanie anomalii IV | Polygon |
| `oi_leadlag` | Crypto | OI vs price lead-lag | — |
| `monetary` | Macro | M2/M3 growth rates | FRED |
| `coinalyze_patterns` | Crypto | Regime detection (OI, L/S) | Coinalyze |
| `coinalyze_backtest` | Crypto | Leverage strategies backtest | Coinalyze |
| `option_anomalies` | Anomaly | IsolationForest + heuristics | — |

## 🔑 API Keys

| Provider | Zmienna | Cel |
|----------|---------|-----|
| Polygon.io | `POLYGON_API_KEY` | Options snapshots |
| Finnhub | `FINNHUB_API_KEY` | Sentiment, insider |
| FRED | `FRED_API_KEY` | US M2 |
| Coinalyze | `COINANALYZE_API_KEY` | Historical OI |
| GetDome | `GETDOME_API_KEY` | Polymarket |
| Massive | `MASSIVE_API_KEY` | OHLC fallback |
| Binance | `BINANCE_API_KEY` | Private account (optional) |

## 💻 CLI

```bash
# Pełna analiza
signalvortex --symbol AAPL --crypto BTCUSDT --macro --output data/

# Tylko opcje
signalvortex --symbol AAPL --no-crypto --no-macro

# Tylko crypto
signalvortex --crypto BTCUSDT --no-options --no-macro

# Pomoc
signalvortex --help
```

## 🧪 Development

```bash
# Instalacja z dev dependencies
pip install -e ".[dev]"

# Linting
ruff check signalvortex/

# Type checking
mypy signalvortex/

# Testy
pytest tests/
```

## 📄 License

MIT
