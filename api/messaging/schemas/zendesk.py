from __future__ import annotations

import enum
from dataclasses import dataclass

from marshmallow.exceptions import ValidationError
from marshmallow_v1 import fields
from zenpy.lib.api_objects import Comment as ZDComment
from zenpy.lib.api_objects import Ticket as ZDTicket

from views.schemas.common import MavenSchema


def validate_platform(platform: str) -> bool:
    if platform not in ["ios", "android", "web"]:
        raise ValidationError(f"{platform} is not a valid platform.")
    return True


# ZendeskWebhookSchema defines the structure of the webhook payload received
# from Zendesk.
class ZendeskWebhookSchema(MavenSchema):
    token = fields.String(required=True)
    comment_id = fields.Integer(required=True)
    message_body = fields.String(required=True)
    maven_user_email = fields.String(required=True)
    comment_author_email = fields.String(required=True)
    tags = fields.String(required=True)
    zendesk_user_id = fields.String(required=True)


def get_zendesk_webhook(body: dict) -> dict:
    if not body:
        return {}
    return {
        "token": str(body["token"]),
        "comment_id": int(body["comment_id"]),
        "message_body": str(body["message_body"]),
        "maven_user_email": str(body["maven_user_email"]),
        "comment_author_email": str(body["comment_author_email"]),
        "tags": str(body["tags"]),
        "zendesk_user_id": str(body["zendesk_user_id"]),
    }


def webhook_to_zendesk_inbound_message_schema(
    loaded_schema: ZendeskWebhookSchema,
) -> ZendeskInboundMessageSchema:
    """
    Converts a webhook schema to a ZendeskInboundMessageSchema.
    """
    if loaded_schema is None:
        raise ValueError("schema cannot be None")
    # we accept the loaded schema and extract the validated data to avoid
    # accepting a generic dict. This forces the caller to load() the schema
    # triggering respective validation errors.
    data = loaded_schema.data

    # ensure comment_id is an int. it comes over webhook as str and as an
    # int from zenpy
    comment_id = int(data["comment_id"])
    # ensure zendesk_user_id is an int. it comes over webhook as str and as
    # an int from zenpy
    zendesk_user_id = int(data["zendesk_user_id"])
    # ensure tags is normalized to a list. it comes over webhook as str and
    # it comes from zenpy as an array of strings
    tags = data["tags"].split(" ")

    return ZendeskInboundMessageSchema(
        comment_id=comment_id,
        message_body=data["message_body"],
        maven_user_email=data["maven_user_email"],
        comment_author_email=data["comment_author_email"],
        zendesk_user_id=zendesk_user_id,
        tags=tags,
        source=ZendeskInboundMessageSource.WEBHOOK,
    )


def ticket_to_zendesk_inbound_message_schema(
    ticket: ZDTicket,
    comment: ZDComment,
) -> ZendeskInboundMessageSchema:
    """
    Creates a ZendeskInboundMessageSchema from a Zendesk ticket and comment.

    The following inbound_message value mapping was determined by
    reviewing the following webhook payload configuration from Zendesk
    and mapping the values.
    {
        "token": "...",
        "comment_id": "{{ticket.latest_public_comment.id}}",
        "message_body": "{{ticket.latest_public_comment.value}}",
        "maven_user_email": "{{ticket.requester.email}}",
        "comment_author_email": "{{current_user.email}}",
        "tags": "{{ticket.tags}}",
        "zendesk_user_id": "{{ticket.requester.id}}"
    }
    """
    if not ticket:
        raise ValueError("ticket cannot be None")
    if not comment:
        raise ValueError("comment cannot be None")

    return ZendeskInboundMessageSchema(
        comment_id=comment.id,
        message_body=comment.body,
        maven_user_email=ticket.requester.email,
        comment_author_email=comment.author.email,
        zendesk_user_id=ticket.requester.id,
        tags=ticket.tags,
        source=ZendeskInboundMessageSource.TICKET,
    )


class ZendeskInboundMessageSource(str, enum.Enum):
    WEBHOOK = "webhook"
    TICKET = "ticket"


# ZendeskInboundMessageSchema is the normalized representation of a message that
# was created in the Zendesk platform. All inbound data sources should marshall
# to this schema before moving forward with processing. This object is frozen to
# prevent accidental mutation during any hand off between async operators.
@dataclass(frozen=True)
class ZendeskInboundMessageSchema:
    """
    Defines the properties required to record a message that was sent from the
    Zendesk platform into Mavens database.
    """

    comment_id: int
    message_body: str
    maven_user_email: str
    comment_author_email: str
    zendesk_user_id: int
    tags: list[str]
    source: ZendeskInboundMessageSource
