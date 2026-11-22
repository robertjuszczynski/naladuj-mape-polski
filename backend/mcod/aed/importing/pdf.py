"""Tables of AED lists published as PDF (e.g. in BIP)."""

import io
import re

from mcod.aed.importing.reader import Table

PDF_HEADER = ("Lp.", "Nazwa obiektu", "Adres", "Liczba AED")
ORDINAL = re.compile(r"^\d+\.?$")
ADDRESS = re.compile(r"^(ul\.|al\.|pl\.|os\.|plac|aleja|aleje|rynek|rondo|osiedle)\s|\s\d+[a-zA-Z]?(/\d+)?$", re.I)


def pdf_row(cells):
    """["12.", "Name", "", "ul. Street 5", "1"] -> ["12", "Name", "ul. Street 5", "1"]; None for headers and totals."""
    values = [(c or "").replace("\n", " ").strip() for c in cells]
    values = [v for v in values if v]
    if len(values) < 3 or not ORDINAL.match(values[0]):
        return None
    count = values.pop() if values[-1].isdigit() else "1"
    address_at = next((i for i in range(len(values) - 1, 0, -1) if ADDRESS.search(values[i])), None)
    if address_at is None:
        return None
    name = " ".join(values[1:address_at]) or values[address_at]
    return [values[0].rstrip("."), name, values[address_at], count]


def pdf_table(content):
    """BIP lists in PDF change their column layout from page to page (merged cells, dropped columns), so every row
    is read by meaning instead of position: number, name, address (a street with a number), AED count."""
    import pdfplumber

    rows = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    parsed = pdf_row(row)
                    if parsed:
                        rows.append(parsed)
    return Table(list(PDF_HEADER), rows, [])
