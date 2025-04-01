from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from authn.models.user import User
from geography import Country
from mpractice.models.common import Pagination
from mpractice.models.translated_appointment import (
    SessionMetaInfo,
    TranslatedMPracticeMember,
    TranslatedProviderAppointmentForList,
)
from utils.api_interaction_mixin import APIInteractionMixin


class TestProviderAppointmentsResource:
    def test_get_provider_appointments_success(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        mock_provider_appointment_service_for_appointments_resource: MagicMock,
        country: Country,
        practitioner_user: User,
    ):
        appointments = [
            TranslatedProviderAppointmentForList(
                id=1,
                appointment_id=2,
                privacy="full_access",
                scheduled_start=datetime(2024, 3, 7, 10, 0, 0),
                scheduled_end=datetime(2024, 3, 7, 11, 0, 0),
                cancelled_at=None,
                member=TranslatedMPracticeMember(
                    id=2, name="test name", first_name="test", country=country
                ),
                post_session=SessionMetaInfo(draft=False),
                repeat_patient=False,
                state="PAYMENT_PENDING",
                privilege_type="",
                rescheduled_from_previous_appointment_time=None,
            )
        ]
        pagination = Pagination(limit=1, offset=0, order_direction="asc", total=2)
        expected_pagination = {
            "limit": 1,
            "offset": 0,
            "order_direction": "asc",
            "total": 2,
        }
        expected_appts = [
            {
                "id": 1,
                "appointment_id": 2,
                "privacy": "full_access",
                "scheduled_start": "2024-03-07T10:00:00",
                "scheduled_end": "2024-03-07T11:00:00",
                "cancelled_at": None,
                "member": {
                    "id": 2,
                    "name": "test name",
                    "first_name": "test",
                    "email": "",
                    "country": {
                        "name": "United Kingdom",
                        "abbr": "UK",
                        "ext_info_link": None,
                        "summary": None,
                    },
                    "organization": None,
                    "profiles": None,
                    "created_at": None,
                },
                "post_session": {
                    "created_at": None,
                    "draft": False,
                    "notes": "",
                },
                "repeat_patient": False,
                "state": "PAYMENT_PENDING",
                "privilege_type": "",
                "rescheduled_from_previous_appointment_time": None,
            }
        ]
        expected_response = {
            "data": expected_appts,
            "pagination": expected_pagination,
        }
        mock_provider_appointment_service_for_appointments_resource.get_provider_appointments.return_value = (
            appointments,
            pagination,
        )
        response = client.get(
            "/api/v1/mpractice/appointments",
            query_string={
                "order_direction": "asc",
                "limit": 1,
                "offset": 0,
            },
            headers=api_helpers.json_headers(practitioner_user),
        )

        assert response.status_code == 200
        response_json = json.loads(response.data)
        assert response_json == expected_response
        mock_provider_appointment_service_for_appointments_resource.get_provider_appointments.assert_called_once_with(
            {
                "practitioner_id": practitioner_user.id,
                "limit": 1,
                "offset": 0,
                "order_direction": "asc",
            }
        )

    @pytest.mark.parametrize(
        argnames="practitioner_id,scheduled_start,scheduled_end,error_code",
        argvalues=[
            (404, None, None, 403),
            (None, "2024-02-26T15:05:49", None, 400),
            (None, None, "2024-03-27T15:05:49", 400),
        ],
        ids=[
            "practitioner_id_user_id_mismatch",
            "has_scheduled_start_no_scheduled_end",
            "has_scheduled_end_no_scheduled_start",
        ],
    )
    def test_get_provider_appointments_error_response_from_valid_params(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        practitioner_user: User,
        practitioner_id: int | None,
        scheduled_start: datetime | None,
        scheduled_end: datetime | None,
        error_code: int,
    ):
        response = client.get(
            "/api/v1/mpractice/appointments",
            query_string={
                "practitioner_id": practitioner_id,
                "scheduled_start": scheduled_start,
                "scheduled_end": scheduled_end,
            },
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == error_code

    @pytest.mark.skip(reason="Not backwards compatible")
    def test_get_provider_appointments_error_response_from_invalid_param(
        self,
        client: FlaskClient,
        api_helpers: APIInteractionMixin,
        practitioner_user: User,
    ):
        response = client.get(
            "/api/v1/mpractice/appointments",
            query_string={"minimal": True},
            headers=api_helpers.json_headers(practitioner_user),
        )
        assert response.status_code == 400
