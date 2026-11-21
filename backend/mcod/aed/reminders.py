"""One e-mail per provider when new tasks appear, with a link to the "Zadania" inbox."""

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from mcod.aed.constants import TaskStatus
from mcod.aed.models import AedTask

PREVIEW = 10
TASKS_PATH = "/aed/aedtask/"


def recipients(organization):
    return sorted({u.email for u in organization.users.filter(is_active=True, is_staff=True) if u.email})


def message(organization, tasks):
    lines = [
        "- %s: %s%s"
        % (t.get_kind_display(), t.aed_name or t.id_aed, t.due_date and " (termin %s)" % t.due_date.strftime("%d.%m.%Y") or "")
        for t in tasks[:PREVIEW]
    ]
    more = len(tasks) - PREVIEW
    if more > 0:
        lines.append("- …i %d więcej" % more)
    return (
        "Dzień dobry,\n\nw portalu dane.gov.pl czekają nowe zadania dla AED instytucji %s:\n\n%s\n\n"
        "Zadania: %s%s\n\nKażda poprawka od razu trafia do Waszego zbioru i na mapę AED.\n"
        "Akcja „Naładuj mapę Polski.”" % (organization.title, "\n".join(lines), settings.ADMIN_URL.rstrip("/"), TASKS_PATH)
    )


def send_reminders(organizations=None, only_new=True):
    """E-mails sent as (recipients, subject, body). The daily run mails only new tasks; "send now" mails all open ones."""
    pending = AedTask.objects.filter(status=TaskStatus.OPEN).select_related("organization")
    if only_new:
        pending = pending.filter(notified__isnull=True)
    if organizations is not None:
        pending = pending.filter(organization__in=organizations)
    by_organization = {}
    for task in pending:
        by_organization.setdefault(task.organization, []).append(task)
    sent = []
    for organization, tasks in by_organization.items():
        to = recipients(organization)
        if not to:
            continue
        subject = "AED: %d %s do zrobienia – %s" % (len(tasks), "zadanie" if len(tasks) == 1 else "zadań", organization.title)
        body = message(organization, tasks)
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, to)
        AedTask.objects.filter(pk__in=[t.pk for t in tasks]).update(notified=timezone.now())
        sent.append((to, subject, body))
    return sent
