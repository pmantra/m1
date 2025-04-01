from models.questionnaires import Question, QuestionSet, QuestionTypes
from pytests.factories import QuestionFactory, QuestionnaireFactory


class TestQuestionnaires:
    def test_duplicate_question_set(self, admin_client, db):
        questionnaire = QuestionnaireFactory.create()
        expected_question_set: QuestionSet = questionnaire.question_sets[0]
        expected_question_set_id = questionnaire.question_sets[0].id
        expected_question_set_oid = questionnaire.question_sets[0].oid
        admin_client.post(
            "/admin/questionset/duplicate",
            data={"record_id": expected_question_set_id},
            headers={"Content-Type": "multipart/form-data"},
        )

        question_set_copy: QuestionSet = (
            db.session.query(QuestionSet)
            .filter(
                (QuestionSet.oid == expected_question_set_oid)
                & (QuestionSet.id != expected_question_set_id)
            )
            .one()
        )
        assert (
            question_set_copy.prerequisite_answer_id
            == expected_question_set.prerequisite_answer_id
        )
        assert (
            question_set_copy.questionnaire_id == expected_question_set.questionnaire_id
        )
        assert question_set_copy.sort_order == expected_question_set.sort_order
        assert len(question_set_copy.questions) > 0
        assert len(question_set_copy.questions) == len(expected_question_set.questions)
        for i in range(0, len(question_set_copy.questions) - 1):
            question = question_set_copy.questions[i]
            expected_question = expected_question_set.questions[i]
            assert question.id != expected_question.id
            assert question.oid == expected_question.oid
            assert question.required == expected_question.required
            assert question.sort_order == expected_question.sort_order
            assert question.type == expected_question.type
            assert (
                question.non_db_answer_options_json
                == expected_question.non_db_answer_options_json
            )
            assert len(question.answers) == len(expected_question.answers)
            if len(question.answers) > 0:
                for answer_i in range(0, len(question.answers) - 1):
                    answer = question.answers[answer_i]
                    expected_answer = expected_question.answers[answer_i]
                    assert answer.id != expected_answer.id
                    assert answer.oid == expected_answer.oid
                    assert answer.sort_order == expected_answer.sort_order
                    assert answer.text == expected_answer.text

    def test_duplicate_question(self, admin_client, db):
        questionnaire = QuestionnaireFactory.create()
        expected_question = QuestionFactory.create(
            label="question label",
            non_db_answer_options_json={"json_test": "this is a test"},
            oid="question oid",
            question_set_id=questionnaire.question_sets[0].id,
            required=True,
            sort_order=14,
            type=QuestionTypes.RADIO,
        )

        admin_client.post(
            "/admin/question/duplicate",
            data={
                "record_id": expected_question.id,
            },
            headers={"Content-Type": "multipart/form-data"},
        )

        question = (
            db.session.query(Question)
            .filter(
                (Question.oid == expected_question.oid)
                & (Question.id != expected_question.id)
            )
            .one()
        )
        assert question.required == expected_question.required
        assert question.sort_order == expected_question.sort_order
        assert question.type == expected_question.type
        assert (
            question.non_db_answer_options_json
            == expected_question.non_db_answer_options_json
        )
        assert len(question.answers) == len(expected_question.answers)
        assert len(question.answers) == 3
        # handle QuestionFactory response not respecting sort order.
        question.answers.sort(key=lambda x: x.sort_order)
        expected_question.answers.sort(key=lambda x: x.sort_order)
        for answer_i in range(0, len(question.answers) - 1):
            answer = question.answers[answer_i]
            expected_answer = expected_question.answers[answer_i]
            assert answer.id != expected_answer.id
            assert answer.oid == expected_answer.oid
            assert answer.sort_order == expected_answer.sort_order
            assert answer.text == expected_answer.text
