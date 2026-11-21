"""Rejestr zbiorczy AED i zbiór ogólnopolski odbudowywane ze zbiorów instytucji."""

import datetime
import logging

from django.core.cache import cache
from django.db import transaction

from mcod.aed.constants import (
    FOREIGN_TAG_NAMES,
    NATIONAL_KEY,
    NATIONAL_ORG_TITLE,
    PROFILE_KEY,
    STATS_CACHE_KEY,
    RecordStatus,
)
from mcod.aed.export import AedCsv
from mcod.aed.importing.pipeline import ImportPipeline, ImportSource
from mcod.aed.importing.reader import TabularReader, UploadError
from mcod.aed.models import AedRecord
from mcod.aed.publishing import DatasetPublisher, aed_datasets, license_name
from mcod.datasets.models import Dataset
from mcod.organizations.models import Organization
from mcod.resources.models import Resource

logger = logging.getLogger("mcod")
BULK_BATCH_SIZE = 500


def tagged_datasets():
    """Zbiory oznaczone tagiem AED, wgrane bez kreatora (np. zwykłym formularzem zasobu)."""
    queryset = Dataset.objects.filter(status="published", tags__name__iregex=r"^(%s)$" % "|".join(FOREIGN_TAG_NAMES)).distinct()
    return (
        queryset.exclude(customfields__has_key=PROFILE_KEY)
        .exclude(customfields__has_key=NATIONAL_KEY)
        .select_related("organization")
    )


class RegistryBuilder:
    def __init__(self, user=None):
        self.user = user

    @classmethod
    def rebuild_on_commit(cls):
        transaction.on_commit(lambda: cls().rebuild())

    def sources(self):
        """(zbiór, najnowszy opublikowany zasób) dla zbiorów z profilem AED i zbiorów z tagiem AED."""
        for dataset in list(aed_datasets()) + list(tagged_datasets()):
            resource = Resource.objects.filter(dataset=dataset, status="published").order_by("-created").first()
            if resource is not None:
                yield dataset, resource

    def records(self, dataset, resource):
        """Wyniki sprawdzenia rekordów jednego zasobu; zasób, którego nie da się odczytać, jest pomijany z wpisem w logu."""
        main_file = resource._main_file
        if main_file is None or not main_file.file:
            return []
        try:
            with main_file.file.open("rb") as fp:
                table = TabularReader().read(main_file.file.name, fp.read())
        except (UploadError, OSError) as exc:
            logger.warning("AED: pominięto zasób %s zbioru %s: %s", resource.pk, dataset.pk, exc)
            return []
        updated = (resource.data_date or datetime.date.today()).isoformat()
        source = ImportSource.for_organization(dataset.organization, "Zbiór „%s” w dane.gov.pl" % dataset.title, updated)
        pipeline = ImportPipeline(source)
        if PROFILE_KEY in (dataset.customfields or {}):
            return pipeline.check([dict(zip(table.header, row)) for row in table.rows])
        return pipeline.run(table.header, table.rows)

    def rebuild(self):
        collected, licenses = {}, {}
        for dataset, resource in self.sources():
            licenses[dataset.organization.title] = license_name(dataset.license_chosen, "licencja zbioru")
            for result in self.records(dataset, resource):
                if result["status"] in RecordStatus.PUBLISHABLE:
                    self._collect(collected, dataset, resource, result)
        with transaction.atomic():
            AedRecord.objects.all().delete()
            AedRecord.objects.bulk_create(
                [AedRecord.from_result(dataset, resource, result) for dataset, resource, result in collected.values()],
                batch_size=BULK_BATCH_SIZE,
            )
        records = [result["record"] for _, _, result in collected.values()]
        self._publish_national(records, licenses)
        cache.delete(STATS_CACHE_KEY)
        logger.info("Rejestr AED odbudowany: %d rekordów", len(records))
        return len(records)

    @staticmethod
    def _collect(collected, dataset, resource, result):
        id_aed = result["record"]["id_aed"]
        if id_aed in collected:
            logger.warning(
                "AED: identyfikator %s występuje w zbiorach %s i %s, pominięto drugi", id_aed, collected[id_aed][0].pk, dataset.pk
            )
            return
        collected[id_aed] = (dataset, resource, result)

    def _publish_national(self, records, licenses):
        organization, _ = Organization.objects.get_or_create(
            title=NATIONAL_ORG_TITLE, defaults={"institution_type": "state", "status": "published"}
        )
        owner = self.user or organization.users.filter(is_staff=True).first()
        publisher = DatasetPublisher(organization, owner)
        dataset = publisher.dataset_for(Dataset.LICENSE_CC_BY, national=True)
        sources = "; ".join("%s (%s)" % item for item in sorted(licenses.items()))
        description = (
            "Zbiór ogólnopolski zestawiony automatycznie ze zbiorów dostawców w dane.gov.pl (%d urządzeń). "
            "Każdy dostawca odpowiada za swoje dane. Źródła i licencje: %s." % (len(records), sources)
        )
        publisher.replace_resource(dataset, AedCsv.to_csv(records), "Defibrylatory AED w Polsce (CSV)", description)
