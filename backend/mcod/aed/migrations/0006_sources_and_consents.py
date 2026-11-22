import django.contrib.postgres.fields.jsonb
import django.db.models.deletion
from django.db import migrations, models

OSM_QUERY = """[out:json][timeout:180];
area["ISO3166-1"="PL"][admin_level=2]->.pl;
node["emergency"="defibrillator"](area.pl);
out body;"""

SOURCES = (
    {
        "name": "Kraków – wykaz AED (program „AED Impuls Życia”)",
        "publisher": "Urząd Miasta Krakowa",
        "url": "https://www.bip.krakow.pl/plik.php?zid=671911&wer=0&new=t&mode=shw",
        "parser": "pdf",
        "licence": "public_info",
        "city": "Kraków",
    },
    {
        "name": "OpenStreetMap – defibrylatory w Polsce",
        "publisher": "Współtwórcy OpenStreetMap",
        "url": "https://overpass-api.de/api/interpreter",
        "parser": "overpass",
        "licence": "odbl",
        "query": OSM_QUERY,
    },
)


def add_sources(apps, schema_editor):
    AedSource = apps.get_model("aed", "AedSource")
    for source in SOURCES:
        AedSource.objects.get_or_create(url=source["url"], defaults=source)


class Migration(migrations.Migration):

    dependencies = [("aed", "0005_aedtask")]

    operations = [
        migrations.AddField(
            model_name="aedrecord",
            name="verified",
            field=models.BooleanField(default=True, verbose_name="Potwierdzony przez dysponenta"),
        ),
        migrations.CreateModel(
            name="AedSource",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=300, verbose_name="Nazwa")),
                ("publisher", models.CharField(max_length=300, verbose_name="Wydawca")),
                ("url", models.URLField(max_length=1000, verbose_name="Adres pliku lub usługi")),
                (
                    "parser",
                    models.CharField(
                        choices=[
                            ("table", "Plik CSV lub XLSX"),
                            ("pdf", "Tabela w PDF"),
                            ("overpass", "OpenStreetMap (Overpass)"),
                        ],
                        default="table",
                        max_length=20,
                        verbose_name="Format",
                    ),
                ),
                (
                    "licence",
                    models.CharField(
                        choices=[
                            ("cc0", "CC0 – można publikować"),
                            ("cc_by", "CC BY – można publikować z podaniem autora"),
                            ("public_info", "Informacja publiczna (BIP) – można publikować z podaniem źródła"),
                            ("odbl", "ODbL (OpenStreetMap) – tylko wewnętrznie, do pozyskania zgody"),
                            ("none", "Brak licencji – tylko wewnętrznie, do pozyskania zgody"),
                        ],
                        max_length=20,
                        verbose_name="Licencja",
                    ),
                ),
                (
                    "city",
                    models.CharField(
                        blank=True,
                        help_text="Dla list z samymi adresami ulic",
                        max_length=200,
                        verbose_name="Miejscowość domyślna",
                    ),
                ),
                ("query", models.TextField(blank=True, verbose_name="Zapytanie Overpass")),
                ("active", models.BooleanField(default=True, verbose_name="Pobieraj co noc")),
                ("fetched", models.DateTimeField(blank=True, null=True, verbose_name="Ostatnie pobranie")),
                ("rows", models.PositiveIntegerField(default=0, verbose_name="Rekordów w źródle")),
                ("published", models.PositiveIntegerField(default=0, verbose_name="Opublikowano")),
                ("held", models.PositiveIntegerField(default=0, verbose_name="Czeka na zgodę")),
                ("error", models.TextField(blank=True, verbose_name="Błąd ostatniego pobrania")),
            ],
            options={"verbose_name": "źródło AED", "verbose_name_plural": "źródła AED", "ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="ConsentRequest",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=300, unique=True, verbose_name="Klucz")),
                ("label", models.CharField(max_length=500, verbose_name="Dysponent lub gmina")),
                ("is_municipality", models.BooleanField(default=False, verbose_name="Przez gminę")),
                ("contact", models.CharField(blank=True, max_length=300, verbose_name="Kontakt")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("to_contact", "Do kontaktu"),
                            ("contacted", "Skontaktowano – czekamy"),
                            ("agreed", "Zgoda – opublikowano"),
                            ("refused", "Odmowa"),
                        ],
                        default="to_contact",
                        max_length=20,
                        verbose_name="Stan",
                    ),
                ),
                ("lead_count", models.PositiveIntegerField(default=0, verbose_name="AED")),
                ("notes", models.TextField(blank=True, verbose_name="Notatki z rozmów")),
                ("updated", models.DateTimeField(auto_now=True, verbose_name="Zmieniono")),
            ],
            options={"verbose_name": "prośba o zgodę", "verbose_name_plural": "prośby o zgodę", "ordering": ("-lead_count",)},
        ),
        migrations.CreateModel(
            name="AedLead",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(max_length=120, verbose_name="Identyfikator w źródle")),
                ("name", models.CharField(blank=True, max_length=500, verbose_name="Nazwa")),
                ("operator", models.CharField(blank=True, max_length=300, verbose_name="Dysponent")),
                ("lat", models.FloatField(verbose_name="Szerokość geograficzna")),
                ("lon", models.FloatField(verbose_name="Długość geograficzna")),
                ("kod_teryt_gminy", models.CharField(blank=True, max_length=7, verbose_name="Kod TERYT gminy")),
                ("data", django.contrib.postgres.fields.jsonb.JSONField(default=dict, verbose_name="Dane wg wzorcowego zakresu")),
                ("in_register", models.BooleanField(default=False, verbose_name="Już jest w wykazie")),
                ("updated", models.DateTimeField(auto_now=True, verbose_name="Aktualizacja")),
                (
                    "request",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="leads",
                        to="aed.ConsentRequest",
                        verbose_name="Prośba o zgodę",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="leads",
                        to="aed.AedSource",
                        verbose_name="Źródło",
                    ),
                ),
            ],
            options={
                "verbose_name": "AED czekający na zgodę",
                "verbose_name_plural": "AED czekające na zgodę",
                "unique_together": {("source", "external_id")},
            },
        ),
        migrations.RunPython(add_sources, migrations.RunPython.noop),
    ]
