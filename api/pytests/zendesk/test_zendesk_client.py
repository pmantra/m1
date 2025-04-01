from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from zenpy.lib.api_objects import Comment, Ticket
from zenpy.lib.exception import APIException, RecordNotFoundException

from messaging.services.zendesk_client import ZENDESK_VENDOR_NAME, ZendeskClient
from models.failed_external_api_call import Status
from utils.failed_external_api_call_recorder import FailedVendorAPICallRecorder
from utils.random_string import generate_random_string

USER_ID = generate_random_string(6)
REQUESTER_ID = generate_random_string(10)
SUBJECT = generate_random_string(40)
COMMENT = generate_random_string(20)


def test_failed_to_update_ticket():
    creds = {"token": "1234"}

    failed_vendor_api_call_recorder = FailedVendorAPICallRecorder()
    zendesk_client = ZendeskClient(creds, failed_vendor_api_call_recorder)

    user_id = generate_random_string(6)
    called_by = generate_random_string(6)
    message_id = generate_random_string(15)
    requester_id = generate_random_string(10)
    subject = generate_random_string(40)
    comment = generate_random_string(20)
    ticket_id = generate_random_string(10)

    updated_ticket = Ticket(
        id=ticket_id,
        requester_id=requester_id,
        status="open",
        subject=subject,
        comment=Comment(body=comment, author_id=requester_id, public=False),
        tags=[],
    )

    with patch(
        "zenpy.lib.api.TicketApi.update",
        side_effect=Exception("Error in update a ticket"),
    ):
        with pytest.raises(Exception) as excinfo:
            zendesk_client.update_ticket(updated_ticket, user_id, called_by, message_id)
        assert str(excinfo.value) == "Error in update a ticket"

        results = list(
            filter(
                lambda rec: rec.api_name == "zenpy.tickets.update",
                failed_vendor_api_call_recorder.get_record_by_status(
                    start_time=datetime.utcnow() - timedelta(seconds=5),
                    end_time=datetime.utcnow() + timedelta(seconds=5),
                    status=Status.pending,
                ),
            )
        )
        assert len(results) == 1

        result = results[0]
        assert result.status == Status.pending
        assert result.vendor_name == ZENDESK_VENDOR_NAME
        assert result.called_by == called_by

        assert result.payload.get("exception_type") == "Exception"
        assert result.payload.get("exception_message") == "Error in update a ticket"
        assert result.payload.get("user_id") == user_id
        assert result.payload.get("zendesk_ticket_id") == ticket_id
        assert result.payload.get("zendesk_user_id") == requester_id
        assert result.payload.get("message_id") == message_id
        assert len(result.external_id) > 0


def test_failed_to_create_ticket():
    creds = {"token": "1234"}

    failed_vendor_api_call_recorder = FailedVendorAPICallRecorder()
    zendesk_client = ZendeskClient(creds, failed_vendor_api_call_recorder)

    user_id = generate_random_string(6)
    called_by = generate_random_string(6)
    message_id = generate_random_string(15)
    requester_id = generate_random_string(10)
    subject = generate_random_string(40)
    comment = generate_random_string(20)

    new_ticket = Ticket(
        requester_id=requester_id,
        status="open",
        subject=subject,
        comment=Comment(body=comment, author_id=requester_id, public=False),
        tags=[],
    )

    with patch(
        "zenpy.lib.api.TicketApi.create",
        side_effect=Exception("Error in create a ticket"),
    ):
        with pytest.raises(Exception) as excinfo:
            zendesk_client.create_ticket(
                new_ticket, user_id, requester_id, called_by, message_id
            )
        assert str(excinfo.value) == "Error in create a ticket"

        results = list(
            filter(
                lambda rec: rec.api_name == "zenpy.tickets.create",
                failed_vendor_api_call_recorder.get_record_by_status(
                    start_time=datetime.utcnow() - timedelta(seconds=5),
                    end_time=datetime.utcnow() + timedelta(seconds=5),
                    status=Status.pending,
                ),
            )
        )
        assert len(results) == 1

        result = results[0]

        assert result.status == Status.pending
        assert result.vendor_name == ZENDESK_VENDOR_NAME
        assert result.called_by == called_by

        assert result.payload.get("exception_type") == "Exception"
        assert result.payload.get("exception_message") == "Error in create a ticket"
        assert result.payload.get("user_id") == user_id
        assert result.payload.get("zendesk_user_id") == requester_id
        assert result.payload.get("message_id") == message_id
        assert len(result.external_id) > 0


def test_failed_to_create_ticket_user_suspended():
    creds = {"token": "1234"}

    failed_vendor_api_call_recorder = FailedVendorAPICallRecorder()
    zendesk_client = ZendeskClient(creds, failed_vendor_api_call_recorder)

    user_id = generate_random_string(6)
    called_by = generate_random_string(6)
    message_id = generate_random_string(15)
    requester_id = generate_random_string(10)
    subject = generate_random_string(40)
    comment = generate_random_string(20)

    new_ticket = Ticket(
        requester_id=requester_id,
        status="open",
        subject=subject,
        comment=Comment(body=comment, author_id=requester_id, public=False),
        tags=[],
    )

    with patch(
        "zenpy.lib.api.TicketApi.create",
        side_effect=Exception(f"Error in create a ticket, user {user_id} is suspended"),
    ), patch("messaging.services.zendesk_client.log.error") as logger:
        with pytest.raises(Exception) as excinfo:
            zendesk_client.create_ticket(
                new_ticket, user_id, requester_id, called_by, message_id
            )
        assert (
            str(excinfo.value)
            == f"Error in create a ticket, user {user_id} is suspended"
        )

        results = list(
            filter(
                lambda rec: rec.api_name == "zenpy.tickets.create",
                failed_vendor_api_call_recorder.get_record_by_status(
                    start_time=datetime.utcnow() - timedelta(seconds=5),
                    end_time=datetime.utcnow() + timedelta(seconds=5),
                    status=Status.pending,
                ),
            )
        )
        assert len(results) == 1

        result = results[0]

        assert (
            logger.call_args[0][0] == "Failed to create new ticket, user is suspended"
        )
        assert result.status == Status.pending
        assert result.vendor_name == ZENDESK_VENDOR_NAME
        assert result.called_by == called_by
        assert result.payload.get("exception_type") == "Exception"
        assert (
            result.payload.get("exception_message")
            == f"Error in create a ticket, user {user_id} is suspended"
        )
        assert result.payload.get("user_id") == user_id
        assert result.payload.get("zendesk_user_id") == requester_id
        assert result.payload.get("message_id") == message_id
        assert len(result.external_id) > 0


def test_failed_to_create_ticket_blank_vlaue():
    creds = {"token": "1234"}

    failed_vendor_api_call_recorder = FailedVendorAPICallRecorder()
    zendesk_client = ZendeskClient(creds, failed_vendor_api_call_recorder)

    user_id = generate_random_string(6)
    called_by = generate_random_string(6)
    message_id = generate_random_string(15)
    requester_id = generate_random_string(10)
    subject = generate_random_string(40)
    comment = generate_random_string(20)

    new_ticket = Ticket(
        requester_id=requester_id,
        status="open",
        subject=subject,
        comment=Comment(body=comment, author_id=requester_id, public=False),
        tags=[],
    )

    with patch(
        "zenpy.lib.api.TicketApi.create",
        side_effect=Exception("Failed to create new ticket, cannot be blank"),
    ), patch("messaging.services.zendesk_client.log.error") as logger:
        with pytest.raises(Exception) as excinfo:
            zendesk_client.create_ticket(
                new_ticket, user_id, requester_id, called_by, message_id
            )
        assert str(excinfo.value) == "Failed to create new ticket, cannot be blank"

        results = list(
            filter(
                lambda rec: rec.api_name == "zenpy.tickets.create",
                failed_vendor_api_call_recorder.get_record_by_status(
                    start_time=datetime.utcnow() - timedelta(seconds=5),
                    end_time=datetime.utcnow() + timedelta(seconds=5),
                    status=Status.pending,
                ),
            )
        )
        assert len(results) == 1

        result = results[0]

        assert logger.call_args[0][0] == "Failed to create new ticket, blank value"
        assert result.status == Status.pending
        assert result.vendor_name == ZENDESK_VENDOR_NAME
        assert result.called_by == called_by
        assert result.payload.get("exception_type") == "Exception"
        assert (
            result.payload.get("exception_message")
            == "Failed to create new ticket, cannot be blank"
        )
        assert result.payload.get("user_id") == user_id
        assert result.payload.get("zendesk_user_id") == requester_id
        assert result.payload.get("message_id") == message_id
        assert len(result.external_id) > 0


def test_failed_to_get_ticket_record_not_found(zendesk_client):
    # Gven:
    user_id = generate_random_string(6)
    ticket_id = 123
    zendesk_client.failed_vendor_api_call_recorder = FailedVendorAPICallRecorder()
    # we expect to get a RecordNotFoundException from zendesk
    zendesk_client.zenpy.tickets.side_effect = RecordNotFoundException("RecordNotFound")

    # When: we try to get a ticket from Zendesk we should hit the RecordNotFound handling
    # and swallow the error, not log an error, and return None for the ticket
    with patch("messaging.services.zendesk_client.log.error") as logger:
        ticket = zendesk_client.get_ticket(ticket_id, user_id)
    assert ticket is None
    logger.assert_not_called()


def test_failed_to_get_ticket_record_other_exception(zendesk_client):
    # Given:
    user_id = generate_random_string(6)
    ticket_id = 123
    zendesk_client.failed_vendor_api_call_recorder = FailedVendorAPICallRecorder()
    # we expect to get a misc exception from zendesk
    zendesk_client.zenpy.tickets.side_effect = APIException("Connection Error")

    # When: we try to get a ticket from Zendesk we will see the raised error
    with patch("messaging.services.zendesk_client.log.error") as logger:
        with pytest.raises(APIException) as excinfo:
            zendesk_client.get_ticket(ticket_id, user_id)
        # Then: since this isn't a record not found error we expect the error to be raised and logged
        assert "Connection Error" in str(excinfo.value)
        assert logger.call_args[0][0] == "Error in looking up zendesk ticket"


def test_get_ticket(zendesk_client):
    # Given: new ticket
    new_ticket = Ticket(
        requester_id=REQUESTER_ID,
        status="open",
        subject=SUBJECT,
        comment=Comment(body=COMMENT, author_id=REQUESTER_ID, public=False),
        tags=[],
    )

    # When: we try to get existing ticket created above
    ticket = zendesk_client.get_ticket(new_ticket.id, USER_ID)

    # Then: we should get a ticket back
    assert ticket is not None
