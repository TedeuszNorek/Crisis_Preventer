# SignalVortex — Dokumentacja Techniczna

## Spis Treści

1. [Przegląd Architektury](#przegląd-architektury)
2. [Wzorce Projektowe](#wzorce-projektowe)
3. [Sources (Źródła Danych)](#sources-źródła-danych)
4. [Analytics (Moduły Analityczne)](#analytics-moduły-analityczne)
5. [Machine Learning](#machine-learning)
6. [Konfiguracja](#konfiguracja)

---

## Przegląd Architektury

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Sources   │────▶│  Analytics  │────▶│  Reporting  │
│  (10 APIs)  │     │ (12 modules)│     │  (outputs)  │
└─────────────┘     └─────────────┘     └─────────────┘
       ▲                   ▲
       │                   │
┌──────┴───────────────────┴──────┐
│    Core (Factory, ML, Config)   │
└─────────────────────────────────┘
```

---

## Sources (Źródła Danych)

### Binance Futures (`sources/binance/client.py`)

```python
from signalvortex.sources import BinanceFuturesClient

client = BinanceFuturesClient()
klines = client.get_klines("BTCUSDT", interval="1h")
oi = client.get_open_interest("BTCUSDT")
ls_ratio = client.get_long_short_ratio("BTCUSDT")
taker = client.get_taker_buy_sell_volume("BTCUSDT")

# Funding Rate (nowe)
funding = client.get_funding_rate("BTCUSDT")
funding_hist = client.get_funding_rate_hist("BTCUSDT", limit=100)
```

### Binance Options (`sources/binance/options.py`)

```python
from signalvortex.sources import BinanceOptionsClient

client = BinanceOptionsClient()
idx = client.get_underlying_index("BTCUSDT")
pc_ratio = client.get_put_call_ratio("BTCUSDT")
chain = client.get_option_chain("BTCUSDT")
iv = client.get_iv_by_expiry("BTCUSDT")
```

### Coinalyze (`sources/coinalyze/`)

```python
from signalvortex.sources import CoinalyzeClient

client = CoinalyzeClient(api_key="...")
df = client.get_combined_dataframe("BTCUSDT_PERP.A")
funding = client.get_funding_rate_history(["BTCUSDT_PERP.A"])
```

---

## Analytics (Moduły Analityczne)

### Crypto Modules (`analytics/crypto/`)

| Moduł | Plik | Opis |
|-------|------|------|
| Funding | `funding.py` | Funding rate analysis |
| Taker Pressure | `taker_pressure.py` | Buy/sell momentum |
| Correlation | `correlation.py` | Cross-asset matrix |
| Liquidation | `liquidation.py` | Cascade risk detector |
| Confluence | `confluence.py` | Multi-TF (5m/1h/4h) |

### Lead-Lag Analysis

```python
from signalvortex.analytics import analyze_oi_price_leadlag

result = analyze_oi_price_leadlag("BTCUSDT")
print(f"OI correlation: {result.oi_correlation}")
```

---

## Machine Learning

### GMM Regime Classification (`analytics/ml/regime.py`)

Zastępuje statyczne progi adaptacyjnym Gaussian Mixture Model.

```python
from signalvortex.analytics.ml import RegimeClassifier, analyze_regime

# Automatic regime detection
result = analyze_regime(df, n_regimes=3)
print(result.current_regime.regime)  # 'high_leverage', 'normal', etc.
print(result.current_regime.probability)  # 0.95
```

**Features:**
- `funding_rate` — current funding
- `oi_change` — OI change %
- `ls_ratio` — long/short ratio
- `momentum` — 6-period price change

**Regimes:**
| Reżim | Charakterystyka |
|-------|-----------------|
| `high_leverage` | High funding + rising OI |
| `deleveraging` | Falling OI, negative funding |
| `accumulation` | Rising OI, neutral funding |
| `normal` | Balanced conditions |

**CLI:**
```bash
signalvortex --crypto BTCUSDT --regime
```

---

## Konfiguracja

### Environment Variables (`.env`)

```bash
POLYGON_API_KEY=xxx
FINNHUB_API_KEY=xxx
FRED_API_KEY=xxx
COINALYZE_API_KEY=xxx
```

**Binance nie wymaga API key** — publiczne endpointy.

---

## CLI Reference

| Flag | Opis |
|------|------|
| `--crypto SYMBOL` | Podstawowa analiza |
| `--regime` | 🤖 GMM regime classification |
| `--binance-funding` | Binance native funding |
| `--binance-options` | Options IV, P/C ratio |
| `--taker-pressure` | Buy/sell momentum |
| `--correlation` | Cross-asset matrix |
| `--liquidation` | Cascade risk |
| `--multi-tf` | 5m/1h/4h confluence |
| `--macro` | M2/M3 growth |

---

## Licencja

MIT © 2024 VortexAnalytica
