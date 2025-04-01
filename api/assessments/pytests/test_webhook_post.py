from datetime import datetime, timedelta, timezone
from unittest.mock import ANY, Mock, patch

import pytest

from assessments.models.hdc_models import HdcExportEventType, HdcExportItem
from assessments.services.hdc_assessment_completion import (
    HdcAssessmentCompletionHandler,
)
from braze.client.braze_client import format_dt
from braze.client.constants import USER_TRACK_ENDPOINT
from health.models.risk_enums import RiskFlagName
from health.services.health_profile_service import HealthProfileService
from incentives.models.incentive_fulfillment import (
    IncentiveAction,
    IncentiveFulfillment,
    IncentiveStatus,
)


@pytest.fixture
def mock_hps_client():
    patcher = patch("health.services.hps_export_utils.HealthProfileServiceClient")
    mock_hps_class = patcher.start()
    mock_client = mock_hps_class.return_value
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    mock_response.ok = True

    mock_client._make_request = Mock(return_value=mock_response)
    mock_client.get_pregnancy.return_value = []
    mock_client.put_pregnancy.return_value = None

    yield mock_client

    patcher.stop()


@pytest.fixture
def webhook_call(client, default_user, api_helpers, mock_hps_client):
    def call_the_hdc_webhook(user, data):
        res = client.post(
            "/api/v1/webhook/health_data_collection",
            headers={
                **api_helpers.standard_headers(user),
                **api_helpers.json_headers(),
            },
            data=api_helpers.json_data(data),
        )
        return res

    return call_the_hdc_webhook


@pytest.fixture()
def braze_make_request_mock():
    old = HdcAssessmentCompletionHandler.PROCESS_ASYNC
    HdcAssessmentCompletionHandler.PROCESS_ASYNC = False
    with patch("braze.client.BrazeClient._make_request") as mock_request:
        yield mock_request
    HdcAssessmentCompletionHandler.PROCESS_ASYNC = old


@pytest.fixture()
def process_completion_mock():
    old = HdcAssessmentCompletionHandler.PROCESS_ASYNC
    HdcAssessmentCompletionHandler.PROCESS_ASYNC = False
    with patch.object(
        HdcAssessmentCompletionHandler, "process_completion"
    ) as mock_request:
        yield mock_request
    HdcAssessmentCompletionHandler.PROCESS_ASYNC = old


def generate_due_date(weeks_from_now):
    """Helper function to generate due date strings."""
    today = datetime.now(timezone.utc)
    due_date = today + timedelta(days=(280 - weeks_from_now * 7))
    return due_date.strftime("%Y-%m-%d %H:%M:%S+00:00")


class TestHDCWebhook:
    def test_invalid_event(self, default_user, webhook_call):
        res = webhook_call(default_user, None)
        assert res.status_code == 400

    def test_health_profile_event(self, default_user, webhook_call):
        data = {
            "event_type": "health_profile",
            "label": "test_event",
            "value": "a fake status",
        }
        res = webhook_call(default_user, data)
        assert res.status_code == 200
        assert "test_event" in default_user.health_profile.json
        assert default_user.health_profile.json["test_event"] == "a fake status"

    def test_expected_health_profile_value(self, default_user, webhook_call):
        data = {
            "event_type": "health_profile",
            "label": "height",
            "value": 64,
        }
        res = webhook_call(default_user, data)
        assert res.status_code == 200
        assert default_user.health_profile.height == 64

    def test_obesity_calc_event_overweight(
        self, default_user, webhook_call, risk_flags
    ):
        data = {
            "event_type": "risk_flag",
            "label": "obesity_calc",
            "value": {"height": 64, "weight": 150},
        }
        res = webhook_call(default_user, data)
        assert res.status_code == 200
        flag_names = [flag.name for flag in default_user.current_risk_flags()]
        assert "Overweight" in flag_names

    def test_obesity_calc_event_obesity(self, default_user, webhook_call, risk_flags):
        data = {
            "event_type": "risk_flag",
            "label": "obesity_calc",
            "value": {"height": 64, "weight": 200},
        }
        res = webhook_call(default_user, data)
        assert res.status_code == 200
        flag_names = [flag.name for flag in default_user.current_risk_flags()]
        assert "Obesity" in flag_names

    def test_first_trimester_due_date(self, default_user, webhook_call, risk_flags):
        data = {
            "event_type": "health_profile",
            "label": "due_date",
            "value": generate_due_date(5),
        }
        with patch("maven.feature_flags.bool_variation", return_value=True):
            res = webhook_call(default_user, data)
            assert res.status_code == 200
            flag_names = [flag.name for flag in default_user.current_risk_flags()]
            assert RiskFlagName.FIRST_TRIMESTER in flag_names

    def test_second_trimester_due_date(self, default_user, webhook_call, risk_flags):
        data = {
            "event_type": "health_profile",
            "label": "due_date",
            "value": generate_due_date(20),
        }
        with patch("maven.feature_flags.bool_variation", return_value=True):
            res = webhook_call(default_user, data)
            assert res.status_code == 200
            flag_names = [flag.name for flag in default_user.current_risk_flags()]
            assert RiskFlagName.SECOND_TRIMESTER in flag_names

    def test_early_third_trimester_due_date(
        self, default_user, webhook_call, risk_flags
    ):
        data = {
            "event_type": "health_profile",
            "label": "due_date",
            "value": generate_due_date(30),
        }
        with patch("maven.feature_flags.bool_variation", return_value=True):
            res = webhook_call(default_user, data)
            assert res.status_code == 200
            flag_names = [flag.name for flag in default_user.current_risk_flags()]
            assert RiskFlagName.EARLY_THIRD_TRIMESTER in flag_names

    def test_late_third_trimester_due_date(
        self, default_user, webhook_call, risk_flags
    ):
        data = {
            "event_type": "health_profile",
            "label": "due_date",
            "value": generate_due_date(36),
        }
        with patch("maven.feature_flags.bool_variation", return_value=True):
            res = webhook_call(default_user, data)
            assert res.status_code == 200
            flag_names = [flag.name for flag in default_user.current_risk_flags()]
            assert RiskFlagName.LATE_THIRD_TRIMESTER in flag_names

    def test_obesity_calc_event_false(self, default_user, webhook_call, risk_flags):
        data = {
            "event_type": "risk_flag",
            "label": "obesity_calc",
            "value": {"height": 64, "weight": 125},
        }
        res = webhook_call(default_user, data)
        assert res.status_code == 200
        assert default_user.current_risk_flags() == []

    def test_user_flag_event(self, default_user, webhook_call, risk_flags):
        res = webhook_call(
            default_user,
            {
                "event_type": "risk_flag",
                "label": "Alcohol use",
            },
        )
        assert res.status_code == 200

    @patch("assessments.resources.hdc_webhook.import_hdc_payload_to_fhir")
    def test_fhir_event(self, mock_task, default_user, webhook_call):
        res = webhook_call(
            default_user,
            {"event_type": "fhir", "label": "Condition", "value": "bar"},
        )
        mock_task.delay.assert_called_once_with(
            default_user.id,
            "Condition",
            ANY,
            service_ns="health",
            team_ns="mpractice_core",
        )
        assert res.status_code == 200

    def test_expected_health_profile_first_time_mom_value_true(
        self, default_user, webhook_call
    ):
        data = {
            "event_type": "health_profile",
            "label": "first_time_mom",
            "value": "yes",
        }
        res = webhook_call(default_user, data)
        assert res.status_code == 200
        assert default_user.health_profile.first_time_mom is True

    def test_expected_health_profile_first_time_mom_value_false(
        self, default_user, webhook_call
    ):
        data = {
            "event_type": "health_profile",
            "label": "first_time_mom",
            "value": "no",
        }
        res = webhook_call(default_user, data)
        assert res.status_code == 200
        assert default_user.health_profile.first_time_mom is False

    def test_expected_fertility_treatment_status_update(
        self, default_user, webhook_call
    ):
        data = {
            "event_type": "health_profile",
            "label": "fertility_treatment_status_update",
            "value": "undergoing_iui",
        }
        hp_service = HealthProfileService(default_user)
        with patch(
            "health.services.health_profile_change_notify_service.send_braze_fertility_status"
        ) as braze_call:
            res = webhook_call(default_user, data)
            assert res.status_code == 200
            assert hp_service.get_fertility_treatment_status() == "undergoing_iui"
            assert braze_call.delay.called is True
            call_args = braze_call.delay.call_args[0]
            assert call_args[0] == default_user.id
            assert call_args[1] == "undergoing_iui"

    def test_add_child_and_member_track_called(self, default_user, webhook_call):
        data = {
            "event_type": "health_profile",
            "label": "baby_dob",
            "value": "2020-01-02",
        }
        hp_service = HealthProfileService(default_user)
        hp = hp_service._health_profile
        with patch(
            "health.services.health_profile_change_notify_service.tracks.on_health_profile_update"
        ) as call:
            res = webhook_call(default_user, data)
            assert res.status_code == 200
            assert len(hp.children) == 2  # default_user already has 1 child
            assert hp.children[1]["birthday"] == "2020-01-02"
            assert call.called is True
            assert call.call_args[1]["user"].id == default_user.id

    def test_handle_assessment_completion(
        self, default_user, webhook_call, braze_make_request_mock
    ):
        user_esp_id = default_user.esp_id
        assessment_slug = "assessment-slug"
        date_completed_str = "2023-12-07 15:53:49.513076"

        # parsing for test assertion
        date_completed = datetime.fromisoformat(date_completed_str)

        data = {
            "event_type": "assessment_completion",
            "label": "",
            "value": {
                "assessments": [
                    {
                        "assessment_slug": assessment_slug,
                        "date_completed": format_dt(date_completed),
                    }
                ]
            },
        }

        res = webhook_call(default_user, data)
        assert res.status_code == 200

        assert braze_make_request_mock.called is True
        assert braze_make_request_mock.call_args[1] == {
            "data": {
                "events": [
                    {
                        "external_id": user_esp_id,
                        "name": f"{assessment_slug}-assessment",
                        "properties": None,
                        "time": format_dt(date_completed),
                    }
                ]
            },
            "endpoint": USER_TRACK_ENDPOINT,
        }


class TestHandleAssessmentCompletion:

    # When
    @pytest.mark.parametrize(
        argnames="missing_data", argvalues=["assessments", "assessment_slug", "all"]
    )
    def test_handle_assessment_completion__no_assessment_slug(
        self,
        missing_data,
        factories,
        process_completion_mock,
    ):
        # Given a call to to handle assessment with incomplete data
        user = factories.DefaultUserFactory()
        if missing_data == "assessments":
            assessments_data = {
                "not_assessments": [
                    {
                        "assessment_slug": "assessment_slug",
                        "date_completed": "2023-12-07 15:53:49.513076",
                    }
                ]
            }
        elif missing_data == "assessment_slug":
            assessments_data = {
                "assessments": [
                    {
                        "not_assessment_slug": "assessment_slug",
                        "date_completed": "2023-12-07 15:53:49.513076",
                    }
                ]
            }
        else:
            assessments_data = {}

        # When
        HdcAssessmentCompletionHandler(user).process_items(
            [
                HdcExportItem(
                    HdcExportEventType.ASSESSMENT_COMPLETION, "", assessments_data
                )
            ]
        )

        # Then, internal functions not called
        assert not process_completion_mock.called

    def test_handle_assessment_completion__with_assessment_slug(
        self, factories, braze_make_request_mock, session
    ):
        """
        Integration test to check offboarding completion incentive flow works
        """

        # Given a user eligible for an incentive, and an offboarding assessment slug for the user's track
        user = factories.EnterpriseUserNoTracksFactory()
        user.member_profile.country_code = "US"
        user_esp_id = user.esp_id
        country_code = user.member_profile.country_code
        track_name = "postpartum"
        member_track = factories.MemberTrackFactory(user=user, name=track_name)
        org = member_track.client_track.organization

        user.member_tracks.append(member_track)
        incentive_action = IncentiveAction.OFFBOARDING_ASSESSMENT

        # Configure incentives
        incentive = factories.IncentiveFactory.create()
        incentive_organization = factories.IncentiveOrganizationFactory.create(
            incentive=incentive,
            organization=org,
            action=incentive_action,
            track_name=track_name,
        )
        factories.IncentiveOrganizationCountryFactory.create(
            incentive_organization=incentive_organization,
            country_code=country_code,
        )

        # Prep request
        assessment_slug = "postpartum-offboarding"
        date_completed_str = "2023-12-07 15:53:49.513076"
        # parsing for test assertion
        date_completed = datetime.fromisoformat(date_completed_str)

        assessments_data = {
            "assessments": [
                {
                    "assessment_slug": assessment_slug,
                    "date_completed": date_completed_str,
                }
            ]
        }

        # When
        HdcAssessmentCompletionHandler(user).process_items(
            [
                HdcExportItem(
                    HdcExportEventType.ASSESSMENT_COMPLETION, "", assessments_data
                )
            ]
        )

        # Then, check incentive is earned
        incentive_fulfillment = (
            session.query(IncentiveFulfillment)
            .filter(
                IncentiveFulfillment.member_track_id == member_track.id,
                IncentiveFulfillment.incentivized_action
                == IncentiveAction.OFFBOARDING_ASSESSMENT,
            )
            .first()
        )
        assert incentive_fulfillment
        assert incentive_fulfillment.status == IncentiveStatus.EARNED
        assert incentive_fulfillment.date_earned

        assert braze_make_request_mock.called is True
        assert braze_make_request_mock.call_args[1] == {
            "data": {
                "events": [
                    {
                        "external_id": user_esp_id,
                        "name": f"{assessment_slug}-assessment",
                        "properties": None,
                        "time": format_dt(date_completed),
                    }
                ]
            },
            "endpoint": USER_TRACK_ENDPOINT,
        }
