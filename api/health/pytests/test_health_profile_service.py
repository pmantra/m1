from datetime import datetime, timedelta, timezone
from unittest import mock
from unittest.mock import MagicMock, Mock, patch

import pytest
from ldclient import Stage

from common.health_profile.health_profile_service_models import (
    ClinicalStatus,
    ConditionType,
    MemberCondition,
    Modifier,
)
from health.data_models.fertility_treatment_status import FertilityTreatmentStatus
from health.data_models.member_risk_flag import MemberRiskFlag
from health.services.health_profile_service import (
    FERTILITY_STATUS_TO_RISK_FLAG_NAME,
    HealthProfileService,
)
from pytests import freezegun
from pytests.factories import PractitionerUserFactory


@pytest.fixture
def mock_db():
    """Mock db.session for database operations."""
    with patch("storage.connection.db.session") as mock:
        yield mock


@pytest.fixture
def mock_risk_service():
    """Mock RiskService instance."""
    with patch("health.services.health_profile_service.RiskService") as MockRiskService:
        mock_service = Mock()
        MockRiskService.return_value = mock_service
        yield mock_service


@pytest.fixture(scope="function")
def mock_hps_client() -> MagicMock:
    with mock.patch(
        "common.health_profile.health_profile_service_client.HealthProfileServiceClient",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "health.services.health_profile_service.HealthProfileServiceClient",
            autospec=True,
            return_value=m,
        ):
            yield m


@pytest.fixture(scope="function")
def mock_migration_flag() -> MagicMock:
    with mock.patch(
        "health.services.health_profile_service.migration_variation",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def practitioner_user():
    return PractitionerUserFactory.create()


class TestHealthProfileService:
    def test_set_fertility_treatment_status_with_feature_flag_off(
        self,
        default_user,
        mock_db: Mock,
        mock_risk_service: Mock,
    ):
        """Test setting fertility status when feature flag is off."""
        fertility_status = "undergoing_ivf"
        health_profile_service = HealthProfileService(default_user)

        # Modify the patch to correctly handle arguments
        with patch(
            "maven.feature_flags.bool_variation",
            side_effect=lambda flag_name, *args, **kwargs: {
                "create-risk-flag-based-on-fertility-status": False,
                "hps-migration-fertility-write": True,
            }.get(flag_name, kwargs.get("default", False)),
        ):
            with patch(
                "health.services.health_profile_service.HealthProfileServiceClient"
            ) as mock_client:
                instance = mock_client.return_value
                health_profile_service.set_fertility_treatment_status(fertility_status)

                # Verify FertilityTreatmentStatus was added
                assert mock_db.add.call_count == 1
                args_list = mock_db.add.call_args_list
                first_call_arg = args_list[0][0][0]
                assert isinstance(first_call_arg, FertilityTreatmentStatus)
                assert first_call_arg.fertility_treatment_status == fertility_status
                assert first_call_arg.user_id == default_user.id

                # Verify commit was called
                mock_db.commit.assert_called_once()

                # Verify risk service wasn't called
                mock_risk_service.get_by_name.assert_not_called()

                # Verify HPS client was called
                instance.set_fertility_status.assert_called_once_with(fertility_status)

    def test_set_fertility_treatment_status_with_feature_flag_on_valid_status(
        self,
        default_user,
        mock_db: Mock,
        mock_risk_service: Mock,
    ):
        """Test setting fertility status with flag on and valid status."""
        fertility_status = "undergoing_ivf"
        risk_flag = Mock(name="risk_flag")
        mock_risk_service.get_by_name.return_value = risk_flag
        health_profile_service = HealthProfileService(default_user)

        feature_flag_patches = [
            patch(
                "maven.feature_flags.bool_variation",
                side_effect=lambda flag_name, *args, **kwargs: {
                    "create-risk-flag-based-on-fertility-status": True,
                    "hps-migration-fertility-write": True,
                }.get(flag_name, kwargs.get("default", False)),
            ),
        ]

        with patch(
            "health.services.health_profile_service.HealthProfileServiceClient"
        ) as mock_client:
            instance = mock_client.return_value
            for patcher in feature_flag_patches:
                with patcher:
                    health_profile_service.set_fertility_treatment_status(
                        fertility_status
                    )

                    # Verify both objects were added to db
                    assert mock_db.add.call_count == 2
                    args_list = mock_db.add.call_args_list

                    # Verify FertilityTreatmentStatus was added
                    first_call_arg = args_list[0][0][0]
                    assert isinstance(first_call_arg, FertilityTreatmentStatus)
                    assert first_call_arg.fertility_treatment_status == fertility_status
                    assert first_call_arg.user_id == default_user.id

                    # Verify MemberRiskFlag was added
                    second_call_arg = args_list[1][0][0]
                    assert isinstance(second_call_arg, MemberRiskFlag)
                    assert second_call_arg.user_id == default_user.id
                    assert second_call_arg.risk_flag == risk_flag
                    assert second_call_arg.start == datetime.now(timezone.utc).date()

                    # Verify commit and risk service calls
                    mock_db.commit.assert_called_once()
                    mock_risk_service.get_by_name.assert_called_once_with(
                        FERTILITY_STATUS_TO_RISK_FLAG_NAME[fertility_status]
                    )

                    # Verify HPS client was called
                    instance.set_fertility_status.assert_called_once_with(
                        fertility_status
                    )

    def test_set_fertility_treatment_status_with_feature_flag_on_invalid_status(
        self,
        default_user,
        mock_db: Mock,
        mock_risk_service: Mock,
    ):
        """Test setting fertility status with flag on but invalid status."""
        fertility_status = "invalid_status"  # Status not in mapping
        health_profile_service = HealthProfileService(default_user)

        feature_flag_patches = [
            patch(
                "maven.feature_flags.bool_variation",
                side_effect=lambda flag_name, *args, **kwargs: {
                    "create-risk-flag-based-on-fertility-status": True,
                    "hps-migration-fertility-write": True,
                }.get(flag_name, kwargs.get("default", False)),
            ),
        ]

        with patch(
            "health.services.health_profile_service.HealthProfileServiceClient"
        ) as mock_client:
            instance = mock_client.return_value
            for patcher in feature_flag_patches:
                with patcher:
                    health_profile_service.set_fertility_treatment_status(
                        fertility_status
                    )

                    # Verify only FertilityTreatmentStatus was added
                    assert mock_db.add.call_count == 1
                    args_list = mock_db.add.call_args_list
                    first_call_arg = args_list[0][0][0]
                    assert isinstance(first_call_arg, FertilityTreatmentStatus)
                    assert first_call_arg.fertility_treatment_status == fertility_status
                    assert first_call_arg.user_id == default_user.id

                    # Verify commit was called and risk service wasn't
                    mock_db.commit.assert_called_once()
                    mock_risk_service.get_by_name.assert_not_called()

                    # Verify HPS client was called
                    instance.set_fertility_status.assert_called_once_with(
                        fertility_status
                    )

    @pytest.mark.parametrize(
        "fertility_status,expected_risk_name",
        [
            ("undergoing_ivf", "Undergoing IVF - Onboarding status"),
            ("undergoing_iui", "Undergoing IUI - Onboarding status"),
            ("ttc_no_treatment", "TTC no treatment - Onboarding status"),
            (
                "considering_fertility_treatment",
                "Considering fertility treatment - Onboarding status",
            ),
            ("not_ttc_learning", "Not TTC learning - Onboarding status"),
            ("ttc_in_six_months", "TTC in 6 months - Onboarding status"),
            ("ttc_no_iui_ivf", "TTC no IUI no IVF - Onboarding status"),
            ("successful_pregnancy", "Successful Pregnancy - Onboarding status"),
            ("invalid_status", None),
        ],
    )
    def test_get_new_member_risk_flag_based_on_fertility_status(
        self,
        default_user,
        mock_risk_service,
        fertility_status,
        expected_risk_name,
    ):
        """Test risk flag creation for different fertility statuses."""
        risk_flag = Mock()
        risk_flag.id = 123
        health_profile_service = HealthProfileService(default_user)
        if expected_risk_name:
            mock_risk_service.get_by_name.return_value = risk_flag

        result = (
            health_profile_service.get_new_member_risk_flag_based_on_fertility_status(
                fertility_status
            )
        )

        if expected_risk_name:
            assert isinstance(result, MemberRiskFlag)
            assert result.user_id == health_profile_service.user_id
            assert result.risk_flag == risk_flag
            assert result.start == datetime.now(timezone.utc).date()
            mock_risk_service.get_by_name.assert_called_once_with(expected_risk_name)
        else:
            assert result is None
            mock_risk_service.get_by_name.assert_not_called()

    def test_update_due_date_in_hps_when_due_date_is_none(
        self, default_user, practitioner_user, mock_hps_client
    ):
        # Given
        svc = HealthProfileService(user=default_user, accessing_user=practitioner_user)

        # When
        svc.update_due_date_in_hps(None, Modifier())

        # Then
        mock_hps_client.assert_not_called()

    def test_update_due_date_in_hps_when_flag_is_off(
        self, default_user, practitioner_user, mock_migration_flag, mock_hps_client
    ):
        # Given
        mock_migration_flag.return_value = (Stage.OFF, None)
        new_due_date = default_user.health_profile.due_date + timedelta(days=5)
        svc = HealthProfileService(user=default_user, accessing_user=practitioner_user)

        # When
        svc.update_due_date_in_hps(new_due_date, Modifier())

        # Then
        mock_hps_client.assert_not_called()

    def test_update_due_date_in_hps_creates_new_pregnancy_in_hps(
        self, default_user, practitioner_user, mock_hps_client, mock_migration_flag
    ):
        # Given
        mock_migration_flag.return_value = (Stage.DUALWRITE, None)
        mock_hps_client.get_pregnancy.return_value = []
        new_due_date = default_user.health_profile.due_date + timedelta(days=5)
        modifier = Modifier(
            id=practitioner_user.id,
            name=practitioner_user.full_name,
            role="practitioner",
            verticals=practitioner_user.practitioner_profile.verticals,
        )
        svc = HealthProfileService(user=default_user, accessing_user=practitioner_user)

        # When
        svc.update_due_date_in_hps(new_due_date, modifier)

        # Then
        mock_hps_client.get_pregnancy.assert_called_once_with(
            default_user.id, ClinicalStatus.ACTIVE.value
        )
        mock_hps_client.put_pregnancy.assert_called_once_with(
            MemberCondition(
                condition_type=ConditionType.PREGNANCY.value,
                status=ClinicalStatus.ACTIVE.value,
                estimated_date=new_due_date,
                modifier=modifier,
            )
        )

    @freezegun.freeze_time("2025-03-09T00:00:00")
    def test_update_due_date_in_hps_updates_existing_pregnancy_in_hps(
        self, default_user, practitioner_user, mock_hps_client, mock_migration_flag
    ):
        # Given
        old_due_date = default_user.health_profile.due_date
        new_due_date = old_due_date + timedelta(days=5)
        mock_migration_flag.return_value = (Stage.DUALWRITE, None)
        mock_hps_client.get_pregnancy.return_value = [
            MemberCondition(
                id="123e4567-e89b-12d3-a456-426614174000",
                status="active",
                estimated_date=old_due_date,
            )
        ]
        modifier = Modifier(
            id=practitioner_user.id,
            name=practitioner_user.full_name,
            role="practitioner",
            verticals=practitioner_user.practitioner_profile.verticals,
        )
        svc = HealthProfileService(user=default_user, accessing_user=practitioner_user)

        # When
        svc.update_due_date_in_hps(new_due_date, modifier)

        # Then
        mock_hps_client.get_pregnancy.assert_called_once_with(
            default_user.id, ClinicalStatus.ACTIVE.value
        )
        mock_hps_client.patch_pregnancy_and_related_conditions.assert_called_once_with(
            "123e4567-e89b-12d3-a456-426614174000",
            {
                "pregnancy": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "user_id": default_user.id,
                    "condition_type": "pregnancy",
                    "status": None,
                    "onset_date": None,
                    "abatement_date": None,
                    "estimated_date": new_due_date.strftime("%Y-%m-%d"),
                    "is_first_occurrence": None,
                    "method_of_conception": None,
                    "outcome": None,
                    "modifier": {
                        "id": practitioner_user.id,
                        "name": practitioner_user.full_name,
                        "role": "practitioner",
                        "verticals": practitioner_user.practitioner_profile.verticals,
                    },
                    "created_at": None,
                    "updated_at": "2025-03-09T00:00:00+00:00",
                },
                "related_conditions": {},
            },
        )

    def test_update_due_date_in_hps_when_multiple_current_pregnancies_exist_in_hps(
        self, default_user, practitioner_user, mock_hps_client, mock_migration_flag
    ):
        # Given
        old_due_date = default_user.health_profile.due_date
        new_due_date = old_due_date + timedelta(days=5)
        mock_migration_flag.return_value = (Stage.DUALWRITE, None)
        mock_hps_client.get_pregnancy.return_value = [
            MemberCondition(
                status=ClinicalStatus.ACTIVE.value, estimated_date=old_due_date
            ),
            MemberCondition(
                status=ClinicalStatus.ACTIVE.value,
                estimated_date=old_due_date + timedelta(days=1),
            ),
        ]
        svc = HealthProfileService(user=default_user, accessing_user=practitioner_user)

        # When
        svc.update_due_date_in_hps(new_due_date, Modifier())

        # Then
        mock_hps_client.get_pregnancy.assert_called_once_with(
            default_user.id, ClinicalStatus.ACTIVE.value
        )
        mock_hps_client.put_pregnancy.assert_not_called()
