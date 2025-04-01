import dataclasses
from unittest.mock import patch

import requests

from common.health_data_collection.models import HDCDisplayCondition, HDCUserAnswer
from common.health_data_collection.question_api import get_question_slug_user_answers


class TestQuestionEndpoint:
    def test_get_question_slug_with_answers(self, question_answer_response):
        response = requests.Response()
        response.status_code = 200

        response.json = lambda: question_answer_response

        with patch(
            "common.health_data_collection.question_api.make_hdc_request",
            return_value=response,
        ):
            question_response = get_question_slug_user_answers(
                user_id=167443, question_slug="maven_missing_impact"
            )

            assert len(question_response.user_answers) == 1
            assert isinstance(question_response.user_answers[0], HDCUserAnswer)
            assert isinstance(question_response.display_condition, HDCDisplayCondition)

    def test_get_question_slug_with_answers_languages(
        self, question_answer_response_languages
    ):
        response = requests.Response()
        response.status_code = 200

        response.json = lambda: question_answer_response_languages

        with patch(
            "common.health_data_collection.question_api.make_hdc_request",
            return_value=response,
        ):
            question_response = get_question_slug_user_answers(
                user_id=2223552, question_slug="preferred_languages"
            )

            assert len(question_response.user_answers) == 3
            assert isinstance(question_response.user_answers[0], HDCUserAnswer)
            hdc_languages = {answer.value for answer in question_response.user_answers}
            assert hdc_languages == {"arabic", "bulgarian", "english"}

    def test_null_response_with_answers(self):
        response = requests.Response()
        response.json = lambda: {}
        response.status_code = 400

        with patch(
            "common.health_data_collection.question_api.make_hdc_request",
            return_value=response,
        ):
            question_response = get_question_slug_user_answers(
                user_id=167443, question_slug="maven_missing_impact"
            )
            assert question_response is None

    def test_no_exception_with_extra_fields(self, question_answer_response):

        # add fields that do not exist in the dataclass models
        question_answer_response["fake_question_key"] = "fake_question_val"
        user_ans_dict = question_answer_response["user_answers"][0]
        user_ans_dict["fake_user_ans_key"] = "fake_user_ans_val"
        question_answer_response["display_condition"]["fake_dc_key"] = "fake_dc_val"

        response = requests.Response()
        response.status_code = 200

        response.json = lambda: question_answer_response

        with patch(
            "common.health_data_collection.question_api.make_hdc_request",
            return_value=response,
        ):
            question_response = get_question_slug_user_answers(
                user_id=167443, question_slug="maven_missing_impact"
            )

            assert "fake_question_key" not in dataclasses.asdict(question_response)
            assert "fake_user_ans_key" not in question_response.user_answers
            assert "fake_dc_key" not in dataclasses.asdict(
                question_response.display_condition
            )
