from __future__ import annotations

from models.questionnaires import RecordedAnswer
from pytests.db_util import enable_db_performance_warnings


def test_post_questionnaire_answers(client, db, factories, api_helpers):
    appt = factories.AppointmentFactory.create()
    member = appt.member
    questionnaire = factories.QuestionnaireFactory.create()
    questions = questionnaire.question_sets[0].questions

    recorded_answers = sorted(
        [
            {
                "question_id": str(questions[0].id),
                "answer_id": str(questions[0].answers[0].id),
                "appointment_id": str(appt.api_id),
                "user_id": member.id,
            },
            {
                "question_id": str(questions[1].id),
                "answer_id": str(questions[1].answers[0].id),
                "appointment_id": str(appt.api_id),
                "user_id": member.id,
            },
            {
                "question_id": str(questions[2].id),
                "answer_id": None,
                "appointment_id": str(appt.api_id),
                "user_id": member.id,
            },
        ],
        key=lambda ra: ra["question_id"],
    )

    with enable_db_performance_warnings(database=db, failure_threshold=13):
        res = client.post(
            "/api/v2/clinical_documentation/questionnaire_answers",
            json=recorded_answers,
            headers=api_helpers.json_headers(member),
        )
        assert res.status_code == 200

    results = (
        db.session.query(RecordedAnswer)
        .filter(RecordedAnswer.appointment_id == appt.id)
        .all()
    )
    expected_answers = [
        {
            "question_id": questions[0].id,
            "answer_id": questions[0].answers[0].id,
            "appointment_id": appt.id,
            "user_id": member.id,
        },
        {
            "question_id": questions[1].id,
            "answer_id": questions[1].answers[0].id,
            "appointment_id": appt.id,
            "user_id": member.id,
        },
        {
            "question_id": questions[2].id,
            "answer_id": None,
            "appointment_id": appt.id,
            "user_id": member.id,
        },
    ]
    actual_answers = sorted(
        [
            {
                "question_id": result.question_id,
                "answer_id": result.answer_id,
                "appointment_id": result.appointment_id,
                "user_id": result.user_id,
            }
            for result in results
        ],
        key=lambda ra: ra["question_id"],
    )

    assert expected_answers == actual_answers


def test_post_questionnaire_answers_replace_answers(client, db, factories, api_helpers):
    appt = factories.AppointmentFactory.create()
    member = appt.member
    questionnaire = factories.QuestionnaireFactory.create()
    questions = questionnaire.question_sets[0].questions

    recorded_answers = sorted(
        [
            {
                "question_id": questions[0].id,
                "answer_id": questions[0].answers[0].id,
                "appointment_id": appt.api_id,
                "user_id": member.id,
            },
            {
                "question_id": questions[1].id,
                "answer_id": questions[1].answers[0].id,
                "appointment_id": appt.api_id,
                "user_id": member.id,
            },
        ],
        key=lambda ra: ra["question_id"],
    )

    res = client.post(
        "/api/v2/clinical_documentation/questionnaire_answers",
        json=recorded_answers,
        headers=api_helpers.json_headers(member),
    )
    assert res.status_code == 200

    next_recorded_answers = sorted(
        [
            {
                "question_id": questions[0].id,
                "answer_id": questions[0].answers[1].id,
                "appointment_id": appt.api_id,
                "user_id": member.id,
            },
            {
                "question_id": questions[1].id,
                "answer_id": questions[1].answers[1].id,
                "appointment_id": appt.api_id,
                "user_id": member.id,
            },
        ],
        key=lambda ra: ra["question_id"],
    )

    res = client.post(
        "/api/v2/clinical_documentation/questionnaire_answers",
        json=next_recorded_answers,
        headers=api_helpers.json_headers(member),
    )
    assert res.status_code == 200

    results = (
        db.session.query(RecordedAnswer)
        .filter(RecordedAnswer.appointment_id == appt.id)
        .all()
    )
    expected_answers = sorted(
        [
            {
                "question_id": questions[0].id,
                "answer_id": questions[0].answers[1].id,
                "appointment_id": appt.id,
                "user_id": member.id,
            },
            {
                "question_id": questions[1].id,
                "answer_id": questions[1].answers[1].id,
                "appointment_id": appt.id,
                "user_id": member.id,
            },
        ],
        key=lambda ra: ra["question_id"],
    )
    actual_answers = sorted(
        [
            {
                "question_id": result.question_id,
                "answer_id": result.answer_id,
                "appointment_id": result.appointment_id,
                "user_id": result.user_id,
            }
            for result in results
        ],
        key=lambda ra: ra["question_id"],
    )

    assert expected_answers == actual_answers


def test_post_multiple_questionnaires(client, db, factories, api_helpers):
    appt = factories.AppointmentFactory.create()

    member = appt.member
    questionnaire = factories.QuestionnaireFactory.create()
    questionnaire2 = factories.QuestionnaireFactory.create()

    recorded_answers = sorted(
        [
            {
                "question_id": questionnaire.question_sets[0].questions[0].id,
                "answer_id": questionnaire.question_sets[0].questions[0].answers[0].id,
                "appointment_id": appt.api_id,
                "user_id": member.id,
            },
            {
                "question_id": questionnaire2.question_sets[0].questions[1].id,
                "answer_id": questionnaire2.question_sets[0].questions[1].answers[0].id,
                "appointment_id": appt.api_id,
                "user_id": member.id,
            },
        ],
        key=lambda ra: ra["question_id"],
    )

    res = client.post(
        "/api/v2/clinical_documentation/questionnaire_answers",
        json=recorded_answers,
        headers=api_helpers.json_headers(member),
    )
    assert res.status_code == 200
    results = (
        db.session.query(RecordedAnswer)
        .filter(RecordedAnswer.appointment_id == appt.id)
        .all()
    )
    expected_answers = sorted(
        [
            {
                "question_id": questionnaire.question_sets[0].questions[0].id,
                "answer_id": questionnaire.question_sets[0].questions[0].answers[0].id,
                "appointment_id": appt.id,
                "user_id": member.id,
            },
            {
                "question_id": questionnaire2.question_sets[0].questions[1].id,
                "answer_id": questionnaire2.question_sets[0].questions[1].answers[0].id,
                "appointment_id": appt.id,
                "user_id": member.id,
            },
        ],
        key=lambda ra: ra["question_id"],
    )

    actual_answers = sorted(
        [
            {
                "question_id": result.question_id,
                "answer_id": result.answer_id,
                "appointment_id": result.appointment_id,
                "user_id": result.user_id,
            }
            for result in results
        ],
        key=lambda ra: ra["question_id"],
    )

    assert expected_answers == actual_answers


def test_invalid_request_multiple_appts(client, db, factories, api_helpers):
    appt = factories.AppointmentFactory.create()
    appt2 = factories.AppointmentFactory.create()

    member = appt.member
    questionnaire = factories.QuestionnaireFactory.create()

    recorded_answers = sorted(
        [
            {
                "question_id": questionnaire.question_sets[0].questions[0].id,
                "answer_id": questionnaire.question_sets[0].questions[0].answers[0].id,
                "appointment_id": appt.api_id,
                "user_id": member.id,
            },
            {
                "question_id": questionnaire.question_sets[0].questions[1].id,
                "answer_id": questionnaire.question_sets[0].questions[1].answers[0].id,
                "appointment_id": appt2.api_id,
                "user_id": member.id,
            },
        ],
        key=lambda ra: ra["question_id"],
    )

    res = client.post(
        "/api/v2/clinical_documentation/questionnaire_answers",
        json=recorded_answers,
        headers=api_helpers.json_headers(member),
    )
    assert res.status_code == 400
