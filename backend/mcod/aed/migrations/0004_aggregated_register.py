"""AED datasets were recognised by dataset customfields and tags; the register now reads resources flagged with
Resource.aggregated_register, so existing AED resources get the flag and the national dataset becomes the main register."""

import django.contrib.postgres.fields.jsonb
import django.db.models.deletion
from django.db import migrations, models

PROFILE_KEY = "aed_profile"
NATIONAL_KEY = "aed_national_dataset"
TAG_NAMES = ("aed", "defibrylator", "defibrylatory", "defibrylatory aed")
REGISTER = "aed"
MAIN_TITLE = "Defibrylatory AED w Polsce – wykaz zbiorczy"


def to_register(apps, schema_editor):
    Dataset = apps.get_model("datasets", "Dataset")
    Resource = apps.get_model("resources", "Resource")
    AggregatedAedInfo = apps.get_model("aed", "AggregatedAedInfo")
    live = {"status": "published", "is_removed": False}
    national = Dataset.objects.filter(customfields__has_key=NATIONAL_KEY, **live).first()
    providers = Dataset.objects.filter(customfields__has_key=PROFILE_KEY, **live) | Dataset.objects.filter(
        tags__name__iregex=r"^(%s)$" % "|".join(TAG_NAMES), **live
    )
    if national is not None:
        providers = providers.exclude(pk=national.pk)
    Resource.objects.filter(dataset__in=providers.distinct(), **live).update(aggregated_register=REGISTER)
    if national is not None:
        Dataset.objects.filter(pk=national.pk).update(title=MAIN_TITLE)
        main = Resource.objects.filter(dataset=national, **live).order_by("-created").first()
        AggregatedAedInfo.objects.create(dataset=national, resource=main)


def from_register(apps, schema_editor):
    Resource = apps.get_model("resources", "Resource")
    Resource.objects.filter(aggregated_register=REGISTER).update(aggregated_register="")


class Migration(migrations.Migration):

    dependencies = [
        ("aed", "0003_english_codes"),
        ("datasets", "0046_auto_20260907_1051"),
        ("resources", "0076_resource_aggregated_register"),
    ]

    operations = [
        migrations.CreateModel(
            name="AggregatedAedInfo",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Utworzono")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Ostatnie scalenie")),
                ("sources", django.contrib.postgres.fields.jsonb.JSONField(default=list, verbose_name="Źródła")),
                (
                    "dataset",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="datasets.Dataset",
                        verbose_name="Zbiór wykazu zbiorczego",
                    ),
                ),
                (
                    "resource",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="resources.Resource",
                        verbose_name="Zasób wykazu zbiorczego",
                    ),
                ),
            ],
            options={"verbose_name": "wykaz zbiorczy AED", "verbose_name_plural": "wykaz zbiorczy AED"},
        ),
        migrations.RunPython(to_register, from_register),
    ]
