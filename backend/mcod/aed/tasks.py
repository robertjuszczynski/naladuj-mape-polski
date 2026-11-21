from celery import shared_task

from mcod.aed.registry import RegistryBuilder
from mcod.aed.reminders import send_reminders


@shared_task(name="mcod.aed.tasks.build_aed_register_task", ignore_result=True)
def build_aed_register_task():
    """Nightly (see celeryapp) and shortly after a register resource changes (see signals)."""
    return RegistryBuilder().rebuild()


@shared_task(name="mcod.aed.tasks.send_aed_task_reminders", ignore_result=True)
def send_aed_task_reminders():
    """Daily: one e-mail per provider about tasks it has not been told about yet."""
    return len(send_reminders())
