from datetime import datetime

import pytest

from appointments.models.appointment import Appointment
from authn.models.user import User
from authz.models.roles import ROLES
from models.questionnaires import (
    COACHING_NOTES_COACHING_PROVIDERS_OID,
    PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
    ProviderAddendum,
    ProviderAddendumAnswer,
    Questionnaire,
    RecordedAnswerSet,
)
from mpractice.models.note import (
    MPracticeAnswer,
    MPracticeProviderAddendum,
    MPracticeProviderAddendumAnswer,
    MPracticeQuestion,
    MPracticeQuestionnaire,
    MPracticeQuestionSet,
    MPracticeRecordedAnswer,
    MPracticeRecordedAnswerSet,
)
from mpractice.repository.mpractice_questionnaire import (
    MPracticeQuestionnaireRepository,
)
from pytests.factories import (
    AnswerFactory,
    ProviderAddendumAnswerFactory,
    ProviderAddendumFactory,
    QuestionFactory,
    QuestionnaireFactory,
    QuestionSetFactory,
    RecordedAnswerFactory,
    RecordedAnswerSetFactory,
    RoleFactory,
)
from storage.connection import db


@pytest.fixture(scope="function")
def questionnaire_100() -> Questionnaire:
    return QuestionnaireFactory.create(id=100)


@pytest.fixture(scope="function")
def questionnaire_200(practitioner_user) -> Questionnaire:
    return QuestionnaireFactory.create(
        id=200, oid=COACHING_NOTES_COACHING_PROVIDERS_OID
    )


@pytest.fixture(scope="function")
def questionnaire_300(practitioner_user) -> Questionnaire:
    return QuestionnaireFactory.create(id=300, oid="async_encounters_np_ca")


@pytest.fixture(scope="function")
def questionnaire_400(practitioner_user) -> Questionnaire:
    return QuestionnaireFactory.create(id=400, oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID)


@pytest.fixture(scope="function")
def recorded_answer_set_100(appointment_100, questionnaire_100, practitioner_user):
    question_set = QuestionSetFactory.create(questionnaire_id=questionnaire_100.id)
    question = QuestionFactory.create(question_set_id=question_set.id)
    recorded_answer = RecordedAnswerFactory.create(
        appointment_id=appointment_100.id,
        question=question,
        user_id=practitioner_user.id,
    )
    return RecordedAnswerSetFactory.create(
        id=100,
        source_user_id=practitioner_user.id,
        questionnaire_id=questionnaire_100.id,
        appointment_id=appointment_100.id,
        submitted_at=datetime(2024, 1, 1, 0, 0, 0),
        modified_at=datetime(2024, 2, 1, 0, 0, 0),
        recorded_answers=[recorded_answer],
    )


@pytest.fixture(scope="function")
def recorded_answer_set_200(appointment_100, questionnaire_200, practitioner_user):
    return RecordedAnswerSetFactory.create(
        id=200,
        source_user_id=practitioner_user.id,
        questionnaire_id=questionnaire_200.id,
        appointment_id=appointment_100.id,
        submitted_at=datetime(2024, 1, 15, 0, 0, 0),
        modified_at=datetime(2024, 2, 1, 0, 0, 0),
    )


@pytest.fixture(scope="function")
def provider_addendum_400(
    appointment_400, questionnaire_400, practitioner_user
) -> ProviderAddendum:
    return ProviderAddendumFactory.create(
        id=400,
        appointment_id=appointment_400.id,
        appointment=appointment_400,
        questionnaire=questionnaire_400,
        user=practitioner_user,
        submitted_at=datetime(2024, 2, 1, 10, 0, 0),
    )


@pytest.fixture(scope="function")
def provider_addendum_answer_400(
    provider_addendum_400, questionnaire_400
) -> ProviderAddendumAnswer:
    return ProviderAddendumAnswerFactory.create(
        provider_addendum=provider_addendum_400,
        question=questionnaire_400.question_sets[0].questions[0],
    )


class TestMPracticeQuestionnaireRepository:
    def test_get_recorded_answer_set_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_recorded_answer_set(
            appointment_id=404, practitioner_id=404
        )
        assert result is None

    def test_get_recorded_answer_set_returns_expected_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        practitioner_user: User,
        appointment_100: Appointment,
        recorded_answer_set_100: RecordedAnswerSet,
        recorded_answer_set_200: RecordedAnswerSet,
    ):
        result = questionnaire_repo.get_recorded_answer_set(
            appointment_id=appointment_100.id, practitioner_id=practitioner_user.id
        )
        expected = MPracticeRecordedAnswerSet(
            id=recorded_answer_set_200.id,
            appointment_id=recorded_answer_set_200.appointment_id,
            questionnaire_id=recorded_answer_set_200.questionnaire_id,
            source_user_id=recorded_answer_set_200.source_user_id,
            draft=recorded_answer_set_200.draft,
            modified_at=recorded_answer_set_200.modified_at,
            submitted_at=recorded_answer_set_200.submitted_at,
        )
        assert result == expected

    def test_get_questionnaire_by_recorded_answer_set_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_questionnaire_by_recorded_answer_set(
            appointment_id=404, practitioner_id=404
        )
        assert result is None

    def test_get_questionnaire_by_recorded_answer_set_returns_expected_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        practitioner_user: User,
        appointment_100: Appointment,
        questionnaire_100: Questionnaire,
        recorded_answer_set_100: RecordedAnswerSet,
    ):
        result = questionnaire_repo.get_questionnaire_by_recorded_answer_set(
            appointment_id=appointment_100.id, practitioner_id=practitioner_user.id
        )
        expected = MPracticeQuestionnaire(
            id=questionnaire_100.id,
            description_text=questionnaire_100.description_text,
            oid=questionnaire_100.oid,
            sort_order=questionnaire_100.sort_order,
            title_text=questionnaire_100.title_text,
            soft_deleted_at=None,
        )
        assert result == expected

    def test_get_questionnaires_by_practitioner_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_questionnaires_by_practitioner(
            practitioner_id=404
        )
        assert result == []

    def test_get_questionnaires_by_practitioner_filters_out_async_encounter_questionnaire(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        questionnaire_300: Questionnaire,
        practitioner_user: User,
    ):
        query = """
            INSERT INTO questionnaire_vertical (questionnaire_id, vertical_id)
            VALUES (:questionnaire_id_300, :vertical_id);
        """
        vertical_id = practitioner_user.practitioner_profile.verticals[0].id
        db.session.execute(
            query,
            {
                "questionnaire_id_300": questionnaire_300.id,
                "vertical_id": vertical_id,
            },
        )
        result = questionnaire_repo.get_questionnaires_by_practitioner(
            practitioner_id=practitioner_user.id
        )
        assert result == []

    def test_get_questionnaires_by_practitioner_returns_expected_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        questionnaire_200: Questionnaire,
        questionnaire_400: Questionnaire,
        practitioner_user: User,
    ):
        vertical_id = practitioner_user.practitioner_profile.verticals[0].id
        query = """
           INSERT INTO questionnaire_vertical (questionnaire_id, vertical_id)
           VALUES (:questionnaire_id_200, :vertical_id), (:questionnaire_id_400, :vertical_id);
       """
        db.session.execute(
            query,
            {
                "questionnaire_id_200": questionnaire_200.id,
                "questionnaire_id_400": questionnaire_400.id,
                "vertical_id": vertical_id,
            },
        )
        result = questionnaire_repo.get_questionnaires_by_practitioner(
            practitioner_id=practitioner_user.id
        )
        expected = [
            MPracticeQuestionnaire(
                id=questionnaire_400.id,
                sort_order=questionnaire_400.sort_order,
                oid=questionnaire_400.oid,
                description_text=questionnaire_400.description_text,
                title_text=questionnaire_400.title_text,
                soft_deleted_at=None,
            ),
            MPracticeQuestionnaire(
                id=questionnaire_200.id,
                sort_order=questionnaire_200.sort_order,
                oid=questionnaire_200.oid,
                description_text=questionnaire_200.description_text,
                title_text=questionnaire_200.title_text,
                soft_deleted_at=None,
            ),
        ]
        assert result == expected

    def test_get_questionnaire_by_oid_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_questionnaire_by_oid(
            oid=COACHING_NOTES_COACHING_PROVIDERS_OID
        )
        assert result is None

    def test_get_questionnaire_by_oid_returns_expected_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        practitioner_user: User,
        questionnaire_200: Questionnaire,
        questionnaire_300: Questionnaire,
    ):
        result = questionnaire_repo.get_questionnaire_by_oid(
            oid=COACHING_NOTES_COACHING_PROVIDERS_OID
        )
        expected = MPracticeQuestionnaire(
            id=questionnaire_200.id,
            sort_order=questionnaire_200.sort_order,
            description_text=questionnaire_200.description_text,
            oid=COACHING_NOTES_COACHING_PROVIDERS_OID,
            title_text=questionnaire_200.title_text,
            soft_deleted_at=None,
        )
        assert result == expected

    def test_get_question_sets_by_questionnaire_id_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_question_sets_by_questionnaire_id(
            questionnaire_id=404
        )
        assert result == []

    def test_get_question_sets_by_questionnaire_id_returns_expected_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        questionnaire_100: Questionnaire,
    ):
        result = questionnaire_repo.get_question_sets_by_questionnaire_id(
            questionnaire_id=questionnaire_100.id
        )
        expected = [
            MPracticeQuestionSet(
                id=question_set.id,
                oid=question_set.oid,
                sort_order=question_set.sort_order,
                prerequisite_answer_id=question_set.prerequisite_answer_id,
                soft_deleted_at=None,
            )
            for question_set in questionnaire_100.question_sets
        ]
        assert result == expected

    def test_get_question_sets_by_questionnaire_id_with_soft_deleted_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        questionnaire_repo_include_soft_deleted_question_sets: MPracticeQuestionnaireRepository,
    ):
        questionnaire = QuestionnaireFactory.create()
        soft_deleted_question_set = QuestionSetFactory.create(
            questionnaire_id=questionnaire.id,
            soft_deleted_at=datetime(2025, 1, 10, 8, 30),
        )

        # load non soft deleted data
        result_without_soft_deleted_data = (
            questionnaire_repo.get_question_sets_by_questionnaire_id(
                questionnaire_id=questionnaire.id
            )
        )
        expected = [
            MPracticeQuestionSet(
                id=question_set.id,
                oid=question_set.oid,
                sort_order=question_set.sort_order,
                prerequisite_answer_id=question_set.prerequisite_answer_id,
                soft_deleted_at=None,
            )
            for question_set in questionnaire.question_sets
        ]
        assert result_without_soft_deleted_data == expected

        # load non soft deleted and soft deleted data
        result_with_soft_deleted_data = questionnaire_repo_include_soft_deleted_question_sets.get_question_sets_by_questionnaire_id(
            questionnaire_id=questionnaire.id
        )
        expected.append(
            MPracticeQuestionSet(
                id=soft_deleted_question_set.id,
                oid=soft_deleted_question_set.oid,
                sort_order=soft_deleted_question_set.sort_order,
                prerequisite_answer_id=soft_deleted_question_set.prerequisite_answer_id,
                soft_deleted_at=soft_deleted_question_set.soft_deleted_at,
            )
        )
        assert result_with_soft_deleted_data == expected

    def test_get_questions_by_question_set_ids_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_questions_by_question_set_ids(
            question_set_ids=[]
        )
        assert result == []
        result = questionnaire_repo.get_questions_by_question_set_ids(
            question_set_ids=[404]
        )
        assert result == []

    def test_get_questions_by_question_set_ids_with_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        questionnaire_100: Questionnaire,
    ):
        question_set_id = questionnaire_100.question_sets[0].id
        result = questionnaire_repo.get_questions_by_question_set_ids(
            question_set_ids=[question_set_id]
        )
        expected = [
            MPracticeQuestion(
                id=question.id,
                sort_order=question.sort_order,
                label=question.label,
                type=question.type.name,
                required=question.required,
                oid=question.oid,
                question_set_id=question_set_id,
                non_db_answer_options_json=question.non_db_answer_options_json,
                soft_deleted_at=question.soft_deleted_at,
            )
            for question in questionnaire_100.question_sets[0].questions
        ]
        assert result == expected

    def test_get_questions_by_question_set_ids_with_soft_deleted_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        questionnaire_repo_include_soft_deleted_question_sets: MPracticeQuestionnaireRepository,
    ):
        questionnaire = QuestionnaireFactory.create()
        question_set_id = questionnaire.question_sets[0].id
        soft_deleted_question = QuestionFactory.create(
            question_set_id=question_set_id,
            soft_deleted_at=datetime(2025, 1, 10, 8, 30),
        )

        # load non soft deleted data
        result_without_soft_deleted_data = (
            questionnaire_repo.get_questions_by_question_set_ids(
                question_set_ids=[question_set_id]
            )
        )
        expected = [
            MPracticeQuestion(
                id=question.id,
                sort_order=question.sort_order,
                label=question.label,
                type=question.type.name,
                required=question.required,
                oid=question.oid,
                question_set_id=question_set_id,
                non_db_answer_options_json=question.non_db_answer_options_json,
                soft_deleted_at=question.soft_deleted_at,
            )
            for question in questionnaire.question_sets[0].questions
        ]
        assert result_without_soft_deleted_data == expected

        # load non soft deleted and soft deleted data
        result_with_soft_deleted_data = questionnaire_repo_include_soft_deleted_question_sets.get_questions_by_question_set_ids(
            question_set_ids=[question_set_id]
        )
        expected.append(
            MPracticeQuestion(
                id=soft_deleted_question.id,
                sort_order=soft_deleted_question.sort_order,
                label=soft_deleted_question.label,
                type=soft_deleted_question.type.name,
                required=soft_deleted_question.required,
                oid=soft_deleted_question.oid,
                question_set_id=question_set_id,
                non_db_answer_options_json=soft_deleted_question.non_db_answer_options_json,
                soft_deleted_at=soft_deleted_question.soft_deleted_at,
            )
        )
        assert result_with_soft_deleted_data == expected

    def test_get_answers_by_question_ids_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_answers_by_question_ids(question_ids=[])
        assert result == []
        result = questionnaire_repo.get_answers_by_question_ids(question_ids=[404])
        assert result == []

    def test_get_answers_by_question_ids_returns_expected_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository, questionnaire_100
    ):
        question_id = questionnaire_100.question_sets[0].questions[0].id
        result = questionnaire_repo.get_answers_by_question_ids(
            question_ids=[question_id]
        )
        expected = [
            MPracticeAnswer(
                id=answer.id,
                sort_order=answer.sort_order,
                oid=answer.oid,
                question_id=question_id,
                text=answer.text,
                soft_deleted_at=answer.soft_deleted_at,
            )
            for answer in questionnaire_100.question_sets[0].questions[0].answers
        ]
        assert result == expected

    def test_get_answers_by_question_ids_with_soft_deleted_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        questionnaire_repo_include_soft_deleted_question_sets: MPracticeQuestionnaireRepository,
    ):
        questionnaire = QuestionnaireFactory.create()
        question_id = questionnaire.question_sets[0].questions[0].id
        soft_deleted_answer = AnswerFactory.create(
            question_id=question_id, soft_deleted_at=datetime(2025, 1, 10, 8, 30)
        )

        # load non soft deleted data
        result_without_soft_deleted_data = (
            questionnaire_repo.get_answers_by_question_ids(question_ids=[question_id])
        )
        expected = [
            MPracticeAnswer(
                id=answer.id,
                sort_order=answer.sort_order,
                oid=answer.oid,
                question_id=question_id,
                text=answer.text,
                soft_deleted_at=answer.soft_deleted_at,
            )
            for answer in questionnaire.question_sets[0].questions[0].answers
        ]
        assert result_without_soft_deleted_data == expected

        # load non soft deleted and soft deleted data
        result_with_soft_deleted_data = questionnaire_repo_include_soft_deleted_question_sets.get_answers_by_question_ids(
            question_ids=[question_id]
        )
        expected.append(
            MPracticeAnswer(
                id=soft_deleted_answer.id,
                sort_order=soft_deleted_answer.sort_order,
                oid=soft_deleted_answer.oid,
                question_id=question_id,
                text=soft_deleted_answer.text,
                soft_deleted_at=soft_deleted_answer.soft_deleted_at,
            )
        )
        assert result_with_soft_deleted_data == expected

    def test_get_recorded_answers_by_recorded_answer_set_id_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_recorded_answers_by_recorded_answer_set_id(
            recorded_answer_set_id=404
        )
        assert result == []

    def test_get_recorded_answers_by_recorded_answer_set_id_returns_expected_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        recorded_answer_set_100: RecordedAnswerSet,
    ):
        result = questionnaire_repo.get_recorded_answers_by_recorded_answer_set_id(
            recorded_answer_set_id=recorded_answer_set_100.id
        )
        expected = [
            MPracticeRecordedAnswer(
                question_id=recorded_answer.question_id,
                user_id=recorded_answer.user_id,
                appointment_id=recorded_answer.appointment_id,
                question_type_in_enum=recorded_answer.question.type,
                answer_id=recorded_answer.answer_id,
                text=recorded_answer.text,
                date=recorded_answer.date,
                payload_string=recorded_answer.payload,
            )
            for recorded_answer in recorded_answer_set_100.recorded_answers
        ]
        assert result == expected

    def test_get_legacy_recorded_answers_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_legacy_recorded_answers(
            appointment_id=404, practitioner_id=404
        )
        assert result == []

    def test_get_legacy_recorded_answers_returns_expected_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        practitioner_user: User,
        appointment_100: Appointment,
        recorded_answer_set_100: RecordedAnswerSet,
    ):
        result = questionnaire_repo.get_legacy_recorded_answers(
            appointment_id=appointment_100.id, practitioner_id=practitioner_user.id
        )
        expected = [
            MPracticeRecordedAnswer(
                question_id=recorded_answer.question_id,
                user_id=recorded_answer.user_id,
                appointment_id=recorded_answer.appointment_id,
                question_type_in_enum=recorded_answer.question.type,
                answer_id=recorded_answer.answer_id,
                text=recorded_answer.text,
                date=recorded_answer.date,
                payload_string=recorded_answer.payload,
            )
            for recorded_answer in recorded_answer_set_100.recorded_answers
        ]
        assert result == expected

    def test_get_roles_for_questionnaires_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_roles_for_questionnaires(questionnaire_ids=[])
        assert result == {}
        result = questionnaire_repo.get_roles_for_questionnaires(
            questionnaire_ids=[404]
        )
        assert result == {}

    def test_get_roles_for_questionnaires_returns_expected_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        questionnaire_100: Questionnaire,
    ):
        member_role = RoleFactory.create(name=ROLES.member)
        care_coordinator_role = RoleFactory(name=ROLES.care_coordinator)
        query = """
           INSERT INTO questionnaire_role (questionnaire_id, role_id)
           VALUES (:questionnaire_id, :member_role_id), (:questionnaire_id, :care_coordinator_role_id);
       """
        db.session.execute(
            query,
            {
                "questionnaire_id": questionnaire_100.id,
                "member_role_id": member_role.id,
                "care_coordinator_role_id": care_coordinator_role.id,
            },
        )
        result = questionnaire_repo.get_roles_for_questionnaires(
            questionnaire_ids=[questionnaire_100.id]
        )
        assert result == {questionnaire_100.id: [ROLES.member, ROLES.care_coordinator]}

    def test_get_trigger_answer_ids_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_trigger_answer_ids(questionnaire_id=404)
        assert result == []

    def test_get_trigger_answer_ids_returns_expected_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        questionnaire_100: Questionnaire,
    ):
        questionnaire_id = questionnaire_100.id
        answer_id = questionnaire_100.question_sets[0].questions[0].answers[0].id
        query = """
            INSERT INTO questionnaire_trigger_answer (questionnaire_id, answer_id)
            VALUES (:questionnaire_id, :answer_id);
        """
        db.session.execute(
            query, {"questionnaire_id": questionnaire_id, "answer_id": answer_id}
        )
        result = questionnaire_repo.get_trigger_answer_ids(
            questionnaire_id=questionnaire_id
        )
        expected = [answer_id]
        assert result == expected

    def test_get_provider_addenda_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_provider_addenda(
            appointment_id=404, practitioner_id=404, questionnaire_id=404
        )
        assert result == []

    def test_get_provider_addenda_returns_expected_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        practitioner_user: User,
        provider_addendum_400: ProviderAddendum,
    ):
        result = questionnaire_repo.get_provider_addenda(
            appointment_id=400,
            questionnaire_id=400,
            practitioner_id=practitioner_user.id,
        )
        expected = [
            MPracticeProviderAddendum(
                id=provider_addendum_400.id,
                questionnaire_id=provider_addendum_400.questionnaire_id,
                user_id=provider_addendum_400.user_id,
                appointment_id=provider_addendum_400.appointment_id,
                submitted_at=provider_addendum_400.submitted_at,
            )
        ]
        assert result == expected

    def test_get_provider_addenda_answers_no_data(
        self, questionnaire_repo: MPracticeQuestionnaireRepository
    ):
        result = questionnaire_repo.get_provider_addenda_answers(addendum_ids=[])
        assert result == []
        result = questionnaire_repo.get_provider_addenda_answers(addendum_ids=[404])
        assert result == []

    def test_get_provider_addenda_answers_returns_expected_data(
        self,
        questionnaire_repo: MPracticeQuestionnaireRepository,
        provider_addendum_answer_400: ProviderAddendumAnswer,
    ):
        result = questionnaire_repo.get_provider_addenda_answers(addendum_ids=[400])
        expected = [
            MPracticeProviderAddendumAnswer(
                question_id=provider_addendum_answer_400.question_id,
                addendum_id=400,
                answer_id=provider_addendum_answer_400.answer_id,
                text=provider_addendum_answer_400.text,
                date=provider_addendum_answer_400.date,
            )
        ]
        assert result == expected
