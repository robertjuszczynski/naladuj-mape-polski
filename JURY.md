# Jak sprawdzić „Naładuj mapę Polski.” (ok. 10 minut)

Rozwiązanie działa wewnątrz portalu dane.gov.pl (fork otwartego kodu portalu na naszym serwerze), nie jako osobny serwis.

Portal: https://178-250-46-63.sslip.io
Panel dostawcy: https://admin.178-250-46-63.sslip.io (konto: aed@marki.example, hasło w zgłoszeniu)

Najlepiej sprawdzać na tych adresach – tylko tam wszystko działa naprawdę. Gdy domena jest niedostępna, otwórz klikalny prototyp `deliverables/prototyp/index.html` (bez internetu). To wersja uproszczona: zrzuty z 22.11.2026, przygotowane ścieżki, bez zapisywania danych.

Bez dostępu do serwera: klikalny prototyp `deliverables/prototyp/index.html` (otwiera się w przeglądarce bez internetu, 18 ekranów z działającego portalu, te same ścieżki co niżej).

Ścieżka urzędnika:
1. Zaloguj się do panelu jako Urząd Miasta Marki i wybierz „Defibrylatory AED” → „Dodaj dane o AED”.
2. Przeciągnij plik backend/mcod/aed/data/testowe/04-marki-oryginal-z-dane-gov-pl.csv (prawdziwy plik Marek z dane.gov.pl, z błędami). Plik z mieszanką dobrych i złych rekordów: 06-mieszany-dobre-i-zle.csv.
3. Kolumny: kreator sam rozpoznał nazwę, adres i współrzędne. Kliknij „Sprawdź dane”.
4. Sprawdzenie: 7 wierszy ma poprawione zamienione współrzędne, punkt w Krośnie jest wstrzymany, a dwa AED w tym samym miejscu czekają na decyzję – kliknij „Zatwierdź” przy obu, żeby trafiły do publikacji. Plik przechodzi reguły jakości portalu; poprawiony plik można pobrać przyciskiem „Pobierz poprawiony plik (CSV)”.
5. Wybierz licencję, zaznacz oświadczenie i opublikuj. Dane trafiają do zbioru Marek i do wykazu zbiorczego.

Ścieżka instytucji, która ma już własny zbiór (bez kreatora):
6. W panelu otwórz dowolny zasób z listą AED (Dane → Zasoby), w polu „Wykaz zbiorczy” wybierz „Wykaz defibrylatorów AED” i zapisz. Kolumny mogą mieć dowolne nazwy.
7. Po chwili zasób jest w wykazie. Raport źródeł: „Defibrylatory AED” → „Wykaz zbiorczy AED” (co odczytano, ile rekordów, co odpadło i dlaczego).

Ścieżka Ministerstwa – jak najwięcej AED w jednym miejscu (konto administratora):
- „Defibrylatory AED” → „Pozyskiwanie danych”: trzy koszyki (potwierdzone, ze źródeł publicznych, czekające na zgodę) i kolejka próśb o zgodę od największych dysponentów. Wpisz e-mail, kliknij „Wyślij zaproszenie” albo po rozmowie „Zgoda – opublikuj”.
- „Źródła zewnętrzne”: Kraków (PDF w BIP, publikowany z podaniem źródła) i OpenStreetMap (tylko wewnętrznie, licencja ODbL).

Ścieżka obywatela:
8. Strona główna portalu: pasek akcji na samej górze.
9. „Mapa AED” w menu: liczba AED, instytucji i AED dostępnych teraz. Wybierz dzień i godzinę suwakiem, kliknij dowolny AED, zgłoś problem.
10. Strona AED → „Wykaz AED w tabeli” (`/pl/aed/wykaz`): wykaz zbiorczy pokazany tak samo jak wykaz chronionych danych DGA, tymi samymi komponentami portalu, z kolumnami wzorcowego zakresu AED. Ten sam zbiór jest w Dane → kategoria „Zdrowie”: zasób CSV (widok tabeli, API) i zasób GeoJSON do map, obok osobnych zbiorów 5 instytucji. GeoJSON jest też w API: `https://api.178-250-46-63.sslip.io/aed?format=geojson`.
- Panel → „Wykaz zbiorczy AED”: raport źródeł i „Sprzeczne dane między źródłami” (np. AED z Warszawy z „całodobowo: nie” przy godzinach „całodobowo”). Kreator pokazuje takie sprzeczności jako ostrzeżenia przy rekordzie.

Pliki do oceny:
11. Wzorcowy zakres danych: deliverables/wzorcowy-zakres-danych-aed.xlsx (30 pól, minimum dla instytucji oznaczone na czerwono).
12. Logo i księga znaku: deliverables/znak/.
13. Raport dostępności WCAG: deliverables/wcag/RAPORT.md.

Więcej plików testowych z opisem oczekiwanych wyników: backend/mcod/aed/data/testowe/README.md.
Kod modułu: backend/mcod/aed/ (backend) i frontend/src/app/pages/aed/ (frontend).
