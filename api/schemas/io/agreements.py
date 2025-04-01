from models.profiles import Agreement
from storage.connection import db

from .sorting import sorted_by


@sorted_by("name", "version")
def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(name=a.name.value, version=a.version, html=a.html) for a in Agreement.query
    ]


def restore(aa):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.bulk_insert_mappings(Agreement, aa)
