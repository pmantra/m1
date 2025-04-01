"""
Get channels that have an intro message sent in 2024

Get created at of that intro message

Check if channel has a message written by member with created at < intro message.created_at +24 hrs

"""


import datetime

from sqlalchemy import or_

from messaging.models.messaging import Channel, Message
from storage.connection import db


@db.from_app_replica
def main() -> None:

    jan_1st_2024 = datetime.date(2024, 1, 1)

    intro_1 = "Hi and welcome to Maven!"
    intro_2 = "Hi there, welcome!"

    # from_app_replica

    messages_tuples = (
        db.session.query(Message.id, Message.created_at, Message.channel_id)
        .filter(Message.created_at >= jan_1st_2024)
        .filter(or_(Message.body.contains(intro_1), Message.body.contains(intro_2)))
        .all()
    )

    n_messages = len(messages_tuples)
    # some channels might unexpectedly have more than 1 intro message
    list_of_unique_channels = list({t[2] for t in messages_tuples})
    n_unique_channels = len(list_of_unique_channels)

    print(f"n_messages: {n_messages}")  # noqa
    print(f"n_unique_channels: {n_unique_channels}")  # noqa
    print(f"difference: {n_messages - n_unique_channels}")  # noqa

    # Create dic to map channels to intro message created at
    channels_to_message_created_at = {}
    for message_tuple in messages_tuples:
        # m_id = message_tuple[0]
        m_created_at = message_tuple[1]
        c_id = message_tuple[2]
        if not (c_id in channels_to_message_created_at):
            channels_to_message_created_at[c_id] = m_created_at
        else:  # case there are 2 intro messages in channel, lets use the date of the most recently sent intro appt
            if m_created_at > channels_to_message_created_at[c_id]:
                channels_to_message_created_at[c_id] = m_created_at

    # Now for every channel, check if any message exist in channel written by member before 24 hrs from intro message
    errors = []
    responded_in_24_hrs = 0
    counter = 0
    for c_id in list_of_unique_channels:
        try:
            channel = Channel.query.get(c_id)
            member_id = channel.member.id
            channel_messages = channel.messages
            for m in channel_messages:
                if not m.user:
                    errors.append(f"{m.channel_id}|{m.id} message has no user")
                    continue
                if (
                    m.user.id == member_id
                    and m.created_at > channels_to_message_created_at[c_id]
                    and m.created_at
                    < channels_to_message_created_at[c_id]
                    + datetime.timedelta(hours=24)
                ):
                    responded_in_24_hrs += 1
                    break  # dont count a channel more than once
        except Exception as e:
            errors.append(str(e))
        counter += 1
        if counter % 100 == 0:
            print(f"processed {counter} of {n_unique_channels} channels")  # noqa

    fraction_of_intro_messages_responded_in_24_hrs = responded_in_24_hrs / counter
    num_errors = len(errors)
    print(f"errors: {num_errors}")  # noqa

    from pprint import pprint

    pprint(errors)  # noqa

    print(  # noqa
        f"fraction_of_intro_messages_responded_in_24_hrs: {fraction_of_intro_messages_responded_in_24_hrs}"
    )


main()
