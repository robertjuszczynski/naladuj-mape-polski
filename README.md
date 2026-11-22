# Naładuj mapę Polski. – dane o defibrylatorach AED w portalu dane.gov.pl

Fork otwartego kodu portalu dane.gov.pl (https://dane.gov.pl/source-code/, `backend_latest` i `frontend_latest` z 21.11.2026) z modułem, który zbiera dane o defibrylatorach AED od dostawców **wewnątrz portalu**: każdy dostawca publikuje własny zbiór według wzorcowego zakresu danych, a portal scala je w jeden wykaz zbiorczy.

- Prototyp: https://178-250-46-63.sslip.io/pl/aed (wersja angielska: /en/aed)
- Panel dostawcy: https://admin.178-250-46-63.sslip.io
- Ścieżka sprawdzenia krok po kroku: [JURY.md](JURY.md)
- Klikalny prototyp bez internetu: `deliverables/prototyp/index.html`; prezentacja: `deliverables/prezentacja/` (HTML i PDF)

## Materiały

| Materiał | Link |
|---|---|
| Prezentacja (HTML, w przeglądarce; → / spacja – dalej, F – pełny ekran) | https://robertjuszczynski.github.io/naladuj-mape-polski/deliverables/prezentacja/prezentacja.html |
| Prezentacja (PDF) | [deliverables/prezentacja/naladuj-mape-polski-prezentacja.pdf](deliverables/prezentacja/naladuj-mape-polski-prezentacja.pdf) |
| Opis rozwiązania i kroki użytkownika (PDF) | [deliverables/prezentacja/naladuj-mape-polski-opis-rozwiazania.pdf](deliverables/prezentacja/naladuj-mape-polski-opis-rozwiazania.pdf) |
| Wideo (2:13) | https://robertjuszczynski.github.io/naladuj-mape-polski/deliverables/prezentacja/wideo/naladuj-mape-polski-wideo.mp4 |
| Klikalny prototyp (bez logowania) | https://robertjuszczynski.github.io/naladuj-mape-polski/deliverables/prototyp/index.html |
| Działający portal z modułem AED | https://178-250-46-63.sslip.io/pl/aed |
| Wzorcowy zakres danych (XLSX) | [deliverables/wzorcowy-zakres-danych-aed.xlsx](deliverables/wzorcowy-zakres-danych-aed.xlsx) |
| Logo (JPG, PNG, PDF, SVG) | [deliverables/znak/logo/](deliverables/znak/logo/) |
| Księga znaku (PDF) | [deliverables/znak/naladuj-mape-polski_ksiega-znaku.pdf](deliverables/znak/naladuj-mape-polski_ksiega-znaku.pdf) |
| Raport dostępności WCAG | [deliverables/wcag/RAPORT.md](deliverables/wcag/RAPORT.md) |

## Kto udostępnia dane

Dostawcą może być każdy dysponent AED, który ma profil dostawcy w dane.gov.pl (instytucja albo firma, zwykle z numerem REGON): urząd, szkoła, szpital, firma, galeria, OSP, fundacja. Udział jest dobrowolny, a każdy dostawca odpowiada za swój zbiór. Gmina może opublikować także AED innych dysponentów ze swojego terenu, jeśli ma ich zgodę lub podstawę prawną (kreator wymaga wtedy osobnego oświadczenia).

Osoba prywatna, która kupiła AED, nie ma profilu dostawcy, a adres jej domu to dane osobowe. Jej AED może trafić do wykazu przez gminę: właściciel zgłasza urządzenie gminie, a gmina publikuje je z oświadczeniem o zgodzie.

## Co zawiera rozwiązanie

- **Wzorcowy zakres danych AED** (30 pól, wersja 0.2.0): `deliverables/wzorcowy-zakres-danych-aed.xlsx`. Minimum od dostawcy to 4 informacje: nazwa, adres, współrzędne (albo sam adres) i dostępność. Zgodny ze standardem technicznym portalu i jego regułami weryfikacji jakości; pola mają odpowiedniki w tagach OpenStreetMap i francuskiej bazie Géo'DAE.
- **Kreator „Dodaj dane o AED” w panelu dostawcy** (`backend/mcod/aed/`): plik CSV/XLSX w dowolnym układzie, dopasowanie kolumn, automatyczne poprawki (zamienione współrzędne, adres w jednej kolumnie, przecinek dziesiętny, godziny zapisane tekstem), współrzędne z adresu (geokodowanie GUGiK), wstrzymanie rekordów, których nie da się poprawić, decyzja dostawcy przy duplikatach, licencja z listy portalu, publikacja jako natywny zbiór i pobranie poprawionego pliku.
- **Wykaz zbiorczy AED w logice portalu** (wzorowany na wykazie chronionych danych DGA): zasób ma nowe pole „Wykaz zbiorczy” (`Resource.aggregated_register`), dostępne w zwykłym formularzu zasobu, w kreatorze i w harvesterze (CKAN: `aggregated_register`, XML: `aggregatedRegister` w schemacie 1.14). Zadanie Celery `build_aed_register_task` co noc i chwilę po zmianie oznaczonego zasobu odczytuje wszystkie takie zasoby (plik albo link, np. lista w BIP), dopasowuje kolumny do wzorcowego zakresu, poprawia typowe błędy i scala je w zasób „Defibrylatory AED w Polsce (CSV)” w zbiorze „Defibrylatory AED w Polsce – wykaz zbiorczy”. Raport źródeł (co odczytano, ile rekordów, co odpadło i dlaczego) jest w panelu: „Wykaz zbiorczy AED” (model `AggregatedAedInfo`, jak `AggregatedDGAInfo`). Kolejne wykazy dodaje się nową wartością pola i definicją wzorca. Wykaz jest pokazany na portalu tak samo jak wykaz chronionych danych DGA: strona `/pl/aed/wykaz` używa tych samych komponentów (tabela danych zasobu, pobieranie plików, filtry, liczniki), a endpoint `/aed/aggregated` zwraca to samo co `/dga-aggregated`. Różni się tylko zakresem kolumn (30 pól wzorcowego zakresu AED).
- **Jak najwięcej AED bez łamania licencji – trzy koszyki** (panel: „Defibrylatory AED” → „Pozyskiwanie danych” i „Źródła zewnętrzne”):
  1. *Potwierdzone przez dysponentów* – zasoby oznaczone jako wykaz AED (kreator, „Dodaj jeden AED”, zwykły formularz zasobu, harvester).
  2. *Ze źródeł publicznych* – listy, które wolno publikować (CC0, CC BY, informacja publiczna z BIP), portal pobiera sam co noc (CSV, XLSX, tabela w PDF) i publikuje z podaniem autora jako „niepotwierdzone”. Przykład: wykaz AED Krakowa (PDF w BIP). Gdy ten sam AED opublikuje dysponent, wersja niepotwierdzona znika z wykazu.
  3. *Czekają na zgodę* – źródła, których licencja nie pozwala publikować (np. OpenStreetMap, ODbL). Dane są tylko wewnętrznie, pogrupowane w prośby o zgodę: po jednej na dysponenta (np. ZUS, InPost) albo na gminę jako pośrednika. Operator wysyła zaproszenie e-mail, notuje rozmowy, a po zgodzie publikuje AED jako potwierdzone przez dysponenta.

  Danym spoza portalu nie ufamy. Każdy punkt z każdego źródła (CSV, XLSX, PDF, OpenStreetMap; nowe źródło dodaje się w panelu) trafia do gminy, na której terenie leży, w „AED do potwierdzenia”. Gmina sprawdza go i zapisuje jako własne dane („To nasz”), wskazuje innego dysponenta („Nie nasz”, informacja trafia do Ministerstwa) albo odrzuca („Nie ma go”). Decyzje przetrwają nocne pobieranie źródeł.
  W API każdy AED ma pole `verified`, więc system 112 sam decyduje, czy używa też niepotwierdzonych.
- **Eksport w otwartych formatach**: zbiór wykazu ma dwa zasoby, odświeżane przy każdym scaleniu: „Defibrylatory AED w Polsce (CSV)” (z widokiem tabeli) i „Defibrylatory AED w Polsce (GeoJSON)” (punkty WGS 84, wszystkie pola wzorcowego zakresu jako właściwości). Portal sam dodaje JSON-LD, a API portalu podaje dane tabelaryczne jako JSON.
- **API modułu** (`https://api.178-250-46-63.sslip.io`):

  | Adres | Co zwraca |
  |---|---|
  | `/aed` | wszystkie AED z dostępnością na teraz albo na `?at=RRRR-MM-DDTGG:MM`; `?format=geojson` – GeoJSON |
  | `/aed/{id}` | jeden AED ze wszystkimi polami i historią poprawek |
  | `/aed/nearest?address=…` albo `?lat=…&lon=…` | 3 najbliższe AED dostępne o wskazanej porze, z czasem dojścia |
  | `/aed/address?q=…` | podpowiedzi adresów (GUGiK) |
  | `/aed/stats` | liczniki, pokrycie gmin i województw, koszyki źródeł |
  | `/aed/aggregated` | zbiór i zasób wykazu – ten sam format co `/dga-aggregated` |
  | `POST /aed/{id}/report` | zgłoszenie problemu z AED (trafia do „Do sprawdzenia” dostawcy) |

- **Jakość danych** – każde wgranie i każde scalenie sprawdza:
  - *duplikaty*: ten sam punkt w pliku czeka na decyzję dostawcy; ten sam AED z dwóch źródeł (do 30 m) albo ten sam identyfikator w dwóch zasobach trafia do wykazu raz;
  - *błędne współrzędne*: punkt poza Polską, poza gminą dostawcy, tuż przy granicy gminy, zamienione szerokość i długość (poprawiane automatycznie, gdy po zamianie punkt leży w gminie), brak współrzędnych (ustalane z adresu przez GUGiK; sam adres miasta nie wystarczy);
  - *sprzeczne dane*: „dostępny całodobowo” niezgodny z godzinami, data przeglądu w przyszłości, piętro przy AED na zewnątrz budynku, a między źródłami różne godziny, dostępność, stan albo rodzaj dostępu tego samego AED. Lista sprzeczności jest w raporcie „Wykaz zbiorczy AED”;
  - *format i kompletność*: pola obowiązkowe, formaty dat, kodów i godzin (opening_hours), dane osobowe (adresy e-mail) oraz reguły weryfikacji jakości portalu.
- **Frontend portalu**: pasek akcji na górze portalu, strona akcji z wyszukiwaniem najbliższego dostępnego AED (adres, sama ulica albo lokalizacja), mapą (także zdjęcie lotnicze GUGiK), dostępnością w wybranym dniu i godzinie, mapą z kropek „Ile mapy już naładowaliśmy?”, wykazem w tabeli (`/pl/aed/wykaz`), strona AED ze zgłoszeniem problemu, wersja PL/EN, tryby wysokiego kontrastu portalu.
- **Kampania**: nazwa i hasło „Naładuj mapę Polski.”, logo i księga znaku w `deliverables/znak/`.

## Dane, źródła i licencje

| Źródło | Wydawca | Licencja | Jak trafia do wykazu |
|---|---|---|---|
| 5 zbiorów AED w dane.gov.pl | urzędy Warszawy, Legionowa, Przemyśla, Krosna, Marek | CC BY 4.0 (Warszawa, Marki), CC0 (pozostałe) | zasoby oznaczone jako wykaz AED, potwierdzone przez dysponenta |
| Wykaz AED programu „AED Impuls Życia” (PDF w BIP) | Urząd Miasta Krakowa | informacja publiczna | pobierany co noc, publikowany z podaniem źródła jako „niepotwierdzony” |
| Defibrylatory w OpenStreetMap | współtwórcy OSM | ODbL | tylko wewnętrznie: „AED do potwierdzenia” dla gmin i kolejka zgód; nie publikujemy |
| Rejestr adresów (geokodowanie), ortofotomapa, granice województw (PRG) | GUGiK | otwarte dane | współrzędne z adresu, adres z pinezki, zdjęcie lotnicze, mapa z kropek |

Każdy rekord wykazu ma w polu `zrodlo_danych` nazwę źródła, adres i licencję. Wykaz zbiorczy ma licencję CC BY 4.0 – najbardziej wymagającą spośród licencji źródeł, które wolno publikować (CC0 i informacja publiczna są z nią zgodne). Danych OpenStreetMap nie publikujemy: ODbL wymaga tej samej licencji dla bazy pochodnej, a tej nie ma na liście licencji portalu.

Metadane zbioru wykazu: tytuł „Defibrylatory AED w Polsce – wykaz zbiorczy”, opis z listą źródeł i licencji, dostawca Ministerstwo Cyfryzacji (Departament Zarządzania Danymi), częstotliwość aktualizacji „codziennie”, kategoria „Zdrowie”, słowa kluczowe AED, defibrylator, Naładuj mapę Polski. Zbiory dostawców mają częstotliwość „co miesiąc” i licencję wybraną przez dostawcę.

## Uruchomienie

**Zalecane: testowanie na domenie.** Działający portal jest pod adresem https://178-250-46-63.sslip.io/pl/aed (panel dostawcy: https://admin.178-250-46-63.sslip.io, konta demo w opisie zgłoszenia). Tylko tam wszystko działa naprawdę: wyszukiwanie adresów, najbliższy AED o wybranej porze, wgrywanie własnego pliku, zapisywanie poprawek, mapa i wykaz z aktualnymi danymi.

**Gdy domena nie jest dostępna** (np. komputer bez internetu albo z blokadą adresów): klikalny prototyp `deliverables/prototyp/index.html` – otwiera się w przeglądarce bez internetu i bez instalacji. To wersja uproszczona, słabsza od domenowej: składa się ze zrzutów ekranów z 22.11.2026, prowadzi przez przygotowane ścieżki, nie zapisuje danych, a klikalne są tylko elementy, które prowadzą do kolejnego zrzutu.

Uruchomienie u siebie od zera:

**Wymagania:** Docker z Docker Compose v2, ok. 8 GB RAM dla kontenerów (Elasticsearch), 15 GB miejsca, Node.js 20+ (tylko do frontendu w trybie deweloperskim). Najprościej na Linuksie – tak działa nasz serwer. Na macOS adresy sieci dockerowej nie są osiągalne z hosta (zob. uwaga w `backend/README.md`).

1. Backend portalu (szczegóły w `backend/README.md`):

   ```shell
   cd backend
   cp env.sample .env                       # ustaw MCOD_NGINX_* jak w backend/README.md; DISCOURSE_FORUM_ENABLED=false
   echo "172.18.18.100 mcod.local api.mcod.local admin.mcod.local cms.mcod.local mail.mcod.local" | sudo tee -a /etc/hosts
   docker compose -f docker-compose.local.yml build
   docker compose -f docker-compose.local.yml run mcod-local-run python manage.py init_mcod_db
   docker compose -f docker-compose.local.yml up -d   # docker-compose.local.yml dołącza bazę, Redis, Elasticsearch
   ```

2. Moduł AED – migracje, dostawcy demonstracyjni z danymi z dane.gov.pl, wykaz zbiorczy:

   ```shell
   docker compose -f docker-compose.local.yml run mcod-local-run python manage.py migrate
   docker compose -f docker-compose.local.yml run -e AED_DEMO_PASSWORD=<hasło-demo> mcod-local-run python manage.py aed_seed
   docker compose -f docker-compose.local.yml run mcod-local-run python manage.py aed_rebuild
   ```

   `aed_seed` zakłada 5 urzędów z kontami `aed@<miasto>.example` i ich zbiory, `aed_rebuild` od razu scala wykaz (normalnie robi to Celery co noc o 3:45 i chwilę po zmianie oznaczonego zasobu; zadania nocne wymagają włączenia celery beat w `CELERY_OPTS` usługi `mcod-local-celery`, zob. `backend/README.md`). Odczyt tabel z PDF (źródło Kraków) wymaga w kontenerach panelu i Celery: `pip install --no-deps pdfplumber==0.11.4 pdfminer.six pypdfium2` (bez zmiany Pillow 8.4, której wymaga Wagtail).

3. Frontend:

   ```shell
   cd frontend
   npm install
   npm start                                # tryb deweloperski, https://mcod.local
   ```

   Wersja jak na serwerze demonstracyjnym (statyczny build w kontenerze): `cd backend && docker compose -f docker-compose.local.yml -f deploy/docker-compose.deploy.yml up -d --build mcod-frontend`.

4. Otwórz https://mcod.local/pl/aed (strona akcji), https://mcod.local/pl/aed/wykaz (wykaz) i https://admin.mcod.local (panel dostawcy). Ścieżka sprawdzenia krok po kroku: [JURY.md](JURY.md).

**Testy modułu:** `docker compose -f docker-compose.local.yml run mcod-local-tests mcod/aed/tests --no-cov` (82 testy). Pliki do przetestowania kreatora: `backend/mcod/aed/data/testowe/` (opis w README w tym katalogu).

**Serwer demonstracyjny:** warstwa `backend/deploy/` (domena, certyfikaty, statyczny frontend): `docker compose -f docker-compose.local.yml -f deploy/docker-compose.deploy.yml up -d`.

## Ograniczenia

- Publikacja w produkcyjnym dane.gov.pl wymaga wdrożenia modułu przez operatora portalu; demonstracja działa na forku na naszym serwerze.
- Reguła „punkt poza gminą” działa dla gmin z danych startowych (granice w `data/gminy.geojson`); pełny zestaw granic to PRG z GUGiK. Kod TERYT gminy dostawcy jest w demonstracji przypisany do znanych dostawców, dlatego „AED do potwierdzenia” widzi 5 urzędów demonstracyjnych; w portalu produkcyjnym kod TERYT powinien być polem profilu instytucji.
- Logowanie przez login.gov.pl istnieje w portalu, ale wymaga certyfikatu wydawanego przez COI; w demonstracji przycisk jest ukryty i używamy kont e-mail i hasło.
- Publiczne serwery OpenStreetMap (Overpass) bywają przeciążone; gdy pobieranie się nie uda, portal spróbuje ponownie następnej nocy, a dotychczasowe dane zostają.
- Część godzin dostępności zapisanych opisowo (np. „w godzinach otwarcia stacji metra”) nie daje się zamienić na format opening_hours; takie AED mają status „dostępność nieznana”.
- Nie ma integracji z systemem dyspozytorskim 112. API (pole `verified`, dostępność na wskazaną godzinę, najbliższy AED) jest gotowe do podłączenia.
- Dostępność sprawdziliśmy automatycznie (Lighthouse) na stronach publicznych. Kreatora w panelu dostawcy nie testowaliśmy, bo wymaga zalogowania; korzysta z szablonów panelu portalu.

## Użycie AI (regulamin zadania §2.8)

Przy pracy korzystaliśmy z asystenta AI (Claude) do analizy dokumentacji i kodu portalu, propozycji architektury, generowania i refaktoryzacji kodu (moduł Django, komponenty Angular, testy), konfiguracji serwera i szkiców materiałów. Głos lektora w filmie to syntezator ElevenLabs. Każdą zmianę przejrzał, uruchomił i zatwierdził autor. Decyzje autora: moduł w portalu zamiast kolejnej mapy, wykaz zbiorczy na wzór wykazu chronionych danych DGA, trzy koszyki danych zależnie od licencji, zakres 30 pól. Sygnet logo to uproszczony kontur Polski z danych Natural Earth (domena publiczna) z pulsem zaprojektowanym przez autora; napis złożono krojem Manrope (SIL OFL).

## Licencja

Moduł AED i nasze zmiany: MIT, zob. [LICENSE](LICENSE). Kod portalu dane.gov.pl pozostaje na licencji jego autorów (https://dane.gov.pl/source-code/).
