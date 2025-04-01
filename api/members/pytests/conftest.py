import datetime

import pytest

from members.pytests.factories import (
    AsyncEncounterSummaryAnswerFactory,
    AsyncEncounterSummaryFactory,
)
from members.repository.async_encounter_summary import AsyncEncounterSummaryRepository
from pytests.factories import (
    AppointmentFactory,
    EnterpriseUserFactory,
    PractitionerUserFactory,
    QuestionnaireFactory,
    VerticalFactory,
)

now = datetime.datetime.utcnow()


@pytest.fixture
def member():
    return EnterpriseUserFactory.create()


@pytest.fixture
def practitioner_user():
    ca_vertical = VerticalFactory(name="Care Advocate", filter_by_state=False)
    return PractitionerUserFactory.create(practitioner_profile__verticals=[ca_vertical])


@pytest.fixture
def new_practitioner():
    ob_vertical = VerticalFactory(name="OB-GYN")
    return PractitionerUserFactory.create(practitioner_profile__verticals=[ob_vertical])


@pytest.fixture
def new_practitioner_allergist():
    ob_vertical = VerticalFactory(name="Allergist")
    return PractitionerUserFactory.create(practitioner_profile__verticals=[ob_vertical])


@pytest.fixture
def valid_appointment_with_user():
    def make_valid_appointment_with_user(
        practitioner,
        scheduled_start=now,
        scheduled_end=None,
        purpose=None,
        member_schedule=None,
    ):
        a = AppointmentFactory.create_with_practitioner(
            member_schedule=member_schedule,
            purpose=purpose,
            practitioner=practitioner,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
        )
        return a

    return make_valid_appointment_with_user


@pytest.fixture
def valid_appointment(valid_appointment_with_user, practitioner_user):
    return valid_appointment_with_user(
        practitioner=practitioner_user,
        purpose="birth_needs_assessment",
        scheduled_start=now + datetime.timedelta(minutes=10),
    )


@pytest.fixture
def async_encounter_summary_repo(db):
    return AsyncEncounterSummaryRepository(db.session)


@pytest.fixture
def async_encounter_summary(practitioner_user, member):
    return AsyncEncounterSummaryFactory.create(
        provider=practitioner_user,
        user=member,
        encounter_date=datetime.date.today() - datetime.timedelta(days=2),
    )


@pytest.fixture
def async_encounter_summary_answer(async_encounter_summary):
    return AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[0],
    )


@pytest.fixture
def async_encounter_summary_second(practitioner_user, member):
    async_encounter_summary = AsyncEncounterSummaryFactory.create(
        provider=practitioner_user,
        user=member,
        encounter_date=now - datetime.timedelta(days=1),
    )
    AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[0],
    )
    return async_encounter_summary


@pytest.fixture
def async_encounter_summary_third(new_practitioner, member):
    async_encounter_summary = AsyncEncounterSummaryFactory.create(
        provider=new_practitioner,
        user=member,
        encounter_date=now - datetime.timedelta(hours=2),
    )
    AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[0],
    )
    AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[1],
    )
    return async_encounter_summary


@pytest.fixture
def async_encounter_summary_fourth(practitioner_user, member):
    async_encounter_summary = AsyncEncounterSummaryFactory.create(
        provider=practitioner_user,
        user=member,
        encounter_date=now - datetime.timedelta(days=1),
    )
    AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[0],
    )
    return async_encounter_summary


@pytest.fixture
def async_encounter_summary_fifth(practitioner_user, member):
    async_encounter_summary = AsyncEncounterSummaryFactory.create(
        provider=practitioner_user,
        user=member,
        encounter_date=now - datetime.timedelta(days=1),
    )
    AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[0],
    )
    return async_encounter_summary


@pytest.fixture
def async_encounter_summary_sixth(practitioner_user, member):
    async_encounter_summary = AsyncEncounterSummaryFactory.create(
        provider=practitioner_user,
        user=member,
        encounter_date=now - datetime.timedelta(days=1),
    )
    AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[0],
    )
    return async_encounter_summary


@pytest.fixture
def async_encounter_summary_seventh(practitioner_user, member):
    async_encounter_summary = AsyncEncounterSummaryFactory.create(
        provider=practitioner_user,
        user=member,
        encounter_date=now - datetime.timedelta(days=1),
    )
    AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[0],
    )
    return async_encounter_summary


@pytest.fixture
def async_encounter_summary_eighth(practitioner_user, member):
    async_encounter_summary = AsyncEncounterSummaryFactory.create(
        provider=practitioner_user,
        user=member,
        encounter_date=now - datetime.timedelta(days=1),
    )
    AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[0],
    )
    return async_encounter_summary


@pytest.fixture
def async_encounter_summary_ninth(practitioner_user, member):
    async_encounter_summary = AsyncEncounterSummaryFactory.create(
        provider=practitioner_user,
        user=member,
        encounter_date=now - datetime.timedelta(days=1),
    )
    AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[0],
    )
    return async_encounter_summary


@pytest.fixture
def async_encounter_summary_tenth(practitioner_user, member):
    async_encounter_summary = AsyncEncounterSummaryFactory.create(
        provider=practitioner_user,
        user=member,
        encounter_date=now - datetime.timedelta(days=1),
    )
    AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[0],
    )
    return async_encounter_summary


@pytest.fixture
def async_encounter_summary_eleventh(practitioner_user, member):
    async_encounter_summary = AsyncEncounterSummaryFactory.create(
        provider=practitioner_user,
        user=member,
        encounter_date=now - datetime.timedelta(days=1),
    )
    AsyncEncounterSummaryAnswerFactory.create(
        async_encounter_summary=async_encounter_summary,
        question=async_encounter_summary.questionnaire.question_sets[0].questions[0],
    )
    return async_encounter_summary


@pytest.fixture
def questionnaire():
    return QuestionnaireFactory.create()
