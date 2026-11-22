"""AED record validation: field formats, location (swapped coordinates, point outside the municipality), duplicates and status."""

import datetime
import re

from mcod.aed.constants import (
    BOUNDARY_TOLERANCE_M,
    DUPLICATE_COORDINATE_DECIMALS,
    QUALITY_EXAMPLES,
    IssueCode,
    RecordStatus,
    Severity,
)
from mcod.aed.field_types import type_of
from mcod.aed.geo import Boundaries, distance_to_boundary_m, in_boundary, in_poland
from mcod.aed.opening_hours import ALWAYS_OPEN, OpeningHours
from mcod.aed.profile import FIELDS

LAT, LON = "szerokosc_geograficzna", "dlugosc_geograficzna"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def issue(field, code, severity, message):
    return {"field": field, "code": code, "severity": severity, "message": message}


def to_float(value):
    try:
        return float((value or "").strip())
    except ValueError:
        return None


def coordinates(record):
    return to_float(record.get(LAT)), to_float(record.get(LON))


class RecordValidator:
    def validate(self, record):
        issues = self._personal_data(record)
        for field in FIELDS:
            value = (record.get(field.name) or "").strip()
            if not value:
                if field.required:
                    issues.append(
                        issue(field.name, IssueCode.MISSING_REQUIRED, Severity.ERROR, "Brak pola obowiązkowego: %s" % field.label)
                    )
                continue
            error = type_of(field).error(value, field)
            if error:
                issues.append(issue(field.name, IssueCode.BAD_FORMAT, Severity.ERROR, "%s: %s" % (field.label, error)))
        if record.get("dostepny_calodobowo") == "false" and not (record.get("godziny_dostepnosci") or "").strip():
            issues.append(
                issue(
                    "godziny_dostepnosci",
                    IssueCode.MISSING_HOURS,
                    Severity.WARNING,
                    "AED nie jest dostępny całodobowo, a brak godzin dostępności – status „nie wiadomo”",
                )
            )
        return issues + self.contradictions(record)

    @staticmethod
    def contradictions(record, today=None):
        """Fields that are each valid but say opposite things about the same AED."""
        today = today or datetime.date.today()
        hours = (record.get("godziny_dostepnosci") or "").strip()
        always = record.get("dostepny_calodobowo")
        found = []
        if always == "true" and hours and hours != ALWAYS_OPEN:
            found.append(("godziny_dostepnosci", "„Dostępny całodobowo: tak”, a godziny to %s" % OpeningHours.to_polish(hours)))
        if always == "false" and hours == ALWAYS_OPEN:
            found.append(("dostepny_calodobowo", "„Dostępny całodobowo: nie”, a godziny to „całodobowo”"))
        inspection = (record.get("data_ostatniego_przegladu") or "").strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", inspection) and inspection > today.isoformat():
            found.append(("data_ostatniego_przegladu", "Data ostatniego przeglądu %s jest w przyszłości" % inspection))
        floor = (record.get("pietro") or "").strip()
        if record.get("wewnatrz_budynku") == "false" and floor not in ("", "0"):
            found.append(("pietro", "AED jest na zewnątrz budynku, a podano piętro %s" % floor))
        return [issue(field, IssueCode.CONFLICTING_DATA, Severity.WARNING, "Sprzeczne dane: " + text) for field, text in found]

    @staticmethod
    def _personal_data(record):
        name = next((k for k, v in record.items() if isinstance(v, str) and EMAIL.search(v)), None)
        if name is None:
            return []
        message = "Pole „%s” zawiera adres e-mail – upewnij się, że to nie dane osobowe" % name
        return [issue(name, IssueCode.PERSONAL_DATA, Severity.WARNING, message)]


class LocationCheck:
    def __init__(self, tolerance_m=BOUNDARY_TOLERANCE_M):
        self.tolerance_m = tolerance_m

    def check(self, record):
        """Returns (record, fixes, issues); the record is a copy whose coordinates may be swapped."""
        record = dict(record)
        lat, lon = coordinates(record)
        if lat is None or lon is None:
            return record, [], []
        own = Boundaries.get(record.get("kod_teryt_gminy"))
        fixes = []
        if not in_poland(lat, lon) and in_poland(lon, lat):
            fixes.append(self._swap(record, own))
            lat, lon = lon, lat
        if not in_poland(lat, lon):
            return record, fixes, [issue(LAT, IssueCode.OUTSIDE_POLAND, Severity.ERROR, "Punkt leży poza Polską")]
        if own and not in_boundary(lat, lon, own):
            return record, fixes, [self._outside_municipality(lat, lon, own)]
        return record, fixes, []

    @staticmethod
    def _swap(record, own):
        lat, lon = record[LAT], record[LON]
        fits = own is None or in_boundary(to_float(lon), to_float(lat), own)
        record[LAT], record[LON] = lon, lat
        return {
            "rule": IssueCode.SWAPPED_COORDINATES,
            "auto": fits,
            "before": "%s, %s" % (lat, lon),
            "after": "%s, %s" % (lon, lat),
            "message": (
                "Szerokość i długość geograficzna były zamienione miejscami – po zamianie punkt leży w gminie"
                if fits
                else "Współrzędne wyglądają na zamienione, ale po zamianie punkt nie leży w gminie"
            ),
        }

    def _outside_municipality(self, lat, lon, own):
        distance = distance_to_boundary_m(lat, lon, own)
        if distance <= self.tolerance_m:
            message = "Punkt leży %d m poza granicą gminy %s – sprawdź lokalizację" % (distance, own["name"])
            return issue(LAT, IssueCode.NEAR_BORDER, Severity.WARNING, message)
        other = Boundaries.containing(lat, lon, exclude=own)
        if other:
            message = "Punkt leży w granicach gminy %s, %d km od gminy %s" % (other["name"], distance / 1000, own["name"])
        else:
            message = "Punkt leży %.1f km poza gminą %s" % (distance / 1000, own["name"])
        return issue(LAT, IssueCode.OUTSIDE_MUNICIPALITY, Severity.ERROR, message)


class DuplicateDetector:
    def mark(self, results):
        groups = {}
        for result in results:
            lat, lon = coordinates(result["record"])
            if lat is not None and lon is not None:
                key = "%.*f,%.*f" % (DUPLICATE_COORDINATE_DECIMALS, lat, DUPLICATE_COORDINATE_DECIMALS, lon)
                groups.setdefault(key, []).append(result)
        for group in groups.values():
            if len(group) < 2:
                continue
            ids = ", ".join(g["record"].get("id_aed", "") for g in group)
            message = "Te same współrzędne ma %d rekordów: %s" % (len(group), ids)
            for result in group:
                result["issues"].append(issue(LAT, IssueCode.DUPLICATE_POINT, Severity.WARNING, message))


class StatusResolver:
    BLOCKING_CODES = (IssueCode.OUTSIDE_POLAND, IssueCode.OUTSIDE_MUNICIPALITY)
    KEY_FIELDS = (LAT, LON, "nazwa_obiektu")

    def resolve(self, fixes, issues):
        errors = [i for i in issues if i["severity"] == Severity.ERROR]
        if any(i["code"] in self.BLOCKING_CODES for i in errors) or any(not f["auto"] for f in fixes):
            return RecordStatus.HELD
        if any(i["code"] != IssueCode.MISSING_REQUIRED or i["field"] in self.KEY_FIELDS for i in errors):
            return RecordStatus.NEEDS_FIX
        if any(i["code"] == IssueCode.DUPLICATE_POINT for i in issues):
            return RecordStatus.NEEDS_DECISION
        if errors:
            return RecordStatus.INCOMPLETE
        return RecordStatus.READY


class RecordChecker:
    """Full check of a batch of records. Result: list of {record, fixes, issues, status, notes}."""

    def __init__(self):
        self.location = LocationCheck()
        self.validator = RecordValidator()
        self.duplicates = DuplicateDetector()
        self.statuses = StatusResolver()

    def check_all(self, records, notes=None):
        notes = notes or [[] for _ in records]
        results = []
        for record, record_notes in zip(records, notes):
            record, fixes, issues = self.location.check(record)
            issues.extend(self.validator.validate(record))
            results.append({"record": record, "fixes": fixes, "issues": issues, "notes": list(record_notes)})
        self.duplicates.mark(results)
        for result in results:
            result["status"] = self.statuses.resolve(result["fixes"], result["issues"])
        return results


class PortalQualityCheck:
    """Portal quality rules (mirrored from mcod/templates/painless) for the data standard columns."""

    def run(self, records):
        out = []
        for field in FIELDS:
            field_type = type_of(field)
            if field_type.portal_rule:
                out.append(self._check_column(field, field_type, records))
        return out

    @staticmethod
    def _check_column(field, field_type, records):
        rule = field_type.portal_rule
        result = {
            "field": field.name,
            "rule": rule.code,
            "label": rule.label,
            "checked": 0,
            "empty": 0,
            "errors": 0,
            "examples": [],
        }
        for row_number, record in enumerate(records, start=1):
            value = (record.get(field.name) or "").strip()
            if not value:
                result["empty"] += 1
                continue
            result["checked"] += 1
            if not field_type.portal_valid(value):
                result["errors"] += 1
                if len(result["examples"]) < QUALITY_EXAMPLES:
                    result["examples"].append({"row": row_number, "value": value})
        return result
