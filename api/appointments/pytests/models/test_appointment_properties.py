import datetime

import pytest
from pytz import timezone
from sqlalchemy import func

from appointments.models.appointment import Appointment
from appointments.services.common import deobfuscate_appointment_id
from models.verticals_and_specialties import CX_VERTICAL_NAME
from pytests import freezegun
from pytests.factories import (
    AppointmentFactory,
    AppointmentMetaDataFactory,
    EnterpriseUserFactory,
    ScheduleFactory,
    VerticalFactory,
)
from storage.connection import db


@pytest.fixture
def appointment():
    return AppointmentFactory.create()


@pytest.fixture
def post_session_note(appointment):
    return AppointmentMetaDataFactory.create(
        appointment=appointment,
        appointment_id=appointment.id,
        content="test note content",
        created_at=datetime.datetime.utcnow(),
    )


@freezegun.freeze_time("2022-04-06 00:17:10")
def test_is_first_in_month(valid_appointment_with_user, practitioner_user):
    """Tests that an appointment is the first in the month for a practitioner."""
    now = datetime.datetime.utcnow()
    ca = practitioner_user()
    member = EnterpriseUserFactory.create()
    ms = ScheduleFactory.create(user=member)
    a = valid_appointment_with_user(
        scheduled_start=now + datetime.timedelta(minutes=15),
        practitioner=ca,
        member_schedule=ms,
    )
    assert a.is_first_for_practitioner_in_month


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_is_not_first_in_month(valid_appointment_with_user, practitioner_user):
    """Tests that an appointment is not the first in the month for a practitioner."""
    now = datetime.datetime.utcnow()
    ca = practitioner_user()
    b = valid_appointment_with_user(scheduled_start=now, practitioner=ca)
    c = valid_appointment_with_user(
        scheduled_start=now + datetime.timedelta(hours=1),
        practitioner=ca,
        member_schedule=b.member_schedule,
    )
    assert not c.is_first_for_practitioner_in_month


def test_api_id_property__api_id_property_can_be_used_in_sql(
    valid_appointment_with_user, practitioner_user
):
    """
    Tests that the Appointment property 'api_id' can be used in a sql query
    """

    ca = practitioner_user()
    appointment = valid_appointment_with_user(practitioner=ca)
    deob_appt_id = deobfuscate_appointment_id(appointment.id)

    appointment = db.session.query(Appointment).filter(
        Appointment.api_id == deob_appt_id
    )
    assert appointment is not None


class TestIsIntro:
    @pytest.mark.parametrize(
        argnames="intro_appt_purpose",
        argvalues=[
            "introduction",
            "introduction_to_smthg",
            "birth_needs_assessment",
            "postpartum_needs_assessment",
        ],
    )
    def test_is_intro__true(self, intro_appt_purpose, appointment):
        # Given an appt whose purpose is associated to an intro appt
        appointment.purpose = intro_appt_purpose

        # When calling appointment.is_intro, then we expect it to be True
        assert appointment.is_intro

    @pytest.mark.parametrize(
        argnames="not_intro_appt_purpose", argvalues=[None, "the_best_purpose"]
    )
    def test_is_intro__false(
        self, not_intro_appt_purpose, appointment
    ):  # Given an appt whose purpose is not associated to an intro appt
        appointment.purpose = not_intro_appt_purpose

        # When calling appointment.is_intro, then we expect it to be False
        assert not appointment.is_intro

    @pytest.mark.parametrize(
        argnames="intro_appt_purpose",
        argvalues=[
            "introduction",
            "introduction_to_smthg",
            "birth_needs_assessment",
            "postpartum_needs_assessment",
        ],
    )
    def test_is_intro_expression__true(self, intro_appt_purpose, appointment):
        # Given an appt whose purpose is associated to an intro appt
        appointment.purpose = intro_appt_purpose

        # When calling looking in the db for appointments with is_intro True
        appointment_query_result = (
            db.session.query(Appointment).filter(Appointment.is_intro == True).all()
        )
        # Then we expect to return our appointment
        assert appointment_query_result[0].id == appointment.id

    @pytest.mark.parametrize(
        argnames="not_intro_appt_purpose", argvalues=[None, "the_best_purpose"]
    )
    def test_is_intro_expression__false(
        self, not_intro_appt_purpose, appointment
    ):  # Given an appt whose purpose is not associated to an intro appt
        appointment.purpose = not_intro_appt_purpose

        # When calling looking in the db for appointments with is_intro False
        appointment_query_result = (
            db.session.query(Appointment).filter(Appointment.is_intro == False).all()
        )
        # Then we expect to return our appointment
        assert appointment_query_result[0].id == appointment.id


class TestIntroAppointmentsFromDateRangeWithTZ:
    @pytest.mark.parametrize(
        argnames="tz,day_range,expected_appointments",
        argvalues=[
            ("UTC", 1, 3),
            ("UTC", 3, 9),
            ("America/Chicago", 1, 3),
            ("America/Chicago", 3, 9),
            ("America/New_York", 1, 3),
            ("America/New_York", 3, 9),
        ],
    )
    @freezegun.freeze_time("2023-06-13 00:17:10.0")
    def test_intro_appointments_from_date_range_with_tz(
        self, tz, day_range, expected_appointments, factories
    ):
        # Given prac with 3 appointments each day in range
        cx_vertical = factories.VerticalFactory(name=CX_VERTICAL_NAME)
        practitioner = factories.PractitionerUserFactory(
            practitioner_profile__verticals=[cx_vertical]
        )

        tz = timezone(tz)
        appointment_start_date = tz.localize(datetime.datetime.now()).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        start_datetime = datetime.datetime.utcnow()
        end_datetime = start_datetime + datetime.timedelta(days=day_range)
        for day in range(day_range):
            # create 3 appointments each day
            AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=appointment_start_date + datetime.timedelta(days=day),
                scheduled_end=appointment_start_date
                + datetime.timedelta(days=day, minutes=15),
                purpose="introduction",
            )
            AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=appointment_start_date
                + datetime.timedelta(days=day, hours=3),
                scheduled_end=appointment_start_date
                + datetime.timedelta(days=day, hours=3, minutes=15),
                purpose="introduction",
            )
            AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=appointment_start_date
                + datetime.timedelta(days=day, hours=12),
                scheduled_end=appointment_start_date
                + datetime.timedelta(days=day, hours=12, minutes=15),
                purpose="introduction",
            )

        # When we pass date range with UTC
        number_of_intro_appointments = (
            Appointment.intro_appointments_from_date_range_with_tz(
                practitioner_id=practitioner.id,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                tz=tz,
            )
            .with_entities(func.count())
            .one()[0]
        )
        # Then we expect the correct number of appointments given local time zone
        assert number_of_intro_appointments == expected_appointments

    def test_intro_appointments_from_date_range_with_tz__now_at_end_of_day_with_appointment_next_day(
        self, factories
    ):
        # Given a practitioner in Chicago
        tz_str = "America/Chicago"
        tz = timezone(tz_str)
        cx_vertical = factories.VerticalFactory(name=CX_VERTICAL_NAME)
        practitioner = factories.PractitionerUserFactory(
            practitioner_profile__verticals=[cx_vertical]
        )

        # That has an appointment on the 5th
        appointment_start_date = datetime.datetime(2023, 7, 5, 20, 10, 0, 0)
        AppointmentFactory.create_with_practitioner(
            practitioner=practitioner,
            scheduled_start=appointment_start_date,
            scheduled_end=appointment_start_date + datetime.timedelta(minutes=15),
            purpose="introduction",
        )

        # When looking for appointments on the 4th, with now being right at the end of the 4th (so 2 am UTC of the 5th for example)
        now = datetime.datetime(2023, 7, 5, 2, 10, 0, 0)

        number_of_appointments = (
            Appointment.intro_appointments_from_date_range_with_tz(
                practitioner_id=practitioner.id,
                start_datetime=now,
                end_datetime=now,
                tz=tz,
            )
            .with_entities(func.count())
            .one()[0]
        )

        # Then we expect no appointments to be found
        assert number_of_appointments == 0

    def test_intro_appointments_from_date_range_with_tz__utc_cusp(self, factories):
        # Given a practitioner in Chicago
        tz_str = "America/Chicago"
        tz = timezone(tz_str)
        cx_vertical = factories.VerticalFactory(name=CX_VERTICAL_NAME)
        practitioner = factories.PractitionerUserFactory(
            practitioner_profile__verticals=[cx_vertical]
        )

        # That has an appointment on the 5th
        appointment_start_date = datetime.datetime(2023, 7, 5, 20, 10, 0, 0)
        AppointmentFactory.create_with_practitioner(
            practitioner=practitioner,
            scheduled_start=appointment_start_date,
            scheduled_end=appointment_start_date + datetime.timedelta(minutes=15),
            purpose="introduction",
        )

        # When looking for appointments on the 4th, with now being right at the end of the 4th (so 2 am UTC of the 5th for example)
        now = datetime.datetime(2023, 7, 5, 2, 10, 0, 0)

        number_of_appointments = (
            Appointment.intro_appointments_from_date_range_with_tz(
                practitioner_id=practitioner.id,
                start_datetime=now,
                end_datetime=now,
                tz=tz,
            )
            .with_entities(func.count())
            .one()[0]
        )

        # Then we expect no appointments to be found
        assert number_of_appointments == 0


class TestIntroAppointmentsFromDateRange:
    @pytest.mark.parametrize(
        argnames="num_users",
        argvalues=[0, 1, 2, 3],
    )
    @freezegun.freeze_time("2023-06-13 00:10:10.0")
    def test_intro_appointments_from_date_range(
        self,
        num_users,
        valid_appointment_with_user,
        practitioner_user,
    ):
        # Given prac with 2 appointments for each user
        now = datetime.datetime.utcnow()
        ca = practitioner_user()
        CA_vertical = VerticalFactory.create(name="Care Advocate")
        ca.practitioner_profile.verticals = [CA_vertical]
        i = 0

        intro_appts = []
        while i < num_users:
            # create an intro and follow up appointment for each user
            member = EnterpriseUserFactory.create()
            ms = ScheduleFactory.create(user=member)

            AppointmentFactory.create_with_practitioner(
                member_schedule=ms,
                practitioner=ca,
                scheduled_start=now + datetime.timedelta(hours=3),
                scheduled_end=now + datetime.timedelta(hours=3, minutes=15),
            )

            intro_appt = AppointmentFactory.create_with_practitioner(
                member_schedule=ms,
                practitioner=ca,
                scheduled_start=now,
                scheduled_end=now + datetime.timedelta(minutes=15),
                purpose="introduction",
            )
            intro_appts.append(intro_appt)

            i += 1

        # When we pass date range
        retrieved_intro_appts = Appointment.intro_appointments_from_date_range(
            practitioner_id=ca.id,
            start_date=now,
            end_date=now,
        )
        intro_appts_ids = [a.id for a in intro_appts]
        retrieved_intro_appts_ids = [a.id for a in retrieved_intro_appts]

        # Sort lists just in case the ids come in different orders
        intro_appts_ids.sort()
        retrieved_intro_appts_ids.sort()

        # Then we expect only the intro appointments for each user
        assert intro_appts_ids == retrieved_intro_appts_ids

    @pytest.mark.parametrize(
        argnames="num_users",
        argvalues=[0, 1, 2, 3],
    )
    @freezegun.freeze_time("2023-06-13 00:10:10.0")
    def test_intro_appointments_from_date_range__intro_outside_of_date_range(
        self,
        num_users,
        valid_appointment_with_user,
        practitioner_user,
    ):
        # Given prac with 2 appointments for each user
        now = datetime.datetime.utcnow()
        two_days_ago = now - datetime.timedelta(days=2)
        ca = practitioner_user()
        CA_vertical = VerticalFactory.create(name="Care Advocate")
        ca.practitioner_profile.verticals = [CA_vertical]
        i = 0
        while i < num_users:
            # create an intro for each user that happened two days ago, and a follow up now
            member = EnterpriseUserFactory.create()
            ms = ScheduleFactory.create(user=member)

            AppointmentFactory.create_with_practitioner(
                member_schedule=ms,
                practitioner=ca,
                scheduled_start=now + datetime.timedelta(hours=3),
                scheduled_end=now + datetime.timedelta(hours=3, minutes=15),
                purpose="follow-up-appointment",
            )

            AppointmentFactory.create_with_practitioner(
                member_schedule=ms,
                practitioner=ca,
                scheduled_start=two_days_ago,
                scheduled_end=two_days_ago + datetime.timedelta(minutes=15),
                purpose="introduction",
            )
            i += 1

        # When we pass date range
        retrieved_intro_appts = Appointment.intro_appointments_from_date_range(
            practitioner_id=ca.id,
            start_date=now,
            end_date=now,
        )

        # Then we expect no intro appointments to be found
        assert retrieved_intro_appts == []


class TestAppointmentPostSession:
    def test_no_post_session(self, appointment):
        # Assert
        assert appointment.post_session == {
            "draft": None,
            "notes": "",
            "created_at": None,
            "modified_at": None,
        }

    def test_post_session(self, appointment, post_session_note):
        # Assert
        assert appointment.post_session == {
            "draft": post_session_note.draft,
            "notes": post_session_note.content,
            "created_at": post_session_note.created_at,
            "modified_at": post_session_note.modified_at,
        }
