from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from mcod.resources.models import AGGREGATED_REGISTER_AED, Resource

SCHEDULED_KEY = "aed:register:scheduled"


def touches_register(resource):
    previous = resource.tracker.previous("aggregated_register") if resource.pk else ""
    return AGGREGATED_REGISTER_AED in (resource.aggregated_register, previous)


@receiver(post_save, sender=Resource)
def schedule_register_rebuild(sender, instance, **kwargs):
    """One rebuild shortly after a register resource is added, flagged, unflagged or replaced.

    Saves in a burst (upload, validation tasks, harvester) share the same scheduled rebuild.
    """
    if not touches_register(instance):
        return
    countdown = settings.MAIN_AED_REBUILD_COUNTDOWN_S
    if cache.add(SCHEDULED_KEY, True, countdown):
        from mcod.aed.tasks import build_aed_register_task

        transaction.on_commit(lambda: build_aed_register_task.apply_async(countdown=countdown))
