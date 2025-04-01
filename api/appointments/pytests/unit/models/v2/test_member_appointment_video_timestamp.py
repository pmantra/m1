import json

import pytest


class TestMemberAppointmentsListElement:
    def test_member_appointments_video_timestamp_struct(self, factories):
        date_str = "2024-03-28T00:00:00"
        json_str = f"""
            {{
                "member_disconnected_at": null,
                "member_disconnect_times": ["{date_str}"]
            }}
        """
        struct = factories.MemberAppointmentVideoTimestampStructFactory.create(
            json_str=json_str
        )
        assert struct.json_data.get("member_disconnect_times") == [date_str]

    def test_member_appointments_video_timestamp_struct__invalid_json(self, factories):
        date_str = "2024-03-28T00:00:00"
        # Json is invalid because it's missing quotes
        invalid_json_str = f"""
            {{
                "member_disconnected_at": null,
                "member_disconnect_times": [{date_str}]
            }}
        """
        with pytest.raises(json.JSONDecodeError):
            factories.MemberAppointmentVideoTimestampStructFactory.create(
                json_str=invalid_json_str
            )
