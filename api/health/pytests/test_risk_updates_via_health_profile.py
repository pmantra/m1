from health.pytests.risk_test_utils import RiskTestUtils


class TestMemberRiskFlagUpdatesViaHealthProfile:
    def test_maternal_age(self, session, default_user, risk_flags):
        session.add(default_user)
        RiskTestUtils.set_age(session, default_user, 34)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" not in risk_names
        assert "Advanced Maternal Age" not in risk_names

        RiskTestUtils.set_age(session, default_user, 36)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" not in risk_names
        assert "Advanced Maternal Age" in risk_names

        RiskTestUtils.set_age(session, default_user, 41)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" in risk_names
        assert "Advanced Maternal Age" in risk_names

        RiskTestUtils.set_age(session, default_user, 34)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" not in risk_names
        assert "Advanced Maternal Age" not in risk_names

    def test_bmi(self, session, default_user, risk_flags):
        session.add(default_user)
        RiskTestUtils.set_height_weight(session, default_user, 12 * 6, 130)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Overweight" not in risk_names
        assert "Obesity" not in risk_names

        RiskTestUtils.set_height_weight(session, default_user, 12 * 6, 300)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Overweight" not in risk_names
        assert "Obesity" in risk_names

        RiskTestUtils.set_height_weight(session, default_user, 12 * 6, 200)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Overweight" in risk_names
        assert "Obesity" not in risk_names

    def test_both(self, session, default_user, risk_flags):
        RiskTestUtils.set_height_weight(session, default_user, 12 * 6, 200, False)
        RiskTestUtils.set_age(session, default_user, 41)
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Overweight" in risk_names
        assert "Obesity" not in risk_names
        assert "Advanced Maternal Age (40+)" in risk_names
        assert "Advanced Maternal Age" in risk_names
