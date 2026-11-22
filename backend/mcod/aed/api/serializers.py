from django.core.cache import cache

from mcod.aed.availability import availability_at
from mcod.aed.constants import (
    MUNICIPALITY_CODE_LENGTH,
    STATS_CACHE_KEY,
    STATS_CACHE_TTL_S,
    VOIVODESHIPS,
    ConsentStatus,
    LeadReview,
    RecordWarning,
    SourceLicence,
    TaskKind,
    TaskStatus,
)
from mcod.aed.models import AedLead, AedRecord, AedTask, ConsentRequest
from mcod.aed.planner import REPORTS_SHOWN_ON_MAP, record_warnings
from mcod.aed.profile import format_address
from mcod.aed.publishing import national_dataset


def reported_ids():
    """AEDs with an open citizen report of a problem a bystander should know about."""
    return set(
        AedTask.objects.filter(kind=TaskKind.REPORT, status=TaskStatus.OPEN, report_type__in=REPORTS_SHOWN_ON_MAP).values_list(
            "id_aed", flat=True
        )
    )


def brief(record, when, reported=frozenset()):
    data = record.data
    return {
        "id": record.id_aed,
        "name": record.nazwa_obiektu,
        "address": format_address(data),
        "city": record.miejscowosc,
        "lat": record.lat,
        "lon": record.lon,
        "availability": availability_at(data, when),
        "open_24_7": data.get("dostepny_calodobowo", ""),
        "opening_hours": data.get("godziny_dostepnosci", ""),
        "access": data.get("dostep", ""),
        "operational": data.get("sprawny", ""),
        "institution": record.organization.title,
        "dataset_id": record.dataset_id,
        "verified": record.verified,
        "warnings": ([] if record.verified else [RecordWarning.UNVERIFIED]) + record_warnings(data, record.id_aed in reported),
    }


def detail(record, when):
    return dict(
        brief(record, when, reported_ids()),
        fields=record.data,
        fixes=record.fixes,
        issues=record.issues,
        status=record.status,
        dataset={"id": record.dataset_id, "title": record.dataset.title, "slug": record.dataset.slug},
        updated=record.updated.isoformat(),
    )


class AedStats:
    """Campaign stats for the banner and the page; cached for STATS_CACHE_TTL_S and cleared on registry rebuild."""

    def __init__(self, now):
        self.now = now

    def get(self):
        stats = cache.get(STATS_CACHE_KEY)
        if stats is None:
            stats = self.compute()
            cache.set(STATS_CACHE_KEY, stats, STATS_CACHE_TTL_S)
        return stats

    def compute(self):
        national = national_dataset()
        return {
            "aed_count": AedRecord.objects.count(),
            "sources": self.sources(),
            "institution_count": AedRecord.objects.order_by().values("organization").distinct().count(),
            "availability": {"now": self.availability()},
            "coverage": self.coverage(self.municipalities()),
            "national_dataset": {"id": national.id, "slug": national.slug, "title": national.title} if national else None,
        }

    @staticmethod
    def sources():
        """All AEDs in one place: confirmed by providers, unconfirmed from public sources, held until the owner agrees."""
        waiting = (
            AedLead.objects.filter(in_register=False)
            .exclude(request__status=ConsentStatus.AGREED)
            .exclude(review__in=LeadReview.CLOSED)
            .exclude(source__licence__in=SourceLicence.PUBLISHABLE)
        )
        return {
            "confirmed": AedRecord.objects.filter(verified=True).count(),
            "public": AedRecord.objects.filter(verified=False).count(),
            "awaiting_consent": waiting.count(),
            "consent_requests": ConsentRequest.objects.filter(lead_count__gt=0).exclude(status=ConsentStatus.AGREED).count(),
        }

    def availability(self):
        counts = {}
        for data in AedRecord.objects.order_by().values_list("data", flat=True).iterator():
            value = availability_at(data, self.now)
            counts[value] = counts.get(value, 0) + 1
        return counts

    @staticmethod
    def municipalities():
        codes = (c.strip() for c in AedRecord.objects.order_by().values_list("kod_teryt_gminy", flat=True).distinct())
        return {c[:MUNICIPALITY_CODE_LENGTH] for c in codes if len(c) >= MUNICIPALITY_CODE_LENGTH and c[:2] in VOIVODESHIPS}

    @staticmethod
    def coverage(municipalities):
        total = sum(count for _, count in VOIVODESHIPS.values())
        provinces = []
        for code, (name, count) in VOIVODESHIPS.items():
            covered = len([m for m in municipalities if m.startswith(code)])
            provinces.append(
                {
                    "code": code,
                    "name": name,
                    "municipalities": covered,
                    "total": count,
                    "percent": round(100.0 * covered / count, 1),
                }
            )
        provinces.sort(key=lambda p: (-p["percent"], p["name"]))
        return {
            "municipalities": len(municipalities),
            "municipalities_total": total,
            "percent": round(100.0 * len(municipalities) / total, 2),
            "provinces": provinces,
        }
