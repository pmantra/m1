import pytest

from assessments.utils.assessment_exporter import AssessmentExportLogic
from pytests.factories import AssessmentFactory


@pytest.fixture(scope="function")
def mock_c_quiz():
    c_quiz_widget = {
        "type": "c-quiz-question",
        "options": [{"label": "Yes", "value": 1}, {"label": "No", "value": "0"}],
    }
    c_quiz = AssessmentFactory(
        quiz_body={
            "questions": [
                AssessmentFactory.format_question(
                    id=1,
                    widget=c_quiz_widget,
                    question_name="first_question",
                    export_logic=AssessmentExportLogic.TEMPLATE_LABEL.value,
                ),
                AssessmentFactory.format_question(
                    id=2,
                    widget=c_quiz_widget,
                    question_name="second_question",
                    export_logic=AssessmentExportLogic.TEMPLATE_LABEL.value,
                ),
            ]
        },
        score_band={},
    )
    return c_quiz
