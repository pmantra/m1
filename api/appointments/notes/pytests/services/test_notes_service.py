import datetime
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import exc
from sqlalchemy.orm import Session
from tenacity import RetryError
from werkzeug.exceptions import HTTPException

import configuration
from appointments.models.appointment import PostSessionNoteUpdate
from appointments.models.appointment_meta_data import (
    AppointmentMetaData,
    PostAppointmentNoteUpdate,
)
from appointments.notes.services.notes import (
    MAX_CHAR_LENGTH,
    add_provider_addendum_v2,
    update_internal_note,
    update_internal_note_v2,
    update_post_session_send_appointment_note_message,
    update_post_session_send_appointment_note_message_v2,
)
from appointments.repository.appointment_metadata import AppointmentMetaDataRepository
from appointments.resources.appointment import AppointmentResource
from appointments.tasks.appointments import send_post_appointment_message
from models.questionnaires import (
    COACHING_NOTES_COACHING_PROVIDERS_OID,
    PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
    Answer,
    ProviderAddendumAnswer,
    Question,
    Questionnaire,
    QuestionTypes,
    RecordedAnswerSet,
)
from pytests import factories
from utils.exceptions import DraftUpdateAttemptException, UserInputValidationError


@pytest.fixture
def member():
    return factories.EnterpriseUserFactory.create()


@pytest.fixture
def member_schedule(member):
    return factories.ScheduleFactory.create(user=member)


@pytest.fixture
def provider():
    return factories.PractitionerUserFactory.create()


@pytest.fixture
def appointment(member_schedule, provider):
    return factories.AppointmentFactory.create_with_practitioner(
        member_schedule=member_schedule,
        practitioner=provider,
    )


@pytest.fixture
def post_session_note(appointment) -> AppointmentMetaData:
    return factories.AppointmentMetaDataFactory.create(
        appointment_id=appointment.id, content="note 1"
    )


@pytest.fixture
def structured_note_questionnaire():
    return factories.QuestionnaireFactory.create(
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID
    )


@pytest.fixture
def recorded_answers(
    structured_note_questionnaire, provider, question, recorded_answer_set
):
    question = factories.QuestionFactory.create(
        question_set_id=structured_note_questionnaire.question_sets[0].id,
        type=QuestionTypes.CONDITION,
    )
    recorded_answer_set = factories.RecordedAnswerSetFactory.create(
        source_user_id=provider.id, questionnaire_id=structured_note_questionnaire.id
    )
    return factories.RecordedAnswerFactory.create(
        user_id=provider.id,
        recorded_answer_set_id=recorded_answer_set.id,
        question_id=question.id,
        payload={"text": "agender"},
    )


@pytest.fixture
def mock_update_post_session_note(post_session_note, draft=False):
    with mock.patch(
        "appointments.models.appointment.Appointment.update_post_session"
    ) as m:
        m.return_value = PostSessionNoteUpdate(
            should_send=draft, post_session=post_session_note
        )
        yield m


@pytest.fixture
def mock_db_session():
    return MagicMock(spec=Session)


@pytest.fixture
def mock_addendum_db_session():
    with patch("storage.connection.db.session", new_callable=MagicMock) as mock_session:
        yield mock_session


@pytest.fixture
def mock_service_appointment_metadata_repo():
    with patch(
        "appointments.notes.services.notes.AppointmentMetaDataRepository"
    ) as mock_repo:
        yield mock_repo


@pytest.fixture
def mock_send_post_appointment_message():
    with patch(
        "appointments.notes.services.notes.send_post_appointment_message"
    ) as mock_task:
        yield mock_task


@pytest.fixture
def mock_sqlalchemy_error():
    with patch("appointments.notes.services.notes.exc.SQLAlchemyError") as mock_error:
        yield mock_error


@pytest.fixture
def mock_create_or_update_recorded_answer_set():
    with mock.patch("models.questionnaires.RecordedAnswerSet.create_or_update") as m:
        yield m


@pytest.fixture
def mock_provider_addendum_create():
    with patch("models.questionnaires.ProviderAddendum.create") as mock_create:
        yield mock_create


@pytest.fixture(scope="function")
def answer(question: Question) -> Answer:
    return Answer(
        id=1,
        sort_order=1,
        oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
        question_id=question.id,
        text="test text",
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def question() -> Question:
    return Question(
        id=1,
        sort_order=1,
        label="label",
        type=QuestionTypes.CONDITION.value,
        required=False,
        oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
        question_set_id=1,
        non_db_answer_options_json=None,
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def questionnaire() -> Questionnaire:
    return Questionnaire(
        id=1,
        sort_order=1,
        oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
        description_text="description",
        title_text="title",
        # soft_deleted_at=datetime.date(2024, 5, 22),
    )


@pytest.fixture(scope="function")
def provider_addendum_answer() -> ProviderAddendumAnswer:
    return ProviderAddendumAnswer(
        question_id=1,
        addendum_id=1,
        answer_id=1,
        text="test text",
        date=datetime.date(2024, 1, 1),
    )


@pytest.fixture()
def recorded_answer_set() -> RecordedAnswerSet:
    return RecordedAnswerSet(
        id=1,
        source_user_id=1,
        appointment_id=1,
        questionnaire_id=1,
        draft=False,
        modified_at=datetime.datetime(2024, 2, 1, 0, 0, 0),
        submitted_at=datetime.datetime(2024, 1, 1, 0, 0, 0),
    )


@pytest.fixture
def mock_abort():
    with patch("appointments.notes.services.notes.abort") as mock_abort_func:

        def abort_side_effect(*args, **kwargs):
            e = HTTPException(description=kwargs.get("description", "Unknown error"))
            e.code = args[0]
            raise e

        mock_abort_func.side_effect = abort_side_effect
        yield mock_abort_func


@pytest.fixture
def repository(mock_db_session):
    return AppointmentMetaDataRepository(session=mock_db_session)


class TestNotesServicePostSessionNotes:
    def test_create_or_update_creates_new_note_when_none_exists(self, repository):
        with patch.object(
            AppointmentMetaDataRepository, "get_by_appointment_id", return_value=None
        ):
            with patch(
                "appointments.repository.appointment_metadata.AppointmentMetaDataRepository.create"
            ) as mock_create:
                mock_create.return_value = MagicMock(spec=AppointmentMetaData)
                result = repository.create_or_update(1, "new content", True)

                assert result.should_send == False
                mock_create.assert_called_once_with("new content", True, 1)

    def test_create_or_update_returns_existing_note_if_no_change(self, repository):
        mock_note = MagicMock(
            spec=AppointmentMetaData, content="existing content", draft=True
        )
        with patch.object(
            AppointmentMetaDataRepository,
            "get_by_appointment_id",
            return_value=mock_note,
        ):
            result = repository.create_or_update(1, "existing content", True)

            assert result.post_session == mock_note
            assert result.should_send == False

    def test_create_or_update_warns_when_updating_draft_to_true(self, repository):
        mock_note = MagicMock(
            spec=AppointmentMetaData, content="existing content", draft=False
        )
        with patch.object(
            AppointmentMetaDataRepository,
            "get_by_appointment_id",
            return_value=mock_note,
        ):
            with pytest.raises(DraftUpdateAttemptException) as excinfo:
                repository.create_or_update(1, "updated content", True)

            assert (
                str(excinfo.value)
                == "Cannot re-submit appointment 1's post appointment note. Please refresh browser or restart your app."
            )

    def test_create_or_update_updates_note_when_changed(self, repository):
        mock_note = MagicMock(
            spec=AppointmentMetaData, content="existing content", draft=True
        )
        with patch.object(
            AppointmentMetaDataRepository,
            "get_by_appointment_id",
            return_value=mock_note,
        ):
            with patch(
                "appointments.repository.appointment_metadata.log.info"
            ) as mock_info:
                result = repository.create_or_update(1, "updated content", False)

                assert result.post_session == mock_note
                assert result.should_send == True
                assert mock_note.content == "updated content"
                assert mock_note.draft == False
                mock_info.assert_any_call(
                    "Update a post appointment note.",
                    draft=False,
                    appointment_id=1,
                )

    def test_update_post_appointment_note_v2_with_notes(
        self,
        mock_service_appointment_metadata_repo,
        mock_db_session,
        mock_send_post_appointment_message,
        appointment,
    ):
        mock_repo_instance = mock_service_appointment_metadata_repo.return_value
        mock_result = MagicMock(spec=PostAppointmentNoteUpdate)
        mock_result.should_send = True
        mock_repo_instance.create_or_update.return_value = mock_result

        args = {"post_session": {"notes": "fake notes", "draft": False}}
        appointment_id = appointment.id

        with patch(
            "appointments.notes.services.notes.db",
            new=MagicMock(session=mock_db_session),
        ):
            update_post_session_send_appointment_note_message_v2(args, appointment_id)

        mock_repo_instance.create_or_update.assert_called_once_with(
            appointment_id, "fake notes", False
        )
        mock_db_session.add.assert_called_once_with(mock_result.post_session)
        mock_db_session.commit.assert_called_once()
        mock_send_post_appointment_message.delay.assert_called_once_with(
            appointment_id=appointment_id,
            appointment_metadata_id=mock_result.post_session.id,
            team_ns="virtual_care",
        )

    def test_update_post_appointment_note_v2_with_draft(
        self,
        mock_db_session,
        mock_service_appointment_metadata_repo,
        mock_send_post_appointment_message,
        appointment,
        post_session_note,
    ):
        mock_repo_instance = mock_service_appointment_metadata_repo.return_value
        mock_result = MagicMock(spec=PostAppointmentNoteUpdate)
        mock_result.should_send = False
        mock_result.post_session.id = post_session_note.id
        mock_repo_instance.create_or_update.return_value = mock_result

        args = {"post_session": {"draft": True}}
        appointment_id = appointment.id

        with patch(
            "appointments.notes.services.notes.db",
            new=MagicMock(session=mock_db_session),
        ):
            update_post_session_send_appointment_note_message_v2(args, appointment_id)

        mock_repo_instance.create_or_update.assert_called_once_with(
            appointment_id, None, True
        )
        mock_db_session.add.assert_called_once_with(mock_result.post_session)
        mock_db_session.commit.assert_called_once()
        mock_send_post_appointment_message.delay.assert_not_called()

    def test_update_post_appointment_note_v2_no_notes_no_draft(
        self,
        mock_db_session,
        mock_service_appointment_metadata_repo,
        mock_send_post_appointment_message,
        appointment,
        post_session_note,
    ):
        args = {"post_session": {}}
        appointment_id = appointment.id

        update_post_session_send_appointment_note_message_v2(args, appointment_id)

        mock_service_appointment_metadata_repo.return_value.create_or_update.assert_not_called()
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()
        mock_send_post_appointment_message.delay.assert_not_called()

    def test_update_post_appointment_note_v2_sqlalchemy_error(
        self,
        mock_db_session,
        mock_service_appointment_metadata_repo,
        mock_send_post_appointment_message,
        appointment,
        post_session_note,
    ):
        mock_repo_instance = mock_service_appointment_metadata_repo.return_value
        mock_repo_instance.create_or_update.side_effect = exc.SQLAlchemyError(
            "Mock SQLAlchemyError"
        )

        args = {"post_session": {"notes": "Some notes", "draft": False}}
        appointment_id = appointment.id

        with patch(
            "appointments.notes.services.notes.db",
            new=MagicMock(session=mock_db_session),
        ):
            with pytest.raises(RetryError):
                update_post_session_send_appointment_note_message_v2(
                    args, appointment_id
                )

        mock_repo_instance.create_or_update.assert_called_with(
            appointment_id, "Some notes", False
        )
        assert mock_repo_instance.create_or_update.call_count == 3
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()
        mock_send_post_appointment_message.delay.assert_not_called()

    def test_update_post_session_send_appointment_note_message_not_member_or_provider(
        self, mock_update_post_session_note, appointment
    ):
        # Arrange
        non_appointment_member = factories.EnterpriseUserFactory.create()
        args = {
            "post_session": {
                "notes": "test of the post session notes",
                "draft": True,
            },
        }

        # Act
        update_post_session_send_appointment_note_message(
            args, non_appointment_member, appointment
        )

        # Assert
        assert mock_update_post_session_note.called is False
        assert appointment.client_notes is None

    def test_update_post_session_send_appointment_note_message_member(
        self, mock_update_post_session_note, member, appointment
    ):
        # Arrange
        args = {
            "post_session": {
                "notes": "test of the post session notes",
                "draft": True,
            },
        }

        # Act
        update_post_session_send_appointment_note_message(args, member, appointment)

        # Assert
        assert mock_update_post_session_note.called is False

    @pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
    @mock.patch("l10n.utils.localization_is_enabled")
    @mock.patch("l10n.utils.get_locale_from_member_preference")
    @mock.patch("appointments.tasks.appointments.PostSessionZendeskTicket")
    @mock.patch("appointments.tasks.appointment_notifications.send_sms")
    def test_send_post_appointment_message(
        self,
        mock_send_sms,
        mock_PostSessionZendeskTicket,
        mock_member_locale,
        mock_localization_is_enabled,
        locale,
        appointment,
    ):
        # Given
        mock_member_locale.return_value = locale
        appointment_meta_data = factories.AppointmentMetaDataFactory.create(
            appointment_id=appointment.id, content="note 1"
        )
        config = configuration.get_api_config()

        # When
        message = send_post_appointment_message(
            appointment_id=appointment.id,
            appointment_metadata_id=appointment_meta_data.id,
        )

        # Then
        member_post_appointment_note_message = {
            "en": (
                "Hi {member_first_name},\n\n I've left notes from our video session in your "
                "Appointments section:\n\n'{post_session_content}'\n\nYou can always review notes from our "
                "sessions under Me > Appointments.  Please let me know if you have any follow up "
                "questions.\n\nAppointments: {base_url}/my-appointments "
            ).format(
                member_first_name=appointment.member.first_name,
                post_session_content=appointment_meta_data.content,
                base_url=config.common.base_url,
            ),
            "es": "member_post_appointment_note_message",
            "fr": "member_post_appointment_note_message",
            "fr_CA": "member_post_appointment_note_message",
        }

        expected_message_arg = member_post_appointment_note_message[locale]
        if locale == "en":
            assert message.body == expected_message_arg
        else:
            assert message.body != expected_message_arg

        mock_PostSessionZendeskTicket.assert_called_once_with(
            appointment.practitioner,
            message,
            user_need_when_solving_ticket="customer-need-member-proactive-outreach-post-appointment-note",
        )

    @pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
    @mock.patch("l10n.utils.localization_is_enabled")
    @mock.patch("l10n.utils.get_locale_from_member_preference")
    @mock.patch("appointments.resources.appointment.PostSessionZendeskTicket")
    @mock.patch("appointments.tasks.appointment_notifications.send_sms")
    def test_AppointmentResource_send_post_appointment_note_message(
        self,
        mock_send_sms,
        mock_PostSessionZendeskTicket,
        mock_member_locale,
        mock_localization_is_enabled,
        locale,
        appointment,
    ):
        # Given
        mock_member_locale.return_value = locale
        appointment_meta_data = factories.AppointmentMetaDataFactory.create(
            appointment_id=appointment.id, content="note 1"
        )

        # When
        resource = AppointmentResource()
        message = resource._send_post_appointment_note_message(
            appointment=appointment, post_session=appointment_meta_data
        )

        # Then
        config = configuration.get_api_config()
        member_post_appointment_note_message = {
            "en": (
                "Hi {member_first_name},\n\n I've left notes from our video session in your "
                "Appointments section:\n\n'{post_session_content}'\n\nYou can always review notes from our "
                "sessions under Me > Appointments.  Please let me know if you have any follow up "
                "questions.\n\nAppointments: {base_url}/my-appointments "
            ).format(
                member_first_name=appointment.member.first_name,
                post_session_content=appointment_meta_data.content,
                base_url=config.common.base_url,
            ),
            "es": "member_post_appointment_note_message_es",
            "fr": "member_post_appointment_note_message_fr",
            "fr_CA": "member_post_appointment_note_message_fr_ca",
        }
        expected_message_arg = member_post_appointment_note_message[locale]
        if locale == "en":
            assert message.body == expected_message_arg
        else:
            assert message.body != expected_message_arg
        mock_PostSessionZendeskTicket.assert_called_once_with(
            appointment.practitioner,
            mock.ANY,
            user_need_when_solving_ticket="customer-need-member-proactive-outreach-post-appointment-note",
        )


class TestNotesServiceInternalNote:
    def test_update_internal_note_abort_max_char(self, provider, appointment):
        # Arrange
        over_max_char_string = "i" * (MAX_CHAR_LENGTH + 1)

        args = {
            "structured_internal_note": {
                "recorded_answer_set": {
                    "appointment_id": 123,
                    "recorded_answers": [
                        {
                            "text": over_max_char_string,
                        }
                    ],
                    "questionnaire_id": 456,
                },
                "recorded_answers": [
                    {
                        "text": over_max_char_string,
                    }
                ],
            }
        }

        # Act
        with pytest.raises(HTTPException) as e:
            update_internal_note(args, provider, appointment)

        # Assert
        assert "422" in str(e)

    def test_update_internal_note_new_recorded_answer_set(
        self, mock_create_or_update_recorded_answer_set, provider, appointment
    ):
        # Arrange
        args = {
            "structured_internal_note": {
                "recorded_answer_set": {
                    "appointment_id": 123,
                    "recorded_answers": [
                        {
                            "text": "hi there",
                        }
                    ],
                    "questionnaire_id": 456,
                },
            }
        }

        # Act
        update_internal_note(args, provider, appointment)

        # Assert
        assert mock_create_or_update_recorded_answer_set.called_with(
            args["structured_internal_note"]["recorded_answer_set"]
        )

    def test_update_internal_note_v2_new_recorded_answer_set(
        self, mock_create_or_update_recorded_answer_set, provider, appointment
    ):
        # Arrange
        args = {
            "structured_internal_note": {
                "recorded_answer_set": {
                    "appointment_id": appointment.id,
                    "recorded_answers": [
                        {
                            "text": "hi there",
                        }
                    ],
                    "questionnaire_id": 456,
                },
            }
        }

        # Act
        update_internal_note_v2(args, provider, appointment.id)

        # Assert
        assert mock_create_or_update_recorded_answer_set.called_with(
            args["structured_internal_note"]["recorded_answer_set"]
        )

    def test_update_internal_note_new_recorded_answers(
        self,
        mock_create_or_update_recorded_answer_set,
        provider,
        appointment,
        structured_note_questionnaire,
        recorded_answers,
    ):
        # Arrange
        args = {
            "structured_internal_note": {
                "recorded_answers": [
                    {
                        "text": "hi there",
                    }
                ]
            }
        }

        attrs = {
            "submitted_at": datetime.datetime.utcnow(),
            "source_user_id": provider.id,
            "draft": False,
            "appointment_id": appointment.id,
            "recorded_answers": recorded_answers,
            "questionnaire_id": structured_note_questionnaire.id,
        }

        # Act
        update_internal_note(args, provider, appointment)

        # Assert
        assert mock_create_or_update_recorded_answer_set.called_with(attrs)

    def test_update_internal_note_v2_new_recorded_answers(
        self,
        mock_create_or_update_recorded_answer_set,
        provider,
        appointment,
        structured_note_questionnaire,
        recorded_answers,
    ):
        # Arrange
        args = {
            "structured_internal_note": {
                "recorded_answers": [
                    {
                        "text": "hi there",
                    }
                ]
            }
        }

        attrs = {
            "submitted_at": datetime.datetime.utcnow(),
            "source_user_id": provider.id,
            "draft": False,
            "appointment_id": appointment.id,
            "recorded_answers": recorded_answers,
            "questionnaire_id": structured_note_questionnaire.id,
        }

        # Act
        update_internal_note_v2(args, provider, appointment.id)

        # Assert
        assert mock_create_or_update_recorded_answer_set.called_with(attrs)

    def test_update_internal_note_existing_recorded_answers(
        self,
        mock_create_or_update_recorded_answer_set,
        member,
        provider,
        appointment,
        recorded_answers,
    ):
        # Arrange
        args = {
            "structured_internal_note": {
                "recorded_answers": [
                    {
                        "text": "hi there",
                    }
                ]
            }
        }

        appointment.recorded_answers = [recorded_answers]

        # Act
        update_internal_note(args, provider, appointment)

        # Assert
        assert not mock_create_or_update_recorded_answer_set.called

    def test_update_internal_note_v2_existing_recorded_answers(
        self,
        mock_create_or_update_recorded_answer_set,
        member,
        provider,
        appointment,
        recorded_answers,
    ):
        # Arrange
        args = {
            "structured_internal_note": {
                "recorded_answers": [
                    {
                        "text": "hi there",
                    }
                ]
            }
        }

        appointment.recorded_answers = [recorded_answers]

        # Act
        update_internal_note_v2(args, provider, appointment.id)

        # Assert
        assert not mock_create_or_update_recorded_answer_set.called


class TestNotesServiceAddendumV2:
    def test_add_provider_addendum_v2_success(
        self, mock_addendum_db_session, mock_provider_addendum_create, provider
    ):
        completed_encounter_summary = MagicMock(id=1, draft=False)
        mock_addendum_db_session.query().join().filter().order_by().first.return_value = (
            completed_encounter_summary
        )
        mock_addendum_db_session.query().filter().scalar.return_value = 1

        args = {
            "provider_addenda": {
                "provider_addenda": [
                    {
                        "questionnaire_id": "1",
                        "associated_question_id": "1",
                        "provider_addendum_answers": [{"text": "Sample text"}],
                    }
                ]
            }
        }

        add_provider_addendum_v2(args, provider, 1)

        mock_provider_addendum_create.assert_called_once()
        mock_addendum_db_session.commit.assert_called_once()

    def test_add_provider_addendum_v2_invalid_provider_addenda_attrs(
        self,
        mock_addendum_db_session,
        mock_abort,
        mock_provider_addendum_create,
        provider,
    ):
        mock_user = provider
        mock_addendum_db_session.query().join().filter().order_by().first.return_value = MagicMock(
            draft=False
        )

        args = {"provider_addenda": {}}

        with pytest.raises(UserInputValidationError) as exc_info:
            add_provider_addendum_v2(args, mock_user, 1)

        assert mock_abort.call_count == 0

        assert (
            str(exc_info.value)
            == "An addendum submission must contain one completed provider addendum"
        )
