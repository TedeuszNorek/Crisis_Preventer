# SignalVortex

**Multi-source market analytics platform** — zunifikowana platforma analizy rynków.

## 🚀 Quick Start

```bash
cd signalvortex
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.template .env  # Uzupełnij API keys

# Pełna analiza
signalvortex --crypto BTCUSDT --funding --taker-pressure --correlation --liquidation --multi-tf
```

## 💻 CLI — Wszystkie Komendy

### Crypto Analysis

```bash
# Podstawowa analiza (OI, L/S ratio, lead-lag)
signalvortex --crypto BTCUSDT

# Binance Funding Rate (natywny, bez Coinalyze)
signalvortex --crypto BTCUSDT --binance-funding

# Binance Options (IV, Greeks, P/C ratio)
signalvortex --crypto BTCUSDT --binance-options

# Taker Buy/Sell Pressure
signalvortex --crypto BTCUSDT --taker-pressure

# Funding Rate via Coinalyze (wymaga API key)
signalvortex --crypto BTCUSDT --funding

# Cross-Asset Correlation Matrix
signalvortex --correlation BTCUSDT ETHUSDT SOLUSDT

# Liquidation Cascade Detector
signalvortex --crypto BTCUSDT --liquidation

# Multi-Timeframe Confluence (5m, 1h, 4h)
signalvortex --crypto BTCUSDT --multi-tf
```

### Options Analysis (Equity)

```bash
# IV Surface + Anomaly Detection (wymaga Polygon API)
signalvortex --symbol AAPL

# Custom grid
signalvortex --symbol AAPL --strike-points 50 --maturity-points 50
```

### Macro Analysis

```bash
# Monetary Aggregates (M2/M3)
signalvortex --macro

# Combined
signalvortex --crypto BTCUSDT --macro
```

### Pełna Analiza

```bash
# Wszystkie moduły crypto
signalvortex --crypto BTCUSDT \
    --binance-funding \
    --binance-options \
    --taker-pressure \
    --funding \
    --correlation BTCUSDT ETHUSDT SOLUSDT \
    --liquidation \
    --multi-tf

# Crypto + Macro
signalvortex --crypto BTCUSDT --macro --funding --taker-pressure
```

## 📁 Architektura

```
signalvortex/
├── core/                    # Factory, Registry, Config
├── sources/                 # 10 providerów danych
│   ├── binance/            # Futures + Options
│   ├── coinalyze/          # OI, L/S, Funding
│   ├── polygon/            # Equity Options
│   └── ...
├── analytics/              
│   ├── crypto/             # 5 modułów
│   │   ├── funding.py      # Funding rate analysis
│   │   ├── taker_pressure.py
│   │   ├── correlation.py  # Cross-asset matrix
│   │   ├── liquidation.py  # Cascade detector
│   │   └── confluence.py   # Multi-TF
│   ├── volatility/         # IV surface
│   ├── leadlag/            # OI-price correlation
│   └── monetary/           # M2/M3
└── cli/                    # Entry points
```

## 📊 Moduły Analityczne

| Moduł | CLI Flag | Opis |
|-------|----------|------|
| Lead-Lag | `--crypto` | OI vs price correlation |
| Funding Rate | `--binance-funding` | Binance native funding |
| Funding (Coinalyze) | `--funding` | Historical analysis |
| Taker Pressure | `--taker-pressure` | Buy/sell momentum |
| Correlation | `--correlation` | Cross-asset matrix |
| Liquidation | `--liquidation` | Cascade risk detector |
| Multi-TF | `--multi-tf` | 5m/1h/4h confluence |
| Options | `--binance-options` | IV, Greeks, P/C ratio |
| IV Surface | `--symbol` | Equity options (Polygon) |
| Macro | `--macro` | M2/M3 growth |

## 🔑 API Keys

```bash
# .env
COINALYZE_API_KEY=xxx     # For --funding
FRED_API_KEY=xxx          # For --macro
POLYGON_API_KEY=xxx       # For --symbol (equity options)
```

**Binance Futures/Options nie wymaga API key** — publiczne endpointy.

## 📄 License

MIT
