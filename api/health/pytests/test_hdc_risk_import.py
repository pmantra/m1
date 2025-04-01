from datetime import datetime, timedelta

import pytest

from assessments.models.hdc_models import HdcExportItem
from health.models.risk_enums import RiskFlagName
from health.pytests.risk_test_utils import RiskTestUtils
from health.services.hdc_risk_import_service import HdcRiskImportService


class TestHdcRiskImport:
    @pytest.mark.parametrize(
        argnames="day_offset,expected_value",
        argvalues=[
            (40, 0),
            (1, 0),
            (0, 0),
            (-15, 0),
            (-20, 0),
            (-31, 1),
            (-45, 1),
            (-366, 12),
        ],
    )
    def test_ttc(self, default_user, risk_flags, day_offset, expected_value):
        today = datetime.today().date()
        value = today + timedelta(days=day_offset)

        HdcRiskImportService(default_user).import_items(
            [
                HdcExportItem.from_json(
                    {
                        "event_type": "risk_flag",
                        "label": "months trying to conceive",
                        "value": value.isoformat(),
                    }
                )
            ]
        )
        risk = RiskTestUtils.get_active_risk(default_user, "months trying to conceive")
        assert risk is not None
        assert risk.value == expected_value

    def test_has_overweight_risk(self, default_user, risk_flags):
        import_result = HdcRiskImportService(default_user).import_items(
            [
                HdcExportItem.from_json(
                    {
                        "event_type": "risk_flag",
                        "label": "obesity_calc",
                        "value": {"height": 66.0, "weight": 170},
                    }
                )
            ]
        )
        assert import_result is True

        risk = RiskTestUtils.get_active_risk(default_user, RiskFlagName.BMI_OVERWEIGHT)
        assert risk is not None

    def test_has_obesity_risk(self, default_user, risk_flags):
        import_result = HdcRiskImportService(default_user).import_items(
            [
                HdcExportItem.from_json(
                    {
                        "event_type": "risk_flag",
                        "label": "obesity_calc",
                        "value": {"height": 66.0, "weight": 200},
                    }
                )
            ]
        )
        assert import_result is True

        risk = RiskTestUtils.get_active_risk(default_user, RiskFlagName.BMI_OBESITY)
        assert risk is not None

    @pytest.mark.parametrize(
        argnames="value",
        argvalues=[
            {},
            {"height": 66.0},
            {"weight": 200},
        ],
    )
    def test_no_bmi_risk_with_partial_input(self, default_user, risk_flags, value):
        import_result = HdcRiskImportService(default_user).import_items(
            [
                HdcExportItem.from_json(
                    {
                        "event_type": "risk_flag",
                        "label": "obesity_calc",
                        "value": value,
                    }
                )
            ]
        )
        assert import_result is True

        for risk_flag in [RiskFlagName.BMI_OVERWEIGHT, RiskFlagName.BMI_OBESITY]:
            with pytest.raises(Exception) as e:
                RiskTestUtils.get_active_risk(default_user, risk_flag)
                assert e.value.message == f"Risk is not Active {risk_flag.name}"
