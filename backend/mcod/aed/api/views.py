import datetime
import json

import falcon
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from mcod.aed.api.serializers import AedStats, brief, detail
from mcod.aed.availability import night_of
from mcod.aed.importing.geocoder import GugikGeocoder
from mcod.aed.models import AedRecord
from mcod.aed.nearest import SEARCH_RADIUS_DEG, AddressLocator, NearestAed

NIGHT_PARAM = "night"
MIN_NEARBY_RECORDS = 20
ADDRESS_TIMEOUT_S = 8


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


class AedNearestView:
    """Nearest AED open at ?at= for a point (?lat=&lon=) or a free-text address (?address=)."""

    def on_get(self, request, response, *args, **kwargs):
        when = requested_time(request)
        point = self.point(request)
        records = self.records_near(point["lat"], point["lon"])
        payload = {
            "meta": {"at": when.isoformat(), "point": point},
            "data": NearestAed(records, when).find(point["lat"], point["lon"]),
        }
        send_json(response, payload)

    @staticmethod
    def point(request):
        address = (request.get_param("address") or "").strip()
        if address:
            point = AddressLocator(GugikGeocoder(cache=cache, timeout=ADDRESS_TIMEOUT_S)).locate(address)
            if point is None:
                raise falcon.HTTPNotFound(title="Nie znaleziono adresu", description="Podaj adres jako: Warszawa, Wiejska 4/6/8")
            return point
        try:
            lat, lon = float(request.get_param("lat")), float(request.get_param("lon"))
        except (TypeError, ValueError):
            raise falcon.HTTPBadRequest(title="Brak punktu", description="Podaj lat i lon albo address")
        return {"lat": lat, "lon": lon, "label": "", "exact": True}

    @staticmethod
    def records_near(lat, lon):
        queryset = AedRecord.objects.select_related("organization").exclude(lat=None)
        nearby = list(
            queryset.filter(
                lat__range=(lat - SEARCH_RADIUS_DEG, lat + SEARCH_RADIUS_DEG),
                lon__range=(lon - SEARCH_RADIUS_DEG, lon + SEARCH_RADIUS_DEG),
            )
        )
        return nearby if len(nearby) >= MIN_NEARBY_RECORDS else list(queryset)
