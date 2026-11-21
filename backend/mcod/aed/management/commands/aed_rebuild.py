from django.core.management.base import BaseCommand

from mcod.aed.registry import RegistryBuilder


class Command(BaseCommand):
    help = "Odbudowuje rejestr zbiorczy AED i zbiór ogólnopolski ze zbiorów instytucji."

    def handle(self, *args, **options):
        self.stdout.write("Rejestr AED: %d urządzeń" % RegistryBuilder().rebuild())
