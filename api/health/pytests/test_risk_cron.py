from authn.models.user import User
from health.pytests.risk_test_utils import RiskTestUtils
from health.tasks.member_risk_flag_update import MemberRiskFlagUpdateTask
from models.tracks.track import TrackName
from pytests.factories import MemberTrackFactory


class TestMemberRiskFlagUpdateTask:
    def test_maternal_age_update(self, session, default_user: User, risk_flags):
        MemberTrackFactory.create(
            user=default_user,
            name=TrackName.PREGNANCY,
        )
        session.add(default_user)
        session.commit()
        RiskTestUtils.set_age(session, default_user, 34)
        RiskTestUtils.delete_member_risks(session, default_user)
        MemberRiskFlagUpdateTask().run()
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" not in risk_names
        assert "Advanced Maternal Age" not in risk_names

        RiskTestUtils.set_age(session, default_user, 36)
        RiskTestUtils.delete_member_risks(session, default_user)
        MemberRiskFlagUpdateTask().run()
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" not in risk_names
        assert "Advanced Maternal Age" in risk_names

        RiskTestUtils.set_age(session, default_user, 41)
        RiskTestUtils.delete_member_risks(session, default_user)
        MemberRiskFlagUpdateTask().run()
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" in risk_names
        assert "Advanced Maternal Age" in risk_names

        RiskTestUtils.set_age(session, default_user, 34)
        RiskTestUtils.delete_member_risks(session, default_user)
        MemberRiskFlagUpdateTask().run()
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" not in risk_names
        assert "Advanced Maternal Age" not in risk_names

    # Risks should already exist so the Task should not make any updates
    def test_maternal_age_no_update(self, session, default_user: User, risk_flags):
        task = MemberRiskFlagUpdateTask()
        MemberTrackFactory.create(
            user=default_user,
            name=TrackName.PREGNANCY,
        )
        session.add(default_user)
        RiskTestUtils.set_age(session, default_user, 34)
        session.commit()
        task.run()
        assert task.num_users_updated == 0
        assert not task.num_created_by_risk_name
        assert not task.num_ended_by_risk_name
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" not in risk_names
        assert "Advanced Maternal Age" not in risk_names

        RiskTestUtils.set_age(session, default_user, 36)
        task.run()
        assert task.num_users_updated == 0
        assert not task.num_created_by_risk_name
        assert not task.num_ended_by_risk_name
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" not in risk_names
        assert "Advanced Maternal Age" in risk_names

        RiskTestUtils.set_age(session, default_user, 41)
        task.run()
        assert task.num_users_updated == 0
        assert not task.num_created_by_risk_name
        assert not task.num_ended_by_risk_name
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" in risk_names
        assert "Advanced Maternal Age" in risk_names

        RiskTestUtils.set_age(session, default_user, 34)
        task.run()
        assert task.num_users_updated == 0
        assert not task.num_created_by_risk_name
        assert not task.num_ended_by_risk_name
        risk_names = RiskTestUtils.get_risk_names(default_user)
        assert "Advanced Maternal Age (40+)" not in risk_names
        assert "Advanced Maternal Age" not in risk_names
