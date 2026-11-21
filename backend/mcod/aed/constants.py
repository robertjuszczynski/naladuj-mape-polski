import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


class RecordStatus:
    READY = "gotowy"
    INCOMPLETE = "niepelny"
    NEEDS_DECISION = "do_decyzji"
    NEEDS_FIX = "do_poprawy"
    HELD = "wstrzymany"

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
    ACCEPT = "akceptuj"
    HOLD = "wstrzymaj"
    RESTORE = "przywroc"
    FIX = "popraw"


class Severity:
    ERROR = "blad"
    WARNING = "ostrzezenie"


class IssueCode:
    PERSONAL_DATA = "dane_osobowe"
    MISSING_REQUIRED = "brak_wymaganego"
    BAD_FORMAT = "zly_format"
    MISSING_HOURS = "brak_godzin"
    OUTSIDE_POLAND = "poza_polska"
    OUTSIDE_MUNICIPALITY = "poza_gmina"
    NEAR_BORDER = "przy_granicy_gminy"
    DUPLICATE_POINT = "duplikat_punktu"
    SWAPPED_COORDINATES = "zamiana_wspolrzednych"


class Availability:
    OPEN = "otwarte"
    CLOSED = "zamkniete"
    UNKNOWN = "nieznane"
    OUT_OF_ORDER = "niesprawny"


class UploadStatus:
    DRAFT = "szkic"
    PUBLISHED = "opublikowany"

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

STATS_CACHE_KEY = "aed:stats"
STATS_CACHE_TTL_S = 300

PROFILE_KEY = "aed_profil"
NATIONAL_KEY = "aed_zbior_ogolnopolski"
NATIONAL_ORG_TITLE = "Departament Zarządzania Danymi – Ministerstwo Cyfryzacji"
AED_TAG_NAMES = ("AED", "defibrylator", "Naładuj mapę Polski")
FOREIGN_TAG_NAMES = ("aed", "defibrylator", "defibrylatory", "defibrylatory aed")

# Liczba gmin w województwach wg TERYT (GUS); kod województwa to pierwsze dwie cyfry kodu gminy.
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
# Kod gminy bez ostatniej cyfry (rodzaju gminy), żeby gmina miejsko-wiejska liczyła się raz.
MUNICIPALITY_CODE_LENGTH = 6
