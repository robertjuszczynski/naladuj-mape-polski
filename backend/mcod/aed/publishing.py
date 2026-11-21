"""Publikacja danych AED jako natywnych zbiorów i zasobów portalu."""

import datetime

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from mcod.aed.constants import AED_TAG_NAMES, NATIONAL_KEY, PROFILE_KEY
from mcod.aed.export import AedCsv
from mcod.aed.profile import PROFILE_VERSION
from mcod.categories.models import Category
from mcod.datasets.models import Dataset
from mcod.resources.models import Resource, ResourceFile
from mcod.tags.models import Tag

ALLOWED_LICENSES = (Dataset.LICENSE_CC0, Dataset.LICENSE_CC_BY)
DEFAULT_LICENSE = Dataset.LICENSE_CC_BY
LICENSE_HINTS = {
    Dataset.LICENSE_CC0: ("bez warunków", "Zalecana w Przewodniku dla dostawców danych dane.gov.pl."),
    Dataset.LICENSE_CC_BY: ("z podaniem źródła", "Kto korzysta z danych, musi wskazać Twoją organizację jako autora."),
}
LICENSE_NAME_TO_CODE = {name: code for code, name in Dataset.LICENSES}


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


def license_from_form(value):
    return next((code for code in ALLOWED_LICENSES if str(code) == value), DEFAULT_LICENSE)


def license_name(code, default=""):
    return Dataset.LICENSE_CODE_TO_NAME.get(code, default)


def aed_datasets(include_national=False):
    queryset = Dataset.objects.filter(status="published", customfields__has_key=PROFILE_KEY)
    if not include_national:
        queryset = queryset.exclude(customfields__has_key=NATIONAL_KEY)
    return queryset.select_related("organization")


def national_dataset():
    return Dataset.objects.filter(customfields__has_key=NATIONAL_KEY, status="published").first()


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
            dataset, AedCsv.to_csv(records), "Defibrylatory AED – %s (CSV)" % self.organization.title, description
        )
        return dataset

    def dataset_for(self, license_code, national=False):
        queryset = Dataset.objects.filter(organization=self.organization, customfields__has_key=PROFILE_KEY)
        if national:
            dataset = queryset.filter(customfields__has_key=NATIONAL_KEY).first()
        else:
            dataset = queryset.exclude(customfields__has_key=NATIONAL_KEY).first()
        if dataset is None:
            return self._create_dataset(license_code, national)
        if dataset.license_chosen != license_code:
            dataset.license_chosen = license_code
            dataset.save()
        return dataset

    def _create_dataset(self, license_code, national):
        custom = {PROFILE_KEY: PROFILE_VERSION}
        if national:
            custom[NATIONAL_KEY] = "tak"
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
            customfields=custom,
            created_by=self.user,
            modified_by=self.user,
        )
        dataset.categories.add(category)
        dataset.tags.add(*self.aed_tags())
        return dataset

    def _describe(self, national):
        if national:
            return (
                "Defibrylatory AED w Polsce – zbiór ogólnopolski",
                "Ogólnopolski zbiór lokalizacji i dostępności automatycznych defibrylatorów zewnętrznych (AED), "
                "zestawiany automatycznie ze zbiorów instytucji publikowanych według wzorcowego zakresu danych AED %s. "
                "Akcja „Naładuj mapę Polski.”" % PROFILE_VERSION,
            )
        title = self.organization.title
        return (
            "Defibrylatory AED – %s" % title,
            "Lokalizacje i dostępność defibrylatorów AED udostępnione przez: %s, według wzorcowego zakresu danych AED %s. "
            "Dane zebrane w ramach akcji „Naładuj mapę Polski.”" % (title, PROFILE_VERSION),
        )

    def replace_resource(self, dataset, content, title, description):
        """Usuwa poprzedni zasób CSV zbioru i dodaje nowy z plikiem; portal sam waliduje i indeksuje plik."""
        for old in Resource.objects.filter(dataset=dataset, status="published"):
            old.delete()
        resource = Resource.objects.create(
            dataset=dataset,
            title=title,
            description=description,
            format="csv",
            type="file",
            status="published",
            data_date=datetime.date.today(),
            created_by=self.user,
            modified_by=self.user,
            show_tabular_view=True,
            tabular_data_schema=AedCsv.table_schema(content),
        )
        name = "aed-%s-%s.csv" % (dataset.pk, timezone.now().strftime("%Y%m%d%H%M%S"))
        ResourceFile.objects.create(resource=resource, is_main=True, format="csv", file=ContentFile(content, name=name))
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
