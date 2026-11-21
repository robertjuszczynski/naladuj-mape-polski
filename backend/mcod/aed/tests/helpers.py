import os

from mcod.aed.constants import DATA_DIR
from mcod.aed.importing.pipeline import ImportPipeline, ImportSource
from mcod.aed.importing.reader import TabularReader

TEST_FILES_DIR = os.path.join(DATA_DIR, "testowe")
MARKI = ImportSource("Urząd Miasta Marki", "test", "2026-11-21", "1434021", "marki")


def read_bytes(*parts):
    with open(os.path.join(DATA_DIR, *parts), "rb") as fp:
        return fp.read()


def read_table(*parts):
    return TabularReader().read(parts[-1], read_bytes(*parts))


def import_test_file(name, geocoder=None):
    table = read_table("testowe", name)
    return ImportPipeline(MARKI, geocoder=geocoder).run(table.header, table.rows)


def by_id(results):
    return {r["record"]["id_aed"]: r for r in results}
