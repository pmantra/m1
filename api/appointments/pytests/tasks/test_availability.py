import datetime
from unittest.mock import patch

from appointments.tasks.availability import (
    create_recurring_availability,
    delete_recurring_availability,
    report_doula_availability,
    update_staff_practitioners_percent_booked,
)
from common.stats import PodNames
from payments.models.practitioner_contract import ContractType
from payments.pytests.factories import PractitionerContractFactory


@patch("appointments.tasks.availability.percent_booked_for_profile")
def test_update_staff_practitioners_percent_booked__no_profiles(
    mock_percent_booked_for_profile,
):

    # Given no practitioners exist

    # When calling update_staff_practitioners_percent_booked
    update_staff_practitioners_percent_booked()

    # Then percent_booked_for_profile is never called
    mock_percent_booked_for_profile.assert_not_called()


@patch("appointments.tasks.availability.percent_booked_for_profile")
def test_update_staff_practitioners_percent_booked__a_practitioner_that_emits_fees_and_one_that_doesnt(
    mock_percent_booked_for_profile, factories
):

    # Given a by appt and a non-by appt practitioner with active and inactive contracts
    by_appt_prac = factories.PractitionerUserFactory()
    # inactive contract that does not emits_fee
    PractitionerContractFactory.create(
        practitioner=by_appt_prac.practitioner_profile,
        contract_type=ContractType.W2,
        start_date=datetime.date.today() - datetime.timedelta(days=10),
        end_date=datetime.date.today() - datetime.timedelta(days=5),
    )
    # active contract that emits_fee
    PractitionerContractFactory.create(
        practitioner=by_appt_prac.practitioner_profile,
        contract_type=ContractType.BY_APPOINTMENT,
        start_date=datetime.date.today() - datetime.timedelta(days=1),
    )

    none_by_appt_prac = factories.PractitionerUserFactory()
    # inactive contract that does emits_fee
    PractitionerContractFactory.create(
        practitioner=none_by_appt_prac.practitioner_profile,
        contract_type=ContractType.BY_APPOINTMENT,
        start_date=datetime.date.today() - datetime.timedelta(days=10),
        end_date=datetime.date.today() - datetime.timedelta(days=5),
    )
    # active contract that does not emits_fee
    PractitionerContractFactory.create(
        practitioner=none_by_appt_prac.practitioner_profile,
        contract_type=ContractType.W2,
        start_date=datetime.date.today() - datetime.timedelta(days=1),
    )

    # When calling update_staff_practitioners_percent_booked
    recent_days = 30
    update_staff_practitioners_percent_booked(recent_days=recent_days)

    # Then percent_booked_for_profile is called once and for the none_by_appt_prac
    mock_percent_booked_for_profile.assert_called_once_with(
        none_by_appt_prac.practitioner_profile, recent_days
    )


@patch(
    "appointments.tasks.availability.RecurringScheduleAvailabilityService.create_schedule_recurring_block"
)
def test_create_recurring_availability(
    mock_create_schedule_recurring_block,
    factories,
):
    practitioner = factories.PractitionerUserFactory.create()
    now = datetime.datetime.now(datetime.timezone.utc)
    create_recurring_availability(
        starts_at=now,
        ends_at=now + datetime.timedelta(days=2),
        frequency="WEEKLY",
        until=now + datetime.timedelta(weeks=1),
        user_id=practitioner.id,
        week_days_index=[2],
        member_timezone="America/New_York",
    )

    mock_create_schedule_recurring_block.assert_called()


@patch(
    "appointments.tasks.availability.RecurringScheduleAvailabilityService.delete_schedule_recurring_block"
)
def test_delete_recurring_availability_not_found(
    mock_delete_schedule_recurring_block,
    factories,
    practitioner_user,
    schedule,
):
    delete_recurring_availability(
        user_id=practitioner_user().id,
        schedule_recurring_block_id=12345,
    )

    mock_delete_schedule_recurring_block.assert_not_called()


@patch(
    "appointments.tasks.availability.RecurringScheduleAvailabilityService.delete_schedule_recurring_block"
)
def test_delete_recurring_availability(
    mock_delete_schedule_recurring_block,
    factories,
    practitioner_user,
    schedule,
):
    start_date = datetime.datetime(2024, 4, 1, 0, 0, 0)
    recurring_block = factories.ScheduleRecurringBlockFactory.create(
        schedule=schedule,
        starts_at=start_date,
        ends_at=start_date + datetime.timedelta(hours=2),
        until=start_date + datetime.timedelta(weeks=1),
    )

    delete_recurring_availability(
        user_id=practitioner_user().id,
        schedule_recurring_block_id=recurring_block.id,
    )

    mock_delete_schedule_recurring_block.assert_called()


@patch("appointments.tasks.availability.stats.gauge")
def test_report_doula_availability(mock_metric, factories):
    # Given doula with availability within 28 days
    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[
            factories.VerticalFactory.create(name="Doula and childbirth educator")
        ],
        practitioner_profile__next_availability=datetime.datetime.now()  # noqa
        + datetime.timedelta(days=3),
    )

    # when
    report_doula_availability()

    # then we get doula availability
    mock_metric.assert_called_with(
        metric_name="appointments.tasks.availability.report_doula_availability",
        metric_value=1,
        pod_name=PodNames.CARE_DISCOVERY,
    )


@patch("appointments.tasks.availability.stats.gauge")
def test_report_doula_availability__non_doula_prac(mock_metric, factories):
    # Given 3 practitioners who should all be filtered out
    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[
            factories.VerticalFactory.create(name="OB-GYN")
        ],
        practitioner_profile__next_availability=datetime.datetime.now()  # noqa
        + datetime.timedelta(days=3),
    )
    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[
            factories.VerticalFactory.create(name="Care Advocate")
        ],
        practitioner_profile__next_availability=datetime.datetime.now()  # noqa
        + datetime.timedelta(days=3),
    )
    factories.PractitionerUserFactory.create(
        practitioner_profile__active=False,
        practitioner_profile__verticals=[
            factories.VerticalFactory.create(name="Doula and childbirth educator")
        ],
        practitioner_profile__next_availability=datetime.datetime.now()  # noqa
        + datetime.timedelta(days=3),
    )

    # when
    report_doula_availability()

    # then we found no doula availability
    mock_metric.assert_called_with(
        metric_name="appointments.tasks.availability.report_doula_availability",
        metric_value=0,
        pod_name=PodNames.CARE_DISCOVERY,
    )


@patch("appointments.tasks.availability.stats.gauge")
def test_report_doula_availability__no_avail_28_days(mock_metric, factories):
    # Given doula with availability outside of 28 days
    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[
            factories.VerticalFactory.create(name="Doula and childbirth educator")
        ],
        practitioner_profile__next_availability=datetime.datetime.now()  # noqa
        + datetime.timedelta(days=29),
    )

    # when
    report_doula_availability()

    # then we will get no doula availability
    mock_metric.assert_called_with(
        metric_name="appointments.tasks.availability.report_doula_availability",
        metric_value=0,
        pod_name=PodNames.CARE_DISCOVERY,
    )
