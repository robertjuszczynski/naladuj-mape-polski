from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("aed", "0006_sources_and_consents")]

    operations = [
        migrations.AddField(
            model_name="aedlead",
            name="review",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Do potwierdzenia"),
                    ("confirmed", "Potwierdzony – dodany do wykazu"),
                    ("not_ours", "Nie nasz – inny dysponent"),
                    ("gone", "Nie ma go na miejscu"),
                ],
                default="",
                max_length=20,
                verbose_name="Ocena gminy",
            ),
        ),
        migrations.AddField(
            model_name="aedlead",
            name="review_note",
            field=models.CharField(blank=True, max_length=500, verbose_name="Uwagi gminy"),
        ),
    ]
