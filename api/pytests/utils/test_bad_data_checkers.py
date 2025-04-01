import datetime
from unittest.mock import call, patch

import pytest

from common.stats import PodNames
from storage.connection import db
from utils.bad_data_checkers import (
    find_appointments_that_should_be_over,
    find_appointments_with_missing_start_or_end_data,
)


@pytest.fixture()
def practitioner(factories):
    return factories.PractitionerUserFactory.create()


@pytest.fixture()
def member(factories):
    member = factories.MemberFactory.create()
    factories.ScheduleFactory(user=member)
    return member


def generate_appointment(
    factories,
    member,
    practitioner,
    scheduled_start,
    scheduled_end,
    member_started_at,
    member_ended_at,
    practitioner_started_at,
    practitioner_ended_at,
):
    appt = factories.AppointmentFactory.create(
        member_schedule=member.schedule,
        product=practitioner.products[0],
        member_started_at=member_started_at,
        member_ended_at=member_ended_at,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        practitioner_started_at=practitioner_started_at,
        practitioner_ended_at=practitioner_ended_at,
    )
    db.session.add(appt)
    db.session.commit()
    return appt


@pytest.fixture()
def insert_appointments(factories, member, practitioner):
    now = datetime.datetime.utcnow()

    # finished_appt
    start = now - datetime.timedelta(minutes=60)
    end = now - datetime.timedelta(minutes=30)
    generate_appointment(
        factories, member, practitioner, start, end, start, end, start, end
    )

    # unfinished_appt w/ both start
    start = now - datetime.timedelta(minutes=35)
    end = now - datetime.timedelta(minutes=5)
    generate_appointment(
        factories, member, practitioner, start, end, start, None, start, None
    )
    # unfinished_appt w/ practitioner start
    start = now - datetime.timedelta(minutes=35)
    end = now - datetime.timedelta(minutes=5)
    generate_appointment(
        factories, member, practitioner, start, end, None, None, start, None
    )

    # unfinished_appt w/member start
    start = now - datetime.timedelta(minutes=35)
    end = now - datetime.timedelta(minutes=5)
    generate_appointment(
        factories, member, practitioner, start, end, start, None, None, None
    )

    # missing_practitioner_start_apt
    start = now - datetime.timedelta(minutes=90)
    end = now - datetime.timedelta(minutes=60)
    generate_appointment(
        factories, member, practitioner, start, end, start, end, None, end
    )

    # missing_practitioner_start_apt >24hr old
    start = now - datetime.timedelta(hours=25, minutes=90)
    end = now - datetime.timedelta(hours=25, minutes=60)
    generate_appointment(
        factories, member, practitioner, start, end, start, end, None, end
    )

    # missing_practitioner_end_apt
    start = now - datetime.timedelta(minutes=120)
    end = now - datetime.timedelta(minutes=90)
    generate_appointment(
        factories, member, practitioner, start, end, start, end, start, None
    )

    # missing_practitioner_end_apt >24hr old
    start = now - datetime.timedelta(hours=25, minutes=90)
    end = now - datetime.timedelta(hours=25, minutes=60)
    generate_appointment(
        factories, member, practitioner, start, end, start, end, start, None
    )

    # missing_member_start_appt
    start = now - datetime.timedelta(minutes=120)
    end = now - datetime.timedelta(minutes=90)
    generate_appointment(
        factories, member, practitioner, start, end, None, end, start, end
    )

    # missing_member_start_appt >24hr old
    start = now - datetime.timedelta(hours=25, minutes=90)
    end = now - datetime.timedelta(hours=25, minutes=60)
    generate_appointment(
        factories, member, practitioner, start, end, None, end, start, end
    )

    # missing_member_end_appt
    start = now - datetime.timedelta(minutes=120)
    end = now - datetime.timedelta(minutes=90)
    generate_appointment(
        factories, member, practitioner, start, end, start, None, start, end
    )

    # missing_member_end_appt > 24hr old
    start = now - datetime.timedelta(hours=25, minutes=90)
    end = now - datetime.timedelta(hours=25, minutes=60)
    generate_appointment(
        factories, member, practitioner, start, end, start, None, start, end
    )


def test_find_appointments_that_should_be_over(
    insert_appointments, member, practitioner
):
    with patch("utils.bad_data_checkers.increment") as mock_stats_increment:
        find_appointments_that_should_be_over()
        expected_calls = [
            call(
                metric_name="api.utils.bad_data_checkers.appointment_that_should_be_over",
                pod_name=PodNames.MPRACTICE_CORE,
            ),
            call(
                metric_name="api.utils.bad_data_checkers.appointment_that_should_be_over",
                pod_name=PodNames.MPRACTICE_CORE,
            ),
        ]
        mock_stats_increment.assert_has_calls(expected_calls)


def test_find_appointments_with_missing_start_or_end_data(
    insert_appointments, member, practitioner
):
    with patch("utils.bad_data_checkers.increment") as mock_stats_increment:
        find_appointments_with_missing_start_or_end_data()
        expected_calls = [
            call(
                metric_name="api.utils.bad_data_checkers.appointment_with_missing_start_or_end_data",
                pod_name=PodNames.MPRACTICE_CORE,
            ),
            call(
                metric_name="api.utils.bad_data_checkers.appointment_with_missing_start_or_end_data",
                pod_name=PodNames.MPRACTICE_CORE,
            ),
            call(
                metric_name="api.utils.bad_data_checkers.appointment_with_missing_start_or_end_data",
                pod_name=PodNames.MPRACTICE_CORE,
            ),
            call(
                metric_name="api.utils.bad_data_checkers.appointment_with_missing_start_or_end_data",
                pod_name=PodNames.MPRACTICE_CORE,
            ),
        ]
        mock_stats_increment.assert_has_calls(expected_calls)
