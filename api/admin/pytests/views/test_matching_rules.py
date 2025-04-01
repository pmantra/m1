import json

import pytest

from admin.blueprints.matching_rules import MatchingRuleEndpointMessage
from care_advocates.models.matching_rules import MatchingRuleSet
from pytests.factories import (
    AssignableAdvocateFactory,
    EnterpriseUserFactory,
    PractitionerUserFactory,
    StateFactory,
    VerticalFactory,
    VerticalInStateMatchStateFactory,
)


class TestAssignableAdvocatesPostEndpoint:
    def test_valid_user(self, commit_expire_behavior, admin_client):
        practitioner = PractitionerUserFactory.create()
        assignable_advocate = AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        body = {
            "id": assignable_advocate.practitioner_id,
            "matching_rules": [
                {
                    "all": False,
                    "entity": "module",
                    "id": 12,
                    "identifiers": ["2"],
                    "type": "include",
                },
            ],
        }

        res = admin_client.post(
            f"/admin/assignable-advocates/{assignable_advocate.practitioner_id}/matching-rule-set",
            json=body,
            headers={"Content-Type": "application/json"},
        )

        assert res.status_code == 200

    def test_aa_does_not_exist(self, admin_client):
        practitioner = PractitionerUserFactory.create()
        body = {
            "id": practitioner.id,
            "matching_rules": [
                {
                    "all": False,
                    "entity": "module",
                    "id": 12,
                    "identifiers": ["2"],
                    "type": "include",
                },
            ],
        }

        res = admin_client.post(
            f"/admin/assignable-advocates/{practitioner.id}/matching-rule-set",
            json=body,
            headers={"Content-Type": "application/json"},
        )

        assert res.status_code == 404
        assert (
            res.json["errors"]
            == MatchingRuleEndpointMessage.MISSING_ASSIGNABLE_ADVOCATE
        )


class TestAssignableAdvocatesPutEndpoint:
    def test_valid_user(self, admin_client):
        practitioner = PractitionerUserFactory.create()
        aa = AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        body = {
            "matching_rules": [
                {
                    "all": True,
                    "entity": "country",
                    "id": 9,
                    "identifiers": [],
                    "type": "include",
                },
            ],
        }
        mrs = MatchingRuleSet(assignable_advocate=aa)
        mrs.id = 1
        MatchingRuleSetResource_url = f"/admin/assignable-advocates/{aa.practitioner_id}/matching-rule-set/{mrs.id}"

        resp = admin_client.put(
            MatchingRuleSetResource_url,
            json=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

    def test_no_matching_rule_set(self, admin_client):
        practitioner = PractitionerUserFactory.create()
        aa = AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        body = {
            "matching_rules": [
                {
                    "all": True,
                    "entity": "country",
                    "id": 9,
                    "identifiers": [],
                    "type": "include",
                },
            ],
        }
        set_id = 1
        MatchingRuleSetResource_url = f"/admin/assignable-advocates/{aa.practitioner_id}/matching-rule-set/{set_id}"

        resp = admin_client.put(
            MatchingRuleSetResource_url,
            json=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 404
        assert resp.json["errors"] == MatchingRuleEndpointMessage.MISSING_MRS

    def test_missing_fields(self, admin_client):
        practitioner = PractitionerUserFactory.create()
        aa = AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        body = {
            "matching_rules": [
                {
                    "all": False,
                    "entity": "country",
                    "id": 9,
                    "identifiers": [],
                    "type": "include",
                },
            ],
        }
        mrs = MatchingRuleSet(assignable_advocate=aa)
        mrs.id = 1
        MatchingRuleSetResource_url = f"/admin/assignable-advocates/{aa.practitioner_id}/matching-rule-set/{mrs.id}"

        resp = admin_client.put(  # type: ignore[union-attr] # Item "None" of "Optional[FlaskClient[Response]]" has no attribute "put"
            MatchingRuleSetResource_url,
            json=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json["errors"] == MatchingRuleEndpointMessage.MISSING_FIELDS


class TestAssignableAdvocatesDeleteEndpoint:
    def test_delete_successful(self, admin_client):
        practitioner = PractitionerUserFactory.create()
        aa = AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        mrs = MatchingRuleSet(assignable_advocate=aa)
        mrs.id = 1
        MatchingRuleSetResource_url = f"/admin/assignable-advocates/{aa.practitioner_id}/matching-rule-set/{mrs.id}"

        resp = admin_client.delete(  # type: ignore[union-attr] # Item "None" of "Optional[FlaskClient[Response]]" has no attribute "delete"
            MatchingRuleSetResource_url,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

    def test_no_mrs_delete_failed(self, admin_client):
        practitioner = PractitionerUserFactory.create()
        aa = AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        MatchingRuleSetResource_url = (
            f"/admin/assignable-advocates/{aa.practitioner_id}/matching-rule-set/0"
        )

        resp = admin_client.delete(  # type: ignore[union-attr] # Item "None" of "Optional[FlaskClient[Response]]" has no attribute "delete"
            MatchingRuleSetResource_url,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json["errors"] == MatchingRuleEndpointMessage.MRS_DNE


@pytest.fixture
def states():
    return {
        "NY": StateFactory.create(name="New York", abbreviation="NY"),
        "NJ": StateFactory.create(name="New Jersey", abbreviation="NJ"),
        "CA": StateFactory.create(name="California", abbreviation="CA"),
        "WA": StateFactory.create(name="Washington", abbreviation="WA"),
    }


class TestInStateMatchAPI:
    def test_state_match_not_permissible_no_user(self, admin_client, states):
        vertical = VerticalFactory(filter_by_state=True)
        practitioner = PractitionerUserFactory(
            practitioner_profile__verticals=[vertical],
            practitioner_profile__certified_states=[states["NY"], states["NJ"]],
        )
        product = practitioner.products[0]
        no_user_fake_id = -1

        res = admin_client.get(
            f"/admin/practitionerprofile/state-match-not-permissible/?product_id={product.id}&user_id={no_user_fake_id}",
        )

        assert res.status_code == 400
        data = json.loads(res.data.decode("utf8"))
        assert data["error"] == "user not found"

    def test_state_match_not_permissible_no_product(self, admin_client, states):
        user = EnterpriseUserFactory(member_profile__state=states["NY"])
        no_product_fake_id = -1

        res = admin_client.get(
            f"/admin/practitionerprofile/state-match-not-permissible/?product_id={no_product_fake_id}&user_id={user.id}"
        )

        assert res.status_code == 400
        data = json.loads(res.data.decode("utf8"))
        assert data["error"] == "product not found"

    def test_in_state_match(self, admin_client, states):
        user = EnterpriseUserFactory(member_profile__state=states["NY"])
        vertical = VerticalFactory(filter_by_state=True)
        practitioner = PractitionerUserFactory(
            practitioner_profile__verticals=[vertical],
            practitioner_profile__certified_states=[states["NY"], states["NJ"]],
        )
        product = practitioner.products[0]

        res = admin_client.get(
            f"/admin/practitionerprofile/state-match-not-permissible/?product_id={product.id}&user_id={user.id}"
        )

        assert res.status_code == 200
        data = json.loads(res.data.decode("utf8"))
        assert data["state_match_not_permissible"] is False

    def test_state_match_not_permissible(self, admin_client, states):
        user = EnterpriseUserFactory(member_profile__state=states["NY"])
        vertical = VerticalFactory(
            filter_by_state=True,
        )
        VerticalInStateMatchStateFactory.create(
            state_id=states["NY"].id, vertical_id=vertical.id
        )
        practitioner = PractitionerUserFactory(
            practitioner_profile__verticals=[vertical],
            practitioner_profile__certified_states=[states["CA"], states["WA"]],
        )
        product = practitioner.products[0]

        res = admin_client.get(
            f"/admin/practitionerprofile/state-match-not-permissible/?product_id={product.id}&user_id={user.id}"
        )

        assert res.status_code == 200
        data = json.loads(res.data.decode("utf8"))
        assert data["state_match_not_permissible"] is True
