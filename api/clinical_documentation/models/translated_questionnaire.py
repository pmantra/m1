from dataclasses import dataclass

from clinical_documentation.models import questionnaire


@dataclass
class TranslatedAnswerStruct(questionnaire.AnswerStruct):
    pass


@dataclass
class TranslatedQuestionStruct(questionnaire.QuestionStruct):
    pass


@dataclass
class TranslatedQuestionSetStruct(questionnaire.QuestionSetStruct):
    pass


@dataclass
class TranslatedQuestionnaireStruct(questionnaire.QuestionnaireStruct):
    pass
