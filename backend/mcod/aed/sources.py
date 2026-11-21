"""Metadane istniejących zbiorów AED instytucji z data/zrodla/zrodla.json (dane demonstracyjne)."""

import json
import os
from functools import lru_cache

from mcod.aed.constants import DATA_DIR

SOURCES_DIR = os.path.join(DATA_DIR, "zrodla")


@lru_cache(maxsize=1)
def source_meta():
    with open(os.path.join(SOURCES_DIR, "zrodla.json"), encoding="utf-8") as fp:
        return tuple(json.load(fp))


def teryt_for(organization_title):
    """TERYT gminy instytucji. Na razie znany tylko dla instytucji z pliku źródeł (ograniczenie wersji demonstracyjnej)."""
    return next((m["kod_teryt_gminy"] for m in source_meta() if m["wydawca"] == organization_title), "")


def source_file(source_id):
    return os.path.join(SOURCES_DIR, "%s.csv" % source_id)
