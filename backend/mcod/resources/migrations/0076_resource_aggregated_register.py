from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0075_add_performance_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="resource",
            name="aggregated_register",
            field=models.CharField(
                blank=True,
                choices=[("aed", "Wykaz defibrylatorów AED")],
                default="",
                help_text=(
                    "Zasób oznaczony jako wykaz jest co noc odczytywany, dopasowywany do wzorcowego zakresu danych "
                    "i scalany z zasobami innych dostawców w jeden wykaz zbiorczy. Kolumny nie muszą mieć nazw ze wzoru."
                ),
                max_length=32,
                verbose_name="Wykaz zbiorczy",
            ),
        ),
        migrations.AddIndex(
            model_name="resource",
            index=models.Index(fields=["aggregated_register"], name="resource_aggr_register_idx"),
        ),
    ]
