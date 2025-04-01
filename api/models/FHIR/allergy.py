from sqlalchemy.orm import joinedload

from authn.models.user import User
from models.questionnaires import QuestionTypes
from storage.connection import db
from views.schemas.FHIR.allergy import FHIRAllergyIntoleranceSchema
from views.schemas.FHIR.common import (
    FLAGGED_EXTENSION_URL,
    FHIRVerificationStatusEnum,
    fhir_reference_from_model,
)

# nonsense made-up url to be replaced when real fhir comes along
ALLERGY_INTOLERANCE_TYPE_URL = (
    "https://mavenclinic.com/fhir/StructureDefinition/allergy"
)


class AllergyIntolerance:
    """Queries and retrieves the allergy statement."""

    @classmethod
    def get_allergy_intolerance_by_user_id(cls, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = (
            db.session.query(User)
            .filter(User.id == user_id)
            .options(joinedload(User.health_profile))
            .one()
        )
        return cls.get_allergy_intolerance_by_user(user)

    @classmethod
    def get_allergy_intolerance_by_user(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        profile_data = user.health_profile.json if user.health_profile else {}
        # NOTE: allergy values are recorded as a csv string on web, iOS, and android
        allergy_medications = profile_data.get(
            AllergyIntolerance.health_binder_field_medications
        )
        allergy_food = profile_data.get(AllergyIntolerance.health_binder_field_food)
        allergy_data = []
        for _, allergy_value in [
            (AllergyIntolerance.health_binder_field_medications, allergy_medications),
            (AllergyIntolerance.health_binder_field_food, allergy_food),
        ]:
            if allergy_value:
                for allergy in allergy_value.split(","):
                    data = {
                        "clinicalStatus": {"text": allergy},
                    }
                    allergy_data.append(data)
        schema = FHIRAllergyIntoleranceSchema()
        return schema.dump(allergy_data, many=True)

    # field name taken from the HealthProfileSchema
    health_binder_field_medications = "medications_allergies"
    health_binder_field_food = "food_allergies"

    @classmethod
    def get_from_questionnaire_answers_for_user(cls, answer_set, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        allergy_data = []
        allergy_answer = next(
            (
                a
                for a in answer_set.recorded_answers
                if a.question.type == QuestionTypes.ALLERGY_INTOLERANCE
            ),
            None,
        )
        if allergy_answer:
            allergy_input = allergy_answer.payload.get("items", [])
            for allergy in allergy_input:
                allergy_data.append(
                    {
                        "identifier": [
                            {"type": {"text": "user"}, "value": f"{user.id}"},
                            {
                                "type": {"text": "health_binder_questionnaire_answer"},
                                "value": f"{allergy}",
                            },
                        ],
                        "clinicalStatus": {"text": allergy["label"]},
                        "verificationStatus": {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                                    "display": FHIRVerificationStatusEnum.provisional.value,
                                    "userSelected": True,
                                }
                            ],
                            "text": FHIRVerificationStatusEnum.provisional.value,
                        },
                        # TODO: convert user refs to patient references once we have that opportunity
                        "patient": fhir_reference_from_model(user),
                        "recordedDate": answer_set.submitted_at.isoformat(),
                        "recorder": fhir_reference_from_model(user),
                        "reaction": [{"description": allergy["label"]}],
                        # Every allergy is flaggable
                        "extension": [
                            {
                                "url": FLAGGED_EXTENSION_URL,
                                "extension": [{"url": "flagged", "valueBoolean": True}],
                            },
                            {
                                "url": ALLERGY_INTOLERANCE_TYPE_URL,
                                "extension": [
                                    {"url": "type", "valueString": allergy["type"]}
                                ],
                            },
                        ],
                    }
                )
        schema = FHIRAllergyIntoleranceSchema()
        return schema.dump(allergy_data, many=True)
