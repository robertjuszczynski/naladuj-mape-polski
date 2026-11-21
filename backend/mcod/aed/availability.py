import datetime

from mcod.aed.constants import NIGHT_HOUR, Availability
from mcod.aed.opening_hours import OpeningHours


def availability_at(record, when):
    if record.get("sprawny") == "false":
        return Availability.OUT_OF_ORDER
    if record.get("dostepny_calodobowo") == "true":
        return Availability.OPEN
    is_open = OpeningHours.is_open_at(record.get("godziny_dostepnosci"), when)
    if is_open is None:
        return Availability.UNKNOWN
    return Availability.OPEN if is_open else Availability.CLOSED


def night_of(now):
    """Najbliższa noc (godzina NIGHT_HOUR) od chwili now."""
    day = now + datetime.timedelta(days=1) if now.hour >= NIGHT_HOUR else now
    return day.replace(hour=NIGHT_HOUR, minute=0, second=0, microsecond=0)
