from dataclasses import dataclass

from mcod.aed.importing.columns import ColumnMatcher
from mcod.aed.importing.mapper import RecordMapper
from mcod.aed.sources import teryt_for
from mcod.aed.validation import RecordChecker


@dataclass(frozen=True)
class ImportSource:
    """Skąd pochodzą rekordy: wartości domyślne dla pól, których plik nie ma, i prefiks identyfikatorów."""

    operator: str
    source_label: str
    updated: str
    teryt: str = ""
    id_prefix: str = "aed"

    @classmethod
    def for_organization(cls, organization, source_label, updated):
        teryt = teryt_for(organization.title)
        prefix = "aed-%s" % (teryt or (organization.regon or "").strip() or organization.pk)
        return cls(organization.title, source_label, updated, teryt, prefix)

    def defaults(self):
        values = {"dysponent_nazwa": self.operator, "zrodlo_danych": self.source_label, "data_aktualizacji": self.updated}
        if self.teryt:
            values["kod_teryt_gminy"] = self.teryt
        return values


class ImportPipeline:
    """Dopasowanie kolumn → rekordy wzorcowego zakresu → (opcjonalnie) geokodowanie → walidacja.

    Używany przez kreator w panelu i przy odbudowie rejestru (zbiory z tagiem AED).
    """

    def __init__(self, source, geocoder=None):
        self.source = source
        self.geocoder = geocoder

    def suggest_mapping(self, header, rows):
        return ColumnMatcher().suggest(header, rows)

    def run(self, header, rows, mapping=None):
        if mapping is None:
            mapping = self.suggest_mapping(header, rows)
        mapped = RecordMapper(self.source.defaults(), self.source.id_prefix).map(header, rows, mapping)
        if self.geocoder is not None:
            self.geocoder.fill_missing(mapped)
        return self.check([record for record, _ in mapped], [notes for _, notes in mapped])

    @staticmethod
    def check(records, notes=None):
        return RecordChecker().check_all(records, notes)
