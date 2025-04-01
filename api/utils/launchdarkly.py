import hashlib
import re
import typing
from datetime import datetime

from maven import feature_flags

from authn.services.integrations.idp import IDPUser
from utils.constants import CronJobName

if typing.TYPE_CHECKING:
    from authn.models.user import User
    from wallet.models.reimbursement_wallet import ReimbursementWallet

from maven.feature_flags import Context

from models.tracks.track import TrackName
from utils.log import logger

log = logger(__name__)

LEGACY_SURVEY_URL_FLAG_NAME = "legacy-survey-url"


def to_camelcase(s: str) -> str:
    return re.sub(
        r"(?!^)_([a-zA-Z])",
        lambda m: m.group(1).capitalize(),
        s,
    )


current_phase_attr = {
    track_name.value: f"{to_camelcase(track_name.value)}CurrentPhase"
    for track_name in TrackName
}
scheduled_end_date_attr = {
    track_name.value: f"{to_camelcase(track_name.value)}ScheduledEndDate"
    for track_name in TrackName
}
start_date_attr = {
    track_name.value: f"{to_camelcase(track_name.value)}StartDate"
    for track_name in TrackName
}


def context(user: "User") -> Context:
    builder = Context.multi_builder()
    builder.add(user_context(user))
    builder.add(health_profile_context(user))
    return builder.build()


def marshmallow_context(esp_id: str, email: str) -> Context:
    builder = Context.builder(esp_id).kind("marshmallow-context")
    builder.set("email", email)
    builder.private("email")
    return builder.build()


def use_legacy_survey_monkey_url() -> bool:
    """
    Returns whether to use the legacy SurveyMonkey URL for wallet applications
    True - Use the legacy URL
    False - Use the WQS URL
    """
    return feature_flags.bool_variation(LEGACY_SURVEY_URL_FLAG_NAME, default=True)


def idp_user_context(idp_user: IDPUser) -> Context:
    key = hashlib.sha256(idp_user.user_id.encode()).hexdigest()
    builder = Context.builder(key).kind("idp-user-context")
    builder.set("auth0UserId", idp_user.user_id)
    builder.private("auth0UserId")
    if idp_user.identities:
        builder.set(
            "connectionName", idp_user.identities[0].connection
        )  # Currently the auth0 identity will only have one
        builder.private("connectionName")
    builder.set("email", idp_user.email)
    builder.private("email")
    builder.set("externalUserId", idp_user.external_user_id)
    builder.private("externalUserId")
    builder.set("employeeId", idp_user.employee_id)
    builder.private("employeeId")
    return builder.build()


def wallet_context(wallet: "ReimbursementWallet") -> Context:
    """
    Builds a general LaunchDarkly Context for the wallets
    """
    builder = Context.builder(str(wallet.id)).kind("wallet")

    builder.set(
        "organizationId", wallet.reimbursement_organization_settings.organization_id
    )
    builder.private("organizationId")

    builder.set(
        "reimbursementOrganizationSettingsId",
        wallet.reimbursement_organization_settings_id,
    )
    builder.private("reimbursementOrganizationSettingsId")

    return builder.build()


def user_context(user: "User") -> Context:
    builder = Context.builder(user.esp_id).kind("user")

    builder.set("userId", user.id)
    builder.private("userId")

    builder.set("createdAt", user.created_at.isoformat())  # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "isoformat"
    builder.private("createdAt")

    builder.set("name", user.full_name)
    builder.private("name")

    builder.set("email", user.email)
    builder.private("email")

    builder.set("lowercaseEmail", user.email.lower())
    builder.private("lowercaseEmail")

    from user_locale.services.locale_preference_service import LocalePreferenceService

    locale_for_user = LocalePreferenceService.get_preferred_locale_for_user(user)

    locale = locale_for_user.language if locale_for_user else "en"
    builder.set("locale", locale)
    builder.private("locale")

    builder.set("country", user.normalized_country_abbr)
    builder.private("country")

    builder.set(
        "state",
        (
            user.member_profile.state.abbreviation
            if user.member_profile and user.member_profile.state
            else None
        ),
    )
    builder.private("state")

    roles = list(user.user_types)
    builder.set("roles", roles)
    builder.private("roles")

    if "practitioner" in roles and user.practitioner_profile:
        verticals = [vertical.name for vertical in user.practitioner_profile.verticals]
        builder.set("verticals", verticals)

    builder.private("verticals")

    is_enterprise = user.is_enterprise
    builder.set("isEnterprise", is_enterprise)
    builder.private("isEnterprise")

    oe_org_id = (
        user.organization_employee.organization_id
        if (is_enterprise and user.organization_employee)
        else None
    )

    builder.set("organizationId", oe_org_id)
    builder.private("organizationId")

    organization_id_v2 = (
        user.active_client_track.organization_id if user.active_client_track else None
    )
    builder.set("organizationV2Id", organization_id_v2)

    if oe_org_id != organization_id_v2:
        log.warning(
            "Organization ID mismatch",
            user_id=user.id,
            oe_org_id=oe_org_id,
            v2_org_id=organization_id_v2,
        )

    # For each active track...
    active_track_names = []
    for track in user.active_tracks:
        # Track Name
        active_track_names.append(track.name)
        # Current Phase
        if (current_phase := track.current_phase) is not None:
            builder.set(current_phase_attr[track.name], current_phase.name)
        # Start Date
        if (start_date := track.start_date) is not None:
            builder.set(
                start_date_attr[track.name],
                int(
                    datetime.combine(start_date, datetime.min.time()).timestamp() * 1000
                ),
            )
        # Scheduled End Date
        builder.set(
            scheduled_end_date_attr[track.name],
            track.get_scheduled_end_date().isoformat(),
        )
    builder.private(*current_phase_attr.values())
    builder.private(*scheduled_end_date_attr.values())
    builder.private(*start_date_attr.values())

    builder.set("activeTracks", active_track_names)
    builder.private("activeTracks")

    builder.set("isMultiTrack", len(active_track_names) > 1)
    builder.private("isMultiTrack")

    return builder.build()


def health_profile_context(user: "User") -> Context:
    from health.services.health_profile_service import HealthProfileService

    builder = Context.builder(user.esp_id).kind("monolith-health-profile")
    hp_service = HealthProfileService(user)
    builder.set(
        "riskFactors",
        [risk_factor.name for risk_factor in user.current_risk_flags()],
    )
    builder.private("riskFactors")

    builder.set("fertilityTreatmentStatus", hp_service.get_fertility_treatment_status())
    builder.private("fertilityTreatmentStatus")

    return builder.build()


def rq_job_context(job_name: str) -> Context:
    return Context.builder(job_name).kind("rq-job").build()


def allow_cycle_currency_switch_process(wallet: "ReimbursementWallet") -> bool:
    """
    Returns if a wallet should be allowed to switch from currency to cycle ROS
    Note: This is specific to the Amazon A/B testing requirements
    """
    return feature_flags.bool_variation(
        "wallet-amazon-cycle-currency-switch",
        wallet_context(wallet=wallet),
        default=False,
    )


def should_job_run_in_airflow(cron_job: CronJobName) -> bool:
    cron_job_name = cron_job.name.upper()

    try:
        return feature_flags.bool_variation(
            "experiment-run-rq-cron-job-in-airflow",
            rq_job_context(cron_job_name),
            default=False,
        )
    except Exception:
        feature_flags.initialize()
        return feature_flags.bool_variation(
            "experiment-run-rq-cron-job-in-airflow",
            rq_job_context(cron_job_name),
            default=False,
        )
