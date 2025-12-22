# SignalVortex — Dokumentacja Techniczna

## Spis Treści

1. [Przegląd Architektury](#przegląd-architektury)
2. [Wzorce Projektowe](#wzorce-projektowe)
3. [Sources (Źródła Danych)](#sources-źródła-danych)
4. [Analytics (Moduły Analityczne)](#analytics-moduły-analityczne)
5. [Konfiguracja](#konfiguracja)
6. [API Reference](#api-reference)

---

## Przegląd Architektury

SignalVortex to modularna platforma analityczna zbudowana w oparciu o:

- **Layered Architecture**: Separacja warstw (sources → analytics → reporting)
- **Dependency Injection**: Konfiguracja wstrzykiwana przez `Config`
- **Factory Pattern**: Centralne tworzenie klientów API
- **Registry Pattern**: Dynamiczna rejestracja modułów analitycznych

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Sources   │────▶│  Analytics  │────▶│  Reporting  │
│  (9 APIs)   │     │ (7 modules) │     │  (outputs)  │
└─────────────┘     └─────────────┘     └─────────────┘
       ▲                   ▲
       │                   │
┌──────┴───────────────────┴──────┐
│         Core (Factory, Registry, Config)         │
└─────────────────────────────────┘
```

---

## Wzorce Projektowe

### 1. Factory Pattern (`core/factory.py`)

**Cel**: Centralizacja tworzenia klientów API z cache'owaniem instancji.

```python
from signalvortex.core import SourceFactory

factory = SourceFactory(config)
client = factory.get("polygon")  # Lazy loading + cache
```

**Cechy**:
- Lazy loading klientów
- Singleton per source type (cache)
- Auto-injection API keys z `Config`
- Registry-based discovery

### 2. Registry Pattern (`core/registry.py`)

**Cel**: Dynamiczna rejestracja i discovery modułów analitycznych.

```python
from signalvortex.core import AnalyticsRegistry, AnalyticsCategory

@AnalyticsRegistry.register("my_analysis", AnalyticsCategory.CRYPTO)
def my_analysis(symbol: str, **kwargs):
    ...

# Later
result = AnalyticsRegistry.run("my_analysis", symbol="BTC")
```

### 3. Strategy Pattern (`analytics/anomaly/`)

**Cel**: Wymienne strategie wykrywania anomalii.

```python
from signalvortex.analytics.anomaly import flag_anomalies

# Heuristic only
df = flag_anomalies(data, method="heuristic")

# Machine Learning (IsolationForest)
df = flag_anomalies(data, method="ml")

# Hybrid (recommended)
df = flag_anomalies(data, method="hybrid")
```

---

## Sources (Źródła Danych)

### Polygon (`sources/polygon/`)

Equity options snapshots i IV data.

```python
from signalvortex.sources import PolygonClient

client = PolygonClient(api_key="...")
chain_df = client.get_option_chain("AAPL")
```

### Binance (`sources/binance/`)

Crypto futures: OI, L/S ratios, klines, archive.

```python
from signalvortex.sources import BinanceFuturesClient
from signalvortex.sources.binance import collect_leverage_metrics

client = BinanceFuturesClient()
oi = client.get_open_interest("BTCUSDT")
klines = client.get_klines("BTCUSDT", interval="1h")

# Multi-period metrics
metrics = collect_leverage_metrics("BTCUSDT", periods=["1h", "4h", "1d"])
```

### FRED + ECB (`sources/fred/`, `sources/ecb/`)

Monetary aggregates M2/M3.

```python
from signalvortex.sources import FredClient, EcbClient

fred = FredClient(api_key="...")
m2_df = fred.get_series("WM2NS")

ecb = EcbClient()
m3_df = ecb.get_m3()
```

### Coinalyze (`sources/coinalyze/`)

Historical OI, L/S ratio, OHLCV, funding rates.

```python
from signalvortex.sources import CoinalyzeClient

client = CoinalyzeClient(api_key="...")
df = client.get_combined_dataframe("BTCUSDT_PERP.A")
```

### Finnhub (`sources/finnhub/`)

Sentiment (social, news), insider trading, options.

```python
from signalvortex.sources import FinnhubClient

client = FinnhubClient(api_key="...")
sentiment = client.get_social_sentiment("AAPL")
insiders = client.get_insider_transactions("AAPL")
```

---

## Analytics (Moduły Analityczne)

### Volatility Surface (`analytics/volatility/`)

```python
from signalvortex.analytics import build_iv_surface, detect_anomalies

# Build SVI-fitted IV surface
strike_grid, maturity_grid, iv_matrix = build_iv_surface(chain_df)

# Detect anomalies
anomalies_df = detect_anomalies(chain_df, strike_grid, maturity_grid, iv_matrix)
```

### Lead-Lag Analysis (`analytics/leadlag/`)

```python
from signalvortex.analytics import analyze_oi_price_leadlag

result = analyze_oi_price_leadlag(symbol="BTCUSDT", lookback_hours=168)
print(f"Correlation: {result.correlation}")
print(f"Best lag: {result.optimal_lag_hours}h")
```

### Monetary Aggregates (`analytics/monetary/`)

```python
from signalvortex.analytics import collect_monetary_aggregates, compute_growth

data = collect_monetary_aggregates(config)
growth_df = compute_growth(data)
```

### Coinalyze Patterns (`analytics/coinalyze/`)

```python
from signalvortex.analytics.coinalyze import analyze_coinalyze_patterns, run_backtest

# Regime detection
patterns = analyze_coinalyze_patterns("BTCUSDT_PERP.A", api_key="...")

# Backtest leverage strategies
results = run_backtest("BTCUSDT_PERP.A", start_date=datetime(2021,1,1))
print(results["leverage_flush_bounce"].win_rate)
```

### Anomaly Detection (`analytics/anomaly/`)

```python
from signalvortex.analytics import flag_anomalies

# Hybrid: IsolationForest + heuristics
flagged_df = flag_anomalies(option_features_df, method="hybrid")
anomalies = flagged_df[flagged_df["anomaly_flag"]]
```

### Feature Engineering (`analytics/features/`)

```python
from signalvortex.analytics import make_option_features, merge_sentiment

# Option features
features_df = make_option_features(option_df, equity_df)

# Add sentiment
enriched_df = merge_sentiment(features_df, social_df, news_df, insider_df)
```

---

## Konfiguracja

### Environment Variables (`.env`)

```bash
POLYGON_API_KEY=your_key
FINNHUB_API_KEY=your_key
FRED_API_KEY=your_key
COINANALYZE_API_KEY=your_key
GETDOME_API_KEY=your_key
MASSIVE_API_KEY=your_key
SIGNALVORTEX_WEBHOOK_URL=https://...
SIGNALVORTEX_OUTPUT_DIR=./data
```

### Programmatic Config

```python
from signalvortex.core import Config

# Z .env
config = Config.from_env()

# Walidacja
missing = config.validate()
if missing:
    print(f"Missing keys: {missing}")
```

---

## API Reference

### SourceFactory

| Metoda | Opis |
|--------|------|
| `get(name)` | Pobiera/tworzy klienta |
| `available_sources()` | Lista dostępnych źródeł |
| `register(name, cls)` | Rejestruje nowe źródło |

### AnalyticsRegistry

| Metoda | Opis |
|--------|------|
| `register(name, category)` | Dekorator rejestrujący moduł |
| `run(name, **kwargs)` | Uruchamia moduł |
| `list_modules(category)` | Lista modułów |
| `check_requirements(name, config)` | Sprawdza wymagane klucze |

---

## Licencja

MIT License © 2024 VortexAnalytica
