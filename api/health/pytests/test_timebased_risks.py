import pytest

from authn.models.user import User
from health.pytests.risk_test_data import *  # type: ignore # noqa
from health.pytests.risk_test_utils import RiskTestUtils
from health.services.member_risk_calc_service import MemberRiskCalcService
from health.services.member_risk_service import MemberRiskService
from health.tasks.member_risk_flag_update import MemberRiskFlagUpdateTask


class TestTimeBasedMemberRiskFlagUpdates:
    @pytest.mark.parametrize(
        argnames="created_at_offset,expected_value_change",
        argvalues=[
            (-40, 0),  # created date in future, shouldn't happen in reality
            (0, 0),  # created today
            (15, 0),  # created 15 days ago
            (20, 0),
            (31, 1),
            (45, 1),
            (366, 12),
        ],
    )
    def test_months_ttc(
        self,
        fertility_user: User,
        risk_flags,
        session,
        created_at_offset: int,
        expected_value_change: int,
    ):
        RiskTestUtils.add_member_risk(
            fertility_user,
            "months trying to conceive",
            5,
            created_at_offset,
        )

        MemberRiskFlagUpdateTask().run()
        actual = RiskTestUtils.get_active_risk(
            fertility_user, "months trying to conceive"
        )
        assert actual.value == 5 + expected_value_change

    def test_months_ttc_none_value_becomes_0(
        self,
        fertility_user: User,
        risk_flags,
    ):
        RiskTestUtils.add_member_risk(fertility_user, "months trying to conceive")

        MemberRiskFlagUpdateTask().run()
        actual = RiskTestUtils.get_active_risk(
            fertility_user, "months trying to conceive"
        )
        assert actual.value == 0

    def test_no_change_track_pregnancy(
        self,
        pregnancy_user: User,
        risk_flags,
    ):
        RiskTestUtils.add_member_risk(
            pregnancy_user,
            "months trying to conceive",
            5,
            120,
        )

        MemberRiskFlagUpdateTask().run()
        actual = RiskTestUtils.get_active_risk(
            pregnancy_user, "months trying to conceive"
        )
        assert actual.value == 5

    # test fails
    # ideally a new/uncommitted risk should not get updated
    # currently though, MemberRiskCalcService sees that the object has an ID and runs the update
    # which then converts None to 0
    def _test_no_change_for_new_risk(
        self,
        fertility_user: User,
        risk_flags,
    ):
        mrs = MemberRiskService(fertility_user, commit=False)
        mrs.set_risk("months trying to conceive")
        MemberRiskCalcService(mrs).run_all()
        mr = mrs.get_active_risk("months trying to conceive")
        assert mr.value is None
