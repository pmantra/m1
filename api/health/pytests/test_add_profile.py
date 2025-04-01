from datetime import date, datetime

import pytest

from authn.models.user import User
from authz.models.roles import ROLES
from health.domain.add_profile import (
    add_name_information_to_profile,
    add_profile_to_user,
    set_country_and_state,
    set_date_of_birth,
)
from health.models.health_profile import HealthProfile
from models.profiles import MemberProfile, PractitionerProfile
from pytests.factories import StateFactory
from storage.connection import db
from utils.passwords import random_password


@pytest.fixture(autouse=True)
def member_role(factories):
    factories.RoleFactory.create(name=ROLES.member)


def test_create_user_with_profile():
    # see authn.resources.user.UsersResource.post
    user_info = {
        "email": "a_test_email@mavenclinic.com",
        "first_name": "Foo",
        "last_name": "Bar",
        "password": "kxパスワードfghs密码👌394",
    }
    user = User(
        first_name=user_info["first_name"],
        last_name=user_info["last_name"],
        email=user_info["email"],
        password=random_password(),
    )
    db.session.add(user)
    assert user.health_profile is None

    add_profile_to_user(user)
    db.session.flush()
    assert user.health_profile is not None
    assert user.health_profile.json == {}


def test_add_name_information_to_member_profile():
    # Given
    profile = MemberProfile()
    assert not profile.first_name
    assert not profile.last_name
    first_name = "John"
    last_name = "Rosencrantz"
    middle_name = "Authur"

    # When
    add_name_information_to_profile(
        profile=profile,
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
    )

    # Then
    assert profile.first_name == first_name
    assert profile.last_name == last_name
    assert profile.middle_name == middle_name


def test_add_name_information_to_practitioner_profile():
    # Given
    profile = PractitionerProfile()
    assert not profile.first_name
    assert not profile.last_name
    first_name = "Jane"
    last_name = "Guildenstern"
    middle_name = "Agnes"

    # When
    add_name_information_to_profile(
        profile=profile,
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
    )

    # Then
    assert profile.first_name == first_name
    assert profile.last_name == last_name
    assert profile.middle_name == middle_name


@pytest.mark.parametrize(
    argnames="dob_input",
    argvalues=[
        pytest.param("1993-05-21"),
        pytest.param(date(1993, 5, 21)),
        pytest.param(datetime(1993, 5, 21)),
    ],
)
def test_set_date_of_birth_success(dob_input):
    # Given
    health_profile = HealthProfile()
    expected_birthday = date(1993, 5, 21)

    # When
    updated_health_profile = set_date_of_birth(health_profile, dob_input)

    # Then
    assert updated_health_profile.birthday == expected_birthday


def test_set_date_of_birth_parsing_error():
    # Given
    health_profile = HealthProfile()
    dob_str = "05-21-1993"

    # When
    with pytest.raises(
        Exception, match="Exception encountered while trying to parse date of birth"
    ):
        _ = set_date_of_birth(health_profile, dob_str)


def test_set_country_and_state():
    # Given
    member_profile = MemberProfile()
    StateFactory.create(name="California", abbreviation="CA")

    # When
    updated_profile = set_country_and_state(
        member_profile=member_profile, country="US", state="CA"
    )

    # Then
    assert updated_profile.country.alpha_2 == "US"
    assert updated_profile.state.abbreviation == "CA"
