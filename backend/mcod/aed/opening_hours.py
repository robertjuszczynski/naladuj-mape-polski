"""Opening hours in the OpenStreetMap opening_hours format: parsing Polish descriptions, validation and open-at checks."""

import re

WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
ALWAYS_OPEN = "24/7"
CLOSED_WORDS = ("off", "closed")

_DAY = r"(%s|PH)" % "|".join(WEEKDAYS)
_WEEKDAY = r"\b(%s)\b" % "|".join(WEEKDAYS)
_DAYS = r"%s(-%s)?(,%s(-%s)?)*" % (_DAY, _DAY, _DAY, _DAY)
_TIME = r"([01]\d|2[0-4]):[0-5]\d"
_TIMES = r"%s-%s(,%s-%s)*" % (_TIME, _TIME, _TIME, _TIME)
_RULE = re.compile(r"^(%s )?(%s|off|closed)$" % (_DAYS, _TIMES))
_SPEC_START = re.compile(r"^(%s|%s)" % ("|".join(WEEKDAYS + ("PH",)), re.escape(ALWAYS_OPEN)))
_RANGE = r"\s*(?:-|–|do)\s*"
_POLISH_SHORT_DAYS = dict(zip(WEEKDAYS + ("PH",), ("pn", "wt", "śr", "czw", "pt", "sob.", "nd", "święta")))

_POLISH_DAY_WORDS = (
    (r"poniedzia[łl]\w*", "Mo"),
    (r"wtor\w*", "Tu"),
    (r"[śs]rod\w*", "We"),
    (r"czwart\w*", "Th"),
    (r"pi[ąa]t\w*", "Fr"),
    (r"sobot\w*", "Sa"),
    (r"niedziel\w*", "Su"),
    (r"\b(pn|pon)\b\.?", "Mo"),
    (r"\bwt\b\.?", "Tu"),
    (r"\b(śr|sr)\b\.?", "We"),
    (r"\bczw\b\.?", "Th"),
    (r"\bpt\b\.?", "Fr"),
    (r"\b(sob|so)\b\.?", "Sa"),
    (r"\b(nd|ndz|niedz|ni)\b\.?", "Su"),
)
_ALWAYS_OPEN_TEXT = re.compile(r"24\s*/\s*7|ca[łl]odob|ca[łl]ą dob[ęe]|24h", re.I)
_WORKDAYS_TEXT = re.compile(
    r"dni powszednie|dni robocze|pon(\.|iedzia[łl]\w*)?%spi[ąa]t|od poniedzia[łl]ku do pi[ąa]tku" % _RANGE
)
_EVERY_DAY_TEXT = re.compile(r"codziennie|ca[łl]y tydzie[ńn]|7 dni")
_TIME_RANGE_TEXT = re.compile(r"(?<![\d.])(\d{1,2})(?:[:.](\d{2}))?%s(\d{1,2})(?:[:.](\d{2}))?(?![\d.])" % _RANGE)


class OpeningHours:
    @staticmethod
    def is_valid(spec):
        spec = spec.strip()
        return spec == ALWAYS_OPEN or all(_RULE.match(rule.strip()) for rule in spec.split(";"))

    @staticmethod
    def looks_like_spec(text):
        return bool(_SPEC_START.match(text))

    @staticmethod
    def to_polish(spec):
        """Readable Polish form: "Mo-Fr 08:00-16:00; Sa 09:00-14:00" -> "pn–pt 8:00–16:00; sob. 9:00–14:00"."""
        spec = (spec or "").strip()
        if spec == ALWAYS_OPEN:
            return "całodobowo"
        if not spec or not OpeningHours.is_valid(spec):
            return spec

        def day(code):
            return _POLISH_SHORT_DAYS.get(code, code)

        def time(value):
            return value.lstrip("0") if not value.startswith("00") else value[1:]

        rules = []
        for rule in [r.strip() for r in spec.split(";")]:
            days, _, ranges = rule.rpartition(" ")
            days = "" if days == "Mo-Su" else days
            days_text = ", ".join("–".join(day(d) for d in part.split("-")) for part in days.split(",")) if days else "codziennie"
            if ranges in CLOSED_WORDS:
                hours_text = "nieczynne"
            else:
                hours_text = ", ".join("–".join(time(t) for t in r.split("-")) for r in ranges.split(","))
            rules.append("%s %s" % (days_text, hours_text))
        return "; ".join(rules)

    @classmethod
    def from_polish(cls, text):
        """Turns "pn-pt 7-18, sob. 9-14" into "Mo-Fr 07:00-18:00; Sa 09:00-14:00"; None if it cannot be parsed."""
        text = (text or "").strip()
        if not text:
            return None
        if _ALWAYS_OPEN_TEXT.search(text):
            return ALWAYS_OPEN
        rules = []
        for part in [p.strip() for p in re.split(r"[;,\n]", text) if p.strip()]:
            rule = cls._polish_rule(part)
            if rule is None:
                return None
            rules.append(rule)
        return "; ".join(rules) or None

    @classmethod
    def _polish_rule(cls, part):
        tm = _TIME_RANGE_TEXT.search(part)
        if not tm or int(tm.group(1)) > 24 or int(tm.group(3)) > 24:
            return None
        days = cls._polish_days(part)
        if not days:
            return None
        return "%s %s:%s-%s:%s" % (days, tm.group(1).zfill(2), tm.group(2) or "00", tm.group(3).zfill(2), tm.group(4) or "00")

    @staticmethod
    def _polish_days(part):
        low = part.lower()
        if _WORKDAYS_TEXT.search(low):
            return "Mo-Fr"
        if _EVERY_DAY_TEXT.search(low):
            return "Mo-Su"
        coded = part
        for pattern, code in _POLISH_DAY_WORDS:
            coded = re.sub(pattern, code, coded, flags=re.I)
        span = re.search(_WEEKDAY + _RANGE + _WEEKDAY, coded)
        if span:
            return "%s-%s" % (span.group(1), span.group(2))
        single = re.search(_WEEKDAY, coded)
        return single.group(1) if single else None

    @classmethod
    def is_open_at(cls, spec, when):
        """True/False by the rules; None when hours are missing or unreadable."""
        spec = (spec or "").strip()
        if not spec:
            return None
        if spec == ALWAYS_OPEN:
            return True
        day, minute = when.weekday(), when.hour * 60 + when.minute
        result = False
        for rule in [r.strip() for r in spec.split(";")]:
            match = re.match(r"^(?:([A-Za-z,-]+)\s+)?(.+)$", rule)
            if not match:
                return None
            days = cls._expand_days(match.group(1)) if match.group(1) else set(range(7))
            if day not in days:
                continue
            if match.group(2) in CLOSED_WORDS:
                result = False
                continue
            hit = cls._in_ranges(match.group(2), minute)
            if hit is None:
                return None
            result = result or hit
        return result

    @staticmethod
    def _in_ranges(ranges, minute):
        hit = False
        for time_range in ranges.split(","):
            start, _, end = time_range.partition("-")
            try:
                start_min = int(start[:2]) * 60 + int(start[3:5])
                end_min = int(end[:2]) * 60 + int(end[3:5])
            except ValueError:
                return None
            if start_min <= minute < end_min if end_min > start_min else (minute >= start_min or minute < end_min):
                hit = True
        return hit

    @staticmethod
    def _expand_days(spec):
        days = set()
        for part in spec.split(","):
            first, _, last = part.partition("-")
            if first not in WEEKDAYS or (last and last not in WEEKDAYS):
                continue
            i, end = WEEKDAYS.index(first), WEEKDAYS.index(last or first)
            days.add(i)
            while i != end:
                i = (i + 1) % 7
                days.add(i)
        return days
