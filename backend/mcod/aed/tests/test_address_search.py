from mcod.aed.address_search import AddressSuggestions


def hit(city, street, number, teryt, lat=50.0):
    return {"city": city, "street": street, "number": number, "teryt": teryt, "lat": lat, "lon": 19.9, "area": []}


class FakeGeocoder:
    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def candidates(self, query):
        self.asked.append(query)
        return self.answers.get(query, [])


def test_short_query_asks_nothing():
    geocoder = FakeGeocoder({})
    assert AddressSuggestions(geocoder).search("Kr") == []
    assert geocoder.asked == []


def test_street_first_query_is_reversed():
    geocoder = FakeGeocoder({"Kraków, Floriańska 1": [hit("Kraków", "ul. Floriańska", "1", "1261011")]})
    found = AddressSuggestions(geocoder).search("Floriańska 1, Kraków")
    assert geocoder.asked == ["Floriańska 1, Kraków", "Kraków, Floriańska 1"]
    assert found[0]["label"] == "ul. Floriańska 1, Kraków"
    assert found[0]["exact"] is True


def test_nearest_municipality_first_without_duplicates():
    far = dict(hit("Marki", "ul. Lipowa", "", "1434031"), area=["", "mazowieckie", "", "Marki"])
    near = dict(hit("Marki", "ul. Lipowa", "", "1261011", lat=50.1), area=["", "małopolskie", "", "Kraków"])
    found = AddressSuggestions(FakeGeocoder({"Marki, Lipowa": [far, near, near]})).search("Marki, Lipowa", near="1261011")
    assert [f["lat"] for f in found] == [50.1, 50.0]


def test_typed_street_before_similar_names():
    answers = {
        "Warszawa, Wiejska 4": [
            hit("Warszawa", "ul. Nowowiejska", "4", "1465011"),
            hit("Warszawa", "ul. Wiejska", "4", "1465011"),
        ]
    }
    found = AddressSuggestions(FakeGeocoder(answers)).search("Warszawa, Wiejska 4")
    assert found[0]["label"] == "ul. Wiejska 4, Warszawa"


def test_bare_street_is_looked_up_in_nearby_town_first():
    answers = {
        "Marki, Wiejska": [hit("Marki", "ul. Wiejska", "", "143402", lat=52.3)],
        "Warszawa, Wiejska": [hit("Warszawa", "ul. Wiejska", "", "146501", lat=52.2)],
    }
    geocoder = FakeGeocoder(answers)
    found = AddressSuggestions(geocoder).search("Wiejska", near="143402", cities=["Marki"])
    assert geocoder.asked[0] == "Wiejska"
    assert [f["miejscowosc"] for f in found[:2]] == ["Marki", "Warszawa"]


def test_town_name_is_not_spread_over_cities():
    geocoder = FakeGeocoder({"Marki": [hit("Marki", "", "", "143402")]})
    AddressSuggestions(geocoder).search("Marki", cities=["Warszawa"])
    assert geocoder.asked == ["Marki"]
