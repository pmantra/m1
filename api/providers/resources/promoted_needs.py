from dataclasses import asdict

from ddtrace import tracer
from flask import request
from marshmallow import Schema, fields
from maven import feature_flags

from appointments.schemas.provider import serialize_datetime
from appointments.services.common import get_platform
from common import stats
from common.services.api import AuthenticatedResource
from l10n.db_strings.translate import TranslateDBFields
from providers.service.need import NeedService
from providers.service.provider import ProviderService
from utils import launchdarkly
from utils.log import logger

log = logger(__name__)


class PromotedNeedsSchema(Schema):
    availability_scope_in_days = fields.Integer(required=False)


class PromotedNeedsResource(AuthenticatedResource):
    @tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Get top 3 needs corresponding to the request user
        For each Need, get 3 providers whose next availability is determined by the query param availability_scope_in_days
        If there is no availability for that Need within that time window,
        then do not include that Need in the response
        """
        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            launchdarkly.user_context(self.user),
            default=False,
        )

        schema = PromotedNeedsSchema()
        args = schema.load(request.args)
        availability_scope_in_days = args.get("availability_scope_in_days", 3)

        # get needs based on request user
        needs = NeedService().get_needs_by_member(self.user)

        # get all provider data based on needs
        need_and_providers = []
        for need in needs:
            # search for providers by need
            providers, _ = ProviderService().search(
                current_user=self.user,
                need_ids=[need.id],
                availability_scope_in_days=availability_scope_in_days,
                order_by="next_availability",
                order_direction="asc",
                limit=3,
            )

            # find the provider with the earliest availability out of the 3
            next_availabilities = [
                provider.practitioner_profile.next_availability
                for provider in providers
                if provider.practitioner_profile.next_availability
            ]
            if len(next_availabilities) > 0:
                if l10n_flag and need.slug:
                    need.name = TranslateDBFields().get_translated_need(
                        need.slug, "name", need.name
                    )
                    need.description = TranslateDBFields().get_translated_need(
                        need.slug, "description", need.description
                    )

                # then format response for providers
                need_and_providers.append(
                    {
                        "need": asdict(need),
                        "providers": [
                            {
                                "id": provider.id,
                                "image_url": provider.avatar_url,
                            }
                            for provider in providers
                        ],
                        "next_availability": serialize_datetime(
                            min(next_availabilities)
                        ),
                    }
                )

        # format response
        needs_and_providers = {"data": need_and_providers}

        # for tracking requests per platform
        platform = get_platform(request.user_agent.string)
        stats.increment(
            metric_name="api.appointments.resources.promoted_needs",
            tags=[
                f"platform:{platform}",
                "variant:promoted_needs",
            ],
            pod_name=stats.PodNames.CARE_DISCOVERY,
        )

        return needs_and_providers
