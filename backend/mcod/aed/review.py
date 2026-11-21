"""Decyzje instytucji w kroku „Sprawdzenie” kreatora: co trafi do publikacji, podsumowanie, ręczne poprawki."""

from collections import namedtuple

from mcod.aed.constants import Decision, RecordStatus, Severity
from mcod.aed.profile import FIELDS_BY_NAME, format_address
from mcod.aed.validation import RecordChecker

EditableField = namedtuple("EditableField", "name label placeholder")

EDITABLE_FIELDS = (
    EditableField("szerokosc_geograficzna", "Szerokość geogr.", ""),
    EditableField("dlugosc_geograficzna", "Długość geogr.", ""),
    EditableField("godziny_dostepnosci", "Godziny dostępności", "Mo-Fr 08:00-16:00"),
    EditableField("dostepny_calodobowo", "Dostępny całodobowo", ""),
    EditableField("sprawny", "Sprawny", ""),
)
ROW_DECISIONS = (Decision.ACCEPT, Decision.HOLD)
HELD_BY_INSTITUTION = "wstrzymany przez instytucję"
ACCEPTED_BY_INSTITUTION = "zatwierdzony przez instytucję"


class UploadReview:
    """checked: lista wyników sprawdzenia {record, fixes, issues, status, notes}; decisions: {indeks wiersza: decyzja}."""

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
        out = {"publish": 0, "auto": 0, "pending": 0, "blocked": 0}
        for i, row in enumerate(self.checked):
            out["publish"] += self.is_published_row(i, row)
            out["auto"] += bool(any(f["auto"] for f in row["fixes"]) or row.get("notes"))
            out["pending"] += row["status"] == RecordStatus.NEEDS_DECISION and self.decision(i) not in ROW_DECISIONS
            out["blocked"] += row["status"] in RecordStatus.BLOCKED
        return out

    def status_label(self, index, row):
        decision = self.decision(index)
        if decision == Decision.HOLD:
            return HELD_BY_INSTITUTION
        if decision == Decision.ACCEPT and row["status"] == RecordStatus.NEEDS_DECISION:
            return ACCEPTED_BY_INSTITUTION
        return RecordStatus.LABELS[row["status"]]

    def apply_decision(self, index, action, values=None):
        """Zwraca False, gdy indeks albo akcja są nieprawidłowe."""
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
        for field in EDITABLE_FIELDS:
            if field.name in values:
                record[field.name] = (values[field.name] or "").strip()
        fixed = RecordChecker().check_all([record], [previous.get("notes", [])])[0]
        fixed["fixes"] = previous["fixes"] + fixed["fixes"]
        self.checked[index] = fixed

    def review_rows(self):
        return [self._review_row(i, row) for i, row in enumerate(self.checked)]

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
            idx=index,
            held=held,
            publish=publish,
            label=RecordStatus.LABELS[RecordStatus.HELD] if held else RecordStatus.LABELS[row["status"]],
            badge_class=RecordStatus.BADGE_CLASSES.get(row["status"], RecordStatus.DEFAULT_BADGE_CLASS),
            address=format_address(row["record"]),
            issues=[dict(i, css="bad" if i["severity"] == Severity.ERROR else "warn") for i in row["issues"]],
            is_foreign_operator=self.is_foreign_operator(row["record"]),
            actions=actions,
            edit_fields=[self._edit_field(field, row["record"]) for field in EDITABLE_FIELDS],
        )

    @staticmethod
    def _edit_field(field, record):
        is_boolean = FIELDS_BY_NAME[field.name].type == "boolean"
        return {
            "name": field.name,
            "label": field.label,
            "placeholder": field.placeholder,
            "value": record.get(field.name, ""),
            "is_boolean": is_boolean,
        }

    @staticmethod
    def _operator_key(name):
        return (name or "").strip().lower()
