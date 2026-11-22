"""Institution decisions in the wizard review step: what gets published, the summary and manual fixes."""

import re

from mcod.aed.changes import HOURS, readable, row_changes, summarize
from mcod.aed.constants import Decision, RecordStatus, Severity
from mcod.aed.hours import DEFAULT_DAYS, DEFAULT_FROM, DEFAULT_TO, form_values, hours_spec, week_rows
from mcod.aed.importing.mapper import normalize_value
from mcod.aed.opening_hours import ALWAYS_OPEN
from mcod.aed.profile import FIELDS_BY_NAME, format_address
from mcod.aed.validation import RecordChecker

EDIT_GROUPS = (
    (
        "Miejsce",
        (
            "nazwa_obiektu",
            "ulica",
            "numer_budynku",
            "numer_lokalu",
            "kod_pocztowy",
            "miejscowosc",
            "kod_teryt_gminy",
            "szerokosc_geograficzna",
            "dlugosc_geograficzna",
            "opis_lokalizacji",
            "pietro",
            "wewnatrz_budynku",
        ),
    ),
    ("Dostępność", ("dostep",)),
    (
        "Urządzenie",
        (
            "sprawny",
            "data_ostatniego_przegladu",
            "data_waznosci_elektrod",
            "data_waznosci_baterii",
            "producent",
            "model",
            "mobilny",
        ),
    ),
    ("Dysponent", ("dysponent_nazwa", "dysponent_telefon", "uwagi")),
)
EDITABLE_FIELDS = tuple(name for _, names in EDIT_GROUPS for name in names)
PLACEHOLDERS = {HOURS: "pn–pt 8–16, sob. 9–14", "kod_pocztowy": "00-000", "pietro": "0 = parter"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WIDE_FIELDS = ("nazwa_obiektu", "opis_lokalizacji", "uwagi")
HOURS_FIELDS = (HOURS, "dostepny_calodobowo")
HOURS_GROUP = "Dostępność"
ROW_DECISIONS = (Decision.ACCEPT, Decision.HOLD)
HELD_BY_INSTITUTION = "wstrzymany przez instytucję"
ACCEPTED_BY_INSTITUTION = "zatwierdzony przez instytucję"
FILTER_AUTO = "auto"
FILTER_PENDING = "pending"
FILTER_BLOCKED = "blocked"


class UploadReview:
    """checked: list of {record, fixes, issues, status, notes}; decisions: {row index: decision}."""

    def __init__(self, checked, decisions, organization_title):
        self.checked = checked
        self.decisions = decisions
        self.own_operator = self._operator_key(organization_title)

    def decision(self, index):
        return self.decisions.get(str(index))

    def is_published_row(self, index, row):
        decision = self.decision(index)
        if decision == Decision.HOLD:
            return False
        if row["status"] == RecordStatus.NEEDS_DECISION:
            return decision == Decision.ACCEPT
        return row["status"] in RecordStatus.PUBLISHABLE

    def rows_for_publish(self):
        return [row["record"] for i, row in enumerate(self.checked) if self.is_published_row(i, row)]

    def foreign_operator_rows(self):
        return [record for record in self.rows_for_publish() if self.is_foreign_operator(record)]

    def is_foreign_operator(self, record):
        return self._operator_key(record.get("dysponent_nazwa")) not in ("", self.own_operator)

    def summary(self):
        out = {"publish": 0, "pending": 0, "blocked": 0}
        for i, row in enumerate(self.checked):
            out["publish"] += self.is_published_row(i, row)
            out["pending"] += self.is_pending(i, row)
            out["blocked"] += row["status"] in RecordStatus.BLOCKED
        out["changes"] = summarize(self.checked)
        return out

    def is_pending(self, index, row):
        return row["status"] == RecordStatus.NEEDS_DECISION and self.decision(index) not in ROW_DECISIONS

    def matches(self, row_filter, index, row):
        if row_filter == FILTER_AUTO:
            return bool(row_changes(row))
        if row_filter == FILTER_PENDING:
            return self.is_pending(index, row)
        if row_filter == FILTER_BLOCKED:
            return row["status"] in RecordStatus.BLOCKED
        return True

    def status_label(self, index, row):
        decision = self.decision(index)
        if decision == Decision.HOLD:
            return HELD_BY_INSTITUTION
        if decision == Decision.ACCEPT and row["status"] == RecordStatus.NEEDS_DECISION:
            return ACCEPTED_BY_INSTITUTION
        return RecordStatus.LABELS[row["status"]]

    def apply_decision(self, index, action, values=None):
        """Returns False for an invalid index or action."""
        if not 0 <= index < len(self.checked):
            return False
        key = str(index)
        if action in ROW_DECISIONS:
            self.decisions[key] = action
        elif action == Decision.RESTORE:
            self.decisions.pop(key, None)
        elif action == Decision.FIX:
            self.apply_manual_fix(index, values or {})
        else:
            return False
        return True

    def apply_manual_fix(self, index, values):
        previous = self.checked[index]
        record = dict(previous["record"])
        for name in EDITABLE_FIELDS:
            if name in values:
                record[name], _ = normalize_value(name, values[name])
        if values.get("hours_mode") in ("always", "range"):
            spec = hours_spec(values)
            if spec:
                record[HOURS] = spec
                record["dostepny_calodobowo"] = "true" if spec == ALWAYS_OPEN else "false"
        fixed = RecordChecker().check_all([record], [previous.get("notes", [])])[0]
        fixed["fixes"] = previous["fixes"] + fixed["fixes"]
        self.checked[index] = fixed

    def review_rows(self, row_filter=""):
        return [self._review_row(i, row) for i, row in enumerate(self.checked) if self.matches(row_filter, i, row)]

    def _review_row(self, index, row):
        decision = self.decision(index)
        held = decision == Decision.HOLD
        publish = self.is_published_row(index, row)
        actions = []
        if row["status"] == RecordStatus.NEEDS_DECISION and decision != Decision.ACCEPT:
            actions.append((Decision.ACCEPT, "Zatwierdź"))
        if held:
            actions.append((Decision.RESTORE, "Przywróć"))
        elif publish:
            actions.append((Decision.HOLD, "Wstrzymaj"))
        return dict(
            row,
            index=index,
            held=held,
            publish=publish,
            label=RecordStatus.LABELS[RecordStatus.HELD] if held else RecordStatus.LABELS[row["status"]],
            badge_class=RecordStatus.BADGE_CLASSES.get(row["status"], RecordStatus.DEFAULT_BADGE_CLASS),
            address=format_address(row["record"]),
            changes=row_changes(row),
            to_check=[f for f in row["fixes"] if not f["auto"]],
            issues=[dict(i, css="bad" if i["severity"] == Severity.ERROR else "warn") for i in row["issues"]],
            is_foreign_operator=self.is_foreign_operator(row["record"]),
            actions=actions,
            edit_groups=self._edit_groups(row),
        )

    @classmethod
    def _edit_groups(cls, row):
        """All fields a provider can correct, grouped; fields with a problem are marked and their group opens first."""
        flagged = {i["field"] for i in row["issues"]} | {f["field"] for f in row["fixes"] if not f["auto"] and f.get("field")}
        groups = []
        for title, names in EDIT_GROUPS:
            fields = [cls._edit_field(name, row["record"], name in flagged) for name in names]
            group = {"title": title, "fields": fields, "flagged": any(f["flagged"] for f in fields), "required": False}
            if title == HOURS_GROUP:
                group["hours"] = cls._hours(row["record"])
                group["hours_flagged"] = bool(flagged & set(HOURS_FIELDS))
                group["flagged"] = group["flagged"] or group["hours_flagged"]
                group["required"] = True
            groups.append(group)
        return sorted(groups, key=lambda g: not g["flagged"])

    @staticmethod
    def _edit_field(name, record, flagged):
        field = FIELDS_BY_NAME[name]
        return {
            "name": name,
            "label": field.label,
            "placeholder": PLACEHOLDERS.get(name, ""),
            "value": readable(name, record.get(name, "")),
            "is_boolean": field.type == "boolean",
            "is_date": field.type == "date" and bool(ISO_DATE.match(record.get(name) or "2000-01-01")),
            "choices": getattr(field, "values", None) or (),
            "wide": name in WIDE_FIELDS,
            "flagged": flagged,
            "required": field.required,
        }

    @staticmethod
    def _hours(record):
        """The hours widget prefilled from the record; specs it cannot show (e.g. a lunch break) are kept unless changed."""
        spec = record.get(HOURS) or ""
        always = record.get("dostepny_calodobowo") == "true" or spec == ALWAYS_OPEN
        parsed = form_values(ALWAYS_OPEN if always else spec)
        values, days = parsed if parsed else ({}, list(DEFAULT_DAYS))
        rows = week_rows(values, days)
        return {
            "mode": values.get("hours_mode", "keep"),
            "keep": "" if parsed else (readable(HOURS, spec) or "nie podano"),
            "week": rows,
            "start": values.get("hours_from") or DEFAULT_FROM,
            "end": values.get("hours_to") or DEFAULT_TO,
            "per_day": bool(values.get("hours_per_day")),
        }

    @staticmethod
    def _operator_key(name):
        return (name or "").strip().lower()
