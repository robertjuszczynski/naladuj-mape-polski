"""Opening hours chosen with buttons: "Całą dobę", or day buttons with one range or a range per day."""

import re

from mcod.aed.opening_hours import ALWAYS_OPEN

DAY_SPANS = {"everyday": "Mo-Su", "workdays": "Mo-Fr", "monsat": "Mo-Sa"}
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

WEEK = (
    ("Mo", "Pn", "Poniedziałek"),
    ("Tu", "Wt", "Wtorek"),
    ("We", "Śr", "Środa"),
    ("Th", "Cz", "Czwartek"),
    ("Fr", "Pt", "Piątek"),
    ("Sa", "Sb", "Sobota"),
    ("Su", "Nd", "Niedziela"),
)
DEFAULT_DAYS = ("Mo", "Tu", "We", "Th", "Fr")
DEFAULT_FROM, DEFAULT_TO = "08:00", "16:00"


def _times(start, end):
    start, end = (start or "").strip(), (end or "").strip()
    return (start, end) if TIME.match(start) and TIME.match(end) and start != end else None


def _group(ranges):
    """[("Mo", "08:00", "16:00"), ...] -> "Mo-Fr 08:00-16:00; Sa 09:00-14:00" (consecutive days with equal hours merge)."""
    codes = [code for code, _, _ in WEEK]
    groups = []
    for code, start, end in ranges:
        last = groups[-1] if groups else None
        if last and last["hours"] == (start, end) and codes.index(code) == codes.index(last["to"]) + 1:
            last["to"] = code
        else:
            groups.append({"from": code, "to": code, "hours": (start, end)})
    return "; ".join(
        "%s %s-%s" % (g["from"] if g["from"] == g["to"] else "%s-%s" % (g["from"], g["to"]), *g["hours"]) for g in groups
    )


def hours_spec(values):
    """ "24/7", or the chosen days with their hours; "" when a chosen day has no valid range."""
    if values.get("hours_mode") == "always":
        return ALWAYS_OPEN
    if values.get("hours_days") in DAY_SPANS:
        times = _times(values.get("hours_from"), values.get("hours_to"))
        return "%s %s-%s" % (DAY_SPANS[values["hours_days"]], *times) if times else ""
    days = values.getlist("hours_day") if hasattr(values, "getlist") else values.get("hours_day", [])
    per_day = bool(values.get("hours_per_day"))
    ranges = []
    for code, _, _ in WEEK:
        if code not in days:
            continue
        times = _times(values.get("from_" + code), values.get("to_" + code)) if per_day else None
        times = times or (None if per_day else _times(values.get("hours_from"), values.get("hours_to")))
        if times is None:
            return ""
        ranges.append((code,) + times)
    return _group(ranges)


def week_rows(values, days):
    return [
        {
            "code": code,
            "short": short,
            "name": name,
            "on": code in days,
            "start": values.get("from_" + code) or values.get("hours_from") or DEFAULT_FROM,
            "end": values.get("to_" + code) or values.get("hours_to") or DEFAULT_TO,
        }
        for code, short, name in WEEK
    ]
