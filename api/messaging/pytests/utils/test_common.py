import pytest
from zenpy.lib.api_objects import Audit, Ticket, TicketAudit

from messaging.utils.common import (
    parse_comment_id_from_ticket_audit,
    parse_ticket_comment_body_from_ticket_audit,
)


@pytest.fixture
def ticket_audit_event():
    ticket_event = [
        {
            "id": 32821737194259,
            "type": "Comment",
            "author_id": 32359327707283,
            "body": "test",
            "html_body": '<div class="zd-comment" dir="auto"><p dir="auto">test</p></div>',
            "plain_body": "test",
            "public": True,
            "attachments": [],
            "audit_id": 32821774934547,
        },
        {
            "id": 32821774936979,
            "type": "Notification",
            "via": {
                "channel": "rule",
                "source": {
                    "from": {
                        "deleted": False,
                        "title": "Notify requester of comment update",
                        "id": 360184345633,
                        "revision_id": 1,
                    },
                    "rel": "trigger",
                },
            },
            "subject": "[{{ticket.account}}] Re: {{ticket.title}}",
            "body": "Your request ({{ticket.id}}) has been updated. To add additional comments, reply to this email.\n{{ticket.comments_formatted}}",
            "recipients": [32359327707283],
        },
        {
            "id": 32821774940947,
            "type": "Notification",
            "via": {
                "channel": "rule",
                "source": {
                    "from": {
                        "deleted": False,
                        "title": "Notify assignee of comment update",
                        "id": 360184345653,
                        "revision_id": 1,
                    },
                    "rel": "trigger",
                },
            },
            "subject": "[{{ticket.account}}] Re: {{ticket.title}}",
            "body": "This ticket (#{{ticket.id}}) has been updated.\n\n{{ticket.comments_formatted}}",
            "recipients": [421968264953],
        },
    ]
    audit = Audit(events=ticket_event)
    ticket = Ticket(id=1)

    return TicketAudit(audit=audit, ticket=ticket)


def test_parse_comment_id_from_ticket_audit(ticket_audit_event):
    # Given

    events = ticket_audit_event

    # When

    # parse the json to extract the comment id
    comment_id = parse_comment_id_from_ticket_audit(ticket_audit=events, user_id=1)

    # Then

    assert comment_id == 32821737194259


def test_parse_ticket_comment_body_from_ticket_audit(ticket_audit_event):
    # Given

    events = ticket_audit_event

    # When

    # parse the json to extract the comment body
    comment_body = parse_ticket_comment_body_from_ticket_audit(
        ticket_audit=events, user_id=1
    )

    # Then

    assert comment_body == "test"
