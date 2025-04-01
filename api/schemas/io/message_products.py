from messaging.models.messaging import MessageProduct
from storage.connection import db

from .sorting import sorted_by


@sorted_by("number_of_messages")
def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(
            number_of_messages=mp.number_of_messages,
            price=mp.price,
            is_active=mp.is_active,
        )
        for mp in MessageProduct.query
    ]


def restore(message_products):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.bulk_insert_mappings(MessageProduct, message_products)
