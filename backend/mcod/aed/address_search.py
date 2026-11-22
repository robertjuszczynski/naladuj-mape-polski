import re
from concurrent.futures import ThreadPoolExecutor

from mcod.aed.importing.address import AddressParser

SUGGESTIONS = 8
MIN_QUERY = 3
BIG_CITIES = ("Warszawa", "Kraków", "Łódź", "Wrocław", "Poznań", "Gdańsk", "Szczecin", "Lublin")


class AddressSuggestions:
    """Address suggestions while typing (GUGiK), nearest municipality first, without duplicates."""

    def __init__(self, geocoder):
        self.geocoder = geocoder

    def search(self, query, near="", cities=()):
        """cities: where to look for a bare street name ("Wiejska"), nearest first; GUGiK reads one word as a town."""
        query = (query or "").strip()
        if len(query) < MIN_QUERY:
            return []
        words = set(re.findall(r"\w+", query.lower()))
        found = self._candidates(query)
        if not found and "," not in query:
            found = self._in_cities(query, cities)
        found = sorted(
            found,
            key=lambda f: (-self.same_street(f, words), -self.closeness(f.get("teryt", ""), near)),
        )
        results, seen = [], set()
        for item in found:
            result = self.suggestion(item)
            if result["label"] not in seen:
                seen.add(result["label"])
                results.append(result)
        return results[:SUGGESTIONS]

    def _in_cities(self, query, cities):
        towns = list(dict.fromkeys(c for c in tuple(cities) + BIG_CITIES if c))
        with ThreadPoolExecutor(max_workers=len(towns)) as pool:
            return [
                hit for hits in pool.map(lambda town: self.geocoder.candidates("%s, %s" % (town, query)), towns) for hit in hits
            ]

    def _candidates(self, query):
        """GUGiK expects "city, street number"; people also type "street number, city"."""
        parts = [p.strip() for p in query.split(",") if p.strip()]
        queries = [query] + ([", ".join(reversed(parts))] if len(parts) == 2 else [])
        for candidate_query in queries:
            found = self.geocoder.candidates(candidate_query)
            if found:
                return found
        return []

    @staticmethod
    def same_street(found, words):
        """ "Wiejska 4" means Wiejska, not Nowowiejska: the typed words contain the whole street name."""
        _, street, _ = AddressParser.split_street(found.get("street", ""))
        street_words = re.findall(r"\w+", street.lower())
        return bool(street_words) and set(street_words) <= words

    @staticmethod
    def closeness(teryt, near):
        """Shared TERYT prefix: same municipality, county, voivodeship first."""
        return next((n for n in (6, 4, 2) if near and teryt[:n] == near[:n]), 0)

    @staticmethod
    def suggestion(found):
        feature, street, _ = AddressParser.split_street(found["street"])
        place = " ".join(x for x in (feature, street, found["number"]) if x).strip()
        area = found.get("area") or []
        context = "%s, %s" % (area[3], area[1]) if len(area) >= 4 else ""
        kind = "address" if found["number"] else ("street" if street else "place")
        label = ", ".join(x for x in (place, found["city"]) if x)
        return {
            "label": label + (" (gm. %s)" % context if context and kind != "address" else ""),
            "kind": kind,
            "ulica": " ".join(x for x in (feature, street) if x) if found["street"] else "",
            "numer_budynku": found["number"],
            "kod_pocztowy": found.get("code", ""),
            "miejscowosc": found["city"],
            "lat": float(found["lat"]),
            "lon": float(found["lon"]),
            "exact": bool(found["number"]),
        }
