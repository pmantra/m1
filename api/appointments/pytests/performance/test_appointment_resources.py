from __future__ import annotations

import datetime
import json

from appointments.services.common import obfuscate_appointment_id
from pytests.db_util import enable_db_performance_warnings
from pytests.factories import (
    CountryMetadataFactory,
    EnterpriseUserFactory,
    ScheduleFactory,
)
from pytests.util import enable_serialization_attribute_errors


# ensures exceptions during serialization are raised in test
@enable_serialization_attribute_errors()
def test_simple_get(
    client, api_helpers, db, practitioner_user, valid_appointment_with_user
):
    # -----------------------------------------------------------
    # simple, happy path test case set up

    uk_metadata = CountryMetadataFactory.create(country_code="GB")
    provider = practitioner_user()
    member = EnterpriseUserFactory.create(
        member_profile__phone_number="2125555555",
        member_profile__country_code=uk_metadata.country_code,
    )

    ms = ScheduleFactory.create(user=member)
    valid_appointment_with_user(
        practitioner=provider,
        member_schedule=ms,
        purpose="birth_needs_assessment",
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
    )

    # -----------------------------------------------------------
    # begin capturing DB activity when we make the API request

    with enable_db_performance_warnings(
        database=db,
        # warning_threshold=1,  # uncomment to to view all queries being made
        failure_threshold=51,
    ):
        res = client.get(
            f"/api/v1/appointments?practitioner_id={provider.id}",
            headers=api_helpers.json_headers(provider),
        )
        data = api_helpers.load_json(res)
        # minimal assertion to ensure we're getting the data we expect
        # actual validation should occur in respective tests
        assert len(data["data"]) == 1


@enable_serialization_attribute_errors()
def test_get_by_appointment_id(
    client, api_helpers, db, practitioner_user, valid_appointment_with_user
):
    # -----------------------------------------------------------
    # simple, happy path test case set up

    uk_metadata = CountryMetadataFactory.create(country_code="GB")
    provider = practitioner_user()
    member = EnterpriseUserFactory.create(
        member_profile__phone_number="2125555555",
        member_profile__country_code=uk_metadata.country_code,
    )

    ms = ScheduleFactory.create(user=member)
    appointment = valid_appointment_with_user(
        practitioner=provider,
        member_schedule=ms,
        purpose="birth_needs_assessment",
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
    )
    appointment_id = obfuscate_appointment_id(appointment.id)

    # -----------------------------------------------------------
    # begin capturing DB activity when we make the API request

    with enable_db_performance_warnings(
        database=db,
        # warning_threshold=1,  # uncomment to view all queries being made
        failure_threshold=50,
    ):
        res = client.get(
            f"/api/v1/appointments/{appointment_id}",
            headers=api_helpers.json_headers(provider),
        )
        data = api_helpers.load_json(res)
        # minimal assertion to ensure we're getting the data we expect
        # actual validation should occur in respective tests
        assert data["id"] == appointment_id


@enable_serialization_attribute_errors()
def test_get_appointments(
    client,
    api_helpers,
    db,
    setup_post_appointment_test,
):
    # -----------------------------------------------------------
    # simple, happy path test case set up

    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    data = appointment_setup_values.data

    # -----------------------------------------------------------
    # begin capturing DB activity when we make the API request

    with enable_db_performance_warnings(
        database=db,
        # warning_threshold=1,  # uncomment to view all queries being made
        failure_threshold=6,
    ):
        res = client.get(
            "/api/v1/appointments",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        response_data = json.loads(res.data)
        # minimal assertion to ensure we're getting the data we expect
        # actual validation should occur in respective tests
        assert res.status_code == 200
        assert response_data["pagination"]["limit"] == 10
