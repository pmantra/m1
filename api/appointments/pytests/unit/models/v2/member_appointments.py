import json
from datetime import datetime

import pytest

from appointments.models.v2.member_appointments import MemberAppointmentsListElement


class TestMemberAppointmentsListElement:
    def test_member_appointments_list(self, factories):
        date_str = "2024-03-28T00:00:00"
        json_str = f"""
            {{
                "member_disconnected_at": null,
                "practitioner_disconnected_at": "{date_str}"
            }}
        """
        member_appt_list_ele: MemberAppointmentsListElement = (
            factories.MemberAppointmentsListElementFactory.create(
                json=json_str,
            )
        )
        assert member_appt_list_ele.member_disconnected_at is None
        assert (
            member_appt_list_ele.practitioner_disconnected_at
            == datetime.fromisoformat(date_str)
        )

    def test_member_appointments_list__invalid_json(self, factories):
        invalid_json_str = (
            '{"member_disconnected_at": Null, practitioner_disconnected_at = "ab"}'
        )
        with pytest.raises(json.JSONDecodeError):
            factories.MemberAppointmentsListElementFactory.create(
                json=invalid_json_str,
            )

    def test_member_appointments_list__invalid_json__member_disconnected_at(
        self, factories
    ):
        # member_disconnected_at is invalid
        invalid_json_str = """
            {
                "member_disconnected_at": "2024-03-28T00:00:00",
                "practitioner_disconnected_at": "204-03-28T00:00:00"
            }
        """
        with pytest.raises(ValueError):
            factories.MemberAppointmentsListElementFactory.create(
                json=invalid_json_str,
            )

    def test_member_appointments_list__invalid_json__practitioner_disconnected_at(
        self, factories
    ):
        # practitioner_disconnected_at is invalid
        invalid_json_str = """
            {
                "member_disconnected_at": "202-03-28T00:00:00",
                "practitioner_disconnected_at": "2024-03-28T00:00:00"
            }
        """
        with pytest.raises(ValueError):
            factories.MemberAppointmentsListElementFactory.create(
                json=invalid_json_str,
            )
