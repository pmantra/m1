from health.pytests.risk_test_utils import RiskTestUtils
from health.services.member_risk_service import MemberRiskService


# Tests to ensure calculated/composite risks get updated in realtime
class TestMemberRiskServiceCalculated:
    def test_moderate_risk_preeclampsia_via_health_profile(
        self, session, default_user, risk_flags
    ):
        # 0 factors
        RiskTestUtils.add_member_risk(
            default_user, "C-section delivery - Past pregnancy"
        )
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" not in risk_names

        # 2 factor
        RiskTestUtils.set_height_weight(session, default_user, 12 * 6, 300, False)
        RiskTestUtils.set_age(session, default_user, 41)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Obesity" in risk_names
        assert "Advanced Maternal Age (40+)" in risk_names
        assert "Moderate risk for preeclampsia" in risk_names

        # 1 factor
        RiskTestUtils.set_age(session, default_user, 30)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" not in risk_names

        # 0 factors
        RiskTestUtils.set_height_weight(session, default_user, 12 * 6, 100, False)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" not in risk_names

        # 1 factor
        RiskTestUtils.set_age(session, default_user, 40)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" not in risk_names

        # 2 factors
        RiskTestUtils.set_height_weight(session, default_user, 12 * 6, 300, False)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" in risk_names

    def test_moderate_risk_preeclampsia_via_derived_risks(
        self, default_user, risk_flags
    ):
        mrs = MemberRiskService(default_user)

        # 1 factor
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" not in risk_names

        # 2 factor , preeclampsia risk should appear
        mrs.set_risk("Unexplained infertility")
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" in risk_names

        # 1 less factor , preeclampsia should be removed
        mrs.set_risk("Preterm birth - Past pregnancy")
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" not in risk_names

        # 2 factor
        mrs.set_risk("Low socioeconomic status")
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" in risk_names

        # no factor change  , preeclampsia risk should appear
        mrs.set_risk("Fullterm birth - Past pregnancy")
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" in risk_names

    def test_obesity_should_trigger_2_composite_risks(
        self, default_user, session, risk_flags
    ):
        # composite risks should not appear yet
        mrs = MemberRiskService(default_user)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" not in risk_names
        assert "Risk for gestational diabetes" not in risk_names

        mrs.set_risk("Gestational diabetes - Past pregnancy")
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" not in risk_names
        assert "Risk for gestational diabetes" not in risk_names

        # Setting high BMI should now pass both composite risks
        RiskTestUtils.set_height_weight(session, default_user, 12 * 6, 300, False)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" in risk_names
        assert "Risk for gestational diabetes" in risk_names

        # Remove high BMI
        RiskTestUtils.set_height_weight(session, default_user, 12 * 6, 100, False)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Moderate risk for preeclampsia" not in risk_names
        assert "Risk for gestational diabetes" not in risk_names
