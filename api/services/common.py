from __future__ import annotations

from typing import TYPE_CHECKING

from maven import feature_flags

from models.common import PrivilegeType
from providers.service.provider import ProviderService
from utils.log import logger

log = logger(__name__)


if TYPE_CHECKING:
    from authn.models.user import User


def calculate_privilege_type_v2(practitioner: User | None, user: User | None) -> str:
    """
    See https://docs.google.com/document/d/1FsO317-HRkXmpmqEu20e5nRMA88h2TJ64OvsNC4PZOw/edit?tab=t.0
    for reference on derivation logic.
    """
    if not practitioner or not user:
        (
            log.error(
                "Missing practitioner or user in calculate_privilege_type, we have not considered how to deal with this",
                practitioner=practitioner.id if practitioner else None,
                user=user.id if user else None,
            )
        )
        return PrivilegeType.EDUCATION_ONLY

    provider_profile = practitioner.practitioner_profile
    verticals = provider_profile.verticals
    if not verticals:
        return PrivilegeType.EDUCATION_ONLY.value

    provider_certified_states = provider_profile.certified_states
    member_org_is_coaching_only = (
        user.organization.education_only if user.organization else False
    )
    member_state_abbreviation = (
        user.member_profile.state.abbreviation if user.member_profile.state else ""
    )
    certified_state_abbreviations = [s.abbreviation for s in provider_certified_states]

    return ProviderService.get_provider_privilege_type_for_member(
        verticals[0].filter_by_state,
        member_state_abbreviation in certified_state_abbreviations,
        provider_profile.is_international,
        user.member_profile.is_international,
        member_org_is_coaching_only,
    )


def _check_if_member_is_international(user: User | None) -> str | None:
    if user and user.member_profile and user.member_profile.is_international:
        return PrivilegeType.INTERNATIONAL.value
    return None


def _check_provider_type(user: User | None, member: User | None) -> str:
    # TODO: user is optional here and the null should be guarded.
    # the ignores below should be removed and the correct logic should be
    # implemented for when user is None.
    provider_service = ProviderService()
    if not provider_service.is_medical_provider(
        user.id,  # type: ignore[union-attr]
        user.practitioner_profile,  # type: ignore[union-attr]
    ):
        return PrivilegeType.STANDARD.value
    member_state = member.profile.state if (member and member.profile) else None
    if member_state is not None and provider_service.in_certified_states(
        user.id,  # type: ignore[union-attr]
        member_state,
        user.practitioner_profile,  # type: ignore[union-attr]
    ):
        if member.organization and member.organization.education_only:  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "organization"
            return PrivilegeType.EDUCATION_ONLY.value
        else:
            return PrivilegeType.STANDARD.value

    return PrivilegeType.ANONYMOUS.value


def calculate_privilege_type(practitioner: User | None, user: User | None) -> str:

    """
    See https://whimsical.com/booking-flow-and-appointment-logics-LyY79gweHVuzAgw3vgsXYC
    for reference on derivation logic.
    n.b.: Only medical providers can have anonymous appointments.
    """
    # avoid circular import that breaks cron jobs in appointment_notifications
    from utils.launchdarkly import user_context

    if feature_flags.bool_variation(
        "release-appointment-scope-of-practice",
        user and user_context(user),
        default=False,
    ):
        return calculate_privilege_type_v2(practitioner, user)

    return _check_if_member_is_international(user) or _check_provider_type(
        practitioner, user
    )
