import re

import flask
import httpproblem
import marshmallow

from authn.models import user
from common.services import api
from models import virtual_events
from storage.connection import db
from utils import zoom
from utils.log import logger
from views import library, tracks

log = logger(__name__)


class VirtualEventSchema(library.LibraryVirtualEventSchema):
    description = marshmallow.fields.String()
    cadence = marshmallow.fields.Function(
        lambda obj: obj.cadence.value if obj.cadence else None
    )
    event_image_url = marshmallow.fields.String()
    provider_profile_url = marshmallow.fields.String()
    description_body = marshmallow.fields.String()
    what_youll_learn_body = marshmallow.fields.Method("get_what_youll_learn")
    what_to_expect_body = marshmallow.fields.String()
    is_user_registered = marshmallow.fields.Method("get_is_user_registered")

    def get_what_youll_learn(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        lines = obj.what_youll_learn_body.splitlines()
        stripped_lines = [l.strip() for l in lines]
        bulletless_lines = [re.sub(r"^- ", "", l) for l in stripped_lines]
        # Remove any empty strings just in case
        return [s for s in bulletless_lines if s]

    def get_is_user_registered(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.context.get("user_id"):
            if next(
                (
                    r
                    for r in obj.user_registrations
                    if r.user_id == self.context["user_id"]
                ),
                None,
            ):
                return True
            return False


class VirtualEventsSchema(marshmallow.Schema):
    virtual_events = marshmallow.fields.List(
        marshmallow.fields.Nested(VirtualEventSchema)
    )


class VirtualEventsResource(api.AuthenticatedResource):
    def get(self, track_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        track = tracks.get_user_active_track(self.user, track_id)
        limit = flask.request.args.get("limit")
        schema = VirtualEventsSchema()
        schema.context["user_id"] = self.user.id
        events = virtual_events.get_valid_virtual_events_for_track(
            track=track, user_id=self.user.id, results_limit=limit
        )
        json = schema.dump({"virtual_events": events})
        return flask.make_response(json, 200)


class VirtualEventResource(api.AuthenticatedResource):
    def get(self, event_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not (self.user.is_enterprise or self.user.is_practitioner):
            raise httpproblem.Problem(403, detail="Not authorized")

        event = virtual_events.get_virtual_event_with_registration_for_one_user(
            virtual_event_id=event_id, user_id=self.user.id
        )

        schema = VirtualEventSchema()
        schema.context["user_id"] = self.user.id

        if event:
            return flask.make_response(schema.dump(event), 200)
        else:
            raise httpproblem.Problem(
                404, detail=f"Virtual event with ID {event_id} not found"
            )


def register_user_for_webinar(user: user.User, webinar_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Register a user for a webinar.
    """
    endpoint = f"webinars/{webinar_id}/registrants"
    data = {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }
    response = zoom.make_zoom_request(endpoint, data=data, method="POST")
    return response


class VirtualEventUserRegistrationResource(api.AuthenticatedResource):
    def post(self, virtual_event_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Check that the virtual event exists
        virtual_event = (
            db.session.query(virtual_events.VirtualEvent)
            .filter(virtual_events.VirtualEvent.id == virtual_event_id)
            .first()
        )
        if virtual_event is None:
            return {"error": "Virtual event not found"}, 404

        # Check that the user isn't already registered for the event
        if virtual_events.user_is_registered_for_event(self.user.id, virtual_event_id):
            return {"error": "User has already registered for event"}, 409

        # Check that the virtual event has a webinar id
        webinar_id = virtual_event.webinar_id
        if not webinar_id:
            return {"error": "Virtual event has no webinar_id"}, 400

        try:
            response = register_user_for_webinar(self.user, webinar_id)
            res_json = response.json()
            join_url = res_json.get("join_url")
            if response.status_code == 201:
                virtual_event_user_registration = (
                    virtual_events.VirtualEventUserRegistration(
                        user_id=self.user.id,
                        virtual_event_id=virtual_event_id,
                    )
                )
                db.session.add(virtual_event_user_registration)
                db.session.commit()
            return {"join_url": join_url}, response.status_code
        except Exception:
            log.error("Zoom API request failed.")
            return {"error": "Zoom API request failed."}, 403
