from unittest.mock import Mock, patch

import pytest

from health.models.risk_enums import RiskFlagName
from health.pytests.risk_test_utils import RiskTestUtils
from health.risk_calculators.moderate_risk_for_preeclampsia_calculator import (
    MODERATE_RISK_RACIAL_IDENTITY,
    ModerateRiskForPreeclampsiaCalculator,
)


@pytest.fixture
def mock_inputs():
    inputs = Mock()
    inputs.has_any_risk.return_value = True
    inputs.has_risk.return_value = False
    inputs.racial_identity.return_value = None
    return inputs


@pytest.fixture
def mock_feature_flags():
    with patch(
        "health.risk_calculators.moderate_risk_for_preeclampsia_calculator.feature_flags.bool_variation"
    ) as mock:
        mock.return_value = True
        yield mock


# Tests to ensure calculated/composite risks get updated in realtime
class TestRiskPreclampsiaModerate:
    def test_nulliparity(self, session, default_user, risk_flags):
        # 1 factor - nulliparity
        assert not RiskTestUtils.has_risk(
            default_user, "Moderate risk for preeclampsia"
        )

        # 2 factors, nulliparity, age
        RiskTestUtils.set_age(session, default_user, 40)
        assert RiskTestUtils.has_risk(default_user, "Moderate risk for preeclampsia")

        # 3 factors nulliparity, age, weight
        RiskTestUtils.set_height_weight(session, default_user, 12 * 6, 300, False)
        assert RiskTestUtils.has_risk(default_user, "Moderate risk for preeclampsia")

        # 2 factors age, weight: add risk that would set nulliparity
        RiskTestUtils.add_member_risk(
            default_user, "C-section delivery - Past pregnancy"
        )
        assert RiskTestUtils.has_risk(default_user, "Moderate risk for preeclampsia")

        # 2 factors age, weight: add another risk that would set nulliparity
        RiskTestUtils.add_member_risk(default_user, "Fullterm birth - Past pregnancy")
        assert RiskTestUtils.has_risk(default_user, "Moderate risk for preeclampsia")

        # 1 factor weighy
        RiskTestUtils.set_age(session, default_user, 30)
        assert not RiskTestUtils.has_risk(
            default_user, "Moderate risk for preeclampsia"
        )

    @pytest.mark.parametrize(
        "racial_identity,other_factors,expected",
        [
            (MODERATE_RISK_RACIAL_IDENTITY, 1, True),  # Black + 1 factor = risk
            (MODERATE_RISK_RACIAL_IDENTITY, 0, False),  # Black alone = no risk
            ("other", 1, False),  # Other race + 1 factor = no risk
            ("other", 2, True),  # Other race + 2 factors = risk
            (None, 2, True),  # No race + 2 factors = risk
            (None, 1, False),  # No race + 1 factor = no risk
        ],
    )
    def test_racial_identity_combinations(
        self, mock_feature_flags, mock_inputs, racial_identity, other_factors, expected
    ):
        mock_inputs.racial_identity.return_value = racial_identity
        mock_feature_flags.bool_variation.return_value = True
        nulliparity = {
            RiskFlagName.PRETERM_LABOR_PAST_PREGNANCY,
            RiskFlagName.FULLTERM_LABOR_PAST_PREGNANCY,
            RiskFlagName.CSECTION_PAST_PREGNANCY,
        }

        # Define side effect for has_any_risk
        def has_any_risk_side_effect(risk_list):
            if set(risk_list) == nulliparity:
                # For 1 or more factors, we want nulliparity risk
                return False if other_factors >= 1 else True
            return False  # No other group risks by default

        mock_inputs.has_any_risk.side_effect = has_any_risk_side_effect

        # Set up BMI risk for 2 or more factors
        if other_factors >= 2:
            mock_inputs.has_risk.side_effect = lambda x: x == RiskFlagName.BMI_OBESITY
        else:
            mock_inputs.has_risk.return_value = False

        calculator = ModerateRiskForPreeclampsiaCalculator()
        result = calculator.should_member_have_risk(mock_inputs)

        assert result is expected

    @pytest.mark.parametrize(
        "risk_factors,expected",
        [
            # Test nulliparity alone
            ({"nulliparity": False}, 1),  # No previous pregnancy = 1 factor
            ({"nulliparity": True}, 0),  # Has previous pregnancy = 0 factors
            # Test low economic status alone
            ({"low_economic_status": True}, 1),  # Has economic risk = 1 factor
            ({"low_economic_status": False}, 0),  # No economic risk = 0 factors
            # Test fertility diagnosis alone
            ({"fertility": True}, 1),  # Has fertility risk = 1 factor
            ({"fertility": False}, 0),  # No fertility risk = 0 factors
            # Test combinations - each should give 2 factors = at risk
            (
                {"nulliparity": False, "low_economic_status": True},
                2,
            ),  # No pregnancy + economic risk
            ({"nulliparity": False, "fertility": True}, 2),  # No pregnancy + fertility
            (
                {"low_economic_status": True, "fertility": True},
                2,
            ),  # Economic + fertility
            # Test all three - should count as 3 factors
            ({"nulliparity": False, "low_economic_status": True, "fertility": True}, 3),
        ],
    )
    def test_risk_factor_combinations(
        self, mock_inputs, mock_feature_flags, risk_factors, expected
    ):
        # Default all risk checks to no risk
        mock_inputs.has_any_risk.return_value = True  # Makes nulliparity check False
        mock_inputs.has_risk.return_value = False

        # Setup specific risk factors based on test parameters
        def has_any_risk_side_effect(risk_list):
            if set(risk_list) == {
                RiskFlagName.PRETERM_LABOR_PAST_PREGNANCY,
                RiskFlagName.FULLTERM_LABOR_PAST_PREGNANCY,
                RiskFlagName.CSECTION_PAST_PREGNANCY,
            }:
                return risk_factors.get("nulliparity", True)

            if set(risk_list) == {
                RiskFlagName.LOW_SOCIOECONOMIC_STATUS,
                RiskFlagName.SDOH_FOOD,
                RiskFlagName.SDOH_HOUSING,
                RiskFlagName.SDOH_MEDICINE,
            }:
                return risk_factors.get("low_economic_status", False)

            if set(risk_list) == {
                RiskFlagName.INFERTILITY_DIAGNOSIS,
                RiskFlagName.FERTILITY_TREATMENTS,
            }:
                return risk_factors.get("fertility", False)

            return True

        mock_inputs.has_any_risk.side_effect = has_any_risk_side_effect

        # Disable racial identity factor for these tests
        mock_feature_flags.bool_variation.return_value = False

        calculator = ModerateRiskForPreeclampsiaCalculator()
        result = calculator.should_member_have_risk(mock_inputs)

        # Verify risk assessment (2 or more factors = at risk)
        assert result is (expected >= 2)
