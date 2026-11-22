# Teksty do formularza HackTribe

## Problem

Ktoś upada na ulicy, w szkole albo w urzędzie. Nie oddycha. Największą szansę ma wtedy, gdy defibrylacja nastąpi w ciągu 3–5 minut: przeżywa wtedy nawet 50–70% osób (wytyczne Europejskiej Rady Resuscytacji). Każda minuta zwłoki te szanse zmniejsza. W Polsce nagłe zatrzymanie krążenia zabija według szacunków prawie 90 osób dziennie. Defibrylatora AED może użyć każdy, ale trzeba wiedzieć, gdzie jest, czy jest dostępny o tej porze i czy działa.

Defibrylatorów AED jest w Polsce wiele, ale państwo nie wie, gdzie są. Nie ma obowiązku ich rejestracji ani jednego otwartego spisu. Dyspozytorzy 112 korzystają z mapy tworzonej przez wolontariuszy (odpowiedź na interpelację poselską z 15.04.2026). Wyszukiwanie „defibrylator” w dane.gov.pl zwraca 4 zbiory, a w całym portalu jest ich 5 na cały kraj (zbioru Legionowa wyszukiwarka nie znajduje). Dane o AED ma w otwartych danych 5 z 2477 gmin, czyli 0,2%.

Te dane, które są, trudno połączyć. Każdy zbiór ma inny układ kolumn. Oficjalny plik Marek ma kolumny podpisane odwrotnie niż dane, więc defibrylator z urzędu miasta ląduje 4 382 km dalej, na pustyni w Arabii Saudyjskiej, a jeden punkt leży w Krośnie. Kraków publikuje wykaz AED jako PDF w BIP, którego program nie odczyta. Największe bazy, np. „Pierwszy Ratownik” z ponad 8 500 AED, są zamknięte. Największa otwarta baza, OpenStreetMap, ma licencję ODbL, której nie ma na liście licencji portalu, więc nie można jej po prostu przenieść do dane.gov.pl. Do tego nikt nie gwarantuje, że AED z mapy wolontariuszy wciąż wisi tam, gdzie go zaznaczono.

Dane rzadko mówią też, czy AED jest dostępny o danej godzinie i czy jest sprawny. W zebranych przez nas danych 340 z 844 urządzeń nie ma żadnej informacji o godzinach. Daty przeglądów, elektrod i baterii zwykle nie są nigdzie zapisane, a po publikacji nikt nie pilnuje, żeby dane były aktualne.

Map AED jest wiele. Brakuje danych, z których mogłyby powstać. Urzędnik ma Excela, nie zna formatów portalu i nie chce opublikować błędu pod nazwą swojej instytucji. Szkoła czy firma z jednym defibrylatorem nie będzie robić pliku. A Ministerstwo nie ma narzędzia, żeby z rozproszonych list zrobić jeden wiarygodny zbiór.

## Solution

„Naładuj mapę Polski.” to rozwiązanie wbudowane w portal dane.gov.pl, a nie kolejna osobna mapa. Każda instytucja publikuje w nim swoje defibrylatory w kilka minut, a portal sam składa z nich ogólnopolski, otwarty i wiarygodny zbiór. Działa na kontach dostawców danych, zwykłych zbiorach portalu, jego regułach jakości, licencjach i mechanizmie uwag do zbioru, więc Ministerstwo nie musi utrzymywać nowego systemu.

**Kreator „Wgraj plik z AED”.** Gmina, szkoła, szpital czy firma loguje się tym samym kontem dostawcy danych co zawsze i wgrywa plik CSV lub XLSX w takim układzie, jaki ma. Kreator sam rozpoznaje kolumny i automatycznie poprawia typowe błędy: zamienione współrzędne, adres w jednej kolumnie, przecinek dziesiętny, godziny zapisane tekstem (zamienia je na format opening_hours). Brakujące współrzędne uzupełnia z adresu przez GUGiK. Wykrywa dane osobowe, punkty poza gminą i poza Polską oraz duplikaty. Przy każdym AED pokazuje, co i w którym polu poprawił. Rekordy, których nie da się poprawić, wstrzymuje albo zostawia do decyzji urzędnika, a cały plik sprawdza tymi samymi regułami jakości co portal. W prawdziwym pliku Marek kreator poprawił 15 pól w 8 rekordach i przeniósł defibrylator z Arabii z powrotem do Marek. Po wyborze licencji (CC0 albo CC BY 4.0 z listy portalu) i oświadczeniu dane stają się zwykłym zbiorem instytucji. Gmina może też opublikować AED szkół czy firm ze swojego terenu, składając osobne oświadczenie o zgodzie lub podstawie prawnej.

**„Dodaj jeden AED”.** Kto nie ma pliku, dodaje pojedynczy defibrylator w prostym formularzu, bez szablonu: adres z podpowiedziami GUGiK, punkt na mapie albo własna lokalizacja, godziny ustawiane przyciskami, opcjonalnie daty przeglądu, elektrod i baterii.

**Wykaz zbiorczy.** Portal co noc i chwilę po każdej zmianie zestawia zbiory wszystkich instytucji w jeden ogólnopolski wykaz według wzorcowego zakresu danych (30 pól, a od instytucji wystarczą 4 informacje: nazwa, adres, współrzędne albo sam adres i dostępność). Instytucja, która ma już własną listę, także jako link do BIP, dołącza ją jednym polem w zasobie, w kreatorze albo przez harvester (CKAN, XML). Mechanizm działa jak wykaz chronionych danych DGA, który portal już ma. Operator widzi raport źródeł: co odczytano, ile rekordów, co odpadło i dlaczego.

**Jak najwięcej AED bez łamania licencji.** Portal sam pobiera listy spoza portalu. Te, które wolno publikować (CC0, CC BY, informacja publiczna z BIP, także tabele w PDF, jak wykaz Krakowa), trafiają do wykazu jako niepotwierdzone, zawsze z podaniem autora. Te, których licencja na to nie pozwala, np. OpenStreetMap na ODbL, zostają wyłącznie wewnętrznie i są pogrupowane w prośby o zgodę: po jednej na dysponenta (np. ZUS, InPost) albo na gminę jako pośrednika. Operator wysyła zaproszenie, notuje rozmowy i po zgodzie publikuje AED jako potwierdzone. Dziś w demo: 778 AED potwierdzonych przez dysponentów i 66 z publicznej listy Krakowa w wykazie oraz 17 971 AED z OpenStreetMap w 5 650 prośbach o zgodę.

**AED do potwierdzenia.** Danym spoza portalu nie ufamy. Każdy punkt z każdego źródła trafia do gminy, na której terenie leży, w „AED do potwierdzenia”. Gmina widzi źródło i licencję punktu i decyduje: „To nasz” (AED trafia do jej zbioru jako potwierdzony), „Nie nasz” (wskazuje dysponenta, informacja trafia do Ministerstwa) albo „Nie ma go”. Decyzje przetrwają nocne pobieranie źródeł. Gdy ten sam AED opublikuje dysponent, wersja niepotwierdzona znika z wykazu. Na mapie i w API każdy AED ma oznaczenie, czy jest potwierdzony (pole verified), więc system 112 sam decyduje, czy korzysta też z niepotwierdzonych.

**„Do sprawdzenia” i przypomnienia.** Portal pilnuje, żeby dane nie starzały się po publikacji. Sam wyłapuje zbliżające się przeglądy, kończące się elektrody i baterie, brak godzin albo lokalizacji i zgłoszenia mieszkańców. Instytucja poprawia je jednym kliknięciem, a przypomnienie e-mailem dostaje 30 dni przed terminem. Poprawki trafiają do osobnego zasobu instytucji, więc nie nadpisują jej oryginalnego pliku.

**Mapa i najbliższy otwarty AED.** Na stronie akcji każdy widzi mapę z informacją, czy AED jest dostępny teraz albo w wybranym dniu i godzinie. Świadek, a po podłączeniu API także dyspozytor 112, wpisuje adres zdarzenia lub używa lokalizacji i dostaje najbliższe AED otwarte w tym momencie (w promieniu 5 km), z czasem dojścia pieszo i gotowym opisem miejsca do przeczytania dzwoniącemu. Gdy najbliższy dostępny AED jest dalej niż 5 minut pieszo, mapa radzi wysłać po niego drugą osobę, a dzwoniącemu nie przerywać uciskania.

**Zgłoszenia.** Niedziałający, zamknięty albo nieistniejący AED każdy może zgłosić jednym kliknięciem. Zgłoszenie trafia do instytucji przez istniejący mechanizm uwag do zbioru i do jej listy „Do sprawdzenia”, a AED dostaje oznaczenie na mapie.

**Otwarte dane.** Wykaz zbiorczy ma widok tabeli, plik CSV, plik GeoJSON, JSON-LD i API, w tym dostępność liczoną na wskazaną godzinę, wyszukiwanie najbliższego AED i statystyki. Wszystkie dane są w formatach odczytywalnych maszynowo, na licencjach z listy portalu.

**Akcja „Naładuj mapę Polski.”.** Żeby instytucje chciały dodać dane, jest akcja z hasłem „Udostępnij dane o swoim AED w dane.gov.pl.”: pasek w całym portalu z liczbą AED, licznik „Ile mapy już naładowaliśmy?” dla województw, posty dla gmin, instytucji publicznych i firm, baner, plakat, naklejka z kodem QR na szafkę AED, odznaka dla dostawcy, logo i księga znaku.

**Dostępność i jakość.** Strona akcji ma wynik 93–94/100 w teście dostępności Lighthouse, działa z trybami wysokiego kontrastu i powiększaniem tekstu portalu, jest responsywna i ma wersję polską i angielską.

**Korzyści.** Instytucja publikuje dane w kilka minut, bez znajomości formatów i bez ryzyka, że błąd pójdzie pod jej nazwą, a o terminach przypomni jej portal. Ministerstwo dostaje jak najwięcej AED w jednym miejscu, spójnych i sprawdzonych, bez łamania licencji i w portalu, który już ma. Dyspozytor 112 i każdy z nas wiedzą, gdzie jest najbliższy defibrylator, czy można z niego teraz skorzystać i czy dane potwierdził dysponent.

## Website

https://178-250-46-63.sslip.io/pl/aed

## Instrukcje jak otworzyć projekt i jak przez niego przejść

Projekt można otworzyć na trzy sposoby i żaden nie wymaga instalacji. Działający portal z mapą AED otwiera się bez logowania pod adresem https://178-250-46-63.sslip.io/pl/aed. Panel, w którym instytucja dodaje swoje defibrylatory, jest pod adresem https://admin.178-250-46-63.sslip.io, a logujemy się na konto aed@marki.example z hasłem [hasło w zgłoszeniu]. Klikalny prototyp działa też bez internetu: w repozytorium wystarczy otworzyć w przeglądarce plik deliverables/prototyp/index.html i klikać przyciski jak w prawdziwym portalu, a strzałki ← → przełączają ekrany. Instrukcja krok po kroku dla jury jest w pliku JURY.md w repozytorium.

Uwaga: zalecamy sprawdzanie na domenie (dwa pierwsze adresy). Tylko tam wszystko działa naprawdę: wyszukiwanie dowolnego adresu, najbliższy AED o wybranej porze, wgrywanie własnego pliku i zapisywanie zmian. Klikalny prototyp to wersja zapasowa na wypadek, gdy domena się nie otworzy. Jest uproszczony: pokazuje zrzuty ekranów z 22.11.2026 i przygotowane ścieżki, nie zapisuje danych.

Ścieżka urzędnika (ok. 3 minuty):
1. Pobierz prawdziwy plik Marek z dane.gov.pl: https://api.dane.gov.pl/media/resources/20250710/Defibrylator_GminaMiastoMarki_1.csv (ten sam plik jest w repozytorium: backend/mcod/aed/data/testowe/04-marki-oryginal-z-dane-gov-pl.csv).
2. Zaloguj się do panelu i wybierz „Defibrylatory AED” → „Wgraj plik z AED”. Przeciągnij plik i kliknij „Wczytaj plik”.
3. Kreator sam rozpoznał kolumny. Kliknij „Sprawdź dane”.
4. Na ekranie sprawdzenia widać 15 pól poprawionych automatycznie (m.in. zamienione współrzędne), punkt w Krośnie wstrzymany i dwa AED w tym samym miejscu do decyzji. Kliknij „Zatwierdź” przy obu.
5. Wybierz licencję, zaznacz oświadczenie i kliknij „Opublikuj w dane.gov.pl”. Dane trafiają do zbioru Marek i do ogólnopolskiego wykazu.

Bez pliku:
6. „Defibrylatory AED” → „Dodaj jeden AED”: wpisz adres, wybierz podpowiedź, kliknij miejsce na mapie, ustaw godziny i opublikuj.
7. „Defibrylatory AED” → „Do sprawdzenia”: terminy przeglądów, elektrod i baterii, braki w danych i zgłoszenia mieszkańców.

Dane spoza portalu (konto gminy, np. aed@warszawa.example):
8. „Defibrylatory AED” → „AED do potwierdzenia”: AED ze źródeł zewnętrznych na terenie gminy. Kliknij „To nasz”, „Nie nasz” albo „Nie ma go”.

Instytucja z gotową listą:
9. „Dane” → „Resources”: otwórz zasób z listą AED, w polu „Wykaz zbiorczy” wybierz „Wykaz defibrylatorów AED” i zapisz. Raport źródeł: „Defibrylatory AED” → „Wykaz zbiorczy AED”.

Obywatel i dyspozytor 112:
10. Na stronie akcji kliknij „Użyj mojej lokalizacji” albo wpisz adres (np. Warszawa, pl. Defilad 1). Zobaczysz najbliższy AED otwarty teraz, czas dojścia i opis do przeczytania dzwoniącemu. Możesz wybrać inny dzień i godzinę.
11. Strona AED ze zgłoszeniem problemu, np. https://178-250-46-63.sslip.io/pl/aed/warszawa-1022.
12. Wykaz zbiorczy (tabela, CSV, API): „Dane” → kategoria „Zdrowie” → „Defibrylatory AED w Polsce – wykaz zbiorczy”.

Pełna instrukcja z wymaganiami zadania przy każdym kroku: JURY.md w repozytorium. Opis rozwiązania (PDF), pitch, wideo, wzorcowy zakres danych (XLSX), logo i księga znaku: katalog deliverables.
