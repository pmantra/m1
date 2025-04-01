from __future__ import annotations

from sqlalchemy.orm.scoping import scoped_session

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from storage import connection
from utils.log import logger

log = logger(__name__)


class TreatmentProcedureService:
    def __init__(
        self,
        session: scoped_session | None = None,
    ):
        self.session = session or connection.db.session
        self.treatment_procedure_repo = TreatmentProcedureRepository(
            session=self.session
        )

    def get_treatment_procedure_by_ids(
        self, ids: list[int]
    ) -> list[TreatmentProcedure]:
        return self.treatment_procedure_repo.get_treatments_by_ids(ids)
