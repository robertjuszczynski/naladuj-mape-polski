"""Nearest AED available at a given moment, for 112 dispatchers and the campaign map."""

import datetime
import math
import re

from mcod.aed.api.serializers import brief
from mcod.aed.availability import availability_at
from mcod.aed.constants import Availability
from mcod.aed.opening_hours import OpeningHours

EARTH_RADIUS_M = 6371000
WALK_M_PER_MIN = 80
DETOUR_FACTOR = 1.3
DISTANCE_ROUNDING_M = 10
SEARCH_RADIUS_DEG = 0.3
MAX_DISTANCE_M = 5000
OPEN_LIMIT = 3
CLOSED_LIMIT = 3
UNKNOWN_LIMIT = 2
OPENS_AT_STEP = datetime.timedelta(minutes=15)
OPENS_AT_HORIZON = datetime.timedelta(days=7)

_POSTCODE = re.compile(r"\b\d{2}-\d{3}\b")
_STREET_WITH_NUMBER = re.compile(r"^(?P<street>.*?[^\d\s])\s+(?P<number>\d+[\w/]*)$")
_STREET_PREFIX = re.compile(r"^(ul|ulica|al|aleja|aleje|pl|plac|os|osiedle|rondo)\.?\s+", re.I)
_SHORT_PREFIXES = (("ulica ", "ul. "), ("Aleja ", "al. "), ("Aleje ", "al. "), ("plac ", "pl. "), ("osiedle ", "os. "))


def distance_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def floor_label(floor):
    floor = (floor or "").strip()
    return "parter" if floor == "0" else ("piętro %s" % floor if floor else "")


def walk_minutes(meters):
    return max(1, round(meters * DETOUR_FACTOR / WALK_M_PER_MIN))


def opens_at(spec, when):
    """First moment within OPENS_AT_HORIZON when the hours say open; None when unknown."""
    step_min = int(OPENS_AT_STEP.total_seconds() // 60)
    moment = when.replace(minute=when.minute - when.minute % step_min, second=0, microsecond=0)
    end = when + OPENS_AT_HORIZON
    while moment < end:
        moment += OPENS_AT_STEP
        if OpeningHours.is_open_at(spec, moment):
            return moment
    return None


class AddressLocator:
    """Free-text address to a point, picking the GUGiK match whose street really is the typed one."""

    def __init__(self, geocoder):
        self.geocoder = geocoder

    @staticmethod
    def parse(text):
        """("Warszawa", "Wiejska", "4") from "ul. Wiejska 4, 00-902 Warszawa" or "Warszawa, Wiejska 4"."""
        parts = [p.strip() for p in _POSTCODE.sub("", text).split(",") if p.strip()]
        if len(parts) != 2:
            return None
        for street_part, city in (parts, parts[::-1]):
            match = _STREET_WITH_NUMBER.match(street_part)
            if match and not any(ch.isdigit() for ch in city):
                return city, _STREET_PREFIX.sub("", match.group("street")).strip(), match.group("number")
        return None

    @staticmethod
    def _street_key(street):
        words = _STREET_PREFIX.sub("", street or "").lower().split()
        return words[-1] if words else ""

    @staticmethod
    def _label(found):
        street = found["street"]
        for long, short in _SHORT_PREFIXES:
            if street.startswith(long):
                street = short + street[len(long) :]
        place = " ".join(x for x in (street, found["number"]) if x)
        return ", ".join(x for x in (place, found["city"]) if x)

    def _point(self, found, exact):
        return {"lat": float(found["lat"]), "lon": float(found["lon"]), "label": self._label(found), "exact": exact}

    def locate(self, text):
        text = (text or "").strip()
        if not text:
            return None
        parsed = self.parse(text)
        if parsed:
            city, street, number = parsed
            key = self._street_key(street)
            for query, exact in (("%s, %s %s" % (city, street, number), True), ("%s, %s" % (city, street), False)):
                match = next((f for f in self.geocoder.candidates(query) if self._street_key(f["street"]) == key), None)
                if match:
                    return self._point(match, exact)
            return None
        found = self.geocoder.candidates(text)
        return self._point(found[0], True) if found else None


class NearestAed:
    def __init__(self, records, when, reported=frozenset()):
        self.records = records
        self.when = when
        self.reported = reported

    def find(self, lat, lon):
        """Up to OPEN_LIMIT open AED, plus closed and unknown ones that are nearer than the farthest open one."""
        ranked = sorted(
            ((distance_m(lat, lon, r.lat, r.lon), r, availability_at(r.data, self.when)) for r in self.records),
            key=lambda item: item[0],
        )
        ranked = [item for item in ranked if item[0] <= MAX_DISTANCE_M]
        available = [item for item in ranked if item[2] == Availability.OPEN][:OPEN_LIMIT]
        reach = available[-1][0] if len(available) == OPEN_LIMIT else float("inf")
        closer = [item for item in ranked if item[0] < reach]
        closed = [item for item in closer if item[2] in (Availability.CLOSED, Availability.FAULTY)][:CLOSED_LIMIT]
        unknown = [item for item in closer if item[2] == Availability.UNKNOWN][:UNKNOWN_LIMIT]
        return {
            "open": [self.item(*item) for item in available],
            "closed": [self.item(*item) for item in closed],
            "unknown": [self.item(*item) for item in unknown],
        }

    def item(self, meters, record, availability):
        data = record.data
        rounded = int(round(meters / DISTANCE_ROUNDING_M) * DISTANCE_ROUNDING_M)
        out = dict(
            brief(record, self.when, self.reported),
            distance_m=rounded,
            walk_min=walk_minutes(meters),
            location=data.get("opis_lokalizacji", ""),
            floor=floor_label(data.get("pietro", "")),
            opens_at=None,
        )
        if availability == Availability.CLOSED:
            moment = opens_at(data.get("godziny_dostepnosci"), self.when)
            out["opens_at"] = moment.isoformat() if moment else None
        out["phrase"] = self.phrase(out)
        return out

    @staticmethod
    def phrase(item):
        """Sentence a dispatcher can read to the caller."""
        place = ", ".join(x for x in (item["name"], item["address"]) if x)
        details = ", ".join(x.strip().rstrip(".") for x in (item["location"], item["floor"]) if x and x.strip())
        sentence = "%d m, ok. %d min pieszo: %s." % (item["distance_m"], item["walk_min"], place)
        return "%s %s." % (sentence, details[0].upper() + details[1:]) if details else sentence
