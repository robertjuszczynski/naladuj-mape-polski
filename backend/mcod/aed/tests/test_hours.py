from mcod.aed.hours import form_values, hours_spec


class Form(dict):
    def getlist(self, key):
        return self.get(key, [])


def round_trip(spec):
    values, days = form_values(spec)
    return hours_spec(Form(values, hours_day=days))


def test_always_open():
    assert form_values("24/7")[0] == {"hours_mode": "always"}


def test_one_range_for_chosen_days():
    values, days = form_values("Mo-Fr 08:00-16:00")
    assert days == ["Mo", "Tu", "We", "Th", "Fr"]
    assert (values["hours_from"], values["hours_to"]) == ("08:00", "16:00")
    assert round_trip("Mo-Fr 08:00-16:00") == "Mo-Fr 08:00-16:00"


def test_different_hours_per_day():
    values, days = form_values("Mo-Fr 08:00-16:00; Sa 09:00-14:00")
    assert values["hours_per_day"] == "on"
    assert days[-1] == "Sa"
    assert round_trip("Mo-Fr 08:00-16:00; Sa 09:00-14:00") == "Mo-Fr 08:00-16:00; Sa 09:00-14:00"


def test_complex_spec_is_left_to_the_person():
    assert form_values("Mo-Fr 08:00-12:00,13:00-16:00; PH off") is None
    assert form_values("") is None
