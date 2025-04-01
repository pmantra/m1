from models.FHIR.allergy import ALLERGY_INTOLERANCE_TYPE_URL, AllergyIntolerance
from models.questionnaires import QuestionTypes


def test_get_allergy_intolerance_by_user_no_allergy(factories, default_user):
    result = AllergyIntolerance.get_allergy_intolerance_by_user(default_user)
    assert result == []


def test_get_allergy_intolerance_by_user_allergy_exists(factories):
    user = factories.DefaultUserFactory.create()
    user.health_profile.json["food_allergies"] = "Shellfish,Wheat"
    user.health_profile.json["medications_allergies"] = "Sulfa Drugs,Penicillins"

    result = AllergyIntolerance.get_allergy_intolerance_by_user(user)
    assert len(result) == 4
    expected_allergies = ["Sulfa Drugs", "Penicillins", "Shellfish", "Wheat"]
    for i in range(len(result)):
        assert result[i]["resourceType"] == "AllergyIntolerance"
        assert result[i]["clinicalStatus"]["text"] == expected_allergies[i]


def test_no_allergy_answers(factories, default_user):
    questionnaire = factories.QuestionnaireFactory.create()
    recorded_answer_set = factories.RecordedAnswerSetFactory.create(
        source_user_id=default_user.id, questionnaire_id=questionnaire.id
    )
    result = AllergyIntolerance.get_from_questionnaire_answers_for_user(
        recorded_answer_set, default_user
    )
    assert result == []


def test_allergy_answer_exists(factories, default_user):
    questionnaire = factories.QuestionnaireFactory.create()
    question = factories.QuestionFactory.create(
        question_set_id=questionnaire.question_sets[0].id,
        type=QuestionTypes.ALLERGY_INTOLERANCE,
    )
    recorded_answer_set = factories.RecordedAnswerSetFactory.create(
        source_user_id=default_user.id, questionnaire_id=questionnaire.id
    )
    recorded_answer_set.recorded_answers.append(
        factories.RecordedAnswerFactory.create(
            user_id=default_user.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=question.id,
            payload={"items": [{"type": "food_other", "label": "gluten"}]},
        )
    )
    result = AllergyIntolerance.get_from_questionnaire_answers_for_user(
        recorded_answer_set, default_user
    )
    assert len(result) == 1
    assert result[0]["clinicalStatus"] == {"text": "gluten"}
    assert result[0]["recordedDate"] == recorded_answer_set.submitted_at.isoformat()
    assert result[0]["reaction"] == [{"description": "gluten"}]
    type_extension = {
        "url": ALLERGY_INTOLERANCE_TYPE_URL,
        "extension": [{"url": "type", "valueString": "food_other"}],
    }
    assert type_extension in result[0]["extension"]
