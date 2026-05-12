import asyncio
import aiohttp
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [DumbMoneyAgent] %(message)s")

API_URL = "http://localhost:8000/ingest"
# W rzeczywistości to może być WebSocket do Telegram API (np. Telethon dla Tree News) 
# lub X/Twitter API v2 Streaming Endpoint.
MOCK_NEWS_WS = "wss://stream.news-api.local/v1/breaking" 

# Symulowany endpoint do natychmiastowego sprawdzenia ceny na Polymarkecie
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com/events?active=true&closed=false"

# Prosty lokalny estymator NLP (dla szybkości < 50ms)
# W produkcji można tu wpiąć model zero-shot np. DeBERTa zoptymalizowany pod ONNX
def analyze_news_severity(text: str) -> float:
    text_lower = text.lower()
    
    # Słowa kluczowe oznaczające "Czarnego Łabędzia" lub poważne eskalacje
    critical_keywords = ["missile", "strike", "nuclear", "war", "assassinated", "resigns", "emergency", "crash", "hacked"]
    high_keywords = ["troops", "tension", "investigation", "subpoena", "breach", "frozen"]
    
    score = 0.0
    for word in critical_keywords:
        if word in text_lower:
            score += 0.8
    for word in high_keywords:
        if word in text_lower:
            score += 0.4
            
    return min(score, 1.0) # Normalizacja [0, 1]

async def check_arbitrage_opportunity(session, event_topic: str, severity: float):
    """
    Funkcja sprawdza czy "Tłum" (Dumb Money) już zareagował na Polymarkecie.
    Jeśli severity wiadomości jest wysokie (np. wojna), a cena 'YES' jest nadal niska (< 10 centów),
    mamy sygnał arbitrażowy.
    """
    if severity < 0.7:
        return # News nie jest wystarczająco istotny
        
    logging.info(f"High severity event detected ({severity}). Checking Polymarket pricing for '{event_topic}'...")
    
    # Symulowane błyskawiczne pobranie ceny z Polymarketu
    # W rzeczywistości Agent powinien trzymać stan orderbooka w pamięci RAM przez WebSocket Polymarketu!
    await asyncio.sleep(0.1) 
    
    # Zakładamy, że znaleźliśmy powiązany rynek (np. "NATO x Russia clash")
    # i cena to np. 3 centy.
    market_price = 0.03
    
    if market_price < 0.15:
        logging.warning(f"🚨 DUMB MONEY ARBITRAGE DETECTED! Price is {market_price}$ but News Severity is {severity}!")
        
        # Wysłanie sygnału do Signal Engine (Vortex)
        payload = {
            "ts_event": time.time(),
            "source": "dumb_money_agent",
            "entity_type": "arbitrage_opportunity",
            "entity_id": event_topic.upper().replace(" ", "_"),
            "features": {
                "news_severity": severity,
                "current_market_price": market_price,
                "alpha_spread": severity - market_price # Im wyższy spread, tym głupszy/wolniejszy jest tłum
            },
            "dq": {
                "timeliness_s": 0.1, # Czas reakcji od newsa do analizy
                "completeness": 1.0, 
                "consistency": 1.0
            }
        }
        
        try:
             async with session.post(API_URL, json=payload) as resp:
                 if resp.status == 200:
                     logging.info(f"✅ Arbitrage Signal Ingested: {payload['entity_id']}")
                 else:
                     logging.error(f"Failed to ingest, status: {resp.status}")
        except Exception as e:
            logging.error(f"Engine connection failed: {e}")

async def news_stream_worker():
    """
    Asynchroniczny worker utrzymujący stałe połączenie ze źródłem 'Breaking News'.
    Agent nigdy nie polled'uje (odpytuje), on tylko czeka na ramki pushowane przez WebSocket.
    """
    logging.info("Connecting to High-Frequency News WebSocket...")
    
    async with aiohttp.ClientSession() as session:
        # Pętla symulująca odbiór wiadomości z WebSocketu w czasie rzeczywistym
        while True:
            # Symulacja czekania na gwałtowny news...
            await asyncio.sleep(5) 
            
            # Wpadła ramka z WebSocketu Telegrama / Terminala Bloomberg / Tweet
            simulated_ws_frame = {
                "timestamp": time.time(),
                "source": "TreeNews_Telegram",
                "text": "BREAKING: Emergency sirens reported in central capital amid unconfirmed reports of a missile strike.",
                "topic": "Geopolitical Escalation"
            }
            
            logging.info(f"⚡ FAST STREAM RECEIVED: {simulated_ws_frame['text']}")
            
            # 1. Błyskawiczna analiza NLP (Time to process: < 50ms)
            start_t = time.process_time()
            severity = analyze_news_severity(simulated_ws_frame['text'])
            elapsed = (time.process_time() - start_t) * 1000
            
            logging.info(f"NLP Evaluated Severity: {severity} in {elapsed:.2f}ms")
            
            # 2. Strzał do funkcji szukającej asymetrii w wycenie
            asyncio.create_task(check_arbitrage_opportunity(session, simulated_ws_frame['topic'], severity))
            
            await asyncio.sleep(30)

if __name__ == "__main__":
    try:
        asyncio.run(news_stream_worker())
    except KeyboardInterrupt:
        logging.info("Dumb Money Agent shutdown.")
