"""Filling in missing coordinates with the GUGiK geocoding service (open data)."""

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor

import requests

from mcod.aed.constants import (
    GEOCODE_CACHE_TTL_S,
    GEOCODE_LIMIT,
    GEOCODE_TIMEOUT_S,
    GEOCODE_WORKERS,
)

logger = logging.getLogger("mcod")


class GugikGeocoder:
    URL = "https://services.gugik.gov.pl/uug/"
    CACHE_PREFIX = "aed:geocode:"

    def __init__(
        self, http=requests, cache=None, timeout=GEOCODE_TIMEOUT_S, cache_ttl=GEOCODE_CACHE_TTL_S, workers=GEOCODE_WORKERS
    ):
        self.http = http
        self.cache = cache
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.workers = workers

    @staticmethod
    def query_for(record):
        """Address in the GUGiK format: "postcode city, street number"."""
        street = " ".join(x for x in (record.get("ulica"), record.get("numer_budynku")) if x)
        city = " ".join(x for x in (record.get("kod_pocztowy"), record.get("miejscowosc")) if x)
        return ", ".join(x for x in (city, street) if x)

    def geocode(self, address):
        """{"lat", "lon", "simc"} or None. Failures are not cached, so a transient outage does not block an address."""
        if not address:
            return None
        key = self.CACHE_PREFIX + hashlib.sha1(address.encode("utf-8")).hexdigest()
        hit = self.cache.get(key) if self.cache is not None else None
        if hit is None:
            hit = self._request(address)
            if hit is not None and self.cache is not None:
                self.cache.set(key, hit, self.cache_ttl)
        return hit

    def _request(self, address):
        params = {"request": "GetAddress", "address": address, "srid": "4326"}
        try:
            response = self.http.get(self.URL, params=params, timeout=self.timeout)
            result = (response.json().get("results") or {}).get("1")
            if result and result.get("x") and result.get("y"):
                return {"lat": "%.6f" % float(result["y"]), "lon": "%.6f" % float(result["x"]), "simc": result.get("simc") or ""}
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            logger.warning("GUGiK geocode failed for %s: %s", address, exc)
        return None

    def fill_missing(self, mapped, limit=GEOCODE_LIMIT):
        """mapped: list of (record, notes). Fills in coordinates for records without them (up to limit addresses)."""
        pending = [(record, notes, self.query_for(record)) for record, notes in mapped if self._needs_coordinates(record)][:limit]
        addresses = sorted({address for _, _, address in pending})
        if not addresses:
            return mapped
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            hits = dict(zip(addresses, pool.map(self.geocode, addresses)))
        for record, notes, address in pending:
            hit = hits[address]
            if hit:
                record["szerokosc_geograficzna"], record["dlugosc_geograficzna"] = hit["lat"], hit["lon"]
                if not record.get("kod_simc") and hit["simc"]:
                    record["kod_simc"] = hit["simc"]
                notes.append("Współrzędne ustalono z adresu (geokodowanie GUGiK): %s, %s" % (hit["lat"], hit["lon"]))
        return mapped

    @staticmethod
    def _needs_coordinates(record):
        has_coordinates = (record.get("szerokosc_geograficzna") or "").strip() and (
            record.get("dlugosc_geograficzna") or ""
        ).strip()
        return not has_coordinates and bool(record.get("miejscowosc"))
