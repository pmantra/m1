from unittest import mock

import flask_babel

from clinical_documentation.models.translated_questionnaire import (
    TranslatedAnswerStruct,
    TranslatedQuestionnaireStruct,
    TranslatedQuestionSetStruct,
    TranslatedQuestionStruct,
)
from clinical_documentation.services.member_questionnaire_service import (
    MemberQuestionnairesService,
)
from pytests.db_util import enable_db_performance_warnings


def test_get_member_questionnaires(
    client,
    db,
    factories,
    api_helpers,
    enterprise_user,
):
    questionnaires = [
        factories.EmptyQuestionnaireFactory.create(
            oid="cancellation_survey", sort_order=1
        ),
        factories.EmptyQuestionnaireFactory.create(
            oid="member_rating_v2", sort_order=0
        ),
    ]

    answers = []
    for questionnaire in questionnaires:
        for i in range(0, 2):
            qs = factories.EmptyQuestionSetFactory.create(
                questionnaire_id=questionnaire.id,
                oid=f"{questionnaire.oid},{i}",
                sort_order=i,
            )
            for j in range(0, 2):
                q = factories.EmptyQuestionFactory.create(
                    question_set_id=qs.id, label=f"{i},{j}", sort_order=1 - j
                )
                if j:
                    a = factories.AnswerFactory.create(
                        question_id=q.id, text=f"{i},{j}", sort_order=0
                    )
                    answers.append(a)

    for i in range(0, 2):
        insert_statement = f"INSERT INTO questionnaire_trigger_answer (answer_id, questionnaire_id) VALUES ({answers[i].id}, {questionnaires[i].id})"
        db.session.execute(insert_statement)

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=10,
    ):
        res = client.get(
            "/api/v2/clinical_documentation/member_questionnaires",
            headers=api_helpers.json_headers(enterprise_user),
        )

    actual = [
        {
            "oid": questionnaire["oid"],
            "sort_order": questionnaire["sort_order"],
            "question_sets": [
                {
                    "oid": question_set["oid"],
                    "sort_order": question_set["sort_order"],
                    "questions": [
                        {
                            "label": question["label"],
                            "sort_order": question["sort_order"],
                            "answers": [
                                {"text": answer["text"]}
                                for answer in question["answers"]
                            ],
                        }
                        for question in question_set["questions"]
                    ],
                }
                for question_set in questionnaire["question_sets"]
            ],
            "trigger_answer_ids": questionnaire["trigger_answer_ids"],
        }
        for questionnaire in res.json["questionnaires"]
    ]
    expected = [
        {
            "oid": "member_rating_v2",
            "sort_order": 0,
            "question_sets": [
                {
                    "oid": "member_rating_v2,0",
                    "sort_order": 0,
                    "questions": [
                        {"label": "0,1", "sort_order": 0, "answers": [{"text": "0,1"}]},
                        {"label": "0,0", "sort_order": 1, "answers": []},
                    ],
                },
                {
                    "oid": "member_rating_v2,1",
                    "sort_order": 1,
                    "questions": [
                        {"label": "1,1", "sort_order": 0, "answers": [{"text": "1,1"}]},
                        {"label": "1,0", "sort_order": 1, "answers": []},
                    ],
                },
            ],
            "trigger_answer_ids": [f"{answers[1].id}"],
        },
        {
            "oid": "cancellation_survey",
            "sort_order": 1,
            "question_sets": [
                {
                    "oid": "cancellation_survey,0",
                    "sort_order": 0,
                    "questions": [
                        {"label": "0,1", "sort_order": 0, "answers": [{"text": "0,1"}]},
                        {"label": "0,0", "sort_order": 1, "answers": []},
                    ],
                },
                {
                    "oid": "cancellation_survey,1",
                    "sort_order": 1,
                    "questions": [
                        {"label": "1,1", "sort_order": 0, "answers": [{"text": "1,1"}]},
                        {"label": "1,0", "sort_order": 1, "answers": []},
                    ],
                },
            ],
            "trigger_answer_ids": [f"{answers[0].id}"],
        },
    ]
    assert expected == actual

    for questionnaire in res.json["questionnaires"]:
        assert isinstance(questionnaire["id"], str)
        for trigger_answer_id in questionnaire["trigger_answer_ids"]:
            assert isinstance(trigger_answer_id, str)
        for question_set in questionnaire["question_sets"]:
            assert isinstance(question_set["id"], str)
            for question in question_set["questions"]:
                assert isinstance(question["id"], str)
                for answer in question["answers"]:
                    assert isinstance(answer["id"], str)


def test_localize_questionnaires():
    # All of these OIDs are derived from the *.po translation files.
    questionnaire = TranslatedQuestionnaireStruct(
        oid="cancellation_survey",
        id_=0,
        sort_order=0,
        title_text="",
        description_text="",
        intro_appointment_only=False,
        track_name="",
        trigger_answer_ids=[],
        question_sets=[
            TranslatedQuestionSetStruct(
                oid="cancellation_survey_question_set",
                id_=0,
                questionnaire_id=0,
                sort_order=0,
                questions=[
                    TranslatedQuestionStruct(
                        oid="cancellation_reason_question",
                        id_=0,
                        question_set_id=0,
                        sort_order=0,
                        label="",
                        type_="",
                        required=False,
                        answers=[
                            TranslatedAnswerStruct(
                                id_=0,
                                text="",
                                sort_order=0,
                                oid="cancellation_reason_forgot",
                            )
                        ],
                    )
                ],
            )
        ],
    )
    with flask_babel.force_locale("en"):
        MemberQuestionnairesService.localize_questionnaires([questionnaire])
        assert (
            questionnaire.question_sets[0].questions[0].label
            != "question_cancellation_survey_cancellation_survey_question_set_cancellation_reason_question_label"
        )
        assert (
            questionnaire.title_text != "questionnaire_cancellation_survey_title_text"
        )
        assert (
            questionnaire.description_text
            != "questionnaire_cancellation_survey_description_text"
        )


def test_get_member_questionnaires__with_l10n(client, db, factories, api_helpers):
    member = factories.EnterpriseUserFactory.create()
    questionnaires = [
        factories.EmptyQuestionnaireFactory.create(
            oid="member_rating_v2", sort_order=0
        ),
    ]

    answers = []
    for questionnaire in questionnaires:
        for i in range(0, 2):
            qs = factories.EmptyQuestionSetFactory.create(
                questionnaire_id=questionnaire.id,
                oid=f"{questionnaire.oid},{i}",
                sort_order=i,
            )
            for j in range(0, 2):
                q = factories.EmptyQuestionFactory.create(
                    question_set_id=qs.id, label=f"{i},{j}", sort_order=1 - j
                )
                if j:
                    a = factories.AnswerFactory.create(
                        question_id=q.id, text=f"{i},{j}", sort_order=0
                    )
                    answers.append(a)

    insert_statement = f"INSERT INTO questionnaire_trigger_answer (answer_id, questionnaire_id) VALUES ({answers[0].id}, {questionnaires[0].id})"
    db.session.execute(insert_statement)

    expected_translation_question = "translatedq"
    expected_translation_answer = "translateda"
    with mock.patch(
        "clinical_documentation.resource.member_questionnaires.feature_flags.bool_variation",
        return_value=True,
    ), mock.patch(
        "l10n.db_strings.translate.TranslateDBFields.get_translated_question",
        return_value=expected_translation_question,
    ) as translation_mock_q, mock.patch(
        "l10n.db_strings.translate.TranslateDBFields.get_translated_answer",
        return_value=expected_translation_answer,
    ) as translation_mock_a:
        res = client.get(
            "/api/v2/clinical_documentation/member_questionnaires",
            headers=api_helpers.json_headers(member),
        )

        # One call each for 4 questions and two answers
        assert translation_mock_q.call_count == 4
        assert translation_mock_a.call_count == 2

    actual_questionnaires = res.json["questionnaires"]
    assert len(actual_questionnaires) == 1
    actual_question_sets = actual_questionnaires[0]["question_sets"]
    assert len(actual_question_sets) == 2

    for actual_question_set in actual_question_sets:
        actual_questions = actual_question_set["questions"]
        for actual_question in actual_questions:
            assert actual_question["label"] == expected_translation_question

            actual_answers = actual_question["answers"]
            assert all(
                [
                    a["text"] == expected_translation_answer
                    for a in actual_answers
                    if a["text"]
                ]
            )
