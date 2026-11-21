"""Wzorcowy zakres danych o defibrylatorach AED: jedna definicja pól dla walidacji, importu i eksportu."""

from dataclasses import dataclass
from typing import Optional, Tuple

PROFILE_VERSION = "0.2.0"

ADDRESS_FEATURES = (
    "ul.",
    "al.",
    "pl.",
    "skwer",
    "bulw.",
    "rondo",
    "park",
    "rynek",
    "szosa",
    "droga",
    "os.",
    "ogród",
    "wyspa",
    "wyb.",
    "inne",
)


class Requirement:
    REQUIRED = "obowiazkowe"
    RECOMMENDED = "zalecane"
    OPTIONAL = "opcjonalne"


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    type: str
    requirement: str
    description: str
    example: str
    values: Tuple[str, ...] = ()
    min: Optional[float] = None
    max: Optional[float] = None
    osm: str = ""
    geodae: str = ""

    @property
    def required(self):
        return self.requirement == Requirement.REQUIRED


R, REC, OPT = Requirement.REQUIRED, Requirement.RECOMMENDED, Requirement.OPTIONAL

FIELDS = (
    Field(
        "id_aed",
        "Identyfikator AED",
        "text",
        R,
        "Stały identyfikator urządzenia nadany przez dysponenta. Nie zmienia się przy aktualizacji danych.",
        "aed-1434021-0001",
        geodae="gid",
    ),
    Field(
        "nazwa_obiektu",
        "Nazwa obiektu",
        "text",
        R,
        "Nazwa budynku lub miejsca, w którym znajduje się AED.",
        "Urząd Miasta Marki",
        geodae="nom",
    ),
    Field(
        "opis_lokalizacji",
        "Opis lokalizacji",
        "text",
        REC,
        "Gdzie dokładnie w obiekcie wisi AED.",
        "Parter, przy wejściu głównym, obok portierni",
        osm="defibrillator:location",
    ),
    Field(
        "pietro",
        "Piętro",
        "integer",
        OPT,
        "Kondygnacja, na której znajduje się AED. 0 to parter, liczby ujemne to podziemie.",
        "0",
        min=-10,
        max=100,
        osm="level",
    ),
    Field(
        "wewnatrz_budynku",
        "Wewnątrz budynku",
        "boolean",
        REC,
        "true, jeśli AED jest wewnątrz budynku; false, jeśli na zewnątrz.",
        "true",
        osm="indoor",
    ),
    Field(
        "cecha_adresu",
        "Cecha adresu",
        "address_feature",
        REC,
        "Rodzaj ulicy według TERYT w osobnej kolumnie (reguła „Cecha adresu” weryfikacji jakości portalu).",
        "al.",
        values=ADDRESS_FEATURES,
    ),
    Field(
        "ulica",
        "Ulica",
        "text",
        REC,
        "Nazwa ulicy lub placu bez cechy. Puste, jeśli miejscowość nie ma ulic.",
        "Józefa Piłsudskiego",
        osm="addr:street",
    ),
    Field("numer_budynku", "Numer budynku", "text", REC, "Numer porządkowy budynku.", "95", osm="addr:housenumber"),
    Field("numer_lokalu", "Numer lokalu", "text", OPT, "Numer lokalu, jeśli AED jest w lokalu wewnątrz budynku.", ""),
    Field("kod_pocztowy", "Kod pocztowy", "postcode", REC, "Kod pocztowy w formacie 00-000.", "05-270", osm="addr:postcode"),
    Field("miejscowosc", "Miejscowość", "text", REC, "Nazwa miejscowości.", "Marki", osm="addr:city"),
    Field(
        "kod_teryt_gminy",
        "Kod TERYT gminy",
        "teryt",
        R,
        "7-cyfrowy kod gminy z rejestru TERC (GUS), zapisany jako tekst.",
        "1434021",
    ),
    Field("kod_simc", "Kod SIMC miejscowości", "simc", OPT, "7-cyfrowy identyfikator miejscowości z rejestru SIMC (GUS).", ""),
    Field(
        "szerokosc_geograficzna",
        "Szerokość geograficzna",
        "decimal",
        R,
        "Szerokość geograficzna WGS84, kropka jako separator. Dla Polski od 49 do 55.",
        "52.326697",
        min=49,
        max=55,
    ),
    Field(
        "dlugosc_geograficzna",
        "Długość geograficzna",
        "decimal",
        R,
        "Długość geograficzna WGS84, kropka jako separator. Dla Polski od 14 do 24,2.",
        "21.107557",
        min=14,
        max=24.2,
    ),
    Field(
        "dostep",
        "Dostęp",
        "enum",
        REC,
        "publiczny, ograniczony (np. w godzinach pracy) albo prywatny.",
        "publiczny",
        values=("publiczny", "ograniczony", "prywatny"),
        osm="access",
    ),
    Field(
        "dostepny_calodobowo",
        "Dostępny całodobowo",
        "boolean",
        R,
        "true, jeśli AED jest dostępny 24 godziny na dobę, 7 dni w tygodniu.",
        "false",
    ),
    Field(
        "godziny_dostepnosci",
        "Godziny dostępności",
        "opening_hours",
        REC,
        "Format opening_hours, np. Mo-Fr 08:00-16:00. Wymagane, gdy dostepny_calodobowo = false.",
        "Mo-Fr 08:00-16:00",
        osm="opening_hours",
    ),
    Field(
        "sprawny", "Sprawny", "boolean", REC, "true, jeśli według dysponenta urządzenie działa i jest gotowe do użycia.", "true"
    ),
    Field(
        "data_ostatniego_przegladu",
        "Data ostatniego przeglądu",
        "date",
        REC,
        "Data ostatniego przeglądu w formacie RRRR-MM-DD.",
        "2026-05-14",
        osm="check_date",
    ),
    Field(
        "data_waznosci_elektrod",
        "Data ważności elektrod",
        "date",
        OPT,
        "Termin ważności elektrod w formacie RRRR-MM-DD.",
        "2028-03-01",
    ),
    Field(
        "data_waznosci_baterii",
        "Data ważności baterii",
        "date",
        OPT,
        "Termin ważności baterii w formacie RRRR-MM-DD.",
        "2029-01-01",
    ),
    Field("producent", "Producent", "text", OPT, "Producent urządzenia.", "Philips", osm="manufacturer"),
    Field("model", "Model", "text", OPT, "Model urządzenia.", "HeartStart FRx", osm="model"),
    Field(
        "mobilny", "Urządzenie mobilne", "boolean", OPT, "true, jeśli AED jest w pojeździe i nie ma stałej lokalizacji.", "false"
    ),
    Field(
        "dysponent_nazwa",
        "Dysponent",
        "text",
        R,
        "Nazwa instytucji lub firmy odpowiedzialnej za urządzenie.",
        "Urząd Miasta Marki",
        osm="operator",
    ),
    Field(
        "dysponent_telefon",
        "Telefon dysponenta",
        "phone",
        REC,
        "Telefon instytucji (nie osoby prywatnej) jako 9 cyfr.",
        "221234567",
        osm="phone",
    ),
    Field(
        "zrodlo_danych",
        "Źródło danych",
        "text",
        R,
        "Skąd pochodzi rekord: nazwa zbioru lub adres zasobu.",
        "https://dane.gov.pl/pl/dataset/4955",
    ),
    Field(
        "data_aktualizacji",
        "Data aktualizacji",
        "date",
        R,
        "Data ostatniej weryfikacji rekordu przez dysponenta (RRRR-MM-DD).",
        "2026-11-21",
    ),
    Field("uwagi", "Uwagi", "text", OPT, "Dodatkowe informacje, np. „klucz w recepcji”.", ""),
)

FIELD_NAMES = [f.name for f in FIELDS]
FIELDS_BY_NAME = {f.name: f for f in FIELDS}


def format_address(record, with_feature=True):
    street_parts = (record.get("cecha_adresu") if with_feature else None, record.get("ulica"), record.get("numer_budynku"))
    street = " ".join(x for x in street_parts if x)
    city = " ".join(x for x in (record.get("kod_pocztowy"), record.get("miejscowosc")) if x)
    return ", ".join(x for x in (street, city) if x)
