"""Publishing AED data as native portal datasets and resources."""

import datetime

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from mcod.aed.constants import AED_TAG_NAMES
from mcod.aed.export import AedCsv
from mcod.aed.profile import PROFILE_VERSION
from mcod.categories.models import Category
from mcod.datasets.models import Dataset
from mcod.resources.models import AGGREGATED_REGISTER_AED, Resource, ResourceFile
from mcod.tags.models import Tag

ALLOWED_LICENSES = (Dataset.LICENSE_CC0, Dataset.LICENSE_CC_BY)
DEFAULT_LICENSE = Dataset.LICENSE_CC_BY
LICENSE_HINTS = {
    Dataset.LICENSE_CC0: ("bez warunków", "Zalecana w Przewodniku dla dostawców danych dane.gov.pl."),
    Dataset.LICENSE_CC_BY: ("z podaniem źródła", "Kto korzysta z danych, musi wskazać Twoją organizację jako autora."),
}
LICENSE_NAME_TO_CODE = {name: code for code, name in Dataset.LICENSES}
PUBLIC_INSTITUTION_TYPES = ("local", "state")


def license_options():
    return [
        {
            "code": code,
            "name": Dataset.LICENSE_CODE_TO_NAME[code],
            "title": LICENSE_HINTS[code][0],
            "hint": LICENSE_HINTS[code][1],
        }
        for code in ALLOWED_LICENSES
    ]


def is_public_institution(organizations):
    """Public bodies publish open data without conditions by default (CC0), so the licence choice starts folded."""
    return all(o.institution_type in PUBLIC_INSTITUTION_TYPES for o in organizations) if organizations else False


def license_from_form(value):
    return next((code for code in ALLOWED_LICENSES if str(code) == value), DEFAULT_LICENSE)


def license_name(code, default=""):
    return Dataset.LICENSE_CODE_TO_NAME.get(code, default)


def register_resources():
    """Published resources flagged as the AED register, whichever way they came: wizard, resource form or harvester."""
    return (
        Resource.objects.filter(aggregated_register=AGGREGATED_REGISTER_AED, status="published", dataset__status="published")
        .select_related("dataset__organization")
        .order_by("dataset__organization__title", "-created")
    )


def national_dataset():
    from mcod.aed.models import AggregatedAedInfo

    info = AggregatedAedInfo.current()
    return info.main_dataset if info else None


class DatasetPublisher:
    def __init__(self, organization, user):
        self.organization = organization
        self.user = user

    @transaction.atomic
    def publish(self, records, license_code):
        dataset = self.dataset_for(license_code)
        description = "Wzorcowy zakres danych AED %s. Liczba urządzeń: %d. Opublikowano przez kreator „Dodaj dane o AED”." % (
            PROFILE_VERSION,
            len(records),
        )
        self.replace_resource(
            dataset, AedCsv.to_csv(records), self.resource_title(), description, register=AGGREGATED_REGISTER_AED
        )
        return dataset

    def resource_title(self):
        """Title of the provider's own standard resource, the one the wizard, single adds and task fixes write to."""
        return "Defibrylatory AED – %s (CSV)" % self.organization.title

    def dataset_for(self, license_code, national=False):
        """The organization's AED dataset (the one holding its register resource), created when missing."""
        if national:
            dataset = national_dataset()
        else:
            dataset = (
                Dataset.objects.filter(
                    organization=self.organization,
                    status="published",
                    resources__aggregated_register=AGGREGATED_REGISTER_AED,
                    resources__status="published",
                )
                .order_by("-modified")
                .first()
            )
        if dataset is None:
            return self._create_dataset(license_code, national)
        if dataset.license_chosen != license_code:
            dataset.license_chosen = license_code
            dataset.save()
        return dataset

    def _create_dataset(self, license_code, national):
        title, notes = self._describe(national)
        category = self.health_category()
        dataset = Dataset.objects.create(
            title=title,
            notes=notes,
            organization=self.organization,
            category=category,
            license_chosen=license_code,
            update_frequency="daily" if national else "monthly",
            status="published",
            created_by=self.user,
            modified_by=self.user,
        )
        dataset.categories.add(category)
        dataset.tags.add(*self.aed_tags())
        return dataset

    def _describe(self, national):
        if national:
            return (
                "Defibrylatory AED w Polsce – wykaz zbiorczy",
                "Wykaz zbiorczy automatycznych defibrylatorów zewnętrznych (AED): portal co noc odczytuje zasoby dostawców "
                "oznaczone jako wykaz AED, dopasowuje je do wzorcowego zakresu danych AED %s i scala w jedną listę. "
                "Akcja „Naładuj mapę Polski.”" % PROFILE_VERSION,
            )
        title = self.organization.title
        return (
            "Defibrylatory AED – %s" % title,
            "Lokalizacje i dostępność defibrylatorów AED udostępnione przez: %s, według wzorcowego zakresu danych AED %s. "
            "Dane zebrane w ramach akcji „Naładuj mapę Polski.”" % (title, PROFILE_VERSION),
        )

    def replace_resource(self, dataset, content, title, description, register="", file_format="csv"):
        """Replace the resource with this title; other resources of the dataset (e.g. the provider's own file) stay."""
        tabular = file_format == "csv"
        for old in Resource.objects.filter(dataset=dataset, status="published", title=title):
            old.delete()
        resource = Resource.objects.create(
            dataset=dataset,
            title=title,
            description=description,
            format=file_format,
            type="file",
            status="published",
            data_date=datetime.date.today(),
            created_by=self.user,
            modified_by=self.user,
            show_tabular_view=tabular,
            tabular_data_schema=AedCsv.table_schema(content) if tabular else None,
            aggregated_register=register,
        )
        name = "aed-%s-%s.%s" % (dataset.pk, timezone.now().strftime("%Y%m%d%H%M%S"), file_format)
        ResourceFile.objects.create(resource=resource, is_main=True, format=file_format, file=ContentFile(content, name=name))
        return resource

    @staticmethod
    def health_category():
        category = (
            Category.objects.filter(code__iexact="HEAL").first() or Category.objects.filter(title__icontains="zdrow").first()
        )
        if category is None:
            category = Category.objects.create(code="HEAL", title="Zdrowie", title_en="Health", status="published")
        return category

    @staticmethod
    def aed_tags():
        return [
            Tag.objects.filter(name=name, language="pl").first()
            or Tag.objects.create(name=name, language="pl", status="published")
            for name in AED_TAG_NAMES
        ]
