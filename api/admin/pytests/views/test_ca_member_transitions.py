import csv
import datetime
import json
import os
from unittest import mock
from unittest.mock import ANY

import factory
import pytest

from care_advocates.models.transitions import CareAdvocateMemberTransitionLog
from care_advocates.services.transition_template import (
    CareAdvocateMemberTransitionTemplateService,
)
from pytests.factories import (
    CareAdvocateMemberTransitionLogFactory,
    CareAdvocateMemberTransitionTemplateFactory,
    DefaultUserFactory,
    PractitionerUserFactory,
)


@pytest.fixture
def log_user():
    return DefaultUserFactory.create()


@pytest.fixture
def complete_log(log_user):
    now = datetime.datetime.utcnow()
    return CareAdvocateMemberTransitionLogFactory.create(
        user_id=log_user.id,
        date_scheduled=now - datetime.timedelta(days=1),
        date_completed=now,
    )


@pytest.fixture
def incomplete_log(log_user):
    now = datetime.datetime.utcnow()
    return CareAdvocateMemberTransitionLogFactory.create(
        user_id=log_user.id,
        date_scheduled=now - datetime.timedelta(days=2),
    )


@pytest.fixture
def transition_logs(complete_log, incomplete_log):
    return [complete_log, incomplete_log]


def _to_expected_date_format(date):
    date_format = "%a, %d %b %Y %H:%M:%S %Z"
    return (
        date.astimezone(datetime.timezone.utc)
        .strftime(date_format)
        .replace("UTC", "GMT")
    )


class TestCAMemberTransitionsLogs:
    def test_get_list_transition_logs(self, admin_client, transition_logs, log_user):
        res = admin_client.get("/admin/ca_member_transitions/transition_logs")
        assert res.status_code == 200
        assert res.json == {
            "data": {
                "items": [
                    {
                        "id": log.id,
                        "user_id": log.user_id,
                        "user_name": log_user.full_name,
                        "date_uploaded": _to_expected_date_format(log.created_at),
                        "date_of_transition": _to_expected_date_format(
                            log.date_transition
                        ),
                        "uploaded_file": log.uploaded_filename,
                        "canDelete": False if log.date_completed else True,
                        "rowProps": {"style": {"fontWeight": "bold"}}
                        if not log.date_completed
                        else {},
                    }
                    for log in transition_logs
                ],
                "pagination": {
                    "limit": 10,
                    "total": 2,
                },
            }
        }

    def test_delete_transition_log__successfully_deleted(
        self, admin_client, incomplete_log, db, commit_expire_behavior
    ):
        expected_id = incomplete_log.id
        res = admin_client.post(
            "/admin/ca_member_transitions/transition_logs/delete",
            data={"id": expected_id},
        )
        assert res.status_code == 302
        log = db.session.query(CareAdvocateMemberTransitionLog).get(expected_id)
        assert log is None

    def test_delete_transition_log__unsuccessfully_deleted(
        self, admin_client, complete_log, db
    ):
        # Due to interactions between the uow rollback and the test session,
        # We cannot replicate the original query-based test assertions.
        expected_id = complete_log.id
        with mock.patch("storage.repository.base.BaseRepository.delete") as mock_delete:
            res = admin_client.post(
                "/admin/ca_member_transitions/transition_logs/delete",
                data={"id": expected_id},
            )
        assert res.status_code == 302
        assert mock_delete.call_count == 0

    def test_download_csv(self, admin_client, complete_log):
        expected_content_type = "text/csv; charset=utf-8"
        res = admin_client.get(
            f"/admin/ca_member_transitions/transition_logs/download_csv/{complete_log.id}"
        )
        assert res.status_code == 200
        assert res.headers["Content-Type"] == expected_content_type


@pytest.fixture
def raw_csv_data(log_user):
    # TODO: make them CAs with the right associations
    prac1, prac2 = PractitionerUserFactory.create_batch(size=2)
    return [
        {
            "member_id": log_user.id,
            "old_cx_id": prac1.id,
            "new_cx_id": prac2.id,
            "messaging": "FAREWELL;FOLLOWUP_INTRO",
        }
    ]


@pytest.fixture
def csv_data(raw_csv_data):
    with open("transitions_file.csv", "w") as output:
        writer = csv.DictWriter(output, fieldnames=list(raw_csv_data[0].keys()))
        writer.writeheader()
        writer.writerows(raw_csv_data)
    yield open("transitions_file.csv", "rb")
    os.remove("transitions_file.csv")


class TestCAMemberTransitions:
    def test_get_list_transition_templates(self, admin_client):
        all_transition_templates = (
            CareAdvocateMemberTransitionTemplateFactory.create_batch(
                size=2, message_type=factory.Iterator(["FAREWELL", "FOLLOWUP_INTRO"])
            )
        )
        expected_transition_templates_data = [
            {
                "id": tt.id,
                "message_type": tt.message_type,
                "message_description": tt.message_description,
                "message_body": CareAdvocateMemberTransitionTemplateService()._get_paragraph_preview(
                    tt.message_body
                ),
                "EditURL": f"/admin/ca_member_transition_templates/edit/?id={tt.id}",
            }
            for tt in all_transition_templates
        ]

        res = admin_client.get("/admin/ca_member_transitions/transition_templates")
        assert res.json == {
            "data": {
                "items": expected_transition_templates_data,
                "pagination": {
                    "limit": 10,
                    "total": len(expected_transition_templates_data),
                },
            }
        }

    def test_submit_transition(
        self, admin_client, db, log_user, raw_csv_data, csv_data
    ):
        transition_logs = db.session.query(CareAdvocateMemberTransitionLog).count()
        assert transition_logs == 0
        transition_date = datetime.datetime.utcnow()
        post_data = {
            "transitions_csv": (csv_data, "transitions_file.csv"),
            "transition_date": transition_date.strftime("%m/%d/%Y %I:%M %p"),
        }
        expected_response = {
            "id": ANY,
            "user_id": log_user.id,
            "date_scheduled": transition_date.strftime("%Y-%m-%dT%H:%M") + ":00",
            "uploaded_filename": "transitions_file.csv",
            "uploaded_content": json.dumps(raw_csv_data),
        }

        with mock.patch(
            "admin.views.models.practitioner.login.current_user", id=log_user.id
        ):
            res = admin_client.post(
                "/admin/ca_member_transitions/submit",
                content_type="multipart/form-data",
                data=post_data,
                buffered=True,
            )
        assert res.status_code == 200
        assert res.json == expected_response
        transition_logs = db.session.query(CareAdvocateMemberTransitionLog).count()
        assert transition_logs == 1
