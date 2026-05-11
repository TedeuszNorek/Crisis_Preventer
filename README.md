<h1 align="center">
  🌍 Crisis Preventer (OrbitAlpha Quant)
</h1>

<p align="center">
  <strong>Alternative Data & Institutional Arbitrage Engine: Satellite Observations meet Crypto Options</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Domain-Alternative%20Data%20%26%20Quant-orange.svg" alt="Quant">
  <img src="https://img.shields.io/badge/Architecture-Async%20Event--Driven-success.svg" alt="Async">
  <img src="https://img.shields.io/badge/Data-Copernicus%20%7C%20Sentinel--2-blueviolet.svg" alt="Satellite">
</p>

## 📖 Overview

**Crisis Preventer** is an institutional-grade quantitative analysis engine that bridges the physical world of agriculture and the digital world of derivatives trading. 

By ingesting **Alternative Data (AltData)** from Copernicus Sentinel-2 satellites to forecast agricultural yields, the engine correlates physical supply-chain shocks with global macro-economic indicators. Simultaneously, it runs a high-performance asynchronous arbitrage engine, calculating **Gamma Squeeze risk** and **Delta Hedging sensitivities** across prediction markets (Polymarket) and traditional crypto derivatives (Deribit/Binance).

> **Note:** This is a stripped-down "Open Core" version. Proprietary alpha-generating strategies, proprietary execution modules, and live API keys have been removed.

---

## 🛰️ Strategic Satellite Dashboard

![Strategic Satellite Dashboard](./sat_strategic_dashboard.png)
*OrbitAlpha UI: High-resolution Sentinel-2 crop health overlays, real-time crypto arbitrage spreads, and Gamma Squeeze monitors.*

---

## ✨ Key Features

*   🛰️ **Satellite Data Ingestion (AltData):** Automated pipelines processing Sentinel-2 L2A satellite data to monitor vegetation indices (NDVI, EVI) and forecast crop yields using LightGBM + Prophet.
*   ⚡ **Real-Time Arbitrage Engine:** Ingests high-frequency data via WebSockets to detect risk-neutral probability spreads and execution opportunities between Polymarket and Binance/Deribit.
*   📊 **Institutional Hedging Analytics:** Calculates critical options market metrics including **Gamma Flip price levels** and **Delta Hedging sensitivity** to anticipate institutional liquidity risks and reflexivity.
*   🛡️ **Robust Signal Architecture:** Built around a strict `SignalContract v1` schema. Features built-in anti-flapping mechanisms, data drift detection, and rigorous data quality gates to prevent false positives in high-volatility environments.
*   📈 **Macro-to-Micro Dashboard:** Streamlit-powered UI that visualizes both satellite-derived commodity forecasts and crypto institutional positioning.

---

## 🏗️ System Architecture

```mermaid
graph TD
    subgraph Alternative Data Layer
        S2[Sentinel-2 Satellite] -->|API| SI[Satellite Data Ingest]
        SI -->|NDVI/EVI| YF[Yield Forecast Engine]
        YF -->|Commodity Signals| SC
    end

    subgraph High-Frequency Ingestion [Crypto & Macro Data Layer]
        P[Polymarket API] -->|WebSockets| WS
        D[Deribit API] -->|WebSockets| WS
        B[Binance API] -->|WebSockets| WS
    end

    WS[Async Stream Coordinators] -->|Raw Data| Q[In-Memory Queues]

    subgraph Core Quant Engine
        Q --> V[Signal Validation]
        V --> AF[Anti-Flapping & Drift Detection]
        AF --> SC[SignalContract v1 Formatter]
    end

    subgraph Analytics & Execution
        SC --> GA[Gamma/Delta Analytics]
        SC --> AR[Arbitrage Detector]
    end

    GA --> DB[(SQLite Analytics DB)]
    AR --> DB
    YF --> DB
    
    DB --> UI[Crisis Preventer Unified Dashboard]
```

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/TedeuszNorek/Crisis_Preventer.git
cd Crisis_Preventer

# Set up virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Environment variables (Create .env file)
# Note: Do not commit your .env file
echo "SENTINEL_HUB_CLIENT_ID=your_id" >> .env
echo "SENTINEL_HUB_CLIENT_SECRET=your_secret" >> .env

# Run the core engine (Mock mode)
python -m signalvortex.cli.run_full --mock-feeds

# Run the UI Dashboard
streamlit run app.py
```
