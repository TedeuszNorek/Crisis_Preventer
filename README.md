# Vortex Analytica — Core Engine

Real-time multi-source intelligence platform. Monitors financial markets, ship movements, global news, and satellite imagery simultaneously — and connects them into a single situational picture. When something matters, an LLM agent decides what to investigate next and writes an entry to the live analyst feed.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                            │
│                                                                 │
│   RSS / News  ·  AIS / Ships  ·  Copernicus (satellite)         │
│   Binance Futures  ·  Deribit Options  ·  Polymarket  ·  FRED   │
│                                                                 │
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
│  (instant, no LLM)   │        │  Claude / DeepSeek / …    │
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
│              WebSocket → browser  ·  REST API                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Source Modules

| Module | What it monitors | Signal fires when | Status |
|--------|-----------------|-------------------|--------|
| **Binance** | OI + funding rate, perpetuals (BTC/ETH/SOL/…) | Z-score >2.5σ — extreme leverage buildup | ✅ Live (public API) |
| **Deribit** | Options IV chain BTC/ETH, gamma exposure | IV spike or crush, unusual volume | ✅ Live (public API) |
| **Polymarket** | Prediction markets — politics, macro, crypto | Probability shift >5% on large pools | ✅ Live (public API) |
| **AIS / Ships** | Vessel movements in strategic straits (Hormuz, Suez, Malacca, Taiwan…) | Tanker stopped, speed anomaly | 🔑 `AISSTREAM_API_KEY` |
| **RSS / News** | 15+ global feeds (Reuters, BBC, OilPrice, shipping news, KNF, NBP…) | Keywords mapped to instruments | ✅ Live (public feeds) |
| **Copernicus** | Sentinel-2: crop health (NDVI), port activity | Activated on-demand by the agent only | 🔑 `SENTINEL_HUB_*` |
| **LLM Agent** | Synthesizes all signals, writes feed, activates modules | Triggered on HIGH/CRITICAL or every 5 min | 🔑 Any LLM key |

---

## Cross-Domain Correlations

The agent does not look at modules in isolation. When one source fires a signal, correlated sources are activated automatically — without LLM involvement, for speed.

Rules live in `src/agent/correlations.py`. Each rule has a named trigger function, a minimum severity threshold, and explicit polling-rate overrides for the activated sources.

| Rule | Trigger | Min severity | Activates | Satellite scan |
|------|---------|-------------|-----------|----------------|
| `maritime_disruption` | AIS anomaly in Suez / Hormuz / Bab el-Mandeb / Taiwan / Malacca | HIGH | Polymarket · Deribit · Binance | Suez · Hormuz |
| `iv_spike_macro_check` | Deribit IV spike (`SPIKE` in title) | HIGH | RSS · Polymarket | — |
| `binance_extreme_funding` | Binance funding rate Z-score | CRITICAL | Deribit · Polymarket · RSS | — |
| `conflict_news` | RSS signal in category `conflict` | HIGH | AIS · Polymarket · Deribit | Black Sea · Suez · Hormuz |
| `supply_disruption_news` | RSS signal in category `supply_disruption` | HIGH | AIS · Deribit · Polymarket | Hormuz · Suez |
| `commodity_satellite` | RSS signal in category `commodity_supply` | MEDIUM | Polymarket | Ukraine wheat |
| `polymarket_repricing` | Polymarket prob shift > 10% | HIGH | RSS · Binance | — |
| `satellite_port_anomaly` | Copernicus: "low port activity" | any | AIS · Polymarket | — |

**How RSS categories work:** the harvester matches articles against `KeywordRule` definitions in `src/sources/rss/feeds.py`. Each category owns its keyword list and minimum severity — e.g. `conflict` fires on `invasion`, `airstrike`, `military offensive` etc. and requires HIGH. A single article can match multiple categories simultaneously, activating multiple rules.

**Polling overrides on activation** (examples):
- `maritime_disruption` → AIS: 30s → 15s, Binance: 30s → 15s
- `conflict_news` → AIS: 30s → 20s, RSS: 300s → 90s
- `binance_extreme_funding` → Binance: 30s → 10s, Deribit: 60s → 20s

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

## Intelligence Lens

When the agent writes a `HIGH` or `CRITICAL` feed entry, the dashboard opens an **intelligence lens** — a focused situation picture for that event.

```
┌─────────────────────────┬──────────────────────────────────────┐
│                         │  ⚠ OIL SUPPLY RISK  [CRITICAL]       │
│   WORLD MAP             │                                      │
│   (Leaflet, dark)       │  Tanker Kharg stopped in Hormuz.     │
│                         │  Deribit IV +18%. Polymarket war     │
│   ● Hormuz  (pulsing)   │  odds up 9%. Watching for further    │
│                         │  AIS anomalies and IV expansion.     │
│                         │  ──────────────────────────────────  │
│                         │  Watch: OIL · GOLD · AIS_HORMUZ      │
│                         │  ──────────────────────────────────  │
│                         │  14:23  ais      Tanker stopped      │
│                         │  14:31  deribit  IV spike +18%       │
│                         │  14:39  rss      "Iran warns of..."  │
└─────────────────────────┴──────────────────────────────────────┘
```

- Map zooms automatically to the relevant geographic zone (Hormuz, Suez, Black Sea…)
- A pulsing marker shows the epicentre; colour matches the severity
- If a new `CRITICAL` arrives while the lens is open, a flashing badge appears — user decides when to switch
- Lens opens via `WebSocket type: "incident"`; also queryable at `GET /incidents/current`

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

## API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /` | Browser dashboard — live feed + intelligence lens |
| `GET /feed` | Agent-written feed entries (JSON) |
| `GET /signals` | Recent signals from all sources |
| `GET /escalations` | Agent escalation history |
| `GET /incidents` | All assembled incidents (newest first) |
| `GET /incidents/current` | Latest active incident (lens data) |
| `GET /polling-rates` | Current polling intervals per source |
| `POST /polling-rates/{source}?seconds=N` | Override polling interval |
| `WS /ws/feed` | Live stream — signals, escalations, incidents |

---

## Repository Structure

```
src/
  core/
    models.py          # RawEvent, Signal, EscalationDecision, Incident
    event_bus.py       # Async event bus — signals, escalations, incidents

  sources/
    rss/harvester.py   # 15+ feeds, keyword→instrument routing, severity tagging
    rss/feeds.py       # Feed list + keyword→instrument map
    binance/client.py  # OI + funding Z-score across 7 symbols
    deribit/client.py  # Volume-weighted IV, gamma flip, spike/crush detection
    polymarket/client.py  # Prob shift detection, free-money scanner, topic tagging
    ais/client.py      # aisstream.io WebSocket, 8 strategic zones, vessel anomaly
    copernicus/client.py  # ESA Sentinel-2 NDVI + port activity (on-demand)

  agent/
    orchestrator.py    # LLM agent — evaluates signals, creates incidents, writes feed
    llm.py             # Provider abstraction: Claude / DeepSeek / OpenAI / local
    correlations.py    # 6 rule-based cross-domain triggers (instant, zero LLM cost)
    context.py         # Builds structured context bundle for LLM

  api/
    server.py          # FastAPI: REST + WebSocket + intelligence lens dashboard

  runner.py            # Async entry point — starts all modules concurrently
```

---

## What's Missing / Open Items

These are the gaps between what's implemented and what a production deployment would need. Useful for contributors or evaluators.

**Signal quality**

| Item | Current state | What's needed |
|------|--------------|---------------|
| **Confidence score** | Z-score per source only | Combined score: `f(z_score, source_count, cross_domain_confirmations)` — displayed in feed and lens |
| **Cross-source deduplication** | Per-source hash dedup only | Fuzzy title match + 15-min window to collapse the same event reported by RSS + AIS simultaneously |
| **Signal ranking** | Severity only | Novelty × cross-domain confirmation × urgency — requires labeled feedback data first |
| **Explainability endpoint** | None | `GET /signals/{id}/explain` — which signals confirmed, which correlation rules fired, what the agent decided and why |

**User feedback**

| Item | Current state | What's needed |
|------|--------------|---------------|
| **In-dashboard feedback** | None | `✓ useful` / `✗ noise` buttons on each feed entry; stored in SQLite for future ranking model training |
| **Session memory** | Agent sees last 30 signals per call; no cross-session continuity | Vector store or long-context summary of past incidents |

**Data & storage**

| Item | Current state | What's needed |
|------|--------------|---------------|
| **Historical storage** | Signals in-memory only; lost on restart | SQLite / TimescaleDB persistence |
| **RSS classification** | Keyword matching only | LLM embeddings for thematic classification (reduces false positives) |
| **Sentinel-2 pipeline** | Simplified NDVI response; real rasterio parsing stubbed out | Full `rasterio` pipeline for actual GeoTIFF processing |
| **FRED / macro** | Streamers exist in `src/streamers/fred_streamer.py` but not wired to signal engine | Connect to event bus, add Z-score anomaly detection |

**Deployment & scale**

| Item | Current state | What's needed |
|------|--------------|---------------|
| **Cost tracking** | 45s LLM cooldown only | Token usage counter, per-provider cost estimate in `/health` |
| **Auth layer** | No authentication | API key middleware for multi-user / institutional deployment |
| **PDF reports** | Not implemented | Periodic synthesis report from accumulated incidents |
| **Alert channel** | None | Push notifications (email / webhook) for CRITICAL signals |
| **Multi-agent** | Single orchestrator for all domains | Separate agents per domain (crypto, maritime, macro) with a meta-agent |

**Deliberately out of scope (for now)**
Event ontology graph (Neo4j), full simulation layer (Mesa/AnyLogic), GNN-based ranking, RDF — all architecturally valid, all premature at this stage.

---

## Roadmap

**Q1 — current (TRL III→IV)**
- [x] Signal engine with Z-score, anti-flapping, data quality gates
- [x] Source modules: Binance, Deribit, Polymarket, AIS, RSS, Copernicus
- [x] LLM agent with cross-domain correlation rules + provider abstraction
- [x] Live feed WebSocket + intelligence lens dashboard (map + incident card)

**Q2 — signal quality + trust**
- [ ] Confidence score on every signal (z-score × cross-domain confirmation count)
- [ ] `GET /signals/{id}/explain` — causal chain, confirmed-by, agent rationale
- [ ] In-dashboard feedback loop (`✓ useful` / `✗ noise`) + SQLite storage
- [ ] Cross-source deduplication (fuzzy match + time window)
- [ ] Historical storage — SQLite persistence
- [ ] Thematic RSS classification (LLM embeddings)
- [ ] FRED macro integration

**Q3 — institutional pilot**
- [ ] Signal ranking model (trained on feedback from Q2)
- [ ] First synthetic PDF report
- [ ] Multi-agent: dedicated agent per domain
- [ ] GUS / KNF / Eurostat integration
- [ ] Auth layer for institutional deployments
- [ ] Full Sentinel-2 rasterio pipeline

---

*Vortex Analytica · TRL III→IV · AI/LLM · Dual-use (MVP: civilian) · B2B/B2G*
