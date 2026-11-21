import datetime
import os

import pytest

from mcod.aed.availability import availability_at, night_of
from mcod.aed.constants import Availability, IssueCode, RecordStatus
from mcod.aed.importing.address import AddressParser
from mcod.aed.importing.columns import ADDRESS_TARGET, ColumnMatcher
from mcod.aed.importing.mapper import normalize_value
from mcod.aed.importing.reader import TabularReader, read_records
from mcod.aed.opening_hours import OpeningHours
from mcod.aed.profile import FIELD_NAMES, FIELDS
from mcod.aed.tests.helpers import by_id, import_test_file, read_bytes, read_table
from mcod.aed.validation import PortalQualityCheck, RecordValidator

MARKI_FILE = "04-marki-oryginal-z-dane-gov-pl.csv"


def test_example_record_is_valid():
    assert RecordValidator().validate({f.name: f.example for f in FIELDS}) == []


def test_missing_required_fields():
    fields = [i["field"] for i in RecordValidator().validate({}) if i["code"] == IssueCode.MISSING_REQUIRED]
    assert fields == [f.name for f in FIELDS if f.required]


def test_marki_file_is_repaired_and_mapped():
    table = read_table("testowe", MARKI_FILE)
    mapping = ColumnMatcher().suggest(table.header, table.rows)
    assert len(table.repairs) == 1
    assert mapping["Lokalizacja"] == "nazwa_obiektu"
    assert mapping["Nazwa"] == ""
    assert mapping["Adres"] == ADDRESS_TARGET
    assert len(import_test_file(MARKI_FILE)) == 8


def test_marki_coordinates_swapped_and_row_7_held():
    results = import_test_file(MARKI_FILE)
    swapped = [
        r["record"]["id_aed"]
        for r in results
        if any(f["rule"] == IssueCode.SWAPPED_COORDINATES and f["auto"] for f in r["fixes"])
    ]
    assert swapped == ["marki-1", "marki-2", "marki-3", "marki-4", "marki-5", "marki-6", "marki-8"]
    row7 = by_id(results)["marki-7"]
    assert row7["status"] == RecordStatus.HELD
    assert "Krosno" in next(i["message"] for i in row7["issues"] if i["code"] == IssueCode.OUTSIDE_MUNICIPALITY)


def test_marki_duplicate_points():
    results = import_test_file(MARKI_FILE)
    assert {r["record"]["id_aed"] for r in results if r["status"] == RecordStatus.NEEDS_DECISION} == {"marki-5", "marki-6"}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Al.. Piłsudskiego 95, 05-270 Marki", ("al.", "Piłsudskiego", "95", "", "05-270", "Marki")),
        ("Rynek Główny 1/4, 31-042 Kraków", ("rynek", "Rynek Główny", "1", "4", "31-042", "Kraków")),
        ("Plac Wolności 3", ("pl.", "Plac Wolności", "3", "", "", "")),
    ],
)
def test_address_split(text, expected):
    keys = ("cecha_adresu", "ulica", "numer_budynku", "numer_lokalu", "kod_pocztowy", "miejscowosc")
    assert tuple(AddressParser.parse(text)[k] for k in keys) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Poniedziałek: godz. 8:00-18:00; Wtorek-Piątek: godz. 8:00-16:00", "Mo 08:00-18:00; Tu-Fr 08:00-16:00"),
        ("dni powszednie 07:00-17:30", "Mo-Fr 07:00-17:30"),
        ("pon.-pt. 10:00-19:00, sob. 9:00-14:00", "Mo-Fr 10:00-19:00; Sa 09:00-14:00"),
        ("całodobowo", "24/7"),
        ("W godzinach otwarcia stacji metra", None),
    ],
)
def test_hours(text, expected):
    assert OpeningHours.from_polish(text) == expected


@pytest.mark.parametrize(
    "field,raw,expected",
    [
        ("dostepny_calodobowo", "TAK", "true"),
        ("wewnatrz_budynku", "na zewnątrz", "false"),
        ("szerokosc_geograficzna", "52,2297", "52.2297"),
        ("data_ostatniego_przegladu", "14.05.2026", "2026-05-14"),
        ("dysponent_telefon", "(22) 123-45-67", "221234567"),
        ("kod_pocztowy", "05 270", "05-270"),
        ("cecha_adresu", "ulica", "ul."),
        ("dostep", "Publiczny", "publiczny"),
        ("godziny_dostepnosci", "pn-pt 7-18", "Mo-Fr 07:00-18:00"),
    ],
)
def test_normalize(field, raw, expected):
    assert normalize_value(field, raw)[0] == expected


def test_availability():
    sat3 = datetime.datetime(2026, 11, 21, 3, 0)
    tue10 = datetime.datetime(2026, 11, 24, 10, 0)
    assert OpeningHours.is_open_at("Mo-Fr 08:00-16:00", tue10) is True
    assert OpeningHours.is_open_at("Mo-Fr 08:00-16:00", sat3) is False
    assert OpeningHours.is_open_at("Sa-Mo 22:00-04:00", sat3) is True
    assert availability_at({"dostepny_calodobowo": "false"}, sat3) == Availability.UNKNOWN
    assert availability_at({"dostepny_calodobowo": "true", "sprawny": "false"}, sat3) == Availability.FAULTY


def test_night_of():
    assert night_of(datetime.datetime(2026, 11, 21, 2, 30, 15)) == datetime.datetime(2026, 11, 21, 3, 0)
    assert night_of(datetime.datetime(2026, 11, 21, 14, 5)) == datetime.datetime(2026, 11, 22, 3, 0)


def test_csv_in_cp1250_is_read():
    table = TabularReader().read("plik.csv", "nazwa;miejscowość\nUrząd;Łódź\n".encode("cp1250"))
    assert table.header == ["nazwa", "miejscowość"] and table.rows == [["Urząd", "Łódź"]]


def test_seed_files_pass_portal_quality_rules():
    for name in ("warszawa", "legionowo", "przemysl", "krosno", "marki"):
        records = read_records(read_bytes("zrodla", name + ".csv").decode("utf-8"))
        assert all(r["errors"] == 0 for r in PortalQualityCheck().run(records)), name


def test_static_template_matches_profile():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "aed", "szablon-danych-aed.csv")
    with open(path, encoding="utf-8-sig") as fp:
        assert TabularReader().parse_csv(fp.read()).header == FIELD_NAMES


def test_opening_hours_in_polish():
    from mcod.aed.opening_hours import OpeningHours

    assert OpeningHours.to_polish("Mo-Fr 08:00-16:00; Sa 09:00-14:00") == "pn–pt 8:00–16:00; sob. 9:00–14:00"
    assert OpeningHours.to_polish("24/7") == "całodobowo"
    assert OpeningHours.to_polish("Mo-Fr 07:00-15:00; Su off") == "pn–pt 7:00–15:00; nd nieczynne"
    assert OpeningHours.to_polish("00:00-24:00") == "codziennie 0:00–24:00"
    assert OpeningHours.to_polish("Mo-Su 07:00-22:00") == "codziennie 7:00–22:00"
    assert OpeningHours.to_polish("rano") == "rano"


def test_changes_are_counted_per_field():
    from mcod.aed.changes import change, summarize

    rows = [
        {"notes": [change("godziny_dostepnosci", "a"), change("szerokosc_geograficzna", "b")], "fixes": []},
        {"notes": ["stary wpis"], "fixes": [{"auto": True, "message": "zamiana", "before": "1, 2", "after": "2, 1"}]},
        {"notes": [], "fixes": [{"auto": False, "message": "do sprawdzenia", "before": "", "after": ""}]},
    ]
    summary = summarize(rows)
    assert summary["fields"] == 4 and summary["records"] == 2
    assert dict(summary["by_field"]) == {"Współrzędne": 2, "Godziny dostępności": 1, "Inne": 1}
