from members.services.async_encounter_summaries import AsyncEncounterSummariesService
from models.profiles import PractitionerProfile
from pytests.factories import VerticalFactory
from storage.connection import db


def test_get(async_encounter_summary_answer, async_encounter_summary_second):
    # Arrange
    async_encounter_summary = async_encounter_summary_answer.async_encounter_summary
    args = {
        "user_id": async_encounter_summary_second.user_id,
    }

    # Act
    results = AsyncEncounterSummariesService().get(args=args)

    # Assert
    assert results == [async_encounter_summary_second, async_encounter_summary]


def test_build_async_encounter_provider_data_no_name(
    async_encounter_summary_answer, async_encounter_summary_second
):
    # Arrange
    async_encounter_summary = async_encounter_summary_answer.async_encounter_summary
    async_encounter_list = [async_encounter_summary_second, async_encounter_summary]
    practitioner = (
        db.session.query(PractitionerProfile)
        .filter(PractitionerProfile.user_id == async_encounter_summary.provider_id)
        .one_or_none()
    )

    # Act
    (
        provider_name,
        provider_vertical,
    ) = AsyncEncounterSummariesService().build_async_encounter_provider_data(
        async_encounter_list
    )

    # Assert
    assert provider_name[async_encounter_summary.id]["first_name"] == ""
    assert provider_name[async_encounter_summary.id]["last_name"] == ""
    assert provider_vertical[async_encounter_summary.id] == [
        vertical.name for vertical in practitioner.verticals
    ]


def test_build_async_encounter_provider_data_with_first_name(
    async_encounter_summary_answer, async_encounter_summary_second
):
    # Arrange
    async_encounter_summary = async_encounter_summary_answer.async_encounter_summary
    async_encounter_list = [async_encounter_summary_second, async_encounter_summary]
    practitioner = (
        db.session.query(PractitionerProfile)
        .filter(PractitionerProfile.user_id == async_encounter_summary.provider_id)
        .one_or_none()
    )
    practitioner.first_name = "Gina"
    obgyn_vertical = VerticalFactory(name="OB-GYN")
    allergist_vertical = VerticalFactory(name="Allergist")
    practitioner.verticals = [obgyn_vertical, allergist_vertical]

    # Act
    (
        provider_name,
        provider_vertical,
    ) = AsyncEncounterSummariesService().build_async_encounter_provider_data(
        async_encounter_list
    )

    # Assert
    assert provider_name[async_encounter_summary.id]["first_name"] == "Gina"
    assert provider_name[async_encounter_summary.id]["last_name"] == ""
    assert provider_vertical[async_encounter_summary.id] == ["OB-GYN", "Allergist"]


def test_build_async_encounter_provider_data_with_last_name(
    async_encounter_summary_answer, async_encounter_summary_second
):
    # Arrange
    async_encounter_summary = async_encounter_summary_answer.async_encounter_summary
    async_encounter_list = [async_encounter_summary_second, async_encounter_summary]
    practitioner = (
        db.session.query(PractitionerProfile)
        .filter(PractitionerProfile.user_id == async_encounter_summary.provider_id)
        .one_or_none()
    )
    practitioner.last_name = "Bob"
    obgyn_vertical = VerticalFactory(name="OB-GYN")
    allergist_vertical = VerticalFactory(name="Allergist")
    practitioner.verticals = [obgyn_vertical, allergist_vertical]

    # Act
    (
        provider_name,
        provider_vertical,
    ) = AsyncEncounterSummariesService().build_async_encounter_provider_data(
        async_encounter_list
    )

    # Assert
    assert provider_name[async_encounter_summary.id]["first_name"] == ""
    assert provider_name[async_encounter_summary.id]["last_name"] == "Bob"
    assert provider_vertical[async_encounter_summary.id] == ["OB-GYN", "Allergist"]


def test_build_async_encounter_provider_data_with_name(
    async_encounter_summary_answer, async_encounter_summary_second
):
    # Arrange
    async_encounter_summary = async_encounter_summary_answer.async_encounter_summary
    async_encounter_list = [async_encounter_summary_second, async_encounter_summary]
    practitioner = (
        db.session.query(PractitionerProfile)
        .filter(PractitionerProfile.user_id == async_encounter_summary.provider_id)
        .one_or_none()
    )
    practitioner.first_name = "Gina"
    practitioner.last_name = "Bob"
    obgyn_vertical = VerticalFactory(name="OB-GYN")
    allergist_vertical = VerticalFactory(name="Allergist")
    practitioner.verticals = [obgyn_vertical, allergist_vertical]

    # Act
    (
        provider_name,
        provider_vertical,
    ) = AsyncEncounterSummariesService().build_async_encounter_provider_data(
        async_encounter_list
    )

    # Assert
    assert provider_name[async_encounter_summary.id]["first_name"] == "Gina"
    assert provider_name[async_encounter_summary.id]["last_name"] == "Bob"
    assert provider_vertical[async_encounter_summary.id] == ["OB-GYN", "Allergist"]


def test_build_async_encounter_questionnaire_data(
    async_encounter_summary_answer, async_encounter_summary_second
):
    # Arrange
    async_encounter_summary = async_encounter_summary_answer.async_encounter_summary
    async_encounter_list = [async_encounter_summary_second, async_encounter_summary]

    # Act
    result = AsyncEncounterSummariesService().build_async_encounter_questionnaire_data(
        async_encounter_list
    )

    # Assert
    assert [*result.keys()] == [
        async_encounter_summary_second.id,
        async_encounter_summary.id,
    ]
    async_encounter_second_data = result[async_encounter_summary_second.id]
    async_encounter_first_data = result[async_encounter_summary.id]
    assert {"id", "question_sets", "trigger_answer_ids"}.issubset(
        set(async_encounter_second_data["questionnaire"].keys())
    )
    async_second_questionnaire_data = async_encounter_second_data["questionnaire"]
    assert (
        async_second_questionnaire_data["id"]
        == async_encounter_summary_second.questionnaire.id
    )
    async_second_question_data = async_second_questionnaire_data["question_sets"][0][
        "questions"
    ][0]
    assert (
        async_second_question_data["id"]
        == async_encounter_summary_second.questionnaire.question_sets[0].questions[0].id
    )
    assert (
        async_second_question_data["answers"][0]["id"]
        == async_encounter_summary_second.questionnaire.question_sets[0]
        .questions[0]
        .answers[0]
        .id
    )
    async_first_questionnaire_data = async_encounter_first_data["questionnaire"]
    assert {"id", "question_sets", "trigger_answer_ids"}.issubset(
        set(async_first_questionnaire_data.keys())
    )
    assert (
        async_first_questionnaire_data["id"] == async_encounter_summary.questionnaire.id
    )
    async_first_question_data = async_first_questionnaire_data["question_sets"][0][
        "questions"
    ][0]
    assert (
        async_first_question_data["id"]
        == async_encounter_summary.questionnaire.question_sets[0].questions[0].id
    )
    assert (
        async_first_question_data["answers"][0]["id"]
        == async_encounter_summary.questionnaire.question_sets[0]
        .questions[0]
        .answers[0]
        .id
    )
