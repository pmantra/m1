from __future__ import annotations

from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import ANY, MagicMock, Mock

import pytest
from maven.feature_flags import TestData
from redset.locks import LockTimeout
from zenpy import Zenpy
from zenpy.lib.api_objects import Comment as ZDComment
from zenpy.lib.api_objects import Identity as ZDIdentity
from zenpy.lib.api_objects import Organization as ZDOrganization
from zenpy.lib.api_objects import Ticket as ZDTicket
from zenpy.lib.api_objects import User as ZDUser
from zenpy.lib.exception import APIException as ZendeskAPIException

from messaging.services.zendesk import creds
from messaging.services.zendesk_client import (
    DEFAULT_ZENDESK_RETRY_WAIT_TIME,
    TICKET_SEARCH_RECURSION_LIMIT,
    CustomSession,
    ZendeskAPIEmailAlreadyExistsException,
    ZendeskClient,
    exception_related_to_email_already_exists,
    get_updated_ticket_search_default_lookback_seconds,
    handle_zendesk_rate_limit,
    warn_on_zendesk_rate_limit,
)
from models.tracks import TrackName
from utils.flag_groups import ZENDESK_V2_RECONCILIATION


@pytest.fixture()
def zendesk_client():
    class ZDTestableClient(ZendeskClient):
        def __init__(self):
            self.zenpy = MagicMock(spec_set=Zenpy(**creds))

    return ZDTestableClient()


class TestZendeskClient:
    _test_to_date = datetime(2021, 1, 7, 10, 0)
    _test_from_date = datetime(2021, 1, 7, 10, 0) - timedelta(
        seconds=get_updated_ticket_search_default_lookback_seconds(),
    )

    @mock.patch(
        "messaging.services.zendesk_client._FALLBACK_UPDATED_TICKET_SEARCH_LOOKBACK_SECONDS",
        1,
    )
    def test_get_updated_ticket_search_default_lookback_seconds(self):
        assert get_updated_ticket_search_default_lookback_seconds() == 1

    @mock.patch(
        "messaging.services.zendesk_client._FALLBACK_UPDATED_TICKET_SEARCH_LOOKBACK_SECONDS",
        1,
    )
    def test_get_updated_ticket_search_default_lookback_seconds_flag_control(
        self,
        ff_test_data: TestData,
    ):
        ff_test_data.update(
            ff_test_data.flag(
                ZENDESK_V2_RECONCILIATION.UPDATED_TICKET_SEARCH_LOOKBACK_SECONDS,
            ).value_for_all(123),
        )
        assert get_updated_ticket_search_default_lookback_seconds() == 123

    @pytest.mark.parametrize(
        ("lookback_seconds", "runaway_guard_seconds", "expected"),
        [
            (0, 0, 0),
            (100, 10, 10),
            (10, 100, 10),
            (10, 10, 10),
            (-10, 10, 0),
            (10, -10, 0),
        ],
    )
    def test_get_updated_ticket_search_default_lookback_seconds_runaway_guard(
        self,
        lookback_seconds,
        runaway_guard_seconds,
        expected,
    ):
        with mock.patch(
            "messaging.services.zendesk_client._FALLBACK_UPDATED_TICKET_SEARCH_LOOKBACK_SECONDS",
            lookback_seconds,
        ), mock.patch(
            "messaging.services.zendesk_client._UPDATED_TICKET_LOOKBACK_SECONDS_RUNAWAY_GUARD",
            runaway_guard_seconds,
        ):
            # Uses the runaway guard value
            assert get_updated_ticket_search_default_lookback_seconds() == expected

    def test_default_updated_ticket_search_window(self, zendesk_client):
        with mock.patch("messaging.services.zendesk_client.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = self._test_to_date
            from_date, to_date = zendesk_client.default_updated_ticket_search_window()

            assert from_date == self._test_from_date
            assert to_date == self._test_to_date

    def test_find_updated_ticket_ids_default_window(self, zendesk_client):
        zendesk_client.zenpy.search.return_value = []
        with mock.patch("messaging.services.zendesk_client.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = self._test_to_date

            zendesk_client.find_updated_ticket_ids()

            zendesk_client.zenpy.search.assert_called_with(
                ANY,
                type=ANY,
                updated_between=[
                    self._test_from_date,
                    self._test_to_date,
                ],
                tags=ANY,
                status_less_than=ANY,
                order_by=ANY,
                sort=ANY,
                minus=ANY,
            )

    def test_find_updated_ticket_ids_custom_window(self, zendesk_client):
        zendesk_client.zenpy.search.return_value = []
        zendesk_client.find_updated_ticket_ids(
            from_date=self._test_from_date,
            to_date=self._test_to_date,
        )
        zendesk_client.zenpy.search.assert_called_with(
            ANY,
            type=ANY,
            updated_between=[
                self._test_from_date,
                self._test_to_date,
            ],
            tags=ANY,
            status_less_than=ANY,
            order_by=ANY,
            sort=ANY,
            minus=ANY,
        )

    def test_find_updated_ticket_ids_search_criteria(self, zendesk_client):
        zendesk_client.zenpy.search.return_value = []
        zendesk_client.find_updated_ticket_ids()
        zendesk_client.zenpy.search.assert_called_with(
            "",  # match all
            type="ticket",
            updated_between=ANY,
            tags=["cx_messaging"],
            status_less_than="closed",
            order_by=ANY,
            sort=ANY,
            minus=ANY,
        )

    def test_find_updated_ticket_ids_sort_ordering(self, zendesk_client):
        zendesk_client.zenpy.search.return_value = []
        zendesk_client.find_updated_ticket_ids()
        zendesk_client.zenpy.search.assert_called_with(
            ANY,
            type=ANY,
            updated_between=ANY,
            tags=ANY,
            status_less_than=ANY,
            order_by="updated_at",
            sort="asc",
            minus=ANY,
        )

    def test_find_updated_ticket_ids_exclude_bot_conversations(self, zendesk_client):
        zendesk_client.zenpy.search.return_value = []
        zendesk_client.find_updated_ticket_ids()
        zendesk_client.zenpy.search.assert_called_with(
            ANY,
            type=ANY,
            updated_between=ANY,
            tags=ANY,
            status_less_than=ANY,
            order_by=ANY,
            sort=ANY,
            minus=["via:sunshine_conversations_api"],
        )

    def test_find_updated_ticket_ids_return_value(self, zendesk_client):
        zendesk_client.zenpy.search.return_value = [
            ZDTicket(id=1),
            ZDTicket(id=2),
            ZDTicket(id=3),
        ]

        result = zendesk_client.find_updated_ticket_ids()
        assert result == [1, 2, 3]

    @mock.patch("time.sleep")
    def test_zenpy_search_rate_limit_retry(self, mock_sleep, zendesk_client):

        # Given
        retry_after_time = 5
        mock_zendesk_response = Mock()
        mock_zendesk_response.headers = {"Retry-After": retry_after_time}
        mock_zendesk_response.status_code = 429

        mock_zendesk_response_two = [
            ZDTicket(id=1),
            ZDTicket(id=2),
            ZDTicket(id=3),
        ]

        zendesk_client.zenpy.search = Mock(
            side_effect=[
                ZendeskAPIException(response=mock_zendesk_response),
                mock_zendesk_response_two,
            ]
        )

        # When
        result = zendesk_client.find_updated_ticket_ids()

        # Then
        assert zendesk_client.zenpy.search.call_count == 2
        mock_sleep.assert_called_once_with(retry_after_time)
        assert result == [1, 2, 3]

    def test_get_comments_for_ticket_id_missing_id(self, zendesk_client):
        result = zendesk_client.get_comments_for_ticket_id()
        assert len(result) == 0

    @mock.patch("messaging.services.zendesk_client.warn_on_zendesk_rate_limit")
    def test_get_comments_for_ticket_id(
        self, mock_warn_on_zendesk_rate_limit, zendesk_client
    ):
        comments = [
            ZDComment(id=1),
            ZDComment(id=2),
            ZDComment(id=3),
        ]
        zendesk_client.zenpy.tickets.comments.return_value = comments

        result = zendesk_client.get_comments_for_ticket_id(ticket_id=1)
        assert len(result) == 3
        for comment in result:
            assert isinstance(comment, ZDComment)
            assert comment.id in [c.id for c in comments]

    @mock.patch(
        "messaging.services.zendesk_client.MAX_TICKETS_PER_SEARCH_CALL",
        1,
    )
    def test_ticket_search_helper(self, zendesk_client):
        search_results = [
            ZDTicket(id=idx, updated_at="2024-02-14T17:25:52Z") for idx in range(1, 3)
        ]

        search_results_copy = search_results[:]

        # this mimics us walking the from_date forward
        # we limit to max 1 per search call
        search_call_count = 0

        def search_result(*args, **kwargs):
            nonlocal search_results
            nonlocal search_call_count
            search_call_count += 1
            to_return = search_results
            search_results = search_results[1:]
            return to_return

        zendesk_client.zenpy.search = search_result

        result = zendesk_client._ticket_search_helper(
            from_date=self._test_from_date,
            to_date=self._test_to_date,
        )

        assert result == search_results_copy
        # we expect 1 more call than search results because the recursive call
        # is verifying there are no more results
        assert search_call_count == len(search_results_copy) + 1

    @mock.patch(
        "messaging.services.zendesk_client.MAX_TICKETS_PER_SEARCH_CALL",
        1,
    )
    def test_ticket_search_helper_recursion_limiter(self, zendesk_client):

        search_results = [
            ZDTicket(id=idx, updated_at="2024-02-14T17:25:52Z") for idx in range(1, 10)
        ]

        search_results_copy_limit = search_results[:TICKET_SEARCH_RECURSION_LIMIT]

        # this mimics us walking the from_date forward
        # we limit to max 1 per search call
        search_call_count = 0

        def search_result(*args, **kwargs):
            nonlocal search_results
            nonlocal search_call_count
            search_call_count += 1
            # to_return begins as the full list
            to_return = search_results
            # search results is sliced forward so next call will return all but
            # the first
            search_results = search_results[1:]
            return to_return

        zendesk_client.zenpy.search = search_result

        result = zendesk_client._ticket_search_helper(
            from_date=self._test_from_date,
            to_date=self._test_to_date,
        )

        assert result == search_results_copy_limit
        # the search helper should not recurse more than the limit
        assert search_call_count == TICKET_SEARCH_RECURSION_LIMIT

    def test_datetime_from_zendesk_date_str(self, zendesk_client):
        with pytest.raises(ValueError):
            zendesk_client.datetime_from_zendesk_date_str(None)

        with pytest.raises(ValueError):
            zendesk_client.datetime_from_zendesk_date_str("NOT_A_DATE")

        zendesk_client.datetime_from_zendesk_date_str("2024-02-14T17:25:52Z")

    def test_create_or_update_zd_user_lock_timeout(self, zendesk_client):
        user_id = "123"
        with mock.patch(
            "messaging.services.zendesk_client.RedisLock", autospec=True
        ) as mock_lock:
            mock_lock.return_value.__enter__.side_effect = LockTimeout("wait for it.")
            with pytest.raises(LockTimeout):
                with zendesk_client.create_or_update_zd_user_lock(
                    user_id=user_id,
                    lock_timeout_sec=5,
                ):
                    pass

    def test_create_or_update_zd_user_lock_operations(self, zendesk_client):
        user_id = "123"
        # this test shows that serial operations on the same lock happen without
        # interference
        counter = 0
        for _ in range(10):
            with zendesk_client.create_or_update_zd_user_lock(
                user_id=user_id,
                lock_timeout_sec=0.5,
            ):
                counter += 1
            # lock is released when scope exits
        assert counter == 10

    @pytest.mark.parametrize(argnames="zd_account_active", argvalues=[True, False])
    def test_get_zendesk_user_by_id(
        self, zd_account_active, default_user, zendesk_client
    ):
        # Given a user who has a ZD user counterpart with their zendesk_user_id
        default_user.zendesk_user_id = 1
        existing_zendesk_user = ZDUser(
            id=default_user.zendesk_user_id, active=zd_account_active
        )
        zendesk_client.zenpy.users.return_value = existing_zendesk_user

        # When
        returned_zendesk_user = zendesk_client.get_zendesk_user(
            zendesk_user_id=default_user.zendesk_user_id
        )

        # Then
        zendesk_client.zenpy.users.assert_called_once_with(id=existing_zendesk_user.id)
        zendesk_client.zenpy.search.assert_not_called()
        if zd_account_active:
            assert returned_zendesk_user
        else:
            assert not returned_zendesk_user

    def test_get_zendesk_user_by_id__no_response(self, default_user, zendesk_client):

        # Given
        default_user.zendesk_user_id = 1
        zendesk_client.zenpy.users.return_value = None

        # When
        returned_zendesk_user = zendesk_client.get_zendesk_user(
            zendesk_user_id=default_user.zendesk_user_id
        )

        # Then
        zendesk_client.zenpy.users.assert_called_once_with(
            id=default_user.zendesk_user_id
        )
        zendesk_client.zenpy.search.assert_not_called()
        assert not returned_zendesk_user

    @pytest.mark.parametrize(argnames="zd_account_active", argvalues=[True, False])
    def test_get_zendesk_user_by_email(
        self, zd_account_active, default_user, zendesk_client
    ):

        # Given a user who has a ZD user counterpart with their email
        existing_zendesk_user = ZDUser(
            email=default_user.email, active=zd_account_active
        )
        zendesk_client.zenpy.search.return_value = iter([existing_zendesk_user])

        # When getting the zd account by user email
        returned_zendesk_user = zendesk_client.get_zendesk_user(
            zendesk_user_email=default_user.email
        )

        # Then
        zendesk_client.zenpy.users.assert_not_called()
        zendesk_client.zenpy.search.assert_called_once_with(
            type="user", query=existing_zendesk_user.email
        )
        if zd_account_active:
            assert returned_zendesk_user
        else:
            assert not returned_zendesk_user

    def test_get_zendesk_user_by_email__no_response(self, default_user, zendesk_client):

        # Given
        default_user.zendesk_user_id = 1
        zendesk_client.zenpy.search.return_value = iter([])

        # When
        returned_zendesk_user = zendesk_client.get_zendesk_user(
            zendesk_user_email=default_user.email
        )

        # Then
        zendesk_client.zenpy.users.assert_not_called()
        zendesk_client.zenpy.search.assert_called_once_with(
            type="user", query=default_user.email
        )
        assert not returned_zendesk_user

    @mock.patch("messaging.services.zendesk_client.ZendeskClient._record_failed_call")
    def test_get_zendesk_user_by_email__api_exception(
        self,
        mock_record_failed_call,
        zendesk_client,
    ):

        # Given
        existing_zendesk_user = ZDUser(id=1)
        zendesk_client.zenpy.users.side_effect = [ZendeskAPIException]

        # When
        returned_zendesk_user = zendesk_client.get_zendesk_user(
            zendesk_user_id=existing_zendesk_user.id
        )

        # Then
        mock_record_failed_call.assert_called_once()
        assert not returned_zendesk_user

    @mock.patch("messaging.services.zendesk_client.log.info")
    def test_update_primary_identity__make_email_primary(
        self, mock_log_info, zendesk_client, factories
    ):

        # Given
        # the Zendesk user already has a primary email
        zendesk_client.zenpy.users.identities.return_value = [
            ZDIdentity(
                id=1,
                type="email",
                value="old_email@mavenclinic.com",
                primary=True,
            ),
            ZDIdentity(
                id=2,
                type="phone",
                value="1-212-555-5555",
            ),
        ]

        # the zendesk user profile retrieved upstream with the new values to be assigned as primary
        zd_user = ZDUser(id=1, email="new_email@mavenclinic.com")

        # When
        zendesk_client.update_primary_identity(
            zendesk_user_id=zd_user.id, zendesk_user=zd_user, update_identity="email"
        )

        # Then
        expected_calls = [
            mock.call(
                "Creating a new primary identity for the user",
                zendesk_user_id=1,
                updated_entity_type="email",
                num_existing_relevant_identites=1,
            ),
            mock.call(
                "Demoting the existing primary identity for user",
                zendesk_user_id=1,
                updated_entity_type="email",
            ),
            mock.call(
                "Updated the primary identity for user",
                zendesk_user_id=1,
                updated_entity_type="email",
            ),
        ]
        mock_log_info.assert_has_calls(expected_calls)

    @mock.patch("messaging.services.zendesk_client.log.info")
    def test_update_primary_identity__make_phone_number_primary(
        self, mock_log_info, zendesk_client, factories
    ):

        # Given
        # the Zendesk user already has a primary phone number
        zendesk_client.zenpy.users.identities.return_value = [
            ZDIdentity(id=1, type="email", value="old_email@mavenclinic.com"),
            ZDIdentity(id=2, type="phone", value="1-212-555-5555", primary=True),
        ]

        # the zendesk user profile retrieved upstream with the new values to be assigned as primary
        zd_user = ZDUser(id=1, phone="1-313-444-4444")

        # When
        zendesk_client.update_primary_identity(
            zendesk_user_id=zd_user.id, zendesk_user=zd_user, update_identity="phone"
        )

        # Then
        expected_calls = [
            mock.call(
                "Creating a new primary identity for the user",
                zendesk_user_id=1,
                updated_entity_type="phone",
                num_existing_relevant_identites=1,
            ),
            mock.call(
                "Demoting the existing primary identity for user",
                zendesk_user_id=1,
                updated_entity_type="phone",
            ),
            mock.call(
                "Updated the primary identity for user",
                zendesk_user_id=1,
                updated_entity_type="phone",
            ),
        ]
        mock_log_info.assert_has_calls(expected_calls)

    @mock.patch("messaging.services.zendesk_client.log.info")
    @mock.patch("messaging.services.zendesk_client.log.error")
    @mock.patch(
        "messaging.services.zendesk_client.exception_related_to_email_already_exists",
        return_value=True,
    )
    def test_update_primary_identity__email_exist_exception(
        self,
        mock_exception_is_email,
        mock_log_error,
        mock_log_info,
        zendesk_client,
        factories,
    ):
        # Given
        zendesk_client.zenpy.users.identities.create.side_effect = ZendeskAPIException()
        # the Zendesk user already has a primary email
        zendesk_client.zenpy.users.identities.return_value = [
            ZDIdentity(
                id=1,
                type="email",
                value="old_email@mavenclinic.com",
                primary=True,
            ),
            ZDIdentity(
                id=2,
                type="phone",
                value="1-212-555-5555",
            ),
            ZDIdentity(
                id=3,
                type="email",
                value="old_email123@mavenclinic.com",
                primary=False,
            ),
        ]

        # the zendesk user profile retrieved upstream with the new values to be assigned as primary
        zd_user = ZDUser(id=1, email="new_email@mavenclinic.com")

        # When
        with pytest.raises(ZendeskAPIEmailAlreadyExistsException):
            zendesk_client.update_primary_identity(
                zendesk_user_id=zd_user.id,
                zendesk_user=zd_user,
                update_identity="email",
            )

        # Then
        expected_calls = [
            mock.call(
                "Creating a new primary identity for the user",
                zendesk_user_id=1,
                updated_entity_type="email",
                num_existing_relevant_identites=2,
            ),
            mock.call(
                "Creating a new primary identity for the user",
                zendesk_user_id=1,
                updated_entity_type="email",
                num_existing_relevant_identites=2,
            ),
        ]
        mock_log_info.assert_has_calls(expected_calls)
        mock_log_error.assert_called_once()

    @mock.patch("messaging.services.zendesk_client.time.sleep", return_value=None)
    @mock.patch("messaging.services.zendesk_client.log.error")
    @mock.patch(
        "messaging.services.zendesk_client.ZendeskClient.update_primary_identity_helper"
    )
    @mock.patch(
        "messaging.services.zendesk_client.exception_related_to_email_already_exists",
        return_value=True,
    )
    def test_update_primary_identity_retry_logic(
        self,
        mock_exception_is_email,
        mock_update_primary_identity_helper,
        mock_log_error,
        mock_sleep,
        zendesk_client,
        factories,
    ):
        # Given
        mock_update_primary_identity_helper.side_effect = [ZendeskAPIException(), None]
        zd_user = ZDUser(id=1, email="new_email@mavenclinic.com")

        # When
        zendesk_client.update_primary_identity(
            zendesk_user_id=zd_user.id, zendesk_user=zd_user, update_identity="email"
        )

        # Then
        assert mock_update_primary_identity_helper.call_count == 2
        mock_log_error.assert_called_once_with(
            "Received zendesk API email already exists exception, will retry",
            zendesk_user_id=1,
            updated_entity_type="email",
        )
        mock_sleep.assert_called_once_with(1)

    @mock.patch("messaging.services.zendesk_client.log.info")
    def test_merge_zendesk_profiles(self, mock_log_info, zendesk_client, factories):

        # Given

        # A source zendesk user profile and a destination zendesk user profile
        source_zendesk_user = ZDUser(id=1)
        destination_zendesk_user = ZDUser(id=2)

        user = factories.DefaultUserFactory.create()

        # zenpy's `merge` function returns the merged profile (by merging the source profile into the destination profile)

        zendesk_client.zenpy.users.merge.return_value = destination_zendesk_user

        # When
        zendesk_client.merge_zendesk_profiles(
            user_id=user.id,
            source_zendesk_user=source_zendesk_user,
            destination_zendesk_user=destination_zendesk_user,
        )

        # Then
        mock_log_info.assert_called_once_with(
            "Successfully merged duplicate Zendesk User Profiles",
            user_id=user.id,
            merged_zendesk_profile_id=destination_zendesk_user.id,
        )

    def test_create_or_update_user__enterprise_user(
        self,
        factories,
        zendesk_client,
    ):

        # Given
        user = factories.EnterpriseUserFactory()
        user.member_profile.phone_number = "7733220947"
        zendesk_client.zenpy.search.return_value = [ZDOrganization(id=123)]
        # When
        zendesk_client.create_or_update_user(user)

        # Then

        create_or_update_mock_args_dict = (
            zendesk_client.zenpy.users.create_or_update.call_args_list[0]
            .kwargs["users"]
            .__dict__
        )
        assert create_or_update_mock_args_dict["email"] == user.email
        assert create_or_update_mock_args_dict["name"] == user.full_name
        assert create_or_update_mock_args_dict["phone"] == "+17733220947"
        assert create_or_update_mock_args_dict["external_id"] == user.id
        # assert (
        #     create_or_update_mock_args_dict["organization_id"]
        #     == user.organization_v2.id
        # )
        assert create_or_update_mock_args_dict["user_fields"] == {
            "care_advocate": user.care_coordinators[0].full_name,
            "track": user.active_tracks[0].name,
        }
        assert create_or_update_mock_args_dict["organization_id"] == 123

    def test_create_or_update_user__default_user(
        self,
        default_user,
        zendesk_client,
    ):

        # Given
        user = default_user
        zendesk_client.zenpy.search.return_value = [ZDOrganization(id=123)]
        # When
        zendesk_client.create_or_update_user(user)

        # Then

        create_or_update_mock_args_dict = (
            zendesk_client.zenpy.users.create_or_update.call_args_list[0]
            .kwargs["users"]
            .__dict__
        )
        assert create_or_update_mock_args_dict["email"] == user.email
        assert create_or_update_mock_args_dict["name"] == user.full_name
        assert create_or_update_mock_args_dict["phone"] == None
        assert create_or_update_mock_args_dict["external_id"] == user.id
        assert create_or_update_mock_args_dict["user_fields"] == {
            "care_advocate": None,
            "track": None,
        }
        assert create_or_update_mock_args_dict["organization_id"] == None

    def test_create_or_update_zd_org_lock_timeout(self, zendesk_client):
        org_id = "123"
        with mock.patch(
            "messaging.services.zendesk_client.RedisLock", autospec=True
        ) as mock_lock:
            mock_lock.return_value.__enter__.side_effect = LockTimeout("wait for it.")
            with pytest.raises(LockTimeout):
                with zendesk_client.create_or_update_zd_org_lock(
                    org_id=org_id,
                    lock_timeout_sec=5,
                ):
                    pass

    def test_create_or_update_zd_org_lock_operations(self, zendesk_client):
        org_id = "123"
        # this test shows that serial operations on the same lock happen without
        # interference
        counter = 0
        for _ in range(10):
            with zendesk_client.create_or_update_zd_org_lock(
                org_id=org_id,
                lock_timeout_sec=0.5,
            ):
                counter += 1
            # lock is released when scope exits
        assert counter == 10

    def test_create_or_update_org(
        self,
        factories,
        zendesk_client,
    ):

        # Given org + tracks
        org = factories.OrganizationFactory()
        factories.ClientTrackFactory.create(organization=org, track=TrackName.ADOPTION)
        factories.ClientTrackFactory.create(organization=org, track=TrackName.PREGNANCY)
        # When
        zendesk_client.create_or_update_organization(
            org.id,
            org.name,
            "Adoption\nPregnancy",
            org.US_restricted,
        )

        # Then
        create_or_update_mock_args_dict = (
            zendesk_client.zenpy.organizations.create_or_update.call_args_list[0]
            .kwargs["organization"]
            .__dict__
        )
        assert (
            create_or_update_mock_args_dict["name"] == org.display_name
            if org.display_name
            else org.name
        )
        assert create_or_update_mock_args_dict["external_id"] == org.id
        assert create_or_update_mock_args_dict["organization_fields"] == {
            "tracks": "Adoption\nPregnancy",
            "offshore_restriction": org.US_restricted,
        }

    def test_get_zendesk_organization(
        self,
        factories,
        zendesk_client,
    ):

        # Given
        zd_org_id = 123
        org = factories.OrganizationFactory()
        zendesk_client.zenpy.search.return_value = [ZDOrganization(id=zd_org_id)]
        # When
        zd_org = zendesk_client.get_zendesk_organization(
            org.id,
        )

        # Then
        assert zd_org.id == zd_org_id

    @mock.patch("messaging.services.zendesk_client.log.error")
    def test_get_zendesk_organization__org_not_in_zd(
        self,
        mock_log_error,
        factories,
        zendesk_client,
    ):
        # Given
        org = factories.OrganizationFactory()
        zendesk_client.zenpy.search.return_value = []
        # When
        zd_org = zendesk_client.get_zendesk_organization(org.id)

        # Then
        assert zd_org is None

    def test_get_zendesk_organization__no_org_passed(
        self,
        factories,
        zendesk_client,
    ):

        # Given
        # When
        zd_org = zendesk_client.get_zendesk_organization(
            None,
        )

        # Then
        assert zd_org is None

    def test_get_zendesk_organization__multiple_orgs(
        self,
        factories,
        zendesk_client,
    ):

        # Given
        zd_org_id = 123
        org = factories.OrganizationFactory()
        zendesk_client.zenpy.search.return_value = [
            ZDOrganization(id=zd_org_id),
            ZDOrganization(id=000),
        ]
        # When
        zd_org = zendesk_client.get_zendesk_organization(
            org.id,
        )

        # Then
        assert zd_org.id == zd_org_id

    @mock.patch("time.sleep")
    def test_find_updated_ticket_ids_retry(self, mock_sleep, zendesk_client):

        # Given
        retry_after_time = 5
        mock_zendesk_response = Mock()
        mock_zendesk_response.headers = {"Retry-After": retry_after_time}
        mock_zendesk_response.status_code = 429

        mock_zendesk_response_two = [
            ZDTicket(id=1),
            ZDTicket(id=2),
            ZDTicket(id=3),
        ]

        zendesk_client.zenpy.search = Mock(
            side_effect=[
                ZendeskAPIException(response=mock_zendesk_response),
                mock_zendesk_response_two,
            ]
        )

        # When
        result = zendesk_client.find_updated_ticket_ids()

        # Then
        assert zendesk_client.zenpy.search.call_count == 2
        mock_sleep.assert_called_once_with(retry_after_time)
        assert result == [1, 2, 3]

    @mock.patch("time.sleep")
    def test_get_comments_for_ticket_id_retry(self, mock_sleep, zendesk_client):
        # Given
        retry_after_time = 5
        mock_zendesk_response = Mock()
        mock_zendesk_response.headers = {"Retry-After": retry_after_time}
        mock_zendesk_response.status_code = 429

        mock_zendesk_response_two = [
            ZDComment(id=1),
            ZDComment(id=2),
            ZDComment(id=3),
        ]

        zendesk_client.zenpy.tickets.comments = Mock(
            side_effect=[
                ZendeskAPIException(response=mock_zendesk_response),
                mock_zendesk_response_two,
            ]
        )

        # When
        result = zendesk_client.get_comments_for_ticket_id(ticket_id=1)

        # Then
        assert zendesk_client.zenpy.tickets.comments.call_count == 2
        mock_sleep.assert_called_once_with(retry_after_time)
        assert len(result) == 3
        for comment in result:
            assert isinstance(comment, ZDComment)
            assert comment.id in [c.id for c in mock_zendesk_response_two]

    @mock.patch("time.sleep")
    def test_ticket_with_id_retry(self, mock_sleep, zendesk_client):

        # Given
        retry_after_time = 5
        mock_zendesk_response = Mock()
        mock_zendesk_response.headers = {"Retry-After": retry_after_time}
        mock_zendesk_response.status_code = 429

        mock_zendesk_response_two = ZDTicket(id=1)

        zendesk_client.zenpy.tickets = Mock(
            side_effect=[
                ZendeskAPIException(response=mock_zendesk_response),
                mock_zendesk_response_two,
            ]
        )

        # When
        result = zendesk_client.ticket_with_id(ticket_id=1)

        # Then
        assert zendesk_client.zenpy.tickets.call_count == 2
        mock_sleep.assert_called_once_with(retry_after_time)
        assert result == mock_zendesk_response_two


class TestZendeskUpdateUser:
    def test_update_user__happy_path(
        self,
        zendesk_client,
    ):
        # Given
        zd_user = Mock()

        # When
        response = zendesk_client.update_user(user_id=123, zendesk_user=zd_user)

        # Then
        assert response == zendesk_client.zenpy.users.update.return_value

    def test_update_user__email_exception_raised(
        self,
        zendesk_client,
    ):

        # Given
        zd_user = Mock()
        mock_zendesk_response = Mock()
        mock_zendesk_response.json.return_value = {
            "details": {"email": [{"error": "DuplicateValue"}]},
        }

        zendesk_client.zenpy.users.update.side_effect = ZendeskAPIException(
            response=mock_zendesk_response
        )
        failed_vendor_api_call_recorder_mock = Mock()
        failed_vendor_api_call_recorder_mock.create_record.return_value = None
        zendesk_client.failed_vendor_api_call_recorder = (
            failed_vendor_api_call_recorder_mock
        )

        # When / Then
        with pytest.raises(ZendeskAPIEmailAlreadyExistsException):
            zendesk_client.update_user(user_id=123, zendesk_user=zd_user)


class TestZendeskAPIException:
    def test_handle_duplicate_value_exception__update_primary_identity(self, factories):

        # Given

        # `update_primary_identity` throws an APIException
        mock_exception = Mock()
        mock_exception.response.json.return_value = {
            "details": {
                "email": [
                    {
                        "description": "Email: <b>User couldn't be updated</b><br>This email is already taken. Try another email. <a href='https://support.zendesk.com/hc/en-us/articles/4408834337562'>Learn about emails in use</a>.",
                        "error": "DuplicateValue",
                    }
                ]
            }
        }

        # Then
        assert exception_related_to_email_already_exists(mock_exception) is True

    def test_handle_duplicate_value_exception__update_user(self, factories):
        # Given
        mock_exception = Mock()
        mock_exception.response.json.return_value = {
            "details": {
                "email": [
                    {
                        "description": "Email: <b>User couldn't be updated</b><br>This email is already taken. Try another email. <a href='https://support.zendesk.com/hc/en-us/articles/4408834337562'>Learn about emails in use</a>.",
                        "error": "DuplicateValue",
                    }
                ]
            }
        }

        # Then
        assert exception_related_to_email_already_exists(mock_exception) is True


class TestZendeskRateLimit:
    @mock.patch("messaging.services.zendesk_client.log.warning")
    def test_warn_on_zendesk_rate_limit(self, mock_log):

        # Given
        mock_zendesk_response = Mock()
        # mock zendesk response headers with remaining rate limits below the default threshold
        mock_zendesk_response.headers = {
            "ratelimit-remaining": 80,
            "Zendesk-RateLimit-Endpoint": 50,
        }

        # When
        warn_on_zendesk_rate_limit(response=mock_zendesk_response)

        # Then
        mock_log.assert_any_call(
            "Zendesk account rate limit is below the warning threshold!",
            warning_threshold=100,
        )
        mock_log.assert_any_call(
            "Zendesk endpoint rate limit is below the warning threshold!",
            warning_threshold=100,
        )

    @mock.patch("messaging.services.zendesk_client.log.info")
    @mock.patch("time.sleep")
    def test_handle_zendesk_rate_limit(self, mock_sleep, mock_log):

        # Given
        mock_zendesk_response = Mock()
        retry_after_time = 5

        # When
        mock_zendesk_response.headers = {"Retry-After": retry_after_time}

        # Then
        handle_zendesk_rate_limit(response=mock_zendesk_response)

        mock_sleep.assert_called_once_with(5)
        mock_log.assert_called_once_with(
            "Zendesk rate limit exceeded. Retrying...", retry_wait_time=5
        )

    @mock.patch("messaging.services.zendesk_client.log.info")
    @mock.patch("time.sleep")
    def test_handle_zendesk_rate_limit__default_wait_time(self, mock_sleep, mock_log):

        # Given
        mock_zendesk_response = Mock()

        # When
        mock_zendesk_response.headers = {}

        # Then
        handle_zendesk_rate_limit(response=mock_zendesk_response)

        mock_sleep.assert_called_once_with(DEFAULT_ZENDESK_RETRY_WAIT_TIME)
        mock_log.assert_called_once_with(
            "Zendesk rate limit exceeded. Retrying...", retry_wait_time=30
        )

    @mock.patch("requests.Session.request")
    @mock.patch("messaging.services.zendesk_client.log.warning")
    def test_warn_on_rate_limit_from_custom_session_request(
        self, mock_warning, mock_request
    ):

        # Given
        mock_response = Mock()
        mock_response.headers = {
            "ratelimit-remaining": 9,
        }
        mock_request.return_value = mock_response

        # When
        # create custom session to intercept request call and trigger `warn_on_zendesk_rate_limit` function
        session = CustomSession(warning_threshold=10)
        session.request("GET", "https://test_url.com")

        # Then
        mock_warning.assert_called_once_with(
            "Zendesk account rate limit is below the warning threshold!",
            warning_threshold=100,
        )
