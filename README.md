# Vortex Analytica — Core Engine

Real-time multi-source intelligence platform. Monitors financial markets, ship movements, global news, and satellite imagery simultaneously — and connects them into a single situational picture. When something matters, an LLM agent decides what to investigate next and writes an entry to the live analyst feed.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                            │
│                                                                 │
│  RSS / News ──┐   Binance Futures ──┐   Deribit Options ──┐    │
│  AIS / Ships ─┤   Polymarket ───────┤   FRED / Macro ─────┤    │
│  Copernicus ──┘                     └────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │  RawEvents
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       SIGNAL ENGINE                             │
│         Z-score anomaly · Anti-flapping · DQ gates             │
│              → Signal(severity, domain, context)                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┴────────────────┐
           │                                │
           ▼                                ▼
┌──────────────────────┐        ┌───────────────────────────┐
│  CORRELATION RULES   │        │      LLM AGENT            │
│  (instant, no LLM)   │        │      (Claude)             │
│                      │        │                           │
│  news:"war"      →   │        │  · write_feed_entry       │
│   AIS + Deribit      │        │  · activate_module        │
│                      │        │  · scan_satellite         │
│  IV spike        →   │        │  · no_action              │
│   RSS + Polymarket   │        │                           │
└──────────┬───────────┘        └─────────────┬─────────────┘
           │                                  │
           └──────────────┬───────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LIVE FEED  ("ticker")                        │
│                                                                 │
│  [CRITICAL]  AIS: tanker stopped in Hormuz + Deribit IV spike   │
│  [HIGH]      Polymarket repriced war probability +12% / 20min   │
│  [MEDIUM]    Copernicus: Ukraine NDVI dropping — harvest risk   │
│  [INFO]      Binance BTC funding rate nominal                   │
│                                                                 │
│           WebSocket → browser · REST API · Telegram (Q2)       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Source Modules

| Module | What it monitors | Signal fires when |
|--------|-----------------|-------------------|
| **Binance** | OI + funding rate, perpetuals (BTC/ETH/SOL/…) | Z-score >2.5σ — extreme leverage buildup |
| **Deribit** | Options IV chain BTC/ETH, gamma exposure | IV spike or crush, unusual volume |
| **Polymarket** | Prediction markets — politics, macro, crypto | Probability shift >5% on large pools |
| **AIS / Ships** | Vessel movements in strategic straits (Hormuz, Suez, Malacca, Taiwan…) | Tanker stopped, speed anomaly |
| **RSS / News** | 15+ global feeds (Reuters, BBC, OilPrice, shipping news, KNF, NBP…) | Keywords mapped to instruments |
| **Copernicus** | Sentinel-2: crop health (NDVI), port activity | Activated on-demand by the agent only |

---

## Cross-Domain Correlations

The agent does not look at modules in isolation. When one source signals a problem, correlated sources are activated automatically:

| Trigger | Agent activates |
|---------|----------------|
| AIS: tanker stopped in Hormuz | Deribit IV (oil proxy), Polymarket (conflict odds), Copernicus (port scan) |
| Deribit IV spike | RSS (find the news driver), Polymarket (market repricing) |
| RSS: "war" / "blockade" / "sanctions" | AIS (shipping disruption), Copernicus (satellite), Deribit (volatility) |
| Polymarket: +10% probability shift | RSS (what happened), Binance (market reaction) |
| Copernicus: low port activity | AIS (cross-check with live ship data) |
| Binance: extreme funding rate | Deribit, Polymarket, RSS (squeeze driver) |

---

## Quick Start

```bash
git clone https://github.com/TedeuszNorek/Crisis_Preventer.git
cd Crisis_Preventer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.template .env
# edit .env — add your API keys

# Run all modules
python -m src.runner

# Run specific modules only
python -m src.runner --modules rss,binance,deribit
```

Dashboard available at **http://localhost:8000**

---

## Environment — `.env`

```env
# Pick your LLM provider — only ONE key is required
LLM_PROVIDER=deepseek          # claude | deepseek | openai | openrouter | local
# LLM_MODEL=deepseek-reasoner  # optional model override

ANTHROPIC_API_KEY=             # https://console.anthropic.com
DEEPSEEK_API_KEY=              # https://platform.deepseek.com  ← cheapest
OPENAI_API_KEY=                # https://platform.openai.com
OPENROUTER_API_KEY=            # https://openrouter.ai

# Local / offline (Ollama, LM Studio, vLLM) — no key needed
# LLM_PROVIDER=local
# LOCAL_LLM_URL=http://localhost:11434/v1
# LLM_MODEL=llama3

# AIS maritime — https://aisstream.io (free tier available)
AISSTREAM_API_KEY=

# ESA Copernicus Sentinel-2 — https://dataspace.copernicus.eu (free)
SENTINEL_HUB_CLIENT_ID=
SENTINEL_HUB_CLIENT_SECRET=
```

DeepSeek is the default recommendation — significantly cheaper than Claude/OpenAI and handles tool use well. Local mode (Ollama) works for air-gapped deployments. Without any LLM key, the system still collects and displays signals — orchestration is just disabled.

---

## Repository Structure

```
src/
  core/
    models.py          # RawEvent, Signal, EscalationDecision, Severity
    event_bus.py       # Central async event bus; manages per-source polling rates

  sources/
    rss/
      harvester.py     # 15+ feeds, keyword→instrument routing, severity tagging
      feeds.py         # Feed list + keyword→instrument map
    binance/
      client.py        # OI + funding Z-score detection across 7 symbols
    deribit/
      client.py        # Volume-weighted IV, gamma flip estimate, spike/crush detection
    polymarket/
      client.py        # Prob shift detection, free-money scanner, topic tagging
    ais/
      client.py        # aisstream.io WebSocket, 8 strategic zones, vessel anomaly detection
    copernicus/
      client.py        # ESA Sentinel-2 NDVI + port activity (agent-activated on demand)

  agent/
    orchestrator.py    # Main LLM agent (Claude tool use) — decides what to do
    correlations.py    # 6 rule-based cross-domain triggers (instant, zero LLM cost)
    context.py         # Builds structured context bundle from recent signals for LLM

  api/
    server.py          # FastAPI: REST + WebSocket /ws/feed + browser dashboard

  runner.py            # Async entry point — starts all modules concurrently
```

---

## API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /` | Browser dashboard (live feed UI) |
| `GET /feed` | Agent-written feed entries (JSON) |
| `GET /signals` | Recent signals from all sources |
| `GET /escalations` | Agent escalation history |
| `GET /polling-rates` | Current polling intervals per source |
| `POST /polling-rates/{source}?seconds=N` | Override polling interval |
| `WS /ws/feed` | WebSocket — live stream of signals and escalations |

---

## Roadmap

**Q1 — current (TRL III→IV)**
- [x] Signal engine with Z-score, anti-flapping, data quality gates
- [x] Source modules: Binance, Deribit, Polymarket, AIS, RSS, Copernicus
- [x] LLM agent with cross-domain correlation rules
- [x] Live feed WebSocket + browser dashboard

**Q2 — critical point detection**
- [ ] Thematic RSS classification (LLM embeddings)
- [ ] Thematic session memory (long-context awareness)
- [ ] Telegram alerts for CRITICAL signals
- [ ] First synthetic PDF report

**Q3 — institutional pilot**
- [ ] Multi-agent: dedicated agent per domain
- [ ] GUS / KNF / Eurostat integration
- [ ] SSO for institutional deployments
- [ ] Full Sentinel-2 rasterio pipeline

---

*Vortex Analytica · TRL II→V · AI/LLM · Dual-use (MVP: civilian) · B2B/B2G*
