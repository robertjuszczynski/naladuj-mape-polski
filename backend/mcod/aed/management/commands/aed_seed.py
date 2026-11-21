import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from mcod.aed.constants import NATIONAL_ORG_TITLE
from mcod.aed.importing.reader import read_records
from mcod.aed.publishing import LICENSE_NAME_TO_CODE, DatasetPublisher
from mcod.aed.registry import RegistryBuilder
from mcod.aed.sources import source_file, source_meta
from mcod.organizations.models import Organization
from mcod.users.models import User

DEMO_PASSWORD_ENV = "AED_DEMO_PASSWORD"
ORGS = {
    "warszawa": {"institution_type": "local", "city": "Warszawa", "email": "aed@warszawa.example"},
    "legionowo": {"institution_type": "local", "city": "Legionowo", "email": "aed@legionowo.example"},
    "przemysl": {"institution_type": "local", "city": "Przemyśl", "email": "aed@przemysl.example"},
    "krosno": {"institution_type": "local", "city": "Krosno", "email": "aed@krosno.example"},
    "marki": {"institution_type": "local", "city": "Marki", "email": "aed@marki.example"},
}
PUBLISH_ON_SEED = ("warszawa", "legionowo", "przemysl", "krosno")


class Command(BaseCommand):
    help = "Dane demonstracyjne: instytucje z istniejącymi zbiorami AED, konta dostawców danych i ich zbiory."

    def handle(self, *args, **options):
        password = os.environ.get(DEMO_PASSWORD_ENV)
        if not password:
            raise CommandError("Ustaw hasło kont demonstracyjnych w zmiennej środowiskowej %s." % DEMO_PASSWORD_ENV)
        self.seed(password)
        self.stdout.write("Konta demonstracyjne: dzd@aed.example oraz aed@<gmina>.example (hasło z %s)" % DEMO_PASSWORD_ENV)

    @transaction.atomic
    def seed(self, password):
        admin = User.objects.filter(is_superuser=True).order_by("id").first()
        national, _ = Organization.objects.get_or_create(
            title=NATIONAL_ORG_TITLE, defaults={"institution_type": "state", "status": "published", "city": "Warszawa"}
        )
        self.provider(national, "dzd@aed.example", password, "Operator zbioru AED (DZD)")
        meta = {m["id"]: m for m in source_meta()}
        for key, extra in ORGS.items():
            source = meta[key]
            defaults = {k: v for k, v in extra.items() if k != "email"}
            organization, _ = Organization.objects.get_or_create(
                title=source["wydawca"], defaults=dict(status="published", **defaults)
            )
            user = self.provider(organization, extra["email"], password, "Dostawca danych – %s" % source["wydawca"])
            if key in PUBLISH_ON_SEED:
                with open(source_file(key), encoding="utf-8") as fp:
                    records = read_records(fp.read())
                DatasetPublisher(organization, user or admin).publish(records, LICENSE_NAME_TO_CODE[source["licencja"]])
                self.stdout.write("%s: %d AED" % (source["wydawca"], len(records)))
        RegistryBuilder.rebuild_on_commit()

    @staticmethod
    def provider(organization, email, password, fullname):
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                email,
                password,
                is_staff=True,
                state="active",
                fullname=fullname,
                phone="221234567",
                email_confirmed=timezone.now(),
            )
        user.organizations.add(organization)
        return user
