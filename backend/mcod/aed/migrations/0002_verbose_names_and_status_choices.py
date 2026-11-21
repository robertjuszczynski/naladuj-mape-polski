import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aed", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="aedupload",
            options={"ordering": ("-created",), "verbose_name": "wgrany plik AED", "verbose_name_plural": "wgrane pliki AED"},
        ),
        migrations.AlterField(
            model_name="aedrecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("gotowy", "Gotowy"),
                    ("niepelny", "Niepełny"),
                    ("do_decyzji", "Do decyzji"),
                    ("do_poprawy", "Do poprawy"),
                    ("wstrzymany", "Wstrzymany"),
                ],
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AlterField(
            model_name="aedupload",
            name="header",
            field=django.contrib.postgres.fields.jsonb.JSONField(default=list, verbose_name="Nagłówek pliku"),
        ),
        migrations.AlterField(
            model_name="aedupload",
            name="rows",
            field=django.contrib.postgres.fields.jsonb.JSONField(default=list, verbose_name="Wiersze pliku"),
        ),
        migrations.AlterField(
            model_name="aedupload",
            name="repairs",
            field=django.contrib.postgres.fields.jsonb.JSONField(default=list, verbose_name="Naprawy pliku"),
        ),
        migrations.AlterField(
            model_name="aedupload",
            name="mapping",
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict, verbose_name="Dopasowanie kolumn"),
        ),
        migrations.AlterField(
            model_name="aedupload",
            name="checked",
            field=django.contrib.postgres.fields.jsonb.JSONField(default=list, verbose_name="Wynik sprawdzenia"),
        ),
        migrations.AlterField(
            model_name="aedupload",
            name="decisions",
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict, verbose_name="Decyzje instytucji"),
        ),
    ]
