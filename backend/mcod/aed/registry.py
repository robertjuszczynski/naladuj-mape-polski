"""The main AED register ("wykaz zbiorczy"), built like the main DGA list: every published resource flagged as the
AED register is read, matched to the data standard and merged into one list published by the register owner."""

import datetime
import logging
import os
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from mcod.aed.conflicts import duplicate_id, find_conflicts, within_record
from mcod.aed.constants import NATIONAL_ORG_TITLE, PUBLIC_TITLE_PREFIX, STATS_CACHE_KEY, RecordStatus
from mcod.aed.export import AedCsv, AedGeoJson
from mcod.aed.importing.geocoder import GugikGeocoder
from mcod.aed.importing.pipeline import ImportPipeline, ImportSource
from mcod.aed.importing.reader import TabularReader, UploadError
from mcod.aed.models import AedRecord, AggregatedAedInfo
from mcod.aed.planner import TaskPlanner
from mcod.aed.profile import FIELD_NAMES
from mcod.aed.publishing import DatasetPublisher, license_name, register_resources
from mcod.aed.validation import RecordValidator
from mcod.datasets.models import Dataset
from mcod.organizations.models import Organization

logger = logging.getLogger("mcod")
BULK_BATCH_SIZE = 500
LINK_TIMEOUT_S = 20
SKIPPED_EMPTY = "Zasób nie ma pliku ani działającego linku"


class SourceError(Exception):
    """A register resource that cannot be read; the message goes to the sources report."""


class SourceReader:
    """Rows of a register resource: its stored file, or the file behind its link (e.g. a list published in BIP)."""

    def __init__(self, http=requests):
        self.http = http

    def read(self, resource):
        main_file = resource._main_file
        if main_file is not None and main_file.file:
            try:
                with main_file.file.open("rb") as fp:
                    return TabularReader().read(main_file.file.name, fp.read())
            except (UploadError, OSError) as exc:
                raise SourceError(str(exc))
        if resource.link:
            return self._read_link(resource.link)
        raise SourceError(SKIPPED_EMPTY)

    def _read_link(self, url):
        try:
            response = self.http.get(url, timeout=LINK_TIMEOUT_S)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SourceError("Nie udało się pobrać pliku z linku: %s" % exc)
        try:
            return TabularReader().read(os.path.basename(urlparse(url).path) or "plik.csv", response.content)
        except UploadError as exc:
            raise SourceError(str(exc))


def is_public_source(resource):
    return resource.title.startswith(PUBLIC_TITLE_PREFIX)


def is_standard(header):
    """Files made with the data standard (e.g. by the wizard) are only checked; any other layout is matched first."""
    return "id_aed" in header and set(header) <= set(FIELD_NAMES)


class RegistryBuilder:
    def __init__(self, user=None, reader=None, geocoder=None):
        self.user = user
        self.reader = reader or SourceReader()
        self.geocoder = geocoder if geocoder is not None else GugikGeocoder(cache=cache)
        self.conflicts = []

    @classmethod
    def rebuild_on_commit(cls):
        transaction.on_commit(lambda: cls().rebuild())

    def records(self, resource):
        dataset = resource.dataset
        table = self.reader.read(resource)
        updated = (resource.data_date or datetime.date.today()).isoformat()
        source = ImportSource.for_organization(dataset.organization, "Zbiór „%s” w dane.gov.pl" % dataset.title, updated)
        if is_standard(table.header):
            return ImportPipeline(source).check([dict(zip(table.header, row)) for row in table.rows])
        return ImportPipeline(source, geocoder=self.geocoder).run(table.header, table.rows)

    def rebuild(self):
        collected, licenses, report = {}, {}, []
        self.conflicts = []
        for resource in sorted(register_resources(), key=lambda r: (is_public_source(r), self._is_original_file(r))):
            report.append(self._read_source(resource, collected, licenses))
        entries = self._without_public_duplicates(collected)
        self.conflicts += find_conflicts(
            [
                {"source": e.resource.title, "id": e.id_aed, "name": e.nazwa_obiektu, "lat": e.lat, "lon": e.lon, "data": e.data}
                for e in entries
            ]
        )
        for e in entries:
            messages = [i["message"] for i in RecordValidator.contradictions(e.data)]
            if messages:
                self.conflicts.append(within_record(e.resource.title, e.id_aed, e.nazwa_obiektu, messages))
        with transaction.atomic():
            AedRecord.objects.all().delete()
            AedRecord.objects.bulk_create(entries, batch_size=BULK_BATCH_SIZE)
        records = [entry.data for entry in entries]
        self._publish_main(records, licenses, report)
        cache.delete(STATS_CACHE_KEY)
        TaskPlanner().sync()
        logger.info("Wykaz zbiorczy AED: %d urządzeń z %d zasobów", len(records), len(report))
        return len(records)

    @staticmethod
    def _without_public_duplicates(collected):
        """Registry entries; an unconfirmed AED from a public source is left out when a provider already published it."""
        from mcod.aed.outside import Proximity

        entries = []
        for resource, result in collected.values():
            entry = AedRecord.from_result(resource.dataset, resource, result)
            entry.verified = not is_public_source(resource)
            entries.append(entry)
        confirmed = Proximity([(e.lat, e.lon) for e in entries if e.verified and e.lat is not None])
        return [e for e in entries if e.verified or e.lat is None or not confirmed.near(e.lat, e.lon)]

    @staticmethod
    def _is_original_file(resource):
        """The provider's standard resource goes first, so single adds and task fixes win over its original files."""
        return resource.title != DatasetPublisher(resource.dataset.organization, None).resource_title()

    def _read_source(self, resource, collected, licenses):
        dataset = resource.dataset
        entry = {
            "resource_id": resource.pk,
            "resource": resource.title,
            "dataset_id": dataset.pk,
            "organization": dataset.organization.title,
            "license": license_name(dataset.license_chosen, "licencja zbioru"),
            "rows": 0,
            "published": 0,
            "error": "",
        }
        try:
            results = self.records(resource)
        except SourceError as exc:
            logger.warning("AED: pominięto zasób %s zbioru %s: %s", resource.pk, dataset.pk, exc)
            return dict(entry, error=str(exc))
        entry["rows"] = len(results)
        for result in results:
            if result["status"] in RecordStatus.PUBLISHABLE and self._collect(collected, resource, result):
                entry["published"] += 1
        if entry["published"]:
            licenses[dataset.organization.title] = entry["license"]
        return entry

    def _collect(self, collected, resource, result):
        id_aed = result["record"]["id_aed"]
        if id_aed in collected:
            logger.warning("AED: identyfikator %s występuje w zasobach %s i %s", id_aed, collected[id_aed][0].pk, resource.pk)
            self.conflicts.append(duplicate_id(id_aed, collected[id_aed][0].title, resource.title))
            return False
        collected[id_aed] = (resource, result)
        return True

    def _owner(self):
        pk = settings.MAIN_AED_DATASET_OWNER_ORGANIZATION_PK
        organization = Organization.objects.filter(pk=pk).first() if pk else None
        if organization is None:
            organization, _ = Organization.objects.get_or_create(
                title=NATIONAL_ORG_TITLE, defaults={"institution_type": "state", "status": "published"}
            )
        return organization

    def _publish_main(self, records, licenses, report):
        organization = self._owner()
        owner = self.user or organization.users.filter(is_staff=True).first()
        publisher = DatasetPublisher(organization, owner)
        dataset = publisher.dataset_for(Dataset.LICENSE_CC_BY, national=True)
        sources = "; ".join("%s (%s)" % item for item in sorted(licenses.items()))
        description = (
            "Wykaz zbiorczy AED zestawiony automatycznie z zasobów dostawców oznaczonych jako wykaz AED (%d urządzeń). "
            "Każdy dostawca odpowiada za swoje dane. Źródła i licencje: %s." % (len(records), sources)
        )
        resource = publisher.replace_resource(dataset, AedCsv.to_csv(records), "Defibrylatory AED w Polsce (CSV)", description)
        publisher.replace_resource(
            dataset,
            AedGeoJson.to_geojson(records),
            "Defibrylatory AED w Polsce (GeoJSON)",
            description + " Ten sam wykaz jako punkty GeoJSON (WGS 84) do map i systemów GIS.",
            file_format="geojson",
        )
        info = AggregatedAedInfo.current() or AggregatedAedInfo()
        info.dataset, info.resource, info.sources = dataset, resource, report
        info.conflicts = self.conflicts
        info.save()
