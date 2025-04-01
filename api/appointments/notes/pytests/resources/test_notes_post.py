import json
from unittest.mock import patch

import pytest
from maven import feature_flags

from appointments.services.common import obfuscate_appointment_id
from models.questionnaires import (
    COACHING_NOTES_COACHING_PROVIDERS_OID,
    PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
    QuestionTypes,
)
from pytests import factories
from utils.exceptions import DraftUpdateAttemptException
from utils.flag_groups import MPACTICE_NOTES_WRITING_WITHOUT_APPT_RELEASE


@pytest.fixture
def ff_test_data():
    with feature_flags.test_data() as td:
        yield td


@pytest.fixture
def member_schedule(enterprise_user):
    return factories.ScheduleFactory.create(user=enterprise_user)


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
def addendum_questionnaire():
    return factories.QuestionnaireFactory.create(oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID)


@pytest.fixture
def internal_note_questionnaire():
    return factories.QuestionnaireFactory.create(
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID
    )


class TestNotesAppointmentsErrors:
    def test_no_post_session_internal_note_addendum_args(
        self, client, api_helpers, appointment, provider
    ):
        # Act
        res = client.post(
            f"/api/v1/appointments/{_obfuscate_appointment(appointment.id)}/notes",
            headers=api_helpers.json_headers(user=provider),
            data={},
        )

        # Assert
        assert res.status_code == 400

    def test_no_appointment_found(self, client, api_helpers, provider):
        # Arrange
        request_args = {
            "post_session": {
                "draft": True,
                "notes": "test of the post session notes",
            },
            "structured_internal_note": {
                "recorded_answers": [
                    {
                        "appointment_id": 5555555,
                        "text": "hi there",
                    }
                ],
            },
            "provider_addenda": {
                "provider_addenda": [],
            },
        }

        # Act
        res = client.post(
            "/api/v1/appointments/5555555/notes",
            headers=api_helpers.json_headers(user=provider),
            data=json.dumps(request_args),
        )

        # Assert
        assert res.status_code == 404

    def test_no_permission_over_appointment(self, client, api_helpers, appointment):
        # Arrange
        request_args = {
            "post_session": {
                "draft": True,
                "notes": "test of the post session notes",
            },
            "structured_internal_note": {
                "recorded_answers": [
                    {
                        "text": "hi there",
                    }
                ],
            },
            "provider_addenda": {
                "provider_addenda": [],
            },
        }
        another_provider = factories.PractitionerUserFactory.create()

        # Act
        res = client.post(
            f"/api/v1/appointments/{_obfuscate_appointment(appointment.id)}/notes",
            headers=api_helpers.json_headers(user=another_provider),
            data=json.dumps(request_args),
        )

        # Assert
        assert res.status_code == 403

    def test_no_completed_encounter_summary_for_addendum(
        self, client, api_helpers, appointment, provider, addendum_questionnaire
    ):
        # Arrange
        request_args = {
            "provider_addenda": {
                "provider_addenda": [
                    {
                        "appointment_id": str(appointment.id),
                        "questionnaire_id": str(addendum_questionnaire.id),
                    }
                ],
            },
        }

        # Act
        res = client.post(
            f"/api/v1/appointments/{_obfuscate_appointment(appointment.id)}/notes",
            headers=api_helpers.json_headers(user=provider),
            data=json.dumps(request_args),
        )

        # Assert
        assert res.status_code == 422
        assert (
            json.loads(res.get_data().decode("utf-8")).get("message")
            == "An addendum can only be added if the encounter summary has been completed"
        )

    def test_draft_update_attempt_exception_should_retrurn_409(
        self, client, api_helpers, appointment, provider, internal_note_questionnaire
    ):
        # Arrange
        questions = internal_note_questionnaire.question_sets[0].questions

        # Find a text question
        text_question = next(q for q in questions if q.type == QuestionTypes.TEXT)
        recorded_answers = [
            {
                "question_id": text_question.id,
                "text": "Testing the answer",
                "answer_id": None,
                "date": None,
            },
        ]
        request_args = {
            "post_session": {
                "draft": True,
                "notes": "test of the post session notes",
            },
            "structured_internal_note": {
                "recorded_answer_set": {
                    "source_user_id": appointment.practitioner.id,
                    "draft": True,
                    "appointment_id": appointment.id,
                    "questionnaire_id": internal_note_questionnaire.id,
                    "recorded_answers": recorded_answers,
                }
            },
        }

        with patch(
            "appointments.notes.resources.notes.is_save_notes_without_appointment_table"
        ) as mock_is_save_notes_without_appointment_table, patch(
            "appointments.notes.resources.notes.update_internal_note_v2"
        ) as mock_update_internal_note_v2:
            mock_is_save_notes_without_appointment_table.return_value = True
            mock_update_internal_note_v2.side_effect = DraftUpdateAttemptException("na")

            res = client.post(
                f"/api/v1/appointments/{_obfuscate_appointment(appointment.id)}/notes",
                headers=api_helpers.json_headers(user=provider),
                data=json.dumps(request_args),
            )

            # Assert
            assert res.status_code == 409

    def test_no_addendum_questionnaire(
        self, client, api_helpers, appointment, provider, internal_note_questionnaire
    ):
        # Arrange
        internal_note_question_set = factories.QuestionSetFactory.create(
            questionnaire_id=internal_note_questionnaire.id
        )
        internal_note_question = factories.QuestionFactory.create(
            question_set_id=internal_note_question_set.id
        )
        recorded_answer_set = factories.RecordedAnswerSetFactory.create(
            source_user_id=provider.id,
            questionnaire_id=internal_note_questionnaire.id,
            draft=False,
            appointment_id=appointment.id,
        )
        factories.RecordedAnswerFactory.create(
            user_id=provider.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=internal_note_question.id,
        )

        request_args = {
            "provider_addenda": {
                "provider_addenda": [
                    {
                        "appointment_id": str(appointment.id),
                        "associated_question_id": str(internal_note_question.id),
                    }
                ],
            },
        }

        # Act
        res = client.post(
            f"/api/v1/appointments/{_obfuscate_appointment(appointment.id)}/notes",
            headers=api_helpers.json_headers(user=provider),
            data=json.dumps(request_args),
        )

        # Assert
        assert res.status_code == 422
        assert (
            json.loads(res.get_data().decode("utf-8")).get("message")
            == "The answers are not for the correct questionnaire"
        )


class TestNotesAppointments:
    def test_return_appointment_notes_addendum_without_appointment_table(
        self,
        client,
        api_helpers,
        appointment,
        provider,
        addendum_questionnaire,
        internal_note_questionnaire,
        ff_test_data,
    ):
        ff_test_data.update(
            ff_test_data.flag(
                "release-mpractice-practitioner-addenda"
            ).variation_for_all(True)
        )
        ff_test_data.update(
            ff_test_data.flag(
                MPACTICE_NOTES_WRITING_WITHOUT_APPT_RELEASE
            ).variation_for_all(True)
        )
        internal_note_question = internal_note_questionnaire.question_sets[0].questions[
            0
        ]
        addendum_question = addendum_questionnaire.question_sets[0].questions[0]
        recorded_answer_set = factories.RecordedAnswerSetFactory.create(
            source_user_id=provider.id,
            questionnaire_id=internal_note_questionnaire.id,
            draft=False,
            appointment_id=appointment.id,
        )
        factories.RecordedAnswerFactory.create(
            user_id=provider.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=internal_note_question.id,
            text="test",
        )

        # Find a text question
        provider_addendum_answers = [
            {
                "question_id": addendum_question.id,
                "text": "Testing the answer",
                "answer_id": None,
            },
        ]
        request_args = {
            "provider_addenda": {
                "provider_addenda": [
                    {
                        "user_id": str(appointment.practitioner.id),
                        "appointment_id": str(appointment.id),
                        "associated_question_id": str(internal_note_question.id),
                        "provider_addendum_answers": provider_addendum_answers,
                        "questionnaire_id": str(addendum_questionnaire.id),
                    }
                ]
            },
        }

        with patch(
            "appointments.notes.resources.notes.add_provider_addendum_v2"
        ) as mock_add_provider_addendum_v2:
            res = client.post(
                f"/api/v1/appointments/{_obfuscate_appointment(appointment.id)}/notes",
                headers=api_helpers.json_headers(user=provider),
                data=json.dumps(request_args),
            )

            assert res.status_code == 201
            mock_add_provider_addendum_v2.assert_called_once_with(
                request_args, provider, appointment.id
            )

    def test_save_notes_without_appointment_table(
        self,
        client,
        api_helpers,
        appointment,
        provider,
        internal_note_questionnaire,
        ff_test_data,
    ):
        ff_test_data.update(
            ff_test_data.flag(
                MPACTICE_NOTES_WRITING_WITHOUT_APPT_RELEASE
            ).variation_for_all(True)
        )

        questions = internal_note_questionnaire.question_sets[0].questions

        # Find a text question
        text_question = next(q for q in questions if q.type == QuestionTypes.TEXT)
        recorded_answers = [
            {
                "question_id": text_question.id,
                "text": "Testing the answer",
                "answer_id": None,
                "date": None,
            },
        ]
        request_args = {
            "post_session": {
                "draft": True,
                "notes": "test of the post session notes",
            },
            "structured_internal_note": {
                "recorded_answer_set": {
                    "source_user_id": appointment.practitioner.id,
                    "draft": True,
                    "appointment_id": appointment.id,
                    "questionnaire_id": internal_note_questionnaire.id,
                    "recorded_answers": recorded_answers,
                }
            },
        }

        # Mock is_save_notes_without_appointment_table to return True
        with patch(
            "appointments.notes.resources.notes.update_post_session_send_appointment_note_message_v2"
        ) as mock_update_post_session, patch(
            "appointments.notes.resources.notes.update_internal_note_v2"
        ) as mock_update_internal_note:
            # Act
            res = client.post(
                f"/api/v1/appointments/{_obfuscate_appointment(appointment.id)}/notes",
                headers=api_helpers.json_headers(user=provider),
                data=json.dumps(request_args),
            )

            # Assert
            assert res.status_code == 201

            mock_update_post_session.assert_called_once_with(
                request_args, appointment.id
            )
            mock_update_internal_note.assert_called_once_with(
                request_args, provider, appointment.id
            )

    def test_return_appointment_notes(
        self, client, api_helpers, appointment, provider, internal_note_questionnaire
    ):
        # Arrange
        questions = internal_note_questionnaire.question_sets[0].questions

        # Find a text question
        text_question = next(q for q in questions if q.type == QuestionTypes.TEXT)
        recorded_answers = [
            {
                "question_id": text_question.id,
                "text": "Testing the answer",
                "answer_id": None,
                "date": None,
            },
        ]
        request_args = {
            "post_session": {
                "draft": True,
                "notes": "test of the post session notes",
            },
            "structured_internal_note": {
                "recorded_answer_set": {
                    "source_user_id": appointment.practitioner.id,
                    "draft": True,
                    "appointment_id": appointment.id,
                    "questionnaire_id": internal_note_questionnaire.id,
                    "recorded_answers": recorded_answers,
                }
            },
        }

        # Act
        res = client.post(
            f"/api/v1/appointments/{_obfuscate_appointment(appointment.id)}/notes",
            headers=api_helpers.json_headers(user=provider),
            data=json.dumps(request_args),
        )
        res_data = api_helpers.load_json(res)

        # Assert
        assert res.status_code == 200
        assert (
            res_data["post_session"]["notes"] == request_args["post_session"]["notes"]
        )
        assert (
            res_data["post_session"]["draft"] == request_args["post_session"]["draft"]
        )
        assert (
            res_data["structured_internal_note"]["recorded_answers"][0]["text"]
            == request_args["structured_internal_note"]["recorded_answer_set"][
                "recorded_answers"
            ][0]["text"]
        )
        assert (
            res_data["structured_internal_note"]["recorded_answer_set"]["draft"]
            == request_args["structured_internal_note"]["recorded_answer_set"]["draft"]
        )

    def test_return_appointment_notes_addendum(
        self,
        client,
        api_helpers,
        appointment,
        provider,
        addendum_questionnaire,
        internal_note_questionnaire,
        ff_test_data,
    ):
        # Arrange
        ff_test_data.update(
            ff_test_data.flag(
                "release-mpractice-practitioner-addenda"
            ).variation_for_all(True)
        )
        internal_note_question = internal_note_questionnaire.question_sets[0].questions[
            0
        ]
        addendum_question = addendum_questionnaire.question_sets[0].questions[0]
        recorded_answer_set = factories.RecordedAnswerSetFactory.create(
            source_user_id=provider.id,
            questionnaire_id=internal_note_questionnaire.id,
            draft=False,
            appointment_id=appointment.id,
        )
        factories.RecordedAnswerFactory.create(
            user_id=provider.id,
            recorded_answer_set_id=recorded_answer_set.id,
            question_id=internal_note_question.id,
            text="test",
        )

        # Find a text question
        provider_addendum_answers = [
            {
                "question_id": addendum_question.id,
                "text": "Testing the answer",
                "answer_id": None,
            },
        ]
        request_args = {
            "provider_addenda": {
                "provider_addenda": [
                    {
                        "user_id": str(appointment.practitioner.id),
                        "appointment_id": str(appointment.id),
                        "associated_question_id": str(internal_note_question.id),
                        "provider_addendum_answers": provider_addendum_answers,
                        "questionnaire_id": str(addendum_questionnaire.id),
                    }
                ]
            },
        }

        # Act
        res = client.post(
            f"/api/v1/appointments/{_obfuscate_appointment(appointment.id)}/notes",
            headers=api_helpers.json_headers(user=provider),
            data=json.dumps(request_args),
        )
        res_data = api_helpers.load_json(res)

        # Assert
        assert res.status_code == 200
        assert (
            res_data["provider_addenda"]["provider_addenda"][0][
                "provider_addendum_answers"
            ][0]["text"]
            == request_args["provider_addenda"]["provider_addenda"][0][
                "provider_addendum_answers"
            ][0]["text"]
        )


def _obfuscate_appointment(appointment_id):
    return str(obfuscate_appointment_id(appointment_id))
