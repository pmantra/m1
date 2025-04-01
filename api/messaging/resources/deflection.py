from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable

import ddtrace
import orjson
from flask import current_app, request
from flask.typing import ResponseReturnValue
from flask_restful import Resource, abort
from maven import feature_flags

import configuration
from appointments.models.needs_and_categories import (
    Need,
    NeedCategory,
    get_need_categories_for_track,
    need_need_category,
)
from appointments.schemas.provider import make_provider_search_result
from appointments.services.v2.cancel_appointment_service import CancelAppointmentService
from appointments.services.v2.member_appointment import MemberAppointmentService
from authn.models.user import User
from messaging.schemas.deflection import (
    DeflectionCancelAppointmentRequestSchema,
    DeflectionCategoryNeedsSchema,
    DeflectionMemberContextResponseSchema,
    DeflectionTrackCategoriesSchema,
    DeflectionUpcomingAppointmentsSchema,
)
from models.tracks.client_track import TrackModifiers
from providers.service.provider import ProviderService
from storage.connection import db
from tracks.utils.common import get_active_member_track_modifiers
from utils.launchdarkly import user_context
from utils.log import logger
from views.search import SearchResult, perform_search

log = logger(__name__)


HEADER_KEY_ZENDESKSC_API_KEY = "x-zendesksc-api-key"


@ddtrace.tracer.wrap()
def with_zendesksc_api_key(f: Callable[[Resource], ResponseReturnValue]) -> Callable:
    @wraps(f)
    def decorated_function(*args: list, **kwargs: dict) -> ResponseReturnValue:
        config = configuration.get_zendesksc_config()

        # get api key from request headers
        provided_api_key = request.headers.get(HEADER_KEY_ZENDESKSC_API_KEY)

        # return 401 if provided_api_key is missing
        if not provided_api_key:
            abort(401, message="missing api key")

        # return 403 if provided_api_key is invalid
        if provided_api_key not in [
            config.api_secret_key_primary,
            config.api_secret_key_secondary,
        ]:
            abort(403, message="invalid api key")

        return f(*args, **kwargs)

    return decorated_function


class DeflectionMemberContextResource(Resource):
    @db.from_app_replica
    @with_zendesksc_api_key
    def get(self) -> ResponseReturnValue:
        """
        Provides a general set of properties for the provided user_id.
        Used to provide personalized decision trees to a user.

        /api/v1/_/vendor/zendesksc/deflection/member_context?member_id=123
        """
        args: dict = request.args
        member_id = args.get("member_id")
        if not member_id:
            abort(400, message="member_id is required")

        # return 404 if user is not found
        user = User.query.get_or_404(member_id)

        if not user.member_profile:
            abort(400, message="user is not a member")

        # get member conext variables
        active_tracks = user.active_tracks
        active_track_ids = [track.id for track in active_tracks]
        active_track_names = [track.name for track in active_tracks]
        member_track_modifiers = get_active_member_track_modifiers(active_tracks)
        member_state = (
            user.member_profile.state.abbreviation
            if user.member_profile.state
            else None
        )

        # determine if user is doula_only
        is_doula_only_member = TrackModifiers.DOULA_ONLY in member_track_modifiers

        resp = DeflectionMemberContextResponseSchema(
            member_id=user.id,
            active_track_ids=active_track_ids,
            is_doula_only_member=is_doula_only_member,
            active_track_names=active_track_names,
            member_state=member_state,
        )

        return asdict(resp)


class DeflectionTrackCategoriesResource(Resource):
    @with_zendesksc_api_key
    def get(self) -> ResponseReturnValue:
        """
        Returns a list of need categories associated with a member's tracks

        /api/v1/_/vendor/zendesksc/deflection/track_categories?member_id=123
        :return: list of need category names
        """
        # get user_id from member_id in request
        args: dict = request.args
        member_id = args.get("member_id")
        if not member_id:
            abort(400, message="member_id is required")

        member = User.query.get(member_id)
        if not member:
            abort(404, message="user not found")

        need_categories: list[NeedCategory] = []
        for track in member.active_tracks:
            need_categories.extend(get_need_categories_for_track(track.name))

        response = DeflectionTrackCategoriesSchema(
            member_id=member.id,
            need_categories=[category.name for category in need_categories],
        )

        return asdict(response)


class DeflectionCategoryNeedsResource(Resource):
    @with_zendesksc_api_key
    def get(self) -> ResponseReturnValue:
        """
        Returns a list of needs associated with a category

        /api/v1/_/vendor/zendesksc/deflection/category_needs?category_name
        :return: list of needs
        """
        args: dict = request.args
        category_name = args.get("category_name")
        if not category_name:
            abort(400, message="category_name is required")

        category = NeedCategory.query.filter(
            NeedCategory.name == category_name
        ).one_or_none()
        if not category:
            abort(404, message="category not found")

        needs = (
            db.session.query(Need.name)
            .join(need_need_category, Need.id == need_need_category.c.need_id)
            .filter(need_need_category.c.category_id == category.id)
            .all()
        )
        response = DeflectionCategoryNeedsSchema(
            needs=[need.name for need in needs],
        )

        return asdict(response)


class DeflectionUpcomingAppointmentsResource(Resource):
    @db.from_app_replica
    @with_zendesksc_api_key
    def get(self) -> ResponseReturnValue:
        """
        Returns a list of upcoming appointments for the provided user_id.

        /api/v1/_/vendor/zendesksc/deflection/upcoming_appointments?member_id=123
        """
        # get user_id from request
        args: dict = request.args
        member_id = args.get("member_id")
        if not member_id:
            abort(400, message="member_id is required")

        limit = args.get("limit", 10)
        offset = args.get("offset", 0)

        # return 404 if user is not found
        member = User.query.get_or_404(member_id)

        # list_member_appointments requires a scheduled_end so some reasonable
        # endpoint is chosen.
        scheduled_start = datetime.utcnow()
        scheduled_end = datetime.utcnow() + timedelta(days=30)

        (
            upcoming_appointments,
            _,
        ) = MemberAppointmentService().list_member_appointments(
            user=member,
            member_id=member.id,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            limit=limit,
            offset=offset,
        )

        resp = DeflectionUpcomingAppointmentsSchema(appointments=upcoming_appointments)
        # silly hack to properly serialize complex types without marshmallow
        return orjson.loads(orjson.dumps(resp, option=orjson.OPT_NAIVE_UTC))


class DeflectionCancelAppointmentsResource(Resource):
    @db.from_app_replica
    @with_zendesksc_api_key
    def post(self) -> ResponseReturnValue:
        """
        Cancels an appointment identified by appointment_id and member_id.

        /api/v1/_/vendor/zendesksc/deflection/cancel_appointment
        """
        request_json = request.json if request.is_json else None
        if request_json is None:
            abort(400, message="empty request body")

        try:
            cancel_args = DeflectionCancelAppointmentRequestSchema(**request_json)
        except Exception as e:
            log.error("error parsing appointment cancel request", error=e)
            abort(400, message="invalid request")

        # return 404 if user is not found
        user = User.query.get_or_404(cancel_args.member_id)
        try:
            CancelAppointmentService().cancel_appointment(
                user=user,
                appointment_id=cancel_args.appointment_id,
            )
        except Exception as e:
            log.exception("failed cancelling appointment", exception=e)
            abort(500, message="failed cancelling appointment")

        return {}


class DeflectionResourcesSearch(Resource):
    @db.from_app_replica
    @with_zendesksc_api_key
    def get(self) -> ResponseReturnValue:
        """
        Searches the resource library against a given query.

        /api/v1/_/vendor/zendesksc/deflection/resource_search
        """
        args: dict = request.args
        member_id = args.get("member_id")
        if not member_id:
            abort(400, message="member_id is required")

        query: str = args.get("query", "")
        if not query:
            abort(400, message="query is required")

        # return 404 if user is not found
        member = User.query.get_or_404(member_id)

        track = member.current_member_track
        result: SearchResult = perform_search("resources", query, track)

        response = asdict(result)
        for resource in response["results"]:
            resource["data"][
                "content_url"
            ] = f"{current_app.config['BASE_URL']}/app/resources/content/article/{resource['data']['slug']}"

        return response


class DeflectionProviderSearchResource(Resource):
    def determine_desired_need_ids_from_categories(
        self,
        *,
        need_category_id: str | None,
        need_category_name: str | None,
    ) -> list[int]:
        """
        Determine all related need ids based on need category id or name
        """
        category_query_by_id = NeedCategory.query.filter(
            NeedCategory.id == need_category_id
        )
        category_query_by_name = NeedCategory.query.filter(
            NeedCategory.name == need_category_name
        )
        need_category_by_id_result = (
            category_query_by_id.one_or_none() if need_category_id else None
        )
        need_category_by_name_result = (
            category_query_by_name.one_or_none() if need_category_name else None
        )

        need_category_by_id_need_list = (
            need_category_by_id_result.needs if need_category_by_id_result else []
        )
        need_category_by_name_need_list = (
            need_category_by_name_result.needs if need_category_by_name_result else []
        )

        all_need_category_needs = (
            need_category_by_id_need_list + need_category_by_name_need_list
        )

        # creates a list of all need ids without None values
        return [need.id for need in all_need_category_needs]

    @with_zendesksc_api_key
    def get(self) -> ResponseReturnValue:
        """
        Returns a list of providers based on passed in parameters, requires member_id
        filter by vertical or category

        /api/v1/_/vendor/zendesksc/deflection/provider_search?member_id=123
        param: member_id, int
        param: vertical, optional string
        param: category, optional string
        :return: list of providers
        """
        args: dict = request.args
        limit = args.get("limit", 7)
        offset = args.get("offset", 0)
        member_id = args.get("member_id")
        if not member_id:
            abort(400, message="member_id is required")

        member = User.query.get(member_id)
        if not member:
            abort(
                404,
                message="user not found",
            )
        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            user_context(member),
            default=False,
        )

        # Provider vertical
        # If both provided, id takes presence
        vertical = args.get("vertical")
        vertical_id = args.get("vertical_id")

        # Need maps to vertical
        need_id = args.get("need_id")
        need_name = args.get("need")

        # Need category maps to a list of needs
        # each need maps to a vertical
        need_category_id = args.get("need_category_id")
        need_category_name = args.get("need_category")

        # Omit provider id from search results
        omit_provider_id = args.get("omit_provider_id")

        # Determine need ids from the category information
        need_ids_from_categories = self.determine_desired_need_ids_from_categories(
            need_category_id=need_category_id,
            need_category_name=need_category_name,
        )

        # creates a list of all need ids without None values
        all_need_ids = need_ids_from_categories + ([need_id] if need_id else [])

        if all([not vertical, not vertical_id, not need_name, not all_need_ids]):
            # no providers to return if there is no search criteria
            return {"providers": []}

        providers, _ = ProviderService().search(
            current_user=member,
            verticals=[vertical] if vertical else None,
            vertical_ids=[vertical_id] if vertical_id else None,
            needs=[need_name] if need_name else None,
            need_ids=all_need_ids if all_need_ids else None,
            limit=limit,
            offset=offset,
        )

        # filter out omitted provider if if given
        providers = [
            p
            for p in providers
            if (not omit_provider_id or str(p.id) != str(omit_provider_id))
        ]

        all_provider_ids = [p.id for p in providers]
        latest_appointment_date_by_provider_id = (
            ProviderService().get_latest_appointments_by_provider_id(
                member.id,
                all_provider_ids,
            )
        )

        result = {
            "providers": [
                {
                    **make_provider_search_result(
                        p,
                        member,
                        latest_appointment_date_by_provider_id,
                        l10n_flag=l10n_flag,
                    ),
                    "booking_url": f"{current_app.config['BASE_URL']}/app/book-practitioner/{p.id}",
                }
                for p in providers
            ]
        }
        return result
