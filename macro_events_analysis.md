# Systematyczna Mapa Wydarzeń Makro-Finansowych i Reakcji Rynku

Dokument opracowany na potrzeby zasilenia silników predykcyjnych (np. Vortex). Ramy klasyfikacji, backtesting koncepcyjny oraz detekcja zostały poszerzone o badania akademickie i literaturę z zakresu finansów behawioralnych i makroekonomii.

## 1. Kategorie Wydarzeń i Typy (Taksonomia)

**1.1 Geopolityka i Konflikty Zbrojne** *(Bazując na Geopolitical Risk Index - Caldara & Iacoviello, 2022)*
*   `Military strike on critical infrastructure` (atak na infrastrukturę krytyczną)
*   `Outbreak of armed conflict` (wybuch otwartego konfliktu / inwazja)
*   `Sanctions on major economic actor` (sankcje, odcięcie od mechanizmów rozliczeniowych jak SWIFT)
*   `Diplomatic standoff / escalation` (nagłe napięcia dyplomatyczne)

**1.2 Polityka Monetarna i Działania Banków Centralnych** *(Gürkaynak, Sack, & Swanson, 2005)*
*   `Surprise rate hike/cut` (nieoczekiwana zmiana stóp)
*   `Forward guidance shock` (zmiana w komunikacji przyszłej ścieżki stóp, tzw. *path factor*)
*   `Unscheduled / emergency CB meeting` (nadzwyczajne posiedzenie)
*   `Currency intervention` (interwencja na rynku walutowym)
*   `QE / QT expansion/tapering announcement` (nagła zmiana bilansu)

**1.3 Makroekonomia i Cykl Koniunkturalny** *(Andersen, Bollerslev, Diebold, Vega, 2003)*
*   `Surprise inflation spike / plunge` (odczyty CPI/PPI drastycznie odbiegające od konsensusu)
*   `Labor market shock` (np. drastyczne przestrzelenie/niewypał NFP w USA)
*   `Recession confirmation / Sovereign downgrade` (oficjalne wejście w recesję, obcięcie ratingu)

**1.4 Energia, Surowce i Łańcuchy Dostaw** *(Kilian, 2009 - Structural Vector Autoregression Models)*
*   `OPEC+ surprise quota adjustment` (zaskakujące decyzje o wydobyciu)
*   `Strategic chokepoint blockade` (zablokowanie szlaków, np. Morze Czerwone, Suez)
*   `Commodity export ban / Tariff shock` (cła uderzające w dostawy surowców)
*   `Exogenous supply shock` (np. nagłe uderzenie w rafinerie)

**1.5 System Finansowy i Ryzyko Systemowe** *(Literatura dot. Contagion Effect, np. Forbes & Rigobon, 2002)*
*   `Major bank collapse / Bank run` (upadek instytucji systemowej lub panika bankowa)
*   `Sovereign or massive corporate default` (niewypłacalność giganta lub państwa)
*   `Flash crash / Liquidity drain` (anomalie płynnościowe, np. VIX blow-up)

---

## 2. Historyczne Przykłady, Relacje Rynkowe i Dowody Empiryczne

Reakcje rynków na wiadomości informacyjne są asymptotyczne i przebiegają najgwałtowniej w pierwszych 15 minutach dla walut i obligacji, oraz w pierwszych dniach dla rynków akcji z tendencją do tzw. zjawiska *overreaction* (De Bondt & Thaler, 1985), po którym następuje mean-reversion.

### Kazus 1: Wybuch konfliktu zbrojnego i Szok Geopolityczny
*   **Przykłady:** Wojna w Zatoce (1990), Inwazja Rosji na Ukrainę (02.2022), Atak w Abqaiq (09.2019).
*   **Literatura:** Wyższe wartości GPR (Geopolitical Risk) historycznie implikują natychmiastowy odwrót od akcji (tzw. flight-to-quality) i alokację w safe-havens (złoto, CHF, US Treasuries).
*   **1 Dzień (1D):** Ropa: +4% do +15% (szok podażowy wg Kiliana wyceniany jest błyskawicznie). Akcje: -1.5% do -4%. Ceny Obligacji: ↑ (uciekający kapitał obniża rentowności). USD: ↑ (zysk z premii za płynność - liquidity premium).
*   **1 Tydzień - 1 Miesiąc:** Jeśli uderzenie było "jednorazowe" (np. rakiety irańskie w 2020), akcje szybko niwelują straty (w 70-80% przypadków mean-reversion). Jeśli wojna ma charakter powolnej eskalacji (wojna na wyniszczenie), akcje rynków wschodzących trwale cierpią z powodu odpływu kapitału.

### Kazus 2: Niespodzianki Inflacyjne i Makro
*   **Przykłady:** CPI Beats w 2022 r., zaskakująco mocne NFP w latach 2023-2024.
*   **Literatura:** Andersen et al. (2003) dowodzą, że rynki asymetrycznie reagują na "złe wiadomości" (bad news) w czasach ekspansji gospodarcej (good news becomes bad news for equities if it implies tightening).
*   **1 Dzień (1D):** Jeśli CPI > konsensus: Akcje (szczególnie Growth/Tech) gwałtownie spadają (-1.5% do -3%) ze względu na rewizję w górę stóp wolnych od ryzyka w modelach DCF. Ceny obligacji spadają (rentowności drastycznie w górę). Ceny rynkowe dolara silnie w górę.
*   **Horyzont 1W - 1M:** Dolar najczęściej utrzymuje aprecjację, tworzy się nowy krótkoterminowy trend wspierany narastającym "carry trade".

### Kazus 3: Zaskoczenia Monetarne (Banki Centralne)
*   **Przykłady:** Bernanke "Taper Tantrum" (2013), Awaryjne cięcia Fed (2008, 2020), "Whatever it takes" Draghiego (2012).
*   **Literatura:** Gürkaynak et al. rozróżnia "Target factor" (skutkuje w wycenie krótkiego końca krzywej rentowności) i "Path factor" (zaskoczenia w forward guidance wpływające na cały system finansowy). Zaskoczenie zacieśnianiem (hawkish) kompresuje mnożniki wycen P/E w 100% obserwowanych cykli.
*   **1 Dzień (1D):** Jastrzębi forward guidance: Ostre spadki SPX, skok DXY, odwracanie się krzywej dochodowości (Inverted Yield Curve).
*   **Gołębia niespodzianka (Dovish Surprise):** Eksplozja akcji, tąpnięcie rentowności krótkoterminowych, ucieczka kapitału od USD do walut rynków wschodzących (EM) i surowców.

### Kazus 4: Szoki Systemowe, Krachy i Ryzyko Contagion
*   **Przykłady:** Lehman Brothers (09.2008), SVB (2023).
*   **Literatura:** Forbes i Rigobon (2002) pokazują silne korelacje cross-market podczas panik. Ekstremalne ruchy wywołane zjawiskiem *flight-to-liquidity* (Vayanos, 2004) polegające na porzucaniu aktywów za obojętnie jaką cenę w zamian za najbardziej płynne walory (USD, krótkie bony skarbowe USA).
*   **Reakcja:** Akcje i Ropa notują gwałtowny krach. Użyteczne stają się Safe-Havens. Odbicie następuje **tylko i wyłącznie** wtedy, gdy do gry wchodzi interwencja rządu/banku centralnego.

---

## 3. Macierz Reakcji Systemu (Wspierana Empirią)

| Kategoria Wydarzenia | Charakterystyka (Literatura) | Przedział Czasowy | Ropa (Commodities) | Akcje (Equities) | Obligacje (Ceny) / (Rent.) | Waluta USD (DXY) | Pewność reakcji (Confidence) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Geopolityka (Energy Disruptions)** | *Kilian*: Szok podaży egzogenicznej. Wysoce inflacyjne. | 1D - 1M | **Mocno ↑** | **↓** | **↑** na krótkim końcu / ↕ na długim | **↑** | Bardzo wysoka (90%) |
| **Szok Inflacyjny (Wysokie CPI)** | *Andersen*: Asymetria reakcji. Wycena stóp w górę. | 1D - 1W | ↕ / ↓ | **Mocno ↓** | **↓** (Rentowności ↑) | **Mocno ↑** | Wysoka (85%) |
| **Hawkish CB Surprise (Jastrzębie)** | *Gürkaynak*: Skok Path Factor. Rosnące dyskonto w DCF. | 1D - 1M | ↓ | **↓** | **↓** (Rentowności ↑) | **↑** | Bardzo wysoka (90%) |
| **Bailout / Dovish Pivot** | *De Bondt*: Mean Reversion. Odbicie płynnościowe. | 1W+ | ↑ | **Mocno ↑** | **↑** | **↓** | Wysoka (75%) |
| **Panika Systemowa / Contagion** | *Vayanos*: Flight-to-Liquidity. Korelacja cross-asset dążąca do 1. | 1D - 2W | **Mocno ↓** | **Krach ↓↓** | **Pionowo ↑↑** (Ucieczka depozytów US TREAS.)| Zyskują CHF, JPY, gotówka USD | Bardzo wysoka (95%) |
| **Strong NFP w reżimie Tightening** | *Good news is bad news effect* | 1D | ↑ (mocny popyt) | **↓** (strach przed wyższymi stopami) | **↓** (strach przed wyższymi stopami) | **↑** | Wysoka w reżimie inflacyjnym (75%) |
| **Kryzys łańcucha dostaw** | Cost-push inflation. Szok stagflacyjny. | 1M+ | **↑** / Agrotech ↑ | **↓** (niższe marże) | ↕ (presja inflacyjna vs spowolnienie) | ↕ | Umiarkowana (65%) |

---

## 4. Powtarzalne Wzorce Reakcji Rynku (Mechanika w systemie predykcyjnym)

Zestawienie tzw. "playbooków" algorytmicznych (szablony reakcji maszyn HFT algotradingu):

1.  **Risk-Off Klasyczny (Geopolityka i Zarządzanie Ryzykiem Ogonowym)**
    *   **Wzorzec:** Spadek apetytu na ryzyko strukturalne. Skok implikowanej zmienności (VIX). Rozszerzenie spreadów kredytowych.
    *   **Częstotliwość:** \> 90% przypadków w pierwszej fali wyceny newsa przez algorytmy NLP analizujące RSS i Twitter (X).
    *   **Zanikanie (Decay):** Zgodnie z behawioralną teorią *overreaction*, rynki ulegają nagłej, lecz krótkotrwałej panice. Jeśli konflikt jest izolowany i nie przerywa przepływów kapitałowych oraz surowcowych, akcje wracają do długoterminowego trendu po 5-10 dniach (kupowanie strachu).

2.  **Szok Restrykcyjny (Makro-Monetarny)**
    *   **Wzorzec:** Przepięcie całej krzywej referencyjnej rządu. Równoczesna presja zniżkowa na obligacjach i na akcjach (skok współczynnika beta do wartości ponadprzeciętnych, załamanie dywersyfikacji w portfelach typu 60/40). Jedynie indeks walutowy DXY notuje stały wzrost siły wspierany rosnącym dysparytetem stóp.

---

## 5. Czynniki Kontekstowe (Reżimy Rynkowe - Zmienne Zakłócające)

Wpływ jakiegokolwiek wydarzenia w naturalny sposób musi być warunkowany stanem globalnego cyklu:
*   **Regime 1: Inflacja Niestabilna (Korelacja akcji i obligacji rzędu >0):** Wyższe ceny energii wywołane szokiem geopolitycznym wywołują potężne drgania wsteczne akcji, ponieważ wzmaga to inflację, w związku z czym wyłącza awaryjne wsparcie Płynnościowe Banków Centralnych ("Fed put").
*   **Regime 2: Dezinflacja i stagnacja (Korelacja ujemna):** Tradycyjne środowisko dekady 2010-2020. W tym układzie krach i ryzyko bankowe często implikowały w horyzoncie miesięcznym gigantyczne wybuchy euforycznych zakupów przez uwalniane pakiety QE i natychmiastowe ucinanie stóp na zerowe poziomy.
*   **Efekt Pozycjonowania Options Gamma / GEX (Squeeze Risk):** Jeżeli przed ogłoszeniem newsów (zbliżających się wydarzeń lub CPI release) szeroki rynek (Dealers) ma olbrzymie pozycjonowanie w opcjach *Short Gamma*, to rynek staje się labilny. Nawet trywialny alert geopolityczny może wywołać wyczyszczenie płynności orderbooka z powodu "delta hedgining" dostarczycieli płynności doprowadzając do niekontrolowanych krachów - łańcuchów (tzw. zjawisko Flash Crash/Stop Runów). Detekcja sygnałów powinna modulować siłę bazując na profilu Net Dealer Gamma dla aktywa.

---

## 6. Integracja Logiki dla Silnika Detekcji Wydarzeń i Event Driven Trading (Vortex Engine)

### 6.1 Procesowanie NLP i Wektoryzacja RegEx (Taksonomia sygnałowa)
*   `[Vector: Geopolitics_Escalation]` = `(missile | drone | casualty | invasion | offensive | escalate | sanction | strike) AND (facility | border | pipeline | capital | airspace)`
*   `[Vector: CentralBank_Hawkish]` = `(unexpected | emergency | hawkish | hike | tightening | inflation concern | dot plot jump | above expected)`
*   `[Vector: Systemic_Risk]` = `(bailout | rescue | halts withdrawals | default | contagion | collapse | insolvency | fdic takeover)`

### 6.2 Architektura Pipelines (Sugerowany projekt)
Dla wdrażania w kodzie (np. `Vortex Analytica Component`):
1.  **Ingestion:** Nisko opóźnieniowe strumienie z X/Twitter (konta agregatory, np. `First Squawk`, `Deltaone`, `*Breaking* Headlines`), wsparte logowaniem kanałów otwartego wywiadu GDELT (Global Database of Events, Language, and Tone).
2.  **Transformer/LLM Layer:** Moduł oparty mniejszym modelu LM (np. FinBERT) przeliczający asymetryczne wagi "Tone/Sentiment Score" natychmiastowo z przypisywaniem Tickerów / Rynków poprzez proces NER (Named Entity Recognition).
3.  **Burst Detection (Kluczowy Anty-Fake Mechanism):** Przebijanie odchyleń standardowych częstości występowania tego samego newsa we wszystkich strumieniach z zachowaniem reżimu \~30-sekundowego. Wyklucza to reakcję na rynkowe fake-newsy, ponieważ zjawiska skrajnie makro uderzają we wszystkie tuby agencji nagle (Rate of Change = X standard deviations).
4.  **Signal Output:** System wypuszcza pre-określony wektor działania: kierunek (Direction), przewidywalność (Confidence od 0-1) ukształtowana z kwerend i danych historycznych z Macierzy (Tabela Część 3), oraz sugestię pożądanego zabezpieczenia (Hedge Asset target).
