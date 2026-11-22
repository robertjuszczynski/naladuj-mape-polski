from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone

from mcod.aed.constants import (
    ConsentStatus,
    LeadReview,
    RecordStatus,
    SourceLicence,
    SourceParser,
    TaskKind,
    TaskStatus,
    UploadStatus,
)
from mcod.aed.review import UploadReview
from mcod.aed.validation import coordinates


class AedRecord(models.Model):
    """Aggregated AED registry entry, rebuilt from provider resources flagged as the AED register."""

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
    verified = models.BooleanField("Potwierdzony przez dysponenta", default=True)
    updated = models.DateTimeField("Aktualizacja", auto_now=True)

    class Meta:
        verbose_name = "Defibrylator AED (rejestr zbiorczy)"
        verbose_name_plural = "Defibrylatory AED (rejestr zbiorczy)"
        ordering = ("miejscowosc", "nazwa_obiektu")

    def __str__(self):
        return "%s – %s" % (self.id_aed, self.nazwa_obiektu)

    @classmethod
    def from_result(cls, dataset, resource, result):
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
    """A session of the "Dodaj dane o AED" wizard in the data provider panel."""

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
    license = models.CharField("Licencja", max_length=20, blank=True)
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
        self.status, self.license, self.dataset, self.published = UploadStatus.PUBLISHED, license_name, dataset, timezone.now()


class AggregatedAedInfo(models.Model):
    """The main AED register, like AggregatedDGAInfo: the merged resource and a report of every source read."""

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Ostatnie scalenie", auto_now=True)
    dataset = models.ForeignKey(
        "datasets.Dataset", on_delete=models.SET_NULL, null=True, related_name="+", verbose_name="Zbiór wykazu zbiorczego"
    )
    resource = models.ForeignKey(
        "resources.Resource", on_delete=models.SET_NULL, null=True, related_name="+", verbose_name="Zasób wykazu zbiorczego"
    )
    sources = JSONField("Źródła", default=list)
    conflicts = JSONField("Sprzeczne dane między źródłami", default=list)

    class Meta:
        verbose_name = "wykaz zbiorczy AED"
        verbose_name_plural = "wykaz zbiorczy AED"

    def __str__(self):
        return "Wykaz zbiorczy AED (%s)" % timezone.localtime(self.updated_at).strftime("%Y-%m-%d %H:%M")

    @classmethod
    def current(cls):
        return cls.objects.order_by("-pk").first()

    @property
    def main_dataset(self):
        dataset = self.dataset
        return dataset if dataset is not None and dataset.status == "published" and not dataset.is_removed else None


class AedTask(models.Model):
    """Something a provider should do about one of its AEDs: a due date, missing data or a citizen report."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="aed_tasks", verbose_name="Instytucja"
    )
    id_aed = models.CharField("Identyfikator AED", max_length=120, db_index=True)
    aed_name = models.CharField("AED", max_length=500, blank=True)
    kind = models.CharField("Rodzaj", max_length=20, choices=TaskKind.CHOICES)
    due_date = models.DateField("Termin", null=True, blank=True)
    report_type = models.CharField("Typ zgłoszenia", max_length=20, blank=True)
    comment = models.TextField("Opis", blank=True)
    status = models.CharField("Stan", max_length=20, choices=TaskStatus.CHOICES, default=TaskStatus.OPEN)
    created = models.DateTimeField("Utworzono", auto_now_add=True)
    resolved = models.DateTimeField("Zamknięto", null=True, blank=True)
    notified = models.DateTimeField("Przypomnienie wysłane", null=True, blank=True)

    class Meta:
        verbose_name = "zadanie AED"
        verbose_name_plural = "zadania AED"
        ordering = ("due_date", "-created")

    def __str__(self):
        return "%s – %s" % (self.get_kind_display(), self.aed_name or self.id_aed)

    def close(self, status=TaskStatus.DONE):
        self.status, self.resolved = status, timezone.now()
        self.save(update_fields=["status", "resolved"])


class AedSource(models.Model):
    """An outside list of AEDs the portal reads on its own: a BIP file, a city website, OpenStreetMap."""

    name = models.CharField("Nazwa", max_length=300)
    publisher = models.CharField("Wydawca", max_length=300)
    url = models.URLField("Adres pliku lub usługi", max_length=1000)
    parser = models.CharField("Format", max_length=20, choices=SourceParser.CHOICES, default=SourceParser.TABLE)
    licence = models.CharField("Licencja", max_length=20, choices=SourceLicence.CHOICES)
    city = models.CharField("Miejscowość domyślna", max_length=200, blank=True, help_text="Dla list z samymi adresami ulic")
    query = models.TextField("Zapytanie Overpass", blank=True)
    active = models.BooleanField("Pobieraj co noc", default=True)
    fetched = models.DateTimeField("Ostatnie pobranie", null=True, blank=True)
    rows = models.PositiveIntegerField("Rekordów w źródle", default=0)
    published = models.PositiveIntegerField("Opublikowano", default=0)
    held = models.PositiveIntegerField("Czeka na zgodę", default=0)
    error = models.TextField("Błąd ostatniego pobrania", blank=True)

    class Meta:
        verbose_name = "źródło AED"
        verbose_name_plural = "źródła AED"
        ordering = ("name",)

    def __str__(self):
        return self.name

    @property
    def publishable(self):
        return self.licence in SourceLicence.PUBLISHABLE

    @property
    def licence_short(self):
        return SourceLicence.SHORT.get(self.licence, self.licence)


class ConsentRequest(models.Model):
    """One phone call or e-mail away from publishing: an operator (or a municipality as intermediary) with its AEDs."""

    key = models.CharField("Klucz", max_length=300, unique=True)
    label = models.CharField("Dysponent lub gmina", max_length=500)
    is_municipality = models.BooleanField("Przez gminę", default=False)
    contact = models.CharField("Kontakt", max_length=300, blank=True)
    status = models.CharField("Stan", max_length=20, choices=ConsentStatus.CHOICES, default=ConsentStatus.TO_CONTACT)
    lead_count = models.PositiveIntegerField("AED", default=0)
    notes = models.TextField("Notatki z rozmów", blank=True)
    updated = models.DateTimeField("Zmieniono", auto_now=True)

    class Meta:
        verbose_name = "prośba o zgodę"
        verbose_name_plural = "prośby o zgodę"
        ordering = ("-lead_count",)

    def __str__(self):
        return self.label


class AedLead(models.Model):
    """An AED known from a source whose licence does not allow publishing; kept internal until its owner agrees."""

    source = models.ForeignKey(AedSource, on_delete=models.CASCADE, related_name="leads", verbose_name="Źródło")
    external_id = models.CharField("Identyfikator w źródle", max_length=120)
    request = models.ForeignKey(
        ConsentRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads", verbose_name="Prośba o zgodę"
    )
    name = models.CharField("Nazwa", max_length=500, blank=True)
    operator = models.CharField("Dysponent", max_length=300, blank=True)
    lat = models.FloatField("Szerokość geograficzna")
    lon = models.FloatField("Długość geograficzna")
    kod_teryt_gminy = models.CharField("Kod TERYT gminy", max_length=7, blank=True)
    data = JSONField("Dane wg wzorcowego zakresu", default=dict)
    in_register = models.BooleanField("Już jest w wykazie", default=False)
    review = models.CharField("Ocena gminy", max_length=20, choices=LeadReview.CHOICES, blank=True, default=LeadReview.PENDING)
    review_note = models.CharField("Uwagi gminy", max_length=500, blank=True)
    updated = models.DateTimeField("Aktualizacja", auto_now=True)

    class Meta:
        verbose_name = "AED czekający na zgodę"
        verbose_name_plural = "AED czekające na zgodę"
        unique_together = (("source", "external_id"),)
