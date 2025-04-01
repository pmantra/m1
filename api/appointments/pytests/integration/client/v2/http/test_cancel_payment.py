import pytest

from appointments.models.payments import FeeAccountingEntry, PaymentAccountingEntry
from payments.services.appointment_payments import AppointmentPaymentsService
from storage.connection import db


# TODO: Re-enable this test
@pytest.mark.skip(reason="Flaky")
def test_cancel_payment_by_member_invalid_product_id(
    client,
    api_helpers,
    member_with_add_appointment,
):
    data = {
        "appointment_id": 1,
        "product_id": 1,
        "member_id": member_with_add_appointment.id,
        "provider_id": 1,
        "scheduled_start": "2024-06-12T10:00:00",
        "scheduled_end": "2024-06-12T12:00:00",
    }
    res = client.post(
        "/api/v2/appointments/process_payments_for_cancel",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 404
    assert res.json["message"] == "Product not found"


def test_cancel_payment_api_invalid_request(
    client,
    api_helpers,
    member_with_add_appointment,
):
    # request missing product_id and provider_id
    data = {
        "appointment_id": 1,
        "member_id": 1,
        "scheduled_start": "2024-06-12T10:00:00",
        "scheduled_end": "2024-06-12T12:00:00",
    }
    res = client.post(
        "/api/v2/appointments/process_payments_for_cancel",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert res.json["message"] == "Invalid request to cancel payment"


def test_cancel_payment_api_by_provider(
    client,
    api_helpers,
    factories,
    scheduled_appointment,
    patch_authorize_payment,
    patch_refund_payment,
):
    appointment_id = scheduled_appointment.id
    product_id = scheduled_appointment.product.id
    member = scheduled_appointment.member
    member_id = member.id
    provider = scheduled_appointment.product.practitioner
    provider_id = scheduled_appointment.product.practitioner.id
    # Simulate the case where payment was authorized and completed
    scheduled_appointment.authorize_payment()
    AppointmentPaymentsService(db.session).complete_payment(
        appointment_id=appointment_id, product_price=scheduled_appointment.product.price
    )

    data = {
        "appointment_id": appointment_id,
        "product_id": product_id,
        "member_id": member_id,
        "provider_id": provider_id,
        "scheduled_start": scheduled_appointment.scheduled_start.isoformat(),
        "scheduled_end": scheduled_appointment.scheduled_end.isoformat(),
    }
    res = client.post(
        "/api/v2/appointments/process_payments_for_cancel",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(provider),
    )

    assert res.status_code == 200
    assert res.json["success"]
    # Check PaymentAccountingEntry is cancelled
    pae = PaymentAccountingEntry.query.filter_by(appointment_id=appointment_id).first()
    assert pae is not None
    assert pae.member_id == member_id
    assert pae.is_captured
    assert pae.cancelled_at is not None


def test_cancel_payment_api_by_member(
    client, api_helpers, factories, scheduled_appointment, patch_authorize_payment
):
    appointment_id = scheduled_appointment.id
    product_id = scheduled_appointment.product.id
    member = scheduled_appointment.member
    member_id = member.id
    provider_id = scheduled_appointment.product.practitioner.id
    # Simulate the case where payment was authorized and completed
    scheduled_appointment.authorize_payment()
    AppointmentPaymentsService(db.session).complete_payment(
        appointment_id=appointment_id, product_price=scheduled_appointment.product.price
    )

    pae = PaymentAccountingEntry.query.filter_by(appointment_id=appointment_id).first()
    pae_captured_at = pae.captured_at
    assert pae_captured_at is not None
    assert pae.is_captured

    data = {
        "appointment_id": appointment_id,
        "product_id": product_id,
        "member_id": member_id,
        "provider_id": provider_id,
        "scheduled_start": scheduled_appointment.scheduled_start.isoformat(),
        "scheduled_end": scheduled_appointment.scheduled_end.isoformat(),
    }
    res = client.post(
        "/api/v2/appointments/process_payments_for_cancel",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    assert res.json["success"]
    # Check PaymentAccountingEntry is not re-captured
    pae = PaymentAccountingEntry.query.filter_by(appointment_id=appointment_id).first()
    assert pae is not None
    assert pae.member_id == member_id
    assert pae.is_captured
    assert pae.captured_at == pae_captured_at

    #     Make sure FeeAccountingEntry created for practitioner fees
    fae = FeeAccountingEntry.query.filter(
        FeeAccountingEntry.practitioner_id == provider_id,
        FeeAccountingEntry.appointment_id == appointment_id,
    ).first()

    assert fae is not None
    assert fae.amount is not None
