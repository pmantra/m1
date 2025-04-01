import datetime

now = datetime.datetime.utcnow()


def test_get_async_encounter_summary(
    async_encounter_summary_repo, async_encounter_summary_answer
):
    # Arrange
    async_encounter_summary_id = (
        async_encounter_summary_answer.async_encounter_summary.id
    )

    # Act & Assert
    assert (
        async_encounter_summary_repo.get(
            async_encounter_summary_id=async_encounter_summary_id
        ).id
        is async_encounter_summary_id
    )


def test_get_no_async_encounter_summary(async_encounter_summary_repo):
    # Act & Assert
    assert (
        async_encounter_summary_repo.get(async_encounter_summary_id=1234567890000)
        is None
    )


def test_get_async_summaries_no_args(
    async_encounter_summary_answer,
    async_encounter_summary_second,
    async_encounter_summary_third,
    async_encounter_summary_repo,
):
    # Act & Assert
    assert async_encounter_summary_repo.get_async_summaries() == []


def test_get_async_summaries_no_filters(
    async_encounter_summary_answer,
    async_encounter_summary_second,
    async_encounter_summary_third,
    async_encounter_summary_repo,
):
    # Arrange
    async_encounter_summary = async_encounter_summary_answer.async_encounter_summary
    args = {
        "user_id": async_encounter_summary.user_id,
        "provider_id": async_encounter_summary.provider_id,
    }

    # Act & Assert
    assert async_encounter_summary_repo.get_async_summaries(args=args) == [
        async_encounter_summary_third,
        async_encounter_summary_second,
        async_encounter_summary,
    ]


def test_no_matching_get_async_summaries(
    async_encounter_summary_answer, async_encounter_summary_repo, new_practitioner
):
    # Arrange
    async_encounter_summary = async_encounter_summary_answer.async_encounter_summary
    args = {
        "user_id": async_encounter_summary.user_id,
        "my_encounters": True,
        "provider_id": new_practitioner.id,
    }

    # Act & Assert
    assert async_encounter_summary_repo.get_async_summaries(args=args) == []


def test_get_async_summaries_sort_by_encounter_date_desc_provider_id_filter(
    async_encounter_summary_answer,
    async_encounter_summary_second,
    async_encounter_summary_repo,
):
    # Arrange
    async_encounter_summary = async_encounter_summary_answer.async_encounter_summary
    args = {
        "user_id": async_encounter_summary.user_id,
        "provider_id": async_encounter_summary.provider_id,
    }

    # Act & Assert
    assert async_encounter_summary_repo.get_async_summaries(args=args) == [
        async_encounter_summary_second,
        async_encounter_summary,
    ]


def test_get_async_summaries_scheduled_start_filter(
    async_encounter_summary_third,
    async_encounter_summary_second,
    async_encounter_summary_repo,
):
    # Arrange
    args = {
        "user_id": async_encounter_summary_third.user_id,
        "provider_id": async_encounter_summary_third.provider_id,
        "scheduled_start": now - datetime.timedelta(hours=6),
    }

    # Act & Assert
    assert async_encounter_summary_repo.get_async_summaries(args=args) == [
        async_encounter_summary_third
    ]


def test_get_async_summaries_scheduled_end_filter(
    async_encounter_summary_answer,
    async_encounter_summary_third,
    async_encounter_summary_second,
    async_encounter_summary_repo,
):
    # Arrange
    async_encounter_summary = async_encounter_summary_answer.async_encounter_summary
    args = {
        "user_id": async_encounter_summary_third.user_id,
        "provider_id": async_encounter_summary_third.provider_id,
        "scheduled_end": now - datetime.timedelta(hours=6),
    }

    # Act & Assert
    assert async_encounter_summary_repo.get_async_summaries(args=args) == [
        async_encounter_summary_second,
        async_encounter_summary,
    ]


def test_get_async_summaries_verticals_filter(
    async_encounter_summary_answer,
    async_encounter_summary_second,
    async_encounter_summary_repo,
):
    # Arrange
    async_encounter_summary = async_encounter_summary_answer.async_encounter_summary
    args = {
        "user_id": async_encounter_summary.user_id,
        "provider_id": async_encounter_summary.provider_id,
        "verticals": ["Care Advocate"],
    }

    # Act & Assert
    assert async_encounter_summary_repo.get_async_summaries(args=args) == [
        async_encounter_summary_second,
        async_encounter_summary,
    ]


def test_create_async_encounter_summary_with_answer_id(
    async_encounter_summary_repo, practitioner_user, member, questionnaire
):
    # Arrange
    question_id = questionnaire.question_sets[0].questions[0].id
    answer_id = questionnaire.question_sets[0].questions[0].answers[0].id

    # Act
    async_encounter_summary = async_encounter_summary_repo.create(
        provider_id=practitioner_user.id,
        user_id=member.id,
        questionnaire_id=questionnaire.id,
        encounter_date=now,
        async_encounter_summary_answers=[
            {
                "question_id": question_id,
                "answer_id": answer_id,
            }
        ],
    )

    # Assert
    assert async_encounter_summary.provider_id == practitioner_user.id
    assert async_encounter_summary.user_id == member.id
    assert async_encounter_summary.questionnaire.id == questionnaire.id
    assert async_encounter_summary.encounter_date == now
    assert (
        async_encounter_summary.async_encounter_summary_answers[0].question_id
        == question_id
    )
    assert (
        async_encounter_summary.async_encounter_summary_answers[0].answer_id
        == answer_id
    )


def test_create_async_encounter_summary_with_text(
    async_encounter_summary_repo, practitioner_user, member, questionnaire
):
    # Arrange
    question_id = questionnaire.question_sets[0].questions[0].id

    # Act
    async_encounter_summary = async_encounter_summary_repo.create(
        provider_id=practitioner_user.id,
        user_id=member.id,
        questionnaire_id=questionnaire.id,
        encounter_date=now,
        async_encounter_summary_answers=[
            {
                "question_id": question_id,
                "text": "This is the answer to a question",
            }
        ],
    )

    # Assert
    assert async_encounter_summary.provider_id == practitioner_user.id
    assert async_encounter_summary.user_id == member.id
    assert async_encounter_summary.questionnaire.id == questionnaire.id
    assert async_encounter_summary.encounter_date == now
    assert (
        async_encounter_summary.async_encounter_summary_answers[0].question_id
        == question_id
    )
    assert (
        async_encounter_summary.async_encounter_summary_answers[0].text
        == "This is the answer to a question"
    )


def test_create_async_encounter_summary_with_date(
    async_encounter_summary_repo, practitioner_user, member, questionnaire
):
    # Arrange
    question_id = questionnaire.question_sets[0].questions[0].id

    # Act
    async_encounter_summary = async_encounter_summary_repo.create(
        provider_id=practitioner_user.id,
        user_id=member.id,
        questionnaire_id=questionnaire.id,
        encounter_date=now,
        async_encounter_summary_answers=[
            {
                "question_id": question_id,
                "date": "2023-12-25T12:25:25.255Z",
            }
        ],
    )

    # Assert
    assert async_encounter_summary.provider_id == practitioner_user.id
    assert async_encounter_summary.user_id == member.id
    assert async_encounter_summary.questionnaire.id == questionnaire.id
    assert async_encounter_summary.encounter_date == now
    assert (
        async_encounter_summary.async_encounter_summary_answers[0].question_id
        == question_id
    )
    assert (
        async_encounter_summary.async_encounter_summary_answers[0].date
        == "2023-12-25T12:25:25.255Z"
    )
