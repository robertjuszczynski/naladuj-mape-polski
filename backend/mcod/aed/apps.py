from django.apps import AppConfig


class AedConfig(AppConfig):
    name = "mcod.aed"
    verbose_name = "Defibrylatory AED – Naładuj mapę Polski"

    def ready(self):
        from mcod.aed import signals  # noqa: F401
