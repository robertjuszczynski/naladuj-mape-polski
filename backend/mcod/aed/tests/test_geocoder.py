import pytest

requests = pytest.importorskip("requests")

from mcod.aed.importing.geocoder import GugikGeocoder  # noqa: E402


class Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class Http:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((params["address"], timeout))
        if self.fail:
            raise requests.ConnectionError("brak sieci")
        return Response({"results": {"1": {"x": "21.1", "y": "52.3", "simc": "0920806"}}})


class Cache(dict):
    def set(self, key, value, ttl):
        self[key] = value


def mapped(*cities):
    return [({"miejscowosc": city, "ulica": "Szkolna", "numer_budynku": "9"}, []) for city in cities]


def test_fill_missing_uses_cache_and_timeout():
    http, cache = Http(), Cache()
    geocoder = GugikGeocoder(http=http, cache=cache)
    rows = mapped("Marki", "Marki")
    geocoder.fill_missing(rows)
    assert http.calls == [("Marki, Szkolna 9", 3)]
    assert rows[1][0]["szerokosc_geograficzna"] == "52.300000" and rows[1][0]["kod_simc"] == "0920806"
    geocoder.fill_missing(mapped("Marki"))
    assert len(http.calls) == 1


def test_failures_are_not_cached():
    http, cache = Http(fail=True), Cache()
    rows = mapped("Marki")
    GugikGeocoder(http=http, cache=cache).fill_missing(rows)
    assert cache == {} and "szerokosc_geograficzna" not in rows[0][0]


def test_limit_and_records_with_coordinates():
    http = Http()
    rows = mapped("A", "B", "C") + [({"miejscowosc": "D", "szerokosc_geograficzna": "52", "dlugosc_geograficzna": "21"}, [])]
    GugikGeocoder(http=http).fill_missing(rows, limit=2)
    assert sorted(a for a, _ in http.calls) == ["A, Szkolna 9", "B, Szkolna 9"]
