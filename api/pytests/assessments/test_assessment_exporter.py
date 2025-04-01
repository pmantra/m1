from assessments.utils.assessment_exporter import (
    AssessmentExporter,
    AssessmentExportTopic,
)


class TestCQuizExport:
    def test_c_quiz_question_template_label_export_type(self, factories, mock_c_quiz):
        # Answer part of the mini C_QUIZ
        # Note: Current assessment code treats integer zero answers as non-answers, hence the string case.
        needs_assessment = factories.NeedsAssessmentFactory.create(
            assessment_template=mock_c_quiz,
            json={
                "meta": {"completed": True},
                "answers": [{"id": 1, "body": 1}, {"id": 2, "body": '"0"'}],
            },
        )
        # Prove answers are exporting for C_QUIZ questions with both raw numbers and text
        exporter = AssessmentExporter()
        answers = [
            a
            for a in exporter.answers_from_needs_assessment(
                needs_assessment=needs_assessment, topic=AssessmentExportTopic.ANALYTICS
            )
        ]

        assert len(answers) == 2
        answer_1 = next(answer for answer in answers if answer.question_id == 1)
        assert answer_1.raw_answer == 1
        assert answer_1.exported_answer == "Yes"
        answer_2 = next(answer for answer in answers if answer.question_id == 2)
        assert answer_2.raw_answer == '"0"'
        assert answer_2.exported_answer == "No"
