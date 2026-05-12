---
description: Skanowanie Anomalii Polymarket i Rynków (Dumb Money)
---
# Skanowanie Anomalii Cenowych (Polymarket / Opcje)

Ten workflow konfiguruje polecenia dla Antigravity do regularnego skanowania i zapisywania nietypowych szans rynkowych (mispricing) z Polymarketu oraz opcji krypto.

## Krok 1: Pobranie najświeższych rynków
Wywołaj skrypt Pythona (lub napisz nowy w `/tmp/`), który pobiera aktywne rynki z `https://gamma-api.polymarket.com/events?active=true&closed=false&limit=500`. 
Zignoruj kategorie: Sport, Popkultura.
// turbo

## Krok 2: Filtracja Zdarzeń
Odfiltruj zdarzenia według warunków:
- Prawdopodobieństwo "Yes" znajduje się w przedziale 0.001 - 0.15 (1 do 15 centów),
- Słowa kluczowe w tytule: inflation, rates, fed, war, strike, btc, crypto, election, resignation, crash.

## Krok 3: Analiza i Raport
Zapisz przefiltrowaną listę (Top 10) do pliku w formacie markdown w katalogu `data/reports/polymarket_anomalies.md`.

## Krok 4: Skreenshoty Zdarzeń (Weryfikacja Wizualna)
Użyj narzędzia `browser_subagent`, aby wejść na stronę Polymarket dla 2-3 najbardziej interesujących rynków wyłapanych w raporcie i zrób screenshot ułożenia orderbooka (dowód analityczny). Zapisz zrzuty ekranu.

## Krok 5: Alert / Powiadomienie Użytkownika
Użyj narzędzia `notify_user`, aby wyświetlić krótki alert użytkownikowi ze znalezionymi anomaliami rynkowymi i linkami do powiązanych screenów.
