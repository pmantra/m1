from models.marketing import TextCopy
from storage.connection import db

from .sorting import sorted_by


@sorted_by("name")
def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [dict(name=t.name, content=t.content) for t in TextCopy.query]


def restore(tt):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.bulk_insert_mappings(TextCopy, tt)
