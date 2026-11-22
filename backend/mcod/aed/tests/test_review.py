from mcod.aed.constants import Decision, RecordStatus
from mcod.aed.review import ACCEPTED_BY_INSTITUTION, HELD_BY_INSTITUTION, UploadReview
from mcod.aed.tests.helpers import import_test_file

ORGANIZATION = "Urząd Miasta Marki"


def review_of(name="06-mieszany-dobre-i-zle.csv"):
    return UploadReview(import_test_file(name), {}, ORGANIZATION)


def duplicate_indexes(review):
    return [i for i, row in enumerate(review.checked) if row["status"] == RecordStatus.NEEDS_DECISION]


def published_names(review):
    return {r["nazwa_obiektu"] for r in review.rows_for_publish()}


def test_rows_needing_decision_are_not_published_without_accept():
    review = review_of()
    duplicates = duplicate_indexes(review)
    assert len(duplicates) == 2
    published = review.rows_for_publish()
    assert not any(review.checked[i]["record"] in published for i in duplicates)
    assert review.summary()["pending"] == 2


def test_accept_publishes_only_the_accepted_duplicate():
    review = review_of()
    first, second = duplicate_indexes(review)
    before = len(review.rows_for_publish())
    assert review.apply_decision(first, Decision.ACCEPT)
    published = review.rows_for_publish()
    assert len(published) == before + 1
    assert review.checked[first]["record"] in published
    assert review.checked[second]["record"] not in published
    assert review.summary()["pending"] == 1
    assert review.status_label(first, review.checked[first]) == ACCEPTED_BY_INSTITUTION


def test_hold_overrides_accept_and_restore_clears_decision():
    review = review_of()
    first = duplicate_indexes(review)[0]
    review.apply_decision(first, Decision.ACCEPT)
    review.apply_decision(first, Decision.HOLD)
    assert not review.is_published_row(first, review.checked[first])
    assert review.status_label(first, review.checked[first]) == HELD_BY_INSTITUTION
    review.apply_decision(first, Decision.RESTORE)
    assert review.decisions == {}


def test_hold_removes_ready_row_from_publication():
    review = review_of()
    ready = next(i for i, row in enumerate(review.checked) if row["status"] == RecordStatus.READY)
    count = review.summary()["publish"]
    review.apply_decision(ready, Decision.HOLD)
    assert review.summary()["publish"] == count - 1


def test_invalid_decision_is_ignored():
    review = review_of()
    assert not review.apply_decision(len(review.checked), Decision.ACCEPT)
    assert not review.apply_decision(0, "delete")
    assert review.decisions == {}


def test_review_rows_offer_accept_only_for_duplicates():
    rows = review_of().review_rows()
    accept_rows = [r for r in rows if (Decision.ACCEPT, "Zatwierdź") in r["actions"]]
    assert {r["status"] for r in accept_rows} == {RecordStatus.NEEDS_DECISION}
    assert all(not r["publish"] for r in accept_rows)


def test_foreign_operators_are_case_insensitive():
    review = review_of("05-gmina-z-innymi-dysponentami.csv")
    review.own_operator = "urząd miasta marki"
    foreign = review.foreign_operator_rows()
    assert len(foreign) == 2
    assert all(r["dysponent_nazwa"] != ORGANIZATION for r in foreign)


def test_manual_fix_rechecks_record_and_keeps_notes():
    review = review_of()
    index = next(
        i
        for i, row in enumerate(review.checked)
        if row["status"] == RecordStatus.NEEDS_FIX and row["record"].get("nazwa_obiektu")
    )
    notes = list(review.checked[index]["notes"])
    review.apply_decision(index, Decision.FIX, {"szerokosc_geograficzna": " 52.3301 ", "dlugosc_geograficzna": "21.1051"})
    fixed = review.checked[index]
    assert fixed["record"]["szerokosc_geograficzna"] == "52.3301"
    assert fixed["notes"] == notes


def test_manual_fix_covers_every_standard_field_group():
    review = review_of()
    row = review.review_rows()[0]
    titles = {g["title"] for g in row["edit_groups"]}
    assert titles == {"Miejsce", "Dostępność", "Urządzenie", "Dysponent"}
    review.apply_decision(row["index"], Decision.FIX, {"ulica": "Wiejska", "producent": "Philips"})
    record = review.checked[row["index"]]["record"]
    assert (record["ulica"], record["producent"]) == ("Wiejska", "Philips")


def test_group_with_a_problem_comes_first():
    review = review_of()
    blocked = next(r for r in review.review_rows() if r["issues"])
    first = blocked["edit_groups"][0]
    assert first["flagged"] and any(f["flagged"] for f in first["fields"])


def test_manual_fix_sets_hours_with_the_widget():
    review = review_of()
    row = review.review_rows()[0]
    hours = next(g for g in row["edit_groups"] if g["title"] == "Dostępność")["hours"]
    assert hours["mode"] in ("always", "range", "keep")
    values = {"hours_mode": "range", "hours_day": ["Mo", "Tu", "We", "Th", "Fr"], "hours_from": "07:00", "hours_to": "15:00"}
    review.apply_decision(row["index"], Decision.FIX, values)
    record = review.checked[row["index"]]["record"]
    assert (record["godziny_dostepnosci"], record["dostepny_calodobowo"]) == ("Mo-Fr 07:00-15:00", "false")


def test_keep_leaves_hours_untouched():
    review = review_of()
    row = review.review_rows()[0]
    before = review.checked[row["index"]]["record"].get("godziny_dostepnosci")
    review.apply_decision(row["index"], Decision.FIX, {"hours_mode": "keep"})
    assert review.checked[row["index"]]["record"].get("godziny_dostepnosci") == before
