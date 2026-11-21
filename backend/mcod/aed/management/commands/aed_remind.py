from django.core.management.base import BaseCommand

from mcod.aed.reminders import send_reminders


class Command(BaseCommand):
    help = "Wysyła dostawcom e-maile o nowych zadaniach AED (normalnie codziennie o 6:00)."

    def handle(self, *args, **options):
        self.stdout.write("Wysłano przypomnień: %d" % len(send_reminders()))
