import re

DEFAULT_FEATURE = "ul."
FEATURE_ALIASES = {
    "ul.": "ul.",
    "ul": "ul.",
    "ulica": "ul.",
    "al.": "al.",
    "al..": "al.",
    "al": "al.",
    "aleja": "al.",
    "aleje": "al.",
    "pl.": "pl.",
    "pl": "pl.",
    "plac": "pl.",
    "os.": "os.",
    "os": "os.",
    "osiedle": "os.",
    "bulw.": "bulw.",
    "bulwar": "bulw.",
    "wyb.": "wyb.",
    "wybrzeże": "wyb.",
    "skwer": "skwer",
    "rondo": "rondo",
    "park": "park",
    "rynek": "rynek",
    "szosa": "szosa",
    "droga": "droga",
    "ogród": "ogród",
    "wyspa": "wyspa",
}
# Słowa, które są częścią nazwy („Rynek Główny”, „Plac Wolności”), a jednocześnie wyznaczają cechę adresu.
FEATURES_KEPT_IN_NAME = {"rynek": "rynek", "rondo": "rondo", "park": "park", "skwer": "skwer", "plac": "pl.", "osiedle": "os."}

_POSTCODE_AND_CITY = re.compile(r"(\d{2}-\d{3})\s*(.*)$")
_STREET_AND_NUMBER = re.compile(r"^(.*?)\s+(\d+[A-Za-z]?(?:[-–]\d+[A-Za-z]?)?)(?:\s*/\s*(\d+[A-Za-z]?))?$")


class AddressParser:
    @staticmethod
    def split_street(text):
        """Zwraca (cecha, ulica, czy_cecha_przyjeta_domyslnie)."""
        street = re.sub(r"\s+", " ", (text or "").strip())
        if not street:
            return "", "", False
        parts = street.split(" ", 1)
        first = parts[0].lower()
        if first in FEATURES_KEPT_IN_NAME:
            return FEATURES_KEPT_IN_NAME[first], street, False
        if len(parts) == 2 and first in FEATURE_ALIASES:
            return FEATURE_ALIASES[first], parts[1], False
        return DEFAULT_FEATURE, street, True

    @classmethod
    def parse(cls, text):
        """Rozdziela adres z jednej kolumny („al. Piłsudskiego 95, 05-270 Marki”) na pola wzorcowego zakresu."""
        out = {"cecha_adresu": "", "ulica": "", "numer_budynku": "", "numer_lokalu": "", "kod_pocztowy": "", "miejscowosc": ""}
        street = re.sub(r"\s+", " ", (text or "").strip())
        city = _POSTCODE_AND_CITY.search(street)
        if city:
            out["kod_pocztowy"], out["miejscowosc"] = city.group(1), city.group(2).strip()
            street = street[: city.start()].rstrip(", ")
        number = _STREET_AND_NUMBER.match(street)
        if number:
            street = number.group(1)
            out["numer_budynku"], out["numer_lokalu"] = number.group(2), number.group(3) or ""
        if street:
            out["cecha_adresu"], out["ulica"], _ = cls.split_street(street)
        return out
