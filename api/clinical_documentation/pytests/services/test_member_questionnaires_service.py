from unittest.mock import patch

from clinical_documentation.models.questionnaire import (
    AnswerStruct,
    QuestionnaireStruct,
    QuestionSetStruct,
    QuestionStruct,
)
from clinical_documentation.models.translated_questionnaire import (
    TranslatedAnswerStruct,
    TranslatedQuestionnaireStruct,
    TranslatedQuestionSetStruct,
    TranslatedQuestionStruct,
)
from clinical_documentation.services.member_questionnaire_service import (
    MemberQuestionnairesService,
)


@patch(
    "clinical_documentation.repository.member_questionnaires.MemberQuestionnaireRepository.get_questionnaires"
)
def test_get_member_questionnaires(
    get_questionnaires,
):
    questionnaires = [
        QuestionnaireStruct(
            id_=1,
            oid="member_rating_survey",
            sort_order=1,
            title_text="title",
            description_text="description",
            intro_appointment_only=True,
            track_name="track",
            question_sets=[
                QuestionSetStruct(
                    id_=2,
                    questionnaire_id=1,
                    sort_order=2,
                    oid="",
                    questions=[
                        QuestionStruct(
                            id_=3,
                            oid="",
                            question_set_id=2,
                            sort_order=3,
                            label="label",
                            type_="radio",
                            required=False,
                            answers=[
                                AnswerStruct(id_=4, oid="", text="answer", sort_order=4)
                            ],
                        )
                    ],
                )
            ],
            trigger_answer_ids=[],
        )
    ]

    expected_questionnaires = [
        TranslatedQuestionnaireStruct(
            id_=1,
            oid="member_rating_survey",
            sort_order=1,
            title_text="title",
            description_text="description",
            intro_appointment_only=True,
            track_name="track",
            question_sets=[
                TranslatedQuestionSetStruct(
                    id_=2,
                    questionnaire_id=1,
                    sort_order=2,
                    oid="",
                    questions=[
                        TranslatedQuestionStruct(
                            id_=3,
                            oid="",
                            question_set_id=2,
                            sort_order=3,
                            label="label",
                            type_="radio",
                            required=False,
                            answers=[
                                TranslatedAnswerStruct(
                                    id_=4, oid="", text="answer", sort_order=4
                                )
                            ],
                        )
                    ],
                )
            ],
            trigger_answer_ids=[],
        )
    ]

    get_questionnaires.return_value = questionnaires
    returned_questionnaires = MemberQuestionnairesService().get_questionnaires()

    assert expected_questionnaires == returned_questionnaires
