import datetime
from unittest.mock import MagicMock, Mock, patch

from braze.client import BrazeExportedUser, BrazeUserAttributes, utils
from braze.client.braze_client import BrazeEvent
from braze.client.utils import recover_braze_user, recover_braze_users


class TestCompareToBrazeProfile:
    def test_compare_to_braze_profile(self, mock_braze_user_profile):
        braze_user_profile = BrazeExportedUser.from_dict(mock_braze_user_profile)
        user_attributes = BrazeUserAttributes(
            external_id="123",
            attributes={
                "first_name": "Jane",
                "last_name": "Deer",  # this has changed, it's "Doe" in the braze_user_profile
                "email": "example@braze.com",
                "country": "US",
                "state": "NY",
            },
        )

        diff_attrs = utils.compare_to_braze_profile(
            user_attributes=user_attributes,
            braze_profile=braze_user_profile,
        )

        expected_diff_attrs = BrazeUserAttributes(
            external_id="123", attributes={"last_name": "Deer"}
        )

        assert diff_attrs == expected_diff_attrs

    def test_compare_to_braze_profile__no_diffs(self, mock_braze_user_profile):
        braze_user_profile = BrazeExportedUser.from_dict(mock_braze_user_profile)
        user_attributes = BrazeUserAttributes(
            external_id="123",
            attributes={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "example@braze.com",
                "country": "US",
                "state": "NY",
            },
        )

        diff_attrs = utils.compare_to_braze_profile(
            user_attributes=user_attributes,
            braze_profile=braze_user_profile,
        )

        assert diff_attrs is None

    def test_compare_to_braze_profile__non_matching_external_ids(
        self, mock_braze_user_profile
    ):
        braze_user_profile = BrazeExportedUser.from_dict(mock_braze_user_profile)
        user_attributes = BrazeUserAttributes(
            external_id="456",  # this does not match as the braze_user_profile's external_id is "123"
            attributes={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "example@braze.com",
                "country": "US",
                "state": "NY",
            },
        )

        diff_attrs = utils.compare_to_braze_profile(
            user_attributes=user_attributes,
            braze_profile=braze_user_profile,
        )

        assert diff_attrs is None


class TestRecoverBrazeUser:
    @patch("braze.client.utils.recover_braze_users")
    def test_recover_braze_user(self, mock_recover_braze_users):
        recover_braze_user(external_id="123")

        mock_recover_braze_users.assert_called_with(
            external_ids=["123"],
        )


class TestRecoverBrazeUsers:
    @patch("braze.client.utils.BrazeClient.track_users")
    @patch("braze.client.utils.build_user_attrs")
    @patch("braze.client.utils.BrazeClient.fetch_user")
    def test_recover_braze_users__no_braze_profile(
        self,
        mock_fetch_user,
        mock_build_user_attrs,
        mock_track_users,
        default_user,
    ):
        braze_user_attributes = BrazeUserAttributes(
            external_id=default_user.esp_id,
            attributes=dict(
                created_at=datetime.datetime(2020, 2, 1),
                email="test@email.com",
                first_name="FIRST",
                state="NY",
                onboarding_state="assessments",
            ),
        )
        mock_build_user_attrs.return_value = braze_user_attributes

        mock_fetch_user.return_value = None

        recover_braze_users(external_ids=[default_user.esp_id])

        mock_track_users.assert_called_once_with(
            user_attributes=[braze_user_attributes]
        )

    @patch("braze.client.utils.BrazeClient.track_users")
    @patch("braze.client.utils.build_user_attrs")
    @patch("braze.client.utils.BrazeClient.fetch_user")
    def test_recover_users__no_attributes_to_update(
        self,
        mock_fetch_user,
        mock_build_user_attrs,
        mock_track_users,
        default_user,
    ):
        braze_user_attributes = BrazeUserAttributes(
            external_id=default_user.esp_id,
            attributes=dict(
                created_at=datetime.datetime(2020, 2, 1),
                email="test@email.com",
                first_name="FIRST",
                state="NY",
                onboarding_state="assessments",
            ),
        )
        mock_build_user_attrs.return_value = braze_user_attributes

        braze_profile = BrazeExportedUser(
            external_id=default_user.esp_id,
            created_at="2020-02-01T00:00:00Z",
            email="test@email.com",
            braze_id="BRAZE_ID",
            first_name="FIRST",
            email_subscribe="subscribed",
            user_aliases=[],
            custom_attributes=dict(
                state="NY",
                onboarding_state="assessments",
            ),
        )
        mock_fetch_user.return_value = braze_profile

        recover_braze_users(external_ids=[default_user.esp_id])

        mock_track_users.assert_not_called()

    @patch("braze.client.utils.BrazeClient.track_users")
    @patch("braze.client.utils.build_user_attrs")
    @patch("braze.client.utils.BrazeClient.fetch_user")
    def test_recover_users(
        self,
        mock_fetch_user,
        mock_build_user_attrs,
        mock_track_users,
        default_user,
    ):
        braze_user_attributes = BrazeUserAttributes(
            external_id=default_user.esp_id,
            attributes=dict(
                created_at=datetime.datetime(2020, 2, 1),
                email="test@email.com",
                first_name="FIRST",
                state="HI",
                onboarding_state="assessments",
            ),
        )
        mock_build_user_attrs.return_value = braze_user_attributes

        braze_profile = BrazeExportedUser(
            external_id=default_user.esp_id,
            created_at="2020-02-01T00:00:00Z",
            email="test@email.com",
            braze_id="BRAZE_ID",
            first_name="FIRST",
            email_subscribe="subscribed",
            user_aliases=[],
            custom_attributes=dict(
                state="NY",
                onboarding_state="assessments",
            ),
        )
        mock_fetch_user.return_value = braze_profile

        recover_braze_users(external_ids=[default_user.esp_id])

        mock_track_users.assert_called_once_with(
            user_attributes=[
                BrazeUserAttributes(
                    external_id=default_user.esp_id, attributes=dict(state="HI")
                )
            ]
        )


class TestRQDelayWithFeatureFlag:
    @patch("braze.client.utils.feature_flags.bool_variation")
    @patch("braze.client.utils.log.warning")
    @patch("braze.client.utils.os.environ.get")
    def test_with_feature_flag_enabled(
        self, mock_os_env, mock_log, mock_bool_variation
    ):
        mock_bool_variation.return_value = True
        mock_func = Mock()

        mock_os_env.return_value = False

        utils.rq_delay_with_feature_flag(mock_func, "arg1", kwarg1="value1")

        mock_bool_variation.assert_called_once_with(
            flag_key="kill-switch-braze-api-requests", default=True
        )
        mock_func.delay.assert_called_once_with("arg1", kwarg1="value1")
        mock_log.assert_not_called()

    @patch("braze.client.utils.feature_flags.bool_variation")
    @patch("braze.client.utils.log.warning")
    @patch("braze.client.utils.os.environ.get")
    def test_with_feature_flag_disabled(
        self, mock_os_env, mock_log, mock_bool_variation
    ):
        mock_bool_variation.return_value = False
        mock_func = Mock()

        mock_os_env.return_value = False

        utils.rq_delay_with_feature_flag(mock_func, "arg1", kwarg1="value1")

        mock_bool_variation.assert_called_once_with(
            flag_key="kill-switch-braze-api-requests", default=True
        )
        mock_func.delay.assert_not_called()
        mock_log.assert_called_once()

    @patch("braze.client.utils.feature_flags.bool_variation")
    @patch("braze.client.utils.log.warning")
    @patch("os.environ", {"TESTING": "True"})
    def test_with_feature_flag_testing_environment(self, mock_log, mock_bool_variation):
        mock_func = Mock()

        utils.rq_delay_with_feature_flag(mock_func, "arg1", kwarg1="value1")

        mock_bool_variation.assert_called_once_with(
            flag_key="kill-switch-braze-api-requests", default=False
        )
        mock_log.assert_not_called()


class TestBrazeSendEvent:
    @patch("braze.client.BrazeClient.track_user")
    @patch("braze.client.utils.log.info")
    def test_send_braze_event_success(self, mock_logger_info, mock_track_user):
        external_id = "test_id"
        event_name = "test_event"
        properties = {"prop1": "value1"}

        mock_response = MagicMock()
        mock_response.ok = True
        mock_track_user.return_value = mock_response

        utils.send_braze_event(
            external_id=external_id, event_name=event_name, properties=properties
        )

        mock_track_user.assert_called_with(
            events=[
                BrazeEvent(
                    external_id=external_id, name=event_name, properties=properties
                )
            ]
        )
        mock_logger_info.assert_called_with(
            "Successfully sent event to Braze",
            external_id=external_id,
            event_name=event_name,
            properties=properties,
        )

    @patch("braze.client.BrazeClient.track_user")
    @patch("braze.client.utils.log.error")
    def test_send_braze_event_failure(self, mock_logger_error, mock_track_user):
        external_id = "test_id"
        event_name = "test_event"
        properties = {"prop1": "value1"}

        mock_response = MagicMock()
        mock_response.ok = False
        mock_track_user.return_value = mock_response

        utils.send_braze_event(
            external_id=external_id, event_name=event_name, properties=properties
        )

        mock_track_user.assert_called_with(
            events=[
                BrazeEvent(
                    external_id=external_id, name=event_name, properties=properties
                )
            ]
        )
        mock_logger_error.assert_called_with(
            "Failed to send event to Braze",
            external_id=external_id,
            event_name=event_name,
            properties=properties,
        )
