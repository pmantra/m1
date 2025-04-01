from __future__ import annotations

from collections import defaultdict

from flask import request
from flask_restful import abort
from marshmallow_v1.exceptions import UnmarshallingError
from werkzeug.exceptions import HTTPException

from direct_payment.clinic.resources.clinic_auth import ClinicAuthorizedResource
from direct_payment.treatment_procedure.repository import (
    treatment_procedure_questionnaire,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from direct_payment.treatment_procedure.schemas.treatment_procedure_questionnaire import (
    TreatmentProcedureQuestionnairesPOSTRequestSchema,
    TreatmentProcedureQuestionnairesSchema,
)
from utils.log import logger

log = logger(__name__)


class TreatmentProcedureQuestionnairesResource(ClinicAuthorizedResource):
    def __init__(self) -> None:
        super().__init__()
        self.questionnaire_global_procedure_repository = (
            treatment_procedure_questionnaire.TreatmentProcedureQuestionnaireRepository()
        )

    def get(self) -> dict[str, dict]:
        result = self.questionnaire_global_procedure_repository.read()

        if not result:
            abort(404, message="No global procedure questionnaires found")

        (
            questionnaire_global_procedures,
            questionnaires,
        ) = result

        questionnaire_id_to_global_procedure_ids: dict[int, list[str]] = defaultdict(
            list
        )
        # Map a questionnaire_id to a list of the global_procedure_ids
        # affiliated with that questionnaire_id.

        for questionnaire_global_procedure in questionnaire_global_procedures:
            questionnaire_id_to_global_procedure_ids[
                questionnaire_global_procedure.questionnaire_id
            ].append(questionnaire_global_procedure.global_procedure_id)

        if len(questionnaire_id_to_global_procedure_ids) != len(questionnaires):
            log.warning("Mismatch in questionnaire global procedures")

        for questionnaire in questionnaires:
            if questionnaire.id in questionnaire_id_to_global_procedure_ids:
                questionnaire.global_procedure_ids = (
                    questionnaire_id_to_global_procedure_ids[questionnaire.id]
                )

        schema = TreatmentProcedureQuestionnairesSchema()

        return schema.dump({"questionnaires": questionnaires})

    def post(self) -> dict[str, bool]:
        """Endpoint for submitting a questionnaire for a treatment procedure."""
        user_id = self.user.id
        schema = TreatmentProcedureQuestionnairesPOSTRequestSchema()

        treatment_procedure_id = None
        questionnaires = None

        try:
            args = schema.load(request.json if request.is_json else None).data
            treatment_procedure_id = args.get("treatment_procedure_id")
            questionnaires = args.get("questionnaires")
        except UnmarshallingError:
            log.warning("Called with invalid payload")

        if not (treatment_procedure_id and questionnaires):
            abort(
                400,
                message="Invalid request body. Must include treatment_procedure_id and questionnaires",
            )

        treatment_procedure = None

        try:
            treatment_procedure = TreatmentProcedureRepository().read(
                treatment_procedure_id=treatment_procedure_id
            )
        except HTTPException:
            abort(400, message="Could not find treatment procedure")

        fertility_clinic_id = treatment_procedure.fertility_clinic_id  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "fertility_clinic_id"

        for questionnaire in questionnaires:  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "__iter__" (not iterable)
            treatment_procedure_recorded_answer_set = self.questionnaire_global_procedure_repository.create_treatment_procedure_answer_set(
                fertility_clinic_id=fertility_clinic_id,
                questionnaire_id=questionnaire.get("questionnaire_id"),
                questions=questionnaire.get("questions"),
                treatment_procedure_id=treatment_procedure_id,
                user_id=user_id,
            )

            if not treatment_procedure_recorded_answer_set:
                abort(
                    500,
                    message="Could not create treatment procedure recorded answer set",
                )

        return {"success": True}
