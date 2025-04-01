from datetime import datetime

import pytest

from appointments.models.appointment import Appointment
from models.questionnaires import Questionnaire, RecordedAnswer
from pytests.factories import (
    AppointmentFactory,
    PractitionerUserFactory,
    QuestionFactory,
    QuestionnaireFactory,
    QuestionSetFactory,
    RecordedAnswerFactory,
)
from utils.random_string import generate_random_string

APPOINTMENT_1000_PURPOSE = generate_random_string(10)
RECORDED_ANSWER_1000_TEXT = generate_random_string(30)
RECORDED_ANSWER_1001_TEXT = generate_random_string(30)


@pytest.fixture(scope="function")
def practitioner_user():
    return PractitionerUserFactory.create()


@pytest.fixture(scope="function")
def appointment_1000() -> Appointment:
    appointment = AppointmentFactory.create(
        id=1000,
        purpose=APPOINTMENT_1000_PURPOSE,
        scheduled_start=datetime(2023, 1, 1, 10, 00, 00),
        scheduled_end=datetime(2023, 1, 1, 11, 00, 00),
    )

    return appointment


@pytest.fixture(scope="function")
def appointment_1001() -> Appointment:
    appointment = AppointmentFactory.create(
        id=1001,
        scheduled_start=datetime(2023, 1, 1, 10, 00, 00),
        scheduled_end=datetime(2023, 1, 1, 11, 00, 00),
    )

    return appointment


@pytest.fixture(scope="function")
def questionnaire_1000() -> Questionnaire:
    return QuestionnaireFactory.create(id=1000)


@pytest.fixture(scope="function")
def recorded_answer_1000(appointment_1000, questionnaire_1000, practitioner_user):
    question_set = QuestionSetFactory.create(questionnaire_id=questionnaire_1000.id)
    question = QuestionFactory.create(question_set_id=question_set.id)
    recorded_answer = RecordedAnswerFactory.create(
        appointment_id=appointment_1000.id,
        question=question,
        user_id=practitioner_user.id,
        text=RECORDED_ANSWER_1000_TEXT,
    )

    return recorded_answer


@pytest.fixture(scope="function")
def recorded_answer_1001(appointment_1000, questionnaire_1000, practitioner_user):
    question_set = QuestionSetFactory.create(questionnaire_id=questionnaire_1000.id)
    question = QuestionFactory.create(question_set_id=question_set.id)
    recorded_answer = RecordedAnswerFactory.create(
        appointment_id=appointment_1000.id,
        question=question,
        user_id=practitioner_user.id,
        text=RECORDED_ANSWER_1001_TEXT,
    )

    return recorded_answer


def test_get_recorded_answer_and_appointment(appointment_1000, recorded_answer_1000):
    recorded_answers_one = appointment_1000.recorded_answers
    assert len(recorded_answers_one) == 1

    recorded_answer_one = recorded_answers_one[0]
    appointment_one = recorded_answer_one.appointment

    assert recorded_answer_one.appointment_id == appointment_1000.id
    assert recorded_answer_one.id == recorded_answer_1000.id
    assert recorded_answer_one.text == RECORDED_ANSWER_1000_TEXT
    assert appointment_one.id == appointment_1000.id
    assert appointment_one.purpose == APPOINTMENT_1000_PURPOSE


def test_update_appointment_from_recorded_answer_same_appointment_id(
    appointment_1000, recorded_answer_1000
):
    new_appointment_purpose = generate_random_string(20)
    current_appointment_modified_at = appointment_1000.modified_at

    appointment_1000.purpose = new_appointment_purpose

    # Update appointment
    recorded_answer_1000.appointment = appointment_1000

    # Query updated appointment
    updated_appointment = Appointment.query.filter(
        Appointment.id == appointment_1000.id
    ).one_or_none()

    assert updated_appointment is not None
    assert updated_appointment.modified_at != current_appointment_modified_at
    assert updated_appointment.purpose == new_appointment_purpose


def test_update_appointment_from_recorded_answer_different_appointment_id(
    appointment_1000, appointment_1001, recorded_answer_1000
):
    # Check if the appointment_id in record answer will be updated when a different appointment is set to it
    recorded_answer_1000.appointment = appointment_1001
    assert recorded_answer_1000.appointment_id == appointment_1001.id

    recorded_answer_1000.appointment = appointment_1000
    assert recorded_answer_1000.appointment_id == appointment_1000.id


def test_update_recorded_answers_from_appointment(
    appointment_1000, appointment_1001, recorded_answer_1000, recorded_answer_1001
):
    assert recorded_answer_1000.appointment_id == appointment_1000.id
    assert recorded_answer_1001.appointment_id == appointment_1000.id

    # Remove the association between appointment_1000 and recorded_answer_1001
    appointment_1000.recorded_answers = [recorded_answer_1000]

    updated_recorded_answer_1001 = RecordedAnswer.query.filter(
        RecordedAnswer.id == recorded_answer_1001.id
    ).one_or_none()
    assert updated_recorded_answer_1001 is not None
    assert updated_recorded_answer_1001.appointment_id is None

    # Add recorded_answer_1001 into appointment_1001
    appointment_1001.recorded_answers = [recorded_answer_1001]
    updated_recorded_answer_1001 = RecordedAnswer.query.filter(
        RecordedAnswer.id == recorded_answer_1001.id
    ).one_or_none()
    assert updated_recorded_answer_1001 is not None
    assert updated_recorded_answer_1001.appointment_id == appointment_1001.id
