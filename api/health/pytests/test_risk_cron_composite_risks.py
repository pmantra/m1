from authn.models.user import User
from health.pytests.risk_test_data import *  # type: ignore # noqa
from health.pytests.risk_test_utils import RiskTestUtils
from health.tasks.member_risk_flag_update import MemberRiskFlagUpdateTask


class TestMemberRiskFlagUpdateTask:
    def test_no_calculated_risks(self, pregnancy_user: User, risk_flags):
        MemberRiskFlagUpdateTask().run()
        assert len(RiskTestUtils.get_risks(pregnancy_user)) == 0
        risk_names = RiskTestUtils.get_risk_names(pregnancy_user)
        assert "High risk for preeclampsia" not in risk_names
        assert "Moderate risk for preeclampsia" not in risk_names
        assert "Risk for preterm birth" not in risk_names

    def test_high_risk_for_preeclampsia(self, pregnancy_user: User, risk_flags):
        RiskTestUtils.add_member_risk(pregnancy_user, "Autoimmune disease")
        MemberRiskFlagUpdateTask().run()
        risk_names = RiskTestUtils.get_risk_names(pregnancy_user)
        assert "High risk for preeclampsia" in risk_names

        # Test Removal of Risk
        RiskTestUtils.delete_member_risk(pregnancy_user, "Autoimmune disease")
        MemberRiskFlagUpdateTask().run()
        assert not RiskTestUtils.has_risk(pregnancy_user, "High risk for preeclampsia")

    def test_moderate_risk_for_preeclampsia(
        self, session, pregnancy_user: User, risk_flags
    ):
        name = "Moderate risk for preeclampsia"

        # Member has 1 factor, Risk should not be set
        RiskTestUtils.add_member_risk(pregnancy_user, "Fullterm birth - Past pregnancy")
        RiskTestUtils.set_age(session, pregnancy_user, 36)
        MemberRiskFlagUpdateTask().run()
        assert not RiskTestUtils.has_risk(pregnancy_user, name)

        # Test Removal of Risk - Add the Risk and run the update, Risk should not be set
        RiskTestUtils.add_member_risk(pregnancy_user, name)
        MemberRiskFlagUpdateTask().run()
        assert not RiskTestUtils.has_risk(pregnancy_user, name)

        # Member has 2 factors, Risk should be set
        RiskTestUtils.set_height_weight(session, pregnancy_user, 12 * 6, 300)
        MemberRiskFlagUpdateTask().run()
        assert RiskTestUtils.has_risk(pregnancy_user, name)

        # Delete existing Member Risks
        RiskTestUtils.delete_member_risks(session, pregnancy_user)

        # Rerun the Update Task -- BMI, Age, And Preeclampsia risks should all be set
        MemberRiskFlagUpdateTask().run()
        assert RiskTestUtils.has_risk(pregnancy_user, "Obesity")
        assert RiskTestUtils.has_risk(pregnancy_user, "Advanced Maternal Age")
        assert RiskTestUtils.has_risk(pregnancy_user, name)

    def test_risk_for_preterm_birth(self, pregnancy_user: User, risk_flags):
        name = "Risk for preterm birth"
        RiskTestUtils.add_member_risk(pregnancy_user, "blood loss")
        MemberRiskFlagUpdateTask().run()
        assert RiskTestUtils.has_risk(pregnancy_user, name)

        # Test Removal of Risk
        RiskTestUtils.delete_member_risk(pregnancy_user, "blood loss")
        MemberRiskFlagUpdateTask().run()
        assert not RiskTestUtils.has_risk(pregnancy_user, name)
