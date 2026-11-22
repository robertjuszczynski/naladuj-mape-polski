"""Filling in missing coordinates with the GUGiK geocoding service (open data)."""

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor

import requests

from mcod.aed.changes import COORDINATES, change
from mcod.aed.constants import GEOCODE_CACHE_TTL_S, GEOCODE_LIMIT, GEOCODE_TIMEOUT_S, GEOCODE_WORKERS

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
        found = self.candidates(address, use_cache=False)
        if not found:
            return None
        return {key: found[0][key] for key in ("lat", "lon", "simc")}

    def candidates(self, address, use_cache=True):
        """All GUGiK matches for a free-text address, in GUGiK's order; [] when nothing matched or the service failed."""
        key = self.CACHE_PREFIX + "all:" + hashlib.sha1(address.encode("utf-8")).hexdigest()
        if use_cache and self.cache is not None:
            hit = self.cache.get(key)
            if hit is not None:
                return hit
        params = {"request": "GetAddress", "address": address, "srid": "4326"}
        try:
            response = self.http.get(self.URL, params=params, timeout=self.timeout)
            results = response.json().get("results") or {}
            found = [self._parse(results[k]) for k in sorted(results, key=int) if results[k].get("x") and results[k].get("y")]
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            logger.warning("GUGiK geocode failed for %s: %s", address, exc)
            return []
        if found and use_cache and self.cache is not None:
            self.cache.set(key, found, self.cache_ttl)
        return found

    @staticmethod
    def _parse(result):
        return {
            "lat": "%.6f" % float(result["y"]),
            "lon": "%.6f" % float(result["x"]),
            "simc": result.get("simc") or "",
            "city": result.get("city") or "",
            "street": result.get("street") or "",
            "number": result.get("number") or "",
            "code": result.get("code") or "",
        }

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
                coordinates = "%s, %s" % (hit["lat"], hit["lon"])
                notes.append(change(COORDINATES, "Współrzędne ustalono z adresu (geokodowanie GUGiK)", "", coordinates))
        return mapped

    @staticmethod
    def _needs_coordinates(record):
        has_coordinates = (record.get("szerokosc_geograficzna") or "").strip() and (
            record.get("dlugosc_geograficzna") or ""
        ).strip()
        return not has_coordinates and bool(record.get("miejscowosc"))
