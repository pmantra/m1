from unittest.mock import patch

from zenpy.lib.api import BaseApi
from zenpy.lib.api_objects import Audit, Ticket, TicketAudit
from zenpy.lib.api_objects import User as ZDUser
from zenpy.lib.exception import APIException

from messaging.services.zendesk import zenpy_client
from utils.log import logger

log = logger(__name__)


class MockZendesk:
    _zd_users = None
    _zd_tickets = None
    _zd_comments = None
    _zd_comment_tickets = None
    add_finalizer = None

    def add_user_tags_to_ticket(self, ticket_id, tags):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        t = self._zd_tickets[ticket_id]  # type: ignore[index] # Value of type "None" is not indexable
        if t.tags is None:
            t.tags = []
        t.tags += tags
        return t

    def mock_zendesk(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Reset simulated Zendesk state.
        self._zd_users = []
        self._zd_tickets = []
        self._zd_comments = {}
        self._zd_comment_tickets = {}

        # Patch the zenpy api client to interact with the simulation.
        p = patch.object(BaseApi, "_call_api", _block_request)
        p.start()
        self.add_finalizer(p.stop)

        p = patch.object(zenpy_client, "search", self._search_user)  # type: ignore[arg-type] # Argument 3 to "object" of "_patcher" has incompatible type "Callable[[Any, Any, Any, Any], Any]"; expected "Callable[[Any, Any, Any, KwArg(Any)], Any]"
        p.start()
        self.add_finalizer(p.stop)

        p = patch.object(
            zenpy_client,
            "create_or_update_user",
            self._create_or_return_user_for_wrapper,  # type: ignore[arg-type] # Argument 3 to "object" of "_patcher" has incompatible type "Callable[[Any, Any, Any, Any], Any]"; expected "Callable[[Any, Any, Any, KwArg(Any)], Any]"
        )
        p.start()
        self.add_finalizer(p.stop)

        p = patch.object(zenpy_client, "create_ticket", self._create_ticket)  # type: ignore[arg-type] # Argument 3 to "object" of "_patcher" has incompatible type "Callable[[Any, Any, Any, Any, Any], Any]"; expected "Callable[[Any, Any, Any, KwArg(Any)], Any]"
        p.start()
        self.add_finalizer(p.stop)

        p = patch.object(zenpy_client, "update_ticket", self._update_ticket)  # type: ignore[arg-type] # Argument 3 to "object" of "_patcher" has incompatible type "Callable[[Any, Any, Any, Any], Any]"; expected "Callable[[Any, Any, Any, KwArg(Any)], Any]"
        p.start()
        self.add_finalizer(p.stop)

        p = patch.object(zenpy_client, "get_ticket", self._show_ticket)  # type: ignore[arg-type] # Argument 3 to "object" of "_patcher" has incompatible type "Callable[[Any, Any, Any, Any], Any]"; expected "Callable[[Any, Any, Any, KwArg(Any)], Any]"
        p.start()
        self.add_finalizer(p.stop)

    def _search_user(self, type, email, user_id="", called_by=""):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        assert type == "user"
        return [u for u in self._zd_users if u.email == email]

    def _create_or_return_user_for_wrapper(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        user,
        called_by="",
        phone_number=None,
    ):
        u = ZDUser(email=user.email, name=user.full_name)

        if u.email in (zd_user.email for zd_user in self._zd_users):
            found_user = next(
                zd_user for zd_user in self._zd_users if zd_user.email == u.email
            )
            return found_user
        u.id = len(self._zd_users)
        self._zd_users.append(u)
        return u

    def _create_or_return_user(self, users, called_by=""):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        u = users
        if u.email in (zd_user.email for zd_user in self._zd_users):
            found_user = next(
                zd_user for zd_user in self._zd_users if zd_user.email == u.email
            )
            return found_user
        u.id = len(self._zd_users)
        self._zd_users.append(u)
        return u

    def _show_ticket(self, id, user_id="", called_by="", message_id=""):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            t = self._zd_tickets[id]
        except IndexError:
            raise APIException("Mock ticket not found.")
        return _copy_ticket(t)

    def _update_ticket(self, t, user_id="", called_by="", message_id=""):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            existing = self._zd_tickets[t.id]
        except IndexError:
            raise APIException("Mock ticket not found.")

        events = []

        if existing.status != t.status:
            events.append(
                dict(
                    field_name="status",
                    previous_value=existing.status,
                    type="Change",
                    value=t.status,
                )
            )
            existing.status = t.status

        if t.comment:
            events.append(self._create_comment(t))

        return TicketAudit(ticket=_copy_ticket(existing), audit=Audit(events=events))

    def _create_ticket(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, t, user_id="", zd_requester_id="", called_by="", message_id=""
    ):
        new_ticket = _copy_ticket(t)
        new_ticket.id = len(self._zd_tickets)
        self._zd_tickets.append(new_ticket)

        events = [dict(field_name="status", type="Create", value=new_ticket.status)]

        if t.comment:
            events.append(self._create_comment(t))

        return TicketAudit(ticket=_copy_ticket(new_ticket), audit=Audit(events=events))

    def _create_comment(self, t):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        c = t.comment
        c.id = len(self._zd_comments) + 1
        self._zd_comments[c.id] = c
        self._zd_comment_tickets[c.id] = t.id
        event = dict(
            attachments=[],
            author_id=c.author_id,
            body=c.body,
            id=c.id,
            plain_body=c.body,
            public=True,
            type="Comment",
        )
        return event


class MockNotImplementedError(NotImplementedError):
    def __init__(self, http_method, url, kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        msg = "A mock is required to avoid a request to the Zendesk API ({}: {} - {})."
        super().__init__(msg.format(http_method.__name__.upper(), url, kwargs))


def _block_request(_self, http_method, url, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    raise MockNotImplementedError(http_method, url, kwargs)


def _copy_ticket(t):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    c = Ticket(
        id=t.id,
        requester_id=t.requester_id,
        status=t.status,
        subject=t.subject,
        tags=t.tags,
    )
    attr = "via_followup_source_id"
    followup = getattr(t, attr, None)
    if followup:
        setattr(c, attr, followup)
    return c
