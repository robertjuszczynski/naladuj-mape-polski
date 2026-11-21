"""The provider's own standard AED resource. Single adds and task fixes are written here, never to a provider's
original file, and the register reads it before the provider's other resources, so its records win."""

from django.utils import timezone

from mcod.aed.importing.pipeline import ImportSource
from mcod.aed.publishing import DEFAULT_LICENSE, DatasetPublisher
from mcod.aed.registry import RegistryBuilder, SourceError, SourceReader
from mcod.resources.models import AGGREGATED_REGISTER_AED, Resource

SINGLE_ID_MARK = "-p"


class ProviderResource:
    def __init__(self, organization, user):
        self.organization = organization
        self.user = user
        self.publisher = DatasetPublisher(organization, user)

    def resource(self):
        return (
            Resource.objects.filter(
                dataset__organization=self.organization,
                title=self.publisher.resource_title(),
                status="published",
                aggregated_register=AGGREGATED_REGISTER_AED,
            )
            .order_by("-created")
            .first()
        )

    def records(self):
        resource = self.resource()
        if resource is None:
            return []
        try:
            table = SourceReader().read(resource)
        except SourceError:
            return []
        return [dict(zip(table.header, row)) for row in table.rows]

    def license_code(self):
        resource = self.resource()
        return resource.dataset.license_chosen if resource is not None else DEFAULT_LICENSE

    def save(self, records, license_code=None):
        dataset = self.publisher.publish(records, license_code or self.license_code())
        RegistryBuilder.rebuild_on_commit()
        return dataset

    def upsert(self, record, license_code=None):
        records = [r for r in self.records() if r.get("id_aed") != record["id_aed"]]
        return self.save(records + [record], license_code)

    def replace_upload(self, records, license_code):
        """A wizard upload replaces the previous file, but AEDs added one by one stay."""
        uploaded = {r.get("id_aed") for r in records}
        kept = [r for r in self.records() if SINGLE_ID_MARK in (r.get("id_aed") or "") and r.get("id_aed") not in uploaded]
        return self.save(records + kept, license_code)

    def new_id(self):
        source = ImportSource.for_organization(self.organization, "", "")
        return "%s%s%s" % (source.id_prefix, SINGLE_ID_MARK, timezone.now().strftime("%Y%m%d%H%M%S"))
