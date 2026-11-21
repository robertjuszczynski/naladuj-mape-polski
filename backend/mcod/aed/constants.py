import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


class RecordStatus:
    READY = "ready"
    INCOMPLETE = "incomplete"
    NEEDS_DECISION = "needs_decision"
    NEEDS_FIX = "needs_fix"
    HELD = "held"

    LABELS = {
        READY: "Gotowy",
        INCOMPLETE: "Niepełny",
        NEEDS_DECISION: "Do decyzji",
        NEEDS_FIX: "Do poprawy",
        HELD: "Wstrzymany",
    }
    CHOICES = tuple(LABELS.items())
    PUBLISHABLE = (READY, INCOMPLETE, NEEDS_DECISION)
    BLOCKED = (NEEDS_FIX, HELD)
    BADGE_CLASSES = {READY: "aed-ok", NEEDS_FIX: "aed-bad", HELD: "aed-bad"}
    DEFAULT_BADGE_CLASS = "aed-warn"


class Decision:
    ACCEPT = "accept"
    HOLD = "hold"
    RESTORE = "restore"
    FIX = "fix"


class Severity:
    ERROR = "error"
    WARNING = "warning"


class IssueCode:
    PERSONAL_DATA = "personal_data"
    MISSING_REQUIRED = "missing_required"
    BAD_FORMAT = "bad_format"
    MISSING_HOURS = "missing_hours"
    OUTSIDE_POLAND = "outside_poland"
    OUTSIDE_MUNICIPALITY = "outside_municipality"
    NEAR_BORDER = "near_municipality_border"
    DUPLICATE_POINT = "duplicate_point"
    SWAPPED_COORDINATES = "swapped_coordinates"


class Availability:
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"
    FAULTY = "faulty"


class TaskKind:
    INSPECTION = "inspection"
    ELECTRODES = "electrodes"
    BATTERY = "battery"
    MISSING_HOURS = "missing_hours"
    MISSING_LOCATION = "missing_location"
    REPORT = "report"

    DATE_FIELDS = {
        INSPECTION: "data_ostatniego_przegladu",
        ELECTRODES: "data_waznosci_elektrod",
        BATTERY: "data_waznosci_baterii",
    }
    CHOICES = (
        (INSPECTION, "Przegląd"),
        (ELECTRODES, "Elektrody"),
        (BATTERY, "Bateria"),
        (MISSING_HOURS, "Brak godzin dostępności"),
        (MISSING_LOCATION, "Brak opisu miejsca"),
        (REPORT, "Zgłoszenie obywatela"),
    )


class TaskStatus:
    OPEN = "open"
    DONE = "done"
    DISMISSED = "dismissed"

    CHOICES = ((OPEN, "Do zrobienia"), (DONE, "Zrobione"), (DISMISSED, "Odrzucone"))


class ReportType:
    """The report options of the AED page."""

    NOT_WORKING = "not_working"
    CLOSED = "inaccessible"
    MISSING = "no_device"
    WRONG_LOCATION = "wrong_location"
    OTHER = "other"

    LABELS = {
        NOT_WORKING: "AED nie działa lub jest uszkodzony",
        CLOSED: "AED jest zamknięty lub niedostępny",
        MISSING: "Nie ma tu urządzenia",
        WRONG_LOCATION: "Zła lokalizacja na mapie",
        OTHER: "Inny problem",
    }


class RecordWarning:
    INSPECTION_OVERDUE = "inspection_overdue"
    ELECTRODES_EXPIRED = "electrodes_expired"
    BATTERY_EXPIRED = "battery_expired"
    REPORTED = "reported"


class UploadStatus:
    DRAFT = "draft"
    PUBLISHED = "published"

    CHOICES = ((DRAFT, "Szkic"), (PUBLISHED, "Opublikowany"))


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = (".csv", ".xlsx")
MAX_UPLOAD_ROWS = 5000
COLUMN_SAMPLE_SIZE = 3

GEOCODE_LIMIT = 200
GEOCODE_TIMEOUT_S = 3
GEOCODE_WORKERS = 8
GEOCODE_CACHE_TTL_S = 7 * 24 * 3600

POLAND_BBOX = {"min_lat": 49.0, "max_lat": 54.9, "min_lon": 14.1, "max_lon": 24.2}
BOUNDARY_TOLERANCE_M = 1000
DUPLICATE_COORDINATE_DECIMALS = 5
QUALITY_EXAMPLES = 5
NIGHT_HOUR = 3

TASK_LEAD_DAYS = 30
INSPECTION_INTERVAL_DAYS = 365
REPORT_RATE_LIMIT = 10
REPORT_RATE_WINDOW_S = 3600

STATS_CACHE_KEY = "aed:stats:v2"
STATS_CACHE_TTL_S = 300

NATIONAL_ORG_TITLE = "Departament Zarządzania Danymi – Ministerstwo Cyfryzacji"
AED_TAG_NAMES = ("AED", "defibrylator", "Naładuj mapę Polski")

# Municipalities per voivodeship (TERYT, GUS); the voivodeship code is the first two digits of a municipality code.
VOIVODESHIPS = {
    "02": ("dolnośląskie", 169),
    "04": ("kujawsko-pomorskie", 144),
    "06": ("lubelskie", 213),
    "08": ("lubuskie", 82),
    "10": ("łódzkie", 177),
    "12": ("małopolskie", 182),
    "14": ("mazowieckie", 314),
    "16": ("opolskie", 71),
    "18": ("podkarpackie", 160),
    "20": ("podlaskie", 118),
    "22": ("pomorskie", 123),
    "24": ("śląskie", 167),
    "26": ("świętokrzyskie", 102),
    "28": ("warmińsko-mazurskie", 116),
    "30": ("wielkopolskie", 226),
    "32": ("zachodniopomorskie", 113),
}
# Municipality code without the last (type) digit, so an urban-rural municipality counts once.
MUNICIPALITY_CODE_LENGTH = 6
