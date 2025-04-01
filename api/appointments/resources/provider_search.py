from ddtrace import tracer
from flask import request
from flask_restful import abort
from maven import feature_flags

from appointments.schemas.provider import (
    MessageableProviderSearchSchema,
    ProviderSearchSchema,
    make_provider_search_result,
)
from appointments.services.common import get_platform
from common import stats
from common.services.api import AuthenticatedResource
from glidepath import glidepath
from models.tracks.client_track import TrackModifiers
from providers.service.provider import ProviderService
from tracks.utils.common import get_active_member_track_modifiers
from utils.launchdarkly import user_context


class ProviderSearchResource(AuthenticatedResource):
    @tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            user_context(self.user),
            default=False,
        )

        # NB (benedict): I'm torn on whether we should use this marshmallow schema at all,
        # I kept it in since it might be nice to have the validation and we can be sure
        # it isn't making any DB queries (all the fields are normal primitives).
        schema = ProviderSearchSchema()
        args = schema.load(request.args)
        args["current_user"] = self.user
        filter_params = [
            "user_ids",
            "verticals",
            "vertical_ids",
            "specialties",
            "specialty_ids",
            "need_ids",
            "need_slugs",
            "language_ids",
        ]

        # we will allow an empty search query when the member is doula_only
        active_tracks = self.user.active_tracks
        member_track_modifiers = get_active_member_track_modifiers(active_tracks)

        is_doula_only_member = TrackModifiers.DOULA_ONLY in member_track_modifiers

        if not any(args.get(p) for p in filter_params) and not is_doula_only_member:
            abort(
                400,
                message="At least one filter param must be present from "
                f"among {filter_params}",
            )

        args["member_track_modifiers"] = member_track_modifiers
        all_practitioners, _ = ProviderService().search(
            include_count=False,
            **args,
        )

        all_practitioner_ids = [p.id for p in all_practitioners]

        latest_appointment_date_by_provider_id = (
            ProviderService().get_latest_appointments_by_provider_id(
                self.user.id, all_practitioner_ids
            )
        )
        # There should be no SQL executed past this point.
        with glidepath.respond():
            result = {
                "data": [
                    make_provider_search_result(
                        p,
                        self.user,
                        latest_appointment_date_by_provider_id,
                        l10n_flag=l10n_flag,
                    )
                    for p in all_practitioners
                ]
            }

            platform = get_platform(request.user_agent.string)
            # Increment stats metrics
            stats.increment(
                metric_name="api.appointments.resources.provider_search",
                tags=[
                    f"platform:{platform}",
                    "variant:provider_selection",
                    "event:provider_search_results",
                ],
                pod_name=stats.PodNames.CARE_DISCOVERY,
            )

            return result


class MessageableProviderSearchResource(ProviderSearchResource):
    @tracer.wrap()
    def get(self) -> dict:
        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            user_context(self.user),
            default=False,
        )

        schema = MessageableProviderSearchSchema()
        args = schema.load(request.args)

        filter_params = [
            "vertical_ids",
            "specialty_ids",
            "need_ids",
            "language_ids",
        ]
        if not any(args.get(p) for p in filter_params):
            abort(
                400,
                message="At least one filter param must be present from "
                f"among {filter_params}",
            )

        # We want to gate the rollout of this feature at first to only requests that specify need ids,
        # but if this launches well, we will remove this constraint.
        if not args.get("need_ids"):
            return {"data": []}

        all_providers = ProviderService().search_messageable(
            current_user=self.user,
            vertical_ids=args.get("vertical_ids"),
            specialty_ids=args.get("specialty_ids"),
            need_ids=args.get("need_ids"),
            language_ids=args.get("language_ids"),
            limit=args.get("limit"),
            offset=args.get("offset"),
            member_track_modifiers=get_active_member_track_modifiers(
                self.user.active_tracks
            ),
        )

        all_practitioner_ids = [p.id for p in all_providers]

        latest_appointment_date_by_provider_id = (
            ProviderService().get_latest_appointments_by_provider_id(
                self.user.id, all_practitioner_ids
            )
        )
        # There should be no SQL executed past this point.
        with glidepath.respond():
            result = {
                "data": [
                    make_provider_search_result(
                        p,
                        self.user,
                        latest_appointment_date_by_provider_id,
                        l10n_flag=l10n_flag,
                    )
                    for p in all_providers
                ]
            }
            return result
