import re

from mcod.aed.profile import FIELD_NAMES

ADDRESS_TARGET = "_address_in_one_column"

SYNONYMS = (
    ("id_aed", r"^(id(_aed)?|identyfikator|numer id|nr|lp\.?)$"),
    ("szerokosc_geograficzna", r"szeroko|^lat(itude)?$|^y$"),
    ("dlugosc_geograficzna", r"d[łl]ugo|^lon(gitude)?$|^lng$|^x$"),
    (ADDRESS_TARGET, r"^adres$"),
    ("cecha_adresu", r"^cecha"),
    ("ulica", r"ulic|^street$"),
    ("numer_budynku", r"nr.?bud|numer.?bud|^numer$|home.?number"),
    ("numer_lokalu", r"^(nr|numer)[ _.]?lokalu$|^lokal$"),
    ("kod_pocztowy", r"kod.?poczt|postcode|^kod$"),
    ("miejscowosc", r"miejscow|miasto|^city$"),
    ("kod_teryt_gminy", r"teryt|terc"),
    ("kod_simc", r"simc"),
    ("opis_lokalizacji", r"opis.?lokal|gdzie"),
    ("nazwa_obiektu", r"^(?!.*(dysponent|w[łl]a[śs]ciciel)).*nazwa|^obiekt$|^lokalizacja$|^name$|instytucja|plac[óo]wk|jednostk"),
    ("pietro", r"pi[ęe]tro|kondygnac|level"),
    ("wewnatrz_budynku", r"wewn[ąa]trz|zewn[ąa]trz|indoor"),
    ("dostepny_calodobowo", r"ca[łl]odob|24.?/?.?7"),
    ("godziny_dostepnosci", r"godzin|dost[ęe]pno[śs][ćc]|opening"),
    ("dostep", r"^dost[ęe]p$|publiczn|access"),
    ("sprawny", r"sprawn|dzia[łl]a"),
    ("data_ostatniego_przegladu", r"przegl[ąa]d|serwis"),
    ("data_waznosci_elektrod", r"elektrod"),
    ("data_waznosci_baterii", r"bater"),
    ("producent", r"producent|manufacturer"),
    ("model", r"^model"),
    ("dysponent_nazwa", r"dysponent|w[łl]a[śs]ciciel|operator"),
    ("dysponent_telefon", r"telefon|tel\.?$|phone"),
    ("uwagi", r"uwag|komentarz"),
)
ALTERNATIVE_NAME_COLUMN = re.compile(r"lokalizacja|miejsce|obiekt", re.I)


class ColumnMatcher:
    """Suggests which data standard field matches each file column."""

    def suggest(self, header, sample_rows=()):
        used, mapping = set(), {}
        for column in header:
            key = column.strip()
            hit = key if key in FIELD_NAMES else next((t for t, rx in SYNONYMS if t not in used and re.search(rx, key, re.I)), "")
            mapping[column] = hit if hit and hit not in used else ""
            if mapping[column]:
                used.add(mapping[column])
        self._prefer_distinct_names(header, sample_rows, mapping)
        return mapping

    @staticmethod
    def _prefer_distinct_names(header, sample_rows, mapping):
        """A "Nazwa" column with the same value in every row (e.g. "Defibrylator") yields to a column with place names."""
        name_column = next((h for h in header if mapping[h] == "nazwa_obiektu"), None)
        alternative = next((h for h in header if not mapping[h] and ALTERNATIVE_NAME_COLUMN.search(h)), None)
        if not name_column or not alternative or len(sample_rows) <= 1:
            return

        def distinct(column):
            i = header.index(column)
            return len(set(r[i] if i < len(r) else "" for r in sample_rows))

        if distinct(name_column) <= 1 and distinct(alternative) > 1:
            mapping[name_column], mapping[alternative] = "", "nazwa_obiektu"
