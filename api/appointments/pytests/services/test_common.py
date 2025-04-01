from datetime import datetime, timedelta
from unittest import mock

import pytest

from appointments.models.appointment import Appointment
from appointments.models.constants import APPOINTMENT_STATES
from appointments.services.common import (
    can_member_book,
    cancel_invalid_appointment_post_track_transition,
    check_intro_appointment_purpose,
    get_cleaned_appointment,
    get_platform,
    obfuscate_appointment_id,
    round_to_nearest_minutes,
)
from models.products import Purposes
from models.tracks.client_track import TrackModifiers
from models.verticals_and_specialties import CX_VERTICAL_NAME, VerticalAccessByTrack
from pytests import factories
from storage.connection import db

expected = [
    (datetime.strptime("2022-08-18T00:00:00", "%Y-%m-%dT%H:%M:%S"), 0),
    (datetime.strptime("2022-08-18T00:07:00", "%Y-%m-%dT%H:%M:%S"), 3),
    (datetime.strptime("2022-08-18T00:05:00", "%Y-%m-%dT%H:%M:%S"), 5),
    (datetime.strptime("2022-08-18T00:01:00", "%Y-%m-%dT%H:%M:%S"), 9),
]


@pytest.fixture
def obfuscate_appointment(appointment):
    return obfuscate_appointment_id(appointment.id)


@pytest.fixture
def member_schedule(enterprise_user):
    return factories.ScheduleFactory.create(user=enterprise_user)


@pytest.fixture
def provider():
    return factories.PractitionerUserFactory.create()


@pytest.fixture
def appointment(member_schedule, provider):
    return factories.AppointmentFactory.create_with_practitioner(
        member_schedule=member_schedule,
        practitioner=provider,
    )


@pytest.mark.parametrize("date_time,rounded_minutes", expected)
def test_odd_time_is_rounded_up(date_time, rounded_minutes):
    rounded = round_to_nearest_minutes(date_time)
    assert rounded == date_time + timedelta(minutes=rounded_minutes)


@pytest.mark.parametrize(
    "user_agent,platform",
    [
        ("Python/3.8 aiohttp/3.6.2", "backend"),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "web",
        ),
        (
            "Maven/4.13.1 (com.mavenclinic.Maven; build:335; iOS 15.1.0) Alamofire/5.7.1",
            "iOS",
        ),
        (
            "MAVEN_ANDROID/3.49.1-debug (com.mavenclinic.android.member.debug; build:32352; Android:13; Manufacturer:Google; Model:sdk_gphone64_arm64)",
            "android",
        ),
    ],
)
def test_get_platform(user_agent: str, platform: str):
    assert get_platform(user_agent) == platform


def test_get_cleaned_appointment_no_matching_appointment(enterprise_user):
    # Act
    result = get_cleaned_appointment(123456, enterprise_user)

    # Assert
    assert result is None


def test_get_cleaned_appointment_not_member_or_practitioner(
    obfuscate_appointment, appointment, enterprise_user
):
    # Arrange
    another_user = factories.EnterpriseUserFactory.create()
    factories.ScheduleFactory.create(user=another_user)

    # Act
    result = get_cleaned_appointment(obfuscate_appointment, another_user)

    # Assert
    assert result == []


def test_get_cleaned_appointment_member(
    obfuscate_appointment, appointment, enterprise_user
):
    # Act
    result = get_cleaned_appointment(obfuscate_appointment, enterprise_user)

    # Assert
    assert result == [appointment]


def test_get_cleaned_appointment_provider(obfuscate_appointment, appointment, provider):
    # Act
    result = get_cleaned_appointment(obfuscate_appointment, provider)

    # Assert
    assert result == [appointment]


class TestIntroAppointmentPurpose:
    @pytest.mark.parametrize(
        argnames="member_track",
        argvalues=["adoption", "egg_freezing", "pregnancy", "postpartum"],
    )
    def test_check_intro_appointment_purpose__first_appt_with_ca__purpose_is_intro(
        self, member_track, setup_post_appointment_state_check, create_state, factories
    ):
        """
        Test that when an introduction appt is created, its purpose is introduction
        """
        # Given we set data up to create an intro appointment with a CA
        setup_values = setup_post_appointment_state_check()
        member = setup_values.member
        product = setup_values.product
        # Make the provider a CA
        cx_vertical = factories.VerticalFactory(
            name=CX_VERTICAL_NAME, filter_by_state=True
        )
        setup_values.practitioner.practitioner_profile.verticals = [cx_vertical]

        # Make the member an enterprise member
        factories.MemberTrackFactory.create(name=member_track, user=member)
        factories.UserOrganizationEmployeeFactory(user=member)

        # Set expected_purpose given member track
        if member_track in ["adoption", "egg_freezing"]:
            expected_purpose = f"introduction_{member_track}"
        elif member_track == "pregnancy":
            expected_purpose = "birth_needs_assessment"
        elif member_track == "postpartum":
            member.health_profile.due_date = datetime.now() - timedelta(days=60)
            expected_purpose = "introduction"

        # when calling check_intro_appointment_purpose
        calculated_purpose = check_intro_appointment_purpose(member, product)
        assert calculated_purpose == expected_purpose

    @pytest.mark.parametrize(
        argnames="member_track",
        argvalues=["adoption", "egg_freezing", "pregnancy", "postpartum"],
    )
    def test_check_intro_appointment_purpose__first_appt_with_ca_after_regular_appt__purpose_is_intro(
        self, member_track, setup_post_appointment_state_check
    ):
        """
        Test that when an introduction appt is created, after member had had another appt with a provider, its purpose is introduction
        """
        # Given we set data up to create an intro appointment with a CA
        setup_values = setup_post_appointment_state_check()
        member = setup_values.member
        product = setup_values.product
        cx_vertical = factories.VerticalFactory(
            name=CX_VERTICAL_NAME, filter_by_state=True
        )
        setup_values.practitioner.practitioner_profile.verticals = [cx_vertical]

        # And an already existing appointment with a provider (not a CA)
        obgyn_vertical = factories.VerticalFactory.create(name="OB-GYN")
        obgyn_provider = factories.PractitionerUserFactory.create(
            practitioner_profile__verticals=[obgyn_vertical],
        )
        factories.AppointmentFactory.create_with_practitioner(
            member_schedule=member.schedule,
            practitioner=obgyn_provider,
        )

        # Make the member an enterprise member
        factories.MemberTrackFactory.create(name=member_track, user=member)
        factories.UserOrganizationEmployeeFactory(user=member)

        # Set expected_purpose given member track
        if member_track in ["adoption", "egg_freezing"]:
            expected_purpose = f"introduction_{member_track}"
        elif member_track == "pregnancy":
            expected_purpose = "birth_needs_assessment"
        elif member_track == "postpartum":
            member.health_profile.due_date = datetime.now() - timedelta(days=60)
            expected_purpose = "introduction"

        # when calling check_intro_appointment_purpose
        calculated_purpose = check_intro_appointment_purpose(member, product)
        assert calculated_purpose == expected_purpose

    @pytest.mark.parametrize(
        argnames="member_track",
        argvalues=["adoption", "egg_freezing", "pregnancy", "postpartum"],
    )
    def test_check_intro_appointment_purpose__first_appt_with_ca_in_second_track_with_no_previous_member_track_id__purpose_is_intro(
        self, member_track, setup_post_appointment_state_check
    ):
        """
        Test that when an introduction appt is created in a second track that is not a transition (has no previous_member_track_id),
        its purpose is introduction
        """
        # Given we set data up to create an intro appointment with a CA
        setup_values = setup_post_appointment_state_check()
        member = setup_values.member
        product = setup_values.product
        # Make the member an enterprise member
        factories.MemberTrackFactory.create(name=member_track, user=member)
        factories.UserOrganizationEmployeeFactory(user=member)
        # Make the practitioner a CA
        cx_vertical = factories.VerticalFactory(
            name=CX_VERTICAL_NAME, filter_by_state=True
        )
        setup_values.practitioner.practitioner_profile.verticals = [cx_vertical]
        # Current member track has no previous_member_track_id
        active_track = member.active_tracks[0]
        active_track.previous_member_track_id = None

        # And a CA appt exists but it was before the new track activation date
        factories.AppointmentFactory.create_with_practitioner(
            practitioner=setup_values.practitioner,
            member_schedule=member.schedule,
            scheduled_start=active_track.activated_at - timedelta(days=7),
        )

        # Set expected_purpose given member track
        if member_track in ["adoption", "egg_freezing"]:
            expected_purpose = f"introduction_{member_track}"
        elif member_track == "pregnancy":
            expected_purpose = "birth_needs_assessment"
        elif member_track == "postpartum":
            member.health_profile.due_date = datetime.now() - timedelta(days=60)
            expected_purpose = "introduction"

        # when calling check_intro_appointment_purpose
        calculated_purpose = check_intro_appointment_purpose(member, product)
        assert calculated_purpose == expected_purpose

    @pytest.mark.parametrize(
        argnames="member_track",
        argvalues=["adoption", "egg_freezing", "pregnancy", "postpartum"],
    )
    def test_check_intro_appointment_purpose__first_appt_with_ca_in_second_track_with_previous_member_track_id__purpose_none(
        self, member_track, setup_post_appointment_state_check
    ):
        """
        Test that when an introduction appt is created, its purpose is introduction
        """
        # Given we set data up to create an intro appointment with a CA
        setup_values = setup_post_appointment_state_check()
        member = setup_values.member
        product = setup_values.product
        # Make the member an enterprise member
        factories.MemberTrackFactory.create(name=member_track, user=member)
        factories.UserOrganizationEmployeeFactory(user=member)
        # Make the practitioner a CA
        cx_vertical = factories.VerticalFactory(
            name=CX_VERTICAL_NAME, filter_by_state=True
        )
        setup_values.practitioner.practitioner_profile.verticals = [cx_vertical]
        # Current member track has previous_member_track_id
        active_track = member.active_tracks[0]
        active_track.previous_member_track_id = 1

        # when calling check_intro_appointment_purpose
        calculated_purpose = check_intro_appointment_purpose(member, product)
        assert not calculated_purpose

    def test_check_intro_appointment_purpose__appt_not_with_ca__purpose_none(
        self, setup_post_appointment_state_check
    ):
        """
        Test that when a not-with-a-CA appt is created, its purpose fallback to the product purpose
        """
        # Given an appointment that's not with a CA (default practitioner vertical is Allergist), and a given product purpose
        setup_values = setup_post_appointment_state_check()
        member = setup_values.member
        product = setup_values.product
        setup_values.product.purpose = Purposes.POSTPARTUM_PLANNING

        # Make the member an enterprise member
        factories.MemberTrackFactory.create(name="adoption", user=member)
        factories.UserOrganizationEmployeeFactory(user=member)

        # when calling check_intro_appointment_purpose
        calculated_purpose = check_intro_appointment_purpose(member, product)
        assert not calculated_purpose

    def test_check_intro_appointment_purpose__appt_not_first_ca_appt__purpose_none(
        self, setup_post_appointment_state_check
    ):
        """
        Test that when a not-first CA appt is created, its purpose fallback to the product purpose
        """
        # Given an appointment that's with a CA but not the first one, and a given product purpose
        setup_values = setup_post_appointment_state_check()
        member = setup_values.member
        product = setup_values.product
        # Make the member an enterprise member
        factories.MemberTrackFactory.create(name="adoption", user=member)
        factories.UserOrganizationEmployeeFactory(user=member)
        # Make the practitioner a CA
        cx_vertical = factories.VerticalFactory(
            name=CX_VERTICAL_NAME, filter_by_state=True
        )
        setup_values.practitioner.practitioner_profile.verticals = [cx_vertical]

        # Lets create the first ever CA appt for the member, so the new one happens after this one
        factories.AppointmentFactory.create_with_practitioner(
            practitioner=setup_values.practitioner, member_schedule=member.schedule
        )

        # when calling check_intro_appointment_purpose
        calculated_purpose = check_intro_appointment_purpose(member, product)
        assert not calculated_purpose


@pytest.mark.parametrize(
    "vertical_name,track_modifiers,expected_result",
    [
        ("Doula and childbirth educator", TrackModifiers.DOULA_ONLY, True),
        ("Wellness Coach", None, False),
    ],
)
@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_can_member_book(
    mock_should_enable_doula_only_track,
    vertical_name,
    track_modifiers,
    expected_result,
    create_doula_only_member,
    factories,
):

    # Given

    member = create_doula_only_member

    active_member_track = member.active_tracks[0]
    client_track_id = active_member_track.client_track_id

    vertical = factories.VerticalFactory.create(
        name=vertical_name,
    )

    # create a VerticalAccessByTrack record to allow vertical <> client track interaction
    factories.VerticalAccessByTrackFactory.create(
        client_track_id=client_track_id,
        vertical_id=vertical.id,
        track_modifiers=track_modifiers,
    )

    product = factories.ProductFactory.create(minutes=60, price=60, vertical=vertical)
    doula_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[product.vertical], products=[product]
    )
    product.practitioner = doula_provider

    # When/ Then
    assert can_member_book(member, product) == expected_result


@pytest.mark.parametrize("is_doula_provider", [True, False])
@mock.patch("appointments.services.common.log.info")
def test_cancel_invalid_appointment_post_track_transition(
    mock_log_info,
    is_doula_provider,
    factories,
):

    # Given
    member = factories.MemberFactory.create()
    member_schedule = factories.ScheduleFactory.create(user=member)

    ca_vertical = factories.VerticalFactory.create(
        name=(
            "Doula And Childbirth Educator"
            if is_doula_provider
            else "Fertility Awareness Educator"
        )
    )

    ca = factories.PractitionerUserFactory(
        practitioner_profile__verticals=[ca_vertical]
    )

    utcnow = datetime.utcnow().replace(second=0, microsecond=0)
    one_hour_from_now = utcnow + timedelta(hours=1)

    appointment = factories.AppointmentFactory.create_with_practitioner(
        member_schedule=member_schedule,
        practitioner=ca,
        scheduled_start=one_hour_from_now,
    )

    appointment_id = appointment.id

    # create a VerticalAccessByTrack record to allow vertical <> client track interaction
    client_track_id = 1
    allowed_verticals_by_track = VerticalAccessByTrack(
        client_track_id=client_track_id,
        vertical_id=ca_vertical.id,
        track_modifiers=[TrackModifiers.DOULA_ONLY] if is_doula_provider else None,
    )

    db.session.add(allowed_verticals_by_track)
    db.session.commit()

    # When
    cancel_invalid_appointment_post_track_transition(
        user_id=member.id,
        member_track_modifiers=[TrackModifiers.DOULA_ONLY],
        client_track_ids=[client_track_id],
    )

    # Then
    if is_doula_provider:
        mock_log_info.assert_not_called()
    else:
        mock_log_info.assert_called_once_with(
            "Cancelled existing appointments booked with unsupported providers",
            member_id=member.id,
            invalid_appointment_ids=[appointment.id],
        )

        # assert that the appointment has been cancelled
        appointment = (
            db.session.query(Appointment).filter_by(id=appointment_id).one_or_none()
        )
        assert appointment.state == APPOINTMENT_STATES.cancelled
