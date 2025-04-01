from unittest import mock

from zenpy.lib.api_objects import Comment as ZDComment
from zenpy.lib.api_objects import Ticket as ZDTicket
from zenpy.lib.api_objects import User as ZDUser

from messaging.schemas.zendesk import (
    ZendeskWebhookSchema,
    ticket_to_zendesk_inbound_message_schema,
    webhook_to_zendesk_inbound_message_schema,
)


def test_webhook_to_zendesk_inbound_message_schema(factories):
    data = {
        "token": "12345",
        "comment_id": "7346354",
        "message_body": "This is a message",
        "maven_user_email": "cool.user.email@mavenclinic.com",
        "comment_author_email": "author@mavenclinic.com",
        "tags": "tag1 tag2",
        "zendesk_user_id": "123456",
    }
    loaded_schema = ZendeskWebhookSchema().load(data)
    zd_schema = webhook_to_zendesk_inbound_message_schema(loaded_schema)

    assert zd_schema.comment_id == 7346354
    assert zd_schema.message_body == data["message_body"]
    assert zd_schema.maven_user_email == data["maven_user_email"]
    assert zd_schema.comment_author_email == data["comment_author_email"]
    assert zd_schema.zendesk_user_id == 123456
    assert zd_schema.tags == ["tag1", "tag2"]


@mock.patch.object(
    ZDTicket,
    "requester",
    new=ZDUser(
        id=999,
        email="requestor@test.com",
    ),
)
@mock.patch.object(
    ZDComment,
    "author",
    new=ZDUser(email="author@test.com"),
)
def test_ticket_to_zendesk_inbound_message_schema():
    tags = ["tag1", "tag2"]
    ticket = ZDTicket(
        id=123,
        tags=tags,
    )
    comment = ZDComment(
        id=123,
        body="body of comment",
    )

    zd_schema = ticket_to_zendesk_inbound_message_schema(ticket, comment)
    assert zd_schema.comment_id == 123
    assert zd_schema.message_body == "body of comment"
    assert zd_schema.maven_user_email == "requestor@test.com"
    assert zd_schema.comment_author_email == "author@test.com"
    assert zd_schema.zendesk_user_id == 999
    assert zd_schema.tags == ["tag1", "tag2"]
