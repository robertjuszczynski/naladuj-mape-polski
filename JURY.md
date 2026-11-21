# Jak sprawdzić „Naładuj mapę Polski.” (ok. 10 minut)

Rozwiązanie działa wewnątrz portalu dane.gov.pl (fork otwartego kodu portalu na naszym serwerze), nie jako osobny serwis.

Portal: https://178-250-46-63.sslip.io
Panel dostawcy: https://admin.178-250-46-63.sslip.io (konto: aed@marki.example, hasło w zgłoszeniu)

Ścieżka urzędnika:
1. Zaloguj się do panelu jako Urząd Miasta Marki i wybierz „Defibrylatory AED” → „Dodaj dane o AED”.
2. Przeciągnij plik backend/mcod/aed/data/testowe/04-marki-oryginal-z-dane-gov-pl.csv (prawdziwy plik Marek z dane.gov.pl, z błędami). Plik z mieszanką dobrych i złych rekordów: 06-mieszany-dobre-i-zle.csv.
3. Kolumny: kreator sam rozpoznał nazwę, adres i współrzędne. Kliknij „Sprawdź dane”.
4. Sprawdzenie: 7 wierszy ma poprawione zamienione współrzędne, punkt w Krośnie jest wstrzymany, a dwa AED w tym samym miejscu czekają na decyzję – kliknij „Zatwierdź” przy obu, żeby trafiły do publikacji. Plik przechodzi reguły jakości portalu; poprawiony plik można pobrać przyciskiem „Pobierz poprawiony plik (CSV)”.
5. Wybierz licencję, zaznacz oświadczenie i opublikuj. Dane trafiają do zbioru Marek i do zbioru ogólnopolskiego.

Ścieżka obywatela:
6. Strona główna portalu: pasek akcji na samej górze.
7. „Mapa AED” w menu: liczba AED, instytucji i AED dostępnych teraz. Wybierz dzień i godzinę suwakiem, kliknij dowolny AED, zgłoś problem.
8. Dane → kategoria „Zdrowie”: zbiór ogólnopolski (widok tabeli, CSV, API) i osobne zbiory 5 instytucji.

Pliki do oceny:
9. Wzorcowy zakres danych: deliverables/wzorcowy-zakres-danych-aed.xlsx (30 pól, minimum dla instytucji oznaczone na czerwono).
10. Logo i księga znaku: deliverables/znak/.
11. Raport dostępności WCAG: deliverables/wcag/RAPORT.md.

Więcej plików testowych z opisem oczekiwanych wyników: backend/mcod/aed/data/testowe/README.md.
Kod modułu: backend/mcod/aed/ (backend) i frontend/src/app/pages/aed/ (frontend).
