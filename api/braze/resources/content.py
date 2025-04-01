from flask import request
from flask_restful import abort

from authn.models.user import User
from braze.schemas.content import _validate_token
from common.services import ratelimiting
from common.services.api import UnauthenticatedResource
from models.marketing import Resource, ResourceConnectedContentTrackPhase
from models.tracks import MemberTrackPhase
from storage.connection import db

# TODO move utils.braze to Braze folder?
from utils.braze import is_whitelisted_braze_ip
from utils.log import logger

log = logger(__name__)


class BrazeContentMixin:
    def check_user(self, user_esp_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = db.session.query(User).filter(User.esp_id == user_esp_id).one_or_none()
        if not user:
            log.warning(f"User with esp_id: {user_esp_id} not found")
            abort(404, message="user not found!")
        return user

    def check_current_phase(self, user) -> MemberTrackPhase:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        member_track = user.current_member_track

        if not member_track:
            abort(400, message="user not in any track")

        current_phase = member_track.current_phase
        if not current_phase:
            abort(400, message="user not in any phase")
        return current_phase

    def get_base_braze_content_query(self, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self.check_user(user_esp_id=data["esp_id"])
        current_phase = self.check_current_phase(user=user)
        track_name = user.current_member_track.name
        query = (
            db.session.query(Resource)
            .join(ResourceConnectedContentTrackPhase)
            .filter(
                ResourceConnectedContentTrackPhase.track_name == track_name,
                ResourceConnectedContentTrackPhase.phase_name == current_phase.name,
            )
        )
        log.info(
            "Looking up resource with connected content track phase.",
            track_name=track_name,
            phase_name=current_phase.name,
        )
        if data.get("type"):
            query = query.filter(Resource.connected_content_type == data["type"])
        elif data.get("types"):
            query = query.filter(Resource.connected_content_type.in_(data["types"]))
        return query


def _get_braze_ip():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    real_ip = request.headers.get("X-Real-IP")
    if not is_whitelisted_braze_ip(real_ip):  # type: ignore[arg-type] # Argument 1 to "is_whitelisted_braze_ip" has incompatible type "Optional[str]"; expected "str"
        log.warning("IP not whitelisted for braze")
        # TODO: After verifying in prod, uncomment the next line to raise exceptions and fail the request.
        # raise RateLimitingException("IP not whitelisted for braze")
    return "BRAZE_REQUEST"


class BrazeConnectedContentResource(UnauthenticatedResource, BrazeContentMixin):
    @ratelimiting.ratelimited(attempts=300, cooldown=2, scope=_get_braze_ip)
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_args = request.args.to_dict()
        request_args["types"] = request.args.getlist("types")
        data = get_braze_connected_content_request(request_args)
        _validate_token(data["token"])
        query = self.get_base_braze_content_query(data=data)
        resources: list[Resource] = query.all()
        if not resources:
            log.warning(
                f'Connected content resource for user with esp_id {data["esp_id"]} not found'
            )
            abort(404, message="connected content resource not found")
        log.info(f"Found {len(resources)} Resources: {resources}")

        if data.get("type"):
            response = self._format_connected_content_resource_response(resources[0])
        else:
            response = {
                resource.connected_content_type: self._format_connected_content_resource_response(
                    resource
                )
                for resource in resources
            }

        return (response, 200)

    @staticmethod
    def _format_connected_content_resource_response(resource):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return {
            "image": resource.image.asset_url() if resource.image else "",
            "copy": resource.body,
            "title": resource.title,
            "slug": resource.slug,
            **{f.field.name: f.value for f in resource.connected_content_fields},
        }


def get_braze_connected_content_request(request_args: dict) -> dict:
    if not request_args:
        return {}
    result = {
        "token": str(request_args["token"]),
        "esp_id": str(request_args["esp_id"]),
    }
    if request_args.get("type"):
        result["type"] = str(request_args["type"])
    if "types" in request_args:
        result["types"] = [str(thing) for thing in (request_args["types"] or [])]  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[str]", target has type "str")
    return result
