"""Conflicting data between sources of the register: the same AED (same place) described differently by two providers."""

import math
from collections import defaultdict

SAME_PLACE_M = 30
GRID = 0.001
COMPARED = (
    ("godziny_dostepnosci", "Godziny dostępności"),
    ("dostepny_calodobowo", "Dostępny całodobowo"),
    ("sprawny", "Sprawny"),
    ("dostep", "Dostęp"),
)


def distance_m(lat1, lon1, lat2, lon2):
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def find_conflicts(entries):
    """entries: dicts with source, id, name, lat, lon, data. Returns one item per pair of sources that disagree."""
    cells = defaultdict(list)
    out = []
    for entry in entries:
        if entry.get("lat") is None or entry.get("lon") is None:
            continue
        cell = (int(entry["lat"] / GRID), int(entry["lon"] / GRID))
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for other in cells.get((cell[0] + di, cell[1] + dj), ()):
                    conflict = _compare(other, entry)
                    if conflict:
                        out.append(conflict)
        cells[cell].append(entry)
    return out


def _compare(a, b):
    if a["source"] == b["source"] or distance_m(a["lat"], a["lon"], b["lat"], b["lon"]) > SAME_PLACE_M:
        return None
    fields = []
    for name, label in COMPARED:
        left, right = (a["data"].get(name) or "").strip(), (b["data"].get(name) or "").strip()
        if left and right and left != right:
            fields.append({"field": label, "a": left, "b": right})
    if not fields:
        return None
    side = lambda e: {"source": e["source"], "id": e["id"], "name": e["name"]}  # noqa: E731
    return {"a": side(a), "b": side(b), "fields": fields}


def within_record(source, id_aed, name, messages):
    """Fields of one record that contradict each other (from the record validator)."""
    return {
        "a": {"source": source, "id": id_aed, "name": name},
        "b": None,
        "fields": [{"field": "W jednym rekordzie", "a": message, "b": ""} for message in messages],
    }


def duplicate_id(id_aed, first_source, second_source):
    """The same identifier in two resources: only the first one goes to the register."""
    return {
        "a": {"source": first_source, "id": id_aed, "name": ""},
        "b": {"source": second_source, "id": id_aed, "name": ""},
        "fields": [{"field": "Identyfikator AED", "a": id_aed, "b": id_aed}],
    }
