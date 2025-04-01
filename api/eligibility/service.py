from __future__ import annotations

import datetime
import hashlib
import uuid
import warnings
from traceback import format_exc
from typing import Any, Dict, List, Optional, Set, Tuple, TypedDict

import ddtrace
import grpc
import sqlalchemy.exc
import sqlalchemy.orm.scoping

from authn.domain import model as authn_model
from authn.domain import service as authn
from authn.models.user import User
from caching.redis import RedisTTLCache
from common import stats
from eligibility import EnterpriseEligibilitySettings, repository
from eligibility.e9y import EligibilityMember
from eligibility.e9y import grpc_service as e9y_service_util
from eligibility.e9y import model
from eligibility.repository import EmployeeInfo, OrgIdentity
from eligibility.utils import verification_utils
from eligibility.utils.e9y_test_utils import is_non_prod
from eligibility.utils.verification_utils import (
    VerificationType,
    VerificationTypeT,
    _translate_verification_type,
    valid_v2_verification_types,
)
from health.models.health_profile import HealthProfile
from models import enterprise
from models.enterprise import OrganizationEligibilityType, OrganizationEmployee
from models.tracks import lifecycle
from models.tracks.member_track import ChangeReason
from models.tracks.track import TrackName
from storage.connection import db
from tasks import braze
from tasks.enterprise import enterprise_user_post_setup
from utils import log as logging

__all__ = (
    "EnterpriseVerificationService",
    "EnterpriseVerificationQueryError",
    "EnterpriseVerificationFailedError",
    "EnterpriseVerificationError",
    "EligibilityTestMemberCreationError",
    "get_verification_service",
    "_empty_or_equal",
)

logger = logging.logger(__name__)


def get_verification_service() -> EnterpriseVerificationService:
    return EnterpriseVerificationService()


class EnterpriseVerificationService:
    """Core business logic for running enterprise member verification."""

    __slots__ = (
        "session",
        "employees",
        "user_org_employees",
        "wallet",
        "orgs",
        "sso",
        "e9y",
        "features",
        "org_id_cache",
    )

    def __init__(
        self,
        *,
        session: sqlalchemy.orm.scoping.ScopedSession | None = None,
        employees: repository.OrganizationEmployeeRepository | None = None,
        user_org_employees: repository.UserOrganizationEmployeeRepository | None = None,
        members: repository.EligibilityMemberRepository | None = None,
        wallet: repository.WalletEnablementRepository | None = None,
        orgs: repository.OrganizationRepository | None = None,
        features: repository.FeatureEligibilityRepository | None = None,
        sso: authn.SSOService | None = None,
        org_id_cache: RedisTTLCache | None = None,
    ):
        self.session = session or db.session
        self.employees = employees or repository.OrganizationEmployeeRepository(
            session=self.session
        )
        self.user_org_employees = (
            user_org_employees
            or repository.UserOrganizationEmployeeRepository(session=self.session)
        )
        self.sso = sso or authn.SSOService(session=self.session)
        self.wallet = wallet or repository.WalletEnablementRepository()
        self.orgs = orgs or repository.OrganizationRepository(
            session=self.session, sso=self.sso
        )
        self.e9y = members or repository.EligibilityMemberRepository()
        self.features = features or repository.FeatureEligibilityRepository()
        self.org_id_cache = org_id_cache or RedisTTLCache(
            namespace="e9y_org_id",
            ttl_in_seconds=30 * 60,
            pod_name=stats.PodNames.ELIGIBILITY,
        )

    @ddtrace.tracer.wrap()
    def get_eligibility_record_by_member_id(
        self, *, member_id: int
    ) -> model.EligibilityMember | None:
        """Return the eligibility member_versioned record for a given ID"""
        metadata = e9y_service_util.get_trace_metadata()
        return self.e9y.get_by_member_id(member_id=member_id, metadata=metadata)

    def _build_additional_fields(
        self,
        *,
        is_employee: bool | None,
        dependent_date_of_birth: datetime.date | None,
        date_of_birth: datetime.date | None,
        verification_creator: str | None,
        zendesk_id: str | None,
        employee_first_name: str | None,
        employee_last_name: str | None,
    ) -> Dict[str, Any]:
        additional_fields: Dict[str, Any] = {}
        if is_employee:
            additional_fields["is_employee"] = is_employee
        if dependent_date_of_birth:
            additional_fields["dependent_date_of_birth"] = str(dependent_date_of_birth)
        if date_of_birth:
            additional_fields["date_of_birth"] = str(date_of_birth)
        if verification_creator:
            additional_fields["verification_creator"] = verification_creator
        if zendesk_id:
            additional_fields["zendesk_id"] = zendesk_id
        if employee_first_name:
            additional_fields["employee_first_name"] = employee_first_name
        if employee_last_name:
            additional_fields["employee_last_name"] = employee_last_name
        return additional_fields

    @ddtrace.tracer.wrap()
    def get_enterprise_association(  # noqa: C901
        self,
        *,
        user_id: int,
        verification_type: Optional[VerificationTypeT] = "lookup",
        # Standard/Alternate/Client-specific Required.
        date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "date_of_birth" (default has type "None", argument has type "date")
        # Standard Verification only
        company_email: str = None,  # type: ignore[assignment] # Incompatible default for argument "company_email" (default has type "None", argument has type "str")
        # Alternate Verification only
        first_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "first_name" (default has type "None", argument has type "str")
        last_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "last_name" (default has type "None", argument has type "str")
        work_state: str = None,  # type: ignore[assignment] # Incompatible default for argument "work_state" (default has type "None", argument has type "str")
        # Alternate/Client-specific
        unique_corp_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "unique_corp_id" (default has type "None", argument has type "str")
        # Client-specific Required.
        organization_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "organization_id" (default has type "None", argument has type "int")
        is_employee: bool = None,  # type: ignore[assignment] # Incompatible default for argument "is_employee" (default has type "None", argument has type "bool")
        # Can be optionally provided by Standard/Alternate/Client-specific.
        dependent_date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "dependent_date_of_birth" (default has type "None", argument has type "date")
        # Can be provided to short-circuit and look up the e9y member directly.
        eligibility_member_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "eligibility_member_id" (default has type "None", argument has type "int")
        verification_creator: str = None,  # type: ignore[assignment] # Incompatible default for argument "verification_creator" (default has type "None", argument has type "str")
        zendesk_id: str | None = None,
        employee_first_name: str | None = None,
        employee_last_name: str | None = None,
        verification_type_v2: str | None = None,
    ) -> model.EligibilityVerification:
        """
        Attempt to verify a member is eligible for Maven-this method will search the e9y database for an eligible member who matches the information entered.
        If found, it will create a record of this verification in the e9y DB for future reference, and associate that user with the e9y record used to verify them.


        ****Please note* We will attempt to find a verification for a user before we create a new one. If we *do* find a verification for a user (and we return it)
        it does *NOT* mean the verification is active- to determine if the verification is still active (i.e. the user still has eligibility with that verification),
        the effective_range field on the verification must be used and confirmed to not have expired
        See also - is_verification_active and check_if_user_has_existing_eligibility
        *****


        :param user_id: Required. Maven UserID associated with a user
        :param verification_type: Optional: The verification flow for a user - guides what fields we use to try and verify eligibility. Defaults to 'Lookup'
        :param date_of_birth: Optional: User's DOB. Defaults to None
        :param company_email: Optional: Email a user entered to verify with. Defaults to None
        :param first_name: Optional: First name a user entered to verify with. Defaults to None
        :param last_name: Optional: Last name a user entered to verify with. Defaults to None
        :param work_state: Optional: State a user entered to verify with. Defaults to None
        :param unique_corp_id: Optional: Unique identifier a user entered to verify with. Defaults to None
        :param organization_id: Optional: Organization a user identifies themselves as being associated with. Defaults to None
        :param is_employee: Optional: Whether a user is an employee or dependent. Defaults to None
        :param dependent_date_of_birth: Optional: Date of birth of the dependent trying to verify. Defaults to None
        :param eligibility_member_id: Optional: If a member previously had verified, the e9y ID they were associated with. Defaults to None
        :param employee_first_name: employee's first name. Defaults to None
        :param employee_last_name: employee's last name.Defaults to None
        :param verification_type_v2: Optional: Identifier to run simplified verification flow
        :return: Eligibility Verification.

        """

        # Try to pre-validate the verification-type,
        #   this will short-circuit for certain cases.
        verification_type_is_validated = self.validate_verification_type(
            organization_id=organization_id,
            company_email=company_email,
            verification_type=verification_type,  # type: ignore[arg-type] # Argument "verification_type" to "validate_verification_type" of "EnterpriseVerificationService" has incompatible type "Optional[Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]]"; expected "Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]"
        )
        metadata = e9y_service_util.get_trace_metadata()

        # Attempt to find existing verification for user
        verification: model.EligibilityVerification | None = (
            self.e9y.get_verification_for_user(user_id=user_id, metadata=metadata)
        )

        existing_associations: List[
            OrganizationEmployee
        ] = self.employees.get_by_user_id(user_id=user_id)

        if verification_type == "lookup" and not eligibility_member_id:
            if not verification:
                raise EnterpriseVerificationFailedError(
                    f"User {user_id} is not associated to an enterprise member.",
                    verification_type=verification_type,
                )

            logger.info(
                "Existing verification found for user",
                user_id=user_id,
                request_verification_type=verification_type,
                verification_type=verification.verification_type,
                verification_org_id=verification.organization_id,
                association_org_ids=[a.organization_id for a in existing_associations],
            )
            # Return only latest OE for now.
            # Once we integrated the e9y GetAllVerificationsForUser api, we can return List[Tuple[model.EligibilityVerification, OrganizationEmployee]]
            return verification

        # Pre-fetch any external identites,
        #   we can use these for SSO-based verification,
        #   regardless of the reported verification type.
        identity_pair = self.orgs.get_organization_by_user_external_identities(
            user_id=user_id
        )

        # region: verification
        member = None

        # Short-circuit all checks and lookup the member directly IF...
        #   1. We were given a member ID
        #   2. We located identities
        if eligibility_member_id is not None:
            # Short-circuit verification-type validation for a direct lookup.
            verification_type_is_validated = True
            member = self.e9y.get_by_member_id(
                member_id=eligibility_member_id, metadata=metadata
            )
        elif identity_pair != (None, None):
            member = self.verify_member_sso(
                user_id=user_id, identity_pair=identity_pair
            )

        # If we still haven't found a member,
        # run through the omnibus verification logic.
        if member is None:
            members = self.run_verification_for_user(
                user_id=user_id,
                verification_type=verification_type,  # type: ignore[arg-type] # Argument "verification_type" to "run_verification_for_user" of "EnterpriseVerificationService" has incompatible type "Optional[Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]]"; expected "Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]"
                date_of_birth=date_of_birth,
                company_email=company_email,
                first_name=first_name,
                last_name=last_name,
                work_state=work_state,
                unique_corp_id=unique_corp_id,
                organization_id=organization_id,
                is_employee=is_employee,
                dependent_date_of_birth=dependent_date_of_birth,
                employee_first_name=employee_first_name,
                employee_last_name=employee_last_name,
                verification_type_v2=verification_type_v2,
            )
            member = members[0] if members else None
        # endregion

        # region: member validation
        # At this point, we *must* have located an e9y member, otherwise it's an error.

        # format a dict of verification params to pass along
        additional_fields: Dict[str, Any] = self._build_additional_fields(
            is_employee=is_employee,
            dependent_date_of_birth=dependent_date_of_birth,
            date_of_birth=date_of_birth,
            verification_creator=verification_creator,
            zendesk_id=zendesk_id,
            employee_first_name=employee_first_name,
            employee_last_name=employee_last_name,
        )

        if member is None:
            logger.info(
                "No e9y member found- failed verification",
                user_id=user_id,
                organization_id=organization_id,
                verification_type=verification_type,
            )

            self.generate_failed_verification_attempt_for_user(
                user_id=user_id,
                verification_type=verification_type,
                organization_id=organization_id,
                unique_corp_id=unique_corp_id,
                first_name=first_name,
                last_name=last_name,
                email=company_email,
                work_state=work_state,
                date_of_birth=date_of_birth,
                eligibility_member_id=eligibility_member_id,
                policy_used=None,
                additional_fields=additional_fields,
            )

            raise EnterpriseVerificationFailedError(
                f"No enterprise member record could be found for User {user_id}",
                verification_type=verification_type,  # type: ignore[arg-type] # Argument "verification_type" to "EnterpriseVerificationFailedError" has incompatible type "Optional[Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]]"; expected "str"
            )

        # If we didn't pre-validate, try again now.
        if verification_type_is_validated is False:
            self.validate_verification_type(
                organization_id=member.organization_id,
                verification_type=verification_type,  # type: ignore[arg-type] # Argument "verification_type" to "validate_verification_type" of "EnterpriseVerificationService" has incompatible type "Optional[Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]]"; expected "Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]"
            )
        # endregion

        # We will create a new verification under these circumstances
        # 1. no existing verification found
        # 2. existing verification's org does not match the newly fetched record's org
        if not verification or verification.organization_id != member.organization_id:
            verification = self.generate_verification_for_user(
                user_id=user_id,
                verification_type=verification_type,
                organization_id=member.organization_id,
                unique_corp_id=member.unique_corp_id,
                date_of_birth=member.date_of_birth,
                first_name=first_name,
                last_name=last_name,
                email=company_email,
                work_state=work_state,
                eligibility_member_id=member.id,
                additional_fields=additional_fields,
                verification_session=uuid.uuid4().hex,
            )
            if verification_utils.no_oe_creation_enabled():
                logger.info(
                    "No OE creation enabled, skipping OE creation", user_id=user_id
                )
            else:
                # Associate the user to this member record.
                self.associate_user_id_to_members(
                    user_id=user_id,
                    members=[member],
                    verification_type=verification_type,
                )

            logger.info(
                "Verification succeeded",
                user_id=user_id,
                verification_type=verification_type,
                verification_org_id=(
                    verification.organization_id if verification is not None else ""
                ),
                verification_id=(
                    verification.verification_id if verification is not None else ""
                ),
                eligibility_member_id=member.id,
            )
        else:
            # If the following condition is met
            # 1. Verification exists
            # 2. Verification is for the same org as the member found

            # Create the OE/UOE in case, so verification and OE/UOE has same data
            if verification_utils.no_oe_creation_enabled():
                logger.info(
                    "No OE creation enabled, skipping OE creation", user_id=user_id
                )
            else:
                self.associate_user_id_to_members(
                    user_id=user_id,
                    members=[member],
                    verification_type=verification_type,
                )

            logger.info(
                "Existing verification found for org that user is attempting to verify against",
                user_id=user_id,
                verification_type=verification_type,
            )

        # endregion
        return verification  # type: ignore[return-value]

    @ddtrace.tracer.wrap()
    def get_enterprise_associations(  # noqa: C901
        self,
        *,
        user_id: int,
        verification_type: Optional[VerificationTypeT] = "lookup",
        # Standard/Alternate/Client-specific Required.
        date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "date_of_birth" (default has type "None", argument has type "date")
        # Standard Verification only
        company_email: str = None,  # type: ignore[assignment] # Incompatible default for argument "company_email" (default has type "None", argument has type "str")
        # Alternate Verification only
        first_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "first_name" (default has type "None", argument has type "str")
        last_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "last_name" (default has type "None", argument has type "str")
        work_state: str = None,  # type: ignore[assignment] # Incompatible default for argument "work_state" (default has type "None", argument has type "str")
        # Alternate/Client-specific
        unique_corp_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "unique_corp_id" (default has type "None", argument has type "str")
        # Client-specific Required.
        organization_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "organization_id" (default has type "None", argument has type "int")
        is_employee: bool = None,  # type: ignore[assignment] # Incompatible default for argument "is_employee" (default has type "None", argument has type "bool")
        # Can be optionally provided by Standard/Alternate/Client-specific.
        dependent_date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "dependent_date_of_birth" (default has type "None", argument has type "date")
        # Can be provided to short-circuit and look up the e9y member directly.
        eligibility_member_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "eligibility_member_id" (default has type "None", argument has type "int")
        verification_creator: str = None,  # type: ignore[assignment] # Incompatible default for argument "verification_creator" (default has type "None", argument has type "str")
        zendesk_id: str | None = None,
        employee_first_name: str | None = None,
        employee_last_name: str | None = None,
        verification_type_v2: str | None = None,
    ) -> List[model.EligibilityVerification]:

        # Validate verification type before proceeding
        # this will short-circuit for certain cases.
        verification_type_is_validated = self.validate_verification_type(
            organization_id=organization_id,
            company_email=company_email,
            verification_type=verification_type,  # type: ignore[arg-type] # Argument "verification_type" to "run_verification_for_user" of "EnterpriseVerificationService" has incompatible type "Optional[Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]]"; expected "Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]"
        )

        metadata = e9y_service_util.get_trace_metadata()

        # Get all existing verifications and associations for the user
        existing_verifications = self.e9y.get_all_verifications_for_user(
            user_id=user_id,
            metadata=metadata,
            active_verifications_only=True,
            organization_ids=[organization_id] if organization_id is not None else [],
        )
        existing_associations = self.employees.get_by_user_id(user_id=user_id)

        if verification_type == "lookup" and not eligibility_member_id:
            if not existing_verifications:
                raise EnterpriseVerificationFailedError(
                    f"User {user_id} is not associated to an enterprise member.",
                    verification_type=verification_type,
                )

            logger.info(
                "Existing verification(s) found for user",
                user_id=user_id,
                request_verification_type=verification_type,
                verification_types=set(
                    v.verification_type for v in existing_verifications
                ),
                verification_org_ids=set(
                    v.organization_id for v in existing_verifications
                ),
                association_org_ids=set(
                    a.organization_id for a in existing_associations
                ),
            )
            return existing_verifications

        # Pre-fetch any external identites,
        #   we can use these for SSO-based verification,
        #   regardless of the reported verification type.
        identity_pair = self.orgs.get_organization_by_user_external_identities(
            user_id=user_id
        )

        # region: verification
        members = []

        # Short-circuit all checks and lookup the member directly IF...
        #   1. We were given a member ID
        #   2. We located identities
        if eligibility_member_id is not None:
            # Short-circuit verification-type validation for a direct lookup.
            verification_type_is_validated = True
            member = self.e9y.get_by_member_id(
                member_id=eligibility_member_id, metadata=metadata
            )
            if member:
                members.append(member)

        elif identity_pair != (None, None):
            member = self.verify_member_sso(
                user_id=user_id, identity_pair=identity_pair
            )
            if member:
                members.append(member)

        # If we still haven't found a member,
        # run through the omnibus verification logic.
        if not members:
            members = self.run_verification_for_user(
                user_id=user_id,
                verification_type=verification_type,  # type: ignore[arg-type] # Argument "verification_type" to "run_verification_for_user" of "EnterpriseVerificationService" has incompatible type "Optional[Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]]"; expected "Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]"
                date_of_birth=date_of_birth,
                company_email=company_email,
                first_name=first_name,
                last_name=last_name,
                work_state=work_state,
                unique_corp_id=unique_corp_id,
                organization_id=organization_id,
                is_employee=is_employee,
                dependent_date_of_birth=dependent_date_of_birth,
                employee_first_name=employee_first_name,
                employee_last_name=employee_last_name,
                verification_type_v2=verification_type_v2,
            )
            # endregion

        # region: member validation
        # At this point, we *must* have located an e9y member, otherwise it's an error.

        # format a dict of verification params to pass along
        additional_fields: Dict[str, Any] = self._build_additional_fields(
            is_employee=is_employee,
            dependent_date_of_birth=dependent_date_of_birth,
            date_of_birth=date_of_birth,
            verification_creator=verification_creator,
            zendesk_id=zendesk_id,
            employee_first_name=employee_first_name,
            employee_last_name=employee_last_name,
        )

        if not members:
            logger.info(
                "No e9y member found- failed verification",
                user_id=user_id,
                organization_id=organization_id,
                verification_type=verification_type,
            )

            self.generate_failed_verification_attempt_for_user(
                user_id=user_id,
                verification_type=verification_type,
                organization_id=organization_id,
                unique_corp_id=unique_corp_id,
                first_name=first_name,
                last_name=last_name,
                email=company_email,
                work_state=work_state,
                date_of_birth=date_of_birth,
                eligibility_member_id=eligibility_member_id,
                policy_used=None,
                additional_fields=additional_fields,
            )

            raise EnterpriseVerificationFailedError(
                f"No enterprise member record could be found for User {user_id}",
                verification_type=verification_type,  # type: ignore[arg-type] # Argument "verification_type" to "EnterpriseVerificationFailedError" has incompatible type "Optional[Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]]"; expected "str"
            )

        # Validate and filter member records if verification type was not pre-validated
        if verification_type_is_validated is False:
            members = self.validate_verification_type_for_multiple_member_records(
                member_records=members,
                verification_type=verification_type,  # type: ignore[arg-type] # Argument "verification_type" to "run_verification_for_user" of "EnterpriseVerificationService" has incompatible type "Optional[Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]]"; expected "Literal[`standard`, `alternate`, `client_specific`, `multistep`, `fileless`, `lookup`, `sso`]"
            )
        # endregion

        # We will create a new verification under these circumstances
        # 1. no existing verification found
        # 2. existing verification's org does not match the newly fetched record's org
        new_verifications = []
        verification_org_set = {v.organization_id for v in existing_verifications}
        member_org_set = {m.organization_id for m in members}
        if verification_org_set != member_org_set:
            new_members = [
                member
                for member in members
                if member.organization_id not in verification_org_set
            ]
            if len(new_members) > 0:
                # date_of_birth is expected to be same across all member records
                date_of_birth = new_members[0].date_of_birth

                new_verifications = self.create_verifications(
                    user_id=user_id,
                    members=new_members,
                    verification_type=verification_type,
                    date_of_birth=date_of_birth,
                    additional_fields=additional_fields,
                )

                logger.info(
                    "Verification succeeded",
                    extra={
                        "user_id": user_id,
                        "verification_type": verification_type,
                        "verification_org_ids": {
                            v.organization_id for v in new_verifications
                        },
                        "eligibility_member_ids": {m.id for m in new_members},
                    },
                )

        # If the following condition is met
        # 1. Verification exists
        # 2. Verification is for the same org as the member found

        if verification_utils.no_oe_creation_enabled():
            logger.info("No OE creation enabled, skipping OE creation", user_id=user_id)
        else:
            # Create the OE/UOE in case, so verification and OE/UOE has same data
            self.associate_user_id_to_members(
                user_id=user_id,
                members=members,
                verification_type=verification_type,
            )

        logger.info(
            "Existing verification(s) found for org(s) that user is attempting to verify against",
            user_id=user_id,
            verification_type=verification_type,
        )

        # endregion
        return existing_verifications + new_verifications

    def create_verifications(
        self,
        user_id: int,
        members: List[model.EligibilityMember],
        verification_type: Optional[VerificationTypeT] = None,
        date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "date_of_birth" (default has type "None", argument has type "date")
        additional_fields: dict | None = None,
    ) -> List[model.EligibilityVerification]:
        if additional_fields is None:
            additional_fields = {}

        verifications = []

        try:
            # Create verifications for the user
            verifications = self.generate_multiple_verifications_for_user(
                user_id=user_id,
                verification_type=verification_type or "lookup",  # Use fallback value
                date_of_birth=date_of_birth,
                members=members,
                additional_fields=additional_fields,
                verification_session=uuid.uuid4().hex,
                verification_data_list=None,
            )

        except EnterpriseVerificationCreationError as e:
            logger.error(
                "Verifications could not be created",
                error=e.args[0],
                user_id=e.user_id,
                verification_type=e.verification_type,
                eligibility_member_ids=e.eligibility_member_ids,
                details=e.details,
            )
            raise

        return verifications

    @staticmethod
    def match_verifications_to_associations(
        verifications: List[model.EligibilityVerification],
        existing_associations: List[OrganizationEmployee],
    ) -> List[
        Tuple[Optional[model.EligibilityVerification], Optional[OrganizationEmployee]]
    ]:
        matched_pairs: List[
            Tuple[
                Optional[model.EligibilityVerification], Optional[OrganizationEmployee]
            ]
        ] = []

        # Create a dictionary for fast lookups for associations by organization_id
        association_dict = {
            association.organization_id: association
            for association in existing_associations
        }

        # Keep track of associations that have been matched
        matched_association_ids = set()

        # Match verifications to associations
        for verification in verifications:
            if verification.organization_id in association_dict:
                matched_pairs.append(
                    (verification, association_dict[verification.organization_id])
                )
                matched_association_ids.add(verification.organization_id)
            else:
                matched_pairs.append((verification, None))

        # Add associations that didn't match any verifications
        for association in existing_associations:
            if association.organization_id not in matched_association_ids:
                matched_pairs.append((None, association))

        return matched_pairs

    def validate_verification_type(
        self,
        *,
        organization_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "organization_id" (default has type "None", argument has type "int")
        company_email: str = None,  # type: ignore[assignment] # Incompatible default for argument "company_email" (default has type "None", argument has type "str")
        verification_type: VerificationTypeT,
    ) -> bool:
        """Double-check the verification type and org config (if it can be found).

        - Will raise an EnterpriseVerificationConfigurationError if invalid.
        - If returns True, we found the org's eligibility settings
          and the verification-type is compatible.
        - If False, we couldn't find the org's eligibility settings.
          (This can happen if both values are null, or we only had the company_email
          and the org doesn't have an email-domain associated.)
        """
        # Don't run verification validation for lookups.
        if verification_type == "lookup":
            return False

        # Nothing to be done, short-circuit.
        if (organization_id, company_email) == (None, None):
            return False

        settings = None
        if organization_id is not None:
            settings = self.orgs.get_eligibility_settings(
                organization_id=organization_id
            )
        elif company_email is not None:
            settings = self.orgs.get_eligibility_settings_by_email(
                company_email=company_email
            )

        # Nothing to be done, short-circuit.
        if settings is None:
            return False

        # Make sure the org's configured eligibility type
        #   is compatible with the declared verification type.
        org_verification_type = get_verification_type_from_eligibility_type(
            settings.eligibility_type
        )
        if (
            org_verification_type in ("fileless", "client_specific")
            and verification_type != org_verification_type
        ):
            raise EnterpriseVerificationConfigurationError(
                "The indicated email is associated to an organization "
                "which is incompatible with the given verification type.",
                verification_type=verification_type,
                settings=settings,
            )
        return True

    def validate_verification_type_for_multiple_member_records(
        self,
        *,
        member_records: List[model.EligibilityMember],
        company_email: str = None,  # type: ignore[assignment] # Incompatible default for argument "company_email" (default has type "None", argument has type "str")
        verification_type: VerificationTypeT,
    ) -> List[model.EligibilityMember]:
        """Double-check the verification type and org config (if it can be found).

        - Will return results where the the org's eligibility settings
          and the verification-type is compatible.
        - If no values returned, we couldn't find the org's eligibility settings.
          (This can happen if both values are null, or we only had the company_email
          and the org doesn't have an email-domain associated.)
        """
        # Don't run verification validation for lookups.
        if verification_type == "lookup":
            return member_records

        # Nothing to be done, short-circuit.
        if (member_records, company_email) == ([], None):
            return member_records

        settings = None

        returned_member_records = []

        for m in member_records:

            if m.organization_id is not None:
                settings = self.orgs.get_eligibility_settings(
                    organization_id=m.organization_id
                )
            elif company_email is not None:
                settings = self.orgs.get_eligibility_settings_by_email(
                    company_email=company_email
                )

            if settings:
                # Make sure the org's configured eligibility type
                #   is compatible with the declared verification type.
                org_verification_type = get_verification_type_from_eligibility_type(
                    settings.eligibility_type
                )

                if (
                    org_verification_type
                    in (
                        OrganizationEligibilityType.FILELESS,
                        OrganizationEligibilityType.CLIENT_SPECIFIC,
                    )
                    and verification_type != org_verification_type
                ):
                    continue

            returned_member_records.append(m)

        return returned_member_records

    def run_verification_for_user(
        self,
        *,
        user_id: int,
        verification_type: VerificationTypeT = "lookup",
        # Standard/Alternate/Client-specific Required.
        date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "date_of_birth" (default has type "None", argument has type "date")
        # Standard Verification only
        company_email: str = None,  # type: ignore[assignment] # Incompatible default for argument "company_email" (default has type "None", argument has type "str")
        # Alternate Verification only
        first_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "first_name" (default has type "None", argument has type "str")
        last_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "last_name" (default has type "None", argument has type "str")
        work_state: str = None,  # type: ignore[assignment] # Incompatible default for argument "work_state" (default has type "None", argument has type "str")
        # Alternate/Client-specific
        unique_corp_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "unique_corp_id" (default has type "None", argument has type "str")
        # Client-specific Required.
        organization_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "organization_id" (default has type "None", argument has type "int")
        is_employee: bool = None,  # type: ignore[assignment] # Incompatible default for argument "is_employee" (default has type "None", argument has type "bool")
        # Can be optionally provided by Standard/Alternate/Client-specific.
        dependent_date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "dependent_date_of_birth" (default has type "None", argument has type "date")
        employee_first_name: str | None = None,
        employee_last_name: str | None = None,
        verification_type_v2: str | None = None,
    ) -> List[model.EligibilityMember]:
        """
        Attempt to look up the associated E9y record for a Maven member, given set of identifying information.
        This will search the E9y DB for an 'active' record for a user- one which matches the identifiers, but also
        is considered actively eligible for Maven i.e. belonging to an organization that is activated, and whose organization
        says they currently have access to maven.

        Input:

        :param user_id: Required. Maven UserID associated with a user
        :param verification_type: Optional: The verification flow for a user. Defaults to 'Lookup'
        :param date_of_birth: Optional: User's DOB. Defaults to None
        :param company_email: Optional: Email a user entered to verify with. Defaults to None
        :param first_name: Optional: First name a user entered to verify with. Defaults to None
        :param last_name: Optional: Last name a user entered to verify with. Defaults to None
        :param work_state: Optional: State a user entered to verify with. Defaults to None
        :param unique_corp_id: Optional: Unique identifier a user entered to verify with. Defaults to None
        :param organization_id: Optional: Organization a user identifies themselves as being associated with. Defaults to None
        :param is_employee: Optional: Whether a user is an employee or dependent. Defaults to None
        :param dependent_date_of_birth: Optional: Date of birth of the dependent trying to verify. Defaults to None
        employee fn/ln not same as users fn/ln in case of partner enrollment.
        :param employee_first_name: employee's first name. Defaults to None
        :param employee_last_name: employee's last name.Defaults to None
        :param verification_type_v2: Optional: Simplified flow to run
        :return: If member is eligible for Maven, EligibilityMember record. If not eligible, Null
        """
        # region parameter validation
        params = verification_utils.VerificationParams(
            user_id=user_id,
            organization_id=organization_id,
            is_employee=is_employee,
            date_of_birth=date_of_birth,
            dependent_date_of_birth=dependent_date_of_birth,
            company_email=company_email,
            first_name=first_name,
            last_name=last_name,
            work_state=work_state,
            unique_corp_id=unique_corp_id,
            employee_first_name=employee_first_name,
            employee_last_name=employee_last_name,
            verification_type=verification_type,
            verification_type_v2=verification_type_v2,
        )
        # endregion

        # handle client_specific and sso, prefer earlier return
        if verification_type in {"client_specific", "sso"}:
            return self._run_external_verification(
                verification_type=verification_type,
                user_id=user_id,
                dependent_date_of_birth=dependent_date_of_birth,
                params=params,
            )

        members = self.run_verification_by_verification_type(
            params=params,
        )

        if members:
            return members

        return self._run_additional_verification(
            verification_type=verification_type,
            user_id=user_id,
            dependent_date_of_birth=dependent_date_of_birth,
            params=params,
        )

    def run_verification_by_verification_type(
        self,
        params: verification_utils.VerificationParams,
    ) -> List[EligibilityMember]:
        """Run verification by verification type"""

        # remove temp log
        logger.info("default to _run_verification_by_verification_type_v2")

        verification_type_v2_str = params.verification_type_v2
        if params.has_verification_type_v2():
            logger.info(
                "evaluating verification type",
                extra={
                    "user_id": params.user_id,
                    "verification_type": params.verification_type,
                    "verification_type_v2": verification_type_v2_str,
                },
            )

            verification_type_v2 = _translate_verification_type(
                verification_type_v2_str  # type: ignore[arg-type] # Argument already validated
            )
            if verification_type_v2 in valid_v2_verification_types:
                return self._run_verification_by_verification_type_v2(
                    verification_type_v2_translated=verification_type_v2,
                    params=params,
                )
        return []

    def _run_verification_by_verification_type_v1(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        params: verification_utils.VerificationParams,
    ):
        warnings.warn(
            "_run_verification_by_verification_type_v1 is deprecated and will be removed in a future version. "
            "Please use _run_verification_by_verification_type_v2 instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        member = None

        logger.info(
            "running verification by verification_type v1",
            user_id=params.user_id,
            verification_type=params.verification_type,
        )

        # region standard verification
        # 'Standard' is the oldest flow on the books, with minimal PII.
        if params.verification_type == "standard":
            if (
                params.has_necessary_multistep_params() is False
                and params.has_necessary_params_for_no_dob_verification() is False
            ):
                raise EnterpriseVerificationQueryError(
                    f"Couldn't run verification for User {params.user_id}.",
                    verification_type=params.verification_type,
                    required_params=("date_of_birth", "company_email"),
                )
            if params.has_necessary_standard_params():
                member = self.verify_member_standard(
                    company_email=params.company_email,
                    date_of_birth=params.date_of_birth,
                    dependent_date_of_birth=params.dependent_date_of_birth,
                )

            # If we have the data we need to run alternate, give it a shot.
            if member is None and params.has_necessary_alternate_params():
                member = self.verify_member_alternate(
                    first_name=params.first_name,
                    last_name=params.last_name,
                    date_of_birth=params.date_of_birth,
                    dependent_date_of_birth=params.dependent_date_of_birth,
                    work_state=params.work_state,
                    unique_corp_id=params.unique_corp_id,
                )

        # endregion

        # region alternate verification
        # 'Alternate' is a more-robust, catch-all flow which handles a lot of PII.
        elif params.verification_type == "alternate":
            if (
                params.has_necessary_multistep_params() is False
                and params.has_necessary_params_for_no_dob_verification() is False
            ):
                raise EnterpriseVerificationQueryError(
                    f"Couldn't run verification for User {params.user_id}.",
                    verification_type=params.verification_type,
                    required_params=("date_of_birth", "first_name", "last_name"),
                )
            if params.has_necessary_alternate_params():
                # Will include at least fn, ln, dob
                member = self.verify_member_alternate(
                    first_name=params.first_name,
                    last_name=params.last_name,
                    date_of_birth=params.date_of_birth,
                    dependent_date_of_birth=params.dependent_date_of_birth,
                    work_state=params.work_state,
                    unique_corp_id=params.unique_corp_id,
                )

            # If we have the data we need for standard, give it a shot.
            if member is None and params.has_necessary_standard_params():
                # Check on DOB and Email Only
                member = self.verify_member_standard(
                    company_email=params.company_email,
                    date_of_birth=params.date_of_birth,
                    dependent_date_of_birth=params.dependent_date_of_birth,
                )
        # endregion

        # region multistep

        # 'Multi-step' is a specific flow introduced for health plans.
        #   It combines alternate and standard verification,
        #   with slightly different fallback logic than what we do above.
        elif params.verification_type == "multistep":
            if params.has_necessary_multistep_params() is False:
                raise EnterpriseVerificationQueryError(
                    f"Couldn't run verification for User {params.user_id}.",
                    verification_type=params.verification_type,
                    required_params=("date_of_birth",),
                )

            # Require at least (dob, email) or (dob, fn, ln)
            member = self.verify_member_multistep(
                date_of_birth=params.date_of_birth,
                company_email=params.company_email,
                first_name=params.first_name,
                last_name=params.last_name,
                work_state=params.work_state,
                unique_corp_id=params.unique_corp_id,
                dependent_date_of_birth=params.dependent_date_of_birth,
                user_id=params.user_id,
            )
        if member:
            return [member]
        return []

    def _run_verification_by_verification_type_v2(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        verification_type_v2_translated: VerificationType,
        params: verification_utils.VerificationParams,
    ) -> List[model.EligibilityMember]:

        logger.info(
            "running verification by verification_type v2",
            user_id=params.user_id,
            verification_type=params.verification_type_v2,
        )

        # Map verification type to verification method
        verification_methods = {
            VerificationType.BASIC: self.verify_member_basic,
            VerificationType.EMPLOYER: self.verify_member_employer,
            VerificationType.HEALTHPLAN: self.verify_member_healthplan,
            VerificationType.MULTISTEP: self.verify_member_multistep_v2,
        }

        verify_method = verification_methods.get(verification_type_v2_translated)
        # This is a guard rail check. We should fallback to v1 verification flows
        if not verify_method:
            logger.error(
                "Couldn't run verification for User due to unknown verification type",
                user_id=params.user_id,
                verification_type_v2=params.verification_type_v2,
            )
            raise EnterpriseVerificationQueryError(
                f"Couldn't run verification for User {params.user_id} due to unknown verification type",
                verification_type=params.verification_type_v2,  # type: ignore[arg-type] # value is printed if it exists
                required_params=("verification_type_v2",),
            )

        return verify_method(params=params)

    def _run_additional_verification(
        self,
        verification_type: VerificationTypeT,
        user_id: int,
        dependent_date_of_birth: datetime.date | None,
        params: verification_utils.VerificationParams,
    ) -> List[model.EligibilityMember]:
        if (
            verification_utils.is_over_eligibility_enabled()
            and params.has_necessary_params_for_overeligibility()
        ):
            logger.info(
                "Attempting to verify if member has overeligibility.",
                verification_type=verification_type,
            )
            members = self.verify_member_overeligibility(
                first_name=params.first_name,
                last_name=params.last_name,
                date_of_birth=params.date_of_birth,
                dependent_date_of_birth=dependent_date_of_birth,
                unique_corp_id=params.unique_corp_id,
                company_email=params.company_email,
                user_id=user_id,
            )
            if members and len(members) > 1:
                member_ids = {member.id for member in members}
                organization_ids = {member.organization_id for member in members}
                unique_corp_ids = {member.unique_corp_id for member in members}
                logger.info(
                    "Found member with overeligibility",
                    user_id=user_id,
                    organization_ids=organization_ids,
                    member_ids=member_ids,
                    unique_corp_ids=unique_corp_ids,
                )
            if members and len(members) > 0:
                return members

        return []

    def _run_external_verification(
        self,
        verification_type: VerificationTypeT,
        user_id: int,
        dependent_date_of_birth: datetime.date | None,
        params: verification_utils.VerificationParams,
    ) -> List[model.EligibilityMember]:
        # region client-specific
        # 'Client-specific' is a flow for custom client integrations.
        if verification_type == "client_specific":
            if not params.has_necessary_client_specific_params():
                raise EnterpriseVerificationQueryError(
                    f"Couldn't run verification for User {user_id}.",
                    verification_type=verification_type,
                    required_params=(
                        "date_of_birth",
                        "organization_id",
                        "unique_corp_id",
                    ),
                )
            member = self.verify_member_client_specific(
                organization_id=params.organization_id,
                unique_corp_id=params.unique_corp_id,
                is_employee=params.is_employee,
                date_of_birth=params.date_of_birth,
                dependent_date_of_birth=dependent_date_of_birth,
            )
            return [member] if member else []

        # endregion

        # region sso
        elif verification_type == "sso":
            member = self.verify_member_sso(user_id=user_id)
            return [member] if member else []
        return []
        # endregion

    @ddtrace.tracer.wrap()
    def generate_verification_for_user(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        *,
        user_id: int,
        verification_type: str,
        organization_id: int,
        unique_corp_id: str,
        date_of_birth: datetime.date | None = None,
        dependent_id: str | None = "",
        first_name: str | None = "",
        last_name: str | None = "",
        email: str | None = "",
        work_state: str | None = "",
        eligibility_member_id: int | None = None,
        additional_fields: dict | None = None,
        verification_session: str | None = None,
    ) -> model.EligibilityVerification | None:
        """
        After a user has verified they are eligible for Maven, generate a record in e9y containing the information they verified with.
        Ties a Maven user_id to an e9y memberID.

        :param user_id:  The Maven ID for the user who just verified
        :param verification_type: The method used to verify the user against e9y
        :param organization_id: The organization the user is associated with
        :param unique_corp_id:  Unique identifier provided by the employer to identify the Maven member
        :param date_of_birth: Optional. The date of birth a member used for verification. Defaults to None.
        :param dependent_id: Optional. Unique identifier for a dependent who verified eligibility. Defaults to None.
        :param first_name: Optional: First name a user entered to verify with. Defaults to None
        :param last_name: Optional: Last name a user entered to verify with. Defaults to None
        :param email:  Optional: Email a user entered to verify with. Defaults to None
        :param work_state: Optional: State a user entered to verify with. Defaults to None
        :param eligibility_member_id: Optional. The E9y member ID for the record we matched a user against for verification. Defaults to None.
        :param additional_fields: Optional. Dictionary capturing any non-standard fields used for verifying a user. Defaults to None.

        :return: model.EligibilityVerification | None
        """
        try:
            metadata = e9y_service_util.get_trace_metadata()
            verification = self.e9y.create_verification_for_user(
                user_id=user_id,
                verification_type=verification_type,
                date_of_birth=date_of_birth,  # type: ignore[arg-type] # Argument "date_of_birth" to "create_verification_for_user" of "EligibilityMemberRepository" has incompatible type "Optional[date]"; expected "date"
                email=email,
                first_name=first_name,
                last_name=last_name,
                work_state=work_state,
                unique_corp_id=unique_corp_id,
                dependent_id=dependent_id,
                organization_id=organization_id,
                additional_fields=additional_fields,
                eligibility_member_id=eligibility_member_id,
                verification_session=verification_session,
                metadata=metadata,
            )
            self.org_id_cache.add(user_id, [organization_id])

            logger.info(
                "Created verification record for user",
                user_id=user_id,
                organization_id=organization_id,
                verification_type=verification_type,
            )

            return verification
        except Exception as err:
            details = None
            if isinstance(err, grpc.RpcError):
                details = err.code()  # type: ignore[attr-defined] # "Exception" has no attribute "details"
            # Attempt to record the grpc details if it's populated
            raise EnterpriseVerificationCreationError(
                "Error creating verification for user",
                verification_type=verification_type,
                user_id=user_id,
                eligibility_member_id=eligibility_member_id,  # type: ignore[arg-type] # Argument "eligibility_member_id" to "EnterpriseVerificationCreationError" has incompatible type "Optional[int]"; expected "int"
                details=details or str(err),
            )
            return None

    @ddtrace.tracer.wrap()
    def generate_multiple_verifications_for_user(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        *,
        user_id: int,
        verification_type: str,
        members: Optional[List[model.EligibilityMember]],
        verification_data_list: Optional[List[model.VerificationData]],
        date_of_birth: datetime.date | None = None,
        first_name: str | None = "",
        last_name: str | None = "",
        additional_fields: dict | None = None,
        verification_session: str | None = None,
    ) -> List[model.EligibilityVerification]:
        """
        If a user has verified they are eligible for Maven and is eligible via multiple organizations,
        generate a record each in e9y containing the information they verified with.
        Ties a Maven user_id to an e9y memberID.

        :param user_id:
        :param verification_type:
        :param members:
        :verification_data_list:
        :param date_of_birth:
        :param first_name:
        :param last_name:
        :param additional_fields:
        :param verification_session:
        :return: List[model.EligibilityVerification] | None
        """

        if verification_data_list and len(verification_data_list) > 0:
            eligibility_member_ids = [
                v.eligibility_member_id for v in verification_data_list
            ]
            organization_ids = [v.organization_id for v in verification_data_list]
        elif members and len(members) > 0:
            organization_ids = [m.organization_id for m in members]
            eligibility_member_ids = [m.id for m in members]

        try:

            metadata = e9y_service_util.get_trace_metadata()
            verifications = self.e9y.create_multiple_verifications_for_user(
                user_id=user_id,
                verification_type=verification_type,
                date_of_birth=date_of_birth,  # type: ignore[arg-type] # Argument "date_of_birth" to "create_verification_for_user" of "EligibilityMemberRepository" has incompatible type "Optional[date]"; expected "date"
                members=members,
                first_name=first_name,
                last_name=last_name,
                additional_fields=additional_fields,
                verification_session=verification_session,
                metadata=metadata,
                verification_data_list=verification_data_list,
            )

            self.org_id_cache.add(user_id, organization_ids)

            logger.info(
                "Created multiple verification records for user",
                user_id=user_id,
                organization_ids=organization_ids,
                verification_type=verification_type,
                eligibility_member_ids=eligibility_member_ids,
            )

            return verifications
        except Exception as err:
            details = None
            if isinstance(err, grpc.RpcError):
                details = err.code()  # type: ignore[attr-defined] # "Exception" has no attribute "details"
            # Attempt to record the grpc details if it's populated
            raise EnterpriseVerificationCreationError(
                "Error creating multiple verifications for user",
                verification_type=verification_type,
                user_id=user_id,
                eligibility_member_ids=eligibility_member_ids,  # type: ignore[arg-type] # Argument "eligibility_member_id" to "EnterpriseVerificationCreationError" has incompatible type "Optional[int]"; expected "int"
                details=details or str(err),
            )
            return []

    @ddtrace.tracer.wrap()
    def generate_failed_verification_attempt_for_user(
        self,
        *,
        user_id: int,
        verification_type: str,
        organization_id: int,
        unique_corp_id: str,
        date_of_birth: datetime.date,
        dependent_id: str | None = "",
        first_name: str | None = "",
        last_name: str | None = "",
        email: str | None = "",
        work_state: str | None = "",
        eligibility_member_id: int | None = None,
        additional_fields: dict | None = None,
        policy_used: str | None = None,
    ) -> model.EligibilityVerificationAttempt | None:
        """
        Create a record of a 'failed verification' attempt- if a user requests to verify against e9y, but we do not have a result for them,
        create a failed verification record for future tracking

        :param user_id:  The Maven ID for the user who just verified
        :param verification_type: The method used to verify the user against e9y
        :param organization_id: The organization the user is associated with
        :param unique_corp_id:  Unique identifier provided by the employer to identify the Maven member
        :param date_of_birth: Optional. The date of birth a member used for verification. Defaults to None.
        :param dependent_id: Optional. Unique identifier for a dependent who verified eligibility. Defaults to None.
        :param first_name: Optional: First name a user entered to verify with. Defaults to None
        :param last_name: Optional: Last name a user entered to verify with. Defaults to None
        :param email:  Optional: Email a user entered to verify with. Defaults to None
        :param work_state: Optional: State a user entered to verify with. Defaults to None
        :param eligibility_member_id: Optional. The E9y member ID for the record we matched a user against for verification. Defaults to None.
        :param additional_fields: Optional. Dictionary capturing any non-standard fields used for verifying a user. Defaults to None.

        :return model.EligibilityVerificationAttempt | None
        """

        try:
            metadata = e9y_service_util.get_trace_metadata()
            verification_attempt = self.e9y.create_failed_verification_attempt_for_user(
                user_id=user_id,
                verification_type=verification_type,
                organization_id=organization_id,
                unique_corp_id=unique_corp_id,
                date_of_birth=date_of_birth,
                dependent_id=dependent_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                work_state=work_state,
                eligibility_member_id=eligibility_member_id,
                additional_fields=additional_fields,
                policy_used=policy_used,
                metadata=metadata,
            )

            logger.info(
                "Created failed verification attempt record for user",
                user_id=user_id,
                organization_id=organization_id,
                verification_type=verification_type,
            )

            return verification_attempt
        except Exception as e:
            logger.error(
                "Error creating failed verification attempt record for user",
                user_id=user_id,
                organization_id=organization_id,
                error=e,
            )
            return None

    @ddtrace.tracer.wrap()
    def deactivate_verification_for_user(
        self, *, user_id: int, verification_id: int
    ) -> int:
        """
        Taking in a user ID and verification ID, deactivate the verification for a user
        Returns 1 for successful deactivation, -1 if there was an error during deactivation

        """

        try:
            deactivation_success = self.e9y.deactivate_verification_for_user(
                user_id=user_id, verification_id=verification_id
            )

        except Exception as err:
            logger.error(
                "Error deactivating verification for user",
                user_id=user_id,
                verification_id=verification_id,
                error=err,
            )

        return deactivation_success

    @ddtrace.tracer.wrap()
    def associate_user_id_to_members(
        self,
        *,
        user_id: int,
        members: List[model.EligibilityMember],
        verification_type: VerificationTypeT,
    ) -> List[OrganizationEmployee]:
        """
        1. Attempts to find the existing OE records created from 'members'
        2. If OE already exists, then check if it is associated to 'user_id'
        3. If OE doesn't exist, don't check if it is associated to 'user_id'
        4. Either create a new OE, or update the existing OE
        5. If not associated, associate the 'user_id' with the OE
        """
        member_per_org = {}
        for member in members:
            member_per_org[member.organization_id] = member

        if len(member_per_org) != len(members):
            raise EnterpriseVerificationOverEligibilityError(
                "multiple members found from the same organization",
                verification_type=verification_type,
                user_id=user_id,
                orgs_and_members=[
                    (member.organization_id, member.id) for member in members
                ],
            )

        # find the OE records using e9y_member_id or org_identities
        # the found OE list will be the most recent (by OE.id) OE record per org
        existing_employees: List[
            OrganizationEmployee
        ] = self.employees.get_by_e9y_member_id_or_org_identity(
            member_ids=[member.id for member in members],
            org_identities=[
                OrgIdentity(
                    unique_corp_id=member.unique_corp_id,
                    dependent_id=member.dependent_id,
                    organization_id=member.organization_id,
                )
                for member in members
            ],
        )

        employee_info_list: List[EmployeeInfo] = []
        for employee in existing_employees:
            try:
                member = member_per_org[employee.organization_id]
                associated_to_user = self.is_associated_to_user(
                    user_id=user_id,
                    association_id=employee.id,
                    verification_type=verification_type,
                    member_id=member.id,
                )
                employee_info_list.append(
                    EmployeeInfo(
                        employee=member_to_employee(member, employee=employee),
                        associated_to_user=associated_to_user,
                        member_id=member.id,
                    )
                )
            except KeyError:
                logger.warning(
                    "org mismatch between employees and members",
                    user_id=user_id,
                    employee_id=employee.id,
                    orgs_and_members=[
                        (member.organization_id, member.id) for member in members
                    ],
                )

        # for non-existing employees, prepare the OE data
        orgs_without_associations = set(member_per_org.keys()) - set(
            [employee.organization_id for employee in existing_employees]
        )
        for org_id in orgs_without_associations:
            member = member_per_org[org_id]
            employee_info_list.append(
                EmployeeInfo(
                    employee=member_to_employee(member),
                    associated_to_user=False,
                    member_id=member.id,
                ),
            )

        with self.session.no_autoflush:
            self.associate_user_id_to_employees(
                user_id=user_id,
                employee_info_list=employee_info_list,
                verification_type=verification_type,
            )
        self.session.commit()

        # Emit a successful verification metric
        try:
            logger.info(
                "updating verification success metric",
                user_id=user_id,
                organization_ids={m.organization_id for m in members},
                verification_type=verification_type,
                verification_status="success",
            )

            # replace this custom metric with log-based metric
            stats.increment(
                metric_name="api.eligibility.verification",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[
                    f"organization_ids:{','.join(str(m.organization_id) for m in members)}",
                    f"verification_type:{verification_type}",
                    "verification_status:success",
                ],
            )
        except Exception as e:
            logger.exception("Encountered issue emitting verification metric", e=e)

        return [employee_info.employee for employee_info in employee_info_list]

    @ddtrace.tracer.wrap()
    def associate_user_id_to_employees(
        self,
        *,
        user_id: int,
        employee_info_list: List[EmployeeInfo],
        verification_type: VerificationTypeT,
    ) -> List[OrganizationEmployee]:
        try:
            # for existing associations, update uoe.ended_at to null
            associated_list = [
                employee_info.employee
                for employee_info in employee_info_list
                if employee_info.associated_to_user
            ]
            if associated_list:
                self.user_org_employees.reset_user_associations(
                    user_id=user_id,
                    organization_employee_ids=[
                        employee.id for employee in associated_list
                    ],
                )

            # if no associations exist, create OEs & UOEs
            new_employees = []
            not_associated_list = [
                employee_info.employee
                for employee_info in employee_info_list
                if not employee_info.associated_to_user
            ]
            if not_associated_list:
                new_employees = self.employees.associate_to_user_id(
                    user_id=user_id,
                    employees=not_associated_list,
                )

            self.session.flush()

            try:
                braze.report_last_eligible_through_organization.delay(user_id)
            except Exception as err:
                logger.error("Error submitting Braze task", err=err)
            return new_employees

        except Exception:
            raise EnterpriseVerificationError(
                f"Error associating user {user_id} with multiple employees",
                verification_type=verification_type,
            )

    @ddtrace.tracer.wrap()
    def is_associated_to_user(
        self,
        *,
        user_id: int,
        association_id: int,
        verification_type: VerificationTypeT,
        member_id: int,
    ) -> bool:
        """Check if this user is associated to this member.

        Also verifies the configuration for this record to ensure we don't allow
        multiple users to be associated to a single member, if configured.
        """
        associations = self.employees.get_existing_claims(id=association_id)
        if not associations:
            return False

        association_settings = self.employees.get_association_settings(
            id=association_id
        )
        is_single_user = association_settings.employee_only or (
            association_settings.medical_plan_only
            and not association_settings.beneficiaries_enabled
        )
        associated_to_user = user_id in associations
        if is_single_user and not associated_to_user:
            claiming_user_id = associations.pop()
            raise EnterpriseVerificationConflictError(
                (
                    f"The enterprise member provided ({member_id}) "
                    f"is currently claimed by user {claiming_user_id} "
                    f"via employee {association_id}."
                ),
                verification_type=verification_type,
                given_user_id=user_id,
                claiming_user_id=claiming_user_id,
                employee_id=association_id,
                eligibility_member_id=member_id,
            )

        return associated_to_user

    @ddtrace.tracer.wrap()
    def verify_member_multistep(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        *,
        user_id: int,
        # Standard / Alternate Verification
        date_of_birth: Optional[datetime.date] = None,
        # To be used in future to help create verifications automatically from e9y
        # Standard / No-DOB Verification
        company_email: str = None,  # type: ignore[assignment] # Incompatible default for argument "company_email" (default has type "None", argument has type "str")
        # Alternate/ No-DOB Verification
        first_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "first_name" (default has type "None", argument has type "str")
        last_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "last_name" (default has type "None", argument has type "str")
        # Alternate Verification only
        work_state: str = None,  # type: ignore[assignment] # Incompatible default for argument "work_state" (default has type "None", argument has type "str")
        unique_corp_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "unique_corp_id" (default has type "None", argument has type "str")
        # Can be provided by both.
        dependent_date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "dependent_date_of_birth" (default has type "None", argument has type "date")
    ):
        # Setup the truths
        params = verification_utils.VerificationParams(
            user_id=user_id,
            date_of_birth=date_of_birth,
            company_email=company_email,
            first_name=first_name,
            last_name=last_name,
            work_state=work_state,
            unique_corp_id=unique_corp_id,
            verification_type_v2=VerificationType.MULTISTEP,
        )

        member = None
        # Start with "Alternate" verification.
        if params.has_necessary_alternate_params():
            member = self.verify_member_alternate(
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                dependent_date_of_birth=dependent_date_of_birth,
                work_state=work_state,
                unique_corp_id=unique_corp_id,
            )

            # It's possible the self-reported work-state isn't on the e9y record.
            #   In that case, try doing a lookup without work-state.
            #   We start with using the provided work-state to limit our risk of
            #   locating the wrong member...
            #   although (first, last, dob) is probably unique enough...
            if member is None and params.has_work_state():
                member = self.verify_member_alternate(
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=date_of_birth,
                    dependent_date_of_birth=dependent_date_of_birth,
                    work_state=None,
                    unique_corp_id=unique_corp_id,
                )
        # If alternate fails or can't be run,
        #   try with "Standard" verification, just to be sure.
        if member is None and params.has_necessary_standard_params():
            member = self.verify_member_standard(
                company_email=company_email,
                date_of_birth=date_of_birth,
                dependent_date_of_birth=dependent_date_of_birth,
            )

        return member

    @ddtrace.tracer.wrap()
    def verify_member_standard(
        self,
        *,
        company_email: str,
        date_of_birth: datetime.date,
        dependent_date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "dependent_date_of_birth" (default has type "None", argument has type "date")
    ) -> model.EligibilityMember | None:
        metadata = e9y_service_util.get_trace_metadata()
        # Prefer dependent dob if provided.
        if dependent_date_of_birth:
            member = self.e9y.get_by_standard_verification(
                date_of_birth=dependent_date_of_birth,
                company_email=company_email,
                metadata=metadata,
            )
            if member:
                return member
        # Fall-back to regular dob.
        member = self.e9y.get_by_standard_verification(
            date_of_birth=date_of_birth,
            company_email=company_email,
            metadata=metadata,
        )
        return member

    @ddtrace.tracer.wrap()
    def verify_member_alternate(
        self,
        *,
        first_name: str,
        last_name: str,
        date_of_birth: datetime.date,
        dependent_date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "dependent_date_of_birth" (default has type "None", argument has type "date")
        work_state: str = None,  # type: ignore[assignment] # Incompatible default for argument "work_state" (default has type "None", argument has type "str")
        unique_corp_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "unique_corp_id" (default has type "None", argument has type "str")
    ) -> model.EligibilityMember | None:
        # NOTE: we're sacrificing a bit of DRY-ness for the sake of readability.
        #   It's far more clear what's happening if this fall-through for
        #   dependent dob is explicit.
        #   The alternative is an unstructured bag o' kwargs,
        #   which is inherently mysterious and not worth supposedly DRY code.
        metadata = e9y_service_util.get_trace_metadata()
        # Prefer dependent dob if provided.
        if dependent_date_of_birth:
            member = self.e9y.get_by_alternate_verification(
                date_of_birth=dependent_date_of_birth,
                first_name=first_name,
                last_name=last_name,
                unique_corp_id=unique_corp_id,
                work_state=work_state,
                metadata=metadata,
            )
            if member:
                return member

        # Fall-back to regular dob.
        member = self.e9y.get_by_alternate_verification(
            date_of_birth=date_of_birth,
            first_name=first_name,
            last_name=last_name,
            unique_corp_id=unique_corp_id,
            work_state=work_state,
            metadata=metadata,
        )
        return member

    @ddtrace.tracer.wrap()
    def verify_member_overeligibility(
        self,
        *,
        first_name: str,
        last_name: str,
        date_of_birth: datetime.date,
        user_id: Optional[int] = None,
        dependent_date_of_birth: Optional[datetime.date] = None,
        unique_corp_id: Optional[str] = None,
        company_email: Optional[str] = None,
    ) -> List[model.EligibilityMember] | None:

        metadata = e9y_service_util.get_trace_metadata()
        # Prefer dependent dob if provided.
        if dependent_date_of_birth:
            members = self.e9y.get_by_overeligibility_verification(
                date_of_birth=dependent_date_of_birth,
                first_name=first_name,
                last_name=last_name,
                unique_corp_id=unique_corp_id,  # type: ignore[arg-type] # Argument "unique_corp_id" to "get_by_overeligibility_verification" of "EligibilityMemberRepository" has incompatible type "Optional[str]"; expected "str"
                company_email=company_email,  # type: ignore[arg-type] # Argument "company_email" to "get_by_overeligibility_verification" of "EligibilityMemberRepository" has incompatible type "Optional[str]"; expected "str"
                user_id=user_id,
                metadata=metadata,
            )
            if members:
                return members

        # Fall-back to regular dob.
        members = self.e9y.get_by_overeligibility_verification(
            date_of_birth=date_of_birth,
            first_name=first_name,
            last_name=last_name,
            unique_corp_id=unique_corp_id,  # type: ignore[arg-type] # Argument "unique_corp_id" to "get_by_overeligibility_verification" of "EligibilityMemberRepository" has incompatible type "Optional[str]"; expected "str"
            company_email=company_email,  # type: ignore[arg-type] # Argument "company_email" to "get_by_overeligibility_verification" of "EligibilityMemberRepository" has incompatible type "Optional[str]"; expected "str"
            user_id=user_id,
            metadata=metadata,
        )
        return members

    @ddtrace.tracer.wrap()
    def verify_member_client_specific(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        *,
        organization_id: int,
        unique_corp_id: str,
        is_employee: bool,
        date_of_birth: datetime.date,
        dependent_date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "dependent_date_of_birth" (default has type "None", argument has type "date")
    ):
        metadata = e9y_service_util.get_trace_metadata()
        member = self.e9y.get_by_client_specific(
            date_of_birth=date_of_birth,
            unique_corp_id=unique_corp_id,
            organization_id=organization_id,
            is_employee=is_employee,
            dependent_date_of_birth=dependent_date_of_birth,
            metadata=metadata,
        )
        return member

    @ddtrace.tracer.wrap()
    def verify_member_no_dob(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
    ):
        metadata = e9y_service_util.get_trace_metadata()
        member = self.e9y.get_by_no_dob_verification(
            email=email,
            first_name=first_name,
            last_name=last_name,
            metadata=metadata,
        )
        return member

    def verify_member_basic(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        params: verification_utils.VerificationParams,
    ) -> List[model.EligibilityMember]:
        if not params.has_necessary_basic_params():
            raise EnterpriseVerificationQueryError(
                f"Couldn't run verification for User {params.user_id}.",
                verification_type=VerificationType.BASIC,
                required_params=("date_of_birth", "first_name", "last_name"),
            )
        metadata = e9y_service_util.get_trace_metadata()
        members = self.e9y.get_by_basic_verification(
            first_name=params.first_name,  # type: ignore[arg-type]
            last_name=params.last_name,  # type: ignore[arg-type]
            date_of_birth=params.date_of_birth,  # type: ignore[arg-type]
            user_id=params.user_id,
            metadata=metadata,
        )

        # No members found
        if not members:
            return []

        if len(members) > 1:
            member_ids = [member.id for member in members]
            organization_ids = [member.organization_id for member in members]
            logger.warning(
                "User has overeligibility",
                extra={
                    "user_id": params.user_id,
                    "member_ids": member_ids,
                    "organization_ids": organization_ids,
                },
            )
            # TODO add member records to cache so we can skip overeligibility check
            # Fail basic verification if more than one eligibility record is found
            return []

        # Single member found
        return members

    def verify_member_employer(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        params: verification_utils.VerificationParams,
    ) -> List[model.EligibilityMember]:
        if (
            not params.has_necessary_basic_params()
            and not params.has_necessary_employer_params()
        ):
            raise EnterpriseVerificationQueryError(
                f"Couldn't run verification for User {params.user_id}.",
                verification_type=VerificationType.EMPLOYER,
                required_params=(
                    "company_email",
                    "date_of_birth",
                    "first_name",
                    "last_name",
                ),
            )
        metadata = e9y_service_util.get_trace_metadata()
        member = self.e9y.get_by_employer_verification(
            company_email=params.company_email,  # type: ignore[arg-type]
            date_of_birth=params.date_of_birth,  # type: ignore[arg-type]
            first_name=params.first_name,  # type: ignore[arg-type]
            last_name=params.last_name,  # type: ignore[arg-type]
            employee_first_name=params.employee_first_name,  # type: ignore[arg-type]
            employee_last_name=params.employee_last_name,  # type: ignore[arg-type]
            work_state=params.work_state,  # type: ignore[arg-type]
            dependent_date_of_birth=params.dependent_date_of_birth,  # type: ignore[arg-type]
            user_id=params.user_id,
            metadata=metadata,
        )
        if member:
            return [member]
        return []

    def verify_member_healthplan(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        params: verification_utils.VerificationParams,
    ):
        if (
            not params.has_necessary_basic_params()
            and not params.has_necessary_healthplan_params()
        ):
            raise EnterpriseVerificationQueryError(
                f"Couldn't run verification for User {params.user_id}.",
                verification_type=VerificationType.HEALTHPLAN,
                required_params=(
                    "date_of_birth",
                    "first_name",
                    "last_name",
                ),
            )
        metadata = e9y_service_util.get_trace_metadata()
        member = self.e9y.get_by_healthplan_verification(
            subscriber_id=params.unique_corp_id,  # type: ignore[arg-type]
            first_name=params.first_name,  # type: ignore[arg-type]
            last_name=params.last_name,  # type: ignore[arg-type]
            date_of_birth=params.date_of_birth,  # type: ignore[arg-type]
            user_id=params.user_id,
            dependent_date_of_birth=params.dependent_date_of_birth,
            employee_first_name=params.employee_first_name,
            employee_last_name=params.employee_last_name,
            metadata=metadata,
        )
        if member:
            return [member]
        return []

    def verify_member_multistep_v2(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        params: verification_utils.VerificationParams,
    ):
        if not params.has_necessary_multistep_v2_params():
            raise EnterpriseVerificationQueryError(
                f"Couldn't run verification for User {params.user_id}.",
                verification_type=VerificationType.MULTISTEP,
                required_params=("basic", "employer", "healthplan"),
            )
        metadata = e9y_service_util.get_trace_metadata()
        member = None
        if params.has_necessary_healthplan_params():
            member = self.e9y.get_by_healthplan_verification(
                subscriber_id=params.unique_corp_id,  # type: ignore[arg-type]
                first_name=params.first_name,  # type: ignore[arg-type]
                last_name=params.last_name,  # type: ignore[arg-type]
                date_of_birth=params.date_of_birth,  # type: ignore[arg-type]
                dependent_date_of_birth=params.dependent_date_of_birth,
                employee_first_name=params.employee_first_name,
                employee_last_name=params.employee_last_name,
                user_id=params.user_id,
                metadata=metadata,
            )

        if not member and params.has_necessary_employer_params():
            member = self.e9y.get_by_employer_verification(
                company_email=params.company_email,  # type: ignore[arg-type]
                date_of_birth=params.date_of_birth,  # type: ignore[arg-type]
                first_name=params.first_name,  # type: ignore[arg-type]
                last_name=params.last_name,  # type: ignore[arg-type]
                employee_first_name=params.employee_first_name,  # type: ignore[arg-type]
                employee_last_name=params.employee_last_name,  # type: ignore[arg-type]
                work_state=params.work_state,  # type: ignore[arg-type]
                dependent_date_of_birth=params.dependent_date_of_birth,  # type: ignore[arg-type]
                user_id=params.user_id,
                metadata=metadata,
            )

        if member:
            return [member]

        members = []
        if params.has_necessary_basic_params():
            members = self.e9y.get_by_basic_verification(  # type: ignore[assignment]
                first_name=params.first_name,  # type: ignore[arg-type]
                last_name=params.last_name,  # type: ignore[arg-type]
                date_of_birth=params.date_of_birth,  # type: ignore[arg-type]
                user_id=params.user_id,
                metadata=metadata,
            )

        if not members:
            return []

        elif len(members) == 1:
            return members

        # we fail basic verification if we find more than one eligibility record
        member_ids = [member.id for member in members]
        organization_ids = [member.organization_id for member in members]
        logger.warning(
            "User has overeligibility",
            extra={
                "user_id": params.user_id,
                "member_ids": member_ids,
                "organization_ids": organization_ids,
            },
        )
        return []

    @ddtrace.tracer.wrap()
    def verify_member_sso(
        self,
        *,
        user_id: int,
        identity_pair: tuple[
            authn_model.UserExternalIdentity, repository.OrganizationMeta
        ] = None,  # type: ignore[assignment] # Incompatible default for argument "identity_pair" (default has type "None", argument has type "Tuple[UserExternalIdentity, OrganizationMeta]")
    ) -> model.EligibilityMember | None:
        if identity_pair is None:
            identity_pair = self.orgs.get_organization_by_user_external_identities(
                user_id=user_id
            )

        identity, org_meta = identity_pair
        if (identity, org_meta) == (None, None):
            return None

        metadata = e9y_service_util.get_trace_metadata()
        member = self.e9y.get_by_org_identity(
            unique_corp_id=(
                str(identity.unique_corp_id)
                if identity.unique_corp_id is not None
                else ""
            ),
            dependent_id="",
            organization_id=org_meta.organization_id,
            metadata=metadata,
        )
        return member

    @ddtrace.tracer.wrap()
    def create_fileless_verification(
        self,
        user_id: int,
        first_name: str,
        last_name: str,
        date_of_birth: datetime.date,
        company_email: str,
        is_dependent: bool,
    ) -> Optional[model.EligibilityVerification]:
        """Create a verification for a fileless org when a user claims their invite"""
        metadata = e9y_service_util.get_trace_metadata()

        # Look up org settings based on company email
        settings = self.orgs.get_eligibility_settings_by_email(
            company_email=company_email,
        )

        if not settings:
            domain = self.orgs.get_email_domain(company_email)
            raise EnterpriseVerificationQueryError(
                f"Couldn't locate organization configuration with {domain=}",
                verification_type="fileless",
                required_params=(
                    "user_id",
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "company_email",
                    "is_dependent",
                ),
            )

        # check if a verification already exists for this user for this org
        existing_verification: model.EligibilityVerification | None = (
            self.get_verification_for_user_and_org(
                user_id=user_id,
                organization_id=settings.organization_id,
                metadata=metadata,
            )
        )
        if (
            existing_verification
            and existing_verification.organization_id == settings.organization_id
        ):
            logger.info(
                "Existing fileless verification found for user",
                user_id=user_id,
                organization_id=existing_verification.organization_id,
                verification_id=existing_verification.verification_id,
            )
            return existing_verification

        # at this point, we know the org is a valid fileless org
        # and no verification exists for the user, or it is for a different org
        sha = hashlib.sha1(company_email.lower().encode()).hexdigest()
        unique_corp_id = f"AUTOGEN{sha}"
        dependent_id = f"AUTOGEN{uuid.uuid4().hex}" if is_dependent else ""

        # prepare the verification data
        verification_data = model.VerificationData(
            eligibility_member_id=None,
            organization_id=settings.organization_id,
            unique_corp_id=unique_corp_id,
            dependent_id=dependent_id,
            email=company_email,
            additional_fields=str({"is_dependent": is_dependent}),
            work_state=None,
        )

        # Create verifications for the user
        verifications = self.generate_multiple_verifications_for_user(
            user_id=user_id,
            verification_type="fileless",
            members=None,
            verification_data_list=[verification_data],
            date_of_birth=date_of_birth,
            first_name=first_name,
            last_name=last_name,
            additional_fields={"is_dependent": is_dependent},
            verification_session=uuid.uuid4().hex,
        )

        if not verifications:
            logger.error(
                "Failed to create fileless verification for user", user_id=user_id
            )
            return None
        return verifications.pop()

    @ddtrace.tracer.wrap()
    def get_fileless_enterprise_association(
        self,
        *,
        user_id: int,
        first_name: str,
        last_name: str,
        date_of_birth: datetime.date,
        company_email: str,
        is_dependent: bool,
    ) -> OrganizationEmployee:
        """Verify a user as a member of an organization with no census data.

        This is run separately from the omnibus verification because:
            1. Association occurs by claiming an invite.
            2. We have no census data ahead of time, so can't verify by other means.
        """
        # look up an org using the given email.
        settings = self.orgs.get_eligibility_settings_by_email(
            company_email=company_email,
        )
        if not settings:
            domain = self.orgs.get_email_domain(company_email)
            raise EnterpriseVerificationQueryError(
                f"Couldn't locate organization configuration with {domain=}",
                verification_type="fileless",
                required_params=(
                    "user_id",
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "company_email",
                    "is_dependent",
                ),
            )

        # Check for an existing association - if we have one, use that
        existing_associations = self.employees.get_by_user_id(
            user_id=user_id,
        )
        filtered_associations = [
            association
            for association in existing_associations
            if association.organization_id == settings.organization_id
        ]
        if filtered_associations:
            return filtered_associations[0]

        # Otherwise, look for an existing org association some provided metadata.
        association = self.employees.get_by_org_id_email_dob(
            organization_id=settings.organization_id,
            email=company_email,
            date_of_birth=date_of_birth,
        )
        # If we found an association, validate we can use it.
        if association:
            # This checks two things:
            #   1. Is the user ID already associated (we don't care here).
            #   2. Is the user ID allowed to claim the association (we do care).
            self.is_associated_to_user(
                user_id=user_id,
                association_id=association.id,
                verification_type="fileless",
                member_id=association.eligibility_member_id,
            )

        # Otherwise, create a new employee record.
        if association is None:
            # Randomly generate these values, since we don't have them.
            sha = hashlib.sha1(company_email.lower().encode()).hexdigest()
            unique_corp_id = f"AUTOGEN{sha}"
            dependent_id = f"AUTOGEN{uuid.uuid4().hex}" if is_dependent else ""
            # Create the member record
            try:
                association = self.employees.create(
                    first_name=first_name,
                    last_name=last_name,
                    email=company_email,
                    date_of_birth=date_of_birth,
                    organization_id=settings.organization_id,
                    unique_corp_id=unique_corp_id,
                    dependent_id=dependent_id,
                )
            except sqlalchemy.exc.IntegrityError:
                raise EnterpriseVerificationFilelessError(
                    (
                        f"Failed to create OE due to conflict"
                        f"unique_corp_id={unique_corp_id} already exists"
                    ),
                    verification_type="fileless",
                    user_id=user_id,
                    organization_id=settings.organization_id,
                    unique_corp_id=unique_corp_id,
                    dependent_id=dependent_id,
                )
            try:
                braze.report_last_eligible_through_organization.delay(user_id)
            except Exception as err:
                logger.error("Error submitting Braze task", err=err)
        # TODO: Create verification here for fileless - primary
        # Associate the record to the user ID.
        associations = self.employees.associate_to_user_id(
            user_id=user_id, employees=[association]
        )
        return associations[0] if associations else None

    @ddtrace.tracer.wrap()
    def get_eligible_organization_ids_for_user(
        self, *, user_id: int, timeout_in_sec: Optional[float] = None
    ) -> Set[int]:
        # Our cache does not like 'None' values- they result in a cache miss
        # To support users with no orgs, we use a -1 to represent they have no org, and then cast it to null value
        metric_name = "api.eligibility.enterpriseverificationservice.get_eligible_organization_ids_for_user"
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.ELIGIBILITY,
        )
        with stats.timed(metric_name=metric_name, pod_name=stats.PodNames.ELIGIBILITY):
            organization_ids = self.org_id_cache.get(user_id)
            if not organization_ids or isinstance(organization_ids, int):
                organization_ids = self._get_raw_organization_ids_for_user(
                    user_id=user_id, timeout_in_sec=timeout_in_sec
                )
                if organization_ids and isinstance(organization_ids, list):
                    self.org_id_cache.add(user_id, organization_ids)

            return set(organization_ids)

    @ddtrace.tracer.wrap()
    def _get_raw_organization_ids_for_user(
        self, *, user_id: int, timeout_in_sec: Optional[float] = None
    ) -> List[int]:
        """Get a user's verified organization ID- return -1 if the user does not have an associated org"""
        stats.increment(
            metric_name="api.eligibility.enterpriseverificationservice.get_org_for_user.cache_miss",
            pod_name=stats.PodNames.ELIGIBILITY,
        )
        verification_list: List[model.EligibilityVerification] = []

        try:
            metadata = e9y_service_util.get_trace_metadata()
            verification_list = self.e9y.get_all_verifications_for_user(
                user_id=user_id, metadata=metadata, timeout=timeout_in_sec
            )
        except Exception as e:
            logger.exception(
                "[verification] Exception encountered while fetching verification for user",
                user_id=user_id,
                error=e,
            )

        return [verification.organization_id for verification in verification_list]

    @staticmethod
    @ddtrace.tracer.wrap()
    def is_active(*, activated_at: datetime.datetime | None) -> bool:
        """Determine if an organization is active"""
        return activated_at is not None and activated_at <= datetime.datetime.utcnow()

    @ddtrace.tracer.wrap()
    def get_organization_ids_for_user(self, *, user_id: int) -> List[int]:  # type: ignore[empty-body] # Missing return statement
        """Placeholder for when multi-org support is implemented"""
        ...

    @ddtrace.tracer.wrap()
    def get_org_e9y_settings(
        self, *, organization_id: int
    ) -> EnterpriseEligibilitySettings | None:
        """Get org level eligibility settings"""
        return self.orgs.get_eligibility_settings(organization_id=organization_id)

    @ddtrace.tracer.wrap()
    def get_all_verifications_for_user(
        self,
        *,
        user_id: int,
        organization_ids: Optional[List[int]] = None,
        active_verifications_only: Optional[bool] = False,
    ) -> List[model.EligibilityVerification]:
        """
        Return a list of verification for a user
        user_id: the id you wish to retrieve a verification for
        organization_ids: Optional- restrict returned verifications only if they are from the specific org list
        active_verifications_only: Optional- if set, only return verifications with a valid (i.e. active E9y record)

        ****Please note* We will attempt to find a verification for a user before we create a new one. If we *do* find a
        verification for a user (and we return it) it does *NOT* mean the verification is active- to determine if the
        verification is still active (i.e. the user still has eligibility with that verification), the effective_range
        field on the verification must be used and confirmed to not have expired

        See also - is_verification_active and check_if_user_has_existing_eligibility
        *****
        """

        metadata = e9y_service_util.get_trace_metadata()
        stats.increment(
            metric_name="api.eligibility.enterpriseverificationservice.get_all_verifications_for_user.grpc",
            pod_name=stats.PodNames.ELIGIBILITY,
        )

        verifications: List[
            model.EligibilityVerification
        ] = self.e9y.get_all_verifications_for_user(
            user_id=user_id,
            metadata=metadata,
            organization_ids=organization_ids,
            active_verifications_only=active_verifications_only,
        )

        return verifications

    @ddtrace.tracer.wrap()
    def get_verification_for_user_and_org(
        self,
        *,
        user_id: int,
        organization_id: int,
        active_verification_only: Optional[bool] = False,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityVerification | None:
        """
        Return the verification for a user and org specified.
        user_id: the id you wish to retrieve a verification for
        organization_id: restrict returned verification only if they are from the specific org list
        active_verifications_only: Optional- if set, only return verifications with a valid (i.e. active E9y record)

        ****Please note* We will attempt to find a verification for a user before we create a new one. If we *do* find a
        verification for a user (and we return it) it does *NOT* mean the verification is active- to determine if the
        verification is still active (i.e. the user still has eligibility with that verification), the effective_range
        field on the verification must be used and confirmed to not have expired

        See also - is_verification_active and check_if_user_has_existing_eligibility
        *****
        """
        metadata = (
            e9y_service_util.get_trace_metadata() if metadata is None else metadata
        )
        stats.increment(
            metric_name="api.eligibility.enterpriseverificationservice.get_verification_for_user_and_org.grpc",
            pod_name=stats.PodNames.ELIGIBILITY,
        )

        verifications: List[
            model.EligibilityVerification
        ] = self.e9y.get_all_verifications_for_user(
            user_id=user_id,
            metadata=metadata,
            organization_ids=[organization_id],
            active_verifications_only=active_verification_only,
        )

        if len(verifications) != 1:
            logger.info(
                "expect one verification found for user and org",
                user_id=user_id,
                organization_id=organization_id,
                active_verifications_only=active_verification_only,
                size=len(verifications),
            )
            return None

        verification = verifications[0]

        try:
            previous_verification = self.get_verification_for_user(
                user_id=user_id,
                organization_id=organization_id,
                active_eligibility_only=active_verification_only,
            )
            compare_verifications(
                user_id=user_id,
                previous_verification=previous_verification,
                new_verification=verification,
            )
        except Exception as e:
            logger.exception(
                "Exception encountered while comparing verifications for user and org",
                user_id=user_id,
                organization_id=organization_id,
                active_verifications_only=active_verification_only,
                error=e,
            )

        return verification

    @ddtrace.tracer.wrap()
    def get_verification_for_user(
        self,
        *,
        user_id: int,
        organization_id: Optional[int] = None,
        active_eligibility_only: Optional[bool] = False,
    ) -> model.EligibilityVerification | None:
        """

        NOTE: This code is currently impacted by the feature flag ELIGIBILITY_NEW_DATA_MODEL_READ
        This flag will stay on - we unfortunately are not able to remove the code below this flag right now
        due to a large number of tests that would be impacted (we are in the process of cleaning them up)

        Please only look at the logic within the flag block to understand what this method is doing.


        Return a verification for a user
        user_id: the id you wish to retrieve a verification for
        source : Fetch the data from OE or grab the latest from e9y via eligibility_member_id
        organization_id: Optional- restrict returned verifications only if they are from a specific org
        active_eligibility_only: Optional- if set, only return verifications with a valid (i.e. active E9y record)
        member_fields_override - Override certain fields from OE with data from e9y

        ****Please note* We will attempt to find a verification for a user before we create a new one. If we *do* find a
        verification for a user (and we return it) it does *NOT* mean the verification is active- to determine if the
        verification is still active (i.e. the user still has eligibility with that verification), the effective_range
        field on the verification must be used and confirmed to not have expired

        See also - is_verification_active and check_if_user_has_existing_eligibility
        *****
        """

        metadata = e9y_service_util.get_trace_metadata()

        stats.increment(
            metric_name="api.eligibility.enterpriseverificationservice.get_verification_for_user.grpc",
            pod_name=stats.PodNames.ELIGIBILITY,
        )
        verification: model.EligibilityVerification | None = (
            self.e9y.get_verification_for_user(
                user_id=user_id,
                metadata=metadata,
                organization_id=organization_id,
                active_eligibility_only=active_eligibility_only,
            )
        )

        return verification

    @staticmethod
    @ddtrace.tracer.wrap()
    def is_single_user(
        *, employee_only: bool, medical_plan_only: bool, beneficiaries_enabled: bool
    ) -> bool:
        return bool(employee_only or (medical_plan_only and not beneficiaries_enabled))

    @ddtrace.tracer.wrap()
    def check_if_user_has_existing_eligibility(
        self,
        *,
        user_id: int,
        timeout: Optional[float] = None,
        organization_id: int | None = None,
    ) -> bool:

        verification = None

        try:
            metadata = e9y_service_util.get_trace_metadata()
            verification = self.e9y.get_verification_for_user(
                user_id=user_id,
                timeout=timeout,
                metadata=metadata,
                organization_id=organization_id,
                active_eligibility_only=True,
            )

            if verification is None:
                logger.info(
                    "[verification] Failed to locate existing verification",
                    user_id=user_id,
                )
                return False

        except Exception as e:
            logger.exception(
                "[verification] Exception encountered while trying to locate verification for user",
                error=e,
                user_id=user_id,
            )

        return True

    @ddtrace.tracer.wrap()
    def is_user_known_to_be_eligible_for_org(
        self,
        *,
        user_id: int,
        organization_id: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        if org_id provided, check user's eligibility in the org;
        otherwise, check whether user has eligibility in any orgs
        """
        try:
            metadata = e9y_service_util.get_trace_metadata()
            verifications = self.e9y.get_all_verifications_for_user(
                user_id=user_id,
                timeout=timeout,
                metadata=metadata,
                organization_ids=[organization_id] if organization_id else None,
                active_verifications_only=True,
            )

            if not verifications:
                logger.info(
                    "[verification] Failed to locate existing verification in org",
                    user_id=user_id,
                    organization_id=organization_id,
                )

            return True if verifications else False

        except Exception as e:
            logger.exception(
                "[verification] Exception encountered while trying to locate verification for user and org",
                error=e,
                user_id=user_id,
                organization_id=organization_id,
            )

        return False

    @staticmethod
    def is_verification_active(
        verification: model.EligibilityVerification | None = None,
    ) -> bool:
        if not verification:
            return False

        # handles the case where the verification was created
        # from an OrganizationEmployee and does not have an effective_range
        # TODO - Remove this when OEs are removed and eligibility checks only go through e9y
        # https://mavenclinic.atlassian.net/browse/ELIG-1602
        if not verification.effective_range:
            return verification.is_active

        upper = verification.effective_range.upper
        if not upper:
            return True

        current_date = datetime.date.today()
        if current_date < upper:
            return True

        return False

    @ddtrace.tracer.wrap()
    def get_pre_eligibility_records(
        self,
        *,
        first_name: str,
        last_name: str,
        date_of_birth: datetime.datetime,
        user_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "user_id" (default has type "None", argument has type "int")
        timeout: Optional[float] = None,
    ) -> model.PreEligibilityResponse:
        """
        Search for a member using user id, first name, last name and date of birth and
        return all organizations they may be part associated with
        """
        has_necessary_query_params = None not in (first_name, last_name, date_of_birth)
        if not has_necessary_query_params:
            # Note: we are returning a success response with INVALID MatchType
            # Ideally this should be an error response; we are doing this because the
            # endpoint gets hit a lot creating a lot of noisy alerts
            response = model.PreEligibilityResponse(
                match_type=model.MatchType.INVALID,
                pre_eligibility_organizations=[],
            )
            return response

        metadata = e9y_service_util.get_trace_metadata()
        return self.e9y.get_by_member_details(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            timeout=timeout,
            metadata=metadata,
        )

    @ddtrace.tracer.wrap()
    def is_user_known_to_be_eligible(
        self,
        *,
        first_name: str,
        last_name: str,
        date_of_birth: datetime.datetime,
        user_id: int,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        since we only need to know if user has existing eligibility, we simply check the user associated
        verification record and see if they have active eligibility. first_name, last_name and date_or_birth can be
        used to look up if user has additional eligibility in the future
        Args:
            first_name: unused param
            last_name: unused param
            date_of_birth: unused param
            user_id: user id to look up verification record
            timeout: seconds before the request should timeout

        Returns: True if user has active eligibility and False otherwise
        """

        return self.check_if_user_has_existing_eligibility(
            user_id=user_id, timeout=timeout
        )

    # region wallet

    @ddtrace.tracer.wrap()
    def get_wallet_enablement_by_user_id(
        self, *, user_id: int
    ) -> model.WalletEnablement | None:
        """Search for a wallet enablement configuration for the provided user ID.

        A "wallet enablement" is a set of configuration values provided to us at the
        member-level by an organization which allows or dis-allows a user to access our
        Maven Wallet product.

        Note- record returned is not guaranteed to be active- you must look at the record itself to determine
        if it represents an eligible user's data. We may return historical data.

        Parameter:
          user_id <int>: The Maven identifier for a user

        Returns:
          A WalletEnablement, if one is found.
        """
        metadata = e9y_service_util.get_trace_metadata()
        result = self.wallet.get_by_user_id(user_id=user_id, metadata=metadata)
        if result:
            return result
        return None

    @ddtrace.tracer.wrap()
    def get_wallet_enablement_by_identity(
        self, *, unique_corp_id: str, dependent_id: str, organization_id: int
    ) -> model.WalletEnablement | None:
        """Search for a wallet enablement using an org identity.

        An 'Org-Identity' is a unique, composite key based on the Organization's ID and
        the eligibility member record's `unique_corp_id` & `dependent_id`.

        Note- record returned is not guaranteed to be active- you must look at the record itself to determine
        if it represents an eligible user's data. We may return historical data.

        Parameters:
            unique_corp_id <str>: The unique_corp_id of the member record.
            dependent_id <str>: The dependent_id of the member record.
            organization_id <str>: The ID of the organization this record should belong to.

        Returns:
            A WalletEnablement, if one is found.
        """
        metadata = e9y_service_util.get_trace_metadata()
        result = self.wallet.get_by_org_identity(
            unique_corp_id=unique_corp_id,
            dependent_id=dependent_id,
            organization_id=organization_id,
            metadata=metadata,
        )
        if result:
            return result
        return None

    @ddtrace.tracer.wrap()
    def get_eligible_features_for_user(
        self, *, user_id: int, feature_type: int
    ) -> List[int] | None:
        """
        Get all configuration features (e.g. Tracks, Wallet) that the user is associated
        e9y contains the sub-populations the user is associated with and the configured features from e9y
        will be returned

        Args:
            user_id: unique user identifier
            feature_type: type of features for narrowing down the search

        Returns: list of feature ids for the user or None if there is no active population
        """
        has_necessary_query_params = None not in (user_id, feature_type)
        if not has_necessary_query_params:
            # check if the request has all input params and raise error if not
            raise EligibilityFeaturesQueryError(
                "Missing required parameters to get eligible features for user",
                required_params=("user_id", "feature_type"),
            )

        metadata = e9y_service_util.get_trace_metadata()
        response = self.features.get_eligible_features_for_user(
            user_id=user_id,
            feature_type=feature_type,
            metadata=metadata,
        )
        # Response will be None if there was an exception during the gRPC call
        if response is None:
            return []
        if not response.has_population:
            return None
        return response.features

    @ddtrace.tracer.wrap()
    def get_eligible_features_for_user_and_org(
        self, *, user_id: int, organization_id: int, feature_type: int
    ) -> List[int] | None:
        """
        Get all configuration features (e.g. Tracks, Wallet) that the user is associated in the org
        e9y contains the sub-populations the user is associated with and the configured features from e9y
        will be returned

        Args:
            user_id: unique user identifier
            organization_id: id for the organization this record should belong to.
            feature_type: type of features for narrowing down the search

        Returns: list of feature ids for the user or None if there is no active population
        """
        has_necessary_query_params = None not in (
            user_id,
            organization_id,
            feature_type,
        )
        if not has_necessary_query_params:
            # check if the request has all input params and raise error if not
            raise EligibilityFeaturesQueryError(
                "Missing required parameters to get eligible features for user",
                required_params=("user_id", "organization_id", "feature_type"),
            )

        metadata = e9y_service_util.get_trace_metadata()
        response = self.features.get_eligible_features_for_user_and_org(
            user_id=user_id,
            organization_id=organization_id,
            feature_type=feature_type,
            metadata=metadata,
        )
        # Response will be None if there was an exception during the gRPC call
        if response is None:
            return []
        if not response.has_population:
            return None
        return response.features

    @ddtrace.tracer.wrap()
    def get_eligible_features_by_sub_population_id(
        self, *, sub_population_id: int, feature_type: int
    ) -> List[int] | None:
        """
        Get all configuration features (e.g. Tracks, Wallet) that the user is associated
        e9y contains the sub-populations the user is associated with and the configured features from e9y
        will be returned

        Args:
            sub_population_id: the id of the sub-population to use to determine the eligible
                features.
            feature_type: type of features for narrowing down the search

        Returns: list of feature ids for the user or None if there is no active population
        """
        has_necessary_query_params = None not in (sub_population_id, feature_type)
        if not has_necessary_query_params:
            # check if the request has all input params and raise error if not
            raise EligibilityFeaturesQueryError(
                "Missing required parameters to get eligible features for user",
                required_params=("user_id", "feature_type"),
            )

        metadata = e9y_service_util.get_trace_metadata()
        response = self.features.get_eligible_features_by_sub_population_id(
            sub_population_id=sub_population_id,
            feature_type=feature_type,
            metadata=metadata,
        )
        # Response will be None if there was an exception during the gRPC call
        if response is None:
            return []
        if not response.has_definition:
            return None
        return response.features

    @ddtrace.tracer.wrap()
    def get_sub_population_id_for_user(self, *, user_id: int) -> int | None:
        """
        Gets the sub-population ID of the user based on the user's org's active population
        and the user's eligibility member attributes.

        Args:
            user_id: the id of the user

        Returns: id for the user's sub-population or None if there is no active population
        """
        has_necessary_query_params = user_id is not None
        if not has_necessary_query_params:
            # check if the request has all input params and raise error if not
            raise EligibilityFeaturesQueryError(
                "Missing required parameters to get eligible features for user",
                required_params=("user_id",),
            )

        metadata = e9y_service_util.get_trace_metadata()
        return self.features.get_sub_population_id_for_user(
            user_id=user_id,
            metadata=metadata,
        )

    @ddtrace.tracer.wrap()
    def get_sub_population_id_for_user_and_org(
        self, *, user_id: int, organization_id: int
    ) -> int | None:
        """
        Gets the sub-population ID of the user based on the org's active population
        and the user's eligibility member attributes.

        Args:
            user_id: the id of the user
            organization_id: the id of the organization

        Returns: id for the user's sub-population in the org or None if there is no active population
        """
        has_necessary_query_params = None not in (user_id, organization_id)
        if not has_necessary_query_params:
            # check if the request has all input params and raise error if not
            raise EligibilityFeaturesQueryError(
                "Missing required parameters to get eligible features for user",
                required_params=(
                    "user_id",
                    "organization_id",
                ),
            )

        metadata = e9y_service_util.get_trace_metadata()
        return self.features.get_sub_population_id_for_user_and_org(
            user_id=user_id,
            organization_id=organization_id,
            metadata=metadata,
        )

    @ddtrace.tracer.wrap()
    def get_other_user_ids_in_family(self, *, user_id: int) -> List[int]:
        """Gets the other active user_id's for a "family" as defined by a shared "unique_corp_id"

        Parameters:
          user_id <int>: id of the user

        Returns:
          A list of user_id's, does not include the input user's own user_id
        """
        has_necessary_query_params = user_id is not None
        if not has_necessary_query_params:
            # check if the request has all input params and raise error if not
            raise ValueError("user_id is a required parameter")

        metadata = e9y_service_util.get_trace_metadata()
        return self.e9y.get_other_user_ids_in_family(
            user_id=user_id,
            metadata=metadata,
        )

    @ddtrace.tracer.wrap()
    def create_test_eligibility_member_records(
        self,
        *,
        organization_id: int,
        test_member_records: List[Dict[str:str]],  # type: ignore[type-arg,valid-type] # "dict" expects 2 type arguments, but 1 given #type: ignore[valid-type] # Invalid type comment or annotation #type: ignore[valid-type] # Invalid type comment or annotation
    ) -> List[str]:
        # Check if non-prod
        if not is_non_prod():
            raise EligibilityTestMemberCreationError(
                "this endpoint is not allowed in production environment"
            )
        # Input validation
        if not organization_id:
            raise EligibilityTestMemberCreationError(
                "organization_id is a required parameter"
            )

        if not test_member_records or len(test_member_records) == 0:
            raise EligibilityTestMemberCreationError(
                "test_member_records is a required parameter"
            )

        logger.debug("Creating test eligibility member records")

        metadata = e9y_service_util.get_trace_metadata()
        return self.e9y.create_test_member_records_for_organization(
            organization_id=organization_id,
            test_member_records=test_member_records,
            metadata=metadata,
        )

    # endregion


# region errors
class EnterpriseVerificationError(Exception):
    def __init__(
        self, message: str, verification_type: str, details: Optional[str] = None
    ):
        self.verification_type = verification_type
        self.details = details
        super().__init__(message)


class PreEligibilityError(Exception):
    def __init__(
        self,
        message: str,
        required_params: tuple[str, ...],
    ):
        self.required_params = required_params
        super().__init__(message)


class EligibilityFeaturesQueryError(Exception):
    def __init__(
        self,
        message: str,
        required_params: tuple[str, ...],
    ):
        self.required_params = required_params
        super().__init__(message)


class EnterpriseVerificationQueryError(EnterpriseVerificationError):
    def __init__(
        self,
        message: str,
        verification_type: str,
        required_params: tuple[str, ...],
    ):
        self.required_params = required_params
        super().__init__(message=message, verification_type=verification_type)


class EnterpriseVerificationConfigurationError(EnterpriseVerificationError):
    def __init__(
        self,
        message: str,
        verification_type: str,
        settings: repository.EnterpriseEligibilitySettings,
    ):
        self.settings = settings
        super().__init__(message, verification_type=verification_type)


class EnterpriseVerificationFailedError(EnterpriseVerificationError):
    ...


class EnterpriseVerificationRetrievalError(EnterpriseVerificationError):
    def __init__(
        self,
        message: str,
        user_id: int,
        organization_id: int | None = None,
        active_verifications_only: bool | None = False,
        details: Optional[str] = None,
    ):
        self.user_id = user_id
        self.organization_id = organization_id
        self.active_verifications_only = active_verifications_only
        self.details = details
        super().__init__(message=message, verification_type="")


class EnterpriseVerificationCreationError(EnterpriseVerificationError):
    def __init__(
        self,
        message: str,
        verification_type: str,
        user_id: int,
        eligibility_member_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "eligibility_member_id" (default has type "None", argument has type "int")
        eligibility_member_ids: List[int] = None,  # type: ignore[assignment]
        details: Optional[str] = None,
    ):
        self.verification_type = verification_type
        self.user_id = user_id
        self.eligibility_member_id = eligibility_member_id
        self.eligibility_member_ids = eligibility_member_ids
        self.details = details
        super().__init__(message, verification_type)


class EnterpriseVerificationConflictError(EnterpriseVerificationError):
    def __init__(
        self,
        message: str,
        verification_type: str,
        given_user_id: int,
        claiming_user_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "claiming_user_id" (default has type "None", argument has type "int")
        employee_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "employee_id" (default has type "None", argument has type "int")
        eligibility_member_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "eligibility_member_id" (default has type "None", argument has type "int")
    ):
        self.given_user_id = given_user_id
        self.claiming_user_id = claiming_user_id
        self.employee_id = employee_id
        self.eligibility_member_id = eligibility_member_id
        super().__init__(message, verification_type)


class EnterpriseVerificationFilelessError(EnterpriseVerificationError):
    def __init__(
        self,
        message: str,
        verification_type: str,
        user_id: int,
        organization_id: int,
        unique_corp_id: str,
        dependent_id: str,
    ):
        self.user_id = user_id
        self.organization_id = organization_id
        self.unique_corp_id = unique_corp_id
        self.dependent_id = dependent_id
        super().__init__(message, verification_type)


class EnterpriseVerificationOverEligibilityError(EnterpriseVerificationError):
    def __init__(
        self,
        message: str,
        verification_type: str,
        user_id: int,
        orgs_and_members: List[int],  # type: ignore[assignment] # Incompatible default for argument "eligibility_member_id" (default has type "None", argument has type "int")
        details: Optional[str] = None,
    ):
        self.verification_type = verification_type
        self.user_id = user_id
        self.orgs_and_members = orgs_and_members
        self.details = details
        super().__init__(message, verification_type)


class EligibilityTestMemberCreationError(Exception):
    def __init__(
        self,
        message: str,
    ):
        super().__init__(message)


# endregion errors


def get_verification_type_from_eligibility_type(
    eligibility_type: repository.OrganizationEligibilityType,
) -> VerificationTypeT | None:
    return _ELIGIBILITY_TYPE_TO_VERIFICATION_TYPE.get(eligibility_type)


_ELIGIBILITY_TYPE_TO_VERIFICATION_TYPE: dict[
    repository.OrganizationEligibilityType, VerificationTypeT
]
_ELIGIBILITY_TYPE_TO_VERIFICATION_TYPE = {
    repository.OrganizationEligibilityType.CLIENT_SPECIFIC: "client_specific",
    repository.OrganizationEligibilityType.STANDARD: "standard",
    repository.OrganizationEligibilityType.ALTERNATE: "alternate",
    repository.OrganizationEligibilityType.HEALTHPLAN: "multistep",
    repository.OrganizationEligibilityType.FILELESS: "fileless",
}


# The following `member_to_employee`, `_extract_address`, `_Address` is moved from translate.py
# Those are only used by `associate_user_id_to_members` and should be cleaned up once we migrate away from oe/uoe
# TODO : remove the following once we remove the associate_user_id_to_members call
def member_to_employee(
    member: model.EligibilityMember,
    *,
    employee: Optional[enterprise.OrganizationEmployee] = None,
) -> enterprise.OrganizationEmployee:
    employee = employee or enterprise.OrganizationEmployee()
    employee.organization_id = member.organization_id
    employee.eligibility_member_id = member.id or None
    employee.json = member.record
    employee.email = member.email
    employee.date_of_birth = member.date_of_birth
    employee.first_name = member.first_name
    employee.last_name = member.last_name
    employee.work_state = member.work_state
    employee.unique_corp_id = member.unique_corp_id
    employee.dependent_id = member.dependent_id
    employee.deleted_at = None
    employee.address = _extract_address(member)
    employee.eligibility_member_2_id = member.member_2_id or None
    employee.eligibility_member_2_version = member.member_2_version or None
    return employee


def _extract_address(member: model.EligibilityMember) -> _Address:
    return _Address(
        employee_first_name=member.record.get("employee_first_name", member.first_name),
        employee_last_name=member.record.get("employee_last_name", member.last_name),
        address_1=member.record.get("address_1", ""),
        address_2=member.record.get("address_2", ""),
        city=member.record.get("city", ""),
        state=member.record.get("state", member.work_state),
        zip_code=member.record.get("zip_code", ""),
        country=member.record.get("country", ""),
    )


def _empty_or_equal(a: str | None, b: str | None) -> bool:
    """
    Check if the input values are both empty ("" or None) or they are the same string
    If both are valid strings, strip leading/trailing whitespace and do case-insensitive check
    """
    if not a and not b:
        return True

    if not a or not b:
        return False

    return a.strip().lower() == b.strip().lower()


def compare_verifications(
    *,
    user_id: int,
    previous_verification: model.EligibilityVerification | None,
    new_verification: model.EligibilityVerification | None,
) -> bool:
    """
    compare verification from get_verification_for_user & get_verification_for_user_and_org
    """
    if not previous_verification and not new_verification:
        return True

    if not previous_verification or not new_verification:
        logger.info(
            "verification comparison - mismatch",
            user_id=user_id,
            previous_verification_id={
                (
                    str(previous_verification.verification_id)
                    if previous_verification
                    else None
                )
            },
            new_verification_id={
                str(new_verification.verification_id) if new_verification else None
            },
        )
        return False

    previous_attrs = vars(previous_verification)
    new_attrs = vars(new_verification)
    differences = []
    for field in previous_attrs:
        if previous_attrs[field] != new_attrs[field]:
            differences.append((field, previous_attrs[field], new_attrs[field]))
    if not differences:
        return True
    else:
        logger.info(
            "verification comparison - mismatch",
            user_id=user_id,
            previous_verification_id={
                (
                    str(previous_verification.verification_id)
                    if previous_verification
                    else None
                )
            },
            new_verification_id={
                str(new_verification.verification_id) if new_verification else None
            },
            differences=differences,
        )
        return False


def _log_oe_verification_match_info(
    user_id: int, oe: OrganizationEmployee, verification: model.EligibilityVerification
) -> None:
    # OE and verification found
    organization_id_valid: bool = oe.organization_id == verification.organization_id
    unique_corp_id_valid: bool = oe.unique_corp_id == verification.unique_corp_id
    dependent_id_valid: bool = _empty_or_equal(
        oe.dependent_id, verification.dependent_id
    )
    first_name_valid: bool = _empty_or_equal(oe.first_name, verification.first_name)
    last_name_valid: bool = _empty_or_equal(oe.last_name, verification.last_name)
    date_of_birth_valid: bool = oe.date_of_birth == verification.date_of_birth
    email_valid: bool = _empty_or_equal(oe.email, verification.email)
    work_state_valid: bool = oe.work_state == verification.work_state

    logger.info(
        "OE and verification found",
        user_id=user_id,
        organization_employee_id={oe.id},
        verification_id={str(verification.verification_id)},
        organization_id_valid=organization_id_valid,
        unique_corp_id_valid={unique_corp_id_valid},
        dependent_id_valid={dependent_id_valid},
        first_name_valid={first_name_valid},
        last_name_valid={last_name_valid},
        date_of_birth_valid={date_of_birth_valid},
        email_valid={email_valid},
        work_state_valid={work_state_valid},
    )


def check_health_profile(
    sender_user_id: int,
    recipient: User,
    invitation_id: str,
    partner_track_name: TrackName,
) -> bool:
    """
    Some tracks require information to be set in the user's health_profile
    before the user may enroll in that track. Here, we forcibly update the
    user's health_profile with information from their partner if possible.

    Returns True if the user may enroll in the track (i.e. the information
    was already present in the user's health_profile OR we were able to
    update the user's health_profile with information from their partner's
    health_profile). Returns False otherwise.
    """
    can_enroll = True
    message = "Share a Wallet -"
    if partner_track_name in (
        TrackName.PREGNANCY,
        TrackName.PARTNER_PREGNANT,
        TrackName.POSTPARTUM,
        TrackName.PARTNER_NEWPARENT,
    ):
        recipient_health_profile = (
            db.session.query(HealthProfile)
            .filter(HealthProfile.user_id == recipient.id)
            .one()
        )
        if partner_track_name in (TrackName.PREGNANCY, TrackName.PARTNER_PREGNANT):
            # Check that the "due_date" is set in the recipient's health profile
            # If it is not set in the recipient's health profile, then we will
            # set it in the recipient's health profile to be the same as what
            # is in the sender's health profile.
            if recipient_health_profile.json.get("due_date"):
                return can_enroll
            else:
                message += " Missing due_date in health profile."
                partner_health_profile = (
                    db.session.query(HealthProfile)
                    .filter(HealthProfile.user_id == sender_user_id)
                    .one()
                )
                if partner_health_profile.json.get("due_date"):
                    recipient_health_profile.json[
                        "due_date"
                    ] = partner_health_profile.json["due_date"]
                    db.session.add(recipient_health_profile)
                    db.session.commit()
                    message += " Setting equal to partner's due_date."
                else:
                    can_enroll = False
        elif partner_track_name in (TrackName.POSTPARTUM, TrackName.PARTNER_NEWPARENT):
            # Check that the "children" is set in the recipient's health profile
            # If it is not set in the recipient's health profile, then we will
            # set it in the recipient's health profile to be the same as what
            # is in the sender's health profile.
            if recipient_health_profile.json.get("children"):
                return can_enroll
            else:
                message += " Missing children in health profile."
                partner_health_profile = (
                    db.session.query(HealthProfile)
                    .filter(HealthProfile.user_id == sender_user_id)
                    .one()
                )
                if partner_health_profile.json.get("children"):
                    recipient_health_profile.json[
                        "children"
                    ] = partner_health_profile.json["children"]
                    db.session.add(recipient_health_profile)
                    db.session.commit()
                    message += " Setting equal to partner's children."
                else:
                    can_enroll = False
    else:
        return True
    logger.info(
        message,
        invitation_id=invitation_id,
        user_id=str(recipient.id),
        sender_user_id=str(sender_user_id),
        can_enroll=str(can_enroll),
        partner_track_name=str(partner_track_name),
    )
    return can_enroll


def successfully_enroll_partner(
    sender_user_id: int, recipient: User, invitation_id: str
) -> bool:
    """
    Enrolls the partner of the sender in the partner tracks of the sender.
    Returns True if the enrollment was successful.
    Returns False otherwise.
    """
    try:
        # Make sure the sender has at least one active MemberTrack
        inviter: User = User.query.get(sender_user_id)
        inviter_tracks = inviter.active_tracks
        if not inviter_tracks:
            # No default tracks to enroll the recipient in.
            logger.info(
                "Share a Wallet - Inviter is not enrolled in a track",
                invitation_id=invitation_id,
                user_id=sender_user_id,
            )
            return True

        if recipient.active_tracks:
            # The recipient is already enrolled in tracks.
            logger.info(
                "Share a Wallet - Recipient is already enrolled in tracks.",
                invitation_id=invitation_id,
                user_id=recipient.id,
            )
            return True

        # Verify that the inviter is still eligible
        verification_svc: EnterpriseVerificationService = get_verification_service()
        verification: model.EligibilityVerification | None = (
            verification_svc.get_verification_for_user(
                user_id=sender_user_id,
                active_eligibility_only=True,
            )
        )
        if verification is None:
            raise lifecycle.MissingEmployeeError(
                f"No enterprise verification found for user_id: {sender_user_id}"
            )

        # We currently limit users to being enrolled in 2 tracks as long as one
        # as one track is Parenting and Pediatrics. Otherwise, a user is limited
        # to one track.

        # Create a partner verification for the recipient
        # inviting_user==sender_user,  invited_user==recipient
        partner_verification = verification_svc.generate_verification_for_user(
            user_id=recipient.id,
            verification_type=verification.verification_type,
            organization_id=verification.organization_id,
            unique_corp_id=verification.unique_corp_id,
            dependent_id=verification.dependent_id,
            first_name=recipient.first_name,
            last_name=recipient.last_name,
            eligibility_member_id=verification.eligibility_member_id,
            additional_fields={"inviting_user_id": sender_user_id},
            verification_session=uuid.uuid4().hex,
        )
        if not partner_verification:
            logger.error(
                "Share a Wallet - Unable to create partner verification",
                inviting_user_id=str(sender_user_id),
                invited_user_id=str(recipient.id),
                invitation_id=invitation_id,
            )
            return False

        for member_track in inviter_tracks:
            # If there is no partner track, then we enroll the partner
            # in the same track.
            partner_track_name: TrackName = (
                member_track.partner_track and member_track.partner_track.name
            ) or member_track._config.name
            # Perform the health profile check.
            if not check_health_profile(
                sender_user_id, recipient, invitation_id, partner_track_name
            ):
                logger.info(
                    "Share a Wallet - cannot enroll partner in track.",
                    partner_track=str(partner_track_name),
                    partner_user_id=str(recipient.id),
                )
                return False

            # Now we need to enroll the invitation recipient in this track.
            lifecycle.initiate(
                user=recipient,
                track=partner_track_name,
                is_employee=False,
                change_reason=ChangeReason.API_CLAIM_WALLET_PARTNER_INVITE,
                eligibility_organization_id=verification.organization_id,
            )
            logger.info(
                "Share a Wallet - successfully enrolled partner in track",
                partner_track=str(partner_track_name),
                partner_user_id=str(recipient.id),
            )
        enterprise_user_post_setup.delay(recipient.id)
        return True
    except Exception as exc:
        logger.error(
            "Share a Wallet - Error while enrolling recipient in tracks.",
            user_id=str(recipient.id),
            exception=str(exc),
            traceback=format_exc(),
        )
        return False


class _Address(TypedDict):
    employee_first_name: str
    employee_last_name: str
    address_1: str
    address_2: str
    city: str
    state: str
    zip_code: str
    country: str


# end region
