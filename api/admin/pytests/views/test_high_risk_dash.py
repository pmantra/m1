from datetime import datetime, timedelta
from unittest import mock

import factory
import pytest

from admin.views.models.users import HighRiskUsersView
from authn.models.user import User
from health.services.member_risk_service import MemberRiskService
from messaging.models.messaging import Channel
from models.profiles import CareTeamTypes
from models.verticals_and_specialties import CX_VERTICAL_NAME
from pytests.factories import (
    AppointmentFactory,
    DefaultUserFactory,
    EnterpriseUserFactory,
    MessageFactory,
    PractitionerUserFactory,
    VerticalFactory,
)


@pytest.fixture
def high_risk_view(db):
    with mock.patch(
        "flask_admin.actions.ActionsMixin.init_actions", return_value=False
    ):
        view = HighRiskUsersView(User, db.session)
    return view


class TestHighRiskDash:
    def test_list_no_users(self, high_risk_view):
        assert (0, []) == high_risk_view.get_list(
            page=0, sort_column=None, sort_desc=False, search=None, filters=[]
        )

    def test_list_users(self, db, high_risk_view, risk_flags):
        now = datetime.utcnow()
        ca_vertical = VerticalFactory(name=CX_VERTICAL_NAME)
        cc_user = PractitionerUserFactory.create(
            email="kaitlyn+prac@mavenclinic.com",
            practitioner_profile__verticals=[ca_vertical],
        )
        prac_user = PractitionerUserFactory.create()
        # filter data setup
        users = EnterpriseUserFactory.create_batch(
            size=5,
        )
        for user in users:
            MemberRiskService(user.id).set_risk("High")
            MemberRiskService(user.id).set_risk("High2")
            user.add_practitioner_to_care_team(
                cc_user.id, CareTeamTypes.CARE_COORDINATOR
            )
        u1, u2, u3, u4, u5 = users
        # include member note filter data
        u3.member_profile.follow_up_reminder_send_time = now
        u2.member_profile.follow_up_reminder_send_time = now - timedelta(hours=1)
        # include activity info filter data
        for user in [u1, u2, u3]:
            prac_channel = Channel.get_or_create_channel(user, [prac_user])
            cc_channel = Channel.get_or_create_channel(user, [cc_user])
            MessageFactory.create_batch(
                size=3,
                user=factory.Iterator([user, prac_user, cc_user]),
                body="Test Message",
                channel=factory.Iterator([prac_channel, prac_channel, cc_channel]),
            )
        for user in [u4, u5]:
            AppointmentFactory.create_with_practitioner(
                member_schedule=user.schedule,
                practitioner=prac_user,
                scheduled_start=now,
            )
            AppointmentFactory.create_with_practitioner(
                member_schedule=user.schedule,
                practitioner=cc_user,
                scheduled_start=now,
            )

        # non-enterprise user who should be filtered out
        non_enterprise_user: User = DefaultUserFactory.create()
        non_enterprise_user.add_practitioner_to_care_team(
            cc_user.id, CareTeamTypes.CARE_COORDINATOR
        )

        # Have the view filter by the cc_user's view via _login_cc_email
        with mock.patch(
            "admin.views.models.users._login_cc_email", return_value=cc_user.email
        ):
            assert (5, [u1, u2, u3, u4, u5]) == high_risk_view.get_list(
                page=0, sort_column=None, sort_desc=False, search=None, filters=[]
            )
            assert (5, [u3, u2, u1, u4, u5]) == high_risk_view.get_list(
                page=0,
                sort_column="member_note",
                sort_desc=True,
                search=None,
                filters=[],
            )
