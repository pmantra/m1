from unittest import mock

import pycountry
import pytest
from sqlalchemy.exc import IntegrityError

from authn.models import user
from pytests import factories
from storage.connection import db


@pytest.mark.parametrize(
    argnames="options,password",
    argvalues=[
        ({}, "password##*$&(#&*Q^R%T*QRFNJIfhw87fewyfiubwf"),
        (
            {"last_name": "時習之，不亦說乎？有朋 Ἰοὺ ἰού· τὰ πάντʼ"},
            "password##*$&(#&*Q^R不亦%T*QRFNJIfhw87fewyfiubwf",
        ),
    ],
    ids=["ascii", "unicode"],
)
def test_user_save(options: dict, password: str):
    # Given
    built = factories.DefaultUserFactory.build(**options)
    # When
    db.session.add(built)
    db.session.commit()
    fetched = db.session.query(user.User).first()
    # Then
    assert (
        fetched
        and fetched.api_key
        and (
            fetched.id,
            fetched.first_name,
            fetched.last_name,
            fetched.email,
        )
        == (
            built.id,
            built.first_name,
            built.last_name,
            built.email,
        )
    )


def test_unique_api_key():
    # Given
    batch = factories.DefaultUserFactory.create_batch(size=2)
    api_keys = {u.api_key for u in batch}
    # Then
    assert len(api_keys) == len(batch)


@pytest.mark.parametrize(
    argnames="options",
    argvalues=[
        {"username": "hyruleprincess84"},
        {"email": "zelda@hyrule-mail.com"},
    ],
    ids=["username", "email"],
)
def test_unique_constraints(options: dict):
    # When/Then
    with pytest.raises(IntegrityError):
        factories.DefaultUserFactory.create_batch(size=2, **options)


@pytest.mark.parametrize(
    argnames="subdivision_code,subdivision",
    argvalues=[
        ("US-NY", pycountry.subdivisions.get(code="US-NY")),
        ("US-NEWYORK", None),
        (None, None),
    ],
)
def test_subdivision(subdivision_code, subdivision):
    # Given
    u = factories.DefaultUserFactory.create()

    # When
    u.subdivision_code = subdivision_code

    # Then
    assert u.subdivision == subdivision


@pytest.mark.parametrize(
    argnames="user,first_name,last_name,middle_name,zendesk_user_id,esp_id",
    argvalues=[
        (
            factories.MemberFactory,
            "new first name",
            "new last name",
            "new middle_name",
            12345,
            "esp_id_new",
        ),
        (factories.MemberFactory, None, None, None, None, None),
        (
            factories.PractitionerUserFactory,
            "new first name",
            "new last name",
            "new middle_name",
            12345,
            "esp_id_new",
        ),
        (factories.PractitionerUserFactory, None, None, None, None, None),
    ],
)
def test_profile_fields_updated(
    user, first_name, last_name, middle_name, zendesk_user_id, esp_id
):
    # Given
    u = user.create()

    # When
    u.first_name = first_name
    u.last_name = last_name
    u.middle_name = middle_name
    u.zendesk_user_id = zendesk_user_id
    u.esp_id = esp_id

    # Then
    mp = u.member_profile
    if mp:
        assert u.first_name == mp.first_name
        assert u.middle_name == mp.middle_name
        assert u.last_name == mp.last_name
        assert u.zendesk_user_id == mp.zendesk_user_id
        assert u.esp_id == mp.esp_id
    pp = u.practitioner_profile
    if pp:
        assert u.first_name == pp.first_name
        assert u.middle_name == pp.middle_name
        assert u.last_name == pp.last_name
        assert u.zendesk_user_id == pp.zendesk_user_id
        assert u.esp_id == pp.esp_id


@mock.patch("tracks.service.TrackSelectionService.get_organization_for_user")
def test_organization_v2(mock_get_organization_for_user, default_user):  #

    #  Given
    mocked_org_id = 100
    org = mock.MagicMock(id=mocked_org_id)
    mock_get_organization_for_user.return_value = org

    # When
    returned_user_org = default_user.organization_v2

    # Then
    mock_get_organization_for_user.assert_called_once_with(user_id=default_user.id)
    assert returned_user_org == org


@mock.patch(
    "messaging.services.zendesk.should_update_zendesk_user_profile", return_value=False
)
@mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
def test_update_zendesk_user_on_attrs_update__ff_off(
    mock_update_zendesk_user,
    mock_should_update_zendesk_user_profile,
):

    # Given a user that has updated to their email
    user = factories.MemberFactory.create()
    user.email = "new_maven_email@mavenclinic.com"

    # When
    # `after_update` only happens after a flush and commit so manually commit to the db to trigger it
    db.session.commit()

    # Then
    mock_update_zendesk_user.assert_not_called()


@mock.patch(
    "messaging.services.zendesk.should_update_zendesk_user_profile", return_value=True
)
@mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
def test_update_zendesk_user_on_attrs_update__no_fields_updated(
    mock_update_zendesk_user,
    mock_should_update_zendesk_user_profile,
):

    # Given a user that has no updates to their attributes
    factories.MemberFactory.create()

    # When
    # `after_update` only happens after a flush and commit so manually commit to the db to trigger it
    db.session.commit()

    # Then
    mock_update_zendesk_user.assert_not_called()


@mock.patch(
    "messaging.services.zendesk.should_update_zendesk_user_profile", return_value=True
)
@mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
def test_update_zendesk_user_on_attrs_update__user_is_a_practitioner(
    mock_update_zendesk_user,
    mock_should_update_zendesk_user_profile,
):

    # Given a user that has updates to their attributes but they are a practitioner
    user = factories.PractitionerUserFactory.create()
    user.email = "new_maven_email@mavenclinic.com"

    # When
    # `after_update` only happens after a flush and commit so manually commit to the db to trigger it
    db.session.commit()

    # Then
    mock_update_zendesk_user.assert_not_called()


@mock.patch(
    "messaging.services.zendesk.should_update_zendesk_user_profile", return_value=True
)
@mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
def test_update_zendesk_user_on_attrs_update__attributes_that_dont_get_propagated_to_zd_have_been_updated(
    mock_update_zendesk_user,
    mock_should_update_zendesk_user_profile,
):
    # Given a user with an updated field that is not one of the ones that gets propagated to zd
    user = factories.MemberFactory.create()
    user.timezone = "best_timezone"

    # When
    # `after_update` only happens after a flush and commit so manually commit to the db to trigger it
    db.session.commit()

    # Then
    mock_update_zendesk_user.assert_not_called()


@pytest.mark.parametrize("field_updated", ["email", "first_name", "last_name"])
@mock.patch(
    "messaging.services.zendesk.should_update_zendesk_user_profile", return_value=True
)
@mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
def test_update_zendesk_user_on_attrs_update__attributes_that_get_propagated_to_zd_have_been_updated(
    mock_update_zendesk_user,
    mock_should_update_zendesk_user_profile,
    field_updated,
):
    # Given a user with an updated field
    user = factories.MemberFactory.create()
    if field_updated == "email":
        user.email = "new_maven_email@mavenclinic.com"
    elif field_updated == "first_name":
        user.first_name = "new first name"
    elif field_updated == "last_name":
        user.last_name = "new last name"

    # When
    # `after_update` only happens after a flush and commit so manually commit to the db to trigger it
    db.session.commit()

    # Then
    mock_update_zendesk_user.assert_called_once_with(
        user_id=user.id,
        update_identity="email" if field_updated == "email" else "name",
        team_ns="virtual_care",
        caller="update_zendesk_user_on_attrs_update",
    )
