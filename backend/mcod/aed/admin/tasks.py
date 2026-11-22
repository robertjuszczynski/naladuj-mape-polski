"""Provider tools beside the file wizard: "Dodaj jeden AED" (a phone-friendly form) and the "Do sprawdzenia" list."""

from django.contrib import admin, messages
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone

from mcod.aed.address_search import AddressSuggestions
from mcod.aed.admin.base import StaffOnlyMixin, user_organizations
from mcod.aed.admin.territory import confirm, lead_for
from mcod.aed.constants import GEOCODE_TIMEOUT_S, RecordStatus, ReportType, TaskKind, TaskStatus
from mcod.aed.geo import Boundaries
from mcod.aed.hours import DEFAULT_DAYS, DEFAULT_FROM, DEFAULT_TO, form_values, hours_spec, week_rows
from mcod.aed.importing.address import AddressParser
from mcod.aed.importing.geocoder import GugikGeocoder
from mcod.aed.importing.mapper import normalize_value
from mcod.aed.importing.pipeline import ImportSource
from mcod.aed.models import AedRecord, AedTask
from mcod.aed.opening_hours import ALWAYS_OPEN
from mcod.aed.provider import ProviderResource
from mcod.aed.publishing import is_public_institution, license_from_form, license_options
from mcod.aed.validation import RecordChecker

SINGLE_SOURCE = "Formularz „Dodaj jeden AED”, %s"
DATE_FIELDS = ("data_ostatniego_przegladu", "data_waznosci_elektrod", "data_waznosci_baterii")
TEXT_FIELDS = ("nazwa_obiektu", "opis_lokalizacji", "pietro", "ulica", "numer_budynku", "kod_pocztowy", "miejscowosc")
GROUP_PREVIEW = 10


def set_hours(record, values):
    record["godziny_dostepnosci"] = spec = hours_spec(values)
    record["dostepny_calodobowo"] = "true" if spec == ALWAYS_OPEN else "false"


@admin.register(AedTask)
class AedTaskAdmin(StaffOnlyMixin, admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path("single/", view(self.single_view), name="aed_single"),
            path("single/locate/", view(self.locate_view), name="aed_locate"),
            path("single/search/", view(self.search_view), name="aed_search"),
            path("<int:pk>/resolve/", view(self.resolve_view), name="aed_task_resolve"),
        ] + super().get_urls()

    def render(self, request, template, **context):
        base = dict(self.admin_site.each_context(request), opts=self.model._meta)
        return render(request, "admin/aed/%s.html" % template, dict(base, **context))

    # Zadania

    def changelist_view(self, request, extra_context=None):
        tasks = self.get_queryset(request).filter(status=TaskStatus.OPEN).select_related("organization")
        kind = request.GET.get("kind", "")
        groups = []
        for code, label in TaskKind.CHOICES:
            items = tasks.filter(kind=code)
            count = items.count()
            if count and (not kind or kind == code):
                groups.append({"kind": code, "label": label, "count": count, "tasks": items if kind else items[:GROUP_PREVIEW]})
        return self.render(
            request,
            "tasks",
            title="Do sprawdzenia",
            groups=groups,
            total=tasks.count(),
            kind=kind,
            preview=GROUP_PREVIEW,
            today=timezone.localdate(),
            report_labels=ReportType.LABELS,
            week=week_rows({}, DEFAULT_DAYS),
        )

    def resolve_view(self, request, pk):
        task = get_object_or_404(self.get_queryset(request), pk=pk, status=TaskStatus.OPEN)
        if request.method != "POST":
            return redirect("admin:aed_aedtask_changelist")
        action = request.POST.get("action", "")
        if action == "dismiss":
            task.close(TaskStatus.DISMISSED)
            messages.info(request, "Zgłoszenie oznaczone jako błędne.")
        else:
            record = AedRecord.objects.filter(id_aed=task.id_aed, organization=task.organization).first()
            if record is None:
                task.close(TaskStatus.DISMISSED)
                messages.warning(request, "Tego AED nie ma już w wykazie – zadanie zamknięte.")
            elif self._apply(request, task, dict(record.data), action):
                task.close()
                messages.success(request, "Zapisano. Mapa i wykaz zbiorczy odświeżą się za chwilę.")
        url = reverse("admin:aed_aedtask_changelist")
        kind = request.POST.get("kind", "")
        return redirect("%s?kind=%s" % (url, kind) if kind else url)

    def _apply(self, request, task, data, action):
        if action == "date":
            value = request.POST.get("date", "")
            if not value:
                messages.error(request, "Podaj datę.")
                return False
            data[TaskKind.DATE_FIELDS[task.kind]] = value
        elif action == "faulty":
            data["sprawny"] = "false"
        elif action in ("hours", "always"):
            set_hours(data, {"hours_mode": "always"} if action == "always" else request.POST)
            if not data["godziny_dostepnosci"]:
                messages.error(request, "Podaj godziny od i do albo wybierz „Całą dobę”.")
                return False
        elif action == "location":
            data["opis_lokalizacji"] = request.POST.get("location", "").strip()
        elif action != "confirm":
            raise Http404
        if action == "confirm" and task.report_type in (ReportType.NOT_WORKING, ReportType.MISSING):
            data["sprawny"] = "false"
        if action != "confirm" or task.report_type in (ReportType.NOT_WORKING, ReportType.MISSING):
            data["data_aktualizacji"] = timezone.localdate().isoformat()
            ProviderResource(task.organization, request.user).upsert(data)
        return True

    # Dodaj jeden AED

    def single_view(self, request):
        organizations = user_organizations(request.user)
        values = {"hours_mode": "always", "hours_from": DEFAULT_FROM, "hours_to": DEFAULT_TO, "license": "", "organization": ""}
        days = list(DEFAULT_DAYS)
        pk = request.POST.get("lead") or request.GET.get("lead")
        lead = lead_for(request.user, pk) if pk else None
        if lead and request.method != "POST":
            values, days = self._from_lead(lead, values)
        if request.method == "POST":
            values, days = request.POST.dict(), request.POST.getlist("hours_day")
            organization = organizations.filter(pk=values.get("organization")).first()
            record, errors = self._single_record(organization, values, request.POST)
            if not errors:
                ProviderResource(organization, request.user).upsert(record, license_from_form(values.get("license", "")))
                if lead:
                    confirm(lead, organization)
                return self.render(
                    request, "single_done", title="Dodaj jeden AED", record=record, organization=organization, lead=lead
                )
            for error in errors:
                messages.error(request, error)
        return self.render(
            request,
            "single",
            title="Dodaj jeden AED",
            organizations=organizations,
            values=values,
            week=week_rows(values, days),
            licenses=license_options(),
            licence_folded=is_public_institution(list(organizations)),
            lead=lead,
            lead_hours=(lead.data or {}).get("godziny_dostepnosci", "") if lead else "",
        )

    @staticmethod
    def _from_lead(lead, values):
        """Prefill from a point found in an outside source; the municipality checks it and confirms as its own data."""
        data = lead.data or {}
        values = dict(values, lead=lead.pk, lat="%.6f" % lead.lat, lon="%.6f" % lead.lon)
        values.update({name: data[name] for name in TEXT_FIELDS if data.get(name)})
        if values.get("nazwa_obiektu") == "AED":
            values["nazwa_obiektu"] = ""
        always = "24/7" if data.get("dostepny_calodobowo") == "true" else ""
        parsed = form_values(data.get("godziny_dostepnosci") or always)
        if parsed is None:
            return values, list(DEFAULT_DAYS)
        values.update(parsed[0])
        return values, parsed[1]

    @staticmethod
    def _missing(organization, values):
        checks = (
            (organization is None, "Wybierz instytucję."),
            (not values.get("consent"), "Zaznacz oświadczenie o prawie do udostępnienia danych."),
            (not (values.get("nazwa_obiektu") or "").strip(), "Podaj nazwę miejsca, np. „Urząd Miasta Marki”."),
        )
        return [message for failed, message in checks if failed]

    def _single_record(self, organization, values, form):
        errors = self._missing(organization, values)
        if errors:
            return None, errors
        today = timezone.localdate().isoformat()
        source = ImportSource.for_organization(organization, SINGLE_SOURCE % organization.title, today)
        provider = ProviderResource(organization, None)
        record = dict(source.defaults(), id_aed=provider.new_id(), sprawny="true", dostep="publiczny")
        for name in TEXT_FIELDS + DATE_FIELDS:
            if (values.get(name) or "").strip():
                record[name], _ = normalize_value(name, values[name])
        record["cecha_adresu"], record["ulica"], _ = AddressParser.split_street(record.get("ulica", ""))
        set_hours(record, form)
        if not record["godziny_dostepnosci"]:
            return None, ["Wybierz dni i podaj godziny od–do albo zaznacz „Całą dobę”."]
        if not self._place(record, values):
            return None, ["Nie mamy lokalizacji – wybierz adres z podpowiedzi albo kliknij miejsce na mapie."]
        checked = RecordChecker().check_all([record])[0]
        if checked["status"] in RecordStatus.BLOCKED:
            return None, [i["message"] for i in checked["issues"]] or ["Sprawdź lokalizację."]
        return checked["record"], []

    @staticmethod
    def _place(record, values):
        """Coordinates from the pin (or the address) and the municipality of that point, not of the institution."""
        lat, lon = (values.get("lat") or "").strip(), (values.get("lon") or "").strip()
        if not (lat and lon):
            hit = GugikGeocoder(cache=cache).geocode(GugikGeocoder.query_for(record)) or {}
            lat, lon = hit.get("lat", ""), hit.get("lon", "")
        if not (lat and lon):
            return False
        record["szerokosc_geograficzna"], _ = normalize_value("szerokosc_geograficzna", lat)
        record["dlugosc_geograficzna"], _ = normalize_value("dlugosc_geograficzna", lon)
        teryt = Boundaries.teryt_at(float(record["szerokosc_geograficzna"]), float(record["dlugosc_geograficzna"]))
        if teryt:
            record["kod_teryt_gminy"] = teryt
        return True

    def search_view(self, request):
        """Address suggestions while typing: each one fills the address fields and moves the pin."""
        geocoder = GugikGeocoder(cache=cache, timeout=GEOCODE_TIMEOUT_S * 2)
        organizations = list(user_organizations(request.user)[:5]) if not request.user.is_superuser else []
        cities = [o.city for o in organizations if o.city]
        results = AddressSuggestions(geocoder).search(request.GET.get("q"), self._home_teryt(request), cities)
        return JsonResponse({"results": results})

    @staticmethod
    def _home_teryt(request):
        organization = user_organizations(request.user).first()
        return ImportSource.for_organization(organization, "", "").teryt if organization else ""

    def locate_view(self, request):
        """Address of the point from the phone's location or the pin (GUGiK reverse geocoding), to prefill the form."""
        try:
            lat, lon = float(request.GET["lat"]), float(request.GET["lon"])
        except (KeyError, ValueError):
            return JsonResponse({"error": "Brak lokalizacji"}, status=400)
        found = GugikGeocoder(cache=cache, timeout=GEOCODE_TIMEOUT_S * 2).reverse(lat, lon)
        return JsonResponse(AddressSuggestions.suggestion(found) if found else {})
