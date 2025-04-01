from appointments.models.cancellation_policy import CancellationPolicy
from storage.connection import db


def restore() -> None:
    defaults = [
        {
            "name": "strict",
            "refund_0_hours": 0,
            "refund_2_hours": 0,
            "refund_6_hours": 0,
            "refund_12_hours": 0,
            "refund_24_hours": 0,
            "refund_48_hours": 0,
        },
        {
            "name": "moderate",
            "refund_0_hours": 0,
            "refund_2_hours": 0,
            "refund_6_hours": 0,
            "refund_12_hours": 0,
            "refund_24_hours": 50,
            "refund_48_hours": 50,
        },
        {
            "name": "flexible",
            "refund_0_hours": 0,
            "refund_2_hours": 0,
            "refund_6_hours": 0,
            "refund_12_hours": 0,
            "refund_24_hours": 100,
            "refund_48_hours": 100,
        },
        {
            "name": "conservative",
            "refund_0_hours": 50,
            "refund_2_hours": 100,
            "refund_6_hours": 100,
            "refund_12_hours": 100,
            "refund_24_hours": 100,
            "refund_48_hours": 100,
        },
    ]
    db.session.bulk_insert_mappings(CancellationPolicy, defaults)
