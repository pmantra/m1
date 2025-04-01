from datetime import datetime

from models.FHIR.patient import (
    AGE_EXTENSION_URL,
    HEIGHT_EXTENSION_URL,
    WEIGHT_EXTENSION_URL,
    FHIRPatientSchemaData,
)
from models.questionnaires import (
    DOB_QUESTION_OID,
    GENDER_FREETEXT_QUESTION_OID,
    GENDER_MULTISELECT_QUESTION_OID,
    GENDER_OTHER_ANSWER_OID,
    HEIGHT_QUESTION_OID,
    WEIGHT_QUESTION_OID,
    QuestionTypes,
)
from pytests.freezegun import freeze_time


def test_gender_without_freetext(factories, member):
    questionnaire = factories.QuestionnaireFactory.create()
    question = factories.QuestionFactory.create(
        question_set_id=questionnaire.question_sets[0].id,
        type=QuestionTypes.CHECKBOX,
        oid=GENDER_MULTISELECT_QUESTION_OID,
    )
    recorded_answer_set = factories.RecordedAnswerSetFactory.create(
        source_user_id=member.id, questionnaire_id=questionnaire.id
    )
    recorded_answer_set.recorded_answers.append(
        factories.RecordedAnswerFactory.create(
            user_id=member.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=question.id,
            answer_id=question.answers[0].id,
        )
    )
    recorded_answer_set.recorded_answers.append(
        factories.RecordedAnswerFactory.create(
            user_id=member.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=question.id,
            answer_id=question.answers[1].id,
        )
    )
    result = FHIRPatientSchemaData.generate_for_user_from_questionnaire_answers(
        recorded_answer_set, member
    )
    assert result["gender"] == f"{question.answers[0].text},{question.answers[1].text}"


def test_gender_with_freetext(factories, member):
    questionnaire = factories.QuestionnaireFactory.create()
    multiselect_question = factories.QuestionFactory.create(
        question_set_id=questionnaire.question_sets[0].id,
        type=QuestionTypes.CHECKBOX,
        oid=GENDER_MULTISELECT_QUESTION_OID,
    )
    freetext_question = factories.QuestionFactory.create(
        question_set_id=questionnaire.question_sets[0].id,
        type=QuestionTypes.TEXT,
        oid=GENDER_FREETEXT_QUESTION_OID,
    )
    recorded_answer_set = factories.RecordedAnswerSetFactory.create(
        source_user_id=member.id, questionnaire_id=questionnaire.id
    )
    recorded_answer_set.recorded_answers.append(
        factories.RecordedAnswerFactory.create(
            user_id=member.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=multiselect_question.id,
            answer_id=next(
                a
                for a in multiselect_question.answers
                if a.oid == GENDER_OTHER_ANSWER_OID
            ).id,
        )
    )
    recorded_answer_set.recorded_answers.append(
        factories.RecordedAnswerFactory.create(
            user_id=member.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=freetext_question.id,
            payload={"text": "agender"},
        )
    )
    result = FHIRPatientSchemaData.generate_for_user_from_questionnaire_answers(
        recorded_answer_set, member
    )
    assert result["gender"] == "agender"


@freeze_time("2020-11-01")
def test_dob(factories, member):
    questionnaire = factories.QuestionnaireFactory.create()
    question = factories.QuestionFactory.create(
        question_set_id=questionnaire.question_sets[0].id,
        type=QuestionTypes.TEXT,
        oid=DOB_QUESTION_OID,
    )
    recorded_answer_set = factories.RecordedAnswerSetFactory.create(
        source_user_id=member.id, questionnaire_id=questionnaire.id
    )
    recorded_answer_set.recorded_answers.append(
        factories.RecordedAnswerFactory.create(
            user_id=member.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=question.id,
            payload={"text": "1989-08-01"},
        )
    )
    result = FHIRPatientSchemaData.generate_for_user_from_questionnaire_answers(
        recorded_answer_set, member
    )
    assert result["birthDate"] == "1989-08-01"
    assert {
        "url": AGE_EXTENSION_URL,
        "extension": [
            {"url": "age", "valueInteger": 31},
            {"url": "flagged", "valueBoolean": False},
            {"url": "label", "valueString": "age"},
        ],
    } in result["extension"]


def test_bmi(factories, member):
    questionnaire = factories.QuestionnaireFactory.create()
    height_question = factories.QuestionFactory.create(
        question_set_id=questionnaire.question_sets[0].id,
        type=QuestionTypes.TEXT,
        oid=HEIGHT_QUESTION_OID,
    )
    weight_question = factories.QuestionFactory.create(
        question_set_id=questionnaire.question_sets[0].id,
        type=QuestionTypes.TEXT,
        oid=WEIGHT_QUESTION_OID,
    )
    recorded_answer_set = factories.RecordedAnswerSetFactory.create(
        source_user_id=member.id, questionnaire_id=questionnaire.id
    )
    recorded_answer_set.recorded_answers.append(
        factories.RecordedAnswerFactory.create(
            user_id=member.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=height_question.id,
            payload={"text": "66"},
        )
    )
    recorded_answer_set.recorded_answers.append(
        factories.RecordedAnswerFactory.create(
            user_id=member.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=weight_question.id,
            payload={"text": "136"},
        )
    )
    result = FHIRPatientSchemaData.generate_for_user_from_questionnaire_answers(
        recorded_answer_set, member
    )

    assert {
        "url": HEIGHT_EXTENSION_URL,
        "extension": [
            {"url": "height", "valueInteger": 66},
            {"url": "label", "valueString": "height"},
        ],
    } in result["extension"]

    assert {
        "url": WEIGHT_EXTENSION_URL,
        "extension": [
            {"url": "weight", "valueInteger": 136},
            {"url": "flagged", "valueBoolean": False},
            {"url": "label", "valueString": "weight"},
        ],
    }


def test_extension_tracks(factories, member):
    def assert_track_extensions(fhir_tracks, url):
        assert fhir_tracks["url"] == url

        tracks_extensions = fhir_tracks[extension]

        assert len(tracks_extensions) == 2

        for tracks_extension in tracks_extensions:
            track = tracks_extension[extension]
            assert len(track) == 3

            if track[0]["valueString"] != "Pregnancy":
                continue

            assert track[0]["url"] == "name"

            assert track[1]["url"] == "period"
            assert track[1]["valuePeriod"] is not None

            assert track[2]["url"] == "currentPhase"
            assert track[2]["valueString"] is not None

    def assert_track_extensions_v2(fhir_tracks, url):
        assert fhir_tracks["url"] == url

        tracks_extensions = fhir_tracks[extension]

        assert len(tracks_extensions) == 2

        for tracks_extension in tracks_extensions:
            track = tracks_extension[extension]
            assert len(track) == 4

            if track[0]["valueString"] != "pregnancy":
                continue

            assert track[0]["url"] == "name"

            assert track[1]["url"] == "displayName"
            assert track[1]["valueString"] is not None

            assert track[2]["url"] == "period"
            assert track[2]["valuePeriod"] is not None

            assert track[3]["url"] == "currentPhase"
            assert track[3]["valueString"] is not None

    extension = "extension"
    tracks_extension_url = "https://mavenclinic.com/fhir/StructureDefinition/tracks"
    inactive_tracks_extension_url = (
        "https://mavenclinic.com/fhir/StructureDefinition/inactive-tracks"
    )

    factories.MemberTrackFactory.create(user=member, name="pregnancy")
    factories.MemberTrackFactory.create(user=member, name="fertility")
    factories.MemberTrackFactory.create(
        user=member,
        name="pregnancy",
        ended_at=datetime(2020, 12, 31, 23, 59, 59),
    )
    factories.MemberTrackFactory.create(
        user=member,
        name="fertility",
        ended_at=datetime(2020, 12, 31, 23, 59, 59),
    )

    result = FHIRPatientSchemaData.generate_for_user(member)

    tracks = result[extension][2]
    assert_track_extensions(tracks, tracks_extension_url)

    inactive_tracks = result[extension][3]
    assert_track_extensions(inactive_tracks, inactive_tracks_extension_url)

    result_v2 = FHIRPatientSchemaData.generate_for_user(member, 2)

    tracks_v2 = result_v2[extension][2]
    assert_track_extensions_v2(tracks_v2, tracks_extension_url)

    inactive_tracks_v2 = result_v2[extension][3]
    assert_track_extensions_v2(inactive_tracks_v2, inactive_tracks_extension_url)


def test_pregnancy_due_date(member):
    result = FHIRPatientSchemaData.get_pregnancy_due_date(user=member)
    assert result == member.health_profile.due_date


def test_get_patient_health_record(factories, member, client, api_helpers):

    factories.MemberTrackFactory.create(user=member, name="pregnancy")
    factories.MemberTrackFactory.create(user=member, name="fertility")

    res = client.get(
        f"/api/v1/users/{member.id}/patient_health_record",
        headers={**api_helpers.standard_headers(member), **api_helpers.json_headers()},
    )

    assert res.status_code == 200
