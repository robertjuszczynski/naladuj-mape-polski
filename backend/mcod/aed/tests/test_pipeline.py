import pytest

from mcod.aed.constants import RecordStatus
from mcod.aed.importing.pipeline import ImportPipeline, ImportSource
from mcod.aed.tests.helpers import MARKI, import_test_file, read_table


class FakeGeocoder:
    def __init__(self):
        self.calls = 0

    def fill_missing(self, mapped):
        for record, notes in mapped:
            if not record.get("szerokosc_geograficzna"):
                self.calls += 1
                record["szerokosc_geograficzna"], record["dlugosc_geograficzna"] = "52.3240", "21.1020"
                notes.append("geokodowanie testowe")
        return mapped


def statuses(results):
    out = {}
    for r in results:
        out[r["status"]] = out.get(r["status"], 0) + 1
    return out


def test_template_xlsx_is_ready():
    results = import_test_file("01-poprawny-szablon-marki.xlsx")
    assert statuses(results) == {RecordStatus.READY: 5}


def test_own_format_with_semicolons():
    results = import_test_file("02-wlasny-format-srednik.csv")
    assert statuses(results) == {RecordStatus.READY: 4}
    first = results[0]["record"]
    assert (first["cecha_adresu"], first["ulica"], first["numer_budynku"]) == ("ul.", "Duża", "3")
    assert first["szerokosc_geograficzna"] == "52.3228"
    assert first["godziny_dostepnosci"] == "Mo-Fr 07:00-18:00"
    assert results[1]["record"]["godziny_dostepnosci"] == "Mo-Fr 10:00-19:00; Sa 09:00-14:00"


def test_errors_file_without_geocoder():
    results = {r["record"]["nazwa_obiektu"]: r for r in import_test_file("03-bledy-do-wylapania.csv")}
    assert results["Punkt w Krakowie"]["status"] == RecordStatus.HELD
    assert results["Punkt poza Polską (Berlin)"]["status"] == RecordStatus.HELD
    assert results["Zły kod pocztowy i data"]["status"] == RecordStatus.READY
    assert results["Zły kod pocztowy i data"]["record"]["kod_pocztowy"] == "05-270"
    assert results["Punkt bez współrzędnych"]["status"] == RecordStatus.NEEDS_FIX


def test_geocoder_is_injected():
    geocoder = FakeGeocoder()
    results = {r["record"]["nazwa_obiektu"]: r for r in import_test_file("03-bledy-do-wylapania.csv", geocoder)}
    assert geocoder.calls == 1
    point = results["Punkt bez współrzędnych"]
    assert point["status"] == RecordStatus.READY
    assert "geokodowanie testowe" in point["notes"]


def test_mixed_file():
    results = import_test_file("06-mieszany-dobre-i-zle.csv", FakeGeocoder())
    assert len(results) == 9
    by_name = {r["record"].get("nazwa_obiektu"): r for r in results}
    assert by_name["Hala MOSiR"]["status"] == RecordStatus.READY
    assert statuses(results)[RecordStatus.NEEDS_DECISION] == 2


def test_operator_from_file_is_kept_and_email_is_flagged():
    results = import_test_file("05-gmina-z-innymi-dysponentami.csv")
    assert results[1]["record"]["dysponent_nazwa"] == "Szkoła Podstawowa nr 1 w Markach"
    assert any(i["code"] == "dane_osobowe" for i in results[2]["issues"])


def test_defaults_and_id_prefix():
    table = read_table("testowe", "02-wlasny-format-srednik.csv")
    results = ImportPipeline(MARKI).run(table.header, table.rows)
    record = results[0]["record"]
    assert record["id_aed"] == "marki-1"
    assert (record["kod_teryt_gminy"], record["dysponent_nazwa"], record["data_aktualizacji"]) == (
        "1434021",
        "Urząd Miasta Marki",
        "2026-11-21",
    )


def test_explicit_mapping_skips_columns():
    table = read_table("testowe", "02-wlasny-format-srednik.csv")
    mapping = {column: "" for column in table.header}
    mapping["Nazwa placówki"] = "nazwa_obiektu"
    results = ImportPipeline(MARKI).run(table.header, table.rows, mapping)
    assert results[0]["record"]["nazwa_obiektu"] == "Szkoła Podstawowa nr 3"
    assert "szerokosc_geograficzna" not in results[0]["record"]


class Organization:
    def __init__(self, title, regon, pk):
        self.title, self.regon, self.pk = title, regon, pk


@pytest.mark.parametrize(
    "organization,prefix,teryt",
    [
        (Organization("Urząd Miasta Marki", None, 5), "aed-1434021", "1434021"),
        (Organization("Gmina Testowa", " 123456789 ", 7), "aed-123456789", ""),
        (Organization("Gmina Bez Regon", None, 9), "aed-9", ""),
    ],
)
def test_source_for_organization(organization, prefix, teryt):
    source = ImportSource.for_organization(organization, "kreator", "2026-11-21")
    assert (source.id_prefix, source.teryt) == (prefix, teryt)
    assert ("kod_teryt_gminy" in source.defaults()) == bool(teryt)
