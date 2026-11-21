"""Provider tasks derived from the register: due dates, missing data. Citizen reports are added by the API."""

import datetime

from mcod.aed.constants import INSPECTION_INTERVAL_DAYS, TASK_LEAD_DAYS
from mcod.aed.constants import RecordWarning as W
from mcod.aed.constants import ReportType, TaskKind, TaskStatus

EXPIRY_WARNINGS = {
    TaskKind.INSPECTION: W.INSPECTION_OVERDUE,
    TaskKind.ELECTRODES: W.ELECTRODES_EXPIRED,
    TaskKind.BATTERY: W.BATTERY_EXPIRED,
}
REPORTS_SHOWN_ON_MAP = (ReportType.NOT_WORKING, ReportType.CLOSED, ReportType.MISSING)


def parse_date(value):
    try:
        return datetime.date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def due_dates(data):
    """{kind: date} for the inspection (last + interval) and the electrode and battery expiry dates."""
    out = {}
    for kind, field in TaskKind.DATE_FIELDS.items():
        date = parse_date(data.get(field))
        if date is not None:
            out[kind] = date + datetime.timedelta(days=INSPECTION_INTERVAL_DAYS) if kind == TaskKind.INSPECTION else date
    return out


def record_warnings(data, reported, today=None):
    today = today or datetime.date.today()
    warnings = [EXPIRY_WARNINGS[kind] for kind, due in due_dates(data).items() if due < today]
    return warnings + ([W.REPORTED] if reported else [])


class TaskPlanner:
    def __init__(self, today=None):
        self.today = today or datetime.date.today()

    def wanted(self, data):
        """[(kind, due date or None)] a record needs now."""
        horizon = self.today + datetime.timedelta(days=TASK_LEAD_DAYS)
        out = [(kind, due) for kind, due in due_dates(data).items() if due <= horizon]
        if data.get("dostepny_calodobowo") != "true" and not data.get("godziny_dostepnosci"):
            out.append((TaskKind.MISSING_HOURS, None))
        if not (data.get("opis_lokalizacji") or "").strip():
            out.append((TaskKind.MISSING_LOCATION, None))
        return out

    def sync(self):
        """Opens tasks for what records need now and closes the ones that no longer apply."""
        from mcod.aed.models import AedRecord, AedTask

        open_tasks = {
            (t.organization_id, t.id_aed, t.kind): t
            for t in AedTask.objects.filter(status=TaskStatus.OPEN).exclude(kind=TaskKind.REPORT)
        }
        seen, new = set(), []
        for record in AedRecord.objects.all().only("organization_id", "id_aed", "nazwa_obiektu", "data"):
            for kind, due in self.wanted(record.data):
                key = (record.organization_id, record.id_aed, kind)
                seen.add(key)
                task = open_tasks.get(key)
                if task is None:
                    new.append(
                        AedTask(
                            organization_id=record.organization_id,
                            id_aed=record.id_aed,
                            aed_name=record.nazwa_obiektu,
                            kind=kind,
                            due_date=due,
                        )
                    )
                elif task.due_date != due:
                    task.due_date = due
                    task.save(update_fields=["due_date"])
        AedTask.objects.bulk_create(new)
        for key, task in open_tasks.items():
            if key not in seen:
                task.close()
        return len(new)
