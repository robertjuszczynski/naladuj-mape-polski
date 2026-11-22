"""AED lists outside the portal. Sources whose licence allows it (CC0, CC BY, public information) are published as
"unconfirmed" resources of the main register with their author; the rest (e.g. OpenStreetMap, ODbL) stay internal
as leads, grouped into consent requests until the owner agrees."""

import datetime
import logging
import re
from collections import defaultdict
from dataclasses import dataclass

import requests
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from mcod.aed.constants import CONSENT_TITLE_PREFIX, PUBLIC_TITLE_PREFIX, VOIVODESHIPS, ConsentStatus, SourceParser
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
        """Reads one source and returns (published, held)."""
        try:
            content = self.reader.fetch(source)
            if source.parser == SourceParser.OVERPASS:
                published, held = 0, self._hold_osm(source, content)
            else:
                published, held = self._publish(source, self.reader.table(source, content)), 0
            source.error = ""
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.warning("AED: źródło %s nie zostało pobrane: %s", source.pk, exc)
            source.error, published, held = str(exc)[:1000], source.published, source.held
        source.fetched, source.published, source.held = timezone.now(), published, held
        source.save()
        return published, held

    # Publishable sources

    def _publish(self, source, table):
        today = datetime.date.today().isoformat()
        label = "%s (%s), licencja: %s" % (source.name, source.url, LICENCE_LABELS.get(source.licence, source.licence))
        importer = OutsideImport(source.publisher, label, today, "", "aed-zr%s" % source.pk, source.city)
        results = ImportPipeline(importer, geocoder=GugikGeocoder(cache=cache)).run(
            table.header, table.rows, column_mapping(table)
        )
        records = [r["record"] for r in results if r["record"].get("szerokosc_geograficzna")]
        source.rows = len(table.rows)
        publisher = self._publisher()
        dataset = self._public_dataset(publisher)
        description = "Dane pobrane automatycznie przez portal ze źródła: %s. Wydawca: %s. Niepotwierdzone przez dysponentów." % (
            label,
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

    # Sources kept internal

    def _hold_osm(self, source, content):
        import json

        from mcod.aed.models import AedLead, AedRecord

        elements = [e for e in json.loads(content).get("elements", []) if e.get("type") == "node" and "lat" in e]
        known = Proximity(AedRecord.objects.values_list("lat", "lon"))
        places = self.reader.municipalities()
        leads = []
        for element in elements:
            lat, lon = element["lat"], element["lon"]
            record = osm_record(element)
            teryt, municipality = places.get(element["id"]) or (Boundaries.teryt_at(lat, lon), "")
            record["gmina_nazwa"] = municipality
            leads.append(
                AedLead(
                    source=source,
                    external_id="osm-node-%s" % element["id"],
                    name=record["nazwa_obiektu"][:500],
                    operator=record["dysponent_nazwa"][:300],
                    lat=lat,
                    lon=lon,
                    kod_teryt_gminy=teryt,
                    data=record,
                    in_register=known.near(lat, lon),
                )
            )
        with transaction.atomic():
            AedLead.objects.filter(source=source).delete()
            AedLead.objects.bulk_create(leads, batch_size=1000)
        source.rows = len(leads)
        ConsentQueue().rebuild()
        return sum(1 for lead in leads if not lead.in_register)


def operator_key(name):
    return re.sub(r"[^\w]+", " ", (name or "").lower()).strip()


class ConsentQueue:
    """One request per operator named in the source; AEDs without an operator go to their municipality as intermediary."""

    def rebuild(self):
        from mcod.aed.models import AedLead, ConsentRequest

        existing = {r.key: r for r in ConsentRequest.objects.all()}
        groups = defaultdict(list)
        for lead in AedLead.objects.filter(in_register=False).only("id", "operator", "kod_teryt_gminy", "data"):
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
        for lead in request.leads.all():
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
