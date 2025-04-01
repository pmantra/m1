import datetime
from typing import Any, Dict, List, Optional

from flask import request
from flask_restful import abort
from httpproblem import Problem
from marshmallow import ValidationError
from maven import feature_flags
from sqlalchemy.dialects import mysql

from authn.models.user import User
from care_plans.care_plans_service import CarePlansService
from common import stats
from common.services.api import (
    AuthenticatedResource,
    AuthenticatedViaTokenResource,
    EnterpriseResource,
    PermissionedUserResource,
    UnauthenticatedResource,
)
from l10n.utils import is_default_langauge, request_locale_str
from learn.models import resource_interaction
from learn.models.article_type import ArticleType
from learn.schemas import article as article_schemas
from learn.services import article_service, banner_service
from learn.services.bookmarks import BookmarksService
from learn.services.predicted_related_reads_service import PredictedRelatedReadsService
from learn.utils import disclaimers
from learn.utils.resource_utils import populate_estimated_read_times_and_media_types
from models import tracks
from models.marketing import (
    Resource,
    ResourceContentTypes,
    ResourceTypes,
    resource_organizations,
)
from models.programs import Module
from models.tracks import ChangeReason, MemberTrack, TrackName
from storage.connection import db
from tasks.enterprise import enterprise_user_post_setup
from tracks import service as tracks_svc
from utils.contentful import parse_preview
from utils.exceptions import ProgramLifecycleError, log_exception_message
from utils.launchdarkly import user_context
from utils.lock import prevent_concurrent_requests
from utils.log import logger
from views.library import SingleOnDemandClassSchema
from views.schemas.transitions import ProgramTransitionSchema, ProgramTransitionsSchema

metric_name = "learn.resources.get_public_resource"

log = logger(__name__)


def enable_predicted_related_reads(user: User) -> bool:
    return feature_flags.bool_variation(
        "experiment-enable-get-predicted-related-reads",
        user_context(user),
        default=False,
    )


class EnterprisePublicContentResource(UnauthenticatedResource):
    __BANNER_SLUG = "banner-unlimited-virtual-care-and-more"

    def get(self, url_slug: str) -> dict:
        preview = parse_preview(request.args)
        query_string_locale = request.args.get("locale")

        url_slug = url_slug.lower()
        resource = None
        if not preview:
            # When someone passes in preview=true, we don't check for the
            # resource in the db/admin.
            # This allows the content team to test articles by slug before
            # publishing in either admin or Contentful.
            resource = Resource.get_public_published_resource_by_slug(url_slug)
            if resource is None:
                raise Problem(404)
        if preview or resource.article_type == ArticleType.RICH_TEXT:  # type: ignore[union-attr] # Item "None" of "Optional[Resource]" has no attribute "article_type"
            # try to get from contentful and if errors, metric and continue on
            # iOS doesn't handle situations where we've told it that its rich_text and then
            # we give the wrong format. therefore, this metric must be alerted on and fixed.
            try:
                article_svc = article_service.ArticleService(
                    preview=preview, user_facing=True, should_localize=True
                )

                article = article_svc.get_value(
                    identifier_value=url_slug, locale=query_string_locale
                )

                if article:
                    schema = article_schemas.ArticleSchema()
                    member_resource = None
                    if not self.user:
                        log.debug(
                            "User is not logged in. Hiding related_reads.",
                            slug=url_slug,
                        )
                        article["related_reads"] = None
                        if not query_string_locale or query_string_locale == "en-US":
                            log.debug(
                                'Because article was requested with locale en-US, including the "Learn More" banner '
                                "in the response."
                            )
                            article[
                                "banner"
                            ] = banner_service.BannerService().get_value(
                                EnterprisePublicContentResource.__BANNER_SLUG
                            )
                        else:
                            log.debug(
                                f'Because article was requested with locale {query_string_locale}, not including the "Learn More" '
                                "banner in the response."
                            )
                            article["banner"] = None
                    elif resource:
                        # only check for a bookmark if logged in, is a contentful article,
                        # and already got article from the DB
                        member_resource = BookmarksService().get_bookmark(
                            user_id=self.user.id, resource=resource
                        )
                    article["type"] = ArticleType.RICH_TEXT
                    article["disclaimer"] = disclaimers.get_disclaimer_by_locale(
                        query_string_locale or request_locale_str()
                    )
                    article["saved"] = (
                        None if not self.user else member_resource is not None
                    )
                    article["content_type"] = resource and resource.content_type
                    article["id"] = resource and str(resource.id)

                    if (
                        self.user
                        and enable_predicted_related_reads(self.user)
                        and is_default_langauge()
                    ):
                        log.info("Accessing predicted related reads")
                        related_reads_svc = PredictedRelatedReadsService(
                            preview=preview, user_facing=True
                        )
                        predicted_related_reads = related_reads_svc.get_related_reads(
                            url_slug
                        )
                        if predicted_related_reads:
                            article["related_reads"] = predicted_related_reads

                    self._increment_get_public_resource_metric(
                        article_type=ArticleType.RICH_TEXT,
                        success=True,
                        preview=preview,
                    )
                    if not preview:
                        self.__save_resource_viewed_time(url_slug, resource)  # type: ignore[arg-type] # Argument 2 to "__save_resource_viewed_time" of "EnterprisePublicContentResource" has incompatible type "Optional[Resource]"; expected "Resource"
                        CarePlansService.send_content_completed(
                            resource, self.user, "mono_content"
                        )
                    return schema.dump(article)
                if not preview:
                    log.warning(
                        "No matching article found in contentful. Falling back to database (if not previewing)",
                        slug=url_slug,
                        preview=preview,
                    )
                self._increment_get_public_resource_metric(
                    article_type=ArticleType.RICH_TEXT, success=False, preview=preview
                )

            except Exception as e:
                log.warning(
                    "Error fetching article from contentful. Falling back to database (if not previewing)",
                    exc_info=True,
                    slug=url_slug,
                    preview=preview,
                    error=e,
                )
                self._increment_get_public_resource_metric(
                    article_type=ArticleType.RICH_TEXT, success=False, preview=preview
                )

        if preview:
            # if we made it this far while previewing, something went wrong
            raise Problem(404, detail="Article not found while previewing")

        # Make sure resource image is up to date
        if resource.webflow_url:  # type: ignore[union-attr] # Item "None" of "Optional[Resource]" has no attribute "webflow_url"
            try:
                resource.pull_image_from_webflow()  # type: ignore[union-attr] # Item "None" of "Optional[Resource]" has no attribute "pull_image_from_webflow"
                db.session.commit()
            except Exception as e:
                log.error("Error fetching image for webflow resource", error=str(e))
        try:
            success = True
            CarePlansService.send_content_completed(resource, self.user, "mono_content")
            return {
                "id": str(resource.id),  # type: ignore[union-attr] # Item "None" of "Optional[Resource]" has no attribute "id"
                "title": resource.title,  # type: ignore[union-attr] # Item "None" of "Optional[Resource]" has no attribute "title"
                "body": resource.get_body_html(),  # type: ignore[union-attr] # Item "None" of "Optional[Resource]" has no attribute "get_body_html"
                "head_html": resource.get_head_html(),  # type: ignore[union-attr] # Item "None" of "Optional[Resource]" has no attribute "get_head_html"
                "content_type": resource.content_type,  # type: ignore[union-attr] # Item "None" of "Optional[Resource]" has no attribute "content_type"
                "type": ArticleType.HTML,
            }
        except Exception:
            success = False
            raise
        finally:
            self._increment_get_public_resource_metric(
                article_type=ArticleType.HTML, success=success, preview=preview
            )
            self.__save_resource_viewed_time(url_slug, resource)  # type: ignore[arg-type] # Argument 2 to "__save_resource_viewed_time" of "EnterprisePublicContentResource" has incompatible type "Optional[Resource]"; expected "Resource"

    @staticmethod
    def _increment_get_public_resource_metric(**kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        stats.increment(
            metric_name,
            pod_name=stats.PodNames.COCOPOD,
            tags=[f"{key}:{format(value).lower()}" for key, value in kwargs.items()],
        )

    def __save_resource_viewed_time(self, slug: str, resource: Resource):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not self.user:
            return
        try:
            if resource.is_article_ish():
                resource_type = resource_interaction.ResourceType.ARTICLE
            elif resource.content_type == ResourceContentTypes.on_demand_class.name:
                resource_type = resource_interaction.ResourceType.ON_DEMAND_CLASS
            else:
                raise Exception("Unknown resource_type")

            insert = mysql.insert(
                resource_interaction.ResourceInteraction, bind=db.engine
            ).values(
                resource_interaction.ResourceInteraction(
                    user_id=self.user.id,
                    resource_type=resource_type,
                    slug=slug,
                    resource_viewed_at=datetime.datetime.utcnow(),
                ).to_dict()
            )
            insert = insert.on_duplicate_key_update(
                resource_viewed_at=insert.inserted.resource_viewed_at
            )
            db.session.execute(insert)
            db.session.commit()
        except Exception as exception:
            log.warning(
                "Error saving article viewed time.",
                exc_info=True,
                slug=slug,
                content_type=resource.content_type,
                error=exception,
            )


class EnterprisePrivateContentResource(AuthenticatedViaTokenResource):
    def get(self, content_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self.user_from_auth_or_token
        if user is None:
            abort(401)

        tracks_service = tracks_svc.TrackSelectionService()
        if not tracks_service.is_enterprise(user_id=user.id):
            abort(403)

        org_id: int = tracks_service.get_organization_id_for_user(user_id=user.id)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[int]", variable has type "int")

        resource = (
            db.session.query(Resource)
            .join(resource_organizations)
            .filter(
                Resource.id == content_id,
                resource_organizations.c.organization_id == org_id,
                Resource.published_at <= datetime.datetime.utcnow(),
                Resource.resource_type == ResourceTypes.PRIVATE,
            )
            .one_or_none()
        )

        if resource is None:
            abort(404)

        # Make sure resource image is up to date
        if resource.webflow_url:
            resource.pull_image_from_webflow()
            db.session.commit()

        return {
            "id": resource.id,
            "title": resource.title,
            "body": resource.get_body_html(),
            "head_html": resource.get_head_html(),
            "content_type": resource.content_type,
        }


class UserCurrentDashboardView(AuthenticatedResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.user.id != user_id:
            abort(403)

        log_exception_message("Dashboard 2019 Load")

        return {
            "version": "1549904664",
            "slug": "final-dash-2019",
            "name": "final-dash-2019",
            "blocks": [
                {
                    "id": 1,
                    "title": "",
                    "cards": [
                        {
                            "icon": {"url": "", "alt": ""},
                            "tag": "",
                            "extras": None,
                            "id": 2,
                            "title": "Hmm, something's not quite right!",
                            "analytics_name": "final-dash-2019-card",
                            "image": {"url": "", "alt": ""},
                            "primary_metadata": "",
                            "secondary_metadata": "",
                            "body": [
                                "Looks like you're on an old version of the Maven app, "
                                "so we can't load your dashboard. Try upgrading your "
                                "Maven app to the newest version to see personalized "
                                "content on your phone!"
                            ],
                            "actions": [],
                            "type": "visual-content",
                            "style": "inline",
                        }
                    ],
                    "type": "content",
                    "theme": "",
                },
                {"id": 3, "title": "", "cards": [], "type": "", "theme": ""},
                {
                    "id": 4,
                    "title": "",
                    "cards": [
                        {
                            "icon": {"url": "", "alt": ""},
                            "tag": "",
                            "extras": None,
                            "id": 0,
                            "title": "The virtual clinic for women & families",
                            "analytics_name": "week-5-maven-promo-maven-promo-card",
                            "image": {"url": "", "alt": ""},
                            "primary_metadata": "Maven",
                            "secondary_metadata": "",
                            "body": [
                                "We’re here for you 24/7. Message your Maven Care Advocate anytime, with any question."
                            ],
                            "actions": [
                                {
                                    "type": "link",
                                    "id": 0,
                                    "cta": {
                                        "url": "/messages",
                                        "text": "Send a message",
                                        "style": "primary",
                                    },
                                }
                            ],
                            "type": "maven-promo",
                            "style": "inline",
                        }
                    ],
                    "type": "maven-promo",
                    "theme": "",
                },
            ],
        }


class UserCurrentPromptView(AuthenticatedResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.user.id != user_id:
            abort(403)

        return {}


class ProgramTransitionsResource(PermissionedUserResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # TODO: [multitrack] This endpoint may need to be re-written to account for
        #  multiple active tracks (and thus multiple sets of transitions)
        user = self._user_or_404(user_id)
        member_track: MemberTrack = user.current_member_track
        if not member_track:
            abort(400)

        module_name = member_track.name
        if not module_name:
            abort(400)

        transitions = {
            "my_program_display_name": member_track.display_name,
            "transitions": [
                {
                    "description": transition.display_description,
                    "subject": {
                        "source_name": member_track.name,
                        "destination_name": transition.name,
                        "source": member_track.id,
                        "destination": Module.id_by_name(transition.name),
                    },
                }
                for transition in member_track.transitions
            ],
        }

        schema = ProgramTransitionsSchema()
        return schema.dump(transitions)

    def _parse_args(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        atomic = request.args.get("atomic", False)
        if atomic:
            try:
                atomic = bool(int(atomic))
            except ValueError:
                log.debug("Got invalid value for query", atomic=atomic)
                atomic = False
        return atomic

    @prevent_concurrent_requests(lambda self, user_id: f"transition:{user_id}")
    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)
        schema = ProgramTransitionSchema()
        atomic = self._parse_args()

        try:
            data = schema.load(request.json if request.is_json else {})
        except ValidationError as e:
            errors = e.messages
            dict_values = list(errors.values())  # type: ignore[union-attr] # Item "List[str]" of "Union[List[str], List[Any], Dict[Any, Any]]" has no attribute "values" #type: ignore[union-attr] # Item "List[Any]" of "Union[List[str], List[Any], Dict[Any, Any]]" has no attribute "values"
            if (
                len(dict_values) > 0
                and isinstance(dict_values, list)
                and len(dict_values[0]) > 0
                and isinstance(dict_values[0], list)
            ):
                error_message = dict_values[0][0]
            else:
                error_message = f"{ProgramTransitionSchema.__name__} validation error"
            abort(400, message=error_message)

        # TODO: [multitrack] We can't assume source_name here, we'll need to somehow
        #  fetch the "source track"
        source_name = data.get("source_name") or user.current_member_track.name
        action_name = None

        if data.get("destination"):  # old
            destination = data.get("destination")
            if destination == "commit-transition" or destination == "cancel-transition":
                action_name = destination
                intended_track = None
            else:
                intended_track = Module.name_by_id(destination)
        else:  # new
            if data.get("action_name"):
                action_name = data.get("action_name")
                intended_track = None
            else:
                intended_track = data.get("destination_name")

        try:
            if action_name == "cancel-transition":
                # TODO: [multitrack] use source_track here
                tracks.cancel_transition(
                    track=user.current_member_track,
                    change_reason=ChangeReason.API_PROGRAM_CANCEL_TRANSITION,
                )
            elif action_name == "commit-transition":
                tracks.finish_transition(
                    track=user.current_member_track,
                    change_reason=ChangeReason.API_PROGRAM_FINISH_TRANSITION,
                )
            else:
                log.debug("Initiating transition.", atomic=atomic)
                if atomic:
                    tracks.transition(
                        source=user.current_member_track,
                        target=intended_track,
                        as_auto_transition=False,
                        prepare_user=True,
                        change_reason=ChangeReason.API_PROGRAM_TRANSITION,
                    )
                else:
                    tracks.initiate_transition(
                        track=user.current_member_track,
                        target=intended_track,
                        change_reason=ChangeReason.API_PROGRAM_INITIATE_TRANSITION,
                    )
        except tracks.TrackLifecycleError as e:
            log.error(e)
            db.session.rollback()
            return {"message": str(e)}, 400
        # TODO: [Track] Phase 3 - drop this.
        except ProgramLifecycleError as e:
            log.log(e.log_level, e)
            db.session.rollback()
            return {"message": e.display_message}, e.status_code
        else:
            db.session.commit()

            # TODO: [Tracks] Remove logic around enrollments
            # Run the post setup job if finishing the transition crossed an
            # enrollment boundary.
            if (source_name == TrackName.FERTILITY) and (
                intended_track == TrackName.PREGNANCY
            ):
                enterprise_user_post_setup.delay(user_id)


class ActivityDashboardMetadataResource(EnterpriseResource):
    def get(self, resource_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._user_is_enterprise_else_403()

        resources_metadata = self.get_resource_metadata(resource_ids=[resource_id])
        if len(resources_metadata) < 1:
            raise Problem(404, "Specified Resource Not Found")
        return resources_metadata[0]

    @staticmethod
    def get_resource_metadata(
        resource_ids: Optional[List[str]] = None,
        resource_slugs: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if resource_ids is None:
            resource_ids = []
        if resource_slugs is None:
            resource_slugs = []
        resources = (
            db.session.query(Resource)
            .filter(Resource.id.in_(resource_ids) | Resource.slug.in_(resource_slugs))
            .all()
        )

        resources = populate_estimated_read_times_and_media_types(resources)

        result = []
        for resource in resources:
            image_url = ""
            if resource.image:
                image_url = resource.image.asset_url()

            on_demand_class_output = {}
            article_output = {}

            if resource.on_demand_class_fields:
                on_demand_class_output = SingleOnDemandClassSchema().dump(
                    {"on_demand_class": resource}
                )
            if resource.estimated_read_time_minutes:
                article_output = {
                    "article": {  # technically they aren't all articles, but it's close enough
                        "estimated_read_time_minutes": resource.estimated_read_time_minutes,
                    }
                }

            result.append(
                {
                    "id": resource.id,
                    "slug": resource.slug,
                    "thumbnail": {
                        "url": image_url,
                    },
                    "media_type": resource.media_type,
                    **on_demand_class_output,
                    **article_output,
                }
            )
        return result


class ActivityDashboardMetadataResourceBatch(EnterpriseResource):
    __MAXIMUM_NUMBER_OF_RESOURCES = 104  # 2 per week

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._user_is_enterprise_else_403()
        resource_ids: List[str] = (
            set(request.args["resource_ids"].split(","))  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Collection[Any]", variable has type "List[str]")
            if "resource_ids" in request.args
            else []
        )
        resource_slugs: List[str] = (
            set(request.args["resource_slugs"].split(","))  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Collection[Any]", variable has type "List[str]")
            if "resource_slugs" in request.args
            else []
        )
        if (
            len(resource_ids) + len(resource_slugs) < 1
            or len(resource_ids) + len(resource_slugs)
            > ActivityDashboardMetadataResourceBatch.__MAXIMUM_NUMBER_OF_RESOURCES
        ):
            raise Problem(
                400,
                detail=f"Total number of resources must be between 1 and {ActivityDashboardMetadataResourceBatch.__MAXIMUM_NUMBER_OF_RESOURCES}, inclusive.",
            )
        resources_metadata = ActivityDashboardMetadataResource.get_resource_metadata(
            resource_ids, resource_slugs
        )

        return {"resources": resources_metadata}


class DismissalsResource(PermissionedUserResource):
    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return None
