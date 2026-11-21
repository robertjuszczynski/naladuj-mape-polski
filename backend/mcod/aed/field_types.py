"""Typy pól wzorcowego zakresu: normalizacja wartości z pliku, walidacja i reguła weryfikacji jakości portalu."""

import datetime
import re
from collections import namedtuple

from mcod.aed.importing.address import AddressParser
from mcod.aed.opening_hours import OpeningHours
from mcod.aed.profile import ADDRESS_FEATURES

PortalRule = namedtuple("PortalRule", "code label")
TableType = namedtuple("TableType", "type format")

STRING_COLUMN = TableType("string", "default")
NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
INTEGER = re.compile(r"^-?\d+$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PORTAL_DATE = re.compile(r"^[12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(T00:00:00\.000Z)?$")
PHONE = re.compile(r"^(\+48)?\d{9}$")
POSTCODE = re.compile(r"^\d{2}-\d{3}$")
SEVEN_DIGITS = re.compile(r"^\d{7}$")


class FieldType:
    portal_rule = None
    table_type = STRING_COLUMN

    def normalize(self, value, field):
        """Zwraca (wartość, notatka o zmianie albo None)."""
        return value, None

    def error(self, value, field):
        return None

    def portal_valid(self, value):
        return self.error(value, None) is None


class Text(FieldType):
    pass


class Number(FieldType):
    portal_rule = PortalRule("numeric", "Pole numeryczne")

    def portal_valid(self, value):
        return NUMBER.match(value) is not None

    @staticmethod
    def range_error(value, field):
        number = float(value)
        if field.min is not None and number < field.min:
            return "Wartość poniżej %s" % field.min
        if field.max is not None and number > field.max:
            return "Wartość powyżej %s" % field.max
        return None


class Integer(Number):
    table_type = TableType("integer", "default")

    def error(self, value, field):
        if not INTEGER.match(value):
            return "Wymagana liczba całkowita"
        return self.range_error(value, field)


class Decimal(Number):
    table_type = TableType("number", "default")

    def normalize(self, value, field):
        compact = value.replace(" ", "")
        if re.match(r"^-?\d+,\d+$", compact):
            return compact.replace(",", "."), "Przecinek dziesiętny zamieniono na kropkę"
        return compact, None

    def error(self, value, field):
        if "," in value:
            return "Użyj kropki jako separatora dziesiętnego"
        if not NUMBER.match(value):
            return "Wymagana liczba dziesiętna"
        return self.range_error(value, field)


class Boolean(FieldType):
    portal_rule = PortalRule("bool", "Pole wartości logicznych")
    table_type = TableType("boolean", "default")
    TRUE = re.compile(r"^(true|tak|t|yes|y|1|x|✓)$", re.I)
    FALSE = re.compile(r"^(false|nie|n|no|0|-)$", re.I)
    FIELD_WORDS = {"wewnatrz_budynku": ((r"wewn", "true"), (r"zewn", "false"))}

    def normalize(self, value, field):
        if self.TRUE.match(value):
            return "true", self._note(value, "true")
        if self.FALSE.match(value):
            return "false", self._note(value, "false")
        for pattern, result in self.FIELD_WORDS.get(field.name, ()):
            if re.search(pattern, value, re.I):
                return result, self._note(value, result)
        return value, None

    @staticmethod
    def _note(value, result):
        return None if value == result else "„%s” zapisano jako %s" % (value, result)

    def error(self, value, field):
        return None if value in ("true", "false") else "Dozwolone wartości: true, false"

    def portal_valid(self, value):
        return value in ("true", "false", "True", "False", "TRUE", "FALSE")


class Date(FieldType):
    portal_rule = PortalRule("date", "Data")
    table_type = TableType("date", "any")

    def normalize(self, value, field):
        match = re.match(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$", value)
        if match:
            iso = "%s-%s-%s" % (match.group(3), match.group(2).zfill(2), match.group(1).zfill(2))
            return iso, "Datę „%s” zapisano jako %s" % (value, iso)
        match = re.match(r"^(\d{4}-\d{2}-\d{2})[T ]", value)
        if match:
            return match.group(1), None
        return value, None

    def error(self, value, field):
        return None if self._is_date(value) else "Wymagana data w formacie RRRR-MM-DD"

    def portal_valid(self, value):
        return PORTAL_DATE.match(value) is not None

    @staticmethod
    def _is_date(value):
        if not ISO_DATE.match(value):
            return False
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            return False
        return True


class Phone(FieldType):
    portal_rule = PortalRule("phone", "Numer telefonu")

    def normalize(self, value, field):
        digits = re.sub(r"^\+?48(?=\d{9}$)", "", re.sub(r"[^\d+]", "", value))
        if digits != value:
            return digits, "Telefon „%s” zapisano jako %s" % (value, digits)
        return value, None

    def error(self, value, field):
        return None if PHONE.match(value) else "Telefon jako 9 cyfr bez spacji (opcjonalnie +48)"


class Postcode(FieldType):
    portal_rule = PortalRule("pna", "Kod PNA")

    def normalize(self, value, field):
        match = re.match(r"^(\d{2})\s?-?\s?(\d{3})$", value)
        if match and value != "%s-%s" % match.groups():
            return "%s-%s" % match.groups(), "Ujednolicono kod pocztowy"
        return value, None

    def error(self, value, field):
        return None if POSTCODE.match(value) else "Kod pocztowy w formacie 00-000"


class RegistryCode(FieldType):
    def error(self, value, field):
        return None if SEVEN_DIGITS.match(value) else "Kod ma 7 cyfr"


class OpeningHoursType(FieldType):
    def normalize(self, value, field):
        if OpeningHours.looks_like_spec(value):
            return value, None
        spec = OpeningHours.from_polish(value)
        if spec:
            return spec, "Godziny „%s” zapisano jako %s" % (value, spec)
        return value, None

    def error(self, value, field):
        return None if OpeningHours.is_valid(value) else "Godziny w formacie opening_hours, np. Mo-Fr 08:00-16:00"


class Enum(FieldType):
    PREFIX_LENGTH = 5

    def normalize(self, value, field):
        hit = next((x for x in field.values if value.lower().startswith(x[: self.PREFIX_LENGTH])), None)
        if hit and hit != value:
            return hit, "„%s” zapisano jako %s" % (value, hit)
        return value, None

    def error(self, value, field):
        return None if value in field.values else "Dozwolone wartości: %s" % ", ".join(field.values)


class AddressFeature(Enum):
    portal_rule = PortalRule("address_feature", "Cecha adresu")

    def normalize(self, value, field):
        feature, _, _ = AddressParser.split_street(value + " x")
        if feature in ADDRESS_FEATURES and feature != value:
            return feature, "„%s” zapisano jako %s" % (value, feature)
        return value, None

    def portal_valid(self, value):
        return value in ADDRESS_FEATURES


TYPES = {
    "text": Text(),
    "integer": Integer(),
    "decimal": Decimal(),
    "boolean": Boolean(),
    "date": Date(),
    "phone": Phone(),
    "postcode": Postcode(),
    "teryt": RegistryCode(),
    "simc": RegistryCode(),
    "opening_hours": OpeningHoursType(),
    "enum": Enum(),
    "address_feature": AddressFeature(),
}


def type_of(field):
    return TYPES[field.type]
