from celery import shared_task

from mcod.aed.registry import RegistryBuilder


@shared_task(name="mcod.aed.tasks.build_aed_register_task", ignore_result=True)
def build_aed_register_task():
    """Nightly (see celeryapp) and shortly after a register resource changes (see signals)."""
    return RegistryBuilder().rebuild()
