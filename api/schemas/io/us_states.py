from models.profiles import State
from storage.connection import db
from utils.geography import us_states


def restore():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    db.session.bulk_insert_mappings(
        State, [{"name": n, "abbreviation": a} for a, n in us_states.items()]
    )
