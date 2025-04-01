from common.health_data_collection.models import (
    AssessmentMetadata,
    HDCAnswerOption,
    HDCDisplayCondition,
    HDCQuestion,
    HDCUserAnswer,
)


class TestConversionModels:
    def test_question_model(self, question_answer_response):

        question_object = HDCQuestion.create_from_api_response(question_answer_response)
        assert isinstance(question_object, HDCQuestion)

        # Check answers converted correctly
        for answer in question_object.user_answers:
            assert isinstance(answer, HDCUserAnswer)

        # Check options converted
        for option in question_object.options:
            assert isinstance(option, HDCAnswerOption)

        assert isinstance(question_object.display_condition, HDCDisplayCondition)

    def test_metadata_assessment_model(
        self, user_assessment_by_slug_populated_user_assessment
    ):

        metadata_assessment = AssessmentMetadata.create_from_api_response(
            json_res=user_assessment_by_slug_populated_user_assessment
        )
        assert isinstance(metadata_assessment, AssessmentMetadata)
