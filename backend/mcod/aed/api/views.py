import datetime
import json

import falcon
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from mcod.aed.address_search import AddressSuggestions
from mcod.aed.api.serializers import AedStats, brief, detail, reported_ids
from mcod.aed.availability import night_of
from mcod.aed.constants import REPORT_RATE_LIMIT, REPORT_RATE_WINDOW_S, ReportType, TaskKind
from mcod.aed.importing.geocoder import GugikGeocoder
from mcod.aed.models import AedRecord, AedTask, AggregatedAedInfo
from mcod.aed.nearest import MAX_DISTANCE_M, SEARCH_RADIUS_DEG, AddressLocator, NearestAed

NIGHT_PARAM = "night"
MIN_NEARBY_RECORDS = 20
REPORT_COMMENT_MAX = 2000
ADDRESS_TIMEOUT_S = 8
ADDRESS_RATE_LIMIT = 60


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
        reported = reported_ids()
        data = [brief(r, when, reported) for r in queryset]
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


class AedAggregatedView:
    """The national AED register resource, in the same shape as /dga-aggregated: the portal shows its table as the wykaz."""

    def on_get(self, request, response, *args, **kwargs):
        info = (
            AggregatedAedInfo.objects.select_related("resource", "resource__dataset")
            .filter(resource__status="published", resource__is_removed=False)
            .order_by("-pk")
            .first()
        )
        if info is None:
            raise falcon.HTTPNotFound(title="Wykaz AED nie jest jeszcze opublikowany")
        resource = info.resource
        send_json(
            response,
            {
                "dataset_id": resource.dataset.id,
                "dataset_slug": resource.dataset.slug,
                "resource_id": resource.id,
                "resource_slug": resource.slug,
            },
        )


class AedNearestView:
    """Nearest AED open at ?at= for a point (?lat=&lon=) or a free-text address (?address=)."""

    def on_get(self, request, response, *args, **kwargs):
        when = requested_time(request)
        point = self.point(request)
        records = self.records_near(point["lat"], point["lon"])
        payload = {
            "meta": {"at": when.isoformat(), "point": point, "radius_km": MAX_DISTANCE_M // 1000},
            "data": NearestAed(records, when, reported_ids()).find(point["lat"], point["lon"]),
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


class AedAddressView:
    """Address suggestions for the incident field on the AED page (?q=)."""

    def on_get(self, request, response, *args, **kwargs):
        limit(request, "address", ADDRESS_RATE_LIMIT, 60)
        geocoder = GugikGeocoder(cache=cache, timeout=ADDRESS_TIMEOUT_S)
        here = self.place(geocoder, request) or {}
        found = AddressSuggestions(geocoder).search(request.get_param("q"), here.get("teryt", ""), [here.get("city", "")])
        send_json(response, {"data": found})

    @staticmethod
    def place(geocoder, request):
        """Where the person is (or looks at on the map), so that "Wiejska" means the street in their town first."""
        try:
            return geocoder.reverse(float(request.get_param("lat")), float(request.get_param("lon")))
        except (TypeError, ValueError):
            return None


def limit(request, name, count_max, window_s):
    key = "aed:%s:%s" % (name, request.access_route[0] if request.access_route else request.remote_addr)
    count = cache.get_or_set(key, 0, window_s)
    if count >= count_max:
        raise falcon.HTTPTooManyRequests(title="Za dużo zapytań, spróbuj później")
    cache.incr(key)


class AedReportView:
    """A citizen report from the AED page; it becomes a task for the provider and a warning on the map."""

    def on_post(self, request, response, id, *args, **kwargs):
        record = AedRecord.objects.filter(id_aed=id).first()
        if record is None:
            raise falcon.HTTPNotFound(title="Nie ma takiego AED")
        payload = request.get_media() or {}
        report_type = payload.get("type")
        if report_type not in ReportType.LABELS:
            raise falcon.HTTPBadRequest(title="Nieznany typ zgłoszenia")
        limit(request, "report", REPORT_RATE_LIMIT, REPORT_RATE_WINDOW_S)
        AedTask.objects.create(
            organization_id=record.organization_id,
            id_aed=record.id_aed,
            aed_name=record.nazwa_obiektu,
            kind=TaskKind.REPORT,
            report_type=report_type,
            comment=(payload.get("comment") or "")[:REPORT_COMMENT_MAX],
        )
        send_json(response, {"data": {"status": "received"}})
        response.status = falcon.HTTP_201
