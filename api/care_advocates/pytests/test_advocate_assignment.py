from unittest.mock import patch

import pytest
from sqlalchemy import func

from authn.models.user import User
from care_advocates.routes import advocate_assignment
from health.models.risk_enums import RiskInputKey
from health.services.member_risk_service import MemberRiskService
from models.tracks.track import TrackName
from pytests.freezegun import freeze_time
from storage.connection import db


class TestAdvocateAssignment:
    url_prefix = "/api/v1/advocate-assignment/reassign"

    def test_unauthenticated_user(self, client, api_helpers):
        resp = client.post(
            f"{self.url_prefix}/1",
            headers=api_helpers.json_headers(),
        )
        assert resp.status_code == 401

    def test_invalid_user_id(self, client, api_helpers, default_user):
        max_id = db.session.query(func.max(User.id)).first()[0]
        invalid_user_id = max_id + 1
        resp = client.post(
            f"{self.url_prefix}/{invalid_user_id}",
            headers=api_helpers.json_headers(default_user),
        )
        assert resp.status_code == 400
        assert api_helpers.load_json(resp)["message"] == "Invalid User ID"

    @patch("tasks.braze.update_care_advocate_attrs.delay")
    def test_valid_user(
        self,
        mock_update_care_advocate_attrs,
        client,
        api_helpers,
        factories,
        default_user,
    ):
        member = factories.EnterpriseUserFactory.create()
        original_ca = member.care_coordinators[0]

        new_practitioner = factories.PractitionerUserFactory.create()
        factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=new_practitioner
        )

        resp = client.post(
            f"{self.url_prefix}/{member.id}",
            headers=api_helpers.json_headers(default_user),
        )
        assert resp.status_code == 200
        assert api_helpers.load_json(resp)["success"] is True
        mock_update_care_advocate_attrs.assert_called_once_with(member.id)

        # Check that change in persistent in db
        db.session.expire(member)
        new_ca = member.care_coordinators[0]

        assert original_ca != new_ca
        assert new_ca == new_practitioner

    def test_valid_user_more_than_one_track(
        self, client, api_helpers, default_user, factories
    ):
        member = factories.EnterpriseUserFactory.create()
        factories.MemberTrackFactory.create(
            name="pregnancy",
            user=member,
        )
        factories.MemberTrackFactory.create(
            name="adoption",
            user=member,
        )
        resp = client.post(
            f"{self.url_prefix}/{member.id}",
            headers=api_helpers.json_headers(default_user),
        )
        assert resp.status_code == 200
        assert (
            api_helpers.load_json(resp)["message"]
            == "User already has a CA and is on a second track."
        )

    @patch.object(advocate_assignment, "_is_a_2nd_aa_call")
    def test_need_updated_risk_factors(
        self, test__is_a_2nd_aa_call, client, api_helpers, default_user, factories
    ):
        member = factories.EnterpriseUserFactory.create()
        original_ca = member.care_coordinators[0]

        new_practitioner = factories.PractitionerUserFactory.create()
        factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=new_practitioner
        )
        # Bypass the is_a_2nd_aa_call check since we only have one call
        test__is_a_2nd_aa_call.return_value = False

        resp = client.post(
            f"{self.url_prefix}/{member.id}",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({"need_updated_risk_factors": True}),
        )
        assert resp.status_code == 200
        assert api_helpers.load_json(resp)["success"] is True

        # Check that change in persistent in db
        db.session.expire(member)
        new_ca = member.care_coordinators[0]

        assert original_ca != new_ca
        assert new_ca == new_practitioner

    @patch("care_advocates.routes.advocate_assignment.ensure_care_advocate")
    @patch.object(advocate_assignment, "_is_a_2nd_aa_call")
    def test_risk_factor_aggregation(
        self,
        test__is_a_2nd_aa_call,
        ensure_care_advocate_mock,
        client,
        api_helpers,
        default_user,
        factories,
        risk_flags,
    ):
        member = factories.EnterpriseUserFactory.create()

        new_practitioner = factories.PractitionerUserFactory.create()
        factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=new_practitioner
        )
        # Bypass the is_a_2nd_aa_call check since we only have one call
        test__is_a_2nd_aa_call.return_value = False
        MemberRiskService(member.id).set_risk("Drug use")
        MemberRiskService(member.id).set_risk("None")
        MemberRiskService(member.id).set_risk("Overweight")

        client.post(
            f"{self.url_prefix}/{member.id}",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({"need_updated_risk_factors": True}),
        )

        ensure_care_advocate_mock.assert_called_once_with(
            user=member, multitrack_onboarding=False
        )


@pytest.fixture
def mock_is_toggle_enabled_true():
    with patch(
        "care_advocates.routes.advocate_assignment.is_toggle_enabled",
        return_value=True,
    ) as mock_is_toggle_enabled:
        yield mock_is_toggle_enabled


@pytest.fixture
def post_aa_reassign(client, api_helpers):
    def _post_aa_reassign(
        user_id,
        default_user,
        data={},  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
    ):
        return client.post(
            f"/api/v1/advocate-assignment/reassign/{user_id}",
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(default_user),
        )

    return _post_aa_reassign


class TestAdvocateAssignmentDisregard2ndCalls:
    def test_duplicate_endpoint_hits(
        self, default_user, factories, post_aa_reassign, risk_flags
    ):
        with freeze_time("2023-02-22T11:00:00"):
            member = factories.EnterpriseUserFactory.create()
            original_ca = member.care_coordinators[0]

        new_practitioner = factories.PractitionerUserFactory.create()
        factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=new_practitioner
        )
        mrs = MemberRiskService(default_user)
        mrs.set_risk("Drug use")
        mrs.calculate_risks({RiskInputKey.WEIGHT_LB: 64, RiskInputKey.HEIGHT_IN: 150})

        with freeze_time("2023-02-23T11:00:00"):
            resp1 = post_aa_reassign(
                user_id=member.id,
                default_user=default_user,
                data={"need_updated_risk_factors": True},
            )
            ca_after_call_1 = member.care_coordinators[0]
            resp2 = post_aa_reassign(
                user_id=member.id,
                default_user=default_user,
                data={"need_updated_risk_factors": True},
            )
            ca_after_call_2 = member.care_coordinators[0]

        # here we expect both hits to return 200, but only one reassignment
        assert resp1.status_code == 200
        assert resp1.json.get("message") is None
        assert resp2.status_code == 200
        assert (
            resp2.json.get("message")
            == "CA MemberPractitionerAssociation created within last 6 seconds. Skipping Advocate Assignment Reassign."
        )

        # ca assigned should only change first time
        assert original_ca != ca_after_call_1
        assert ca_after_call_1 == ca_after_call_2


class TestAdvocateAssignmentResourceMultitrack:
    url_prefix = "/api/v1/advocate-assignment/reassign"

    def test_advocate_assignment_resource_multitrack__true(
        self, client, api_helpers, default_user, factories
    ):
        # Given a user with multiple tracks and back_to_back_assessments True
        member = factories.EnterpriseUserFactory.create()
        original_ca = member.care_coordinators[0]

        factories.MemberTrackFactory.create(
            name=TrackName.PARENTING_AND_PEDIATRICS,
            user=member,
        )
        factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=member)

        new_practitioner = factories.PractitionerUserFactory.create()
        factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=new_practitioner
        )

        # When
        resp = client.post(
            f"{self.url_prefix}/{member.id}",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({"back_to_back_assessments": True}),
        )

        # Then CA is reassigned
        assert resp.status_code == 200
        assert api_helpers.load_json(resp)["success"] is True

        # Check that change in persistent in db
        db.session.expire(member)
        new_ca = member.care_coordinators[0]

        assert original_ca != new_ca
        assert new_ca == new_practitioner

    def test_advocate_assignment_resource_multitrack__false_reassign_ca(
        self, client, api_helpers, default_user, factories, risk_flags
    ):
        # Given a user with one track and back_to_back_assessments False
        member = factories.EnterpriseUserFactory.create()
        original_ca = member.care_coordinators[0]

        new_practitioner = factories.PractitionerUserFactory.create()
        factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=new_practitioner
        )

        # When
        resp = client.post(
            f"{self.url_prefix}/{member.id}",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({"back_to_back_assessments": False}),
        )
        # Then
        assert resp.status_code == 200
        assert api_helpers.load_json(resp)["success"] is True

        # Check that change in persistent in db
        db.session.expire(member)
        new_ca = member.care_coordinators[0]

        assert original_ca != new_ca
        assert new_ca == new_practitioner

    @patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.replace_care_coordinator_for_member"
    )
    def test_advocate_assignment_resource_multitrack__false_dont_reassign_ca(
        self,
        replace_care_coordinator_for_member_mock,
        client,
        api_helpers,
        default_user,
        factories,
    ):
        # Given a user with multiple tracks, a CA, and back_to_back_assessments False
        member = factories.EnterpriseUserFactory.create()
        original_ca = member.care_coordinators[0]

        factories.MemberTrackFactory.create(
            name=TrackName.PARENTING_AND_PEDIATRICS,
            user=member,
        )
        factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=member)

        new_practitioner = factories.PractitionerUserFactory.create()
        factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=new_practitioner
        )

        # When
        resp = client.post(
            f"{self.url_prefix}/{member.id}",
            headers=api_helpers.json_headers(default_user),
            data=api_helpers.json_data({"back_to_back_assessments": False}),
        )

        # Then CA does not change
        assert resp.status_code == 200
        assert api_helpers.load_json(resp)["success"] is True

        # Check that change in persistent in db
        db.session.expire(member)
        new_ca = member.care_coordinators[0]

        assert original_ca == new_ca
        assert new_ca != new_practitioner

        # and replace_care_coordinator_for_member not called
        replace_care_coordinator_for_member_mock.assert_not_called()
