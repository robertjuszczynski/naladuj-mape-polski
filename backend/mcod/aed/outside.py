"""AED lists outside the portal (any format: CSV, XLSX, PDF, OpenStreetMap). The portal does not trust them: every point
becomes a lead that its municipality confirms, rejects or marks as someone else's. Sources whose licence allows it
(CC0, CC BY, public information) are also published meanwhile as "unconfirmed" with their author; the rest (e.g.
OpenStreetMap, ODbL) stay internal and are grouped into consent requests until the owner agrees."""

import datetime
import hashlib
import logging
import re
from collections import defaultdict
from dataclasses import dataclass

import requests
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from mcod.aed.constants import (
    CONSENT_TITLE_PREFIX,
    GEOCODE_TIMEOUT_S,
    PUBLIC_TITLE_PREFIX,
    VOIVODESHIPS,
    ConsentStatus,
    LeadReview,
    SourceLicence,
    SourceParser,
)
from mcod.aed.export import AedCsv
from mcod.aed.geo import Boundaries
from mcod.aed.importing.columns import ColumnMatcher
from mcod.aed.importing.geocoder import GugikGeocoder
from mcod.aed.importing.pdf import pdf_table
from mcod.aed.importing.pipeline import ImportPipeline, ImportSource
from mcod.aed.importing.reader import TabularReader
from mcod.aed.nearest import distance_m
from mcod.aed.opening_hours import OpeningHours
from mcod.aed.publishing import DatasetPublisher, national_dataset
from mcod.datasets.models import Dataset
from mcod.resources.models import AGGREGATED_REGISTER_AED

logger = logging.getLogger("mcod")
USER_AGENT = "dane.gov.pl AED register (Naladuj mape Polski)"
FETCH_TIMEOUT_S = 240
MUNICIPALITY_TIMEOUT_S = 300
OVERPASS_MIRRORS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
MUNICIPALITY_QUERY = """[out:csv(::type,::id,"teryt:terc",name;false;"|")][timeout:300];
area["teryt:terc"="%s"]["admin_level"="4"]->.woj;
rel(area.woj)["boundary"="administrative"]["admin_level"~"^(6|7)$"]["teryt:terc"~"^[0-9]{7}$"];
map_to_area->.gminy;
foreach.gminy->.g(
  .g out tags;
  node(area.g)["emergency"="defibrillator"];
  out ids;
);"""
PUBLIC_DATASET_TITLE = "Defibrylatory AED ze źródeł publicznych (niepotwierdzone)"
SAME_PLACE_M = 30
MUNICIPALITY_PREFIX = 6
GRID = 0.001
NAME_COLUMN = re.compile(r"miejsce|nazwa|obiekt|lokalizacja", re.I)
LICENCE_LABELS = {"cc0": "CC0 1.0", "cc_by": "CC BY 4.0", "public_info": "informacja publiczna"}
OSM_FIELDS = {
    "opening_hours": "godziny_dostepnosci",
    "defibrillator:location": "opis_lokalizacji",
    "defibrillator:location:pl": "opis_lokalizacji",
    "level": "pietro",
    "phone": "dysponent_telefon",
    "addr:street": "ulica",
    "addr:housenumber": "numer_budynku",
    "addr:postcode": "kod_pocztowy",
    "addr:city": "miejscowosc",
}


@dataclass(frozen=True)
class OutsideImport(ImportSource):
    city: str = ""

    def defaults(self):
        values = super().defaults()
        if self.city:
            values["miejscowosc"] = self.city
        return values


class SourceReader:
    def __init__(self, http=requests):
        self.http = http

    def overpass(self, query, timeout):
        """Public Overpass servers are often busy; the next mirror is tried before giving up."""
        error = None
        for url in OVERPASS_MIRRORS:
            try:
                response = self.http.post(url, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=timeout)
                response.raise_for_status()
                return response.content
            except requests.RequestException as exc:
                error = exc
        raise error

    def municipalities(self):
        """{OSM node id: (TERYT code, municipality name)} from the municipality boundaries in OpenStreetMap,
        one voivodeship per query so that a busy public server does not time out."""
        out = {}
        for code in VOIVODESHIPS:
            try:
                out.update(self._municipalities(code))
            except requests.RequestException as exc:
                logger.warning("AED: nie pobrano gmin województwa %s z OSM: %s", code, exc)
        return out

    def _municipalities(self, voivodeship):
        out, current = {}, ("", "")
        for line in self.overpass(MUNICIPALITY_QUERY % voivodeship, MUNICIPALITY_TIMEOUT_S).decode("utf-8").splitlines():
            kind, osm_id, terc, name = (line.split("|") + ["", "", "", ""])[:4]
            if kind == "area":
                current = (terc, name)
            elif kind == "node" and current[0]:
                out[int(osm_id)] = current
        return out

    def fetch(self, source):
        if source.parser == SourceParser.OVERPASS:
            return self.overpass(source.query, FETCH_TIMEOUT_S)
        response = self.http.get(source.url, headers={"User-Agent": USER_AGENT}, timeout=FETCH_TIMEOUT_S)
        response.raise_for_status()
        return response.content

    def table(self, source, content):
        if source.parser == SourceParser.PDF:
            return pdf_table(content)
        return TabularReader().read(source.url.rsplit("/", 1)[-1] or "plik.csv", content)


def column_mapping(table):
    mapping = ColumnMatcher().suggest(table.header, table.rows[:3])
    if "nazwa_obiektu" not in mapping.values():
        name = next((c for c in table.header if NAME_COLUMN.search(c) and not mapping.get(c)), None)
        if name:
            mapping[name] = "nazwa_obiektu"
    return mapping


def osm_record(element):
    tags = element.get("tags") or {}
    record = {target: tags[key] for key, target in OSM_FIELDS.items() if tags.get(key)}
    hours = record.get("godziny_dostepnosci", "")
    if hours and not OpeningHours.is_valid(hours):
        record.pop("godziny_dostepnosci")
    if hours == "24/7":
        record["dostepny_calodobowo"] = "true"
    record["nazwa_obiektu"] = tags.get("name") or tags.get("operator") or "AED"
    record["dysponent_nazwa"] = tags.get("operator", "")
    return record


class Proximity:
    """Is there a point within SAME_PLACE_M metres? A grid of ~100 m cells keeps 18 000 checks fast."""

    def __init__(self, points):
        self.cells = defaultdict(list)
        for lat, lon in points:
            self.cells[(int(lat / GRID), int(lon / GRID))].append((lat, lon))

    def near(self, lat, lon):
        ci, cj = int(lat / GRID), int(lon / GRID)
        return any(
            distance_m(lat, lon, la, lo) <= SAME_PLACE_M
            for di in (-1, 0, 1)
            for dj in (-1, 0, 1)
            for la, lo in self.cells.get((ci + di, cj + dj), ())
        )


class OutsideSources:
    def __init__(self, user=None, reader=None):
        self.user = user
        self.reader = reader or SourceReader()

    def run(self, source):
        """Reads one source and returns (published, held). Every point becomes a lead for its municipality to confirm;
        the licence only decides whether the points are also published as unconfirmed meanwhile."""
        try:
            content = self.reader.fetch(source)
            if source.parser == SourceParser.OVERPASS:
                found = self._osm_points(content)
            else:
                found = self._table_points(source, self.reader.table(source, content))
            source.rows = len(found)
            published = self._publish(source, [point.record for point in found]) if source.publishable else 0
            held = self._hold(source, found)
            source.error = ""
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.warning("AED: źródło %s nie zostało pobrane: %s", source.pk, exc)
            source.error, published, held = str(exc)[:1000], source.published, source.held
        source.fetched, source.published, source.held = timezone.now(), published, held
        source.save()
        return published, held

    # Reading points

    def _table_points(self, source, table):
        today = datetime.date.today().isoformat()
        importer = OutsideImport(source.publisher, self.label(source), today, "", "aed-zr%s" % source.pk, source.city)
        results = ImportPipeline(importer, geocoder=GugikGeocoder(cache=cache)).run(
            table.header, table.rows, column_mapping(table)
        )
        points = []
        for result in results:
            record = result["record"]
            if not record.get("szerokosc_geograficzna"):
                continue
            lat, lon = float(record["szerokosc_geograficzna"]), float(record["dlugosc_geograficzna"])
            operator = record.get("dysponent_nazwa", "")
            points.append(
                Point(
                    external_id=row_id(record),
                    record=record,
                    lat=lat,
                    lon=lon,
                    teryt=self._teryt(record, lat, lon),
                    operator="" if operator == source.publisher else operator,
                )
            )
        return points

    @staticmethod
    def _teryt(record, lat, lon):
        """Municipality of a row: from the row, from its address (GUGiK), or from the nearest address to the point."""
        if record.get("kod_teryt_gminy"):
            return record["kod_teryt_gminy"][:MUNICIPALITY_PREFIX]
        geocoder = GugikGeocoder(cache=cache)
        found = geocoder.candidates(geocoder.query_for(record)) if record.get("miejscowosc") else []
        return (found[0]["teryt"] if found else "")[:MUNICIPALITY_PREFIX] or municipality_at(lat, lon)

    def _osm_points(self, content):
        import json

        elements = [e for e in json.loads(content).get("elements", []) if e.get("type") == "node" and "lat" in e]
        places = self.reader.municipalities()
        points = []
        for element in elements:
            lat, lon = element["lat"], element["lon"]
            record = osm_record(element)
            teryt, municipality = places.get(element["id"]) or (Boundaries.teryt_at(lat, lon), "")
            record["gmina_nazwa"] = municipality
            points.append(Point("osm-node-%s" % element["id"], record, lat, lon, (teryt or "")[:7], record["dysponent_nazwa"]))
        return points

    @staticmethod
    def label(source):
        return "%s (%s), licencja: %s" % (source.name, source.url, LICENCE_LABELS.get(source.licence, source.licence))

    # Publishable sources

    def _publish(self, source, records):
        publisher = self._publisher()
        dataset = self._public_dataset(publisher)
        description = "Dane pobrane automatycznie przez portal ze źródła: %s. Wydawca: %s. Niepotwierdzone przez dysponentów." % (
            self.label(source),
            source.publisher,
        )
        publisher.replace_resource(
            dataset, AedCsv.to_csv(records), PUBLIC_TITLE_PREFIX + source.name, description, register=AGGREGATED_REGISTER_AED
        )
        return len(records)

    def _publisher(self):
        info_dataset = national_dataset()
        organization = info_dataset.organization if info_dataset else None
        if organization is None:
            from mcod.aed.registry import RegistryBuilder

            organization = RegistryBuilder(self.user)._owner()
        return DatasetPublisher(organization, self.user or organization.users.filter(is_staff=True).first())

    @staticmethod
    def _public_dataset(publisher):
        dataset = Dataset.objects.filter(
            organization=publisher.organization, title=PUBLIC_DATASET_TITLE, status="published"
        ).first()
        if dataset is None:
            dataset = publisher._create_dataset(Dataset.LICENSE_CC_BY, national=False)
            dataset.title = PUBLIC_DATASET_TITLE
            dataset.notes = (
                "AED z list publikowanych przez instytucje poza portalem (np. w BIP), pobierane automatycznie co noc. "
                "Każdy rekord ma podane źródło i licencję. Dysponent może je potwierdzić, publikując własny zbiór."
            )
            dataset.save()
        return dataset

    # Leads: every point waits for its municipality (and, if the licence requires, for the owner's consent)

    def _hold(self, source, points):
        from mcod.aed.models import AedLead, AedRecord

        confirmed = Proximity(AedRecord.objects.filter(verified=True).values_list("lat", "lon"))
        reviews = {
            external_id: (review, note)
            for external_id, review, note in AedLead.objects.filter(source=source)
            .exclude(review="")
            .values_list("external_id", "review", "review_note")
        }
        leads = []
        for point in points:
            review, note = reviews.get(point.external_id, ("", ""))
            leads.append(
                AedLead(
                    source=source,
                    external_id=point.external_id,
                    name=(point.record.get("nazwa_obiektu") or "AED")[:500],
                    operator=point.operator[:300],
                    lat=point.lat,
                    lon=point.lon,
                    kod_teryt_gminy=point.teryt,
                    data=point.record,
                    in_register=confirmed.near(point.lat, point.lon) or review == LeadReview.CONFIRMED,
                    review=review,
                    review_note=note,
                )
            )
        with transaction.atomic():
            AedLead.objects.filter(source=source).delete()
            AedLead.objects.bulk_create(leads, batch_size=1000)
        ConsentQueue().rebuild()
        return 0 if source.publishable else sum(1 for lead in leads if not lead.in_register)


@dataclass(frozen=True)
class Point:
    external_id: str
    record: dict
    lat: float
    lon: float
    teryt: str
    operator: str


def row_id(record):
    """Stable id of a row without an id of its own: the same AED at the same address keeps its municipality's decision."""
    key = "|".join(str(record.get(k) or "").strip().lower() for k in ("nazwa_obiektu", "ulica", "numer_budynku", "miejscowosc"))
    return "row-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]


def municipality_at(lat, lon):
    """Municipality code (6 digits, as GUGiK gives it) of a point: the nearest address in the national register."""
    found = GugikGeocoder(cache=cache, timeout=GEOCODE_TIMEOUT_S).reverse(lat, lon) or {}
    teryt = found.get("teryt") or Boundaries.teryt_at(lat, lon) or ""
    return teryt[:MUNICIPALITY_PREFIX]


def operator_key(name):
    return re.sub(r"[^\w]+", " ", (name or "").lower()).strip()


class ConsentQueue:
    """One request per operator named in the source; AEDs without an operator go to their municipality as intermediary."""

    def rebuild(self):
        from mcod.aed.models import AedLead, ConsentRequest

        existing = {r.key: r for r in ConsentRequest.objects.all()}
        groups = defaultdict(list)
        waiting = (
            AedLead.objects.filter(in_register=False)
            .exclude(review__in=LeadReview.CLOSED)
            .exclude(source__licence__in=SourceLicence.PUBLISHABLE)
        )
        for lead in waiting.only("id", "operator", "kod_teryt_gminy", "data"):
            key = "op:" + operator_key(lead.operator) if operator_key(lead.operator) else "gm:" + (lead.kod_teryt_gminy or "?")
            groups[key].append(lead)
        with transaction.atomic():
            for key, leads in groups.items():
                request = existing.get(key) or ConsentRequest(key=key)
                request.label, request.is_municipality = self._label(key, leads[0])
                request.lead_count = len(leads)
                request.save()
                AedLead.objects.filter(pk__in=[lead.pk for lead in leads]).update(request=request)
            ConsentRequest.objects.exclude(key__in=groups).filter(status=ConsentStatus.TO_CONTACT).update(lead_count=0)
        return len(groups)

    @staticmethod
    def _label(key, lead):
        if key.startswith("op:"):
            return lead.operator, False
        boundary = Boundaries.get(lead.kod_teryt_gminy)
        name = (lead.data or {}).get("gmina_nazwa") or (boundary["name"] if boundary else "")
        if not name:
            return "Gmina nieustalona", True
        name = re.sub(r"^(gmina|miasto)\s+", "", name, flags=re.I)
        return "Gmina %s (dla AED bez wskazanego dysponenta)" % name, True

    def publish_agreed(self, request, user):
        """After the owner confirmed its AEDs (phone or e-mail): publish them as its statement, under CC0."""
        sources = OutsideSources(user)
        publisher = sources._publisher()
        dataset = sources._public_dataset(publisher)
        today = datetime.date.today().isoformat()
        records = []
        for lead in request.leads.filter(in_register=False).exclude(review__in=LeadReview.CLOSED):
            record = dict(lead.data)
            record.update(
                {
                    "id_aed": "aed-zgoda-%s" % lead.external_id,
                    "szerokosc_geograficzna": "%.6f" % lead.lat,
                    "dlugosc_geograficzna": "%.6f" % lead.lon,
                    "kod_teryt_gminy": lead.kod_teryt_gminy,
                    "dysponent_nazwa": lead.operator or request.label,
                    "zrodlo_danych": "Dane potwierdzone przez dysponenta: %s, %s" % (request.label, today),
                    "data_aktualizacji": today,
                }
            )
            records.append(record)
        description = "AED potwierdzone przez dysponenta (%s) po kontakcie portalu, %s. Licencja CC0." % (request.label, today)
        publisher.replace_resource(
            dataset,
            AedCsv.to_csv(records),
            CONSENT_TITLE_PREFIX + request.label[:200],
            description,
            register=AGGREGATED_REGISTER_AED,
        )
        request.status = ConsentStatus.AGREED
        request.save()
        return len(records)
