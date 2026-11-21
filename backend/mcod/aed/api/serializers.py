from django.core.cache import cache
from django.db.models import Count

from mcod.aed.availability import availability_at, night_of
from mcod.aed.constants import (
    MUNICIPALITY_CODE_LENGTH,
    STATS_CACHE_KEY,
    STATS_CACHE_TTL_S,
    VOIVODESHIPS,
)
from mcod.aed.models import AedRecord
from mcod.aed.profile import format_address
from mcod.aed.publishing import aed_datasets, national_dataset


def brief(record, when):
    data = record.data
    return {
        "id": record.id_aed,
        "nazwa_obiektu": record.nazwa_obiektu,
        "adres": format_address(data),
        "miejscowosc": record.miejscowosc,
        "lat": record.lat,
        "lon": record.lon,
        "dostepnosc": availability_at(data, when),
        "dostepny_calodobowo": data.get("dostepny_calodobowo", ""),
        "godziny_dostepnosci": data.get("godziny_dostepnosci", ""),
        "dostep": data.get("dostep", ""),
        "sprawny": data.get("sprawny", ""),
        "instytucja": record.organization.title,
        "zbior_id": record.dataset_id,
    }


def detail(record, when):
    return dict(
        brief(record, when),
        dane=record.data,
        poprawki=record.fixes,
        uwagi=record.issues,
        status=record.status,
        zbior={"id": record.dataset_id, "tytul": record.dataset.title, "slug": record.dataset.slug},
        aktualizacja=record.updated.isoformat(),
    )


class AedStats:
    """Statystyki akcji dla banera i strony; liczone raz na STATS_CACHE_TTL_S i czyszczone po odbudowie rejestru."""

    def __init__(self, now):
        self.now = now

    def get(self):
        stats = cache.get(STATS_CACHE_KEY)
        if stats is None:
            stats = self.compute()
            cache.set(STATS_CACHE_KEY, stats, STATS_CACHE_TTL_S)
        return stats

    def compute(self):
        institutions = list(
            AedRecord.objects.values("organization__title").annotate(count=Count("id")).order_by("-count", "organization__title")
        )
        national = national_dataset()
        return {
            "liczba_aed": sum(i["count"] for i in institutions),
            "liczba_instytucji": len(institutions),
            "liczba_zbiorow": aed_datasets().count(),
            "dostepnosc": self.availability(),
            "naladowanie": self.charge(self.municipalities()),
            "instytucje": [{"nazwa": i["organization__title"], "liczba": i["count"]} for i in institutions],
            "zbior_ogolnopolski": {"id": national.id, "slug": national.slug, "tytul": national.title} if national else None,
        }

    def availability(self):
        moments = {"teraz": self.now, "noc": night_of(self.now)}
        counts = {key: {} for key in moments}
        for data in AedRecord.objects.order_by().values_list("data", flat=True).iterator():
            for key, when in moments.items():
                value = availability_at(data, when)
                counts[key][value] = counts[key].get(value, 0) + 1
        return counts

    @staticmethod
    def municipalities():
        codes = (c.strip() for c in AedRecord.objects.order_by().values_list("kod_teryt_gminy", flat=True).distinct())
        return {c[:MUNICIPALITY_CODE_LENGTH] for c in codes if len(c) >= MUNICIPALITY_CODE_LENGTH and c[:2] in VOIVODESHIPS}

    @staticmethod
    def charge(municipalities):
        total = sum(count for _, count in VOIVODESHIPS.values())
        voivodeships = []
        for code, (name, count) in VOIVODESHIPS.items():
            covered = len([m for m in municipalities if m.startswith(code)])
            voivodeships.append(
                {"kod": code, "nazwa": name, "gminy": covered, "razem": count, "procent": round(100.0 * covered / count, 1)}
            )
        voivodeships.sort(key=lambda v: (-v["procent"], v["nazwa"]))
        return {
            "gminy": len(municipalities),
            "gminy_razem": total,
            "procent": round(100.0 * len(municipalities) / total, 2),
            "wojewodztwa": voivodeships,
            "zrodlo": "Liczba gmin: TERYT (GUS), %d gmin" % total,
        }
