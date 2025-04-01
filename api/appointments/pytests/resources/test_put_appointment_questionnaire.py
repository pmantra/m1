import json
from http import HTTPStatus

import pytest
from faker import Faker

from appointments.utils.appointment_utils import check_appointment_by_ids
from models.base import db
from models.questionnaires import (
    COACHING_NOTES_COACHING_PROVIDERS_OID,
    QuestionTypes,
    RecordedAnswerSet,
)

fake = Faker()


@pytest.fixture
def get_text_question_and_put_text_answer(
    client,
    api_helpers,
    valid_questionnaire_with_oid,
):
    """Returns a function to get the text question and put a supplied
    text answer on the endpoint
    """

    questionnaire = valid_questionnaire_with_oid(
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID
    )
    questions = questionnaire.question_sets[0].questions

    def get_text_question_and_put_text_answer_func(
        appointment,
        text_answer,
    ):
        # Find a text question
        text_question = next(q for q in questions if q.type == QuestionTypes.TEXT)

        # Add the text answer
        recorded_answers = [
            {
                "question_id": text_question.id,
                "text": text_answer,
                "answer_id": None,
                "date": None,
            },
        ]
        data = {
            "structured_internal_note": {
                "recorded_answer_set": {
                    "source_user_id": appointment.practitioner.id,
                    "draft": False,
                    "appointment_id": appointment.id,
                    "questionnaire_id": questionnaire.id,
                    "recorded_answers": recorded_answers,
                }
            }
        }

        # Put answers on the endpoint
        res = client.put(
            f"/api/v1/appointments/{appointment.api_id}",
            data=json.dumps(data),
            headers=api_helpers.json_headers(appointment.practitioner),
        )

        return text_question, res

    return get_text_question_and_put_text_answer_func


def test_put_recorded_answers_text(
    basic_appointment,
    get_text_question_and_put_text_answer,
):
    """Tests setting a questionnaire text answer and confirms that the
    recorded answer is what was sent.
    """
    # Set the answer to a random string
    answer_text = fake.pystr(min_chars=1001, max_chars=1100)
    text_question, res = get_text_question_and_put_text_answer(
        text_answer=answer_text, appointment=basic_appointment
    )

    # Assert the success of the call by checking the HTTP status
    assert res.status_code == HTTPStatus.OK

    ra_response = (
        res.json.get("structured_internal_note")
        .get("recorded_answer_set")
        .get("recorded_answers")
    )

    # Get the recorded answer from the response
    recorded_answer = next(
        ra for ra in ra_response if int(ra.get("question_id")) == text_question.id
    )
    # Assert that the answers match
    assert recorded_answer.get("text") == answer_text


def test_put_recorded_answers_text_too_long(
    get_text_question_and_put_text_answer, basic_appointment
):
    """Tests setting a questionnaire text answer to something too long
    and confirms that the recorded answer is what was sent.
    """
    # Set the answer to a random string that is too long
    _, res = get_text_question_and_put_text_answer(
        text_answer=fake.pystr(min_chars=6001, max_chars=6100),
        appointment=basic_appointment,
    )

    # Assert the failure of the call by checking the HTTP status
    assert res.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    # Check that a message was sent to explain the problem
    bad_res_parsed = json.loads(res.data)
    assert len(bad_res_parsed["message"]) > 0


def test_put_recorded_answers_text_changed_keys(
    basic_appointment, get_text_question_and_put_text_answer, create_practitioner
):
    """
    Tests updating a questionnaire with a different provider id.
    Unclear what real-world usecase triggers this but we are seeing
    error logs that make it seem like something like this is happening.
    """
    # Set the answer to a random string
    answer_text = fake.pystr(min_chars=1001, max_chars=1100)
    text_question, res = get_text_question_and_put_text_answer(
        text_answer=answer_text, appointment=basic_appointment
    )

    # Assert the success of the call by checking the HTTP status
    assert res.status_code == HTTPStatus.OK

    second_practitioner = create_practitioner()
    basic_appointment.product.practitioner = second_practitioner
    answer_text = fake.pystr(min_chars=1001, max_chars=1100)
    text_question, res = get_text_question_and_put_text_answer(
        text_answer=answer_text, appointment=basic_appointment
    )

    # Assert the success of the call by checking the HTTP status
    assert res.status_code == HTTPStatus.OK


def test_put_simulate_race(
    monkeypatch,
    basic_appointment,
    get_text_question_and_put_text_answer,
    create_practitioner,
):
    """
    Simulates a second PUT executing at the same time
    """

    orig_fn = RecordedAnswerSet.find_by_id_or_attrs
    dupe_created = False

    @classmethod
    def race_condition_find_by_id_or_attrs(cls, attrs, id_=None):
        nonlocal dupe_created
        rac = orig_fn(attrs, id_)
        check_appointment_by_ids([attrs.get("appointment_id")], True)
        if not rac and not dupe_created:
            # simulate another one getting created at the same time
            dupe = RecordedAnswerSet(
                id=attrs.get("id"),
                source_user_id=attrs.get("source_user_id"),
                questionnaire_id=attrs.get("questionnaire_id"),
                appointment_id=attrs.get("appointment_id"),
            )
            db.session.add(dupe)
            db.session.commit()
            dupe_created = True
        return rac

    monkeypatch.setattr(
        "models.questionnaires.RecordedAnswerSet.find_by_id_or_attrs",
        race_condition_find_by_id_or_attrs,
    )

    # Set the answer to a random string
    answer_text = fake.pystr(min_chars=1001, max_chars=1100)
    text_question, res = get_text_question_and_put_text_answer(
        text_answer=answer_text, appointment=basic_appointment
    )

    # Assert the success of the call by checking the HTTP status
    assert res.status_code == HTTPStatus.OK
