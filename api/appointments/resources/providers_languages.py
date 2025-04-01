from dataclasses import asdict

from ddtrace import tracer
from flask import request
from flask_restful import abort
from marshmallow import ValidationError
from maven import feature_flags

from appointments.schemas.provider import ProvidersLanguagesGetSchema
from common.services.api import AuthenticatedResource
from models.tracks.client_track import TrackModifiers
from providers.schemas.provider_languages import (
    ProviderLanguagesClientResponseElement,
    ProvidersLanguagesClientResponseStruct,
)
from providers.service.provider import ProviderService
from tracks.utils.common import get_active_member_track_modifiers
from utils.launchdarkly import user_context
from utils.log import logger

log = logger(__name__)


class ProvidersLanguagesResource(AuthenticatedResource):
    @tracer.wrap()
    def get(self) -> dict:
        schema = ProvidersLanguagesGetSchema()
        try:
            args = schema.load(request.args)
        except ValidationError as exc:
            log.warn(exc.messages)
            abort(400, message=exc.messages)

        args["current_user"] = self.user
        filter_params = [
            "user_ids",
            "verticals",
            "vertical_ids",
            "specialties",
            "specialty_ids",
            "need_ids",
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
        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            user_context(self.user),
            default=False,
        )

        all_providers, _ = ProviderService().search(
            include_count=False,
            **args,
        )
        all_provider_ids = [p.id for p in all_providers]
        log.info(
            "Providers Languages - Found providers",
            provider_ids=all_provider_ids,
        )

        languages = ProviderService.get_provider_languages(all_provider_ids, l10n_flag)

        response = ProvidersLanguagesClientResponseStruct(
            [
                ProviderLanguagesClientResponseElement(id=l.id, display_name=l.name)
                for l in languages
            ]
        )
        return asdict(response)
