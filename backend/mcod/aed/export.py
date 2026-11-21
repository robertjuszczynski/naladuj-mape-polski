import csv
import io
import re
import unicodedata
from urllib.parse import quote

from django.http import HttpResponse

from mcod.aed.field_types import STRING_COLUMN, type_of
from mcod.aed.profile import FIELD_NAMES, FIELDS_BY_NAME

UTF8_BOM = "﻿"


class AedCsv:
    """Plik CSV we wzorcowym zakresie i schemat kolumn dla widoku tabeli portalu."""

    @staticmethod
    def write(header, rows):
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        writer.writerow(header)
        writer.writerows(rows)
        return buffer.getvalue()

    @classmethod
    def to_csv(cls, records):
        return cls.write(FIELD_NAMES, ([r.get(f, "") for f in FIELD_NAMES] for r in records)).encode("utf-8")

    @staticmethod
    def table_schema(content):
        """Kolumna z pustymi komórkami zostaje tekstowa, bo portal nie traktuje pustej komórki jako braku danych."""
        rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
        header, body = rows[0], rows[1:]
        fields = []
        for i, name in enumerate(header):
            field = FIELDS_BY_NAME.get(name)
            column = type_of(field).table_type if field else STRING_COLUMN
            if column != STRING_COLUMN and any(i >= len(r) or r[i] == "" for r in body):
                column = STRING_COLUMN
            fields.append({"name": name, "type": column.type, "format": column.format})
        return {"fields": fields, "missingValues": []}


class CorrectedCsvExport:
    """Plik z kroku „Sprawdzenie”: dane po poprawkach i kolumny status, zmiany_automatyczne, do_sprawdzenia."""

    EXTRA_COLUMNS = ["status", "zmiany_automatyczne", "do_sprawdzenia"]

    def __init__(self, upload):
        self.upload = upload

    def rows(self):
        review = self.upload.review
        for i, row in enumerate(self.upload.checked):
            changes = ["%s (%s → %s)" % (f["message"], f["before"], f["after"]) for f in row["fixes"] if f["auto"]]
            changes += list(row.get("notes", []))
            todo = [x["message"] for x in row["issues"]] + [f["message"] for f in row["fixes"] if not f["auto"]]
            values = [row["record"].get(f, "") for f in FIELD_NAMES]
            yield values + [review.status_label(i, row), " | ".join(changes), " | ".join(todo)]

    def filename(self):
        return (self.upload.filename.rsplit(".", 1)[0] or "aed") + "-poprawiony.csv"

    def response(self):
        content = UTF8_BOM + AedCsv.write(FIELD_NAMES + self.EXTRA_COLUMNS, self.rows())
        response = HttpResponse(content.encode("utf-8"), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = attachment_header(self.filename())
        return response


def attachment_header(filename):
    """Nazwa ASCII dla starszych przeglądarek i pełna nazwa w UTF-8 (RFC 6266), bez znaków sterujących."""
    clean = re.sub(r"[\x00-\x1f\x7f]", "", filename)
    ascii_name = unicodedata.normalize("NFKD", clean).encode("ascii", "ignore").decode("ascii").replace('"', "").replace("\\", "")
    return "attachment; filename=\"%s\"; filename*=UTF-8''%s" % (ascii_name or "aed.csv", quote(clean))
