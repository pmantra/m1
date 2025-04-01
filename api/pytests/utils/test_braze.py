import datetime
import os
from unittest import mock
from unittest.mock import mock_open, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from authz.models.roles import ROLES
from braze import BrazeEvent, client, constants, format_dt
from direct_payment.clinic.pytests.factories import (
    FertilityClinicFactory,
    FertilityClinicLocationFactory,
    FertilityClinicUserProfileFactory,
)
from geography import CountryRepository, SubdivisionRepository
from models.tracks import TrackName
from pytests import factories
from pytests.factories import RoleFactory, RoleProfileFactory
from utils import braze
from utils.braze import (
    LAST_ORGANIZATION_OFFERS_PNP,
    appointment_rescheduled_member,
    is_whitelisted_braze_ip,
    send_event,
    track_user,
    track_user_locale,
)


def test_pregnancy_available_attr(factories):
    organization = factories.OrganizationFactory.create()
    pregnancy_client_track = factories.ClientTrackFactory.create(
        organization=organization, track=TrackName.PREGNANCY
    )
    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(
        user=user, name=TrackName.PREGNANCY, client_track=pregnancy_client_track
    )

    pregnancy_client_track.active = False
    user_attrs = braze.build_user_attrs(user)
    attrs = user_attrs.attributes
    assert attrs["pregnancy_available"] is False

    pregnancy_client_track.active = True
    user_attrs = braze.build_user_attrs(user)
    attrs = user_attrs.attributes
    assert attrs["pregnancy_available"] is True


def test_last_organization_offers_pnp_when_no_active_track(factories):
    member = factories.EnterpriseUserFactory.create(
        enabled_tracks=["parenting_and_pediatrics"]
    )
    for t in member.active_tracks:
        t.ended_at = datetime.datetime.utcnow()

    user_attrs = braze.build_user_attrs(member)
    attrs = user_attrs.attributes

    assert attrs[LAST_ORGANIZATION_OFFERS_PNP] is True


def test_last_organization_offers_pnp_is_false(factories):
    member = factories.EnterpriseUserFactory.create(enabled_tracks=["pregnancy"])

    user_attrs = braze.build_user_attrs(member)
    attrs = user_attrs.attributes

    assert attrs[LAST_ORGANIZATION_OFFERS_PNP] is False


def test_braze_fertility_clinic_attributes_multiple_clinics_locations():
    # Arrange
    user = factories.DefaultUserFactory.create()
    fertility_clinic = FertilityClinicFactory.create()
    fertility_clinic_2 = FertilityClinicFactory.create()
    fc_location_2 = FertilityClinicLocationFactory.create(
        name="name 2",
        address_1="456 Second Ave",
        city="San Francisco",
        subdivision_code="US-CA",
        postal_code="99999",
        country_code="US",
        fertility_clinic=fertility_clinic,
    )
    fc_2_location_2 = FertilityClinicLocationFactory.create(
        name="fc 2 name 2",
        address_1="6 Pancras Square",
        city="London",
        subdivision_code="GB-LND",
        postal_code="N1C 4AG",
        country_code="GB",
        fertility_clinic=fertility_clinic_2,
    )
    fertility_clinic_user_profile = FertilityClinicUserProfileFactory.create(
        user_id=user.id, clinics=[fertility_clinic, fertility_clinic_2]
    )
    fc_role = RoleFactory.create(name=ROLES.fertility_clinic_user)
    RoleProfileFactory.create(role=fc_role, user=user)

    # Act
    user_attrs = braze.braze_fertility_clinic_user_attributes(user)
    attrs = user_attrs.attributes

    # Assert
    country_repo = CountryRepository()
    state_repo = SubdivisionRepository()

    assert attrs["first_name"] == user.first_name
    assert attrs["last_name"] == user.last_name
    assert attrs["user_role"] == fertility_clinic_user_profile.role
    assert not attrs.get("sms_phone_number")
    assert fertility_clinic.name in attrs["clinic_name"]
    assert fertility_clinic_2.name in attrs["clinic_name"]
    assert (
        country_repo.get(country_code=fc_location_2.country_code).alpha_2
        in attrs["clinic_location_country"]
    )
    assert (
        country_repo.get(country_code=fc_2_location_2.country_code).alpha_2
        in attrs["clinic_location_country"]
    )
    assert fc_location_2.name in attrs["clinic_location_name"]
    assert fc_2_location_2.name in attrs["clinic_location_name"]
    assert (
        state_repo.get(subdivision_code=fc_location_2.subdivision_code).abbreviation
        in attrs["clinic_location_state"]
    )
    assert (
        state_repo.get(subdivision_code=fc_2_location_2.subdivision_code).abbreviation
        in attrs["clinic_location_state"]
    )
    assert sum(s == "NY" for s in attrs["clinic_location_state"]) == 1
    assert sum(c == "US" for c in attrs["clinic_location_country"]) == 1


def test_braze_fertility_clinic_attributes_null_country_code():
    """
    Test that a fertility clinic that has a location with a None country_code
    is still able to build attributes
    """
    # Arrange
    user = factories.DefaultUserFactory.create()
    fertility_clinic = FertilityClinicFactory.create()
    FertilityClinicLocationFactory.create(
        name="name 2",
        address_1="456 Second Ave",
        city="San Francisco",
        subdivision_code="US-CA",
        postal_code="99999",
        country_code=None,
        fertility_clinic=fertility_clinic,
    )
    FertilityClinicUserProfileFactory.create(
        user_id=user.id, clinics=[fertility_clinic]
    )
    fc_role = RoleFactory.create(name=ROLES.fertility_clinic_user)
    RoleProfileFactory.create(role=fc_role, user=user)

    # Act
    user_attrs = braze.braze_fertility_clinic_user_attributes(user)
    attrs = user_attrs.attributes

    # Assert
    country_repo = CountryRepository()

    assert (
        country_repo.get(
            country_code=fertility_clinic.locations[0].country_code
        ).alpha_2
        in attrs["clinic_location_country"]
    )


@patch("braze.client.BrazeClient.track_user")
def test_track_user_non_fertility_user(mock_track_user):
    # Arrange
    user = factories.DefaultUserFactory.create()

    # Act
    track_user(user)

    # Assert
    mock_track_user.assert_called_with(
        user_attributes=braze.build_user_attrs(user),
    )


@patch("braze.client.BrazeClient.track_user")
@patch.dict(os.environ, {"BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY": "some_key"})
def test_track_user_fertility_user(mock_track_user, fertility_clinic_user):
    constants.BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY = os.environ.get(
        "BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY"
    )
    # Act
    track_user(fertility_clinic_user)

    # Assert
    mock_track_user.assert_called_with(
        user_attributes=braze.braze_fertility_clinic_user_attributes(
            fertility_clinic_user
        ),
    )


@patch("braze.client.BrazeClient.track_user")
def test_track_user_locale(mock_track_user):
    # Act
    track_user_locale(mock_track_user, "fr-FR")

    user_attributes = client.BrazeUserAttributes(
        external_id=mock_track_user.esp_id, attributes={"language": "fr"}
    )
    # Assert
    mock_track_user.assert_called_with(
        user_attributes=user_attributes,
    )


@patch("braze.client.BrazeClient", autospec=True)
def test_braze_send_event_non_fertility_user(mock_braze_client):
    # Arrange
    user = factories.DefaultUserFactory.create()
    mock_expected_event = BrazeEvent(
        external_id=user.esp_id,
        name="fake_event",
    )

    # Act
    send_event(user, mock_expected_event.name)

    # Assert
    mock_braze_client.assert_called_with()  # make sure no args (i.e. api_key) is passed to the constructor
    mock_braze_client.return_value.track_user.assert_called_with(
        user_attributes=None,
        events=[mock_expected_event],
    )


@patch("braze.client.BrazeClient", autospec=True)
@patch.dict(os.environ, {"BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY": "some_key"})
def test_braze_send_event_fertility_user(mock_braze_client):
    constants.BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY = os.environ.get(
        "BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY"
    )
    # Arrange
    user = factories.DefaultUserFactory.create()
    FertilityClinicUserProfileFactory.create(user_id=user.id)
    mock_expected_event = BrazeEvent(
        external_id=user.esp_id,
        name="fake_event",
    )

    # Act
    send_event(user, mock_expected_event.name)

    # Assert
    mock_braze_client.assert_called_with(
        api_key=constants.BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY,
    )
    mock_braze_client.return_value.track_user.assert_called_with(
        user_attributes=None,
        events=[mock_expected_event],
    )


def test_last_track():
    member = factories.EnterpriseUserFactory.create(enabled_tracks=["pregnancy"])

    ended_at = datetime.datetime(2022, 1, 1)
    factories.MemberTrackFactory(
        ended_at=ended_at - datetime.timedelta(days=3),
        user=member,
        name=TrackName.TRYING_TO_CONCEIVE.value,
    )
    factories.MemberTrackFactory(
        ended_at=ended_at, user=member, name=TrackName.PREGNANCY.value
    )

    attrs = braze.build_user_attrs(member).attributes

    assert attrs["last_track"] == "pregnancy"
    assert attrs["last_track_ended_date"] == "2022-01-01T00:00:00"


@pytest.mark.parametrize(
    argnames=["user_fixture_name", "is_doula_only"],
    argvalues=[("create_doula_only_member", True), ("enterprise_user", False)],
)
@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_is_doula_only(
    mock_should_enable_doula_only_track,
    user_fixture_name: str,
    is_doula_only: bool,
    request,
):
    assert (
        braze.build_user_attrs(request.getfixturevalue(user_fixture_name)).attributes[
            "is_doula_only"
        ]
        is is_doula_only
    )


@patch("utils.braze_events._gcal_link")
@patch("utils.braze_events._ical_link")
@patch("tracks.service.tracks.TrackSelectionService.get_organization_for_user")
@patch("braze.client.BrazeClient", autospec=True)
def test_appointment_rescheduled_member(
    mock_braze_client, mock_get_organization_for_user, mock_ical_link, mock_gcal_link
):
    # Given
    appointment = factories.AppointmentFactory.create()
    organization = factories.OrganizationFactory.create()

    # mocking the return as _ical_link interacts with a token
    mock_ical_link.return_value = "test_ical_link@google.com"
    mock_gcal_link.return_value = "test_gcal_link@google.com"
    mock_get_organization_for_user.return_value = organization

    expected_properties = {
        "appointment_id": appointment.api_id,
        "practitioner_id": appointment.practitioner.id
        if appointment.practitioner
        else None,
        "practitioner_name": appointment.practitioner.full_name
        if appointment.practitioner
        else None,
        "practitioner_image": appointment.practitioner.avatar_url
        if appointment.practitioner
        else None,
        "practitioner_type": ", ".join(
            v.name for v in appointment.practitioner.practitioner_profile.verticals
        )
        if appointment.practitioner
        else None,
        "scheduled_start_time": format_dt(appointment.scheduled_start),
        "booked_at": format_dt(appointment.created_at),
        "has_pre_session_note": bool(appointment.client_notes),
        "health_binder_fields_completed": all(
            (
                appointment.member.health_profile.height,
                appointment.member.health_profile.weight,
            )
        ),
        "user_country": (
            appointment.member.country and appointment.member.country.name
        ),
        "user_organization": organization.name,
        "appointment_purpose": appointment.purpose,
        "anonymous_appointment": appointment.is_anonymous,
        "prescription_available": appointment.rx_enabled
        and appointment.practitioner.practitioner_profile.dosespot != {}
        if appointment.practitioner
        else None,
        "gcal_link": "test_gcal_link@google.com",
        "ical_link": "test_ical_link@google.com",
    }

    mock_expected_event = BrazeEvent(
        external_id=appointment.member.esp_id,
        name="appointment_rescheduled_member",
        properties=expected_properties,
    )

    # When
    appointment_rescheduled_member(appointment=appointment)

    # Then
    mock_braze_client.assert_called_with()  # make sure no args (i.e. api_key) is passed to the constructor
    mock_braze_client.return_value.track_user.assert_called_with(
        events=[mock_expected_event],
    )


@pytest.mark.parametrize(
    "ip_address, expected_result, redis_members, yaml_content",
    [
        ("192.0.2.1", True, {"192.0.2.1", "192.0.2.2"}, None),
        ("192.0.2.3", False, {"192.0.2.1", "192.0.2.2"}, None),
        (None, False, set(), None),
        ("", False, set(), None),
        (
            "192.0.2.3",
            True,
            set(),
            '{"braze": {"whitelist-ips": ["192.0.2.1", "192.0.2.3"]}}',
        ),
    ],
)
def test_is_whitelisted_braze_ip(
    ip_address, expected_result, redis_members, yaml_content
):
    with patch("utils.braze.redis_client") as mock_redis_client, patch(
        "builtins.open", mock_open(read_data=yaml_content)
    ):

        mock_redis = mock_redis_client.return_value
        mock_redis.smembers.return_value = redis_members
        mock_redis.sismember.return_value = ip_address in redis_members

        result = is_whitelisted_braze_ip(ip_address)

        assert result == expected_result

        if not redis_members and yaml_content:
            mock_redis.sadd.assert_called_once()
        elif not redis_members and not yaml_content:
            mock_redis.sadd.assert_not_called()


def test_is_whitelisted_braze_ip_file_error():
    exception = Exception("File not found")
    with patch("utils.braze.redis_client") as mock_redis_client, patch(
        "builtins.open", side_effect=exception
    ), patch("utils.braze.log") as mock_log:

        mock_redis = mock_redis_client.return_value
        mock_redis.smembers.return_value = set()

        result = is_whitelisted_braze_ip("192.0.2.1")

        assert result == True
        mock_log.error.assert_called_once_with(
            "Could not load Braze whitelisted IPs", exception=exception
        )


def test_is_whitelisted_braze_ip_redis_connection_error():
    with patch("redis.Redis.execute_command") as mock_redis_client, patch(
        "builtins.open",
        mock_open(read_data='{"braze": {"whitelist-ips": ["192.0.2.1", "192.0.2.2"]}}'),
    ):

        mock_redis_client.side_effect = RedisConnectionError("Connection refused")

        result = is_whitelisted_braze_ip("192.0.2.1")

        assert result == True

    with patch("redis.Redis.execute_command") as mock_redis_client, patch(
        "builtins.open",
        mock_open(read_data='{"braze": {"whitelist-ips": ["192.0.2.1", "192.0.2.2"]}}'),
    ):

        mock_redis_client.side_effect = RedisConnectionError("Connection refused")

        result = is_whitelisted_braze_ip("192.0.2.4")

        assert result == False


def test_update_current_track_phase_pnp():
    user = factories.EnterpriseUserFactory(tracks__name="parenting_and_pediatrics")
    track = user.active_tracks[0]
    assert track.name == "parenting_and_pediatrics"

    # Call the function
    braze.update_current_track_phase(track)

    # Assert
    user_attrs = braze.build_user_attrs(user)
    assert user_attrs.attributes["current_phase_pnp"] == "week-1"


def test_update_current_track_phase_non_pnp():
    user = factories.EnterpriseUserFactory(tracks__name="pregnancy")
    track = user.active_tracks[0]
    assert track.name == "pregnancy"

    # Call the function
    braze.update_current_track_phase(track)

    # Assert
    user_attrs = braze.build_user_attrs(user)
    assert user_attrs.attributes["current_phase_pnp"] is None
    assert user_attrs.attributes["current_phase"] == "week-1"
