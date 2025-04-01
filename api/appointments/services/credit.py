import datetime

from utils.log import logger

log = logger(__name__)


def calculate_total_available_credits(user, start_date):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    active_date = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)

    available_credits = [
        c
        for c in user.credits
        if (
            c.appointment_id is None
            and c.used_at is None
            and (c.activated_at is None or c.activated_at <= active_date)
            and (c.expires_at is None or c.expires_at >= start_date)
        )
    ]

    return sum(a.amount for a in available_credits) if available_credits else 0
