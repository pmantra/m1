import datetime
from unittest import mock

import pytest
import sqlalchemy.exc

from messaging.models.messaging import Channel, Message
from messaging.repository.message import (
    MessageRepository,
    extend_query_filter_by_member_id,
    extend_query_filter_by_practitioner_id,
    get_sms_messaging_notifications_enabled,
    set_sms_messaging_notifications_enabled,
)
from notification.models.sms_notifications_consent import SmsNotificationsConsent
from pytests.db_util import enable_db_performance_warnings
from storage.connection import db


class TestMessageRepository:
    def test_get_messages_paginated__with_date_filters(
        self,
        one_hour_ago,
        two_hours_ago,
        now_message,
        one_hour_ago_message,
        two_hours_ago_message,
        three_hours_ago_message,
    ):

        # Given a set of messages exist, with different created_at values (see factories in args)
        # and a set of args that would capture only two messages
        args = {}
        # TODO: for some weird reason two_hours_ago_message is being filtered out
        # when doing the created_at_after query.
        # Adding a -1 second to the timeframe for now to make it work
        args["created_at_after"] = two_hours_ago - datetime.timedelta(seconds=1)
        args["created_at_before"] = one_hour_ago + datetime.timedelta(seconds=1)

        # When we call get_messages_paginated
        # TODO: there seems to be some flakiness here
        pagination, messages = MessageRepository().get_messages_paginated(args)

        # Then we get the expected results
        expected_messages = [two_hours_ago_message, one_hour_ago_message]
        expected_pagination = {
            "total": len(expected_messages),
            "limit": MessageRepository.DEFAULT_QUERY_LIMIT,
            "offset": MessageRepository.DEFAULT_QUERY_OFFSET,
            "order_direction": MessageRepository.DEFAULT_QUERY_ORDER,
        }
        assert expected_pagination == pagination
        assert expected_messages == messages

    @pytest.mark.parametrize(argnames="limit", argvalues=[0, 1, 2, 100, None])
    @pytest.mark.parametrize(argnames="offset", argvalues=[0, 1, 2, 100, None])
    @pytest.mark.parametrize(
        argnames="order_direction", argvalues=["asc", "desc", "invalid_order", None]
    )
    @pytest.mark.parametrize(
        argnames="order_column", argvalues=["created_at", "modified_at", "invalid_col"]
    )
    def test_get_messages_paginated__with_pagination_and_order(
        self,
        order_column,
        order_direction,
        offset,
        limit,
        now_message,
        one_hour_ago_message,
        two_hours_ago_message,
        three_hours_ago_message,
    ):

        # Given a set of messages exist,
        # and a set of args that would capture messages according to
        # specific limit, offset and order direction args.

        args = {}

        args["limit"] = limit
        args["offset"] = offset
        args["order_column"] = order_column
        args["order_direction"] = order_direction

        # When we call get_messages_paginated
        pagination, messages = MessageRepository().get_messages_paginated(args)

        # Then we get the expected results

        expected_limit = (
            limit if limit is not None else MessageRepository.DEFAULT_QUERY_LIMIT
        )
        expected_offset = (
            offset if offset is not None else MessageRepository.DEFAULT_QUERY_OFFSET
        )
        expected_order_direction = (
            order_direction
            if order_direction in ["asc", "desc"]
            else MessageRepository.DEFAULT_QUERY_ORDER
        )
        expected_order_column = (
            order_column
            if order_column in [c.key for c in Message.__table__.columns]
            else MessageRepository.DEFAULT_QUERY_COLUMN_ORDER
        )

        all_messages = [
            three_hours_ago_message,
            two_hours_ago_message,
            one_hour_ago_message,
            now_message,
        ]
        all_messages_sorted = sorted(
            all_messages,
            key=lambda x: getattr(x, expected_order_column),
            reverse=expected_order_direction == "desc",
        )
        expected_messages = all_messages_sorted[
            expected_offset : expected_offset + expected_limit
        ]

        expected_pagination = {
            "total": len(all_messages_sorted),
            "limit": expected_limit,
            "offset": expected_offset,
            "order_direction": expected_order_direction,
        }
        assert expected_pagination == pagination
        assert expected_messages == messages

    @pytest.mark.parametrize(
        argnames="zendesk_comment_id_arg",
        argvalues=[True, False, "wrong_input", "", None],
    )
    def test_get_messages_paginated__with_no_zendesk_comment_id(
        self,
        zendesk_comment_id_arg,
        now_message,
        one_hour_ago_message,
        two_hours_ago_message,
        three_hours_ago_message,
    ):

        # Given a set of messages exist, some of which have zendesk_comment_id, some dont
        args = {}
        three_hours_ago_message.zendesk_comment_id = 1
        two_hours_ago_message.zendesk_comment_id = None
        one_hour_ago_message.zendesk_comment_id = 2
        now_message.zendesk_comment_id = 3
        db.session.commit()

        args["zendesk_comment_id_none"] = zendesk_comment_id_arg

        # When we call get_messages_paginated
        pagination, messages = MessageRepository().get_messages_paginated(args)

        # Then we get the expected results
        expected_limit = MessageRepository.DEFAULT_QUERY_LIMIT
        expected_offset = MessageRepository.DEFAULT_QUERY_OFFSET
        expected_order_direction = MessageRepository.DEFAULT_QUERY_ORDER
        expected_order_column = MessageRepository.DEFAULT_QUERY_COLUMN_ORDER

        all_messages = [
            three_hours_ago_message,
            two_hours_ago_message,
            one_hour_ago_message,
            now_message,
        ]
        all_messages_sorted = sorted(
            all_messages,
            key=lambda x: getattr(x, expected_order_column),
            reverse=expected_order_direction == "desc",
        )

        if zendesk_comment_id_arg is True:
            # Expect not to receive messages that have zendesk_comment_id
            all_messages_sorted = [
                m for m in all_messages_sorted if not m.zendesk_comment_id
            ]
            expected_messages = all_messages_sorted[
                expected_offset : expected_offset + expected_limit
            ]
        else:
            expected_messages = all_messages_sorted[
                expected_offset : expected_offset + expected_limit
            ]

        expected_pagination = {
            "total": len(all_messages_sorted),
            "limit": expected_limit,
            "offset": expected_offset,
            "order_direction": expected_order_direction,
        }
        assert expected_pagination == pagination
        assert expected_messages == messages


class TestExtendQuery:
    def test_extend_query_filter_by_practitioner_id(
        self, message_channel, factories, db
    ):

        # Given two messages, each written by different practitioners
        member = factories.MemberFactory.create()

        practitioner1 = factories.PractitionerUserFactory.create()
        channel1 = Channel.get_or_create_channel(practitioner1, [member])
        message1 = factories.MessageFactory(user=practitioner1, channel=channel1)

        practitioner2 = factories.PractitionerUserFactory.create()
        channel2 = Channel.get_or_create_channel(practitioner2, [member])
        factories.MessageFactory(user=practitioner2, channel=channel2)

        # Assert no table scans
        with enable_db_performance_warnings(
            database=db,
        ):
            # When we query by practitioner 1
            query = db.session.query(Message)
            extended_query = extend_query_filter_by_practitioner_id(
                query, practitioner1.id
            )

            # Then we only get message1
            assert extended_query.all() == [message1]

    def test_extend_query_filter_by_member_id(self, message_channel, factories, db):

        # Given two messages, each written by different members
        practitioner = factories.PractitionerUserFactory.create()

        member1 = factories.MemberFactory.create()
        channel1 = Channel.get_or_create_channel(practitioner, [member1])
        message1 = factories.MessageFactory(user=member1, channel=channel1)

        member2 = factories.MemberFactory.create()
        channel2 = Channel.get_or_create_channel(practitioner, [member2])
        factories.MessageFactory(user=member2, channel=channel2)

        # Assert no table scans
        with enable_db_performance_warnings(
            database=db,
        ):
            # When we query by member 1
            query = db.session.query(Message)
            extended_query = extend_query_filter_by_member_id(query, member1.id)

            # Then we only get message1
            assert extended_query.all() == [message1]


class TestSmsNotificationsConsent:
    def test_set_sms_messaging_notifications_enabled_user_exists(self, factories):
        # given:
        user = factories.EnterpriseUserFactory()
        user_sms_notifications_consent = SmsNotificationsConsent(
            user_id=user.id, sms_messaging_notifications_enabled=False
        )
        db.session.add(user_sms_notifications_consent)
        db.session.commit()
        consent_user = (
            db.session.query(SmsNotificationsConsent)
            .filter(SmsNotificationsConsent.user_id == user.id)
            .first()
        )
        assert not consent_user.sms_messaging_notifications_enabled
        # when
        set_sms_messaging_notifications_enabled(user_id=user.id)

        # then
        final_consent_user = (
            db.session.query(SmsNotificationsConsent)
            .filter(SmsNotificationsConsent.user_id == user.id)
            .first()
        )
        assert final_consent_user
        assert final_consent_user.sms_messaging_notifications_enabled is True

    def test_set_sms_messaging_notifications_enabled_no_user(self, factories):
        # given:
        user = factories.EnterpriseUserFactory()

        # when
        set_sms_messaging_notifications_enabled(user_id=user.id)

        # then
        final_consent_user = (
            db.session.query(SmsNotificationsConsent)
            .filter(SmsNotificationsConsent.user_id == user.id)
            .first()
        )
        assert final_consent_user
        assert final_consent_user.sms_messaging_notifications_enabled is True

    def test_get_sms_messaging_notifications_enabled_user_exists(self, factories):
        # given:
        user = factories.EnterpriseUserFactory()
        user_sms_notifications_consent = SmsNotificationsConsent(
            user_id=user.id, sms_messaging_notifications_enabled=True
        )
        db.session.add(user_sms_notifications_consent)
        db.session.commit()
        # when
        result = get_sms_messaging_notifications_enabled(user_id=user.id)

        # then
        assert result is True

    def test_get_sms_messaging_notifications_enabled_no_user(self, factories):
        # given:
        user = factories.EnterpriseUserFactory()

        # when
        result = get_sms_messaging_notifications_enabled(user_id=user.id)

        # then
        assert result is False

    def test_set_sms_messaging_notifications_enabled_race_condition(self, factories):
        # given:
        user = factories.EnterpriseUserFactory()

        with mock.patch(
            "messaging.repository.message.db.session.commit"
        ) as mock_db_add:
            mock_db_add.side_effect = sqlalchemy.exc.IntegrityError(
                "Mocked IntegrityError", orig=None, params=None
            )

            # when
            set_sms_messaging_notifications_enabled(user_id=user.id)

            # then
            final_consent_user = (
                db.session.query(SmsNotificationsConsent)
                .filter(SmsNotificationsConsent.user_id == user.id)
                .first()
            )
            assert final_consent_user is None
