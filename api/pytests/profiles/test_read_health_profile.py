import json

import pytest
from dateutil.parser import parse

from health.models.health_profile import HealthProfile, HealthProfileHelpers
from storage.connection import db
from utils.age import calculate_age

BIRTHDAY = "1990-01-01"
HEIGHT = 66
WEIGHT = 130
DUE_DATE = "2022-01-01"
FIRST_CHILD_BIRTHDAY = "2020-02-01"
SECOND_CHILD_BIRTHDAY = "2021-01-02"


@pytest.fixture
def child_list():
    return [
        {"id": "abc123", "name": "younger", "birthday": FIRST_CHILD_BIRTHDAY},
        {"id": "def456", "name": "older", "birthday": SECOND_CHILD_BIRTHDAY},
    ]


@pytest.fixture()
def user_with_health_profile(factories, child_list):
    health_profile = {
        "birthday": BIRTHDAY,
        "height": HEIGHT,
        "weight": WEIGHT,
        "due_date": DUE_DATE,
        "children": child_list,
    }
    user = factories.DefaultUserFactory.create(id=12345)
    user.health_profile.json = health_profile
    return user


@pytest.fixture()
def user_with_no_children(user_with_health_profile):
    user_with_health_profile.health_profile.json["children"] = None
    return user_with_health_profile


class TestHealthProfile:
    def test_null_profile(self, default_user):
        # Default user has no health profile
        health_profile: HealthProfile = default_user.health_profile

        assert health_profile.age is None
        assert health_profile.height is None
        assert health_profile.weight is None

        # A due date is required and created automatically for the default user
        assert health_profile.due_date is not None

    def test_age_calculation(self, user_with_health_profile):

        health_profile: HealthProfile = user_with_health_profile.health_profile

        assert health_profile.age == calculate_age(parse(BIRTHDAY))
        assert health_profile.height == HEIGHT
        assert health_profile.weight == WEIGHT
        assert health_profile.due_date == parse(DUE_DATE).date()

    def test_children_as_none(self, user_with_no_children):
        health_profile: HealthProfile = user_with_no_children.health_profile
        assert health_profile.children == []

    def test_bmi_calculation(self, user_with_health_profile):
        health_profile: HealthProfile = user_with_health_profile.health_profile

        bmi_dict = {"height": HEIGHT, "weight": WEIGHT}
        assert health_profile.bmi == HealthProfileHelpers.get_bmi_from_json(bmi_dict)

    def test_children_calculation(self, user_with_health_profile, child_list):

        health_profile: HealthProfile = user_with_health_profile.health_profile
        assert health_profile.last_child_birthday == parse(SECOND_CHILD_BIRTHDAY).date()
        assert len(health_profile.children) == len(child_list)

        children_with_age = health_profile.children_with_age
        returned_childrens_ages = [x["age"] for x in children_with_age]
        expected_childrens_ages = [
            HealthProfileHelpers.child_age_repr(parse(x).date())
            for x in [SECOND_CHILD_BIRTHDAY, FIRST_CHILD_BIRTHDAY]
        ]
        assert set(returned_childrens_ages) == set(expected_childrens_ages)


class TestPersistedHealthProfile:
    def test_health_profile_load(self, user_with_health_profile, child_list):

        health_profile: HealthProfile = user_with_health_profile.health_profile

        assert health_profile.age_persisted is None
        assert health_profile.bmi_persisted is None
        assert health_profile.children_persisted == "[]"
        assert health_profile.children_with_age_persisted == "[]"
        assert health_profile.last_child_birthday_persisted is None

        user_id = user_with_health_profile.id
        db.session.add(user_with_health_profile)

        committed_data: HealthProfile = HealthProfile.query.filter(
            HealthProfile.user_id == user_id
        ).one()
        assert committed_data.age_persisted == calculate_age(parse(BIRTHDAY))

        bmi_dict = {"height": HEIGHT, "weight": WEIGHT}
        assert committed_data.bmi_persisted == HealthProfileHelpers.get_bmi_from_json(
            bmi_dict
        )

        assert isinstance(committed_data.children_persisted, str)
        assert committed_data.children_persisted == json.dumps(child_list)
        assert (
            committed_data.last_child_birthday_persisted
            == parse(SECOND_CHILD_BIRTHDAY).date()
        )

        committed_childrens_ages = [
            x["age"] for x in json.loads(committed_data.children_with_age_persisted)
        ]
        expected_childrens_ages = [
            HealthProfileHelpers.child_age_repr(parse(x).date())
            for x in [SECOND_CHILD_BIRTHDAY, FIRST_CHILD_BIRTHDAY]
        ]
        assert set(committed_childrens_ages) == set(expected_childrens_ages)
