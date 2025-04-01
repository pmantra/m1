from datetime import datetime
from itertools import chain

from sqlalchemy.orm import joinedload

from assessments.utils.assessment_exporter import (
    AssessmentExporter,
    AssessmentExportTopic,
)
from authn.models.user import User
from models.questionnaires import QuestionTypes
from storage.connection import db
from utils.log import logger
from views.schemas.FHIR.common import (
    FHIR_DATETIME_FORMAT,
    FLAGGED_EXTENSION_URL,
    FHIRVerificationStatusEnum,
    fhir_reference_from_model,
)
from views.schemas.FHIR.condition import FHIRClinicalStatusEnum, FHIRConditionSchema

log = logger(__name__)


class Condition:
    @classmethod
    def construct_fhir_condition_json(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls,
        identifiers,
        condition_text: str,
        subject: User,
        recorder: User,
        recorded_date: datetime,
        extensions=None,
        clinical_status_text=None,
        verification_status_text=None,
    ):
        def create_identifier(type_text, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            return {"type": {"text": type_text}, "value": str(value)}

        def create_coding(system: str, display: str, user_selected: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
            return {
                "coding": [
                    {
                        "system": system,
                        "display": display,
                        "userSelected": user_selected,
                    }
                ],
                "text": display,
            }

        condition = {
            "resourceType": "Condition",
            "identifier": [
                create_identifier(type_text, value) for type_text, value in identifiers
            ],
            "category": [{"text": "problem-list-item"}],
            "code": {"text": condition_text},
            "subject": fhir_reference_from_model(subject, custom_type="Patient"),
            "recordedDate": recorded_date,
            "recorder": fhir_reference_from_model(recorder, custom_type="Patient"),
            "meta": {},
        }
        if clinical_status_text:
            condition["clinicalStatus"] = create_coding(
                "http://hl7.org/fhir/ValueSet/condition-clinical", clinical_status_text
            )
        if verification_status_text:
            condition["verificationStatus"] = create_coding(
                "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                verification_status_text,
            )
        if extensions:
            condition["extension"] = extensions
        return condition

    @classmethod
    def get_conditions_by_user_id(cls, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = (
            db.session.query(User)
            .filter(User.id == user_id)
            .options(joinedload(User.health_profile))
            .one()
        )
        profile_data = user.health_profile.json if user.health_profile else {}
        current_conditions = profile_data.get(Condition.health_binder_fields_current)
        past_conditions = profile_data.get(Condition.health_binder_fields_past)
        condition_data = []
        recorded_date = user.health_profile.modified_at.strftime(FHIR_DATETIME_FORMAT)
        for condition in [current_conditions, past_conditions]:
            condition_data.append(
                {
                    "code": {"text": condition},
                    "recordedDate": recorded_date,
                },
            )
        schema = FHIRConditionSchema()
        return schema.dump(condition_data, many=True)

    health_binder_fields_current = "health_issues_current"
    health_binder_fields_past = "health_issues_past"

    @classmethod
    def get_assessment_conditions_by_user_id(cls, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = User.query.filter(User.id == user_id).one()
        exporter = AssessmentExporter.for_user_assessments(user)
        answers = exporter.all_answers_for(
            user, AssessmentExportTopic.FHIR, Condition.question_names
        )
        if answers is None:
            return []

        condition_data = cls.export_assessment_conditions(answers, user)
        schema = FHIRConditionSchema()
        return schema.dump(condition_data, many=True)

    @classmethod
    def export_assessment_conditions(cls, answers, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return chain.from_iterable(
            (
                (
                    Condition.export_assessment_condition(
                        assessment_data, condition, user
                    )
                    for condition in assessment_data.exported_answer
                )
                if isinstance(assessment_data.exported_answer, list)
                else [
                    Condition.export_assessment_condition(
                        assessment_data, assessment_data.exported_answer, user
                    )
                ]
            )
            for assessment_data in answers
        )

    @classmethod
    def export_assessment_condition(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        cls, exported_assessment_data, condition_text, user
    ):
        return Condition.construct_fhir_condition_json(
            identifiers=[
                ("user_id", str(user.id)),
                (
                    "needs_assessment_id",
                    str(exported_assessment_data.needs_assessment_id),
                ),
                ("question_id", str(exported_assessment_data.question_id)),
                ("question_name", exported_assessment_data.question_name),
            ],
            condition_text=condition_text,
            clinical_status_text=FHIRClinicalStatusEnum.active.value
            if exported_assessment_data.question_name
            in ["conditions_active", "existing_conditions"]
            else None,
            verification_status_text=FHIRVerificationStatusEnum.provisional.value,
            subject=user,
            recorded_date=exported_assessment_data.needs_assessment_modified_at.strftime(
                FHIR_DATETIME_FORMAT
            ),
            recorder=user,
            extensions=[
                {
                    "url": FLAGGED_EXTENSION_URL,
                    "extension": [{"url": "flagged", "valueBoolean": True}],
                }
                if cls._is_flagged_assessment(exported_assessment_data)
                else None
            ],
        )

    question_names = [
        "pregnancy_conditions",
        "existing_conditions",
        "past_pregnancy",
    ]

    @classmethod
    def get_from_questionnaire_answers_for_user(cls, answer_set, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        condition_answer = next(
            (
                ra
                for ra in answer_set.recorded_answers
                if ra.question.type == QuestionTypes.CONDITION
            ),
            None,
        )
        if not condition_answer:
            return []
        condition_data = []
        for condition_string in condition_answer.payload["items"]:
            condition_data.append(
                {
                    "identifier": [
                        {"type": {"text": "user"}, "value": f"{user.id}"},
                        {
                            "type": {"text": "health_binder_questionnaire_answer"},
                            "value": f"{condition_string}",
                        },
                    ],
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
                    "clinicalStatus": {"text": condition_string},
                    "category": [{"text": "problem-list-item"}],
                    "code": {"text": condition_string},
                    "subject": fhir_reference_from_model(user, custom_type="Patient"),
                    "recordedDate": answer_set.submitted_at.isoformat(),
                    "recorder": fhir_reference_from_model(user, custom_type="Patient"),
                    # Every condition is flaggable
                    "extension": [
                        {
                            "url": FLAGGED_EXTENSION_URL,
                            "extension": [{"url": "flagged", "valueBoolean": True}],
                        }
                        if cls._is_flagged_questionnaire_response(condition_string)
                        else None
                    ],
                }
            )
        schema = FHIRConditionSchema()
        return schema.dump(condition_data, many=True)

    @classmethod
    def _is_flagged_assessment(cls, exported_answer_data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Return True if the given export data is an area of concern to be marked High Risk in mPractice"""
        # TODO: placeholder for when we calculate high risk separately and don't flag everything
        # NOTE: there are questions for which some data is flagged, and some is not.
        return True

    @classmethod
    def _is_flagged_questionnaire_response(cls, condition_string):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Return True if the given export data is an area of concern to be marked High Risk in mPractice"""
        # TODO: placeholder for when we calculate high risk separately
        return True
