import datetime
import json
from unittest.mock import ANY

from faker import Faker

from common.health_profile.health_profile_service_models import Modifier
from health.services.health_profile_service import HealthProfileService

fake = Faker()


class TestHealthProfileFreeTextField:
    def test_free_text_field_too_long(self, default_user, client, api_helpers):
        """Test validation function for free text fields limiting length, negative case."""
        long_text = fake.pystr(min_chars=1001, max_chars=1100)
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps({"medications_current": long_text}),
        )
        assert res.status_code == 400
        assert "errors" in res.json
        assert {
            "status": 400,
            "title": "Bad Request",
            "field": "medications_current",
            "detail": "Please put less than 1000 characters in the free text field.",
        } in res.json["errors"]

    def test_free_text_field_saves_normally(self, default_user, client, api_helpers):
        """Test validation function for free text fields limiting length, positive case."""
        short_text = fake.text(max_nb_chars=200)
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps({"medications_current": short_text}),
        )
        assert res.status_code == 200

    def test_999_characters_in_three_fields(self, default_user, client, api_helpers):
        """1000 character limit per field doesn't mean 1000 character limit overall."""
        just_below_the_limit_text = fake.pystr(min_chars=999, max_chars=999)
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(
                {
                    "medications_allergies": just_below_the_limit_text,
                    "medications_current": just_below_the_limit_text,
                    "medications_past": just_below_the_limit_text,
                }
            ),
        )
        assert res.status_code == 200


class TestPutHealthProfile:
    def test_can_add_meaningless_value(self, client, api_helpers, default_user):
        data = {"foo": "bar"}
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert res.status_code == 200

    def test_birthday_in_past(self, client, api_helpers, default_user):
        data = {"birthday": "1970-01-01T00:00:00"}
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert res.status_code == 200
        assert res.json["birthday"] == "1970-01-01T00:00:00"

    def test_birthday_in_future(self, client, api_helpers, default_user):
        data = {"birthday": "2070-01-01T00:00:00"}
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert res.status_code == 400

    def test_user_created_with_bad_due_date(
        self, client, api_helpers, default_user, empty_health_profile
    ):
        """Test for covering data when the FE used to send the due_date in the display format."""
        empty_health_profile.update(
            {"due_date": "09/02/2023", "birthday": "1990-01-01"}
        )
        data = empty_health_profile
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert res.status_code == 200
        assert res.json["due_date"] == "2023-09-02"

    def test_valid_data(self, client, api_helpers, default_user, empty_health_profile):
        empty_health_profile["birthday"] = "1970-01-01"
        data = empty_health_profile
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert res.json == data
        assert res.status_code == 200

    def test_invalid_json(self, client, api_helpers, default_user):
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data='{"adasdasd',
        )
        assert res.status_code == 400

    def test_overwrite_health_profile(
        self, client, api_helpers, default_user, empty_health_profile
    ):
        expected_health_profile = {
            "due_date": ANY,
            "children": [{"id": ANY, "name": ANY, "birthday": ANY}],
            "child_auto_added_at": ANY,
            "fertility_treatment_status": ANY,
        }
        initial_profile = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert initial_profile.json == expected_health_profile

        # generate a new different health profile
        empty_health_profile["children"] = [
            {
                "name": "Albert",
                "birthday": "2007-12-12T00:00:00",
                "gender": "male",
                "sex_at_birth": "female",
            },
            {
                "name": "Belle",
                "birthday": "2008-12-12T00:00:00",
                "gender": "female",
                "sex_at_birth": "female",
            },
        ]
        new_profile = empty_health_profile
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(new_profile),
        )
        new_profile_children = new_profile["children"]
        for idx in range(len(new_profile_children)):
            new_profile_children[idx]["id"] = ANY
        assert res.json == new_profile
        assert res.json != initial_profile.json

    def test_update_biological_sex(
        self,
        client,
        api_helpers,
        default_user,
        empty_health_profile,
        patch_braze_send_event,
    ):
        empty_health_profile["sex_at_birth"] = "Female"
        data = empty_health_profile
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert res.json == data
        assert res.status_code == 200
        patch_braze_send_event.assert_called_once_with(
            user=default_user,
            event_name="biological_sex",
            user_attributes={"biological_sex": "Female"},
        )

    def test_update_biological_sex__no_change(
        self,
        client,
        api_helpers,
        default_user,
        empty_health_profile,
        patch_braze_send_event,
    ):
        default_user.health_profile.json["sex_at_birth"] = "Female"
        empty_health_profile["sex_at_birth"] = "Female"
        data = empty_health_profile
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert res.json == data
        assert res.status_code == 200
        patch_braze_send_event.assert_not_called()

    def test_update_fertility_treatment_status(
        self,
        client,
        api_helpers,
        default_user,
        empty_health_profile,
    ):
        empty_health_profile["fertility_treatment_status"] = "preconception"
        data = empty_health_profile
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert res.json == data
        assert res.status_code == 200
        assert (
            HealthProfileService(default_user).get_fertility_treatment_status()
            == "preconception"
        )

    def test_update_due_date_triggers_hps_call(
        self,
        client,
        api_helpers,
        default_user,
        empty_health_profile,
        mock_health_profile_service,
    ):
        # get old due date
        mock_health_profile_service.get_fertility_treatment_status.return_value = None
        initial_profile = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        old_due_date = initial_profile.json["due_date"]

        # update to new due date
        new_due_date = datetime.date.fromisoformat(old_due_date) + datetime.timedelta(
            days=10
        )
        empty_health_profile["due_date"] = new_due_date.isoformat()
        data = empty_health_profile
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert res.json == data
        assert res.status_code == 200

        # verify call to HPS happened
        modifier = Modifier(
            id=default_user.id,
            name=default_user.full_name,
            role="member",
        )
        mock_health_profile_service.update_due_date_in_hps.assert_called_once_with(
            new_due_date, modifier
        )

        # verify due date is updated in mono
        updated_profile = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert updated_profile.json["due_date"] == new_due_date.isoformat()

    def test_no_hps_call_when_no_due_date_update(
        self,
        client,
        api_helpers,
        default_user,
        empty_health_profile,
        mock_health_profile_service,
    ):
        # get existing due date
        mock_health_profile_service.get_fertility_treatment_status.return_value = None
        initial_profile = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        existing_due_date = initial_profile.json["due_date"]

        # no due date update
        empty_health_profile["height"] = 64
        empty_health_profile["due_date"] = existing_due_date
        data = empty_health_profile
        res = client.put(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
            data=json.dumps(data),
        )
        assert res.json == data
        assert res.status_code == 200

        # verify no call to HPS
        mock_health_profile_service.update_due_date_in_hps.assert_not_called()

        # verify due date is not updated in mono
        updated_profile = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert updated_profile.json["due_date"] == existing_due_date
