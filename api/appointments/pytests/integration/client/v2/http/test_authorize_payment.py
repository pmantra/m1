from appointments.models.payments import PaymentAccountingEntry


def test_authorize_payment_api_invalid_product_id(
    client,
    api_helpers,
    member_with_add_appointment,
):
    data = {
        "appointment_id": 1,
        "product_id": 1,
        "member_id": 1,
        "provider_id": 1,
        "scheduled_start": "2024-06-12T10:00:00",
        "scheduled_end": "2024-06-12T12:00:00",
    }
    res = client.post(
        "/api/v2/appointments/reserve_payment_or_credits",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 404
    assert res.json["message"] == "Product not found"


def test_authorize_payment_api_invalid_request(
    client,
    api_helpers,
    member_with_add_appointment,
):
    # request missing scheduled_start & scheduled_end
    data = {"appointment_id": 1, "product_id": 1, "member_id": 1}
    res = client.post(
        "/api/v2/appointments/reserve_payment_or_credits",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )
    assert res.status_code == 400
    assert res.json["message"] == "Invalid request to authorize payment"


def test_authorize_payment_api_with_no_mono_appt(
    client, api_helpers, member_with_add_appointment, factories, patch_authorize_payment
):
    appointment_id = 1
    product = factories.ProductFactory.create()
    data = {
        "appointment_id": appointment_id,
        "product_id": product.id,
        "member_id": member_with_add_appointment.id,
        "provider_id": product.practitioner.id,
        "scheduled_start": "2024-06-12T10:00:00",
        "scheduled_end": "2024-06-12T12:00:00",
    }
    res = client.post(
        "/api/v2/appointments/reserve_payment_or_credits",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(member_with_add_appointment),
    )

    assert res.status_code == 200
    assert res.json["success"]
    # Sanity check new PaymentAccountEntry is created
    pae = PaymentAccountingEntry.query.filter_by(appointment_id=appointment_id).first()
    assert pae is not None
    assert pae.member_id == member_with_add_appointment.id


def test_authorize_payment_api_with_existing_mono_appt(
    client, api_helpers, factories, scheduled_appointment, patch_authorize_payment
):
    appointment_id = scheduled_appointment.id
    product_id = scheduled_appointment.product.id
    member = scheduled_appointment.member
    member_id = member.id
    # Simulate the case where payment already created
    scheduled_appointment.authorize_payment()
    pae = PaymentAccountingEntry.query.filter_by(appointment_id=appointment_id).first()
    pae_created_at = pae.created_at

    data = {
        "appointment_id": appointment_id,
        "product_id": product_id,
        "member_id": member_id,
        "provider_id": scheduled_appointment.product.practitioner.id,
        "scheduled_start": scheduled_appointment.scheduled_start.isoformat(),
        "scheduled_end": scheduled_appointment.scheduled_end.isoformat(),
    }
    res = client.post(
        "/api/v2/appointments/reserve_payment_or_credits",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    assert res.json["success"]
    # Sanity check PaymentAccountingEntry is not re-created
    pae = PaymentAccountingEntry.query.filter_by(appointment_id=appointment_id).first()
    assert pae is not None
    assert pae.member_id == member_id
    assert pae.created_at == pae_created_at


def test_authorize_payment_api_with_no_existing_payment(
    client, api_helpers, factories, scheduled_appointment, patch_authorize_payment
):
    appointment_id = scheduled_appointment.id
    product_id = scheduled_appointment.product.id
    member = scheduled_appointment.member
    member_id = member.id
    # There should be no payment
    pae = PaymentAccountingEntry.query.filter_by(appointment_id=appointment_id).first()

    assert pae is None

    data = {
        "appointment_id": appointment_id,
        "product_id": product_id,
        "member_id": member_id,
        "provider_id": scheduled_appointment.product.practitioner.id,
        "scheduled_start": scheduled_appointment.scheduled_start.isoformat(),
        "scheduled_end": scheduled_appointment.scheduled_end.isoformat(),
    }
    res = client.post(
        "/api/v2/appointments/reserve_payment_or_credits",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    assert res.json["success"]
    # Sanity check PaymentAccountingEntry is created
    pae = PaymentAccountingEntry.query.filter_by(appointment_id=appointment_id).first()
    assert pae is not None
