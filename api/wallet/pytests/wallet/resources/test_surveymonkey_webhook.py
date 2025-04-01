from unittest.mock import patch

import pytest

from wallet.resources.surveymonkey_webhook import _get_subject_and_text


@pytest.mark.parametrize(
    argnames="survey_title, member_id_hash, survey_url, expected_subject, expected_text, expected_html",
    argvalues=[
        (
            "Test_Title",
            "ABC123",
            "fake.com",
            "Test_Title just completed a survey!",
            "Member Hash Id: ABC123\nAnalyze Survey URL: fake.com",
            "<p>Member Hash Id: ABC123</p>\n<a href=fake.com>Analyze Survey URL</a>",
        ),
        (
            None,
            "ABC123",
            "fake.com",
            "Survey Completed",
            "Member Hash Id: ABC123\nAnalyze Survey URL: fake.com",
            "<p>Member Hash Id: ABC123</p>\n<a href=fake.com>Analyze Survey URL</a>",
        ),
        (
            "Test_Title",
            None,
            "fake.com",
            "Test_Title just completed a survey!",
            "Analyze Survey URL: fake.com",
            "<a href=fake.com>Analyze Survey URL</a>",
        ),
        (
            "Test_Title",
            "ABC123",
            None,
            "Test_Title just completed a survey!",
            "Member Hash Id: ABC123\n",
            "<p>Member Hash Id: ABC123</p>\n",
        ),
        (
            None,
            None,
            None,
            "Survey Completed",
            "Webhook Error - Please review logs",
            "<p>Webhook Error - Please review logs</p>",
        ),
    ],
)
def test_get_subject_and_text(
    survey_title,
    member_id_hash,
    survey_url,
    expected_subject,
    expected_text,
    expected_html,
):
    subject, text, html = _get_subject_and_text(
        survey_title, member_id_hash, survey_url
    )
    assert subject == expected_subject
    assert text == expected_text
    assert html == expected_html


headers = {"Sm-Signature": "fake_key"}
mock_post_data = {
    "name": "My Webhook",
    "object_type": "response",
    "object_id": "123456",
    "resources": {
        "collector_id": "123456789",
        "survey_id": "123456789",
        "user_id": "123456789",
    },
}


@patch("utils.slack_v2._notify_slack_channel")
class TestSurveyMonkeyWebhook:
    @patch("redis.StrictRedis.get")
    def test_survey_monkey_webhook_successful(self, mock_redis_get, slack_mail, client):
        data = {"wallet_survey_title:123456789": "Survey Title"}

        def get(key):
            return data[key]

        mock_redis_get.side_effect = get
        with patch(
            "wallet.resources.surveymonkey_webhook.compare_signatures",
            return_value=True,
        ):
            with patch(
                "utils.survey_monkey.get_from_survey_monkey"
            ) as survey_monkey_return:
                survey_monkey_return.side_effect = [
                    {
                        "survey_id": "123456",
                        "custom_variables": {"member_id_hash": "abc123"},
                    }
                ]
                response = client.post(
                    "/api/v1/vendor/surveymonkey/survey-completed-webhook",
                    json=mock_post_data,
                    headers=headers,
                )
        assert mock_redis_get.called
        assert survey_monkey_return.called
        assert slack_mail.called
        assert response.status_code == 200

    @patch("redis.StrictRedis.get")
    def test_survey_monkey_webhook_no_data(self, mock_redis_get, slack_mail, client):
        data = {"wallet_survey_title:123456789": "Survey Title"}

        def get(key):
            return data[key]

        mock_redis_get.side_effect = get
        with patch(
            "wallet.resources.surveymonkey_webhook.compare_signatures",
            return_value=True,
        ):
            with patch(
                "utils.survey_monkey.get_from_survey_monkey"
            ) as survey_monkey_return:
                survey_monkey_return.side_effect = [
                    {
                        "survey_id": "123456",
                        "custom_variables": {"member_id_hash": "abc123"},
                    }
                ]
                response = client.post(
                    "/api/v1/vendor/surveymonkey/survey-completed-webhook",
                    json={},
                    headers=headers,
                )
        assert mock_redis_get.call_count == 0
        assert survey_monkey_return.call_count == 0
        assert slack_mail.called
        assert response.status_code == 400

    @patch("redis.StrictRedis.get")
    def test_survey_monkey_webhook_not_authenticated(
        self, mock_redis_get, slack_mail, client
    ):
        data = {"wallet_survey_title:123456789": "Survey Title"}

        def get(key):
            return data[key]

        mock_redis_get.side_effect = get
        with patch(
            "wallet.resources.surveymonkey_webhook.compare_signatures",
            return_value=False,
        ):
            with patch(
                "utils.survey_monkey.get_from_survey_monkey"
            ) as survey_monkey_return:
                survey_monkey_return.side_effect = [
                    {
                        "survey_id": "123456",
                        "custom_variables": {"member_id_hash": "abc123"},
                    }
                ]
                response = client.post(
                    "/api/v1/vendor/surveymonkey/survey-completed-webhook",
                    json={},
                    headers=headers,
                )
        assert mock_redis_get.call_count == 0
        assert survey_monkey_return.call_count == 0
        assert slack_mail.call_count == 0
        assert response.status_code == 401

    @patch("redis.StrictRedis.get")
    def test_survey_monkey_webhook_no_survey_data(
        self, mock_redis_get, slack_mail, client
    ):
        data = {"wallet_survey_title:123456789": "Survey Title"}

        def get(key):
            return data[key]

        mock_redis_get.side_effect = get
        with patch(
            "wallet.resources.surveymonkey_webhook.compare_signatures",
            return_value=True,
        ):
            with patch(
                "utils.survey_monkey.get_from_survey_monkey"
            ) as survey_monkey_survey:
                survey_monkey_survey.return_value = []
                response = client.post(
                    "/api/v1/vendor/surveymonkey/survey-completed-webhook",
                    json=mock_post_data,
                    headers=headers,
                )
        assert mock_redis_get.called
        assert survey_monkey_survey.called
        assert slack_mail.called
        assert response.status_code == 400
