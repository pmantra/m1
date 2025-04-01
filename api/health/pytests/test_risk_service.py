from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from common.health_profile.health_profile_service_client import (
    HealthProfileServiceClient,
)
from health.data_models.member_risk_flag import MemberRiskFlag
from health.models.risk_enums import ModifiedReason, RiskFlagName, RiskInputKey
from health.pytests.risk_test_utils import RiskTestUtils
from health.services.member_risk_service import MemberRiskService
from models.tracks import TrackName
from pytests.factories import MemberRiskFlagFactory, MemberTrackFactory


class TestMemberRiskService:
    def test_update_age_36(self, session, default_user, risk_flags):
        mrs = MemberRiskService(default_user)
        mrs.calculate_risks({RiskInputKey.AGE: 36})
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" not in risk_names
        assert "Advanced Maternal Age" in risk_names

    def test_set_risk(self, session, default_user, risk_flags):
        name = "High blood pressure - Current pregnancy"
        now = datetime.now(timezone.utc)
        today = date.today()
        mrs = MemberRiskService(default_user)
        result = mrs.set_risk(name)
        assert result.confirmed_risk is None
        assert result.ended_risk is None
        assert result.created_risk is not None
        flag: MemberRiskFlag = result.created_risk  # type: ignore
        id = flag.id
        member_risks = RiskTestUtils.get_risks(default_user)

        assert len(member_risks) == 1
        assert member_risks[0].id == id

        assert flag.risk_flag.name == name
        assert flag.start == today
        assert flag.end == None
        assert flag.value == None
        assert flag.confirmed_at >= now
        assert flag.confirmed_at.date() == today

    def test_confirm_risk_same_day(self, session, default_user, risk_flags):
        name = "High blood pressure - Current pregnancy"
        # create the risk
        mrs = MemberRiskService(default_user)
        result = mrs.set_risk(name)
        flag: MemberRiskFlag = result.created_risk  # type: ignore
        id = flag.id
        confirmed_at = flag.confirmed_at

        # confirm risk
        result2 = mrs.set_risk(name)
        assert result2.confirmed_risk is not None
        assert result2.ended_risk is None
        assert result2.created_risk is None
        assert result2.confirmed_risk.id == id
        assert result2.confirmed_risk.confirmed_at >= confirmed_at

        member_risks = RiskTestUtils.get_risks(default_user)
        assert len(member_risks) == 1
        assert member_risks[0].id == id

    def test_confirm_risk_different_day(self, session, default_user, risk_flags):
        name = "High blood pressure - Current pregnancy"
        # create the risk
        mrs = MemberRiskService(default_user)
        result = mrs.set_risk(name)
        flag: MemberRiskFlag = result.created_risk  # type: ignore
        id = flag.id
        confirmed_at = flag.confirmed_at

        # backdate it
        flag.start = date(2024, 1, 1)
        session.add(flag)
        session.commit()

        # confirm risk
        result2 = mrs.set_risk(name)
        assert result2.confirmed_risk is not None
        assert result2.ended_risk is None
        assert result2.created_risk is None
        assert result2.confirmed_risk.id == id
        assert result2.confirmed_risk.confirmed_at >= confirmed_at

        member_risks = RiskTestUtils.get_risks(default_user)
        assert len(member_risks) == 1
        assert member_risks[0].id == id

    def test_track_filter(self, session, default_user, risk_flags):
        mrs = MemberRiskService(default_user)
        mrs.set_risk("Advanced Maternal Age")

        # member has no track so risk should not appear
        relevant_risks = mrs.get_member_risks(False, True)
        assert len(relevant_risks) == 0

        # add pregnancy track
        track = MemberTrackFactory(
            user=default_user,
            created_at=datetime.utcnow() - timedelta(days=3),
            name=TrackName.PREGNANCY.value,
        )
        session.add(track)
        session.commit()
        session.refresh(default_user)

        relevant_risks = mrs.get_member_risks(True, True)
        assert len(relevant_risks) == 1
        assert relevant_risks[0].risk_flag.name == "Advanced Maternal Age"

    @pytest.mark.parametrize(
        "risk_flag_name,handle_method",
        [
            (RiskFlagName.DIABETES_EXISTING, "_handle_chronic_diabetes"),
            (
                RiskFlagName.GESTATIONAL_DIABETES_CURRENT_PREGNANCY,
                "_handle_gdm_current_pregnancy",
            ),
        ],
    )
    def test_set_risk_handles_diabetes_risks(
        self, session, default_user, risk_flags, risk_flag_name, handle_method
    ):
        # Mock feature flag to return True
        with patch(
            "utils.launchdarkly.feature_flags.bool_variation", return_value=True
        ):
            # Mock the handler methods
            with patch.object(MemberRiskService, handle_method) as mock_handle_method:
                # Mock external dependencies
                with patch.object(
                    HealthProfileServiceClient,
                    "put_member_conditions",
                    return_value=None,
                ), patch.object(
                    HealthProfileServiceClient,
                    "put_current_pregnancy_and_gdm_status",
                    return_value=None,
                ):
                    mrs = MemberRiskService(default_user)

                    # Call set_risk
                    result = mrs.set_risk(risk_flag_name.value)

                    # Ensure the correct method is called
                    mock_handle_method.assert_called_once()

                    # Verify the outcome
                    assert result.created_risk is not None
                    assert result.confirmed_risk is None
                    assert result.ended_risk is None

    @pytest.mark.parametrize(
        "pregnancy_week, expected_risk_flag",
        [
            (13, RiskFlagName.FIRST_TRIMESTER),
            (14, RiskFlagName.SECOND_TRIMESTER),
            (27, RiskFlagName.SECOND_TRIMESTER),
            (28, RiskFlagName.EARLY_THIRD_TRIMESTER),
            (33, RiskFlagName.EARLY_THIRD_TRIMESTER),
            (34, RiskFlagName.LATE_THIRD_TRIMESTER),
            (35, RiskFlagName.LATE_THIRD_TRIMESTER),
        ],
    )
    def test_set_risk_create_trimester_risk_flags(
        session, default_user, risk_flags, pregnancy_week, expected_risk_flag
    ):

        with patch(
            "utils.launchdarkly.feature_flags.bool_variation", return_value=True
        ):
            mrs = MemberRiskService(default_user)

            # Simulate the user's trimester based on pregnancy week
            expected_due_date = (
                datetime.now(timezone.utc) + timedelta(weeks=(40 - pregnancy_week))
            ).date()

            result = mrs.create_trimester_risk_flags(expected_due_date)

            assert result.created_risk.risk_flag.name == expected_risk_flag.value

    @pytest.mark.parametrize(
        "risk_flag_name,handle_method",
        [
            (RiskFlagName.DIABETES_EXISTING, "_handle_chronic_diabetes"),
            (
                RiskFlagName.GESTATIONAL_DIABETES_CURRENT_PREGNANCY,
                "_handle_gdm_current_pregnancy",
            ),
        ],
    )
    def test_set_risk_handles_diabetes_risks_does_not_hps_request_when_request_is_from_hps(
        self, session, default_user, risk_flags, risk_flag_name, handle_method
    ):
        # Mock feature flag to return True
        with patch(
            "utils.launchdarkly.feature_flags.bool_variation", return_value=True
        ):
            # Mock the handler methods
            with patch.object(MemberRiskService, handle_method) as mock_handle_method:
                # Mock external dependencies
                with patch.object(
                    HealthProfileServiceClient,
                    "put_member_conditions",
                    return_value=None,
                ), patch.object(
                    HealthProfileServiceClient,
                    "put_current_pregnancy_and_gdm_status",
                    return_value=None,
                ):
                    mrs = MemberRiskService(
                        user=default_user,
                        modified_reason=ModifiedReason.GDM_STATUS_UPDATE,
                    )

                    # Call set_risk
                    result = mrs.set_risk(risk_flag_name.value)

                    # Ensure the handle method is not called
                    mock_handle_method.assert_not_called()

                    # Verify the outcome
                    assert result.created_risk is not None
                    assert result.confirmed_risk is None
                    assert result.ended_risk is None

    @pytest.mark.parametrize(
        "risk_flag_name",
        [
            RiskFlagName.DIABETES_EXISTING,
            RiskFlagName.GESTATIONAL_DIABETES_CURRENT_PREGNANCY,
        ],
    )
    def test_update_hps_gdm_status_uses_none_onset_date(
        self, default_user, risk_flags, risk_flag_name
    ):
        with patch(
            "common.health_profile.health_profile_service_client.HealthProfileServiceClient",
            autospec=True,
            spec_set=True,
        ) as mock_health_profile_service_client:
            with patch(
                "health.services.member_risk_service.HealthProfileServiceClient",
                autospec=True,
                return_value=mock_health_profile_service_client,
            ):
                member_risk_service = MemberRiskService(default_user)
                member_risk_flag = MemberRiskFlagFactory.create(
                    user_id=default_user.id, risk_flag=risk_flags.get(risk_flag_name)
                )
                member_risk_service.update_hps_gdm_status(
                    member_risk_flag, default_user
                )

                if risk_flag_name == RiskFlagName.DIABETES_EXISTING:
                    mock_health_profile_service_client.put_member_conditions.assert_called_once()
                    kwargs = (
                        mock_health_profile_service_client.put_member_conditions.call_args.kwargs
                    )
                    assert kwargs["member_conditions"][0]["onset_date"] is None

                if (
                    risk_flag_name
                    == RiskFlagName.GESTATIONAL_DIABETES_CURRENT_PREGNANCY
                ):
                    mock_health_profile_service_client.put_current_pregnancy_and_gdm_status.assert_called_once()
                    kwargs = (
                        mock_health_profile_service_client.put_current_pregnancy_and_gdm_status.call_args.kwargs
                    )
                    assert kwargs["gdm_onset_date"] is None

    def test_update_hps_gdm_status_does_not_call_hps_client_when_due_date_is_missing(
        self, default_user, risk_flags
    ):
        with patch(
            "common.health_profile.health_profile_service_client.HealthProfileServiceClient",
            autospec=True,
            spec_set=True,
        ) as mock_health_profile_service_client:
            with patch(
                "health.services.member_risk_service.HealthProfileServiceClient",
                autospec=True,
                return_value=mock_health_profile_service_client,
            ):
                # Given
                default_user.health_profile.due_date = None
                member_risk_service = MemberRiskService(default_user)
                risk_flag = risk_flags.get(
                    RiskFlagName.GESTATIONAL_DIABETES_CURRENT_PREGNANCY
                )
                member_risk_flag = MemberRiskFlagFactory.create(
                    user_id=default_user.id, risk_flag=risk_flag
                )
                # When
                member_risk_service.update_hps_gdm_status(
                    member_risk_flag, default_user
                )
                # Then
                mock_health_profile_service_client.put_current_pregnancy_and_gdm_status.assert_not_called()
