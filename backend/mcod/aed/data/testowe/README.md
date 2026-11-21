# Pliki testowe kreatora „Dodaj dane o AED”

Wgrywaj jako Urząd Miasta Marki (`aed@marki.example`). Współrzędne leżą w gminie Marki, więc reguła „punkt poza gminą” działa tak jak w opisie.

| Plik | Co sprawdza | Oczekiwany wynik |
|---|---|---|
| `06-mieszany-dobre-i-zle.csv` | **Najlepszy do pokazu:** 9 AED, część dobrych, część z błędami | 3 × gotowy (w tym zamienione współrzędne poprawione automatycznie); przychodnia bez współrzędnych → uzupełnione z adresu (GUGiK), gotowy; punkt w Krakowie → wstrzymany; brak nazwy → do poprawy; dwa wejścia szkoły w tym samym punkcie → do decyzji (Zatwierdź/Wstrzymaj); stacja paliw z błędną datą „32.13.2026” → do poprawy; w kroku Licencja oświadczenie dla AED innych dysponentów (szkoła) |
| `01-poprawny-szablon-marki.xlsx` | Szablon XLSX wypełniony zgodnie z wzorcowym zakresem | 5 × gotowy, kolumny dopasowane 1:1 |
| `02-wlasny-format-srednik.csv` | Plik „z urzędu”: średniki, polskie nagłówki („Nazwa placówki”, „Gdzie wisi”), adres w jednej kolumnie, przecinek dziesiętny, godziny tekstem („pn-pt 7-18”, „pon.-pt. 10:00-19:00, sob. 9:00-14:00”, „codziennie 9-21”), „tak/nie” | 4 × gotowy; adres rozdzielony, przecinki zamienione na kropki, godziny w formacie opening_hours |
| `03-bledy-do-wylapania.csv` | Typowe błędy | brak współrzędnych → współrzędne ustalone z adresu (geokodowanie GUGiK), gotowy; punkt w Krakowie → wstrzymany (poza gminą); punkt w Berlinie → wstrzymany (poza Polską); zły kod pocztowy i data „15.01.2026” → poprawione automatycznie, gotowy; dwa AED w tym samym punkcie → do decyzji; zamienione współrzędne → poprawione, gotowy |
| `05-gmina-z-innymi-dysponentami.csv` | Gmina publikuje też AED szkoły i firmy (kolumna „Dysponent”), w jednym polu jest adres e-mail | 3 × gotowy; dysponent z pliku zostaje; ostrzeżenie o adresie e-mail; w kroku Licencja dodatkowe oświadczenie o zgodzie lub podstawie prawnej dla 2 AED innych dysponentów |
| `04-marki-oryginal-z-dane-gov-pl.csv` | Prawdziwy plik Marek z dane.gov.pl | wiersze w cudzysłowie rozpakowane, 7 × zamienione współrzędne, punkt w Krośnie wstrzymany, duplikat do decyzji; 7 AED do publikacji |

Na kroku Sprawdzenie przycisk „Pobierz poprawiony plik (CSV)” zwraca dane po poprawkach z kolumnami status, zmiany_automatyczne i do_sprawdzenia.

Każda publikacja zastępuje poprzedni plik zbioru instytucji, więc po teście z plikiem 01 lub 02 wgraj na koniec plik 04, żeby wrócić do danych demonstracyjnych Marek.
