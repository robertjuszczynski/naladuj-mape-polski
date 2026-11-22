import datetime

import pytest

pytest.importorskip("django")
if not __import__("django.apps", fromlist=["apps"]).apps.ready:
    pytest.skip("needs the portal's Django setup (conftest)", allow_module_level=True)

from mcod.aed.nearest import AddressLocator, NearestAed, opens_at, walk_minutes  # noqa: E402

MONDAY_EVENING = datetime.datetime(2026, 11, 23, 21, 40)


class Organization:
    title = "Urząd"


class Record:
    organization = Organization()
    dataset_id = 1

    def __init__(self, id_aed, lat, lon, **data):
        self.id_aed, self.nazwa_obiektu, self.miejscowosc = id_aed, id_aed, "Warszawa"
        self.lat, self.lon, self.data = lat, lon, data


class Geocoder:
    def __init__(self, answers):
        self.answers, self.queries = answers, []

    def candidates(self, query):
        self.queries.append(query)
        return self.answers.get(query, [])


def found(street, number, lat="52.22", lon="21.02"):
    return {"lat": lat, "lon": lon, "simc": "", "city": "Warszawa", "street": street, "number": number}


def test_parse_accepts_both_orders_and_postcode():
    assert AddressLocator.parse("Warszawa, Wiejska 4") == ("Warszawa", "Wiejska", "4")
    assert AddressLocator.parse("ul. Wiejska 4/6/8, 00-902 Warszawa") == ("Warszawa", "Wiejska", "4/6/8")
    assert AddressLocator.parse("Marszałkowska") is None


def test_locate_skips_similar_street_and_falls_back_to_street():
    geocoder = Geocoder(
        {
            "Warszawa, Wiejska 4": [found("ulica Nowowiejska", "4")],
            "Warszawa, Wiejska": [found("ulica Wiejska", "", lat="52.2256")],
        }
    )
    point = AddressLocator(geocoder).locate("Wiejska 4, Warszawa")
    assert point == {"lat": 52.2256, "lon": 21.02, "label": "ul. Wiejska, Warszawa", "exact": False}


def test_closed_nearer_than_open_are_listed_separately():
    records = [
        Record("sejm", 52.2247, 21.0276, godziny_dostepnosci="Mo-Fr 07:00-18:00"),
        Record("hotel", 52.2260, 21.0300, dostepny_calodobowo="true"),
        Record("szkola", 52.2250, 21.0280),
        Record("metro", 52.2300, 21.0200, godziny_dostepnosci="24/7"),
        Record("dworzec", 52.2290, 21.0030, dostepny_calodobowo="true"),
        Record("daleko", 52.4000, 21.2000, dostepny_calodobowo="true"),
    ]
    result = NearestAed(records, MONDAY_EVENING).find(52.2247, 21.0276)
    assert [r["id"] for r in result["open"]] == ["hotel", "metro", "dworzec"]
    assert [r["id"] for r in result["closed"]] == ["sejm"]
    assert result["closed"][0]["opens_at"] == "2026-11-24T07:00:00"
    assert [r["id"] for r in result["unknown"]] == ["szkola"]
    assert result["open"][0]["phrase"].startswith("%d m, ok. " % result["open"][0]["distance_m"])


def test_walk_minutes_and_opens_at():
    assert walk_minutes(10) == 1 and walk_minutes(800) == 13
    assert opens_at("", MONDAY_EVENING) is None
