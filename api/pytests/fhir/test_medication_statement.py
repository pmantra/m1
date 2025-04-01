from models.FHIR.medication import MedicationStatement
from models.questionnaires import QuestionTypes
from pytests.freezegun import freeze_time
from views.schemas.FHIR.medication import MedicationStatementStatusEnum


def test_get_medication_statement_by_user_no_medication(factories, default_user):
    result = MedicationStatement.get_medication_statement_by_user(default_user)
    assert result == []


@freeze_time("2024-01-18T13:10:00")
def test_get_medication_statement_by_user_medication_exists(factories):
    user = factories.DefaultUserFactory.create()
    user.health_profile.json[
        MedicationStatement.health_binder_fields_current
    ] = "current_medication"
    user.health_profile.json[
        MedicationStatement.health_binder_fields_past
    ] = "past_medication"
    result = MedicationStatement.get_medication_statement_by_user(user)
    assert len(result) == 2
    assert result[0]["note"][0]["text"] == "current_medication"
    assert result[0]["status"] == MedicationStatementStatusEnum.active.value
    assert result[0]["resourceType"] == "MedicationStatement"
    assert result[0]["dateAsserted"] == "2024-01-18 13:10:00"
    assert result[1]["note"][0]["text"] == "past_medication"
    assert result[1]["status"] == MedicationStatementStatusEnum.unknown.value
    assert result[1]["resourceType"] == "MedicationStatement"
    assert result[1]["dateAsserted"] == "2024-01-18 13:10:00"


def test_no_medication_answers(factories, default_user):
    questionnaire = factories.QuestionnaireFactory.create()
    recorded_answer_set = factories.RecordedAnswerSetFactory.create(
        source_user_id=default_user.id, questionnaire_id=questionnaire.id
    )
    result = MedicationStatement.get_from_questionnaire_answers_for_user(
        recorded_answer_set, default_user
    )
    assert result == []


def test_condition_answer_exists(factories, default_user):
    questionnaire = factories.QuestionnaireFactory.create()
    question = factories.QuestionFactory.create(
        question_set_id=questionnaire.question_sets[0].id, type=QuestionTypes.MEDICATION
    )
    recorded_answer_set = factories.RecordedAnswerSetFactory.create(
        source_user_id=default_user.id, questionnaire_id=questionnaire.id
    )
    recorded_answer_set.recorded_answers.append(
        factories.RecordedAnswerFactory.create(
            user_id=default_user.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=question.id,
            payload={"items": [{"status": "current", "label": "amrita"}]},
        )
    )
    result = MedicationStatement.get_from_questionnaire_answers_for_user(
        recorded_answer_set, default_user
    )
    assert len(result) == 1
    assert result[0]["dateAsserted"] == recorded_answer_set.submitted_at.isoformat()
    assert len(result[0]["note"]) == 1
    assert result[0]["note"][0]["text"] == "amrita"
