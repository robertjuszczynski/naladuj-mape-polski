import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0025_auto_20251010_1248"),
        ("aed", "0004_aggregated_register"),
    ]

    operations = [
        migrations.CreateModel(
            name="AedTask",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("id_aed", models.CharField(db_index=True, max_length=120, verbose_name="Identyfikator AED")),
                ("aed_name", models.CharField(blank=True, max_length=500, verbose_name="AED")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("inspection", "Przegląd"),
                            ("electrodes", "Elektrody"),
                            ("battery", "Bateria"),
                            ("missing_hours", "Brak godzin dostępności"),
                            ("missing_location", "Brak opisu miejsca"),
                            ("report", "Zgłoszenie obywatela"),
                        ],
                        max_length=20,
                        verbose_name="Rodzaj",
                    ),
                ),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="Termin")),
                ("report_type", models.CharField(blank=True, max_length=20, verbose_name="Typ zgłoszenia")),
                ("comment", models.TextField(blank=True, verbose_name="Opis")),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Do zrobienia"), ("done", "Zrobione"), ("dismissed", "Odrzucone")],
                        default="open",
                        max_length=20,
                        verbose_name="Stan",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True, verbose_name="Utworzono")),
                ("resolved", models.DateTimeField(blank=True, null=True, verbose_name="Zamknięto")),
                ("notified", models.DateTimeField(blank=True, null=True, verbose_name="Przypomnienie wysłane")),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="aed_tasks",
                        to="organizations.Organization",
                        verbose_name="Instytucja",
                    ),
                ),
            ],
            options={"verbose_name": "zadanie AED", "verbose_name_plural": "zadania AED", "ordering": ("due_date", "-created")},
        ),
    ]
