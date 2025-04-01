import datetime
from unittest.mock import ANY, patch

import pytest

from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.payments import FeeAccountingEntry, PaymentAccountingEntry
from appointments.tasks.appointments import appointment_completion
from common.services.stripe import StripeCustomerClient
from incentives.models.incentive import IncentiveAction
from incentives.models.incentive_fulfillment import IncentiveStatus
from pytests.stripe_fixtures import uncaptured_payment

now = datetime.datetime.utcnow()
p15 = now + datetime.timedelta(minutes=15)
p60 = now + datetime.timedelta(minutes=60)


@pytest.fixture
def finish_appointment(put_appointment_on_endpoint, api_helpers):
    def _finish_appointment(appointment):
        api_id = appointment.api_id
        a_id = appointment.id
        member = appointment.member
        practitioner = appointment.practitioner
        data = {
            "member_started_at": now.isoformat(),
            "member_ended_at": p60.isoformat(),
        }
        put_appointment_on_endpoint(
            api_id=api_id, user=member, data_json_string=api_helpers.json_data(data)
        )

        data = {
            "practitioner_started_at": now.isoformat(),
            "practitioner_ended_at": p60.isoformat(),
        }
        put_appointment_on_endpoint(
            api_id=api_id,
            user=practitioner,
            data_json_string=api_helpers.json_data(data),
        )

        appointment_completion(a_id)

    return _finish_appointment


def get_payments_and_fees(a):
    fees = FeeAccountingEntry.query.filter_by(appointment_id=a.id).all()
    payments = PaymentAccountingEntry.query.filter_by(appointment_id=a.id).all()
    return fees, payments


def test_appointment_completion_paid_with_credit(
    valid_appointment, finish_appointment, new_credit
):
    a = valid_appointment()
    new_credit(amount=2000, user=a.member)
    a.authorize_payment()
    finish_appointment(a)
    fees, payments = get_payments_and_fees(a)

    assert a.state == APPOINTMENT_STATES.payment_resolved
    assert len(fees) == 1
    assert len(payments) == 0
    assert a.fee_paid
    assert a.fee_paid_at


def test_appointment_completion_paid_with_stripe(
    valid_appointment, finish_appointment, patch_authorize_payment
):
    a = valid_appointment()
    a.authorize_payment()
    finish_appointment(a)
    fees, payments = get_payments_and_fees(a)

    assert a.state == APPOINTMENT_STATES.payment_resolved
    assert len(fees) == 1
    assert len(payments) == 1
    assert a.fee_paid
    assert a.fee_paid_at


def test_appointment_completion_on_phone_call(
    valid_appointment, client, api_helpers, finish_appointment, patch_authorize_payment
):
    a = valid_appointment()
    a.authorize_payment()

    data = {"member_started_at": now.isoformat()}
    client.put(
        f"/api/v1/appointments/{a.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(a.member),
    )

    data = {
        "phone_call_at": p15.isoformat(),
        "practitioner_started_at": now.isoformat(),
    }
    client.put(
        f"/api/v1/appointments/{a.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(a.practitioner),
    )

    finish_appointment(a)
    fees, payments = get_payments_and_fees(a)

    assert a.state == APPOINTMENT_STATES.payment_resolved
    assert len(fees) == 1
    assert len(payments) == 1
    assert a.fee_paid
    assert a.fee_paid_at


def test_appointment_completion_capture_fails(
    valid_appointment, finish_appointment, patch_authorize_payment
):
    with patch.object(
        StripeCustomerClient, "capture_charge", return_value=None
    ), patch.object(
        StripeCustomerClient, "create_charge", return_value=uncaptured_payment
    ):
        a = valid_appointment()
        a.authorize_payment()
        finish_appointment(a)
        fees, payments = get_payments_and_fees(a)
        assert a.state == APPOINTMENT_STATES.payment_pending
        assert len(fees) == 1
        assert len(payments) == 1
        assert a.payment.amount_captured is None


def test_appointment_completion_capture_retry_success(
    valid_appointment, finish_appointment, patch_authorize_payment
):
    a = valid_appointment()
    a.authorize_payment()
    finish_appointment(a)
    fees, payments = get_payments_and_fees(a)

    assert a.state == APPOINTMENT_STATES.payment_resolved
    assert len(fees) == 1
    assert len(payments) == 1
    assert a.fee_paid
    assert a.fee_paid_at


def test_appointment_completion__incentive_not_earned_because_appt_is_not_intro(
    valid_appointment, finish_appointment, factories, patch_authorize_payment
):
    # Given an appt that is not intro and an incentive configured for the member, which has been seen
    a = valid_appointment()
    a.purpose = "a_not_intro_purpose"

    member_track = a.member.current_member_track

    incentive = factories.IncentiveFactory()

    incentivized_action = IncentiveAction.CA_INTRO
    incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
        member_track=member_track,
        incentive=incentive,
        incentivized_action=incentivized_action,
        status=IncentiveStatus.SEEN,
    )

    # When finishing the appointment
    finish_appointment(a)

    # Then the incentive associated to the appointment is still marked as seen
    assert incentive_fulfillment.status == IncentiveStatus.SEEN


def test_appointment_completion__incentive_earned_because_appt_is_intro_and_incentive_fulfillment_exists(
    valid_appointment, finish_appointment, factories, patch_authorize_payment
):
    # Given an intro appt and an incentive_fulfillment configured for the member, which has been seen
    a = valid_appointment()
    a.purpose = "introduction"

    member_track = a.member.current_member_track

    incentive = factories.IncentiveFactory()

    incentivized_action = IncentiveAction.CA_INTRO
    incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
        member_track=member_track,
        incentive=incentive,
        incentivized_action=incentivized_action,
        status=IncentiveStatus.SEEN,
    )

    # When finishing the appointment
    finish_appointment(a)

    # Then the incentive associated to the appointment gets set as earned
    assert incentive_fulfillment.status == IncentiveStatus.EARNED


# Note: This test should be removed as part of KICK-1588
@patch(
    "incentives.repository.incentive_fulfillment.IncentiveFulfillmentRepository.create"
)
@patch("incentives.services.incentive_organization.log.warning")
def test_appointment_completion__incentive_is_earned_because_appt_is_intro_but_no_incentive_fulfillment_exists_but_incentive_is_configured(
    mock_log_warning,
    mock_create_incentive_fulfillment,
    valid_appointment,
    finish_appointment,
    factories,
    patch_authorize_payment,
):
    # Given an appt that is intro, an incentive is configured, but no incentive fulfillment exists
    a = valid_appointment()
    a.purpose = "introduction"

    # Create incentive
    user = a.member
    user.member_profile.country_code = "US"
    country_code = user.member_profile.country_code
    member_track = user.current_member_track
    org = member_track.client_track.organization

    incentive_track = member_track.name
    incentive_action = IncentiveAction.CA_INTRO

    incentive = factories.IncentiveFactory.create()
    incentive_organization = factories.IncentiveOrganizationFactory.create(
        incentive=incentive,
        organization=org,
        action=incentive_action,
        track_name=incentive_track,
    )
    factories.IncentiveOrganizationCountryFactory.create(
        incentive_organization=incentive_organization,
        country_code=country_code,
    )

    # When finishing the appointment
    finish_appointment(a)

    # Then assert we get the log warning saying no incentive fulfillment exists but incentive is configured
    mock_log_warning.assert_called_once_with(
        "Member has no incentive-fulfillment record, is not a transition, started track after implementation, and is currently eligible for an incentive. Will create EARNED incentive-fulfillment record.",
        user_incentive_id=incentive.id,
        incentivized_action=IncentiveAction.CA_INTRO,
        member_track_id=member_track.id,
        track_name=member_track.name,
        user_id=user.id,
    )
    # and we create an EARNED incentive-fulfillment record
    mock_create_incentive_fulfillment.assert_called_once_with(
        incentive_id=incentive.id,
        member_track_id=member_track.id,
        incentivized_action=incentive_action,
        date_status_changed=ANY,
        status=IncentiveStatus.EARNED,
    )


@patch("incentives.services.incentive_organization.log.info")
def test_appointment_completion__incentive_not_earned_because_appt_is_intro_but_no_incentive_fulfillment_exists_and_incentive_is_not_configured(
    mock_log_info,
    valid_appointment,
    finish_appointment,
    patch_authorize_payment,
):
    # Given an appt that is intro, no incentive is configured and no incentive fulfillment exists
    a = valid_appointment()
    a.purpose = "introduction"
    member_track = a.member.current_member_track

    # When finishing the appointment
    finish_appointment(a)

    # Then assert we get the log warning saying no incentive fulfillment exists but incentive is configured
    mock_log_info.assert_called_with(
        "No incentive marked as earned as incentive_fulfillment was not found, which makes sense as user is not eligible for one",
        incentivized_action=IncentiveAction.CA_INTRO,
        member_track_id=member_track.id,
    )
