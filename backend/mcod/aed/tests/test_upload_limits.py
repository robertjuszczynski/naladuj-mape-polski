import io

import pytest
from openpyxl import Workbook

from mcod.aed.importing.reader import TabularReader, UploadError, UploadValidator


class Uploaded:
    def __init__(self, name, data, size=None):
        self.name = name
        self._data = data
        self.size = len(data) if size is None else size

    def read(self):
        return self._data


def csv_bytes(rows):
    return ("nazwa,miejscowosc\n" + "".join("AED %d,Marki\n" % i for i in range(rows))).encode("utf-8")


def xlsx_bytes(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["nazwa", "miejscowosc"])
    for i in range(rows):
        sheet.append(["AED %d" % i, "Marki"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_valid_csv_is_read():
    table = UploadValidator().read(Uploaded("aed.CSV", csv_bytes(3)))
    assert table.header == ["nazwa", "miejscowosc"] and len(table.rows) == 3


@pytest.mark.parametrize("name", ["aed.xls", "aed.txt", "aed", "aed.csv.exe"])
def test_extension_whitelist(name):
    with pytest.raises(UploadError, match="CSV albo XLSX"):
        UploadValidator().read(Uploaded(name, csv_bytes(1)))


def test_size_limit():
    with pytest.raises(UploadError, match="za duży"):
        UploadValidator().read(Uploaded("aed.csv", csv_bytes(1), size=10 * 1024 * 1024 + 1))


def test_size_limit_allows_exactly_10_mb():
    UploadValidator().validate_file("aed.csv", 10 * 1024 * 1024)


@pytest.mark.parametrize("maker,name", [(csv_bytes, "aed.csv"), (xlsx_bytes, "aed.xlsx")])
def test_row_limit(maker, name):
    validator = UploadValidator(max_rows=5)
    assert len(validator.read(Uploaded(name, maker(5))).rows) == 5
    with pytest.raises(UploadError, match="za dużo wierszy"):
        validator.read(Uploaded(name, maker(6)))


def test_default_row_limit_is_5000():
    assert len(UploadValidator().read(Uploaded("aed.csv", csv_bytes(5000))).rows) == 5000
    with pytest.raises(UploadError):
        UploadValidator().read(Uploaded("aed.csv", csv_bytes(5001)))


@pytest.mark.parametrize(
    "name,data", [("aed.xlsx", b"to nie jest xlsx"), ("aed.xlsx", b"PK\x03\x04uszkodzony"), ("aed.csv", b"\x81\x8d\x8f\x90\x9d")]
)
def test_broken_file_gives_fixed_message(name, data):
    with pytest.raises(UploadError) as error:
        TabularReader().read(name, data)
    assert str(error.value) == TabularReader.UNREADABLE
