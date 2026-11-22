import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("aed", "0007_lead_review")]

    operations = [
        migrations.AddField(
            model_name="aggregatedaedinfo",
            name="conflicts",
            field=django.contrib.postgres.fields.jsonb.JSONField(default=list, verbose_name="Sprzeczne dane między źródłami"),
        ),
    ]
