from django.core.cache import cache

from mcod.aed.availability import availability_at
from mcod.aed.constants import (
    MUNICIPALITY_CODE_LENGTH,
    STATS_CACHE_KEY,
    STATS_CACHE_TTL_S,
    VOIVODESHIPS,
)
from mcod.aed.models import AedRecord
from mcod.aed.profile import format_address
from mcod.aed.publishing import national_dataset


def brief(record, when):
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
    }


def detail(record, when):
    return dict(
        brief(record, when),
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
            "institution_count": AedRecord.objects.order_by().values("organization").distinct().count(),
            "availability": {"now": self.availability()},
            "coverage": self.coverage(self.municipalities()),
            "national_dataset": {"id": national.id, "slug": national.slug, "title": national.title} if national else None,
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
