from models.FHIR.condition import Condition
from models.questionnaires import QuestionTypes
from pytests.freezegun import freeze_time


@freeze_time("2024-01-17T11:24:00")
def test_get_conditions_by_user_id_no_condition(factories, default_user):
    conditions = Condition.get_conditions_by_user_id(default_user.id)
    assert len(conditions) == 2
    for condition in conditions:
        assert condition["code"]["text"] is None
        assert condition["recordedDate"] == "2024-01-17T11:24:00Z"


@freeze_time("2024-01-17T11:24:00")
def test_get_conditions_by_user_id_conditions_exist(factories):
    user = factories.DefaultUserFactory.create()
    user.health_profile.json[
        Condition.health_binder_fields_current
    ] = "current condition"
    user.health_profile.json[Condition.health_binder_fields_past] = "past condition"

    conditions = Condition.get_conditions_by_user_id(user.id)
    assert len(conditions) == 2
    assert conditions[0]["code"]["text"] == "current condition"
    assert conditions[0]["recordedDate"] == "2024-01-17T11:24:00Z"
    assert conditions[1]["code"]["text"] == "past condition"
    assert conditions[1]["recordedDate"] == "2024-01-17T11:24:00Z"


def test_no_condition_answers(factories, default_user):
    questionnaire = factories.QuestionnaireFactory.create()
    recorded_answer_set = factories.RecordedAnswerSetFactory.create(
        source_user_id=default_user.id, questionnaire_id=questionnaire.id
    )
    result = Condition.get_from_questionnaire_answers_for_user(
        recorded_answer_set, default_user
    )
    assert result == []


def test_condition_answer_exists(factories, default_user):
    questionnaire = factories.QuestionnaireFactory.create()
    question = factories.QuestionFactory.create(
        question_set_id=questionnaire.question_sets[0].id, type=QuestionTypes.CONDITION
    )
    recorded_answer_set = factories.RecordedAnswerSetFactory.create(
        source_user_id=default_user.id, questionnaire_id=questionnaire.id
    )
    recorded_answer_set.recorded_answers.append(
        factories.RecordedAnswerFactory.create(
            user_id=default_user.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=question.id,
            payload={"items": ["endometriosis"]},
        )
    )
    result = Condition.get_from_questionnaire_answers_for_user(
        recorded_answer_set, default_user
    )
    assert len(result) == 1
    assert result[0]["code"] == {"text": "endometriosis"}
    assert result[0]["recordedDate"] == recorded_answer_set.submitted_at.isoformat()
