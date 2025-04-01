from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from dateutil import parser

from common.health_profile.health_profile_service_client import (
    HealthProfileServiceClient,
)
from common.health_profile.health_profile_service_models import (
    ClinicalStatus,
    GestationalDiabetesStatus,
    MemberCondition,
    MethodOfConception,
    Modifier,
    Outcome,
    ValueWithModifierAndUpdatedAt,
)
from health.constants import (
    BABY_DOB_LABEL,
    GLUCOSE_TEST_NOT_TAKEN_EXPORT_VALUE,
    GLUCOSE_TEST_RESULT_NEED_3H_TEST,
    GLUCOSE_TEST_RESULT_NO_GDM,
    LOSS_WHEN,
    PREGNANT_DURING_IUI,
    PREGNANT_DURING_IVF,
)
from health.services.hdc_health_profile_import_service import DUE_DATE
from health.services.hps_export_utils import (
    CONDITION_TYPE_PREGNANCY,
    DAYS_BEFORE_ESTIMATED_DATE_PRETERM_BIRTH,
    MEMBER_ROLE,
    determine_outcome_for_loss,
    determine_should_skip_export_pregnancy_data_to_hps,
    export_pregnancy_data_to_hps,
    handle_glucose_test_result_export,
)


@pytest.fixture
def mock_hps_client():
    return Mock(spec=HealthProfileServiceClient)


class TestHPSExportUtils:
    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_new_pregnancy_with_iui(self, mock_hps_client_class, default_user):
        mock_client = mock_hps_client_class.return_value
        mock_client.get_pregnancy.return_value = []

        export_pregnancy_data_to_hps(
            default_user, "Fertility treatments", PREGNANT_DURING_IUI
        )

        mock_client.put_pregnancy.assert_called_once()
        called_pregnancy = mock_client.put_pregnancy.call_args[0][0]
        assert called_pregnancy.condition_type == CONDITION_TYPE_PREGNANCY
        assert called_pregnancy.modifier.id == default_user.id
        assert called_pregnancy.modifier.name == default_user.full_name
        assert called_pregnancy.modifier.role == MEMBER_ROLE
        assert (
            called_pregnancy.method_of_conception.value == MethodOfConception.IUI.value
        )
        assert called_pregnancy.method_of_conception.modifier == Modifier(
            id=default_user.id,
            name=default_user.full_name,
            role=MEMBER_ROLE,
        )
        assert called_pregnancy.estimated_date == default_user.health_profile.due_date
        assert called_pregnancy.is_first_occurrence is None
        assert called_pregnancy.outcome is None
        assert called_pregnancy.abatement_date is None
        assert called_pregnancy.status == "active"

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_new_pregnancy_with_ivf(self, mock_hps_client_class, default_user):
        mock_client = mock_hps_client_class.return_value
        mock_client.get_pregnancy.return_value = []

        export_pregnancy_data_to_hps(
            default_user, "Fertility treatments", PREGNANT_DURING_IVF
        )

        mock_client.put_pregnancy.assert_called_once()
        called_pregnancy = mock_client.put_pregnancy.call_args[0][0]
        assert called_pregnancy.condition_type == CONDITION_TYPE_PREGNANCY
        assert called_pregnancy.modifier.id == default_user.id
        assert called_pregnancy.modifier.name == default_user.full_name
        assert called_pregnancy.modifier.role == MEMBER_ROLE
        assert (
            called_pregnancy.method_of_conception.value == MethodOfConception.IVF.value
        )
        assert called_pregnancy.method_of_conception.modifier == Modifier(
            id=default_user.id,
            name=default_user.full_name,
            role=MEMBER_ROLE,
        )
        assert called_pregnancy.estimated_date == default_user.health_profile.due_date
        assert called_pregnancy.is_first_occurrence is None
        assert called_pregnancy.outcome is None
        assert called_pregnancy.abatement_date is None
        assert called_pregnancy.status == "active"

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_pregnancy_welcome_export(self, mock_hps_client_class, default_user):
        mock_client = mock_hps_client_class.return_value
        mock_client.get_pregnancy.return_value = []
        value = {"first_time_mom": "yes", "Fertility treatments": "yes"}

        export_pregnancy_data_to_hps(default_user, "pregnancy_welcome_export", value)

        mock_client.put_pregnancy.assert_called_once()
        called_pregnancy = mock_client.put_pregnancy.call_args[0][0]
        assert called_pregnancy.condition_type == CONDITION_TYPE_PREGNANCY
        assert called_pregnancy.modifier.id == default_user.id
        assert called_pregnancy.modifier.name == default_user.full_name
        assert called_pregnancy.modifier.role == MEMBER_ROLE
        assert (
            called_pregnancy.method_of_conception.value
            == MethodOfConception.OTHER_FERTILITY_TREATMENT.value
        )
        assert called_pregnancy.method_of_conception.modifier == Modifier(
            id=default_user.id,
            name=default_user.full_name,
            role=MEMBER_ROLE,
        )
        assert called_pregnancy.estimated_date == default_user.health_profile.due_date
        assert called_pregnancy.is_first_occurrence is True
        assert called_pregnancy.outcome is None
        assert called_pregnancy.abatement_date is None
        assert called_pregnancy.status == "active"

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_fertility_transition_export(self, mock_hps_client_class, default_user):
        mock_client = mock_hps_client_class.return_value
        mock_client.get_pregnancy.return_value = []
        expected_date = parser.parse("2025-03-19").date()
        value = {
            "due_date": "2025-03-19T20:08:00+00:00",
            "Fertility treatments": "pregnant_during_iui",
        }

        export_pregnancy_data_to_hps(
            default_user, "fertility_transition_offboarding_export", value
        )

        mock_client.put_pregnancy.assert_called_once()
        called_pregnancy = mock_client.put_pregnancy.call_args[0][0]
        assert called_pregnancy.condition_type == CONDITION_TYPE_PREGNANCY
        assert called_pregnancy.modifier.id == default_user.id
        assert called_pregnancy.modifier.name == default_user.full_name
        assert called_pregnancy.modifier.role == MEMBER_ROLE
        assert (
            called_pregnancy.method_of_conception.value == MethodOfConception.IUI.value
        )
        assert called_pregnancy.method_of_conception.modifier == Modifier(
            id=default_user.id,
            name=default_user.full_name,
            role=MEMBER_ROLE,
        )
        assert called_pregnancy.estimated_date == expected_date
        assert (
            called_pregnancy.is_first_occurrence
            == default_user.health_profile.first_time_mom
        )
        assert called_pregnancy.outcome is None
        assert called_pregnancy.abatement_date is None
        assert called_pregnancy.status == "active"

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_due_date_update(self, mock_hps_client_class, default_user):
        mock_client = mock_hps_client_class.return_value
        mock_client.get_pregnancy.return_value = []
        expected_date = parser.parse("2025-03-19").date()
        value = "2025-03-19T20:08:00+00:00"

        export_pregnancy_data_to_hps(default_user, DUE_DATE, value)

        mock_client.put_pregnancy.assert_called_once()
        called_pregnancy = mock_client.put_pregnancy.call_args[0][0]
        assert called_pregnancy.condition_type == CONDITION_TYPE_PREGNANCY
        assert called_pregnancy.modifier.id == default_user.id
        assert called_pregnancy.modifier.name == default_user.full_name
        assert called_pregnancy.modifier.role == MEMBER_ROLE
        assert called_pregnancy.method_of_conception is None
        assert called_pregnancy.estimated_date == expected_date
        assert called_pregnancy.is_first_occurrence is None
        assert called_pregnancy.outcome is None
        assert called_pregnancy.abatement_date is None
        assert called_pregnancy.status == "active"

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_baby_birth_update(self, mock_hps_client_class, default_user):
        mock_client = mock_hps_client_class.return_value
        mock_client.get_pregnancy.return_value = []

        due_date = default_user.health_profile.due_date
        baby_dob = due_date - timedelta(days=10)  # 10 days before due date (term birth)
        value = baby_dob.isoformat()

        export_pregnancy_data_to_hps(default_user, BABY_DOB_LABEL, value)

        mock_client.put_pregnancy.assert_called_once()
        called_pregnancy = mock_client.put_pregnancy.call_args[0][0]
        assert called_pregnancy.condition_type == CONDITION_TYPE_PREGNANCY
        assert called_pregnancy.modifier.id == default_user.id
        assert called_pregnancy.modifier.name == default_user.full_name
        assert called_pregnancy.modifier.role == MEMBER_ROLE
        assert called_pregnancy.method_of_conception is None
        assert called_pregnancy.estimated_date == default_user.health_profile.due_date
        assert called_pregnancy.is_first_occurrence is None
        assert called_pregnancy.outcome.value == Outcome.LIVE_BIRTH_TERM.value
        assert called_pregnancy.abatement_date == baby_dob
        assert called_pregnancy.status == "resolved"

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_baby_birth_update_preterm(self, mock_hps_client_class, default_user):
        mock_client = mock_hps_client_class.return_value
        mock_client.get_pregnancy.return_value = []

        due_date = default_user.health_profile.due_date
        baby_dob = due_date - timedelta(
            days=DAYS_BEFORE_ESTIMATED_DATE_PRETERM_BIRTH + 5
        )  # 34 days before due date (preterm birth)
        value = baby_dob.isoformat()

        export_pregnancy_data_to_hps(default_user, BABY_DOB_LABEL, value)

        mock_client.put_pregnancy.assert_called_once()
        called_pregnancy = mock_client.put_pregnancy.call_args[0][0]
        assert called_pregnancy.condition_type == CONDITION_TYPE_PREGNANCY
        assert called_pregnancy.modifier.id == default_user.id
        assert called_pregnancy.modifier.name == default_user.full_name
        assert called_pregnancy.modifier.role == MEMBER_ROLE
        assert called_pregnancy.method_of_conception is None
        assert called_pregnancy.estimated_date == default_user.health_profile.due_date
        assert called_pregnancy.is_first_occurrence is None
        assert called_pregnancy.outcome.value == Outcome.LIVE_BIRTH_PRETERM.value
        assert called_pregnancy.abatement_date == baby_dob
        assert called_pregnancy.status == "resolved"

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_pregnancy_loss(self, mock_hps_client_class, default_user):
        """Test that a pregnancy loss is handled correctly"""
        mock_client = mock_hps_client_class.return_value
        mock_client.get_pregnancy.return_value = []
        value = "9-12"

        # Create a fixed date for testing
        mock_date = datetime(2023, 6, 1).date()

        # Mock the handle_loss function to set the outcome and abatement_date
        def mock_handle_loss_impl(pregnancy, user, val):
            outcome = determine_outcome_for_loss(val)
            pregnancy.outcome = ValueWithModifierAndUpdatedAt(
                value=outcome.value,
                modifier=Modifier(
                    id=user.id,
                    name=user.full_name,
                    role=MEMBER_ROLE,
                ),
                updated_at=datetime.utcnow(),
            )
            pregnancy.abatement_date = mock_date

        with patch(
            "health.services.hps_export_utils.handle_loss",
            side_effect=mock_handle_loss_impl,
        ):
            # Execute the function
            export_pregnancy_data_to_hps(default_user, LOSS_WHEN, value)

            # Verify the pregnancy was updated correctly
            mock_client.put_pregnancy.assert_called_once()
            called_pregnancy = mock_client.put_pregnancy.call_args[0][0]
            assert called_pregnancy.condition_type == CONDITION_TYPE_PREGNANCY
            assert called_pregnancy.modifier.id == default_user.id
            assert called_pregnancy.modifier.name == default_user.full_name
            assert called_pregnancy.modifier.role == MEMBER_ROLE
            assert called_pregnancy.method_of_conception is None
            assert (
                called_pregnancy.estimated_date == default_user.health_profile.due_date
            )
            assert called_pregnancy.is_first_occurrence is None
            assert (
                called_pregnancy.outcome.value
                == determine_outcome_for_loss("9-12").value
            )
            assert called_pregnancy.abatement_date == mock_date
            assert called_pregnancy.status == "resolved"

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_existing_pregnancy_update(self, mock_hps_client_class, default_user):
        mock_client = mock_hps_client_class.return_value
        existing_pregnancy = MemberCondition(
            condition_type=CONDITION_TYPE_PREGNANCY,
            modifier=Modifier(
                id=default_user.id,
                name=default_user.full_name,
                role=MEMBER_ROLE,
            ),
            estimated_date=parser.parse("2025-01-01").date(),
            is_first_occurrence=True,
            method_of_conception=ValueWithModifierAndUpdatedAt(
                value=MethodOfConception.IUI.value,
                modifier=Modifier(
                    id=123,
                    name="Test provider",
                    role="practitioner",
                    verticals=["ob-gyn"],
                ),
            ),
            status="active",
        )
        mock_client.get_pregnancy.return_value = [existing_pregnancy]
        expected_date = parser.parse("2025-03-19").date()
        value = "2025-03-19T20:08:00+00:00"

        export_pregnancy_data_to_hps(default_user, DUE_DATE, value)

        mock_client.put_pregnancy.assert_called_once()
        called_pregnancy = mock_client.put_pregnancy.call_args[0][0]
        assert called_pregnancy.condition_type == CONDITION_TYPE_PREGNANCY
        assert called_pregnancy.modifier.id == default_user.id
        assert called_pregnancy.modifier.name == default_user.full_name
        assert called_pregnancy.modifier.role == MEMBER_ROLE
        assert (
            called_pregnancy.method_of_conception.value == MethodOfConception.IUI.value
        )
        # since there's no change on method_of_conception, modifier should stay unchanged as provider
        assert called_pregnancy.method_of_conception.modifier == Modifier(
            id=123,
            name="Test provider",
            role="practitioner",
            verticals=["ob-gyn"],
        )
        assert called_pregnancy.estimated_date == expected_date
        assert called_pregnancy.is_first_occurrence is True
        assert called_pregnancy.outcome is None
        assert called_pregnancy.abatement_date is None
        assert called_pregnancy.status == "active"

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_export_with_invalid_data(self, mock_hps_client_class, default_user):
        """Test that errors are properly caught and logged in export_pregnancy_data_to_hps"""
        mock_client = mock_hps_client_class.return_value
        mock_client.get_pregnancy.return_value = []

        # Test with invalid date format for baby DOB
        with patch("health.services.hps_export_utils.log") as mock_log:
            with pytest.raises(ValueError) as excinfo:
                export_pregnancy_data_to_hps(default_user, BABY_DOB_LABEL, "not-a-date")

            assert "Unknown string format" in str(excinfo.value)
            mock_log.error.assert_called()

        # Test with invalid data type for pregnancy welcome
        with patch("health.services.hps_export_utils.log") as mock_log:
            with pytest.raises(ValueError) as excinfo:
                export_pregnancy_data_to_hps(
                    default_user, "pregnancy_welcome_export", "not-a-dict"
                )

            assert "Expected dict for pregnancy_welcome_export" in str(excinfo.value)
            mock_log.error.assert_called()

        # Test with None value for baby DOB
        with patch("health.services.hps_export_utils.log") as mock_log:
            with pytest.raises(TypeError) as excinfo:
                export_pregnancy_data_to_hps(default_user, BABY_DOB_LABEL, None)

            assert "Parser must be a string or character stream, not NoneType" in str(
                excinfo.value
            )
            mock_log.error.assert_called()

        # Verify that no pregnancy was saved in any of these error cases
        assert mock_client.put_pregnancy.call_count == 0

    def test_determine_outcome_for_loss(self):
        """Test the determine_outcome_for_loss function"""
        # Test miscarriage outcomes
        for value in ["5-8", "9-12", "13-19"]:
            assert determine_outcome_for_loss(value) == Outcome.MISCARRIAGE.value

        # Test stillbirth outcomes
        for value in ["20-23", "24-or-more"]:
            assert determine_outcome_for_loss(value) == Outcome.STILLBIRTH.value

        # Test unknown outcome
        assert determine_outcome_for_loss("unknown") == Outcome.UNKNOWN.value
        assert determine_outcome_for_loss(None) == Outcome.UNKNOWN.value


class TestSkipHPSExportUtils:
    def test_skip_export_current_pregnancy_exists(self, mock_hps_client, default_user):
        # Arrange
        pregnancy = MemberCondition(id=8237434619)
        abatement_date = datetime(2025, 1, 1).date()

        # Act
        result = determine_should_skip_export_pregnancy_data_to_hps(
            pregnancy=pregnancy,
            abatement_date=abatement_date,
            hps_client=mock_hps_client,
            user=default_user,
        )

        # Assert
        assert result is False
        mock_hps_client.get_pregnancy.assert_not_called()

    def test_skip_export_no_resolved_pregnancies(self, mock_hps_client, default_user):
        # Arrange
        pregnancy = MemberCondition(id=None)
        abatement_date = datetime(2025, 1, 1).date()
        mock_hps_client.get_pregnancy.return_value = []

        # Act
        result = determine_should_skip_export_pregnancy_data_to_hps(
            pregnancy=pregnancy,
            abatement_date=abatement_date,
            hps_client=mock_hps_client,
            user=default_user,
        )

        # Assert
        assert result is False
        mock_hps_client.get_pregnancy.assert_called_once_with(
            default_user.id, ClinicalStatus.RESOLVED.value
        )

    def test_skip_export_matching_abatement_date(self, mock_hps_client, default_user):
        # Arrange
        pregnancy = MemberCondition(id=None)
        abatement_date = datetime(2025, 1, 1).date()

        mock_resolved_pregnancy = Mock()
        mock_resolved_pregnancy.abatement_date = abatement_date
        mock_hps_client.get_pregnancy.return_value = [mock_resolved_pregnancy]

        # Act
        result = determine_should_skip_export_pregnancy_data_to_hps(
            pregnancy=pregnancy,
            abatement_date=abatement_date,
            hps_client=mock_hps_client,
            user=default_user,
        )

        # Assert
        assert result is True
        mock_hps_client.get_pregnancy.assert_called_once_with(
            default_user.id, ClinicalStatus.RESOLVED.value
        )

    def test_skip_export_no_matching_abatement_date(
        self, mock_hps_client, default_user
    ):
        # Arrange
        pregnancy = MemberCondition(id=None)
        abatement_date = datetime(2025, 1, 1).date()

        different_date = abatement_date - timedelta(days=1)
        mock_resolved_pregnancy = Mock()
        mock_resolved_pregnancy.abatement_date = different_date
        mock_hps_client.get_pregnancy.return_value = [mock_resolved_pregnancy]

        # Act
        result = determine_should_skip_export_pregnancy_data_to_hps(
            pregnancy=pregnancy,
            abatement_date=abatement_date,
            hps_client=mock_hps_client,
            user=default_user,
        )

        # Assert
        assert result is False
        mock_hps_client.get_pregnancy.assert_called_once_with(
            default_user.id, ClinicalStatus.RESOLVED.value
        )

    def test_skip_export_multiple_pregnancies_one_match(
        self, mock_hps_client, default_user
    ):
        # Arrange
        pregnancy = MemberCondition(id=None)
        abatement_date = datetime(2025, 1, 1).date()

        mock_pregnancy1 = Mock()
        mock_pregnancy1.abatement_date = abatement_date - timedelta(days=10)

        mock_pregnancy2 = Mock()
        mock_pregnancy2.abatement_date = abatement_date

        mock_hps_client.get_pregnancy.return_value = [mock_pregnancy1, mock_pregnancy2]

        # Act
        result = determine_should_skip_export_pregnancy_data_to_hps(
            pregnancy=pregnancy,
            abatement_date=abatement_date,
            hps_client=mock_hps_client,
            user=default_user,
        )

        # Assert
        assert result is True
        mock_hps_client.get_pregnancy.assert_called_once_with(
            default_user.id, ClinicalStatus.RESOLVED.value
        )


class TestGlucoseTestResultExport:
    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_handle_glucose_test_not_taken(self, mock_hps_client, default_user):
        mock_client = mock_hps_client.return_value
        mock_client.get_pregnancy.return_value = []
        value = GLUCOSE_TEST_NOT_TAKEN_EXPORT_VALUE

        handle_glucose_test_result_export(default_user, value, True)

        mock_client.put_current_pregnancy_and_gdm_status.assert_called_once()
        call_kwargs = mock_client.put_current_pregnancy_and_gdm_status.call_args[1]
        assert call_kwargs["gdm_status"] == GestationalDiabetesStatus.NOT_TESTED

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_handle_glucose_test_negative(self, mock_hps_client, default_user):
        mock_client = mock_hps_client.return_value
        mock_client.get_pregnancy.return_value = []
        value = GLUCOSE_TEST_RESULT_NO_GDM

        handle_glucose_test_result_export(default_user, value, True)

        mock_client.put_current_pregnancy_and_gdm_status.assert_called_once()
        call_kwargs = mock_client.put_current_pregnancy_and_gdm_status.call_args[1]
        assert call_kwargs["gdm_status"] == GestationalDiabetesStatus.TESTED_NEGATIVE

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_handle_glucose_test_pending(self, mock_hps_client, default_user):
        mock_client = mock_hps_client.return_value
        mock_client.get_pregnancy.return_value = []
        value = GLUCOSE_TEST_RESULT_NEED_3H_TEST

        handle_glucose_test_result_export(default_user, value, True)

        mock_client.put_current_pregnancy_and_gdm_status.assert_called_once()
        call_kwargs = mock_client.put_current_pregnancy_and_gdm_status.call_args[1]
        assert (
            call_kwargs["gdm_status"] == GestationalDiabetesStatus.TEST_RESULT_PENDING
        )

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_handle_glucose_test_invalid_value(self, mock_hps_client, default_user):
        mock_client = mock_hps_client.return_value
        value = "invalid_value"

        handle_glucose_test_result_export(default_user, value, True)

        mock_client.put_current_pregnancy_and_gdm_status.assert_not_called()

    @patch("health.services.hps_export_utils.HealthProfileServiceClient")
    def test_handle_glucose_use_due_date_from_health_profile(
        self, mock_hps_client, default_user
    ):
        mock_client = mock_hps_client.return_value
        value = GLUCOSE_TEST_NOT_TAKEN_EXPORT_VALUE
        handle_glucose_test_result_export(default_user, value, True)

        mock_client.put_current_pregnancy_and_gdm_status.assert_called_once()
        call_kwargs = mock_client.put_current_pregnancy_and_gdm_status.call_args[1]
        assert call_kwargs["gdm_status"] == GestationalDiabetesStatus.NOT_TESTED
        assert call_kwargs["pregnancy_due_date"] == default_user.health_profile.due_date
