import datetime
import json

import falcon
from django.db.models import Q
from django.utils import timezone

from mcod.aed.api.serializers import AedStats, brief, detail
from mcod.aed.availability import night_of
from mcod.aed.models import AedRecord

NIGHT_PARAM = "night"


def requested_time(request):
    at = request.get_param("at")
    if at == NIGHT_PARAM:
        return night_of(timezone.localtime())
    if at:
        try:
            return datetime.datetime.fromisoformat(at)
        except ValueError:
            raise falcon.HTTPBadRequest(
                title="Nieprawidłowy parametr at", description="Użyj formatu RRRR-MM-DDTGG:MM albo at=night"
            )
    return timezone.localtime()


def send_json(response, payload):
    response.content_type = "application/json; charset=utf-8"
    response.text = json.dumps(payload, ensure_ascii=False)
    response.status = falcon.HTTP_200


class AedListView:
    def on_get(self, request, response, *args, **kwargs):
        when = requested_time(request)
        queryset = AedRecord.objects.select_related("organization").exclude(lat=None)
        query = (request.get_param("q") or "").strip()
        if query:
            queryset = queryset.filter(Q(nazwa_obiektu__icontains=query) | Q(miejscowosc__icontains=query))
        data = [brief(r, when) for r in queryset]
        send_json(response, {"meta": {"count": len(data), "at": when.isoformat()}, "data": data})


class AedDetailView:
    def on_get(self, request, response, id, *args, **kwargs):
        record = AedRecord.objects.select_related("organization", "dataset").filter(id_aed=id).first()
        if record is None:
            raise falcon.HTTPNotFound(title="Nie ma takiego AED")
        send_json(response, {"data": detail(record, requested_time(request))})


class AedStatsView:
    def on_get(self, request, response, *args, **kwargs):
        send_json(response, {"data": AedStats(timezone.localtime()).get()})
