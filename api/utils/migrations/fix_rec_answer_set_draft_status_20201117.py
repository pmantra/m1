from models.questionnaires import RecordedAnswerSet
from storage.connection import db


def fix():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # There will be only a handful, created between 11/16/2020 morning and 11/17/2020 noon
    # Any recorded answer set that has a draft state at this time (11/17/2020) has it in error,
    # since draft functionality is not yet supported by clients.
    RecordedAnswerSet.query.filter(RecordedAnswerSet.draft == True).update(
        {"draft": False}
    )
    db.session.commit()
