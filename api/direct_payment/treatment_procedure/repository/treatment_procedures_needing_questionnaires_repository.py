from __future__ import annotations

import ddtrace.ext
import sqlalchemy.orm.scoping

from direct_payment.treatment_procedure.models.treatment_proceedure_needing_questionnaire import (
    TreatmentProceduresNeedingQuestionnaires,
)
from storage import connection
from utils.log import logger

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)
metric_prefix = "api.direct_payment.treatment_procedure.repository.treatment_procedure"


class TreatmentProceduresNeedingQuestionnairesRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession | None = None):
        self.session = session or connection.db.session

    @trace_wrapper
    def create_tpnq_from_treatment_procedure_id(
        self, treatment_procedure_id: int
    ) -> TreatmentProceduresNeedingQuestionnaires:
        """
        Creates, adds, and returns a TreatmentProceduresNeedingQuestionnaires affiliated with a given
        treatment_procedure_id.
        This method does NOT COMMIT.
        """
        tpnq = TreatmentProceduresNeedingQuestionnaires(
            treatment_procedure_id=treatment_procedure_id
        )
        self.session.add(tpnq)
        return tpnq

    @trace_wrapper
    def get_tpnqs_by_treatment_procedure_ids(
        self, treatment_procedure_ids: list[int]
    ) -> list[TreatmentProceduresNeedingQuestionnaires]:
        return (
            self.session.query(TreatmentProceduresNeedingQuestionnaires)
            .filter(
                TreatmentProceduresNeedingQuestionnaires.treatment_procedure_id.in_(
                    treatment_procedure_ids
                )
            )
            .all()
        )
