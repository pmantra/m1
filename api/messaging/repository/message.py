from __future__ import annotations

import datetime
from typing import List, Tuple

import ddtrace.ext
import sqlalchemy.exc
import sqlalchemy.orm
from sqlalchemy.orm import aliased
from sqlalchemy.orm.query import Query

from authn.models.user import User
from messaging.models.messaging import Channel, ChannelUsers, Message
from models.profiles import PractitionerProfile
from notification.models.sms_notifications_consent import SmsNotificationsConsent
from storage import connection
from storage.connection import db
from utils.log import logger

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class MessageRepository:

    __slots__ = ("session",)

    DEFAULT_QUERY_LIMIT = 100
    DEFAULT_QUERY_OFFSET = 0
    DEFAULT_QUERY_ORDER = "asc"
    DEFAULT_QUERY_COLUMN_ORDER = "created_at"

    def __init__(self, session: sqlalchemy.orm.Session = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "Session")
        self.session = session or connection.db.session().using_bind("default")

    @trace_wrapper
    def get(self, *, id: int) -> Message | None:
        return self.session.query(Message).get(id)

    @trace_wrapper
    def _get_messages(self, args: dict) -> Query | None:
        query = self.session.query(Message)

        if args.get("created_at_after"):
            query = query.filter(Message.created_at >= args["created_at_after"])
        if args.get("created_at_before"):
            query = query.filter(Message.created_at <= args["created_at_before"])
        if args.get("zendesk_comment_id_none"):
            query = query.filter(Message.zendesk_comment_id.is_(None))
        if args.get("users_ids_excluded"):
            query = query.filter(Message.user_id.notin_(args["users_ids_excluded"]))

        return query

    @trace_wrapper
    def get_messages_paginated(
        self,
        args: dict | None = None,
    ) -> Tuple[dict, List[Message]]:
        def _validate_args(args: dict | None = None) -> dict:

            # Guard against None args
            if args is None:
                args = {}

            # Validate args
            args["created_at_after"] = (
                args["created_at_after"]
                if "created_at_after" in args
                and isinstance(args["created_at_after"], datetime.datetime)
                else None
            )
            args["created_at_before"] = (
                args["created_at_before"]
                if "created_at_before" in args
                and isinstance(args["created_at_before"], datetime.datetime)
                else None
            )
            args["limit"] = (
                args["limit"]
                if "limit" in args and isinstance(args["limit"], int)
                else self.DEFAULT_QUERY_LIMIT
            )
            args["offset"] = (
                args["offset"]
                if "offset" in args and isinstance(args["offset"], int)
                else self.DEFAULT_QUERY_OFFSET
            )

            message_cols = [c.key for c in Message.__table__.columns]

            args["order_column"] = (
                args["order_column"]
                if ("order_column" in args and args["order_column"] in message_cols)
                else self.DEFAULT_QUERY_COLUMN_ORDER
            )

            args["order_direction"] = (
                args["order_direction"]
                if (
                    "order_direction" in args
                    and args["order_direction"] in ["asc", "desc"]
                )
                else self.DEFAULT_QUERY_ORDER
            )
            # if zendesk_comment_id_none is specified, it must be either False or True, defaulting to False
            if (
                "zendesk_comment_id_none" in args
                and args["zendesk_comment_id_none"] is not True
            ):
                args["zendesk_comment_id_none"] = False

            # if users_ids_excluded is specified, it must be a list of integers
            if "users_ids_excluded" in args:
                if not (
                    isinstance(args["users_ids_excluded"], list)
                    and all(isinstance(i, int) for i in args["users_ids_excluded"])
                ):
                    args.pop("users_ids_excluded", None)

            return args

        args = _validate_args(args)

        messages_query = self._get_messages(args)
        total_records = messages_query.count()

        # Prep sorting
        sort = (
            sqlalchemy.asc(args["order_column"])
            if args["order_direction"] == "asc"
            else sqlalchemy.desc(args["order_column"])
        )

        # Get messages and return them together with pagination data
        messages_records = (
            messages_query.order_by(sort)
            .limit(args["limit"])
            .offset(args["offset"])
            .all()
        )

        pagination = {
            "total": total_records,
            "limit": args["limit"],
            "offset": args["offset"],
            "order_direction": args["order_direction"],
        }

        return pagination, messages_records


def extend_query_filter_by_practitioner_id(message_query: Query, user_id: int) -> Query:

    channel_model = aliased(Channel, name="channel_in_filter_by_practitioner_query")
    extended_query = (
        message_query.join(channel_model, Message.channel_id == channel_model.id)
        .join(ChannelUsers, channel_model.id == ChannelUsers.channel_id)
        .join(User, User.id == ChannelUsers.user_id)
        .join(PractitionerProfile, ChannelUsers.user_id == PractitionerProfile.user_id)
        .filter(User.id == user_id)
    )
    return extended_query


def extend_query_filter_by_member_id(message_query: Query, user_id: int) -> Query:

    # Need to alias tables in case extend_query_filter_by_practitioner_id is also applied
    Channel_ = aliased(Channel, name="channel_alias")
    ChannelUsers_ = aliased(ChannelUsers, name="channel_users_alias")
    User_ = aliased(User, name="user_alias")
    PractitionerProfile_ = aliased(
        PractitionerProfile, name="practitioner_profile_alias"
    )

    extended_query = (
        message_query.join(Channel_, Message.channel_id == Channel_.id)
        .join(ChannelUsers_, Channel_.id == ChannelUsers_.channel_id)
        .join(User_, User_.id == ChannelUsers_.user_id)
        .outerjoin(
            PractitionerProfile_, ChannelUsers_.user_id == PractitionerProfile_.user_id
        )
        .filter(PractitionerProfile_.user_id.is_(None), User_.id == user_id)
    )
    return extended_query


def set_sms_messaging_notifications_enabled(user_id: int) -> None:
    user_sms_notifications_consent = (
        db.session.query(SmsNotificationsConsent)
        .filter(SmsNotificationsConsent.user_id == user_id)
        .first()
    )

    if user_sms_notifications_consent:
        # If the user exists, update the 'enabled' field to True
        user_sms_notifications_consent.sms_messaging_notifications_enabled = True
    else:
        # If the user does not exist, create and insert a new row
        user_sms_notifications_consent = SmsNotificationsConsent(
            user_id=user_id, sms_messaging_notifications_enabled=True
        )
        db.session.add(user_sms_notifications_consent)
    try:
        db.session.commit()
    except sqlalchemy.exc.IntegrityError:
        log.info(
            "race condition while setting sms_messaging_notifications_enabled",
            user_id=user_id,
        )
        db.session.rollback()
        return


def get_sms_messaging_notifications_enabled(user_id: int) -> bool:
    user_sms_notifications_consent = (
        db.session.query(SmsNotificationsConsent)
        .filter(SmsNotificationsConsent.user_id == user_id)
        .first()
    )
    return (
        user_sms_notifications_consent.sms_messaging_notifications_enabled
        if user_sms_notifications_consent
        else False
    )
