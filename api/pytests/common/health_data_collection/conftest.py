import json
import os

import pytest

HDC_DATA_FOLDER = os.path.dirname(os.path.realpath(__file__)) + "/data"


@pytest.fixture
def question_answer_response():
    with open(f"{HDC_DATA_FOLDER}/question_user_answer.json", "r") as f:
        response_json = json.load(f)

    return response_json


@pytest.fixture
def question_answer_response_languages():
    with open(f"{HDC_DATA_FOLDER}/question_user_answer_languages.json", "r") as f:
        response_json = json.load(f)

    return response_json


@pytest.fixture
def user_assessment_by_slug_populated_user_assessment():
    with open(f"{HDC_DATA_FOLDER}/user_assessments_slug_completed.json", "r") as f:
        response_json = json.load(f)

    return response_json


@pytest.fixture
def user_assessment_by_slug_null_user_assessment():
    with open(f"{HDC_DATA_FOLDER}/user_assessments_slug_not_completed.json", "r") as f:
        response_json = json.load(f)

    return response_json
