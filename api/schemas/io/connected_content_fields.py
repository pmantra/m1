from models.marketing import ConnectedContentField
from storage.connection import db


def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        {"name": c.name}
        for c in ConnectedContentField.query.order_by(ConnectedContentField.name)
    ]


def restore(cc):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.bulk_insert_mappings(ConnectedContentField, cc)
