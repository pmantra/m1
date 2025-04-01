from unittest.mock import Mock, patch

import pytest

from health.risk_calculators.risk_for_gestational_diabetes_calculator import (
    RiskForGestationalDiabetesCalculator,
)


@pytest.fixture
def mock_feature_flags():
    with patch(
        "health.risk_calculators.risk_for_gestational_diabetes_calculator.feature_flags.bool_variation"
    ) as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_inputs():
    mock = Mock()
    mock.racial_identity.return_value = None
    mock.has_risk.return_value = False
    return mock


class TestRiskCalculator:
    @pytest.mark.parametrize(
        "racial_identity,bmi,has_other_risks,expected",
        [
            (
                "asian",
                22,
                False,
                False,
            ),  # Asian under threshold, no risks -> False due to BMI
            (
                "asian",
                22,
                True,
                False,
            ),  # Asian under threshold, with risks -> False due to BMI
            (
                "asian",
                23,
                False,
                False,
            ),  # Asian at threshold, no risks -> False due to BMI
            (
                "asian",
                23,
                True,
                False,
            ),  # Asian at threshold, with risks -> False due to BMI
            (
                "asian",
                24,
                False,
                True,
            ),  # Asian over threshold, no risks -> True due to high risk race
            ("asian", 24, True, True),  # Asian over threshold, with risks -> True
            (
                "black",
                24,
                False,
                False,
            ),  # Black under regular threshold -> False due to BMI
            (
                "black",
                26,
                False,
                True,
            ),  # Black over threshold -> True due to high risk race
            ("black", 26, True, True),  # Black over threshold, with risks -> True
            (
                "white",
                24,
                False,
                False,
            ),  # White under threshold, no risks -> False due to BMI
            (
                "white",
                24,
                True,
                False,
            ),  # White under threshold, with risks -> False due to BMI
            (
                "white",
                25,
                False,
                False,
            ),  # White at threshold, no risks -> False due to BMI
            (
                "white",
                25,
                True,
                False,
            ),  # White at threshold, with risks -> False due to BMI
            ("white", 26, False, False),  # White over threshold, no risks -> False
            ("white", 26, True, True),  # White over threshold, with risks -> True
            (
                "hispanic",
                22,
                False,
                False,
            ),  # Hispanic under threshold -> False due to BMI
            (
                "hispanic",
                26,
                False,
                True,
            ),  # Hispanic over threshold -> True due to high risk race
            (
                "native_american",
                22,
                False,
                False,
            ),  # Native American under threshold -> False due to BMI
            (
                "native_american",
                26,
                False,
                True,
            ),  # Native American over threshold -> True due to high risk race
            (
                "pacific_islander",
                22,
                False,
                False,
            ),  # Pacific Islander under threshold -> False due to BMI
            (
                "pacific_islander",
                26,
                False,
                True,
            ),  # Pacific Islander over threshold -> True due to high risk race
        ],
    )
    def test_ethnicity_bmi_combinations(
        self,
        mock_feature_flags,
        mock_inputs,
        racial_identity,
        bmi,
        has_other_risks,
        expected,
    ):
        with patch(
            "health.risk_calculators.risk_for_gestational_diabetes_calculator.BmiOverweightCalculator"
        ) as MockBmiCalc:
            MockBmiCalc.return_value.get_bmi.return_value = bmi
            mock_inputs.racial_identity.return_value = racial_identity
            mock_inputs.has_risk.return_value = has_other_risks
            calculator = RiskForGestationalDiabetesCalculator()

            result = calculator.should_member_have_risk(mock_inputs)

            assert result is expected
            assert mock_feature_flags.called
            mock_feature_flags.assert_called_with(
                "include-ethnicity-in-risk-calculation", default=False
            )

    def test_none_bmi_returns_none(self, mock_feature_flags, mock_inputs):
        """Test that None BMI returns None regardless of ethnicity."""
        with patch(
            "health.risk_calculators.risk_for_gestational_diabetes_calculator.BmiOverweightCalculator"
        ) as MockBmiCalc:
            MockBmiCalc.return_value.get_bmi.return_value = None
            mock_inputs.racial_identity.return_value = "asian"
            calculator = RiskForGestationalDiabetesCalculator()

            result = calculator.should_member_have_risk(mock_inputs)

            assert result is None

    def test_none_racial_identity(self, mock_feature_flags, mock_inputs):
        """Test behavior when racial_identity is None."""
        with patch(
            "health.risk_calculators.risk_for_gestational_diabetes_calculator.BmiOverweightCalculator"
        ) as MockBmiCalc:
            MockBmiCalc.return_value.get_bmi.return_value = 26
            mock_inputs.racial_identity.return_value = None
            mock_inputs.has_risk.return_value = False
            calculator = RiskForGestationalDiabetesCalculator()

            result = calculator.should_member_have_risk(mock_inputs)

            assert result is False
