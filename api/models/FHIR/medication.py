from sqlalchemy.orm import joinedload

from authn.models.user import User
from models.questionnaires import QuestionTypes
from storage.connection import db
from views.schemas.FHIR.common import fhir_reference_from_model
from views.schemas.FHIR.medication import (
    FHIRMedicationStatementSchema,
    MedicationStatementStatusEnum,
)


class MedicationStatement:
    """Queries and retrieves the medication statement."""

    @classmethod
    def get_medication_statement_by_user_id(cls, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = (
            db.session.query(User)
            .filter(User.id == user_id)
            .options(joinedload(User.health_profile))
            .one()
        )
        return cls.get_medication_statement_by_user(user)

    @classmethod
    def get_medication_statement_by_user(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        profile_data = user.health_profile.json if user.health_profile else {}
        current_medications = profile_data.get(
            MedicationStatement.health_binder_fields_current
        )
        past_medications = profile_data.get(
            MedicationStatement.health_binder_fields_past
        )
        medication_data = []
        for field, medications in [
            (MedicationStatement.health_binder_fields_current, current_medications),
            (MedicationStatement.health_binder_fields_past, past_medications),
        ]:
            if medications:
                data = {
                    "status": MedicationStatementStatusEnum.active.value
                    if field == MedicationStatement.health_binder_fields_current
                    else MedicationStatementStatusEnum.unknown.value,
                    "dateAsserted": user.health_profile.modified_at,
                    "note": [{"text": medications}],
                }
                medication_data.append(data)
        schema = FHIRMedicationStatementSchema()
        return schema.dump(medication_data, many=True)

    # field names taken from the HealthProfileSchema
    health_binder_fields_current = "medications_current"
    health_binder_fields_past = "medications_past"

    @classmethod
    def get_from_questionnaire_answers_for_user(cls, answer_set, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        medication_answer = next(
            (
                ra
                for ra in answer_set.recorded_answers
                if ra.question.type == QuestionTypes.MEDICATION
            ),
            None,
        )
        if not medication_answer:
            return []
        medication_data = []
        for medication in medication_answer.payload["items"]:
            medication_data.append(
                {
                    "identifier": [
                        {"type": {"text": "user"}, "value": f"{user.id}"},
                        {
                            "type": {"text": "health_binder_questionnaire_answer"},
                            "value": f"{medication}",
                        },
                    ],
                    "status": cls.medication_status_from_input(medication["status"]),
                    "subject": fhir_reference_from_model(user),
                    "dateAsserted": answer_set.submitted_at.isoformat(),
                    "informationSource": fhir_reference_from_model(user),
                    "note": [
                        {
                            "author": fhir_reference_from_model(user),
                            "text": medication["label"],
                        }
                    ],
                }
            )
        schema = FHIRMedicationStatementSchema()
        return schema.dump(medication_data, many=True)

    @classmethod
    def medication_status_from_input(cls, status_input):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if status_input == "current":
            return MedicationStatementStatusEnum.active.value
        elif status_input == "past":
            return MedicationStatementStatusEnum.completed.value
        else:
            return MedicationStatementStatusEnum.unknown.value
