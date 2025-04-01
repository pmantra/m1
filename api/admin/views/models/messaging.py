from __future__ import annotations

from typing import TYPE_CHECKING, Type

from flask_admin.actions import action
from flask_admin.contrib.sqla.filters import FilterEmpty
from jinja2 import (  # type: ignore[attr-defined] # Module "jinja2" has no attribute "pass_context"
    pass_context,
)

from admin.views.base import AdminCategory, AdminViewT, IsFilter, MavenAuditedView
from audit_log.utils import emit_audit_log_update
from authn.models.user import User
from messaging.models.messaging import (
    Channel,
    ChannelUsers,
    Message,
    MessageBilling,
    MessageCredit,
    MessageProduct,
)
from messaging.repository.message import (
    extend_query_filter_by_member_id,
    extend_query_filter_by_practitioner_id,
)
from models.profiles import PractitionerProfile
from storage.connection import RoutingSQLAlchemy, db

if TYPE_CHECKING:
    from sqlalchemy.orm.query import Query


class MessageViewPractitionerIdFilter(IsFilter):
    def apply(self, query: Query, value: int, alias=None) -> Query:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        query = extend_query_filter_by_practitioner_id(
            message_query=query,
            user_id=value,
        )
        return query


class MessageViewMemberIdFilter(IsFilter):
    def apply(self, query: Query, value: int, alias=None) -> Query:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        query = extend_query_filter_by_member_id(
            message_query=query,
            user_id=value,
        )
        return query


class MessageViewPractitionerEmailFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(Channel)
            .join(ChannelUsers, Channel.id == ChannelUsers.channel_id)
            .join(User, User.id == ChannelUsers.user_id)
            .join(
                PractitionerProfile, ChannelUsers.user_id == PractitionerProfile.user_id
            )
            .filter(User.email == value)
        )


class MessageViewMemberEmailFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(Channel)
            .join(ChannelUsers, Channel.id == ChannelUsers.channel_id)
            .join(User, User.id == ChannelUsers.user_id)
            .outerjoin(
                PractitionerProfile, ChannelUsers.user_id == PractitionerProfile.user_id
            )
            .filter(PractitionerProfile.user_id.is_(None), User.email == value)
        )


class MessageView(MavenAuditedView):
    read_permission = "read:message"

    can_view_details = True
    details_template = "message_details_template.html"

    column_list = (
        "id",
        "user.id",
        "user.full_name",
        "recipient",
        "created_at",
        "modified_at",
        "channel_id",
        "channel.internal",
        "zendesk_comment_id",
    )
    column_labels = {
        "user.id": "Sender ID",
        "user.full_name": "Sender Name",
        "recipient": "Recipient Name",
        "channel.internal": "CX Channel",
    }
    column_exclude_list = ("body", "status")  # list view
    column_details_list = (
        "id",
        "channel_id",
        "user.id",
        "user.full_name",
        "member",
        "practitioner",
        "is_first_message",
        "status",
        "created_at",
        "modified_at",
        "deadline",
        "replied_at",
        "refunded_at",
        "credit",
        "channel.internal",
        "zendesk_comment_id",
    )
    column_filters = (
        MessageViewPractitionerIdFilter(None, "Practitioner ID"),
        MessageViewMemberIdFilter(None, "Member ID"),
        MessageViewPractitionerEmailFilter(None, "Practitioner Email"),
        MessageViewMemberEmailFilter(None, "Member Email"),
        "channel_id",
        "channel.internal",
        FilterEmpty(
            Message.zendesk_comment_id,
            "Zendesk comment ID",
            options=((1, "None"), (0, "Not None")),
        ),
    )
    column_details_exclude_list = ("body",)  # detail view

    @pass_context
    def get_detail_value(self, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation

        if name == "practitioner":
            return model.channel.practitioner
        elif name == "member":
            return model.channel.member
        elif name == "is_first_message":
            return model.is_first_message_in_channel
        elif name == "replied_at":
            return (
                model.credit.responded_at if model.credit else "N/A (no credit found!)"
            )
        elif name == "refunded_at":
            return (
                model.credit.refunded_at if model.credit else "N/A (no credit found!)"
            )
        elif name == "deadline":
            return model.credit.respond_by if model.credit else "N/A (no credit found!)"
        elif name == "recipient":
            if model.user_id == model.channel.member.id:
                return model.channel.practitioner.full_name
            else:
                return model.channel.member.full_name
        else:
            return self._get_list_value(
                context,
                model,
                name,
                self.column_formatters,
                self.column_type_formatters,
            )

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[override,assignment] # Argument 1 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[RoutingSQLAlchemy]" #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[override,assignment] # Argument 2 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[AdminCategory]" #type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[override,assignment] # Argument 3 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[str]" #type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[override,assignment] # Argument 4 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[str]" #type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            Message,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class MessageProductView(MavenAuditedView):
    read_permission = "read:message-product"
    delete_permission = "delete:message-product"
    create_permission = "create:message-product"
    edit_permission = "edit:message-product"

    form_rules = ["number_of_messages", "price"]
    form_excluded_columns = ["modified_at", "created_at"]

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[override,assignment] # Argument 1 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[RoutingSQLAlchemy]" #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[override,assignment] # Argument 2 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[AdminCategory]" #type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[override,assignment] # Argument 3 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[str]" #type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[override,assignment] # Argument 4 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[str]" #type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            MessageProduct,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class MessageBillingView(MavenAuditedView):
    read_permission = "read:message-billing"
    delete_permission = "delete:message-billing"
    create_permission = "create:message-billing"
    edit_permission = "edit:message-billing"

    can_view_details = True
    column_exclude_list = ("json",)

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[override,assignment] # Argument 1 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[RoutingSQLAlchemy]" #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[override,assignment] # Argument 2 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[AdminCategory]" #type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[override,assignment] # Argument 3 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[str]" #type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[override,assignment] # Argument 4 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[str]" #type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            MessageBilling,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class MessageCreditView(MavenAuditedView):
    read_permission = "read:message-credit"
    delete_permission = "delete:message-credit"
    create_permission = "create:message-credit"

    can_view_details = True
    column_list = (
        "id",
        "message_id",
        "message_billing_id",
        "created_at",
        "respond_by",
        "responded_at",
        "refunded_at",
    )
    column_exclude_list = ("user", "response", "modified_at", "json")
    details_template = "message_credit_details_template.html"

    @action("refund_credit", "Refund Credit", "You Sure?")
    def refund_credit(self, credit_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        db.session.expunge_all()

        credits = (
            db.session.query(MessageCredit)
            .filter(MessageCredit.id.in_(credit_ids))
            .all()
        )

        for credit in credits:
            credit.refund()
            emit_audit_log_update(credit)

        db.session.commit()

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[override,assignment] # Argument 1 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[RoutingSQLAlchemy]" #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[override,assignment] # Argument 2 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[AdminCategory]" #type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[override,assignment] # Argument 3 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[str]" #type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[override,assignment] # Argument 4 of "factory" is incompatible with supertype "MavenAdminView"; supertype defines the argument type as "Optional[str]" #type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            MessageCredit,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
