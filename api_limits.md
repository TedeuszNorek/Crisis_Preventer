# Limity API i Architektura: Polymarket (CLOB) vs Kalshi

## 1. Różnica strukturalna: REST (GET) vs WebSocket
*   **REST API (GET/POST):** Model żądanie-odpowiedź. Polega na odpytywaniu serwera o dany stan w danym momencie (tzw. _polling_). Nadaje się idealnie do: pobrania listy aktywnych rynków raz dziennie, zdobycia tokena uwierzytelniającego, wysyłania pojedynczych zleceń egzekucyjnych. Limity mierzone są ilością żądań HTTP na horyzont czasowy (np. 150 requests/second).
*   **WebSocket API (WS):** Połączenie strumieniowe, dwukierunkowe i utrzymywane na stałe (TCP). Wykonujesz jeden "handshake", po czym serwer sam wpycha (_pushes_) wiadomości do Twojego systemu za każdym razem, gdy zmieni się cena lub wpadnie zlecenie na rynek. Niezbędne dla algotradingu i _Signal Engine_. Zamiast limitu zapytań (często go tu nie ma), platformy limitują ilość jednoczesnych połączeń z jednego IP oraz ilość kanałów na jedno połączenie. Od klienta wymaga się wysyłania zwrotnych ramek `Heartbeat / Pong` by uniknąć wyrzucenia z serwera.

---

## 2. Polymarket (CLOB / Gamma API)
Wymusza limity wykorzystując infrastrukturę Cloudflare (zwraca błędy HTTP 429 jeżeli limit zostanie przebity).

**Limity REST API (Standard/Unverified Tier):**
*   `GET /book` (Orderbook), `GET /price`, `GET /midpoint`: **1500 zapytań na 10 sekund** (czyli 150/s).
*   `GET /books`, `GET /prices` (zbiorcze): **500 zapytań na 10 sekund** (50/s).
*   Wysyłanie zleceń (`POST /order`): limit Burst to 500 zleceń / 10 sek, a limit Sustained to 3000 zleceń / 10 minut.
*   Gamma API (dane o rynkach/tokenach): 4000 zapytań na 10 sekund.

**Limity WebSocket API (WS):**
*   Polymarket zniósł niedawny limit wpisywania maksymalnie 100 tokenów na subskrypcję w kanale `Markets`. Obecnie możesz nasłuchiwać nieskończonej liczby rynków.
*   Brak nałożonego hard-limitu ramkowego (message limit), jednakże system musi szybko konsumować bufory, by uniknąć odcięcia przez cloudflare z tytułu "slow readera".

---

## 3. Kalshi (Trade API v2)
Kalshi mocno stawia na profesjonalnych dostawców płynności i dzieli użytkowników na Tiery (Basic, Advanced, Premier, Prime na bazie wolumenu). 

**Limity REST API:**
*   Wymaga podwójnej autoryzacji na operacje niepubliczne korzystając z podpisów asymetrycznych (RSA-PSS) oraz odnawiania tokena co 30 minut. Pula requestów dozwolonych na GET znacznie niższa niż na Polymarkecie dla kont "Basic".
*   Każde anulowanie zlecenia np. operacją zbiorczą (`BatchCancelOrders`) zlicza rzędy wagowo (np. 0.2 wartości transakcji API na sztukę), by nie hamować animowania rynku.

**Limity WebSocket API (WS):**
*   Aby połączyć się przez WS do Kalshi, musisz najpierw pobrać token przez autoryzowany punkt REST, a potem wysłać wiadomość subskrybującą w pierwszych chwilach po podłączeniu WebSocketu do `wss://trading-api.kalshi.com`.
*   **Ważne ograniczenie:** Kalshi wysyła specjalny pakiet wymuszający odpowiedź sieciową co **10 sekund (Ping)**. Brak odpowiedzi `Pong` na czas doprowadza do natychmiastowego zerwania streamu i utraty połączenia.

---

## Wnioski Implementacyjne (Vortex Engine)
Aby stosować się do w/w prawideł w architekturze `Vortex Analytica`:
1. Twój _PolymarketStreamer_ i _KalshiStreamer_ używają REST API podczas ruszania aplikacji (pobranie ID kontraktów geopolitycznych i autoryzacja).
2. Natychmiast po tym wchodzą w asynchroniczną pętlę i przełączają proces główny na **WebSocket**, zrzucając z siebie narzut limitu 150 requestów/sekundę.
3. W _KalshiStreamerze_ należy zaimplementować pętlę async odpowiadającą ramkami PONG w zadanym interwale, by nie tracić dostępu do taśmy.
