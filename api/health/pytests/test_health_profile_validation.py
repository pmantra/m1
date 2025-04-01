import pytest
from marshmallow import ValidationError

from health.models.health_profile import LIFE_STAGES, HealthProfileActivityLevel
from health.resources.health_profile import HealthProfileSchema


class TestValidHealthProfileValidation:
    @pytest.mark.parametrize(
        ("field_name", "value"),
        [
            ("birthday", "1990-03-18"),
            ("number_of_pregnancies", 2),
            ("due_date", "2016-06-16"),
            ("health_issues_current", "flu"),
            ("life_stage", 1),
        ],
    )
    def test_valid_field_inputs(self, field_name, value):
        try:
            HealthProfileSchema().load({field_name: value})
        except ValidationError as e:
            raise AssertionError(e)

    def test_activity_levels(self):
        levels = [
            HealthProfileActivityLevel.__dict__[k]
            for k in HealthProfileActivityLevel.__dict__.keys()
            if not k.startswith("__")
        ]
        hsp = HealthProfileSchema()
        try:
            for level in levels:
                hsp.load({"activity_level": level})
        except ValidationError as e:
            raise AssertionError(e)

    def test_life_stage(self):
        stage_ids = [s["id"] for s in LIFE_STAGES]
        hsp = HealthProfileSchema()
        try:
            for stage_id in stage_ids:
                hsp.load({"life_stage": stage_id})
        except ValidationError as e:
            raise AssertionError(e)


class TestInvalidHealthProfileValidation:
    @pytest.mark.parametrize(
        ("field_name", "value"),
        [
            # ("birthday", "2016-03-18T23:59:59"),
            # ("birthday", "2016-03-18T23:59:59.130822-08:00"),
            ("number_of_pregnancies", True),
            ("due_date", 2022),
            ("due_date", "YYYY-MM-dd-HH:MM:ss"),
            ("health_issues_current", 12),
            ("life_stage", "one"),
        ],
    )
    def test_invalid_field_inputs(self, field_name, value):
        with pytest.raises(ValidationError):
            HealthProfileSchema().load({field_name: value})

    @pytest.mark.parametrize("invalid_input", ["not_a_level", False, 1])
    def test_invalid_activity_level(self, invalid_input):
        with pytest.raises(ValidationError):
            HealthProfileSchema().load({"activity_level": invalid_input})

    @pytest.mark.parametrize("invalid_input", ["not_a_life_stage", False, -1])
    def test_invalid_life_stage(self, invalid_input):
        with pytest.raises(ValidationError):
            HealthProfileSchema().load({"life_stage": invalid_input})


def test_health_profile_backwards_compatibility():
    health_profile = {
        "abortions": 0,
        "activity_level": "",
        "birthday": "",
        "children": [],
        "due_date": "",
        "food_allergies": "",
        "full_term_babies": 0,
        "gender": "",
        "health_issues_current": "",
        "health_issues_past": "",
        "height": 0,
        "insurance": "",
        "life_stage": 1,
        "medications_allergies": "",
        "medications_current": "",
        "medications_past": "",
        "miscarriages": 0,
        "number_of_pregnancies": 0,
        "premature_babies": 0,
        "weight": 0,
    }
    try:
        HealthProfileSchema().load(health_profile)
    except ValidationError as exc:
        raise AssertionError(exc)
