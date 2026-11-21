# Raport dostępności (WCAG) – 21.11.2026

Narzędzie: Lighthouse 12.2.1, kategoria „Accessibility” (reguły axe-core), emulacja telefonu (412 px szerokości).

| Strona | Wynik | Uwagi |
|---|---|---|
| Strona akcji `/pl/aed` | 93/100 | 2 uwagi z komponentów portalu (niżej) |
| Strona AED `/pl/aed/warszawa-622` | 94/100 | jw. |
| Strona główna `/pl` | 93/100 | jw. |

Uwagi i co z nimi zrobiliśmy:

1. `aria-dialog-name` – okno „Polityka prywatności i RODO” (komponent portalu) nie miało nazwy dostępnej dla czytników ekranu. Poprawione: okno wskazuje swój nagłówek przez `aria-labelledby`.
2. `aria-progressbar-name` – pasek postępu ładowania (biblioteka ngx-progressbar używana przez portal) nie ma nazwy. Bez zmian, bo to część oryginalnego portalu, nie modułu AED.

Moduł AED nie ma własnych błędów w tym teście. Zastosowane zasady: kontrast tekstu co najmniej 4,5 : 1 (granat #0B2545 na bieli, krem na granacie), czerwień tylko w grafice i na przyciskach z białym pogrubionym tekstem, pola formularzy z etykietami, grupy filtrów w `fieldset` z `legend`, suwak godziny z etykietą i wynikiem ogłaszanym przez `aria-live`, cele dotykowe min. 44 px, animacja logo wyłączana przy ustawieniu „ogranicz ruch”, układ jednokolumnowy poniżej 860 px.

Ograniczenia: test automatyczny wykrywa tylko część problemów WCAG. Kreator w panelu dostawcy (Django admin) nie był testowany Lighthouse’em, bo wymaga zalogowania; korzysta z szablonów panelu portalu.
