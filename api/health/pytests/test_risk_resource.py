import datetime
from typing import List, Optional
from unittest import mock

from authn.models.user import User
from health.data_models.member_risk_flag import MemberRiskFlag
from health.models.risk_enums import ModifiedReason, RiskFlagName
from health.services.member_risk_service import MemberRiskService, SetRiskResult
from pytests.factories import MemberRiskFlagFactory


class TestGetHealthProfile:
    def url(
        self,
        user: User,
        active_only: Optional[bool] = None,
        track_relevant_only: Optional[bool] = None,
    ):
        url = f"/api/v1/risk-flags/member/{user.id}?"
        if active_only is not None:
            url += f"active_only={active_only}&"
        if track_relevant_only is not None:
            url += f"track_relevant_only={track_relevant_only}&"
        return url

    def validate_response(self, response, expected: List[MemberRiskFlag]):
        assert response.status_code == 200
        json = response.json
        assert len(json) == len(expected)
        json = sorted(json, key=lambda i: (i["name"], i["start"], i["end"]))
        expected = sorted(expected, key=lambda i: (i.risk_flag.name, i.start, i.end))
        for i in range(0, len(json)):
            self.validate_item(json[i], expected[i])

    def validate_item(self, item, member_risk: MemberRiskFlag):  # response item
        # MemberRiskFlag fields
        assert item["value"] == member_risk.value
        if member_risk.start:
            assert item["start"] == member_risk.start.isoformat()
        else:
            assert item["start"] is None
        if member_risk.end:
            assert item["end"] == member_risk.end.isoformat()
        else:
            assert item["end"] is None

        # RiskFlag fields
        risk = member_risk.risk_flag
        assert item["name"] == risk.name
        assert item["severity"] == risk.severity.value
        assert item["is_mental_health"] == risk.is_mental_health
        assert item["is_physical_health"] == risk.is_physical_health
        assert item["is_utilization"] == risk.is_utilization
        assert item["is_situational"] == risk.is_situational
        assert item["relevant_to_maternity"] == risk.relevant_to_maternity
        assert item["relevant_to_fertility"] == risk.relevant_to_fertility

        assert item["uses_value"] == risk.uses_value
        if risk.value_unit is None:
            assert item["value_unit"] == ""
        else:
            assert item["value_unit"] == risk.value_unit

        # Display Specific Fields
        assert item["display_name"] is not None
        # assert item["display_context"]

    def test_no_risks(self, default_user, api_helpers, client, risk_flags):
        res = client.get(
            self.url(default_user),
            headers=api_helpers.json_headers(default_user),
        )
        self.validate_response(res, [])

    def test_single_active_not_relevant(
        self, default_user, client, api_helpers, risk_flags, session
    ):
        # active but not relevant
        service = MemberRiskService(default_user)
        result = service.set_risk("High")
        mr = result.created_risk
        res = client.get(
            self.url(default_user),
            headers=api_helpers.json_headers(default_user),
        )
        self.validate_response(res, [])

        res = client.get(
            self.url(default_user, track_relevant_only=False),
            headers=api_helpers.json_headers(default_user),
        )
        self.validate_response(res, [mr])

    def test_single_never_active(
        self, default_user, client, api_helpers, risk_flags, session
    ):
        # Since  start==end it gets filtered out as never having been active
        service = MemberRiskService(default_user)
        service.set_risk("High")
        service.clear_risk("High")
        res = client.get(
            self.url(default_user, active_only=False, track_relevant_only=False),
            headers=api_helpers.json_headers(default_user),
        )
        self.validate_response(res, [])

    def test_single_inactive_irrelevant(
        self, default_user, client, api_helpers, risk_flags, session
    ):
        service = MemberRiskService(default_user)
        result = service.set_risk("High")
        mr = result.created_risk
        mr.start = mr.start - datetime.timedelta(days=1)  # type: ignore
        service.clear_risk("High")

        mr.start = mr.start - datetime.timedelta(days=1)  # type: ignore
        session.add(mr)
        session.commit()
        # Ended  but only Relevant
        res = client.get(
            self.url(default_user, active_only=False),
            headers=api_helpers.json_headers(default_user),
        )
        self.validate_response(res, [])

        res = client.get(
            self.url(default_user, active_only=False, track_relevant_only=False),
            headers=api_helpers.json_headers(default_user),
        )
        self.validate_response(res, [mr])

        # def test_single_active_relevant(self, default_user:User, client, api_helpers, risk_flags, session):


class TestPostMemberRiskFlags:
    def url(self, user_id: int):
        return f"/api/v1/risk-flags/member/{user_id}"

    def validate_response(self, response, expected_status_code, expected_data=None):
        assert response.status_code == expected_status_code
        if expected_data:
            assert response.json == expected_data

    def test_create_risk_flag(self, default_user, client, api_helpers, risk_flags):
        with mock.patch(
            "health.resources.member_risk_resource.MemberRiskService", autospec=True
        ) as mock_member_risk_service:
            created_risk = MemberRiskFlagFactory.create(
                user_id=default_user.id,
                risk_flag=risk_flags.get(RiskFlagName.DIABETES_EXISTING),
            )
            mock_member_risk_service.return_value.set_risk.return_value = SetRiskResult(
                created_risk=created_risk
            )

            payload = {
                "risk_flag_name": "Diabetes - Existing condition",
                "modified_reason": "GDM Status Update",
            }
            res = client.post(
                self.url(default_user.id),
                json=payload,
                headers=api_helpers.json_headers(default_user),
            )

            assert res.status_code == 201
            self.validate_response(
                res,
                201,
                {
                    "risk_flag_name": "Diabetes - Existing condition",
                    "created_risk": True,
                    "ended_risk": False,
                    "confirmed_risk": False,
                },
            )
            mock_member_risk_service.assert_called_once_with(
                user=default_user.id, modified_reason=ModifiedReason.GDM_STATUS_UPDATE
            )

    def test_invalid_risk_flag_400(self, default_user, client, api_helpers, risk_flags):
        payload = {"risk_flag_name": "Invalid Risk Flag"}
        res = client.post(
            self.url(default_user.id),
            json=payload,
            headers=api_helpers.json_headers(default_user),
        )

        assert res.status_code == 400
