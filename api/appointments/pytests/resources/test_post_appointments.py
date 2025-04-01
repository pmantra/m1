import datetime
import json
from unittest import mock
from unittest.mock import patch

import pytest

from appointments.models.constants import APPOINTMENT_STATES, PRIVACY_CHOICES
from appointments.models.needs_and_categories import NeedAppointment
from appointments.services.common import deobfuscate_appointment_id
from authz.models.roles import ROLES
from common.services.stripe import StripeCustomerClient
from models.products import Purposes
from models.tracks.client_track import TrackModifiers
from models.verticals_and_specialties import CX_VERTICAL_NAME, DOULA_ONLY_VERTICALS
from pytests import factories
from pytests.db_util import enable_db_performance_warnings

now = datetime.datetime.utcnow()


@pytest.fixture
def post_api(client, api_helpers):
    def _post_api(data, member):
        return client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

    return _post_api


@pytest.mark.parametrize("bool_variation", [True, False])
@patch("services.common.feature_flags.bool_variation")
def test_create_appointment(
    mock_bool_variation,
    client,
    api_helpers,
    setup_post_appointment_test,
    bool_variation,
):
    mock_bool_variation.return_value = bool_variation
    """Tests basic success case"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    data = appointment_setup_values.data
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201
    response_data = json.loads(res.data)
    assert "product" in response_data
    assert response_data["privacy"] == "basic"


@pytest.mark.parametrize("bool_variation", [True, False])
@patch("services.common.feature_flags.bool_variation")
def test_create_appointment_intl(
    mock_bool_variation,
    client,
    api_helpers,
    setup_post_appointment_test,
    bool_variation,
):
    mock_bool_variation.side_effect = lambda flag_name, *args, **kwargs: {
        "disco-5342-fix": False,
    }.get(flag_name, bool_variation)
    """Tests basic success case"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    member.member_profile.state.abbreviation = "ZZ"
    appointment_setup_values.practitioner.practitioner_profile.country_code = "FR"
    verticals = [factories.VerticalFactory.create()]
    appointment_setup_values.practitioner.practitioner_profile.verticals = verticals

    data = appointment_setup_values.data
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201
    response_data = json.loads(res.data)
    assert "product" in response_data
    assert response_data["privacy"] == "basic"
    assert response_data["appointment_type"] == "education_only"
    assert response_data["privilege_type"] == "international"


@pytest.mark.parametrize("bool_variation", [True, False])
@patch("services.common.feature_flags.bool_variation")
def test_create_appointment_intl_with_5432_ff_on(
    mock_bool_variation,
    client,
    api_helpers,
    setup_post_appointment_test,
    bool_variation,
):
    mock_bool_variation.side_effect = lambda flag_name, *args, **kwargs: {
        "disco-5342-fix": True,
    }.get(flag_name, bool_variation)
    """Tests basic success case"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    member.member_profile.state.abbreviation = "ZZ"
    appointment_setup_values.practitioner.practitioner_profile.country_code = "FR"
    verticals = [factories.VerticalFactory.create()]
    appointment_setup_values.practitioner.practitioner_profile.verticals = verticals

    data = appointment_setup_values.data
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201
    response_data = json.loads(res.data)
    assert "product" in response_data
    assert response_data["privacy"] == "basic"
    assert response_data["appointment_type"] == "education_only"
    assert response_data["privilege_type"] == "international"


@pytest.mark.parametrize("bool_variation", [True, False])
@patch("services.common.feature_flags.bool_variation")
def test_create_appointment_intl_with_us_provider(
    mock_bool_variation,
    client,
    api_helpers,
    setup_post_appointment_test,
    bool_variation,
):
    mock_bool_variation.side_effect = lambda flag_name, *args, **kwargs: {
        "disco-5342-fix": False,
    }.get(flag_name, bool_variation)

    """Tests basic success case"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    member.member_profile.state.abbreviation = "ZZ"
    appointment_setup_values.practitioner.practitioner_profile.country_code = "US"
    verticals = [factories.VerticalFactory.create(name=CX_VERTICAL_NAME)]
    appointment_setup_values.practitioner.practitioner_profile.verticals = verticals

    data = appointment_setup_values.data
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201
    response_data = json.loads(res.data)
    assert "product" in response_data
    assert response_data["privacy"] == "basic"
    assert response_data["appointment_type"] == "education_only"
    assert response_data["privilege_type"] == "international"


@pytest.mark.parametrize("bool_variation", [True])
@patch("maven.feature_flags.bool_variation")
def test_create_appointment_intl_with_us_provider_with_5432_ff_on(
    mock_bool_variation,
    client,
    api_helpers,
    setup_post_appointment_test,
    bool_variation,
):
    mock_bool_variation.side_effect = lambda flag_name, *args, **kwargs: {
        "disco-5342-fix": True,
    }.get(flag_name, bool_variation)

    """Tests basic success case"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    member.member_profile.state.abbreviation = "ZZ"
    appointment_setup_values.practitioner.practitioner_profile.country_code = "US"
    verticals = [factories.VerticalFactory.create(name=CX_VERTICAL_NAME)]
    appointment_setup_values.practitioner.practitioner_profile.verticals = verticals

    data = appointment_setup_values.data
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201
    response_data = json.loads(res.data)
    assert "product" in response_data
    assert response_data["privacy"] == "basic"
    assert response_data["appointment_type"] == "standard"
    assert response_data["privilege_type"] == "standard"


@pytest.mark.parametrize("bool_variation", [True, False])
@patch("services.common.feature_flags.bool_variation")
def test_create_appointment_with_filter_by_state_vertical(
    mock_bool_variation,
    client,
    api_helpers,
    setup_post_appointment_state_check,
    bool_variation,
):
    mock_bool_variation.return_value = bool_variation

    """Tests basic success case"""
    appointment_setup_values = setup_post_appointment_state_check()
    member = appointment_setup_values.member
    data = appointment_setup_values.data
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201
    response_data = json.loads(res.data)
    assert "product" in response_data
    assert response_data["privacy"] == "basic"


def test_create_appointment__base_db_calls(
    client,
    db,
    api_helpers,
    setup_post_appointment_test,
):
    """Tests that db calls don't go above a specified value"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    data = appointment_setup_values.data
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        with enable_db_performance_warnings(
            database=db,
            # warning_threshold=1,  # uncomment to to view all queries being made
            failure_threshold=45,
        ):
            res = client.post(
                "/api/v1/appointments",
                data=json.dumps(data),
                headers=api_helpers.json_headers(member),
            )
    assert res.status_code == 201
    assert "product" in json.loads(res.data)


def test_member_conflict(
    factories,
    client,
    api_helpers,
    practitioner_user,
    valid_appointment_with_user,
    member_with_add_appointment,
):
    """Tests error when the member has a conflicting appointment already"""
    practitioner_1 = practitioner_user()
    factories.ScheduleEventFactory.create(
        schedule=practitioner_1.schedule,
        ends_at=now + datetime.timedelta(minutes=500),
    )

    practitioner_2 = practitioner_user()
    factories.ScheduleEventFactory.create(
        schedule=practitioner_2.schedule,
        ends_at=now + datetime.timedelta(minutes=500),
    )

    start = now + datetime.timedelta(minutes=10)

    member = member_with_add_appointment
    ms = factories.ScheduleFactory.create(user=member)
    valid_appointment_with_user(
        practitioner=practitioner_2,
        member_schedule=ms,
        scheduled_start=start,
    )

    # Conflict appointment should return 400
    data = {
        "product_id": practitioner_1.products[0].id,
        "scheduled_start": start.isoformat(),
    }
    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )
    assert res.status_code == 400


def test_post_appointment__multiple_schedule_events(
    factories,
    client,
    api_helpers,
    practitioner_user,
    member_with_add_appointment,
):
    """Tests no error if the requested time spans 3+ schedule events"""
    start = now.replace(second=0, microsecond=0)

    practitioner = practitioner_user()
    product = practitioner.products[0]
    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    for i in range(100):
        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=start + datetime.timedelta(minutes=200 + i),
            ends_at=start + datetime.timedelta(minutes=201 + i),
        )

    data = {
        "product_id": product.id,
        "scheduled_start": (start + datetime.timedelta(minutes=220)).isoformat(),
    }
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201


def test_post_appointment__error_with_noncontiguous_events(
    factories,
    client,
    api_helpers,
    practitioner_user,
    member_with_add_appointment,
):
    """
    Tests that an error occurs if there are several non-contiguous events
    during the requested timeframe
    """
    start = now.replace(second=0, microsecond=0)

    practitioner = practitioner_user()
    product = practitioner.products[0]
    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=start + datetime.timedelta(minutes=200),
        ends_at=start + datetime.timedelta(minutes=222),
    )
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=start + datetime.timedelta(minutes=224),
        ends_at=start + datetime.timedelta(minutes=226),
    )
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=start + datetime.timedelta(minutes=228),
        ends_at=start + datetime.timedelta(minutes=240),
    )

    data = {
        "product_id": product.id,
        "scheduled_start": (start + datetime.timedelta(minutes=220)).isoformat(),
    }
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 400

    # Add the missing schedule events and try again.
    # We should get a success this time.
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=start + datetime.timedelta(minutes=222),
        ends_at=start + datetime.timedelta(minutes=224),
    )
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=start + datetime.timedelta(minutes=226),
        ends_at=start + datetime.timedelta(minutes=228),
    )

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201


def test_overlapping_no_member_conflict(
    client,
    api_helpers,
    setup_post_appointment_test,
):
    """Tests no error if member has an existing, non-conflicting appointment"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    product = appointment_setup_values.product
    data = appointment_setup_values.data

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201

    start = now + datetime.timedelta(minutes=20)
    no_conflict_start = start + datetime.timedelta(minutes=product.minutes)
    no_conflict_data = {
        "product_id": product.id,
        "scheduled_start": no_conflict_start.isoformat(),
    }
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(no_conflict_data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201


def test_no_conflict_cancelled(
    factories,
    client,
    api_helpers,
    practitioner_user,
    member_with_add_appointment,
):
    """Tests that we can create a new appointment at the same time as a previous cancelled appointment"""
    practitioner = practitioner_user()
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule, ends_at=now + datetime.timedelta(minutes=500)
    )

    product = practitioner.products[0]
    start = (now + datetime.timedelta(minutes=20)).replace(microsecond=0)

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    data = {"product_id": product.id, "scheduled_start": start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    data = json.loads(res.data)
    data["cancelled_at"] = now.isoformat()

    res = client.put(
        "/api/v1/appointments/%d" % data["id"],
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )
    res_data = json.loads(res.data)
    assert res_data["cancelled_at"]
    assert res_data["state"] == APPOINTMENT_STATES.cancelled
    assert res_data["scheduled_start"] == start.isoformat()

    data = {"product_id": product.id, "scheduled_start": start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201


def test_conflict_partial_overlap_over(
    factories,
    client,
    api_helpers,
    practitioner_user,
    member_with_add_appointment,
):
    """
    Tests error if the member attempts to create a new appointment that
    overlaps the beginning of an existing appointment
    """
    practitioner = practitioner_user()
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        ends_at=now + datetime.timedelta(minutes=500),
    )

    product = practitioner.products[0]
    early_start = now + datetime.timedelta(minutes=20)
    late_start = now + datetime.timedelta(minutes=25)

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    data = {"product_id": product.id, "scheduled_start": late_start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201

    data = {
        "product_id": product.id,
        "scheduled_start": early_start.isoformat(),
    }

    # The new appointment starts slightly before the existing appointment
    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )
    assert res.status_code == 400


def test_conflict_partial_overlap_under(
    factories,
    client,
    api_helpers,
    practitioner_user,
    member_with_add_appointment,
):
    """
    Tests error if the member attempts to create a new appointment that
    overlaps the end of an existing appointment
    """
    practitioner = practitioner_user()
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        ends_at=now + datetime.timedelta(minutes=500),
    )

    product = practitioner.products[0]
    early_start = now + datetime.timedelta(minutes=20)
    late_start = now + datetime.timedelta(minutes=25)

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    data = {"product_id": product.id, "scheduled_start": early_start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201

    data = {
        "product_id": product.id,
        "scheduled_start": late_start.isoformat(),
    }

    # The new appointment starts slightly after the existing appointment
    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )
    assert res.status_code == 400


def test_no_create_appointment_inside_buffer(
    factories,
    client,
    api_helpers,
    member_with_add_appointment,
    vertical_ca,
):
    """Tests error if you try to book an appointment within the practitioner's booking buffer"""
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=30,
        practitioner_profile__verticals=[vertical_ca],
    )
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule, ends_at=now + datetime.timedelta(minutes=500)
    )

    product = practitioner.products[0]
    start = now + datetime.timedelta(minutes=29)

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    data = {"product_id": product.id, "scheduled_start": start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 400
    assert json.loads(res.data)["message"] == "Please choose a later start time!"


def test_no_create_appointment_prep_buffer_15(
    factories,
    client,
    api_helpers,
    member_with_add_appointment,
):
    """Tests error if you try to book an appointment within the practitioner's prep buffer"""

    vertical = factories.VerticalFactory.create(
        products=[{"minutes": 15, "price": 60}],
        filter_by_state=False,
    )
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=30,
        practitioner_profile__default_prep_buffer=15,
        practitioner_profile__verticals=[vertical],
        products__minutes=15,
    )
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=now,
        ends_at=now + datetime.timedelta(days=2),
    )

    product = practitioner.products[0]

    # Start at noon tomorrow
    start = (now + datetime.timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )

    # Add first appointment at noon
    factories.AppointmentFactory.create_with_practitioner(
        practitioner,
        scheduled_start=start,
        scheduled_end=start + datetime.timedelta(minutes=product.minutes),
    )

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    # Try to scheudle the second appointment 5 minutes after the first one ends
    second_appt_start = start + datetime.timedelta(minutes=20)
    data = {"product_id": product.id, "scheduled_start": second_appt_start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 400
    assert (
        json.loads(res.data)["message"]
        == "That start time is unavailable! Most likely there is a booking conflict."
    )


def test_no_create_appointment_no_cancellation(
    factories,
    client,
    api_helpers,
    member_with_add_appointment,
    vertical_ca,
):
    """Tests error if you try to book an appointment when the practitioner has no cancellation policy"""
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_ca],
        practitioner_profile__default_cancellation_policy=None,
    )
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule, ends_at=now + datetime.timedelta(minutes=500)
    )

    product = practitioner.products[0]
    start = now + datetime.timedelta(minutes=20)

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    data = {"product_id": product.id, "scheduled_start": start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 400
    assert (
        json.loads(res.data)["message"]
        == "No cancellation policy for that practitioner."
    )


def test_no_create_appointment_with_self(
    factories,
    client,
    api_helpers,
    practitioner_user,
):
    """Tests error if you try to book an appointment with yourself"""
    c = factories.CapabilityFactory.create(object_type="appointment", method="post")
    factories.RoleFactory.create(name=ROLES.practitioner, capabilities=[c])
    practitioner = practitioner_user()
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule, ends_at=now + datetime.timedelta(minutes=500)
    )

    product = practitioner.products[0]
    start = now + datetime.timedelta(minutes=29)

    data = {"product_id": product.id, "scheduled_start": start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(practitioner),
        )
    assert res.status_code == 400
    assert json.loads(res.data)["message"] == "Cannot book with yourself!"


@patch("appointments.resources.appointments.log.warning")
def test_cx_not_in_care_team_logged(
    mock_log,
    factories,
    client,
    api_helpers,
    setup_post_appointment_test,
    practitioner_user,
):
    # Given - a member is booking for a cx not in their care team
    appointment_setup_values = setup_post_appointment_test()
    assigned_cx = practitioner_user()
    unassigned_cx = practitioner_user()
    member = factories.EnterpriseUserFactory.create(care_team=[assigned_cx])
    factories.ScheduleFactory.create(user=member)
    data = appointment_setup_values.data
    data["product_id"] = unassigned_cx.products[0].id

    # When - we call the endpoint
    client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    # Then - the log is recorded
    mock_log.assert_any_call(
        "Appointment being booked with care coordinator not in care team",
        user_id=member.id,
        practitioner_id=unassigned_cx.id,
        care_team=[ct.user_id for ct in member.care_team],
    )


def test_create_appointment_2_events(
    factories,
    client,
    api_helpers,
    practitioner_user,
    member_with_add_appointment,
):
    """Tests success when scheduling on the boundary of two AVAILABLE events"""
    practitioner = practitioner_user()
    event_end = now + datetime.timedelta(minutes=60)
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        ends_at=event_end,
    )
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=event_end,
        ends_at=event_end + datetime.timedelta(minutes=60),
    )

    product = practitioner.products[0]

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    data = {
        "product_id": product.id,
        "scheduled_start": (now + datetime.timedelta(minutes=59)).isoformat(),
    }

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201


def test_create_appointment_bad_time(
    factories,
    client,
    api_helpers,
    practitioner_user,
    member_with_add_appointment,
):
    """Tests error if practitioner isn't available at scheduled_start"""
    practitioner = practitioner_user()
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule, ends_at=now + datetime.timedelta(minutes=60)
    )

    product = practitioner.products[0]
    start = now + datetime.timedelta(minutes=61)

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    data = {"product_id": product.id, "scheduled_start": start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 400
    assert (
        json.loads(res.data)["message"]
        == "That start time is unavailable! Most likely there is a booking conflict."
    )


def test_create_appointment_greater_than_7_less_than_30_days(
    factories,
    client,
    api_helpers,
    practitioner_user,
    post_api,
    member_with_add_appointment,
):
    """
    Feature flag BOOKING_EXTEND_DATE_30_DAYS test coverage for booking > 7 and < 30 days
    """
    practitioner = practitioner_user()
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule, ends_at=now + datetime.timedelta(days=21)
    )

    product = practitioner.products[0]
    start = now + datetime.timedelta(days=8)

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    data = {"product_id": product.id, "scheduled_start": start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        # Tests a user cannot book an appointment > 30 days
        start = now + datetime.timedelta(days=31)
        data = {"product_id": product.id, "scheduled_start": start.isoformat()}
        res = post_api(data, member)

        assert res.status_code == 400
        assert (
            json.loads(res.data)["message"]
            == "Cannot currently schedule an appt > 7 days!"
        )

        # Tests a user can book an appointment > 7 days
        start = now + datetime.timedelta(days=10)
        data = {"product_id": product.id, "scheduled_start": start.isoformat()}
        res = post_api(data, member)

        assert res.status_code == 201


def test_first_cx_purpose_planning(
    client, api_helpers, setup_post_appointment_test, factories
):
    """
    A user's first appointment should be 'birth_needs_assessment' when:
    - First Appointment
    - With Care Advocate (set in the `practitioner_user` fixture)
    - User has an upcoming due date (automatically set by our factories)
    """
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    factories.MemberTrackFactory.create(name="postpartum", user=member)
    factories.UserOrganizationEmployeeFactory(user=member)
    data = appointment_setup_values.data
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201
    assert json.loads(res.data)["purpose"] == "birth_needs_assessment"


def test_first_cx_purpose_introduction(
    factories,
    client,
    api_helpers,
    practitioner_user,
):
    """
    A user's first appointment should be 'birth_needs_assessment' when:
    - First Appointment
    - With Care Advocate (set in the `practitioner_user` fixture)
    - No upcoming due date
    """
    practitioner = practitioner_user()
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule, ends_at=now + datetime.timedelta(minutes=500)
    )

    product = practitioner.products[0]
    start = now + datetime.timedelta(minutes=20)

    c = factories.CapabilityFactory.create(object_type="appointment", method="post")
    r = factories.RoleFactory.create(name="member", capabilities=[c])

    member = factories.DefaultUserFactory.create(health_profile__due_date=None)
    factories.MemberProfileFactory.create(user=member, role=r)
    factories.MemberTrackFactory.create(name="pregnancy", user=member)
    factories.UserOrganizationEmployeeFactory(user=member)
    factories.ScheduleFactory.create(user=member)

    data = {"product_id": product.id, "scheduled_start": start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201
    assert json.loads(res.data)["purpose"] == "introduction"


def test_set_purpose(
    factories,
    client,
    api_helpers,
    practitioner_user,
    member_with_add_appointment,
    valid_appointment_with_user,
):
    """If it isn't the user's first appointment, it should use the product.purpose"""
    product = factories.ProductFactory(purpose=Purposes.POSTPARTUM_NEEDS_ASSESSMENT)
    practitioner = product.practitioner
    # It seems there's some state issue with this particular test with models tests,
    # causing the schedule ends is less than event ends, expanding schedule ends as workaround
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule, ends_at=now + datetime.timedelta(minutes=700)
    )

    start = now + datetime.timedelta(minutes=20)

    member = member_with_add_appointment
    ms = factories.ScheduleFactory.create(user=member)
    valid_appointment_with_user(
        practitioner=practitioner,
        member_schedule=ms,
        scheduled_start=start,
    )

    start = start + datetime.timedelta(minutes=product.minutes + 60)

    data = {"product_id": product.id, "scheduled_start": start.isoformat()}

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201
    assert json.loads(res.data)["purpose"] == product.purpose.value


def test_create_appointment_all_credit(
    client,
    api_helpers,
    setup_post_appointment_test,
    new_credit,
):
    """Tests if member can create an appointment with all credit"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    product = appointment_setup_values.product
    data = appointment_setup_values.data

    credit = new_credit(product.price, member)

    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)

    assert res.status_code == 201
    assert credit.appointment_id == deobfuscate_appointment_id(res_data["id"])


def test_create_appointment_fails_no_card(
    client,
    api_helpers,
    setup_post_appointment_test,
):
    """Tests that member cannot create an appointment with no credit card (e.g. could not authorize payment)"""
    with patch.object(
        StripeCustomerClient,
        "create_charge",
        return_value=None,
    ), patch.object(StripeCustomerClient, "list_cards", return_value=[]):
        appointment_setup_values = setup_post_appointment_test()
        member = appointment_setup_values.member
        data = appointment_setup_values.data

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        assert res.status_code == 400


def test_create_appointment_fails_no_card_credit_state_ok(
    client,
    api_helpers,
    setup_post_appointment_test,
    new_credit,
):
    """Tests that member cannot create an appointment with no credit card but with existing credit"""
    with patch.object(
        StripeCustomerClient,
        "create_charge",
        return_value=None,
    ), patch.object(StripeCustomerClient, "list_cards", return_value=[]):
        appointment_setup_values = setup_post_appointment_test()
        member = appointment_setup_values.member
        data = appointment_setup_values.data
        new_credit(1, member)

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        assert res.status_code == 400


def test_create_appointment_with_note(setup_post_appointment_test, client, api_helpers):
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    data = appointment_setup_values.data
    note = "foobar"
    data["pre_session"] = {"notes": note}
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201
    data = json.loads(res.data)
    assert "product" in data
    assert data["pre_session"]["notes"] == note


def test_create_appointment_no_pharmacy_id(
    client,
    api_helpers,
    setup_post_appointment_test,
):
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    data = appointment_setup_values.data
    data["prescription_info"] = {}
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 201
    data = json.loads(res.data)
    assert data["prescription_info"]["pharmacy_id"] == ""


@patch("appointments.resources.appointments.ratelimiting.ratelimited")
def test_create_appointment__need_appointment_table_populates_correctly(
    ratelimit_mock,
    db,
    client,
    api_helpers,
    factories,
    setup_post_appointment_test,
):
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    data = appointment_setup_values.data

    expected_need = factories.NeedFactory.create(name="test_need")
    data["need_id"] = expected_need.id

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

    assert res.status_code == 201
    data = res.json
    assert data.get("need_id") == expected_need.id

    na_table_count = db.session.query(NeedAppointment).count()
    assert na_table_count == 1


@patch("appointments.resources.appointments.ratelimiting.ratelimited")
def test_create_appointment_null_need_does_not_set_row(
    ratelimit_mock,
    db,
    client,
    api_helpers,
    setup_post_appointment_test,
):
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    data = appointment_setup_values.data

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

    assert res.status_code == 201
    data = res.json
    assert data.get("need_id") is None
    na_table_count = db.session.query(NeedAppointment).count()
    assert na_table_count == 0


@patch("appointments.resources.appointments.log.warning")
@patch("appointments.resources.appointments.ratelimiting.ratelimited")
def test_create_appointment_bad_need_id_emits_log(
    ratelimit_mock,
    warn_log_mock,
    client,
    api_helpers,
    setup_post_appointment_test,
):
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    data = appointment_setup_values.data

    data["need_id"] = 5

    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

    assert res.status_code == 201
    warn_log_mock.assert_any_call(
        "need_id not found when creating appointment",
        need_id=data["need_id"],
    )


@pytest.mark.parametrize(
    "vertical_name,expected_status_code,expected_status_message",
    [
        ("Doula and childbirth educator", 201, None),
        (
            "Wellness Coach",
            400,
            "Doula member is not allowed to book with a non-doula provider",
        ),
    ],
)
@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_create_appointment__doula_only_member(
    mock_should_enable_doula_only_track,
    vertical_name,
    expected_status_code,
    expected_status_message,
    factories,
    doula_only_member_with_add_appointment_permission,
    client,
    api_helpers,
):

    # Given
    member = doula_only_member_with_add_appointment_permission

    # set up doula only provider
    vertical = factories.VerticalFactory.create(
        name=vertical_name,
    )

    active_member_track = member.active_tracks[0]
    client_track_id = active_member_track.client_track_id

    # create a VerticalAccessByTrack record to allow vertical <> client track interaction
    if vertical.name.lower() in DOULA_ONLY_VERTICALS:
        factories.VerticalAccessByTrackFactory.create(
            client_track_id=client_track_id,
            vertical_id=vertical.id,
            track_modifiers=TrackModifiers.DOULA_ONLY,
        )

    product = factories.ProductFactory.create(minutes=60, price=60, vertical=vertical)
    doula_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[product.vertical], products=[product]
    )
    product.practitioner = doula_provider

    # set up schedule details for provider and member
    schedule_start = now.replace(microsecond=0)
    factories.ScheduleEventFactory.create(
        schedule=doula_provider.schedule,
        starts_at=schedule_start,
        ends_at=now + datetime.timedelta(minutes=500),
    )
    factories.ScheduleFactory.create(user=member)

    start = schedule_start + datetime.timedelta(minutes=20)

    data = {
        "product_id": product.id,
        "scheduled_start": start.isoformat(),
        "privacy": PRIVACY_CHOICES.anonymous,
    }

    # When
    with patch(
        "appointments.resources.appointments.Appointment.authorize_payment"
    ) as payment_mock:
        payment_mock.return_value = True

        res = client.post(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

    # Then
    assert res.status_code == expected_status_code
    if expected_status_message:
        assert json.loads(res.data)["message"] == expected_status_message
