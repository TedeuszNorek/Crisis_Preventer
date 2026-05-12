# ⚡ Vortex Analytica — Core Engine

**System automatycznej analizy i kontekstualizacji informacji w czasie rzeczywistym.**

Monitoruje jednocześnie rynki finansowe, ruchy statków, wiadomości globalne i dane satelitarne — i łączy je w jeden spójny obraz sytuacji. Gdy coś jest ważne, agent LLM decyduje co sprawdzić dalej i pisze wpis do live feed analityka.

---

## Jak to działa

```
┌─────────────────────────────────────────────────────────────┐
│                     ŹRÓDŁA DANYCH                           │
│                                                             │
│  RSS/News ──┐   Binance ──┐   Deribit ──┐                  │
│  AIS/Statki─┤   Polymarket┤   FRED/Macro┤                  │
│  Copernicus─┘             └─────────────┘                  │
└─────────────────────────┬───────────────────────────────────┘
                          │ RawEvents
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  SIGNAL ENGINE                              │
│  Z-score anomaly · Anti-flapping · Data quality gates       │
│  → Signal(severity, domain, context)                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
┌─────────────────┐            ┌──────────────────────┐
│  CORRELATION    │            │   LLM AGENT          │
│  RULES          │            │   (Claude)           │
│  (instant)      │            │                      │
│                 │            │  · write_feed_entry  │
│  news+war →     │            │  · activate_module   │
│   AIS+Deribit   │            │  · scan_satellite    │
│                 │            │  · no_action         │
│  IV spike →     │            │                      │
│   RSS+Polymarket│            │  Pisze po polsku     │
└────────┬────────┘            └──────────┬───────────┘
         │                               │
         └───────────────┬───────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              LIVE FEED ("BIEŻACZKA")                        │
│                                                             │
│  [CRITICAL] AIS: tanker stopped w Hormuz + IV spike BTC     │
│  [HIGH]     Polymarket wycenił wojnę +12% w 20 min         │
│  [MEDIUM]   NDVI Ukraina spada — ryzyko urodzaju            │
│  [INFO]     Binance funding BTC normalny                    │
│                                                             │
│  WebSocket → przeglądarka · REST API · Telegram (Q2)       │
└─────────────────────────────────────────────────────────────┘
```

---

## Moduły źródłowe

| Moduł | Co monitoruje | Anomalia = |
|-------|--------------|-----------|
| **Binance** | OI, funding rate perpetuals (BTC/ETH/SOL…) | Z-score >2.5σ — ekstremalne lewarowanie |
| **Deribit** | IV opcji BTC/ETH, gamma exposure | IV spike/crush, duży ruch vol |
| **Polymarket** | Rynki predykcji (polityka, makro, krypto) | Zmiana prawdopodobieństwa >5% na dużej puli |
| **AIS / Statki** | Ruch statków w kluczowych cieśninach (Hormuz, Suez, Malacca…) | Zatrzymanie tankowca, anomalia prędkości |
| **RSS / News** | 15+ globalnych feedów (Reuters, BBC, OilPrice, shipping news…) | Słowa kluczowe mapowane na instrumenty |
| **Copernicus** | Sentinel-2: zdrowie roślin (NDVI), aktywność portów | Aktywowana przez agenta on-demand |

---

## Korelacje cross-domain

Agent nie patrzy na moduły osobno. Gdy jeden źródło sygnalizuje problem, agent aktywuje powiązane:

| Trigger | Co agent sprawdza dalej |
|---------|------------------------|
| AIS: tanker zatrzymany w Hormuz | Deribit IV (ropa), Polymarket (conflict), Copernicus (port) |
| Deribit IV spike | RSS (szukaj news-drivera), Polymarket (repricing) |
| RSS: "war" / "blockade" | AIS (marynarka), Copernicus (satelita), Deribit (volatility) |
| Polymarket: +10% zmiana | RSS (co się stało), Binance (market reaction) |
| Copernicus: niska aktywność portu | AIS (cross-check live ships) |
| Binance: extreme funding | Deribit, Polymarket, RSS (squeeze driver) |

---

## Quick Start

```bash
git clone https://github.com/TedeuszNorek/SignalVortex.git
cd SignalVortex
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Skonfiguruj klucze API
cp .env.template .env
# Edytuj .env

# Uruchom wszystkie moduły
python -m src.runner

# Uruchom tylko wybrane
python -m src.runner --modules rss,binance,deribit
```

Dashboard dostępny na **http://localhost:8000**

---

## Konfiguracja — `.env`

```env
# LLM Agent (wymagane)
ANTHROPIC_API_KEY=sk-ant-...

# AIS Maritime (opcjonalne — https://aisstream.io)
AISSTREAM_API_KEY=...

# Copernicus Satellite (opcjonalne — https://dataspace.copernicus.eu)
SENTINEL_HUB_CLIENT_ID=...
SENTINEL_HUB_CLIENT_SECRET=...

# Polymarket extended (opcjonalne)
DOME_API_KEY=...
```

Bez `ANTHROPIC_API_KEY` system działa — zbiera i wyświetla sygnały, ale agent LLM jest wyłączony.  
Bez `AISSTREAM_API_KEY` moduł AIS jest pominięty.  
Bez `SENTINEL_HUB_*` satelita jest pominięta (agent poinformuje że chciał skasować ale nie może).

---

## Architektura — pliki

```
src/
  core/
    models.py          # RawEvent, Signal, EscalationDecision, Severity
    event_bus.py       # Centralny event bus; zarządza polling rates
  
  sources/
    rss/
      harvester.py     # Pobiera 15+ feedów, mapuje słowa kluczowe na instrumenty
      feeds.py         # Lista feedów + keyword→instrument mapping
    binance/
      client.py        # OI + funding rate z Z-score detection
    deribit/
      client.py        # Łańcuch opcji, volume-weighted IV, gamma flip estimate
    polymarket/
      client.py        # Active markets, prob shifts, free money detection
    ais/
      client.py        # WebSocket aisstream.io, anomaly detection na prędkości
    copernicus/
      client.py        # ESA Sentinel-2 (NDVI + port activity) — on-demand
  
  agent/
    orchestrator.py    # Główny agent (Claude tool use) — decyduje co robić
    correlations.py    # Reguły cross-domain (rule-based, instant)
    context.py         # Buduje kontekst dla LLM z ostatnich sygnałów
  
  api/
    server.py          # FastAPI: REST + WebSocket /ws/feed + dashboard UI
  
  runner.py            # Main entry point — odpala wszystko async
```

---

## API

| Endpoint | Opis |
|----------|------|
| `GET /` | Dashboard HTML (live feed) |
| `GET /feed` | Agent feed — wpisy bieżaczki (JSON) |
| `GET /signals` | Ostatnie sygnały ze wszystkich źródeł |
| `GET /escalations` | Historia decyzji agenta |
| `GET /polling-rates` | Aktualne interwały pollingu |
| `POST /polling-rates/{source}?seconds=N` | Ręczna zmiana interwału |
| `WS /ws/feed` | WebSocket — live stream sygnałów i eskalacji |

---

## Roadmap

**Q1 — obecny (TRL III→IV)**
- [x] Signal engine z anti-flapping i Z-score
- [x] Moduły: Binance, Deribit, Polymarket, AIS, RSS, Copernicus
- [x] Agent LLM z regułami korelacji cross-domain
- [x] Live feed WebSocket + dashboard

**Q2 — detekcja punktów krytycznych**
- [ ] Klasyfikacja tematyczna RSS (LLM embedding)
- [ ] Utrzymywanie sesji tematycznych (pamięć kontekstowa)
- [ ] Telegram bot dla alertów CRITICAL
- [ ] Pierwszy raport syntetyczny PDF

**Q3 — pilotaż**
- [ ] Multi-agent: osobny agent per domena
- [ ] Integracja GUS / KNF / Eurostat
- [ ] SSO dla instytucji
- [ ] Pełny Sentinel-2 pipeline (rasterio)

---

*Vortex Analytica — TRL II→V · AI/LLM · Dual-use (MVP: cywilny) · B2B/B2G*
