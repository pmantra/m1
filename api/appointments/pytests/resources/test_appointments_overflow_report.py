import datetime
import json

import pytest

from appointments.models.appointment import Appointment
from utils import security


@pytest.fixture
def overflow_report_params(valid_appointment_with_user):
    def create_overflow_report_params(practitioner):
        now = datetime.datetime.utcnow()
        start = now - datetime.timedelta(minutes=20)
        end = now - datetime.timedelta(minutes=10)

        appointment = valid_appointment_with_user(practitioner)
        appointment.scheduled_start = start
        appointment.scheduled_end = end
        appointment.member_started_at = start
        appointment.practitioner_started_at = start

        token = security.new_overflowing_appointment_token(appointment.id)
        return appointment, token

    return create_overflow_report_params


def test_bad_request(client):
    res = client.post(
        "/api/v1/overflow_report", headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 400


def test_bad_request_unsupported_media_type(client):
    res = client.post(
        "/api/v1/overflow_report",
    )
    # flask version >2.1.3 behavior
    # 415 Unsupported Media Type if there is no request.is_json check
    # refactored logic to keep the existing behavior
    assert res.status_code == 400


def test_bad_report(
    client,
    api_helpers,
    create_practitioner,
    overflow_report_params,
):
    practitioner = create_practitioner()
    _, token = overflow_report_params(practitioner)

    res = client.post(
        "/api/v1/overflow_report",
        headers=api_helpers.json_headers(practitioner),
        data=json.dumps({"token": token, "report": "FOO"}),
    )

    assert res.status_code == 400


def test_good_yes_report(
    client,
    api_helpers,
    create_practitioner,
    overflow_report_params,
):
    practitioner = create_practitioner()
    appointment, token = overflow_report_params(practitioner)

    res = client.post(
        "/api/v1/overflow_report",
        headers=api_helpers.json_headers(practitioner),
        data=json.dumps({"token": token, "report": "YES"}),
    )

    assert res.status_code == 204

    appointment = Appointment.query.get(appointment.id)
    assert appointment.ended_at
    assert appointment.json["completed_via_report"]


def test_bad_yes_report(
    client,
    api_helpers,
    create_practitioner,
    overflow_report_params,
):
    practitioner = create_practitioner()
    appointment, token = overflow_report_params(practitioner)
    appointment.practitioner_started_at = None

    res = client.post(
        "/api/v1/overflow_report",
        headers=api_helpers.json_headers(practitioner),
        data=json.dumps({"token": token, "report": "YES"}),
    )

    assert res.status_code == 400
