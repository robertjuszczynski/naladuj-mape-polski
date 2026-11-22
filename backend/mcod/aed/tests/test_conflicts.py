import datetime
import json

from mcod.aed.conflicts import find_conflicts
from mcod.aed.export import AedGeoJson
from mcod.aed.validation import RecordValidator

TODAY = datetime.date(2026, 11, 22)


def codes(record):
    return [i["field"] for i in RecordValidator.contradictions(record, TODAY)]


def test_always_open_against_hours():
    assert codes({"dostepny_calodobowo": "true", "godziny_dostepnosci": "Mo-Fr 08:00-16:00"}) == ["godziny_dostepnosci"]
    assert codes({"dostepny_calodobowo": "false", "godziny_dostepnosci": "24/7"}) == ["dostepny_calodobowo"]
    assert codes({"dostepny_calodobowo": "true", "godziny_dostepnosci": "24/7"}) == []


def test_inspection_in_future_and_floor_outdoors():
    assert codes({"data_ostatniego_przegladu": "2027-01-01"}) == ["data_ostatniego_przegladu"]
    assert codes({"data_ostatniego_przegladu": "2026-05-01"}) == []
    assert codes({"wewnatrz_budynku": "false", "pietro": "2"}) == ["pietro"]


def entry(source, id_aed, lat, hours):
    return {"source": source, "id": id_aed, "name": id_aed, "lat": lat, "lon": 21.0, "data": {"godziny_dostepnosci": hours}}


def test_same_place_from_two_sources_with_different_hours():
    found = find_conflicts([entry("A", "a-1", 52.0, "24/7"), entry("B", "b-1", 52.0001, "Mo-Fr 08:00-16:00")])
    assert len(found) == 1 and found[0]["fields"][0]["field"] == "Godziny dostępności"


def test_no_conflict_when_far_apart_same_source_or_same_data():
    assert find_conflicts([entry("A", "a-1", 52.0, "24/7"), entry("B", "b-1", 52.01, "Mo-Fr 08:00-16:00")]) == []
    assert find_conflicts([entry("A", "a-1", 52.0, "24/7"), entry("A", "a-2", 52.0001, "Mo-Fr 08:00-16:00")]) == []
    assert find_conflicts([entry("A", "a-1", 52.0, "24/7"), entry("B", "b-1", 52.0001, "24/7")]) == []


def test_geojson_points_with_standard_fields():
    records = [
        {"id_aed": "x-1", "nazwa_obiektu": "Urząd", "szerokosc_geograficzna": "52.32", "dlugosc_geograficzna": "21.10"},
        {"id_aed": "x-2", "szerokosc_geograficzna": ""},
    ]
    data = json.loads(AedGeoJson.to_geojson(records))
    assert data["type"] == "FeatureCollection" and len(data["features"]) == 1
    feature = data["features"][0]
    assert feature["geometry"] == {"type": "Point", "coordinates": [21.10, 52.32]}
    assert feature["properties"]["nazwa_obiektu"] == "Urząd" and "szerokosc_geograficzna" not in feature["properties"]
