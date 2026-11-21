from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone

from mcod.aed.constants import RecordStatus, UploadStatus
from mcod.aed.review import UploadReview
from mcod.aed.validation import coordinates


class AedRecord(models.Model):
    """Rekord zbiorczego rejestru AED, odbudowywany ze zbiorów instytucji oznaczonych profilem AED."""

    id_aed = models.CharField("Identyfikator AED", max_length=120, unique=True)
    dataset = models.ForeignKey(
        "datasets.Dataset", on_delete=models.CASCADE, related_name="aed_records", verbose_name="Zbiór instytucji"
    )
    resource = models.ForeignKey(
        "resources.Resource", on_delete=models.SET_NULL, null=True, blank=True, related_name="aed_records", verbose_name="Zasób"
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="aed_records", verbose_name="Instytucja"
    )
    nazwa_obiektu = models.CharField("Nazwa obiektu", max_length=500, blank=True)
    miejscowosc = models.CharField("Miejscowość", max_length=200, blank=True)
    kod_teryt_gminy = models.CharField("Kod TERYT gminy", max_length=7, blank=True)
    lat = models.FloatField("Szerokość geograficzna", null=True)
    lon = models.FloatField("Długość geograficzna", null=True)
    data = JSONField("Dane wg wzorcowego zakresu", default=dict)
    fixes = JSONField("Poprawki automatyczne", default=list)
    issues = JSONField("Uwagi walidacji", default=list)
    status = models.CharField("Status", max_length=20, choices=RecordStatus.CHOICES)
    updated = models.DateTimeField("Aktualizacja", auto_now=True)

    class Meta:
        verbose_name = "Defibrylator AED (rejestr zbiorczy)"
        verbose_name_plural = "Defibrylatory AED (rejestr zbiorczy)"
        ordering = ("miejscowosc", "nazwa_obiektu")

    def __str__(self):
        return "%s – %s" % (self.id_aed, self.nazwa_obiektu)

    @classmethod
    def from_result(cls, dataset, resource, result):
        """Rekord rejestru z wyniku sprawdzenia {record, fixes, issues, status}."""
        record = result["record"]
        lat, lon = coordinates(record)
        return cls(
            id_aed=record["id_aed"],
            dataset=dataset,
            resource=resource,
            organization_id=dataset.organization_id,
            nazwa_obiektu=cls._fit("nazwa_obiektu", record),
            miejscowosc=cls._fit("miejscowosc", record),
            kod_teryt_gminy=cls._fit("kod_teryt_gminy", record),
            lat=lat,
            lon=lon,
            data=record,
            fixes=result["fixes"],
            issues=result["issues"],
            status=result["status"],
        )

    @classmethod
    def _fit(cls, name, record):
        return (record.get(name) or "")[: cls._meta.get_field(name).max_length]


class AedUpload(models.Model):
    """Sesja kreatora „Dodaj dane o AED” w panelu dostawcy danych."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="aed_uploads", verbose_name="Użytkownik"
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="aed_uploads", verbose_name="Instytucja"
    )
    filename = models.CharField("Plik", max_length=300)
    header = JSONField("Nagłówek pliku", default=list)
    rows = JSONField("Wiersze pliku", default=list)
    repairs = JSONField("Naprawy pliku", default=list)
    mapping = JSONField("Dopasowanie kolumn", default=dict)
    checked = JSONField("Wynik sprawdzenia", default=list)
    decisions = JSONField("Decyzje instytucji", default=dict)
    licencja = models.CharField("Licencja", max_length=20, blank=True)
    status = models.CharField("Status", max_length=20, choices=UploadStatus.CHOICES, default=UploadStatus.DRAFT)
    dataset = models.ForeignKey("datasets.Dataset", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Zbiór")
    created = models.DateTimeField("Utworzono", auto_now_add=True)
    published = models.DateTimeField("Opublikowano", null=True, blank=True)

    class Meta:
        verbose_name = "wgrany plik AED"
        verbose_name_plural = "wgrane pliki AED"
        ordering = ("-created",)

    def __str__(self):
        return "%s (%s)" % (self.filename, self.organization)

    @property
    def is_published(self):
        return self.status == UploadStatus.PUBLISHED

    @property
    def review(self):
        return UploadReview(self.checked, self.decisions, self.organization.title)

    def run_import(self, pipeline, mapping):
        self.mapping = mapping
        self.checked = pipeline.run(self.header, self.rows, mapping)
        self.decisions = {}

    def rows_for_publish(self):
        return self.review.rows_for_publish()

    def foreign_operator_rows(self):
        return self.review.foreign_operator_rows()

    def summary(self):
        return self.review.summary()

    def apply_decision(self, index, action, values=None):
        return self.review.apply_decision(index, action, values)

    def mark_published(self, dataset, license_name):
        self.status, self.licencja, self.dataset, self.published = UploadStatus.PUBLISHED, license_name, dataset, timezone.now()
