from datetime import datetime, timedelta

import pytest

from models.questionnaires import (
    SINGLE_EMBRYO_TRANSFER_QUESTIONNAIRE_OID,
    Questionnaire,
    QuestionTypes,
    RecordedAnswerSet,
)
from pytests.factories import DefaultUserFactory, QuestionnaireFactory
from storage.connection import db


@pytest.fixture
def treatment_procedure_recorded_answer_set_questionnaire():
    questionnaire = QuestionnaireFactory.create(
        oid=SINGLE_EMBRYO_TRANSFER_QUESTIONNAIRE_OID
    )
    questions = questionnaire.question_sets[0].questions

    radio_question = next(q for q in questions if q.type == QuestionTypes.RADIO)
    questions = [
        {
            "question_id": radio_question.id,
            "answer_id": radio_question.answers[0].id,
        },
    ]

    return {"questionnaire_id": questionnaire.id, "questions": questions}


def test_soft_deleted_records_not_represented(factories):
    questionnaire = factories.QuestionnaireFactory.create()
    questions = questionnaire.question_sets[0].questions

    questions_count_before = len(questions)

    questions[0].soft_deleted_at = datetime.now()
    questions[1].answers[0].soft_deleted_at = datetime.now()
    db.session.add(questionnaire)
    db.session.commit()
    db.session.expire_all()

    updated_questionnaire = Questionnaire.query.get(questionnaire.id)
    assert len(updated_questionnaire.question_sets) == 1
    rendered_questions = updated_questionnaire.question_sets[0].questions
    assert str(questions[0].id) not in [q.id for q in rendered_questions]
    assert len(rendered_questions) == questions_count_before - 1
    assert str(questions[1].answers[0].id) not in [
        a.id for a in rendered_questions[0].answers
    ]


def test_soft_deletion_cascades(factories):
    now = datetime.now()
    questionnaire = factories.QuestionnaireFactory.create()
    qs = questionnaire.question_sets[0]
    qs.soft_deleted_at = now
    for q in qs.questions:
        assert q.soft_deleted_at == now
        assert all(a.soft_deleted_at == now for a in q.answers)


def test_soft_deletion_cascade_doesnt_affect_already_soft_deleted(factories):
    now = datetime.now()
    questionnaire = factories.QuestionnaireFactory.create()
    before = now - timedelta(hours=1)
    qs = questionnaire.question_sets[0]
    qs.questions[0].soft_deleted_at = before
    qs.soft_deleted_at = now
    assert qs.questions[0].soft_deleted_at == before
    assert qs.questions[1].soft_deleted_at == now


class TestRecordedAnswerSet:
    @pytest.mark.parametrize(
        argnames="attr",
        argvalues=({"questionnaire_id": 1}, {"source_user_id": 3}),
        ids=["no questionnaire id", "no source user id"],
    )
    def test_create_recorded_answer_set_invalid_attrs(self, db, attr):
        with pytest.raises(
            ValueError,
            match="questionnaire id and source user id cannot be empty in recorded_answer_set!",
        ):
            RecordedAnswerSet.create(attr)

    def test_create_recorded_answer_set_success(
        self, treatment_procedure_recorded_answer_set_questionnaire
    ):
        user = DefaultUserFactory.create()
        questionnaire_id = treatment_procedure_recorded_answer_set_questionnaire[
            "questionnaire_id"
        ]
        questions = treatment_procedure_recorded_answer_set_questionnaire["questions"]

        attr = {
            "source_user_id": user.id,
            "questionnaire_id": questionnaire_id,
            "recorded_answers": questions,
        }

        rac = RecordedAnswerSet.create(attr)
        assert rac is not None
        assert rac.source_user_id == user.id
        assert rac.questionnaire_id == questionnaire_id
        assert len(rac.recorded_answers) == len(questions)
        assert rac.recorded_answers[0].answer_id == questions[0]["answer_id"]
