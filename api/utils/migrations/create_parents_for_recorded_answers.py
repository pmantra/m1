from collections import defaultdict

import snowflake
from sqlalchemy.orm import load_only

from appointments.utils.appointment_utils import check_appointment_by_ids
from models.questionnaires import (
    Question,
    QuestionSet,
    RecordedAnswer,
    RecordedAnswerSet,
)
from storage.connection import db


def create(force=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    log_prefix = "[live]" if force else "[dry run]"

    # STEP 1...
    # query all the recorded answers that are missing a parent set and group them into their sets
    parentless_answer_count = 0
    rec_answer_sets_by_appt = defaultdict(list)
    appointment_ids = []
    for ra in RecordedAnswer.query.options(
        load_only("id", "user_id", "appointment_id")
    ).filter(
        RecordedAnswer.appointment_id != None,
        RecordedAnswer.recorded_answer_set_id == None,
    ):
        appt_id_and_user_id = (ra.appointment_id, ra.user_id)
        appointment_ids.append(ra.appointment_id)
        rec_answer_sets_by_appt[appt_id_and_user_id].append(ra.id)
        parentless_answer_count += 1
    print(
        f"{log_prefix} Collecting {parentless_answer_count} answers without parents into {len(rec_answer_sets_by_appt)} recorded answer sets."
    )
    ra = None

    check_appointment_by_ids(appointment_ids, True)

    # STEP 2...
    # create an answer set and tie the recorded answers to it
    for (
        (appointment_id, user_id),
        recorded_answer_ids,
    ) in rec_answer_sets_by_appt.items():
        ra0_id = recorded_answer_ids[0]
        questionnaire_id = (
            db.session.query(QuestionSet.questionnaire_id)
            .join(Question)
            .join(RecordedAnswer)
            .filter(RecordedAnswer.id == ra0_id)
            .scalar()
        )
        rec_answer_set = RecordedAnswerSet(
            submitted_at=snowflake.to_datetime(ra0_id),
            source_user_id=user_id,
            draft=False,
            questionnaire_id=questionnaire_id,
            appointment_id=appointment_id,
        )
        print(
            f"{log_prefix} Created recorded answer set for appointment {appointment_id} and user {user_id} with {len(recorded_answer_ids)} answers."
        )
        if force:
            db.session.add(rec_answer_set)
            db.session.commit()
            db.session.execute(
                f"UPDATE recorded_answer SET recorded_answer_set_id={rec_answer_set.id} WHERE id IN ({','.join(str(id_) for id_ in recorded_answer_ids)});"
            )
            db.session.commit()
        else:
            db.session.rollback()

    print(f"{log_prefix} All done.")
