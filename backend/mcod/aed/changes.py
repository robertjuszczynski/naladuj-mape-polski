"""Automatic changes made on import: which field changed and how, so the wizard can count and show them per field."""

from collections import Counter

from mcod.aed.opening_hours import OpeningHours
from mcod.aed.profile import FIELDS_BY_NAME

COORDINATES = "wspolrzedne"
ADDRESS = "adres"
HOURS = "godziny_dostepnosci"
GROUP_OF = {"szerokosc_geograficzna": COORDINATES, "dlugosc_geograficzna": COORDINATES}
GROUP_LABELS = {COORDINATES: "Współrzędne", ADDRESS: "Adres"}


def change(field, message, before="", after=""):
    return {"field": GROUP_OF.get(field, field), "message": message, "before": before, "after": after}


def as_change(note):
    """Uploads checked before this format stored plain sentences."""
    return note if isinstance(note, dict) else change("", note)


def field_label(field):
    if field in GROUP_LABELS:
        return GROUP_LABELS[field]
    return FIELDS_BY_NAME[field].label if field in FIELDS_BY_NAME else "Inne"


def readable(field, value):
    return OpeningHours.to_polish(value) if field == HOURS else value


def row_changes(row):
    """Automatic changes of one checked row: import notes plus coordinate fixes that were applied."""
    out = [as_change(note) for note in row.get("notes", [])]
    out += [change(COORDINATES, f["message"], f["before"], f["after"]) for f in row["fixes"] if f["auto"]]
    return [dict(c, label=field_label(c["field"]), show_values=c["field"] == COORDINATES and bool(c["after"])) for c in out]


def summarize(rows):
    """{"fields": changes, "records": rows with any change, "by_field": [(label, count)] most frequent first}."""
    per_row = [row_changes(row) for row in rows]
    counts = Counter(c["label"] for changes in per_row for c in changes)
    return {
        "fields": sum(counts.values()),
        "records": sum(1 for changes in per_row if changes),
        "by_field": counts.most_common(),
    }
