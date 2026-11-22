"""Provider tools beside the file wizard: "Dodaj jeden AED" (a phone-friendly form) and the "Zadania" inbox."""

import re

import requests
from django.contrib import admin, messages
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone

from mcod.aed.admin.base import StaffOnlyMixin, user_organizations
from mcod.aed.constants import GEOCODE_TIMEOUT_S, RecordStatus, ReportType, TaskKind, TaskStatus
from mcod.aed.geo import Boundaries
from mcod.aed.importing.address import AddressParser
from mcod.aed.importing.geocoder import GugikGeocoder
from mcod.aed.importing.mapper import normalize_value
from mcod.aed.importing.pipeline import ImportSource
from mcod.aed.models import AedRecord, AedTask
from mcod.aed.opening_hours import ALWAYS_OPEN
from mcod.aed.provider import ProviderResource
from mcod.aed.publishing import license_from_form, license_options
from mcod.aed.reminders import send_reminders
from mcod.aed.validation import RecordChecker

DAY_SPANS = {"everyday": "Mo-Su", "workdays": "Mo-Fr", "monsat": "Mo-Sa"}
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
SUGGESTIONS = 8
SINGLE_SOURCE = "Formularz „Dodaj jeden AED”, %s"
DATE_FIELDS = ("data_ostatniego_przegladu", "data_waznosci_elektrod", "data_waznosci_baterii")
TEXT_FIELDS = ("nazwa_obiektu", "opis_lokalizacji", "pietro", "ulica", "numer_budynku", "kod_pocztowy", "miejscowosc")
GROUP_PREVIEW = 10
LAST_MAIL_KEY = "aed:lastmail:%s"
LAST_MAIL_TTL_S = 600
REVERSE_URL = "https://services.gugik.gov.pl/uug/"


WEEK = (
    ("Mo", "Pn", "Poniedziałek"),
    ("Tu", "Wt", "Wtorek"),
    ("We", "Śr", "Środa"),
    ("Th", "Cz", "Czwartek"),
    ("Fr", "Pt", "Piątek"),
    ("Sa", "Sb", "Sobota"),
    ("Su", "Nd", "Niedziela"),
)
DEFAULT_DAYS = ("Mo", "Tu", "We", "Th", "Fr")
DEFAULT_FROM, DEFAULT_TO = "08:00", "16:00"


def _times(start, end):
    start, end = (start or "").strip(), (end or "").strip()
    return (start, end) if TIME.match(start) and TIME.match(end) and start != end else None


def _group(ranges):
    """[("Mo", "08:00", "16:00"), ...] -> "Mo-Fr 08:00-16:00; Sa 09:00-14:00" (consecutive days with equal hours merge)."""
    codes = [code for code, _, _ in WEEK]
    groups = []
    for code, start, end in ranges:
        last = groups[-1] if groups else None
        if last and last["hours"] == (start, end) and codes.index(code) == codes.index(last["to"]) + 1:
            last["to"] = code
        else:
            groups.append({"from": code, "to": code, "hours": (start, end)})
    return "; ".join(
        "%s %s-%s" % (g["from"] if g["from"] == g["to"] else "%s-%s" % (g["from"], g["to"]), *g["hours"]) for g in groups
    )


def hours_spec(values):
    """ "24/7", or the chosen days with their hours; "" when a chosen day has no valid range."""
    if values.get("hours_mode") == "always":
        return ALWAYS_OPEN
    if values.get("hours_days") in DAY_SPANS:
        times = _times(values.get("hours_from"), values.get("hours_to"))
        return "%s %s-%s" % (DAY_SPANS[values["hours_days"]], *times) if times else ""
    days = values.getlist("hours_day") if hasattr(values, "getlist") else values.get("hours_day", [])
    per_day = bool(values.get("hours_per_day"))
    ranges = []
    for code, _, _ in WEEK:
        if code not in days:
            continue
        times = _times(values.get("from_" + code), values.get("to_" + code)) if per_day else None
        times = times or (None if per_day else _times(values.get("hours_from"), values.get("hours_to")))
        if times is None:
            return ""
        ranges.append((code,) + times)
    return _group(ranges)


def week_rows(values, days):
    return [
        {
            "code": code,
            "short": short,
            "name": name,
            "on": code in days,
            "start": values.get("from_" + code) or values.get("hours_from") or DEFAULT_FROM,
            "end": values.get("to_" + code) or values.get("hours_to") or DEFAULT_TO,
        }
        for code, short, name in WEEK
    ]


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
            path("remind/", view(self.remind_view), name="aed_task_remind"),
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
            last_mail=cache.get(LAST_MAIL_KEY % request.user.pk),
        )

    def remind_view(self, request):
        if request.method == "POST":
            sent = send_reminders(user_organizations(request.user), only_new=False)
            if sent:
                cache.set(LAST_MAIL_KEY % request.user.pk, sent, LAST_MAIL_TTL_S)
                messages.success(request, "Wysłano przypomnienie e-mail (%d) do osób z Twojej instytucji." % len(sent))
            else:
                messages.info(request, "Brak otwartych zadań albo adresów e-mail – nic nie wysłano.")
        return redirect("admin:aed_aedtask_changelist")

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
        if request.method == "POST":
            values, days = request.POST.dict(), request.POST.getlist("hours_day")
            organization = organizations.filter(pk=values.get("organization")).first()
            record, errors = self._single_record(organization, values, request.POST)
            if not errors:
                ProviderResource(organization, request.user).upsert(record, license_from_form(values.get("license", "")))
                return self.render(request, "single_done", title="Dodaj jeden AED", record=record, organization=organization)
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
        )

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
        """Address suggestions while typing (GUGiK): each one fills the address fields and moves the pin."""
        query = (request.GET.get("q") or "").strip()
        if len(query) < 3:
            return JsonResponse({"results": []})
        geocoder = GugikGeocoder(cache=cache, timeout=GEOCODE_TIMEOUT_S * 2)
        near = self._home_teryt(request)
        found = sorted(self._candidates(geocoder, query), key=lambda f: -self._closeness(f.get("teryt", ""), near))
        results, seen = [], set()
        for item in found:
            result = self._suggestion(item)
            if result["label"] not in seen:
                seen.add(result["label"])
                results.append(result)
        return JsonResponse({"results": results[:SUGGESTIONS]})

    @staticmethod
    def _suggestion(found):
        feature, street, _ = AddressParser.split_street(found["street"])
        place = " ".join(x for x in (feature, street, found["number"]) if x).strip()
        area = found.get("area") or []
        context = "%s, %s" % (area[3], area[1]) if len(area) >= 4 else ""
        kind = "address" if found["number"] else ("street" if street else "place")
        label = ", ".join(x for x in (place, found["city"]) if x)
        return {
            "label": label + (" (gm. %s)" % context if context and kind != "address" else ""),
            "kind": kind,
            "ulica": " ".join(x for x in (feature, street) if x) if found["street"] else "",
            "numer_budynku": found["number"],
            "kod_pocztowy": found.get("code", ""),
            "miejscowosc": found["city"],
            "lat": float(found["lat"]),
            "lon": float(found["lon"]),
            "exact": bool(found["number"]),
        }

    @staticmethod
    def _home_teryt(request):
        organization = user_organizations(request.user).first()
        return ImportSource.for_organization(organization, "", "").teryt if organization else ""

    @staticmethod
    def _closeness(teryt, near):
        """Shared TERYT prefix: same municipality, county, voivodeship first."""
        return next((n for n in (6, 4, 2) if near and teryt[:n] == near[:n]), 0)

    @staticmethod
    def _candidates(geocoder, query):
        """GUGiK expects "city, street number"; people also type "street number, city"."""
        parts = [p.strip() for p in query.split(",") if p.strip()]
        queries = [query] + ([", ".join(reversed(parts))] if len(parts) == 2 else [])
        for candidate_query in queries:
            found = geocoder.candidates(candidate_query)
            if found:
                return found
        return []

    def locate_view(self, request):
        """Address of the point from the phone's location (GUGiK reverse geocoding), to prefill the form."""
        try:
            lat, lon = float(request.GET["lat"]), float(request.GET["lon"])
        except (KeyError, ValueError):
            return JsonResponse({"error": "Brak lokalizacji"}, status=400)
        params = {"request": "GetAddressReverse", "location": "POINT(%f %f)" % (lon, lat), "srid": "4326"}
        try:
            found = (requests.get(REVERSE_URL, params=params, timeout=GEOCODE_TIMEOUT_S * 2).json().get("results") or {}).get("1")
        except (requests.RequestException, ValueError):
            found = None
        if not found:
            return JsonResponse({})
        return JsonResponse(
            {
                "ulica": found.get("street") or "",
                "numer_budynku": found.get("number") or "",
                "kod_pocztowy": found.get("code") or "",
                "miejscowosc": found.get("city") or "",
            }
        )
