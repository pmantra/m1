from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import sqlalchemy
from sqlalchemy.orm import contains_eager

from authn.models.user import User
from messaging.models.messaging import Channel
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class ChannelMetadata:
    """
    A simple class to hold metadata about a channel
    """

    def __init__(self, channel_id: int):
        if channel_id is None:
            raise ValueError("channel_id must not be None")
        self.channel_id: int = channel_id
        self.created_at: Optional[datetime] = None
        self.message_count: int = 0
        self.latest_message_timestamp: Optional[datetime] = None

    def update_properties(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)
        return None


class ChannelMetadataStore:
    """
    A simple store for channel metadata
    """

    def __init__(self) -> None:
        self.channel_lookup: dict[int, ChannelMetadata] = {}

    def add_metadata(self, channel_id: int, **kwargs: Any) -> None:
        if channel_id is None:
            raise ValueError("channel_id must not be None")
        if channel_id not in self.channel_lookup:
            self.channel_lookup[channel_id] = ChannelMetadata(channel_id=channel_id)
        self.channel_lookup[channel_id].update_properties(**kwargs)
        return None

    def get(self, channel_id: int) -> Optional[ChannelMetadata]:
        return self.channel_lookup.get(channel_id)

    def get_all(self) -> List[ChannelMetadata]:
        return list(self.channel_lookup.values())


def get_list_of_channel_ids_user_participates_in(
    user: Optional[User] = None,
) -> List[int]:
    """
    Given a user, return the list of channel ids that user participates in
    """
    if user is None:
        return []

    users_channel_ids_rows = (
        db.session()
        .using_bind("default")
        .execute(
            """
        SELECT
          channel_id
        FROM
          channel_users
        WHERE
          user_id = :user_id
        """,
            {"user_id": user.id},
        )
    )
    return [row[0] for row in users_channel_ids_rows if row[0] is not None]


def get_channel_metadata_for_channel_ids(
    channel_ids: List[
        int
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
) -> List[dict]:
    """
    Given a list of channel ids, return the channel metadata for each
    """
    if len(channel_ids) == 0:
        return []
    channel_metadata_rows = (
        db.session()
        .using_bind("default")
        .execute(
            """
        SELECT
          id,
          created_at
        FROM
          channel
        WHERE
          id in :channel_ids
        ORDER BY
          created_at DESC
        """,
            {"channel_ids": channel_ids},
        )
        .fetchall()
    )

    return [
        dict(channel_id=channel_id, created_at=created_at)
        for channel_id, created_at in channel_metadata_rows
    ]


def get_message_metadata_for_channel_ids(
    channel_ids: List[
        int
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
) -> List[dict]:
    """
    Given a list of channel ids, return the message metadata for each
    """
    if len(channel_ids) == 0:
        return []
    message_metadata_per_channel = (
        db.session()
        .using_bind("default")
        .execute(
            """
        SELECT
          message.channel_id,
          count(message.id),
          max(message.created_at)
        FROM
          message
        WHERE
          message.channel_id in :channel_ids
        GROUP BY
          message.channel_id
        ORDER BY
          message.created_at DESC
        """,
            {"channel_ids": channel_ids},
        )
        .fetchall()
    )

    return [
        dict(
            channel_id=channel_id,
            message_count=message_count,
            latest_message_timestamp=latest_message_timestamp,
        )
        for channel_id, message_count, latest_message_timestamp in message_metadata_per_channel
    ]


def gather_metadata_for_channels(
    channel_ids: List[
        int
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
) -> ChannelMetadataStore:
    """
    Given a list of channel ids, gather metadata about those channels
    Metadata includes:
    - channel creation timestamp
    - latest message timestamp
    - message count
    """
    channel_metadata_store = ChannelMetadataStore()
    channel_meta = get_channel_metadata_for_channel_ids(
        channel_ids=channel_ids,
    )
    if len(channel_meta) != len(channel_ids):
        raise Exception("Unable to find all metadata for list of channel ids")
    for kws in channel_meta:
        channel_metadata_store.add_metadata(**kws)

    message_meta = get_message_metadata_for_channel_ids(
        channel_ids=channel_ids,
    )
    for kws in message_meta:
        channel_metadata_store.add_metadata(**kws)
    return channel_metadata_store


def filter_channels_by_message_count(
    channel_ids: List[
        int
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
    channel_metadata_store: Optional[ChannelMetadataStore] = None,
    min_count_of_messages_in_channel: int = 0,
) -> List[int]:
    """
    Given a list of channel ids, filter them based on the desired min message count
    channel_metadata_store can be sourced with `gather_metadata_for_channels`
    """
    # if one is not provided, make a new store
    if channel_metadata_store is None:
        channel_metadata_store = ChannelMetadataStore()
    # filter the channels to return based on the desired min message count
    filtered_channel_ids = []
    for channel_id in channel_ids:
        # if we dont resolve the metadata for a channel, we should not return it
        # metadata includes properties on the channel itself implying there was
        # some form of error in the aggregation process
        meta = channel_metadata_store.get(channel_id)
        if meta is not None and meta.message_count >= min_count_of_messages_in_channel:
            filtered_channel_ids.append(channel_id)
    return filtered_channel_ids


def sort_channels(
    channel_ids: list[int],
    channel_metadata_store: ChannelMetadataStore,
    sort_descending: bool = True,
) -> list[int]:
    """
    Sorts the list of channel ids using the details provided in
    channel_metadata_store (required).
    The sort priority is:
    1. latest message in channel
    2. channel creation timestamp
    """
    # short circuit if there are no channel ids to sort
    if len(channel_ids) == 0:
        return []

    def sorter(chan_id: int) -> datetime:
        meta = channel_metadata_store.get(chan_id)

        if meta is None:
            raise ValueError(f"Could not find metadata for channel id {chan_id}")
        chanel_created_timestamp = meta.created_at
        latest_message_timestamp = meta.latest_message_timestamp

        if latest_message_timestamp is not None:
            return latest_message_timestamp
        if chanel_created_timestamp is not None:
            return chanel_created_timestamp
        # in the event we dont have a created_at or latest_message_timestamp
        # return the oldest possible date to ensure this channel is sorted to
        # the very bottom
        return datetime.min

    sorted_channel_ids = sorted(
        channel_ids,
        key=sorter,
        reverse=sort_descending,
    )
    return sorted_channel_ids


def get_channel_ids_for_user(
    user: User,
    min_count_of_messages_in_channel: int = 0,
    sort_descending: bool = True,
) -> list[int]:
    """
    For a given user determine the ordered list of channel ids that should be
    returned based on the desired order and min message count
    """
    # find all the possible channel ids
    users_channel_ids = get_list_of_channel_ids_user_participates_in(
        user=user,
    )
    # gather metadata about those channels
    channel_metadata_store = gather_metadata_for_channels(
        channel_ids=users_channel_ids,
    )

    # filter the channels to return based on the desired min message count
    filtered_channel_ids = filter_channels_by_message_count(
        channel_ids=users_channel_ids,
        channel_metadata_store=channel_metadata_store,
        min_count_of_messages_in_channel=min_count_of_messages_in_channel,
    )
    # sort the channel ids based on the desired order
    sorted_channel_ids = sort_channels(
        channel_ids=filtered_channel_ids,
        channel_metadata_store=channel_metadata_store,
        sort_descending=sort_descending,
    )

    return sorted_channel_ids


def get_channels_by_id(
    channel_ids: List[int],
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[Channel]:
    """
    Given a list of channel ids, fetch them from the DB
    respects the limit and offset provided
    """
    # short circuit if there is no work to do
    if not channel_ids:
        return []

    # guard invalid limit
    if not limit or limit <= 0:
        limit = 10

    # guard invalid offset
    if not offset or offset <= 0:
        offset = 0

    channels_query = (
        db.session.query(Channel)
        .filter(Channel.id.in_(channel_ids))
        .order_by(sqlalchemy.func.field(Channel.id, *channel_ids))
        .limit(limit)
        .offset(offset)
        .subquery()
    )

    final_result = (
        db.session.query(Channel)
        .select_entity_from(channels_query)
        # perform the joins AFTER to ensure the joins dont interfere with the
        # limit. Without isouter, channels with no messages will not be returned
        .join(Channel.messages, isouter=True)
        .join(Channel.participants)
        .options(
            contains_eager(Channel.messages),
            contains_eager(Channel.participants),
        )
        .all()
    )

    return final_result


def filter_channels(
    channel_list: List[Channel],
    *,
    include_wallet: bool = True,
    include_no_messages: bool = True,
) -> List[Channel]:
    """
    Filters the provided list of channels based on the desired criteria
    """
    if not channel_list:
        return []

    filtered_channels = []
    for channel in channel_list:
        if channel.is_wallet:
            filtered_channels.append(channel) if include_wallet else None
        elif not channel.messages:
            filtered_channels.append(channel) if include_no_messages else None
        else:
            filtered_channels.append(channel)

    return filtered_channels
