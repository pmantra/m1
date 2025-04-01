from sqlalchemy.orm import aliased

from appointments.models.appointment import Appointment
from appointments.models.constants import PRIVACY_CHOICES
from appointments.models.schedule import Schedule
from messaging.models.messaging import ChannelUsers, Message
from models.products import Product
from storage.connection import db


def get_member_access_by_practitioner(practitioner_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Returns a query that retrieves all of the id's of member profiles that
    the passed in practitioner has access to.  Practitioners have access to the
    member profile of users who have sent them at least one message or
    they have at least 1 non-cancelled, non-anonymous appointment.
    """
    practitioner_channel_user = aliased(ChannelUsers)
    member_channel_user = aliased(ChannelUsers)
    messaging_history = (
        db.session.query(member_channel_user.user_id)
        .join(
            practitioner_channel_user,
            (member_channel_user.channel_id == practitioner_channel_user.channel_id)
            & (member_channel_user.user_id != practitioner_channel_user.user_id),
        )
        .join(
            Message,
            (Message.channel_id == practitioner_channel_user.channel_id)
            & (Message.user_id == member_channel_user.user_id),
        )
        .filter(practitioner_channel_user.user_id == practitioner_id)
    )
    non_cancelled_appts = (
        db.session.query(Schedule.user_id)
        .join(Appointment)
        .join(Product)
        .filter(
            Product.user_id == practitioner_id,
            Appointment.cancelled_at == None,
            Appointment.privacy != PRIVACY_CHOICES.anonymous,
        )
    )
    return messaging_history.union(non_cancelled_appts)
