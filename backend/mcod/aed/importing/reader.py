"""Odczyt plików CSV/XLSX od dysponentów i limity wgrywanych plików."""

import csv
import datetime
import io
import os
import zipfile
from collections import namedtuple

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from mcod.aed.constants import ALLOWED_UPLOAD_EXTENSIONS, MAX_UPLOAD_BYTES, MAX_UPLOAD_ROWS

Table = namedtuple("Table", "header rows repairs")
CSV_ENCODINGS = ("utf-8-sig", "cp1250")
READ_ERRORS = (ValueError, UnicodeDecodeError, csv.Error, zipfile.BadZipFile, InvalidFileException, KeyError, OSError)


class UploadError(Exception):
    """Błąd z komunikatem, który można pokazać użytkownikowi."""


class UploadValidator:
    TOO_LARGE = "Plik jest za duży – maksymalnie %d MB." % (MAX_UPLOAD_BYTES // (1024 * 1024))
    BAD_EXTENSION = "Wgraj plik CSV albo XLSX."
    TOO_MANY_ROWS = "Plik ma za dużo wierszy – maksymalnie %d defibrylatorów w jednym pliku." % MAX_UPLOAD_ROWS

    def __init__(self, max_bytes=MAX_UPLOAD_BYTES, extensions=ALLOWED_UPLOAD_EXTENSIONS, max_rows=MAX_UPLOAD_ROWS):
        self.max_bytes = max_bytes
        self.extensions = extensions
        self.max_rows = max_rows

    def validate_file(self, filename, size):
        if os.path.splitext(filename or "")[1].lower() not in self.extensions:
            raise UploadError(self.BAD_EXTENSION)
        if size > self.max_bytes:
            raise UploadError(self.TOO_LARGE)

    def read(self, uploaded):
        """uploaded: plik z atrybutami name i size oraz metodą read() (np. UploadedFile Django)."""
        self.validate_file(uploaded.name, uploaded.size)
        return TabularReader(max_rows=self.max_rows).read(uploaded.name, uploaded.read())


class TabularReader:
    UNREADABLE = "Nie udało się odczytać pliku – zapisz go jako CSV w UTF-8 albo XLSX."

    def __init__(self, max_rows=None):
        self.max_rows = max_rows

    def read(self, filename, data):
        try:
            if filename.lower().endswith(".xlsx"):
                return self.parse_xlsx(data)
            return self.parse_csv(self.decode(data))
        except UploadError:
            raise
        except READ_ERRORS as exc:
            raise UploadError(self.UNREADABLE) from exc

    def decode(self, data):
        for encoding in CSV_ENCODINGS:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise UploadError(self.UNREADABLE)

    def parse_csv(self, text):
        """Naprawia też pliki, w których każdy wiersz jest w całości ujęty w cudzysłów."""
        repairs = []
        text = text.lstrip("﻿")
        first_line = text.splitlines()[0] if text.strip() else ""
        delimiter = self._detect_delimiter(first_line.strip('"'))
        rows = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in r)]
        if rows and all(len(r) == 1 for r in rows) and delimiter in rows[0][0]:
            rows = [next(csv.reader(io.StringIO(r[0]), delimiter=delimiter)) for r in rows]
            repairs.append("Każdy wiersz był w całości ujęty w cudzysłów – rozpakowano wiersze, żeby odczytać kolumny")
        rows = [[c.strip() for c in r] for r in rows]
        if not rows:
            return Table([], [], repairs)
        self._check_size(rows)
        return Table(rows[0], rows[1:], repairs)

    def parse_xlsx(self, data):
        sheet = load_workbook(io.BytesIO(data), read_only=True, data_only=True).worksheets[0]
        rows = []
        for raw in sheet.iter_rows(values_only=True):
            values = [self._cell(v) for v in raw]
            if any(values):
                rows.append(values)
                self._check_size(rows)
        if not rows:
            return Table([], [], [])
        return Table(rows[0], rows[1:], [])

    def _check_size(self, rows):
        if self.max_rows is not None and len(rows) - 1 > self.max_rows:
            raise UploadError(UploadValidator.TOO_MANY_ROWS)

    @staticmethod
    def _cell(value):
        if value is None:
            return ""
        if isinstance(value, (datetime.date, datetime.datetime)):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    @staticmethod
    def _detect_delimiter(first_line):
        counts = {d: first_line.count(d) for d in (",", ";", "\t")}
        return max(counts, key=counts.get) if any(counts.values()) else ","


def read_records(text):
    """Plik CSV we wzorcowym zakresie jako lista słowników."""
    table = TabularReader().parse_csv(text)
    return [dict(zip(table.header, row)) for row in table.rows]
