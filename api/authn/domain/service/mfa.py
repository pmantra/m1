from __future__ import annotations

import datetime
from enum import Enum
from typing import Literal

import ddtrace
import phonenumbers
import sqlalchemy.orm

from authn.domain import model, repository, service
from authn.models.user import MFAState
from authn.services.integrations import idp, mfa, twilio
from common import stats
from provider_matching.services.matching_engine import get_practitioner_profile
from storage.connection import db
from utils.log import logger

log = logger(__name__)

__all__ = (
    "MFARequireType",
    "MFA_REQUIRED_TYPE_TO_REASON_MAP",
    "MFAService",
    "UserMFAError",
    "UserMFAConfigurationError",
    "UserMFAVerificationError",
    "UserMFARateLimitError",
    "UserMFAIntegrationError",
)


class MFARequireType(Enum):
    ORG = ("ORG",)
    USER = ("USER",)
    PRACTITIONER = "PRACTITIONER"
    NOT_REQUIRED = "NOT_REQUIRED"


class MFAEnforcementReason(Enum):
    REQUIRED_BY_ORGANIZATION = (1,)
    REQUIRED_BY_USER = (2,)
    REQUIRED_FOR_PRACTITIONER = 3
    NOT_REQUIRED = 4


MFA_REQUIRED_TYPE_TO_REASON_MAP = {
    MFARequireType.ORG: MFAEnforcementReason.REQUIRED_BY_ORGANIZATION,
    MFARequireType.USER: MFAEnforcementReason.REQUIRED_BY_USER,
    MFARequireType.PRACTITIONER: MFAEnforcementReason.REQUIRED_FOR_PRACTITIONER,
    MFARequireType.NOT_REQUIRED: MFAEnforcementReason.NOT_REQUIRED,
}


def get_mfa_service() -> MFAService:
    return MFAService()


class MFAService:
    """Core business logic for managing our Multi-Factor Authentication integration."""

    __slots__ = ("repo", "user_service", "organization_auth", "user_auth", "session")

    ELIGIBILITY_TIME_OUT_SEC = 1

    def __init__(
        self,
        *,
        repo: repository.UserMFARepository = None,  # type: ignore[assignment] # Incompatible default for argument "repo" (default has type "None", argument has type "UserMFARepository")
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        user_service: service.UserService = None,  # type: ignore[assignment] # Incompatible default for argument "user_service" (default has type "None", argument has type "UserService")
        organization_auth: repository.OrganizationAuthRepository = None,  # type: ignore[assignment] # Incompatible default for argument "organization_auth" (default has type "None", argument has type "OrganizationAuthRepository")
        user_auth: repository.UserAuthRepository = None,  # type: ignore[assignment] # Incompatible default for argument "user_auth" (default has type "None", argument has type "UserAuthRepository")
        is_in_uow: bool = False,
    ):
        self.session = session or db.session
        self.repo = repo or repository.UserMFARepository(
            session=self.session, is_in_uow=is_in_uow
        )
        self.user_service = user_service or service.UserService(
            session=self.session, is_in_uow=is_in_uow
        )
        self.organization_auth = (
            organization_auth
            or repository.OrganizationAuthRepository(
                session=self.session, is_in_uow=is_in_uow
            )
        )
        self.user_auth = user_auth or repository.UserAuthRepository(
            session=self.session, is_in_uow=is_in_uow
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(repository={self.repo}, user_service={self.user_service}, organization_auth={self.organization_auth})>"

    def get_all_by_time_range(
        self, end: datetime.date, start: datetime.date
    ) -> list[model.OrganizationAuth] | None:
        if end <= start:
            log.error(f"{end} time is less or equal to {start} time")
            return None
        return self.organization_auth.get_all_by_time_range(start=start, end=end)

    def process_challenge_response(
        self, user: model.User, action: mfa.VerificationRequiredActions, token: str
    ) -> model.UserMFA | None:
        """Verify the provided token and handle the signalled action."""
        enablement = self.verify_token(user=user, token=token)
        # First time here...
        if action == mfa.VerificationRequiredActions.ENABLE_MFA:
            enablement.verified = True
            verified = self.repo.update(instance=enablement)
            return verified
        # Last time here...
        if action == mfa.VerificationRequiredActions.DISABLE_MFA:
            self.repo.delete(id=user.id)
            return  # type: ignore[return-value] # Return value expected
        # Just a regular login...
        return enablement

    def begin_enable(
        self, user: model.User, sms_phone_number: str, require_resend: bool = False
    ) -> model.UserMFA:
        """Initialize an MFA configuration for a user.

        Once we've created or updated an enablement for a given user, we will send a token
        to the phone number provided via `sms_phone_number`.

        Setting the new configuration to `verified` will occur when the user inputs the token.
        """
        metric_name = "api.authn.domain.service.mfa.begin_enable"
        parsed, normalized = self.normalize_phone(sms_phone_number=sms_phone_number)
        # Look for an existing MFA config
        existing_enablement = self.repo.get(id=user.id)  # type: ignore[arg-type] # Argument "id" to "get" of "BaseRepository" has incompatible type "Optional[int]"; expected "int"
        has_enablement = existing_enablement is not None
        is_verified = has_enablement and existing_enablement.verified  # type: ignore[union-attr] # Item "None" of "Optional[UserMFA]" has no attribute "verified"
        same_number = (
            has_enablement and existing_enablement.sms_phone_number == normalized  # type: ignore[union-attr] # Item "None" of "Optional[UserMFA]" has no attribute "sms_phone_number"
        )
        truth = (has_enablement, is_verified, same_number)
        # Already configured and verified with this number.
        # If resend is not required:
        #   Nothing to be done here.
        #   Short-circuit the function.
        # If resend is required:
        #   Send out the MFA challenge.
        #   Short-circuit the function.
        if truth == (True, True, True):
            if require_resend:
                self.send_challenge(sms_phone_number=normalized)
            return existing_enablement  # type: ignore[return-value] # Incompatible return value type (got "Optional[UserMFA]", expected "UserMFA")
        # Already configured with this number, but not verified.
        #   Send a new token to the user to retry verification.
        #   Short-circuit the function.
        if truth == (True, False, True):
            self.send_challenge(sms_phone_number=normalized)
            return existing_enablement  # type: ignore[return-value] # Incompatible return value type (got "Optional[UserMFA]", expected "UserMFA")
        # Non-matching number.
        if truth in {
            # Old number is verified
            (True, True, False),
            # Old number is un-verified
            (True, False, False),
        }:
            log.info("MFA enrollment update for user_id %s received!", user.id)
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=["type:update"],
            )
            # Delete the existing configuration, it's invalid.
            self.repo.delete(id=user.id)
            # Implicit fall-though to creating a new configuration
        if truth == (False, False, False):
            log.info("MFA enrollment request for user_id %s received!", user.id)
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=["type:enrollment"],
            )

        # Create a new configuration and twilio challenge.
        new_enablement = self.repo.create(
            instance=model.UserMFA(
                user_id=user.id,  # type: ignore[arg-type] # Argument "user_id" to "UserMFA" has incompatible type "Optional[int]"; expected "int"
                sms_phone_number=normalized,
                external_user_id=None,  # type: ignore[arg-type] # Argument "external_user_id" to "UserMFA" has incompatible type "None"; expected "int"
                mfa_state="pending_verification",
            ),
            fetch=True,
        )
        # Send an MFA challenge to the end-user.
        self.send_challenge(
            sms_phone_number=normalized,
        )
        return new_enablement

    def begin_disable(self, user: model.User) -> model.UserMFA:
        """Begin disabling a user's MFA configuration.

        Set the configuration as un-verified to prevent normal login and send a token to the
        user to verify that they wish to disable their configuration.

        Deleting the configuration will occur once the user responds with the token.
        """
        # Fetch the mfa enablement for this user.
        enablement = self.get(user_id=user.id)  # type: ignore[arg-type] # Argument "user_id" to "get" of "MFAService" has incompatible type "Optional[int]"; expected "int"
        # If there isn't one, there's nothing to be done here.
        if enablement is None:
            return  # type: ignore[return-value] # Return value expected

        # Set the current configuration to un-verified.
        enablement.verified = False
        disabled = self.repo.update(instance=enablement)
        # Send a challenge to the user to verify who they are before we actually nuke the config.
        self.send_challenge(
            sms_phone_number=enablement.sms_phone_number,
        )
        return disabled

    def verify_token(self, *, user: model.User, token: str) -> model.UserMFA:
        enablement = self.get(user_id=user.id)  # type: ignore[arg-type] # Argument "user_id" to "get" of "MFAService" has incompatible type "Optional[int]"; expected "int"
        # Can't verify this user for MFA, we haven't configured them for it.
        if not enablement:
            raise UserMFAConfigurationError(
                "Couldn't locate a MFA Configuration for the given user."
            )
        # The token provided failed verification with our provider.
        if not twilio.verify_otp(enablement.sms_phone_number, token):
            raise UserMFAVerificationError(
                "Failed to verify the given user with the given token."
            )
        return enablement

    @staticmethod
    def send_challenge(
        sms_phone_number: str,
    ) -> Literal[True]:
        try:
            sent = twilio.request_otp_via_sms(sms_phone_number)
        except twilio.TwilioRateLimitException:
            raise UserMFARateLimitError(
                "You have reached the rate limit. Please try again in a few minutes."
            )
        except twilio.TwilioApiException:
            raise UserMFAIntegrationError(
                "Error sending verification code via SMS, please try again."
            )

        if not sent:
            raise UserMFAIntegrationError(
                "Error sending verification code via SMS, please try again."
            )

        return sent

    def get(self, user_id: int) -> model.UserMFA | None:
        enablement = self.repo.get(id=user_id)
        return enablement

    def update_mfa_status_and_sms_phone_number(
        self, user_id: int, sms_phone_number: str, is_enable: bool
    ) -> None:
        record = self.repo.get(id=user_id)
        if not record:
            log.warning(f"Can't find MFA data for user {user_id}")
        else:
            parsed, normalized = self.normalize_phone(sms_phone_number)
            record.sms_phone_number = normalized
            record.mfa_state = MFAState.ENABLED if is_enable else MFAState.DISABLED  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Literal[MFAState.ENABLED, MFAState.DISABLED]", variable has type "Optional[Literal[disabled, pending_verification, enabled]]")
            self.repo.update(instance=record)

    def update_user_company_mfa_to_auth0(
        self, user_id: int, is_company_mfa_required: bool
    ) -> str | None:
        """
        Update the company mfa required information in the user app_metadata.
        Return the Auth0 user phone number to update in the Maven DB
        """
        management_client = idp.ManagementClient()
        user_auth = self.user_auth.get_by_user_id(user_id=user_id)
        log.info(f"user auth info is {user_auth}")
        if user_auth is None:
            log.error(
                f"Update user company mfa, can't find user auth for user id {user_id}"
            )
            return None
        external_id_str = user_auth.external_id

        management_client.update_company_enforce_mfa(
            external_id=external_id_str, company_enforce_mfa=is_company_mfa_required
        )
        log.info(
            f"Successfully sync company mfa {is_company_mfa_required} to Auth0 for user {user_id}"
        )
        return management_client.get_user_mfa_sms_phone_number(
            external_id=external_id_str
        )

    @staticmethod
    def normalize_phone(sms_phone_number: str) -> tuple[phonenumbers.PhoneNumber, str]:
        # Parse and normalize the provided phone number.
        try:
            parsed = phonenumbers.parse(sms_phone_number, "US")
        except phonenumbers.NumberParseException:
            raise UserMFAConfigurationError(
                "The provided phone number could not be parsed."
            )

        # Short-circuit this method if the phone number isn't valid.
        if not phonenumbers.is_valid_number(parsed):
            raise UserMFAConfigurationError(
                "The provided phone number could not be validated."
            )
        normalized = phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.E164,
        )
        return parsed, normalized

    @ddtrace.tracer.wrap()
    @stats.timed(
        metric_name="api.authn.domain.service.mfa.get_org_id_by_user_id.timer",
        pod_name=stats.PodNames.CORE_SERVICES,
    )
    def get_org_id_by_user_id(self, *, user_id: int) -> int | None:
        # To avoid circular import issue
        from tracks.service import TrackSelectionService

        metric_name = "api.authn.domain.service.mfa.get_org_id_by_user_id"
        org_id = None
        try:
            tracks_service = TrackSelectionService()
            org_id = tracks_service.get_organization_id_for_user(user_id=user_id)
        except Exception:
            # Will catch all the exceptions, it won't impact login flow
            log.error(f"Failed to get org id for user {user_id}")
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=["has_org_id:false", "error:true"],
            )
            return org_id

        if org_id:
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=["has_org_id:true", "error:false"],
            )
            return org_id
        else:
            stats.increment(
                metric_name=metric_name,
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=["has_org_id:false", "error:false"],
            )
            return None

    def is_mfa_required_for_user_profile(self, *, user_id: int) -> bool:
        """
        The function to check whether the user has practitioner profile. If so, the user needs to do MFA
        """
        prac_profile = get_practitioner_profile(user_id)

        return prac_profile is not None

    def is_mfa_required_for_org(self, *, org_id: int) -> bool:
        """
        The function to check whether the organization of the user requires MFA
        """
        org_auth: model.OrganizationAuth = (
            self.organization_auth.get_by_organization_id(organization_id=org_id)
        )

        if org_auth is None:
            return False

        return org_auth.mfa_required

    def get_user_mfa_status(
        self, *, user_id: int
    ) -> tuple[bool, MFAEnforcementReason] | None:
        """
        The function to check whether the user needs MFA.
        If it returns None, it means there is an error, the callee should throw a corresponding error.

        It is based on 3 conditions in order:
        1. the organization of the user requires MFA.
        2. the user is practitioner.
        3. the user enabled MFA at user level.

        """
        # check mfa for organization
        org_id: int | None = self.get_org_id_by_user_id(user_id=user_id)
        org_mfa: bool | None = False
        if org_id is None:
            log.info("Org id is not found for user id: %s", user_id)
        else:
            org_mfa = self.is_mfa_required_for_org(org_id=org_id)
            metric_name = "api.authn.domain.service.mfa.get_org_mfa_status"

            if org_mfa:
                stats.increment(
                    metric_name=metric_name,
                    pod_name=stats.PodNames.CORE_SERVICES,
                    tags=["org_mfa:true"],
                )
                # In this section, the org_mfa is True for the user
                management_client = idp.ManagementClient()
                user_auth_entry = self.user_auth.get_by_user_id(user_id=user_id)
                external_id = user_auth_entry.external_id
                management_client.update_company_enforce_mfa(
                    external_id=external_id, company_enforce_mfa=True
                )

                return org_mfa, MFA_REQUIRED_TYPE_TO_REASON_MAP[MFARequireType.ORG]
            else:
                stats.increment(
                    metric_name=metric_name,
                    pod_name=stats.PodNames.CORE_SERVICES,
                    tags=["org_mfa:false"],
                )

        # The check for practitioner is disabled because we have found some practitioners missing MFA setup.
        # We will revisit this piece of code after closing the gap of MFA setup among practitioners.
        # check mfa for practitioner
        # is_practitioner = self.is_mfa_required_for_user_profile(user_id=user_id)
        # if is_practitioner:
        #     return True, MFA_REQUIRED_TYPE_TO_REASON_MAP[MFARequireType.PRACTITIONER]

        # check mfa for user
        user_mfa = self.get(user_id=user_id)
        if user_mfa is None or user_mfa.mfa_state != MFAState.ENABLED:
            return False, MFA_REQUIRED_TYPE_TO_REASON_MAP[MFARequireType.NOT_REQUIRED]
        else:
            return True, MFA_REQUIRED_TYPE_TO_REASON_MAP[MFARequireType.USER]


class UserMFAError(Exception):
    ...


class UserMFAConfigurationError(UserMFAError):
    ...


class UserMFAVerificationError(UserMFAError):
    ...


class UserMFARateLimitError(UserMFAError):
    ...


class UserMFAIntegrationError(UserMFAError):
    ...
