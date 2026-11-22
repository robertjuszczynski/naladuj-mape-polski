# Naładuj mapę Polski. – dane o defibrylatorach AED w portalu dane.gov.pl

HackNation 2026, wyzwanie „Misja AED – dane na ratunek” (Departament Zarządzania Danymi, Ministerstwo Cyfryzacji).

Fork otwartego kodu portalu dane.gov.pl (https://dane.gov.pl/source-code/, `backend_latest` i `frontend_latest` z 21.11.2026) z modułem, który zbiera dane o defibrylatorach AED od dostawców **wewnątrz portalu**: każdy dostawca publikuje własny zbiór według wzorcowego zakresu danych, a portal scala je w jeden wykaz zbiorczy.

- Prototyp: https://178-250-46-63.sslip.io/pl/aed (wersja angielska: /en/aed)
- Panel dostawcy: https://admin.178-250-46-63.sslip.io
- Ścieżka sprawdzenia krok po kroku: [JURY.md](JURY.md)

## Kto udostępnia dane

Dostawcą może być każdy dysponent AED z numerem REGON i profilem dostawcy w dane.gov.pl: urząd, szkoła, szpital, firma, galeria, OSP, fundacja. Udział jest dobrowolny, a każdy dostawca odpowiada za swój zbiór. Gmina może opublikować także AED innych dysponentów ze swojego terenu, jeśli ma ich zgodę lub podstawę prawną (kreator wymaga wtedy osobnego oświadczenia).

## Co zawiera rozwiązanie

- **Wzorcowy zakres danych AED** (30 pól, wersja 0.2.0): `deliverables/wzorcowy-zakres-danych-aed.xlsx`. Minimum od dostawcy to 4 informacje: nazwa, adres, współrzędne (albo sam adres) i dostępność. Zgodny ze standardem technicznym portalu i jego regułami weryfikacji jakości; pola mają odpowiedniki w tagach OpenStreetMap i francuskiej bazie Géo'DAE.
- **Kreator „Dodaj dane o AED” w panelu dostawcy** (`backend/mcod/aed/`): plik CSV/XLSX w dowolnym układzie, dopasowanie kolumn, automatyczne poprawki (zamienione współrzędne, adres w jednej kolumnie, przecinek dziesiętny, godziny zapisane tekstem), współrzędne z adresu (geokodowanie GUGiK), wstrzymanie rekordów, których nie da się poprawić, decyzja dostawcy przy duplikatach, licencja z listy portalu, publikacja jako natywny zbiór i pobranie poprawionego pliku.
- **Wykaz zbiorczy AED w logice portalu** (wzorowany na wykazie chronionych danych DGA): zasób ma nowe pole „Wykaz zbiorczy” (`Resource.aggregated_register`), dostępne w zwykłym formularzu zasobu, w kreatorze i w harvesterze (CKAN: `aggregated_register`, XML: `aggregatedRegister` w schemacie 1.14). Zadanie Celery `build_aed_register_task` co noc i chwilę po zmianie oznaczonego zasobu odczytuje wszystkie takie zasoby (plik albo link, np. lista w BIP), dopasowuje kolumny do wzorcowego zakresu, poprawia typowe błędy i scala je w zasób „Defibrylatory AED w Polsce (CSV)” w zbiorze „Defibrylatory AED w Polsce – wykaz zbiorczy”. Raport źródeł (co odczytano, ile rekordów, co odpadło i dlaczego) jest w panelu: „Wykaz zbiorczy AED” (model `AggregatedAedInfo`, jak `AggregatedDGAInfo`). Kolejne wykazy dodaje się nową wartością pola i definicją wzorca.
- **Jak najwięcej AED bez łamania licencji – trzy koszyki** (panel: „Defibrylatory AED” → „Pozyskiwanie danych” i „Źródła zewnętrzne”):
  1. *Potwierdzone przez dysponentów* – zasoby oznaczone jako wykaz AED (kreator, „Dodaj jeden AED”, zwykły formularz zasobu, harvester).
  2. *Ze źródeł publicznych* – listy, które wolno publikować (CC0, CC BY, informacja publiczna z BIP), portal pobiera sam co noc (CSV, XLSX, tabela w PDF) i publikuje z podaniem autora jako „niepotwierdzone”. Przykład: wykaz AED Krakowa (PDF w BIP). Gdy ten sam AED opublikuje dysponent, wersja niepotwierdzona znika z wykazu.
  3. *Czekają na zgodę* – źródła, których licencja nie pozwala publikować (np. OpenStreetMap, ODbL). Dane są tylko wewnętrznie, pogrupowane w prośby o zgodę: po jednej na dysponenta (np. ZUS, InPost) albo na gminę jako pośrednika. Operator wysyła zaproszenie e-mail, notuje rozmowy, a po zgodzie publikuje AED jako potwierdzone przez dysponenta.
  W API każdy AED ma pole `verified`, więc system 112 sam decyduje, czy używa też niepotwierdzonych.
- **API**: `/aed`, `/aed/stats`, `/aed/{id}`, dostępność liczona na wskazaną godzinę (`?at=RRRR-MM-DDTGG:MM`).
- **Frontend portalu**: pasek akcji na górze portalu, strona akcji z licznikiem „Ile mapy już naładowaliśmy?”, mapą i dostępnością w wybranym dniu i godzinie, strona AED ze zgłoszeniem problemu przez mechanizm uwag do zbioru, wersja PL/EN, tryby wysokiego kontrastu portalu.
- **Kampania**: nazwa i hasło „Naładuj mapę Polski.”, logo i księga znaku w `deliverables/znak/`.

## Dane

Dane startowe pochodzą z 5 zbiorów AED opublikowanych w dane.gov.pl: Warszawa (CC BY 4.0), Legionowo (CC0), Przemyśl (CC0), Krosno (CC0), Marki (CC BY 4.0). Danych OpenStreetMap nie włączamy: licencja ODbL wymaga tej samej licencji dla bazy pochodnej i nie ma jej na liście licencji portalu.

## Uruchomienie

Zgodnie z README portalu (`backend/README.md`, docker compose). Konfiguracja serwera demonstracyjnego: `backend/deploy/`. Po starcie portalu:

```
python manage.py migrate aed
AED_DEMO_PASSWORD=... python manage.py aed_seed   # dostawcy demonstracyjni i ich zbiory
python manage.py aed_rebuild                      # scalenie wykazu zbiorczego od razu (normalnie co noc)
```

Testy modułu: `pytest mcod/aed/tests`. Czytanie tabel z PDF wymaga `pdfplumber` (w obrazie z Pillow 8.4 dla Wagtail: `pip install --no-deps pdfplumber==0.11.4 pdfminer.six pypdfium2`). Pliki do testów kreatora: `backend/mcod/aed/data/testowe/` (opis w README w tym katalogu).

## Użycie AI (regulamin zadania §2.8)

Przy pracy korzystaliśmy z asystenta AI (Claude) do analizy dokumentacji i kodu portalu, propozycji architektury, generowania i refaktoryzacji kodu (moduł Django, komponenty Angular, testy), konfiguracji serwera i szkiców materiałów. Każdą zmianę przejrzał, uruchomił i zatwierdził autor. Sygnet logo to uproszczony kontur Polski z danych Natural Earth (domena publiczna) z pulsem zaprojektowanym przez autora; napis złożono krojem Manrope (SIL OFL).

## Ograniczenia

- Publikacja w produkcyjnym dane.gov.pl wymaga wdrożenia modułu przez operatora portalu; demonstracja działa na forku na naszym serwerze.
- Reguła „punkt poza gminą” działa dla gmin z danych startowych (granice w `data/gminy.geojson`); pełny zestaw granic to PRG z GUGiK. Kod TERYT gminy dostawcy jest w demonstracji przypisany do znanych dostawców.
- Logowanie przez login.gov.pl istnieje w portalu, w demonstracji używamy kont e-mail i hasło.
- Część godzin dostępności zapisanych opisowo (np. „w godzinach otwarcia stacji metra”) nie daje się zamienić na format opening_hours; takie AED mają status „dostępność nieznana”.

## Licencja

Moduł AED i nasze zmiany: MIT, zob. [LICENSE](LICENSE). Kod portalu dane.gov.pl pozostaje na licencji jego autorów (https://dane.gov.pl/source-code/).
