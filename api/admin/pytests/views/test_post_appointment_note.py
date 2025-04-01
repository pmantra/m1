from unittest import mock

import factory
import pytest

from appointments.models.appointment_meta_data import AppointmentMetaData
from authn.domain.model import User
from messaging.models.messaging import Channel, Message
from models.questionnaires import RecordedAnswerSet
from pytests.factories import (
    AppointmentFactory,
    AppointmentMetaDataFactory,
    ChannelFactory,
    ChannelUsersFactory,
    MessageFactory,
)


@pytest.fixture
def make_channel():
    def make_channel(practitioner, member):
        channel = ChannelFactory.create()
        ChannelUsersFactory.create_batch(
            size=2,
            channel_id=channel.id,
            user_id=factory.Iterator([member.id, practitioner.id]),
        )
        return channel

    return make_channel


@pytest.fixture
def make_post_appointment_note():
    def return_note(
        practitioner: User, channel: Channel, content: str, draft: bool = False
    ) -> AppointmentMetaData:
        appointment = AppointmentFactory.create_with_practitioner(
            practitioner=practitioner
        )
        message = MessageFactory.create(
            user_id=practitioner.id,
            user=practitioner,
            channel_id=channel.id,
            channel=channel,
            body=f"Post appointment note: {content}",
        )
        note = AppointmentMetaDataFactory.create(
            content=content,
            message=message,
            message_id=message.id,
            appointment=appointment,
            appointment_id=appointment.id,
            draft=draft,
        )
        return note

    return return_note


class TestPostAppointmentNoteGeneratedMessageCAManager:
    def test_redact_no_note_fails(self, admin_client):
        # when
        with mock.patch(
            "admin.views.models.schedules.feature_flags.bool_variation",
            return_value=True,
        ):
            res = admin_client.post(
                "/admin/appointmentmetadata/action/",
                data={
                    "action": "redact_generated_message",
                    "rowid": [-1],
                },
            )

        html = res.data.decode("utf8")
        assert res.status_code == 400
        assert "Note -1 does not exist." in html

    def test_redact_one_message(
        self, factories, make_post_appointment_note, make_channel, admin_client
    ):
        # given
        redacted_message = "This message has been removed."
        practitioner = factories.PractitionerUserFactory.create()
        member = factories.EnterpriseUserFactory.create()
        channel = make_channel(practitioner, member)
        note = make_post_appointment_note(practitioner, channel, "Note Content")
        assert note.draft is False

        questionnaire = factories.QuestionnaireFactory.create()
        encounter_summary = factories.RecordedAnswerSetFactory.create(
            source_user_id=practitioner.id,
            questionnaire_id=questionnaire.id,
            appointment_id=note.appointment_id,
            draft=False,
        )
        assert encounter_summary.draft is False

        # when
        with mock.patch(
            "admin.views.models.schedules.feature_flags.bool_variation",
            return_value=True,
        ):
            res = admin_client.post(
                "/admin/appointmentmetadata/action/",
                data={
                    "action": "redact_generated_message",
                    "rowid": [note.id],
                },
            )

        note_after = AppointmentMetaData.query.get(note.id)
        message_after = Message.query.get(note.message_id)
        summary_after = RecordedAnswerSet.query.get(encounter_summary.id)

        assert note_after.content == redacted_message
        assert message_after.body == redacted_message
        assert note_after.draft is True
        assert summary_after.draft is True
        # Note: following the redirect here breaks the test session, so 302 instead of 200
        assert res.status_code == 302

    def test_redact_multiple_messages_at_once_fails(
        self, factories, make_post_appointment_note, make_channel, admin_client
    ):
        # given
        practitioner = factories.PractitionerUserFactory.create()
        member = factories.EnterpriseUserFactory.create()
        channel = make_channel(practitioner, member)
        note1 = make_post_appointment_note(practitioner, channel, "Note Content")
        note2 = make_post_appointment_note(practitioner, channel, "Note Content")

        # when
        with mock.patch(
            "admin.views.models.schedules.feature_flags.bool_variation",
            return_value=True,
        ):
            res = admin_client.post(
                "/admin/appointmentmetadata/action",
                data={
                    "action": "redact_generated_message",
                    "rowid": [note1.id, note2.id],
                },
                follow_redirects=True,
            )

        html = res.data.decode("utf8")
        assert res.status_code == 400
        assert (
            "Bulk redaction is not allowed. Please redact one note at a time." in html
        )

    def test_redact_messages_flag_fails(
        self, factories, make_post_appointment_note, make_channel, admin_client
    ):
        # given
        practitioner = factories.PractitionerUserFactory.create()
        member = factories.EnterpriseUserFactory.create()
        channel = make_channel(practitioner, member)
        note = make_post_appointment_note(practitioner, channel, "Note Content")

        # when
        with mock.patch(
            "admin.views.models.schedules.feature_flags.bool_variation",
            return_value=False,
        ):
            res = admin_client.post(
                "/admin/appointmentmetadata/action",
                data={
                    "action": "redact_generated_message",
                    "rowid": [note.id],
                },
            )

        # then
        message_after = Message.query.get(note.message_id)
        assert message_after.body == "Post appointment note: Note Content"
        assert res.status_code == 308

    def test_redact_messages_flag_fails_with_redirect(
        self, factories, make_post_appointment_note, make_channel, admin_client
    ):
        # given
        practitioner = factories.PractitionerUserFactory.create()
        member = factories.EnterpriseUserFactory.create()
        channel = make_channel(practitioner, member)
        note = make_post_appointment_note(practitioner, channel, "Note Content")

        # when
        with mock.patch(
            "admin.views.models.schedules.feature_flags.bool_variation",
            return_value=False,
        ):
            res = admin_client.post(
                "/admin/appointmentmetadata/action",
                data={
                    "action": "redact_generated_message",
                    "rowid": [note.id],
                },
                follow_redirects=True,
            )

        # then
        html = res.data.decode("utf8")
        assert (
            "This user is not configured for access to this feature in LaunchDarkly."
            in html
        )
        assert res.status_code == 400
