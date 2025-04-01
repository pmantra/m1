from __future__ import annotations

import ddtrace.ext
import sqlalchemy.orm.scoping

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from direct_payment.treatment_procedure.models.treatment_proceedure_needing_questionnaire import (
    TreatmentProceduresNeedingQuestionnaires,
)
from storage import connection
from storage.connector import RoutingSession
from utils.log import logger

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class TreatmentProceduresNeedingQuestionnairesRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession | RoutingSession | None = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    def create_tpnq_from_treatment_procedure_id(
        self,
        *,
        treatment_procedure_id: int,
    ) -> TreatmentProceduresNeedingQuestionnaires:
        """
        Creates and returns a TreatmentProceduresNeedingQuestionnaires. Commits to the DB.
        """
        tpnq = TreatmentProceduresNeedingQuestionnaires(
            treatment_procedure_id=treatment_procedure_id,
        )
        self.session.add(tpnq)
        return tpnq

    @trace_wrapper
    def get_tpnqs_by_treatment_procedure_id(
        self, treatment_procedure_ids: list[int]
    ) -> list[TreatmentProceduresNeedingQuestionnaires]:
        return (
            self.session.query(TreatmentProceduresNeedingQuestionnaires)
            .filter(TreatmentProcedure.id.in_(treatment_procedure_ids))
            .all()
        )
