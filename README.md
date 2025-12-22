# SignalVortex

**Multi-source market analytics platform** — zunifikowana platforma analizy rynków z ML.

## 🚀 Quick Start

```bash
cd signalvortex
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.template .env  # Uzupełnij API keys

# Pełna analiza z GMM regime classification
signalvortex --crypto BTCUSDT --regime --binance-funding --multi-tf
```

## 💻 CLI — Wszystkie Komendy

### Crypto Analysis

```bash
# Podstawowa analiza (OI, L/S ratio, lead-lag)
signalvortex --crypto BTCUSDT

# 🤖 GMM Regime Classification (ML)
signalvortex --crypto BTCUSDT --regime

# Binance Funding Rate (natywny)
signalvortex --crypto BTCUSDT --binance-funding

# Binance Options (IV, Greeks, P/C ratio)
signalvortex --crypto BTCUSDT --binance-options

# Taker Buy/Sell Pressure
signalvortex --crypto BTCUSDT --taker-pressure

# Funding Rate via Coinalyze
signalvortex --crypto BTCUSDT --funding

# Cross-Asset Correlation Matrix
signalvortex --correlation BTCUSDT ETHUSDT SOLUSDT

# Liquidation Cascade Detector
signalvortex --crypto BTCUSDT --liquidation

# Multi-Timeframe Confluence (5m, 1h, 4h)
signalvortex --crypto BTCUSDT --multi-tf
```

### Pełna Analiza

```bash
signalvortex --crypto BTCUSDT \
    --regime \
    --binance-funding \
    --binance-options \
    --taker-pressure \
    --correlation BTCUSDT ETHUSDT SOLUSDT \
    --liquidation \
    --multi-tf
```

## 🤖 GMM Regime Classification

Zastępuje statyczne progi maszynowym uczeniem (Gaussian Mixture Model):

| Reżim | Opis |
|-------|------|
| 🔴 `high_leverage` | Overleveraged — high funding, rising OI |
| 🟡 `deleveraging` | Leverage unwinding — falling OI |
| 🟢 `accumulation` | OI building, neutral funding |
| ⚪ `normal` | Balanced market conditions |

**Features:** funding_rate, oi_change, ls_ratio, momentum

## 📁 Architektura

```
signalvortex/
├── analytics/              
│   ├── ml/                 # 🤖 Machine Learning
│   │   └── regime.py       # GMM classifier
│   ├── crypto/             # 5 modułów
│   │   ├── funding.py
│   │   ├── taker_pressure.py
│   │   ├── correlation.py
│   │   ├── liquidation.py
│   │   └── confluence.py
│   ├── volatility/
│   ├── leadlag/
│   └── monetary/
├── sources/                 # 10 providerów
│   ├── binance/            # Futures + Options
│   ├── coinalyze/
│   └── polygon/
└── cli/
```

## 📊 Moduły Analityczne

| Moduł | CLI Flag | Opis |
|-------|----------|------|
| **GMM Regime** | `--regime` | 🤖 ML regime classification |
| Lead-Lag | `--crypto` | OI vs price correlation |
| Funding | `--binance-funding` | Binance native funding |
| Taker Pressure | `--taker-pressure` | Buy/sell momentum |
| Correlation | `--correlation` | Cross-asset matrix |
| Liquidation | `--liquidation` | Cascade risk detector |
| Multi-TF | `--multi-tf` | 5m/1h/4h confluence |
| Options | `--binance-options` | IV, Greeks, P/C ratio |
| Macro | `--macro` | M2/M3 growth |

## 🔑 API Keys

```bash
# .env
COINALYZE_API_KEY=xxx     # For --funding
FRED_API_KEY=xxx          # For --macro
POLYGON_API_KEY=xxx       # For --symbol (equity options)
```

**Binance nie wymaga API key** — publiczne endpointy.

## 📄 License

MIT
