from __future__ import annotations

from traceback import format_exc
from typing import Tuple

import ddtrace.ext
import sqlalchemy.orm.scoping

from direct_payment.clinic.models.questionnaire_global_procedure import (
    QuestionnaireGlobalProcedure,
)
from direct_payment.treatment_procedure.models.treatment_procedure_recorded_answer_set import (
    TreatmentProcedureRecordedAnswerSet,
)
from models.questionnaires import Questionnaire, RecordedAnswerSet
from storage import connection
from utils.log import logger

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class TreatmentProcedureQuestionnaireRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    def read(
        self,
    ) -> Tuple[list[QuestionnaireGlobalProcedure], list[Questionnaire]] | None:
        questionnaire_global_procedures = self.session.query(
            QuestionnaireGlobalProcedure
        ).all()

        if not questionnaire_global_procedures:
            return None

        questionnaires = (
            self.session.query(Questionnaire)
            .join(
                QuestionnaireGlobalProcedure,
                QuestionnaireGlobalProcedure.questionnaire_id == Questionnaire.id,
            )
            .order_by(Questionnaire.sort_order)
            .distinct()  # wasn't getting dupe questionnaires without this, but added just in case
            .all()
        )

        # Due to the foreign key constraint, this should never happen, but adding just in case/
        # future-proofing against turning stuff into services w/o foreign key constraints
        if not questionnaires:
            return None

        return (
            questionnaire_global_procedures,
            questionnaires,
        )

    @trace_wrapper
    def create_treatment_procedure_answer_set(
        self,
        fertility_clinic_id: int,
        questionnaire_id: int,
        questions: list[dict],
        treatment_procedure_id: int,
        user_id: int,
    ) -> RecordedAnswerSet | None:
        try:
            recorded_answer_set = RecordedAnswerSet.create(
                {
                    "source_user_id": user_id,
                    "questionnaire_id": questionnaire_id,
                    "recorded_answers": questions,
                },
            )

            treatment_procedure_recorded_answer_set = (
                TreatmentProcedureRecordedAnswerSet(
                    treatment_procedure_id=treatment_procedure_id,
                    recorded_answer_set_id=recorded_answer_set.id,
                    questionnaire_id=questionnaire_id,
                    user_id=user_id,
                    fertility_clinic_id=fertility_clinic_id,
                )
            )

            self.session.add(treatment_procedure_recorded_answer_set)
            # Delete the treatment_procedures_needing_questionnaires entry
            # affiliated with this treatment_procedure.
            self.delete_tp_needing_questionnaire(treatment_procedure_id)
            self.session.commit()
        except Exception as e:
            log.error(
                "Failed to create treatment procedure recorded answer set record",
                error=str(e),
                traceback=format_exc(),
            )
            self.session.rollback()
            return None

        return treatment_procedure_recorded_answer_set

    def delete_tp_needing_questionnaire(self, treatment_procedure_id: int) -> None:
        """
        Deletes all (should be 1) entries in the
        treatment_procedures_needing_questionnaires with
        the matching treatment_procedure_id.
        """
        self.session.execute(
            "DELETE FROM treatment_procedures_needing_questionnaires WHERE treatment_procedure_id = :tp_id;",
            {"tp_id": treatment_procedure_id},
        )
