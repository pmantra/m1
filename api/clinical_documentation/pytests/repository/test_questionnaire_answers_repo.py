from appointments.utils.appointment_utils import check_appointment_by_ids
from clinical_documentation.models.questionnaire_answers import RecordedAnswer
from clinical_documentation.repository.questionnaire_answers import (
    QuestionnaireAnswersRepository,
)


class TestQuestionnaireAnswersRepository:
    def test_insert_recorded_answers(self, db, factories):
        q = factories.QuestionnaireFactory.create()
        question1 = q.question_sets[0].questions[0]
        question2 = q.question_sets[0].questions[1]
        appointment = factories.AppointmentFactory.create()

        repo = QuestionnaireAnswersRepository(db.session)
        check_appointment_by_ids([appointment.id], True)

        recorded_answers = [
            RecordedAnswer(
                question_id=question1.id,
                answer_id=question1.answers[0].id,
                text="boo",
                appointment_id=appointment.id,
                user_id=appointment.member_id,
            ),
            RecordedAnswer(
                question_id=question2.id,
                answer_id=question2.answers[0].id,
                text="boo",
                appointment_id=appointment.id,
                user_id=appointment.member_id,
            ),
        ]
        repo.insert_recorded_answers(recorded_answers)

        inserted = {
            result.question_id
            for result in db.session.execute("select question_id from recorded_answer")
        }
        assert inserted == {question1.id, question2.id}

    def test_delete_recorded_answers(self, db, factories):
        q = factories.QuestionnaireFactory.create()
        question1 = q.question_sets[0].questions[0]
        question2 = q.question_sets[0].questions[1]
        appointment = factories.AppointmentFactory.create()

        repo = QuestionnaireAnswersRepository(db.session)
        check_appointment_by_ids([appointment.id], True)

        recorded_answers = [
            RecordedAnswer(
                question_id=question1.id,
                answer_id=question1.answers[0].id,
                text="boo",
                appointment_id=appointment.id,
                user_id=appointment.member_id,
            ),
            RecordedAnswer(
                question_id=question2.id,
                answer_id=question2.answers[0].id,
                text="boo",
                appointment_id=appointment.id,
                user_id=appointment.member_id,
            ),
        ]
        repo.insert_recorded_answers(recorded_answers)
        repo.delete_existing_recorded_answers(appointment.id, q.id)

        inserted = {
            result.question_id
            for result in db.session.execute("select question_id from recorded_answer")
        }
        assert len(inserted) == 0

    def test_distinct_questionnaire_ids(self, db, factories):
        q = factories.QuestionnaireFactory.create()
        question1 = q.question_sets[0].questions[0]
        question2 = q.question_sets[0].questions[1]

        q2 = factories.QuestionnaireFactory.create()
        question3 = q2.question_sets[0].questions[1]

        repo = QuestionnaireAnswersRepository(db.session)
        questionnaire_ids = repo.get_distinct_questionnaire_ids_from_question_ids(
            [question1.id, question2.id, question3.id]
        )

        assert {q.id, q2.id} == questionnaire_ids

    def test_get_distinct_questionnaire_ids_from_question_ids__empty(self, db):
        repo = QuestionnaireAnswersRepository(db.session)
        expected = set()
        actual = repo.get_distinct_questionnaire_ids_from_question_ids([])

        assert actual == expected
