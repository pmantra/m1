from datetime import datetime

import pytest

from pytests import factories


def test_get_notes_as_ca(client, api_helpers, factories):
    # Arrange
    ca_vertical = factories.VerticalFactory.create(name="Care Advocate")
    ca = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[ca_vertical],
    )
    appointment = factories.AppointmentFactory.create_with_practitioner(
        purpose="follow_up",
        practitioner=ca,
        scheduled_start=datetime.utcnow(),
        scheduled_end=None,
    )
    factories.AppointmentMetaDataFactory.create(
        appointment=appointment,
        appointment_id=appointment.id,
        content="test note content",
        created_at=datetime.utcnow(),
    )

    # Act
    res = client.get(
        f"/api/v1/users/{appointment.member.id}/notes",
        headers=api_helpers.standard_headers(ca),
    )

    # Assert
    appointment_data = [
        "id",
        "post_session",
        "pre_session",
        "structured_internal_note",
        "provider_addenda",
        "scheduled_start",
        "product",
        "state",
        "cancelled_by",
        "need",
    ]
    res_data = api_helpers.load_json(res)
    assert res.status_code == 200

    for data in appointment_data:
        assert data in res_data["data"][0]


@pytest.fixture
def test_data(factories: factories):
    """Returns a dictionary of Appointment object references so that assertions can be made
    comparing the 4 expected possible cancelled_by options (None, "member, "provider" and
    "other") and the result of the calls in test_cancelled_by.

    The @pytest.mark.parametrize decorator references the expected values by their dictionary key.
    """
    ca_vertical = factories.VerticalFactory.create(name="Care Advocate")
    ca = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[ca_vertical],
    )
    other_ca = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[ca_vertical],
    )
    member = factories.EnterpriseUserNoTracksFactory.create()
    member_schedule = factories.ScheduleFactory.create(user=member)

    appointment_cancelled_by_none = (
        factories.AppointmentFactory.create_with_practitioner(
            purpose="follow_up",
            practitioner=ca,
            scheduled_start=datetime.utcnow(),
            scheduled_end=None,
        )
    )
    factories.AppointmentMetaDataFactory.create(
        appointment=appointment_cancelled_by_none,
        content="test note content",
        appointment_id=appointment_cancelled_by_none.id,
        created_at=datetime.utcnow(),
    )
    appointment_cancelled_by_member = (
        factories.AppointmentFactory.create_with_practitioner(
            member_schedule=member_schedule,
            purpose="follow_up",
            practitioner=ca,
            scheduled_start=datetime.utcnow(),
            scheduled_end=None,
            cancelled_by_user_id=member.id,
        )
    )
    factories.AppointmentMetaDataFactory.create(
        appointment=appointment_cancelled_by_member,
        content="test note content",
        appointment_id=appointment_cancelled_by_member.id,
        created_at=datetime.utcnow(),
    )
    appointment_cancelled_by_provider = (
        factories.AppointmentFactory.create_with_practitioner(
            purpose="follow_up",
            practitioner=ca,
            scheduled_start=datetime.utcnow(),
            scheduled_end=None,
            cancelled_by_user_id=ca.id,
        )
    )
    factories.AppointmentMetaDataFactory.create(
        appointment=appointment_cancelled_by_provider,
        content="test note content",
        appointment_id=appointment_cancelled_by_provider.id,
        created_at=datetime.utcnow(),
    )
    appointment_cancelled_by_other = (
        factories.AppointmentFactory.create_with_practitioner(
            purpose="follow_up",
            practitioner=ca,
            scheduled_start=datetime.utcnow(),
            scheduled_end=None,
            cancelled_by_user_id=other_ca.id,
        )
    )
    factories.AppointmentMetaDataFactory.create(
        appointment=appointment_cancelled_by_other,
        content="test note content",
        appointment_id=appointment_cancelled_by_other.id,
        created_at=datetime.utcnow(),
    )
    return {
        "appointment_cancelled_by_none": appointment_cancelled_by_none,
        "appointment_cancelled_by_member": appointment_cancelled_by_member,
        "appointment_cancelled_by_provider": appointment_cancelled_by_provider,
        "appointment_cancelled_by_other": appointment_cancelled_by_other,
    }


@pytest.mark.parametrize(
    # Used by test_cancelled_by to take expected appointments and match with expected cancelled_by string
    ["input_appointment", "expected_cancelled_by"],
    [
        ("appointment_cancelled_by_none", None),
        ("appointment_cancelled_by_member", "member"),
        ("appointment_cancelled_by_provider", "provider"),
        ("appointment_cancelled_by_other", "other"),
    ],
)
def test_cancelled_by(
    test_data,
    client,
    api_helpers,
    input_appointment,
    expected_cancelled_by,
):
    appointment = test_data[input_appointment]

    res = client.get(
        f"/api/v1/users/{appointment.member.id}/notes",
        headers=api_helpers.standard_headers(appointment.practitioner),
    )
    res_data = api_helpers.load_json(res)

    assert "cancelled_by" in res_data["data"][0]
    if expected_cancelled_by is None:
        assert res_data["data"][0]["cancelled_by"] is None
    else:
        assert expected_cancelled_by == res_data["data"][0]["cancelled_by"]
