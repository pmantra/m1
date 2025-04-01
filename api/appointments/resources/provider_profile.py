from ddtrace import tracer
from flask import request
from flask_restful import abort
from maven import feature_flags
from sqlalchemy.orm.exc import NoResultFound

from appointments.schemas.provider import make_provider_profile_result
from appointments.services.common import get_platform
from authn.models.user import User
from common import stats
from common.services.api import AuthenticatedResource
from models.base import db
from models.tracks import MemberTrack
from providers.domain.model import Provider
from providers.service.provider import ProviderService
from tracks.utils.common import get_active_member_track_modifiers
from utils.launchdarkly import user_context


class BookingFlowProviderProfileResource(AuthenticatedResource):
    @tracer.wrap()
    def get(self, provider_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            user_context(self.user),
            default=False,
        )

        try:
            return_inactive_providers = feature_flags.bool_variation(
                "release-return-inactive-providers-from-get-providers-by-id",
                user_context(self.user),
                default=False,
            )
            if return_inactive_providers:
                provider: User = (
                    db.session.query(User)
                    .join(Provider, Provider.user_id == User.id)
                    .filter(
                        User.id == provider_id,
                    )
                    .one()
                )
            else:
                provider = (
                    db.session.query(User)
                    .join(Provider, Provider.user_id == User.id)
                    .filter(
                        User.id == provider_id,
                        Provider.active.is_(True),
                    )
                    .one()
                )
        except NoResultFound:
            abort(404, message="That provider ID does not exist!")

        platform = get_platform(request.user_agent.string)
        latest_appointment_date_by_provider_id = (
            ProviderService().get_latest_appointments_by_provider_id(
                self.user.id, [provider_id]
            )
        )

        active_member_tracks = (
            db.session.query(MemberTrack)
            .filter(
                MemberTrack.active,
                MemberTrack.user_id == self.user.id,
            )
            .all()
        )

        member_track_modifiers = get_active_member_track_modifiers(active_member_tracks)
        client_track_ids = [track.client_track_id for track in active_member_tracks]

        # Increment stats metrics
        stats.increment(
            metric_name="api.appointments.resources.provider_profile",
            tags=[
                f"platform:{platform}",
                "variant:provider_selection",
                "event:provider_profile",
            ],
            pod_name=stats.PodNames.CARE_DISCOVERY,
        )
        return make_provider_profile_result(
            provider,
            self.user,
            latest_appointment_date_by_provider_id,
            member_track_modifiers,
            client_track_ids,
            l10n_flag=l10n_flag,
        )
