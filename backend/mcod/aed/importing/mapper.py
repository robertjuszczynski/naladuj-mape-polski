import re

from mcod.aed.field_types import type_of
from mcod.aed.importing.address import AddressParser
from mcod.aed.importing.columns import ADDRESS_TARGET
from mcod.aed.opening_hours import ALWAYS_OPEN
from mcod.aed.profile import FIELDS_BY_NAME


def normalize_value(name, raw):
    """Returns (value, change note or None) for a data standard field."""
    value = re.sub(r"\s+", " ", (raw or "").strip())
    field = FIELDS_BY_NAME.get(name)
    if not field or value == "":
        return value, None
    return type_of(field).normalize(value, field)


class RecordMapper:
    """Turns file rows into data standard records using the column mapping."""

    def __init__(self, defaults, id_prefix):
        self.defaults = defaults
        self.id_prefix = id_prefix

    def map(self, header, rows, mapping):
        """Returns a list of (record, notes)."""
        return [self._map_row(index, header, row, mapping) for index, row in enumerate(rows)]

    def _map_row(self, index, header, row, mapping):
        record, notes = dict(self.defaults), []
        for i, column in enumerate(header):
            target = mapping.get(column, "")
            raw = row[i].strip() if i < len(row) else ""
            if target and raw:
                self._set(record, notes, target, raw)
        self._complete_street(record, notes)
        self._assign_id(record, index)
        self._complete_availability(record, notes)
        return record, notes

    @staticmethod
    def _set(record, notes, target, raw):
        if target == ADDRESS_TARGET:
            record.update({k: v for k, v in AddressParser.parse(raw).items() if v})
            notes.append("Adres z jednej kolumny rozdzielono na osobne pola")
            return
        record[target], note = normalize_value(target, raw)
        if note:
            notes.append(note)

    @staticmethod
    def _complete_street(record, notes):
        if record.get("ulica") and not record.get("cecha_adresu"):
            record["cecha_adresu"], record["ulica"], assumed = AddressParser.split_street(record["ulica"])
            if assumed:
                notes.append("Brak cechy adresu – przyjęto „ul.”")

    def _assign_id(self, record, index):
        own_id = record.get("id_aed") or str(index + 1)
        record["id_aed"] = own_id if own_id.startswith(self.id_prefix) else "%s-%s" % (self.id_prefix, own_id)

    @staticmethod
    def _complete_availability(record, notes):
        hours = record.get("godziny_dostepnosci")
        if record.get("dostepny_calodobowo") == "true" and not hours:
            record["godziny_dostepnosci"] = ALWAYS_OPEN
        elif not record.get("dostepny_calodobowo") and hours:
            record["dostepny_calodobowo"] = "true" if hours == ALWAYS_OPEN else "false"
            notes.append("Dostępność całodobową ustalono z godzin dostępności")
