from marshmallow_v1 import fields

from views.questionnaires import QuestionnaireSchema
from views.schemas.common import MavenSchema


class TreatmentProcedureQuestionnaireSchema(QuestionnaireSchema):
    global_procedure_ids = fields.List(fields.String)


class TreatmentProcedureQuestionnairesSchema(MavenSchema):
    questionnaires = fields.Nested(TreatmentProcedureQuestionnaireSchema, many=True)


class TreatmentProcedureRecordedAnswerPOSTSchema(MavenSchema):
    question_id = fields.String(required=True)
    answer_id = fields.String(required=True)


class TreatmentProcedureQuestionnairePOSTSchema(MavenSchema):
    questionnaire_id = fields.String(required=True)
    questions = fields.Nested(TreatmentProcedureRecordedAnswerPOSTSchema, many=True)


class TreatmentProcedureQuestionnairesPOSTRequestSchema(MavenSchema):
    questionnaires = fields.Nested(TreatmentProcedureQuestionnairePOSTSchema, many=True)
    treatment_procedure_id = fields.Integer(required=True)
