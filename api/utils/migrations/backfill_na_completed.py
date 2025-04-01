from models.enterprise import NeedsAssessment
from storage.connection import db


def backfill_na_completed():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for na in db.session.query(NeedsAssessment).all():
        na.completed = na.status == "completed"
        db.session.commit()
