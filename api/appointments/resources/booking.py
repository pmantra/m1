from __future__ import annotations

from typing import Any, Collection, List, Optional, Tuple

from ddtrace import tracer
from flask import request
from maven import feature_flags
from sqlalchemy import not_, or_
from sqlalchemy.orm import Query, joinedload

from appointments.models.needs_and_categories import (
    Need,
    NeedCategory,
    NeedCategoryTrack,
    NeedTrack,
    need_need_category,
)
from appointments.schemas.booking import (
    BookingFlowCategoriesGetSchema,
    BookingFlowSearchGetSchema,
    BookingFlowSearchSchema,
)
from appointments.schemas.booking_v3 import (
    BookingFlowSearchGetSchemaV3,
    BookingFlowSearchSchemaV3,
)
from appointments.services.common import get_platform
from appointments.utils.booking_flow_search import search_api_booking_flow
from appointments.utils.errors import SearchApiError
from authn.models.user import User
from common import stats
from common.services.api import AuthenticatedResource
from l10n.db_strings.translate import TranslateDBFields
from models.profiles import practitioner_specialties
from models.tracks import TrackName
from models.verticals_and_specialties import (
    Specialty,
    SpecialtyKeyword,
    Vertical,
    VerticalGroup,
    is_cx_coaching_speciality_slug,
    is_cx_vertical_name,
    vertical_group_specialties,
)
from providers.service.provider import ProviderService
from storage.connection import db
from utils import launchdarkly
from utils.log import logger
from views.internal import vertical_groups_by_track

log = logger(__name__)


TIME_OF_DAY_FILTERS = [
    {"name": "Overnight", "start_time": 0.0, "end_time": 5.0},
    {"name": "Morning", "start_time": 5.0, "end_time": 12.0},
    {"name": "Afternoon", "start_time": 12.0, "end_time": 17.0},
    {"name": "Evening", "start_time": 17.0, "end_time": 24.0},
]


PARENTING_CATEGORY_NAME = "Parenting"
PEDIATRICS_CATEGORY_NAME = "Pediatrics"


def _get_specialties_lite(
    user: User,
    is_common: bool,
    query: Optional[str],
    offset: int,
    limit: int,
    order_direction: str,
) -> Tuple[List[Specialty], int]:
    """A lightweight version of _get_specialties used for booking_flow search."""
    specialties_query = Specialty.query.options(
        joinedload(Specialty.specialty_keywords)
    ).filter(
        Specialty.id.in_(
            db.session.query(practitioner_specialties.c.specialty_id).distinct()
        )
    )

    if is_common:
        vertical_groups = _get_vertical_groups_query_lite(user).subquery()
        specialties_query = (
            specialties_query.join(
                vertical_group_specialties,
                Specialty.id == vertical_group_specialties.c.specialty_id,
            )
            .join(
                vertical_groups,
                vertical_groups.c.id == vertical_group_specialties.c.vertical_group_id,
            )
            .distinct()
        )

    if query:
        specialties_query = specialties_query.filter(
            Specialty.name.like("%" + query + "%")
        )

    count = specialties_query.count()

    specialties_query = (
        specialties_query.order_by(
            getattr(Specialty.ordering_weight, order_direction)(),
        )
        .offset(offset)
        .limit(limit)
    )

    specialties = specialties_query.all()

    return specialties, count


def _get_verticals_lite(
    query: Optional[str],
    offset: int,
    limit: int,
    order_direction: str,
) -> Tuple[List[Vertical], int]:
    """A lightweight version of _get_verticals used for booking_flow search.

    This function gets all verticals that match the query string and, unlike
    _get_verticals, does not filter based on vertical groups.

    This function will not return the Care Advocate/Care Coordinator vertical.
    """
    vertical_query = db.session.query(Vertical)

    if query:
        query_string = "%" + query + "%"
        vertical_query = vertical_query.filter(Vertical.name.like(query_string))

    # filter out care advocate/care coordinator vertical
    vertical_query = vertical_query.filter(
        Vertical.deleted_at == None,
        not_(is_cx_vertical_name(Vertical.name)),
    )

    v_count = vertical_query.count()
    vertical_query = (
        vertical_query.order_by(
            getattr(Vertical.name, order_direction)(),
        )
        .offset(offset)
        .limit(limit)
    )
    return vertical_query.all(), v_count


def _get_vertical_groups_query_lite(user: User) -> Query[VerticalGroup]:
    """A lightweight function to get the vertical groups of a user for
    booking_flow search.
    """
    member_track = user.current_member_track
    vertical_groups = vertical_groups_by_track(
        member_track and member_track.name, eager_load_data=False
    )

    return vertical_groups


def _get_keywords(
    query: Optional[str],
    offset: int,
    limit: int,
    order_direction: str,
) -> Tuple[List[SpecialtyKeyword], int]:
    """Returns a list of specialty keywords that match the query, paired by
    the offset, limit, and order direction given, along with the total number
    if not limited.
    """
    keyword_query = db.session.query(SpecialtyKeyword)

    if query:
        query_string = "%" + query + "%"
        keyword_query = keyword_query.filter(SpecialtyKeyword.name.like(query_string))

    k_count = keyword_query.count()
    keyword_query = (
        keyword_query.order_by(
            getattr(SpecialtyKeyword.name, order_direction)(),
        )
        .offset(offset)
        .limit(limit)
    )
    return keyword_query.all(), k_count


def _get_needs(
    query: Optional[str],
    category_ids: List[int],
    tracks: Collection[str],
    offset: int,
    limit: int,
) -> Tuple[List[Need], int]:
    """Returns a list of needs that match the query, or linked to category paired by
    the offset, limit, and order direction given, along with the total number
    if not limited.
    """
    need_query = (
        db.session.query(Need).join(NeedTrack).filter(NeedTrack.track_name.in_(tracks))
    )

    or_stmts = []
    if query:
        query_string = "%" + query + "%"
        or_stmts.append(Need.name.like(query_string))

    if category_ids:
        need_query = need_query.outerjoin(need_need_category).outerjoin(NeedCategory)
        or_stmts.append(NeedCategory.id.in_(category_ids))

    if or_stmts:
        need_query = need_query.filter(or_(*or_stmts))

    if len(tracks) > 1:
        need_query = need_query.filter(Need.hide_from_multitrack == False)

    n_count = need_query.count()
    need_query = (
        need_query.order_by(
            Need.display_order.is_(None).asc(), Need.display_order.asc()
        )
        .offset(offset)
        .limit(limit)
    )
    return need_query.all(), n_count


def _get_need_categories(
    query: Optional[str],
    tracks: Collection[str],
    offset: int,
    limit: int,
) -> Tuple[List[NeedCategory], int]:
    """Returns a list of need categories that match the query, paired by
    the offset, limit, and order direction given, along with the total number
    if not limited.
    """
    need_category_query = (
        db.session.query(NeedCategory)
        .join(NeedCategoryTrack)
        .filter(NeedCategoryTrack.track_name.in_(tracks))
    )
    if len(tracks) > 1:
        need_category_query = need_category_query.filter(
            NeedCategory.hide_from_multitrack == False
        )

    if query:
        query_string = "%" + query + "%"
        need_category_query = need_category_query.filter(
            NeedCategory.name.like(query_string)
        )

    # TODO: we should not be computing count() as a separate query, that is unnecessarily expensive.
    nc_count = need_category_query.count()
    need_category_query = (
        need_category_query.order_by(
            NeedCategory.display_order.is_(None).asc(), NeedCategory.display_order.asc()
        )
        .offset(offset)
        .limit(limit)
    )
    return need_category_query.all(), nc_count


class BookingFlowSearchResource(AuthenticatedResource):
    @property
    def launchdarkly_context(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return launchdarkly.marshmallow_context(self.user.esp_id, self.user.email)

    def _get_feature_flags(self) -> Tuple[bool, bool, bool, bool]:
        # Feature flags
        experiment_enabled: bool = feature_flags.bool_variation(
            "experiment-marshmallow-bookflow-search-upgrade",
            self.launchdarkly_context,
            default=False,
        )
        search_api_enabled: bool = feature_flags.bool_variation(
            "enable-booking-flow-with-search-api",
            launchdarkly.user_context(self.user),
            default=False,
        )
        enable_semantic_search: bool = feature_flags.bool_variation(
            "enable-booking-flow-search-semantic-search",
            launchdarkly.user_context(self.user),
            default=False,
        )
        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            launchdarkly.user_context(self.user),
            default=False,
        )

        return experiment_enabled, search_api_enabled, enable_semantic_search, l10n_flag

    @tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Get information for booking flow based on search criteria provided
        by the query.
        """
        (
            experiment_enabled,
            search_api_enabled,
            enable_semantic_search,
            l10n_flag,
        ) = self._get_feature_flags()
        args_schema = (
            BookingFlowSearchGetSchema()
            if not experiment_enabled
            else BookingFlowSearchGetSchemaV3()
        )
        args = (
            args_schema.load(request.args).data  # type: ignore[attr-defined] # "object" has no attribute "load"
            if not experiment_enabled
            else args_schema.load(request.args)  # type: ignore[attr-defined] # "object" has no attribute "load"
        )

        query = args["query"]
        is_common = args["is_common"]
        if query and is_common:
            # Using query and is_common together is not supported and should
            # return a 400 HTTP error
            return "Cannot use query and is_common together", 400

        offset = args["offset"]
        limit = args["limit"]
        order_direction = args["order_direction"]

        query = query.strip()

        s_count = 0
        specialties: list[Specialty] | list[dict[str, Any]] = []
        v_count = 0
        verticals: list[Vertical] | list[dict[str, Any]] = []
        k_count = 0
        keywords: list[SpecialtyKeyword] | list[dict[str, Any]] = []
        p_count = 0
        practitioners: list[User] = []
        n_count = 0
        needs: list[Need] | list[dict[str, Any]] = []
        nc_count = 0
        need_categories: list[NeedCategory] | list[dict[str, Any]] = []

        if is_common:
            # Get matching specialties
            specialties, s_count = _get_specialties_lite(
                self.user,
                is_common,
                query,
                offset,
                limit,
                order_direction,
            )

            # Get matching verticals
            # TODO: Should refactor query methods to make limit and offset param optional
            verticals, v_count = _get_verticals_lite(
                query=None,
                offset=offset,
                limit=1000,
                order_direction="asc",
            )

        elif search_api_enabled:
            # Search using search-api
            try:
                (
                    specialties,
                    keywords,
                    verticals,
                    practitioners,
                    need_categories,
                    needs,
                ) = search_api_booking_flow(
                    query,
                    limit,
                    self.user,
                    enable_semantic_search,
                    l10n_flag,
                )
            except SearchApiError as e:
                # Disable search api to continue onto the older code as a fallback
                search_api_enabled = False
                log.error(
                    "An error occured hitting the search api, falling back to DB search",
                    error=e,
                )
            else:
                s_count = len(specialties)
                k_count = len(keywords)
                v_count = len(verticals)
                p_count = len(practitioners)
                nc_count = len(need_categories)
                n_count = len(needs)
                log.info(
                    "Search api response lengths",
                    s_count=s_count,
                    k_count=k_count,
                    v_count=v_count,
                    p_count=p_count,
                    nc_count=nc_count,
                    n_count=n_count,
                )

        if not is_common and not search_api_enabled:
            # Get matching specialties
            specialties, s_count = _get_specialties_lite(
                self.user,
                is_common,
                query,
                offset,
                limit,
                order_direction,
            )

            # Get matching verticals
            verticals, v_count = _get_verticals_lite(
                query,
                offset,
                limit,
                order_direction,
            )

            # Get matching keywords
            keywords, k_count = _get_keywords(
                query,
                offset,
                limit,
                order_direction,
            )

            practitioners, p_count = ProviderService().search(
                current_user=self.user,
                name_query=query,
                exclude_CA_names=True,
                offset=offset,
                limit=limit,
                order_direction=order_direction,
                order_by="first_name",
            )

            active_track_names = {at.name for at in self.user.active_tracks}
            if not self.user.is_enterprise:
                # Marketplace users do not have a track, but we will treat them as though they were on the
                # General Wellness track for booking only.
                # https://mavenclinic.atlassian.net/jira/software/c/projects/DISCO/boards/216?assignee=712020%3A49deb732-f61f-4665-9284-92e5dd333f2c&selectedIssue=DISCO-3202
                active_track_names.add(TrackName.GENERAL_WELLNESS)

            # Get matching need categories
            need_categories, nc_count = _get_need_categories(
                query,
                active_track_names,
                offset,
                limit,
            )

            need_category_ids = [need_category.id for need_category in need_categories]
            # Get matching needs
            needs, n_count = _get_needs(
                query,
                need_category_ids,
                active_track_names,
                offset,
                limit,
            )

        pagination = {
            "total": max(v_count, s_count, k_count, p_count, n_count, nc_count),
            "offset": offset,
            "limit": limit,
            "order_direction": order_direction,
        }

        del args["limit"]
        del args["offset"]
        del args["order_direction"]

        if l10n_flag:
            translated_specialties = []
            translated_verticals = []
            translated_needs = []

            for s in specialties:
                if isinstance(s, Specialty):
                    # In the line below and similiar code, we didn't want to mutate
                    # the model without intending on commit these changes. s.__dict__.copy()
                    # was chosen to expedite this code, but isn't ideal
                    s = s.__dict__.copy()  # safely detach from sqla
                if is_cx_coaching_speciality_slug(s["slug"]):
                    # We want to exclude care advocate coaching specialties from showing up as search
                    # suggestions, since we don't let members search for CAs
                    continue
                s["name"] = TranslateDBFields().get_translated_specialty(
                    s["slug"], "name", s["name"]
                )
                translated_specialties.append(s)

            for v in verticals:
                if isinstance(v, Vertical):
                    v = v.__dict__.copy()  # safely detach from sqla
                v["name"] = TranslateDBFields().get_translated_vertical(
                    v["slug"], "name", v["name"]
                )
                translated_verticals.append(v)

            for n in needs:
                n = n.__dict__.copy()  # safely detach from sqla
                n["name"] = TranslateDBFields().get_translated_need(
                    n["slug"], "name", n["name"]
                )
                n["description"] = TranslateDBFields().get_translated_need(
                    n["slug"], "description", n["description"]
                )
                translated_needs.append(n)

            data_dict = {
                "specialties": translated_specialties,
                "verticals": translated_verticals,
                "keywords": keywords,
                "practitioners": practitioners,
                "needs": translated_needs,
                "need_categories": need_categories,
            }
        else:
            data_dict = {
                "specialties": specialties,
                "verticals": verticals,
                "keywords": keywords,
                "practitioners": practitioners,
                "needs": needs,
                "need_categories": need_categories,
            }

        data = {
            "data": data_dict,
            "meta": args,
            "pagination": pagination,
        }

        schema = (
            BookingFlowSearchSchema()
            if not experiment_enabled
            else BookingFlowSearchSchemaV3()
        )
        return schema.dump(data).data if not experiment_enabled else schema.dump(data)  # type: ignore[attr-defined] # "object" has no attribute "dump"


class BookingFlowCategoriesResource(AuthenticatedResource):
    @tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            launchdarkly.user_context(self.user),
            default=False,
        )
        """Get the authenticated user's need categories"""
        active_track_names = {at.name for at in self.user.active_tracks}

        if not self.user.is_enterprise:
            # Marketplace users do not have a track, but we will treat them as though they were on the
            # General Wellness track for this endpoint only.
            # https://mavenclinic.atlassian.net/jira/software/c/projects/DISCO/boards/216?assignee=712020%3A49deb732-f61f-4665-9284-92e5dd333f2c&selectedIssue=DISCO-3202
            active_track_names.add(TrackName.GENERAL_WELLNESS)

        categories_query = (
            db.session.query(NeedCategory)
            .join(NeedCategoryTrack)
            .filter(NeedCategoryTrack.track_name.in_(active_track_names))
            # Order by ascending order, with nulls last
            # NOTE: nullslast function cannot be used in mysql 5.6
            .order_by(
                NeedCategory.display_order.is_(None).asc(),
                NeedCategory.display_order.asc(),
            )
        )

        if len(active_track_names) > 1:
            categories_query = categories_query.filter(
                NeedCategory.hide_from_multitrack == False
            )
        categories = categories_query.all()

        data = {
            "data": {
                "categories": categories,
            }
        }

        platform = get_platform(request.user_agent.string)

        # Increment stats metrics
        stats.increment(
            metric_name="api.utils.provider.needs_selection",
            tags=[f"platform:{platform}"],
            pod_name=stats.PodNames.CARE_DISCOVERY,
        )

        schema = BookingFlowCategoriesGetSchema(context={"l10n_flag": l10n_flag})
        return schema.dump(data)
