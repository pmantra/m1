from __future__ import annotations

import dataclasses
import datetime
import functools
import hashlib
from typing import List, NamedTuple, Optional

import ddtrace.ext
import sqlalchemy as sa
import sqlalchemy.orm.scoping
from rq.serializers import DefaultSerializer
from sqlalchemy.sql import func

from authn.domain import model as authn_model
from authn.domain import service as authn
from caching.redis import RedisTTLCache
from common import stats
from eligibility.e9y import grpc_service, model
from eligibility.e9y.grpc_service import channel
from models.enterprise import (
    Organization,
    OrganizationEligibilityField,
    OrganizationEligibilityType,
    OrganizationEmailDomain,
    OrganizationEmployee,
    OrganizationExternalID,
    OrganizationType,
    UserOrganizationEmployee,
)
from models.tracks import ClientTrack
from storage import connection
from utils import log as logging

logger = logging.logger(__name__)

__all__ = (
    "OrganizationEmployeeRepository",
    "OrganizationRepository",
    "EligibilityMemberRepository",
    "WalletEnablementRepository",
    "OrganizationAssociationSettings",
    "EnterpriseEligibilitySettings",
    "EligibilityField",
    "EmailDomain",
    "OrganizationMeta",
    "ProductEnablement",
    "OrgIdentity",
    "EmployeeInfo",
)


trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class OrganizationEmployeeRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    def get(self, *, id: int) -> OrganizationEmployee | None:
        return self.session.query(OrganizationEmployee).get(id)

    @trace_wrapper
    def create(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        date_of_birth: datetime.date,
        organization_id: int,
        unique_corp_id: str,
        dependent_id: str = "",
        **json,
    ) -> OrganizationEmployee:
        employee = OrganizationEmployee(
            first_name=first_name,
            last_name=last_name,
            email=email,
            date_of_birth=date_of_birth,
            organization_id=organization_id,
            unique_corp_id=unique_corp_id,
            dependent_id=dependent_id,
            json=json,
        )
        self.session.add(employee)
        self.session.flush()
        return employee

    @trace_wrapper
    def get_by_org_id_email_dob(
        self, organization_id: int, email: str, date_of_birth: datetime.date
    ) -> OrganizationEmployee | None:
        query = self.session.query(OrganizationEmployee).filter(
            OrganizationEmployee.email == sa.bindparam("email"),
            OrganizationEmployee.date_of_birth == sa.bindparam("date_of_birth"),
            OrganizationEmployee.organization_id == sa.bindparam("organization_id"),
        )
        result = query.params(
            organization_id=organization_id,
            email=email,
            date_of_birth=date_of_birth,
        ).first()
        return result

    @trace_wrapper
    def get_by_e9y_member_id(self, *, member_id: int) -> OrganizationEmployee | None:
        """Get an org association by the e9y member ID provided."""
        query = self.session.query(OrganizationEmployee).filter(
            OrganizationEmployee.eligibility_member_id == sa.bindparam("member_id")
        )
        result = query.params(member_id=member_id).first()
        return result

    @trace_wrapper
    def get_by_org_identity(
        self,
        *,
        unique_corp_id: str,
        dependent_id: str,
        organization_id: int,
    ) -> OrganizationEmployee | None:
        """Get an org association by the org identity provided."""
        query = self.session.query(OrganizationEmployee).filter(
            OrganizationEmployee.unique_corp_id == sa.bindparam("unique_corp_id"),
            OrganizationEmployee.dependent_id == sa.bindparam("dependent_id"),
            OrganizationEmployee.organization_id == sa.bindparam("organization_id"),
        )
        result = query.params(
            unique_corp_id=unique_corp_id,
            dependent_id=dependent_id,
            organization_id=organization_id,
        ).first()
        return result

    @trace_wrapper
    def get_by_e9y_member_id_or_org_identity(
        self,
        *,
        member_ids: List[int],
        org_identities: List[OrgIdentity],
    ) -> List[OrganizationEmployee] | None:
        """Get a list organization employee,

        either by the e9y member ID or the org identity information provided.
        """
        member_ids = [] if member_ids is None else member_ids
        org_identities = [] if org_identities is None else org_identities

        subquery = (
            self.session.query(
                OrganizationEmployee.organization_id,
                func.max(OrganizationEmployee.id).label("id"),
            )
            .filter(
                sa.or_(
                    OrganizationEmployee.eligibility_member_id.in_(
                        member_ids
                        # sa.bindparam("member_ids", expanding=True),
                    ),
                    sa.tuple_(
                        OrganizationEmployee.unique_corp_id,
                        OrganizationEmployee.dependent_id,
                        OrganizationEmployee.organization_id,
                    ).in_(org_identities)
                    # sa.bindparam("org_identities", expanding=True)),
                )
            )
            .group_by(OrganizationEmployee.organization_id)
            .subquery()
        )

        query = self.session.query(OrganizationEmployee).join(
            subquery,
            (OrganizationEmployee.organization_id == subquery.c.organization_id)
            & (OrganizationEmployee.id == subquery.c.id),
        )
        results = query.params(
            member_ids=member_ids, org_identities=org_identities
        ).all()
        return results

    @trace_wrapper
    def get_by_user_id(
        self,
        *,
        user_id: int,
    ) -> List[OrganizationEmployee]:
        """
        Get all active org associations for a user,
        """
        query = (
            self.session.query(OrganizationEmployee)
            .join(UserOrganizationEmployee)
            .filter(
                # Only active relationships, so end_at is null.
                UserOrganizationEmployee.ended_at == sa.null(),
                # For the given user id.
                UserOrganizationEmployee.user_id == sa.bindparam("user_id"),
            )
            .order_by(UserOrganizationEmployee.id.desc())
        )
        result = query.params(
            user_id=user_id,
        ).all()
        return result

    @trace_wrapper
    def associate_to_user_id(
        self, *, user_id: int, employees: List[OrganizationEmployee]
    ) -> List[OrganizationEmployee]:
        """Associate a user_id to a given "employee" (enterprise member record)."""
        self.session.add_all(employees)
        self.session.flush(employees)

        uoe_list = [
            UserOrganizationEmployee(
                user_id=user_id,
                organization_employee_id=employee.id,
            )
            for employee in employees
        ]
        self.session.add_all(uoe_list)
        self.session.flush(uoe_list)

        return employees

    @trace_wrapper
    def get_existing_claims(self, *, id: int) -> set[int]:
        """Get all user IDs which are currently claiming this employee ID."""
        existing = (
            self.session.query(UserOrganizationEmployee.user_id)
            .filter(
                sa.and_(
                    UserOrganizationEmployee.organization_employee_id == id,
                    sa.or_(
                        UserOrganizationEmployee.ended_at == None,
                        UserOrganizationEmployee.ended_at
                        > datetime.datetime.now(tz=datetime.timezone.utc),
                    ),
                )
            )
            .all()
        )
        return {e.user_id for e in existing}

    @trace_wrapper
    def get_association_settings(
        self, *, id: int
    ) -> OrganizationAssociationSettings | None:
        """Get the member-level and organization-level settings

        which determine under what conditions a user may be associated to a member.
        """
        query = (
            self.session.query(
                OrganizationEmployee.organization_id,
                OrganizationEmployee.json,
                Organization.employee_only,
                Organization.medical_plan_only,
            )
            .filter(OrganizationEmployee.id == sa.bindparam("id"))
            .join(Organization, Organization.id == OrganizationEmployee.organization_id)
        )
        settings = query.params(id=id).first()
        if not settings:
            return None
        return OrganizationAssociationSettings(
            # The organization ID this member record belongs to.
            organization_id=settings.organization_id,
            # Whether this record may only be associated to a single user,
            #   at the org-level.
            employee_only=settings.employee_only,
            # When combined with `beneficiaries_enabled` (member-level flag),
            #   whether this record may only be associated to single user.
            medical_plan_only=settings.medical_plan_only,
            beneficiaries_enabled=settings.json.get("beneficiaries_enabled", False),
        )


class UserOrganizationEmployeeRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    def get(self, *, id: int) -> UserOrganizationEmployee | None:
        return self.session.query(UserOrganizationEmployee).get(id)

    @trace_wrapper
    def get_for_organization_employee_id(
        self, organization_employee_id: int
    ) -> List[UserOrganizationEmployee] | List:
        query = self.session.query(UserOrganizationEmployee).filter(
            UserOrganizationEmployee.organization_employee_id
            == sa.bindparam("organization_employee_id")
        )
        return query.params(organization_employee_id=organization_employee_id).all()

    @trace_wrapper
    def reset_user_associations(self, user_id: int, organization_employee_ids: List[int]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        query = self.session.query(UserOrganizationEmployee).filter(
            UserOrganizationEmployee.organization_employee_id.in_(
                sa.bindparam("organization_employee_ids", expanding=True)
            ),
            UserOrganizationEmployee.user_id == sa.bindparam("user_id"),
        )
        user_organization_employees: List[UserOrganizationEmployee] = query.params(
            user_id=user_id, organization_employee_ids=organization_employee_ids
        ).all()

        if not user_organization_employees or len(user_organization_employees) != len(
            organization_employee_ids
        ):
            logger.warning(
                "not all user_organization_employees to reset found",
                user_id=user_id,
                organization_employee_ids=organization_employee_ids,
            )
            return

        for uoe in user_organization_employees:
            if uoe.ended_at:
                uoe.ended_at = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "Column[Optional[datetime]]")


class OrganizationAssociationSettings(NamedTuple):
    organization_id: int
    employee_only: bool
    medical_plan_only: bool
    beneficiaries_enabled: bool


class OrganizationRepository:
    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        sso: authn.SSOService = None,  # type: ignore[assignment] # Incompatible default for argument "sso" (default has type "None", argument has type "SSOService")
    ):
        self.session = session or connection.db.session
        self.sso = sso or authn.SSOService(session=self.session)

    @trace_wrapper
    def get_organization_by_user_external_identities(
        self, *, user_id: int, identities: list[authn_model.UserExternalIdentity] = None  # type: ignore[assignment] # Incompatible default for argument "identities" (default has type "None", argument has type "List[UserExternalIdentity]")
    ) -> tuple[None, None] | tuple[authn_model.UserExternalIdentity, OrganizationMeta]:
        # Locate the identites for the user ID.
        identities = identities or self.sso.fetch_identities(user_id=user_id)
        # If there aren't any identities, we can't try to use them for verification...
        if not identities:
            return None, None

        external_id_idp_pairs = [
            (i.identity_provider_id, i.external_organization_id) for i in identities
        ]
        org_ids_by_external_id = {
            o.external_id: o
            for o in self.get_orgs_by_external_ids(*external_id_idp_pairs)
        }
        # If we have more than 1 potential organization,
        #   we don't know which one to use.
        # FIXME: why don't we just try them all? Is this a real use-case?
        if not 0 < len(org_ids_by_external_id) <= 1:
            return None, None

        external_id, org_meta = org_ids_by_external_id.popitem()
        # Get the identity we used to locate this organization.
        # NOTE: This feels like something we could do via the DB.
        #   And you'd be correct, at this current time.
        #   HOWEVER, SSO will eventually not live in the same DB,
        #   so we're adapting the logic in-place to handle this.
        identity = next(
            i for i in identities if i.external_organization_id == external_id
        )
        return identity, org_meta

    @trace_wrapper
    def get_orgs_by_external_ids(
        self, *idp_external_id_pairs: tuple[int, str]
    ) -> list[OrganizationMeta]:
        """Get all (external_id, organization_id) pairs corresponding to the

        provided (identity_provider_id, external_id) pairs.
        """
        query = (
            self.session.query(
                OrganizationExternalID.organization_id,
                sa.func.coalesce(Organization.display_name, Organization.name).label(
                    "organization_name"
                ),
                OrganizationExternalID.external_id,
                OrganizationExternalID.identity_provider_id,
            )
            .join(
                Organization, Organization.id == OrganizationExternalID.organization_id
            )
            .filter(
                sa.tuple_(
                    OrganizationExternalID.identity_provider_id,
                    OrganizationExternalID.external_id,
                ).in_(sa.bindparam("idp_external_id_pairs", expanding=True))
            )
        )
        org_ids = query.params(idp_external_id_pairs=idp_external_id_pairs).all()
        return org_ids

    def get_active_enablements(self, *, organization_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Get all active & launched product enablements for a given organization."""
        tracks = (
            self.session.query(
                ClientTrack.id,
                ClientTrack.track,
                ClientTrack.active,
                ClientTrack.launch_date,
                ClientTrack.length_in_days,
            )
            .filter(
                ClientTrack.organization_id == organization_id,
                ClientTrack.active == sa.true(),
                sa.func.coalesce(ClientTrack.launch_date, sa.func.current_date())
                <= sa.func.current_date(),
            )
            .all()
        )
        enablements = [
            ProductEnablement(
                product=t.track,
                active=t.active,
                launch_date=t.launch_date,
                length_in_days=t.length_in_days,
            )
            for t in tracks
        ]
        # Hacking in BMS.
        bms_enabled = (
            self.session.query(Organization.bms_enabled)
            .filter_by(id=organization_id)
            .scalar()
        )
        if bms_enabled:
            enablements.append(
                ProductEnablement(product="breast-milk-shipping", active=True)
            )
        return enablements

    def get_enablement(
        self, *, organization_id: int, product: str
    ) -> ProductEnablement | None:
        """Get a configured product enablement for an organization by name.

        A `ProductEnablement` represents a generic product configuration which an
        organization has purchased from Maven.
        """
        if product == "breast-milk-shipping":
            # Hacking in BMS.
            bms_enabled_query = self.session.query(Organization.bms_enabled).filter(
                Organization.id == sa.bindparam("organization_id")
            )
            enabled: bool | None = bms_enabled_query.params(
                organization_id=organization_id
            ).scalar()
            enablement = (
                None
                if enabled is None
                else ProductEnablement(product=product, active=enabled)
            )
            return enablement

        # Query for a track matching the provided `product` name, for this organization.
        track_query = self.session.query(
            ClientTrack.track.label("product"),
            ClientTrack.active,
            ClientTrack.launch_date,
            ClientTrack.length_in_days,
        ).filter(
            ClientTrack.organization_id == sa.bindparam("organization_id"),
            ClientTrack.track == sa.bindparam("product"),
        )
        track = track_query.params(
            organization_id=organization_id, product=product
        ).first()
        enablement = None if track is None else ProductEnablement(**track._asdict())
        return enablement

    def get_eligibility_settings(
        self, *, organization_id: int
    ) -> EnterpriseEligibilitySettings | None:
        """Get the organization-level settings for verifying individuals."""
        filter = Organization.id == organization_id
        return self._get_eligibility_settings_with_filter(filter=filter)

    def get_eligibility_settings_by_email(
        self,
        *,
        company_email: str,
    ) -> EnterpriseEligibilitySettings | None:
        domain = self.get_email_domain(company_email)
        filter = OrganizationEmailDomain.domain == domain
        join = (
            OrganizationEmailDomain,
            Organization.id == OrganizationEmailDomain.organization_id,
        )
        return self._get_eligibility_settings_with_filter(
            join,
            filter=filter,
        )

    def get_organization_by_name(self, *, name: str) -> Organization | None:
        return (
            self.session.query(Organization)
            .filter(
                (Organization.name == name) | (Organization.display_name == name),
                Organization.internal_type != OrganizationType.TEST,
            )
            .order_by(Organization.id.asc())
            .first()
        )

    def get_by_organization_id(self, *, org_id: int) -> Organization | None:
        return self.session.query(Organization).get(org_id)

    @staticmethod
    @functools.lru_cache(maxsize=2000)
    def get_email_domain(email: str) -> str:
        domain = email.rsplit("@", maxsplit=1)[-1]
        return domain

    def _get_eligibility_settings_with_filter(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, *joins, filter
    ) -> EnterpriseEligibilitySettings | None:
        query = self.session.query(
            Organization.id.label("organization_id"),
            Organization.marketing_name.label("organization_name"),
            Organization.name.label("organization_shortname"),
            Organization.icon.label("organization_logo"),
            Organization.eligibility_type,
            Organization.employee_only,
            Organization.medical_plan_only,
            Organization.activated_at,
        ).filter(filter)
        if joins:
            query = query.join(*joins)

        org_config = query.first()
        if not org_config:
            return None

        eligibility_fields = (
            self.session.query(
                OrganizationEligibilityField.name,
                OrganizationEligibilityField.label,
            )
            .filter_by(organization_id=org_config.organization_id)
            .all()
        )

        email_domains = (
            self.session.query(
                OrganizationEmailDomain.domain,
                OrganizationEmailDomain.eligibility_logic,
            )
            .filter_by(organization_id=org_config.organization_id)
            .all()
        )
        return EnterpriseEligibilitySettings(
            **org_config._asdict(),
            fields=[
                EligibilityField(name=ef.name, label=ef.label)
                for ef in eligibility_fields
            ],
            email_domains=[
                EmailDomain(
                    domain=ed.domain,
                    eligibility_type=OrganizationEligibilityType(ed.eligibility_logic),
                )
                for ed in email_domains
            ],
        )


class EligibilityMemberRepository:
    """A lightweight repository wrapper for locating enterprise eligibility records."""

    def __init__(self) -> None:
        self.grpc = grpc_service
        self.grpc_connection = channel()
        self.verification_cache = RedisTTLCache(
            namespace="e9y_verifications_for_user",
            ttl_in_seconds=60,
            serializer=DefaultSerializer,
            pod_name=stats.PodNames.ELIGIBILITY,
        )
        self.verification_overeligibility_cache = RedisTTLCache(
            namespace="e9y_verifications_for_user_overeligibility",
            ttl_in_seconds=60,
            serializer=DefaultSerializer,
            pod_name=stats.PodNames.ELIGIBILITY,
        )

    def _is_verification_live(
        self, verification: model.EligibilityVerification
    ) -> bool:
        """
        Check if a verification is currently live based on its effective_range.
        live means that underlying member eligibility record is active.
        Lower bound is inclusive, upper bound is exclusive.

        Args:
            verification: The verification to check

        Returns:
            bool: True if the verification is currently live, False otherwise
        """
        if not verification.effective_range:
            return False

        today = datetime.date.today()
        effective_range = verification.effective_range

        # Check if today falls within the effective range
        # Lower bound is inclusive
        is_within_lower = (
            effective_range.lower is None or effective_range.lower <= today
        )

        # Upper bound is exclusive
        is_within_upper = effective_range.upper is None or effective_range.upper > today

        return is_within_lower and is_within_upper

    def _build_single_verification_cache_key(
        self,
        *,
        user_id: int,
        active_eligibility_only: bool,
    ) -> tuple[int, bool]:
        """
        Build a cache key for a single verification.

        Args:
            user_id: The user ID
            active_eligibility_only: Whether to only return active verifications

        Returns:
            tuple[int, bool]: The cache key
        """
        return (user_id, active_eligibility_only)

    def _build_multiple_verifications_cache_key(
        self,
        *,
        user_id: int,
        organization_ids: List[int] | None,
        active_verifications_only: bool,
    ) -> str:
        """
        Build a cache key for multiple verifications.

        Args:
            user_id: The user ID
            organization_ids: List of organization IDs to filter by
            active_verifications_only: Whether to only return active verifications

        Returns:
            str: The cache key hash
        """
        # Deduplicate and sort organization IDs for consistent cache keys
        org_ids_str = "None"
        if organization_ids is not None:
            dedup_organization_ids = list({id for id in organization_ids})
            org_ids_str = str(sorted(dedup_organization_ids))

        raw_key = ",".join([str(user_id), org_ids_str, str(active_verifications_only)])
        return hashlib.sha1(raw_key.encode()).hexdigest()

    def _update_single_verification_cache(
        self,
        *,
        user_id: int,
        verification: model.EligibilityVerification,
        skip_live_check: bool = False,
    ) -> None:
        """
        Update the single verification cache with a verification. For newly created verifications (skip_live_check=True),
        we cache with both keys since they are guaranteed to be live. For retrieved verifications, we check if they are live.
        """
        # Always cache with False (all verifications)
        self.verification_cache.add(
            self._build_single_verification_cache_key(
                user_id=user_id,
                active_eligibility_only=False,
            ),
            verification,
        )

        # For new verifications, we know they are live, so skip the check
        if skip_live_check or self._is_verification_live(verification):
            self.verification_cache.add(
                self._build_single_verification_cache_key(
                    user_id=user_id,
                    active_eligibility_only=True,
                ),
                verification,
            )

    def _update_multiple_verifications_cache(
        self,
        *,
        user_id: int,
        verifications: List[model.EligibilityVerification],
        organization_ids: List[int] | None = None,
        skip_live_check: bool = False,
    ) -> None:
        """
        Update the multiple verifications cache.

        Args:
            user_id: The user ID
            verifications: List of verifications to cache
            organization_ids: Optional list of organization IDs to filter by
            skip_live_check: Whether to skip the liveliness check (e.g. for new verifications)
        """
        if not verifications:
            return

        # Always cache all verifications
        self.verification_overeligibility_cache.add(
            self._build_multiple_verifications_cache_key(
                user_id=user_id,
                organization_ids=organization_ids,
                active_verifications_only=False,
            ),
            verifications,
        )

        # Always cache active verifications
        live_verifications = (
            verifications
            if skip_live_check
            else [v for v in verifications if self._is_verification_live(v)]
        )
        self.verification_overeligibility_cache.add(
            self._build_multiple_verifications_cache_key(
                user_id=user_id,
                organization_ids=organization_ids,
                active_verifications_only=True,
            ),
            live_verifications,
        )

    def get_by_member_id(
        self,
        *,
        member_id: int,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityMember | None:
        """Get an E9y Member record by member ID."""

        return self.grpc.member_id_search(
            member_id=member_id,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

    def get_by_org_identity(
        self,
        *,
        organization_id: int,
        unique_corp_id: str,
        dependent_id: str = "",
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityMember | None:
        """Get an E9y Member record by org identity."""

        return self.grpc.org_identity_search(
            unique_corp_id=unique_corp_id,
            dependent_id=dependent_id,
            organization_id=organization_id,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

    def get_by_basic_verification(
        self,
        *,
        first_name: str,
        last_name: str,
        date_of_birth: datetime.date,
        user_id: Optional[int] = None,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> List[model.EligibilityMember] | None:
        """Get E9y Member records by basic verification."""

        return self.grpc.basic(
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            user_id=user_id,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

    def get_by_healthplan_verification(
        self,
        *,
        first_name: str,
        last_name: str,
        date_of_birth: datetime.date,
        subscriber_id: Optional[str] = None,
        dependent_date_of_birth: Optional[datetime.date] = None,
        employee_first_name: Optional[str] = None,
        employee_last_name: Optional[str] = None,
        user_id: Optional[int] = None,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityMember | None:
        """Get E9y Member records by healthplan verification."""

        return self.grpc.healthplan(
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            subscriber_id=subscriber_id,
            dependent_date_of_birth=dependent_date_of_birth,
            employee_first_name=employee_first_name,
            employee_last_name=employee_last_name,
            user_id=user_id,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

    def get_by_employer_verification(
        self,
        date_of_birth: datetime.date,
        *,
        company_email: Optional[str] = None,
        dependent_date_of_birth: Optional[datetime.date] = None,
        employee_first_name: Optional[str] = None,
        employee_last_name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        work_state: Optional[str] = None,
        user_id: Optional[int] = None,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityMember | None:
        return self.grpc.employer(
            company_email=company_email,
            date_of_birth=date_of_birth,
            dependent_date_of_birth=dependent_date_of_birth,
            employee_first_name=employee_first_name,
            employee_last_name=employee_last_name,
            first_name=first_name,
            last_name=last_name,
            work_state=work_state,
            user_id=user_id,
            timeout=timeout,
            metadata=metadata,
        )

    def get_by_standard_verification(
        self,
        *,
        date_of_birth: datetime.date,
        company_email: str,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityMember | None:
        """Get an E9y Member record by "standard" verification."""

        return self.grpc.standard(
            date_of_birth=date_of_birth,
            company_email=company_email,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

    def get_by_alternate_verification(
        self,
        *,
        date_of_birth: datetime.date,
        first_name: str,
        last_name: str,
        work_state: str = None,  # type: ignore[assignment] # Incompatible default for argument "work_state" (default has type "None", argument has type "str")
        unique_corp_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "unique_corp_id" (default has type "None", argument has type "str")
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityMember | None:
        """Get an E9y Member record by "alternate" verification."""

        return self.grpc.alternate(
            date_of_birth=date_of_birth,
            first_name=first_name,
            last_name=last_name,
            unique_corp_id=unique_corp_id,
            work_state=work_state,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

    def get_by_overeligibility_verification(
        self,
        *,
        date_of_birth: datetime.date,
        first_name: str,
        last_name: str,
        user_id: Optional[int] = None,
        company_email: str = None,  # type: ignore[assignment] # Incompatible default for argument "company_email" (default has type "None", argument has type "str")
        unique_corp_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "unique_corp_id" (default has type "None", argument has type "str")
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> List[model.EligibilityMember] | None:
        """Get an E9y Member record by "overeligibility" verification."""

        return self.grpc.overeligibility(
            date_of_birth=date_of_birth,
            work_state="",
            first_name=first_name,
            last_name=last_name,
            unique_corp_id=unique_corp_id,
            company_email=company_email,
            user_id=str(user_id) if user_id else "",  # type: ignore[arg-type] # Argument "user_id" to "overeligibility" has incompatible type "str"; expected "int"
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

    def get_by_client_specific(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        *,
        date_of_birth: datetime.date,
        unique_corp_id,
        organization_id: int,
        is_employee: bool,
        dependent_date_of_birth: datetime.date | None = None,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityMember | None:
        """Get an E9y Member record by "client-specific" verification."""
        return self.grpc.client_specific(
            date_of_birth=date_of_birth,
            unique_corp_id=unique_corp_id,
            organization_id=organization_id,
            is_employee=is_employee,
            dependent_date_of_birth=dependent_date_of_birth,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

    def get_by_no_dob_verification(
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityMember | None:
        """
        Get an E9y Member record by "no-dob" verification.
        Only applicable to Organizations that dont send date of birth in census files
        """
        return self.grpc.no_dob_verification(
            email=email,
            first_name=first_name,
            last_name=last_name,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

    def get_by_member_details(
        self,
        *,
        user_id: int | None = None,
        first_name: str,
        last_name: str,
        date_of_birth: datetime.date,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.PreEligibilityResponse:
        """Get an E9y Member record(s) by member id, first name, last name and date of birth"""
        return self.grpc.member_search(  # type: ignore[return-value] # Incompatible return value type (got "Optional[PreEligibilityResponse]", expected "PreEligibilityResponse")
            user_id=user_id,  # type: ignore[arg-type] # Argument "user_id" to "member_search" has incompatible type "Optional[int]"; expected "int"
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

    def create_verification_for_user(
        self,
        *,
        user_id: int,
        verification_type: str,
        date_of_birth: datetime.date = None,  # type: ignore[assignment] # Incompatible default for argument "date_of_birth" (default has type "None", argument has type "date")
        email: str | None = "",
        first_name: str | None = "",
        last_name: str | None = "",
        work_state: str | None = "",
        unique_corp_id: str | None = None,
        dependent_id: str | None = None,
        organization_id: int | None = None,
        additional_fields: dict | None = None,
        eligibility_member_id: int | None = None,
        verification_session: str | None = None,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityVerification:
        """Generate a verification for a user"""

        verified_at = datetime.datetime.utcnow()

        verification, err = self.grpc.create_verification(
            user_id=user_id,
            verification_type=verification_type,
            organization_id=organization_id,  # type: ignore[arg-type] # Argument "organization_id" to "create_verification" has incompatible type "Optional[int]"; expected "int"
            unique_corp_id=unique_corp_id,
            dependent_id=dependent_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            work_state=work_state,
            date_of_birth=date_of_birth,
            eligibility_member_id=eligibility_member_id,
            additional_fields=additional_fields,
            verified_at=verified_at,
            verification_session=verification_session,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

        if err is not None:
            from eligibility.service import EnterpriseVerificationCreationError

            raise EnterpriseVerificationCreationError(
                "Error creating verification for user",
                verification_type=verification_type,
                user_id=user_id,
                eligibility_member_id=eligibility_member_id,  # type: ignore[arg-type] # Argument "eligibility_member_id" to "EnterpriseVerificationCreationError" has incompatible type "Optional[int]"; expected "int"
                details=err.details if err and hasattr(err, "details") else str(err),
            )

        if verification is not None:
            self._update_single_verification_cache(
                user_id=user_id,
                verification=verification,
                skip_live_check=True,  # New verifications are guaranteed to be live
            )

        return verification  # type: ignore[return-value] # Incompatible return value type (got "Optional[EligibilityVerification]", expected "EligibilityVerification")

    def create_multiple_verifications_for_user(
        self,
        user_id: int,
        verification_type: str,
        members: Optional[List[model.EligibilityMember]],
        verification_data_list: Optional[List[model.VerificationData]] = None,
        first_name: str | None = "",
        last_name: str | None = "",
        date_of_birth: datetime.datetime | None = None,
        verification_session: str | None = None,
        additional_fields: dict | None = None,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> List[model.EligibilityVerification]:
        """Generate multiple verifications for a user
        This api is only applicable for members with overeligibility"""

        verified_at = datetime.datetime.utcnow()
        eligibility_member_ids = []

        if members is not None and len(members) > 0:
            # Build verification data from member records
            verification_data_list = []
            for member in members:
                verification_data = model.VerificationData(
                    eligibility_member_id=member.id,
                    organization_id=member.organization_id,
                    unique_corp_id=member.unique_corp_id,
                    dependent_id=member.dependent_id,
                    email=member.email,
                    work_state=member.work_state,  # type: ignore[arg-type] # Argument "work_state" to "VerificationData" has incompatible type "Optional[str]"; expected "str""
                    additional_fields=str(additional_fields),
                )
                eligibility_member_ids.append(member.id)
                verification_data_list.append(verification_data)

        if verification_data_list is None or len(verification_data_list) == 0:
            raise ValueError(
                "Either a non-empty 'members' list or a non-empty 'verification_data_list' must be provided."
            )

        verifications, err = self.grpc.create_multiple_verifications_for_user(
            user_id=user_id,
            verification_type=verification_type,
            verification_data_list=verification_data_list,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            verification_session=verification_session,
            verified_at=verified_at,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

        if err is not None:
            from eligibility.service import EnterpriseVerificationCreationError

            raise EnterpriseVerificationCreationError(
                "Error creating verifications for user",
                verification_type=verification_type,
                user_id=user_id,
                eligibility_member_id=eligibility_member_ids,  # type: ignore[arg-type] # Argument "eligibility_member_id" to "EnterpriseVerificationCreationError" has incompatible type "Optional[int]"; expected "int"
                details=err.details if err and hasattr(err, "details") else str(err),
            )

        if verifications:
            self._update_multiple_verifications_cache(
                user_id=user_id,
                verifications=verifications,
                organization_ids=None,
                skip_live_check=True,  # New verifications are guaranteed to be live
            )
        return verifications  # type: ignore[return-value] # Incompatible return value type (got "Optional[EligibilityVerification]", expected "EligibilityVerification")

    def create_failed_verification_attempt_for_user(
        self,
        *,
        user_id: int,
        verification_type: str,
        organization_id: int | None = None,
        unique_corp_id: str | None = None,
        first_name: str | None = "",
        last_name: str | None = "",
        email: str | None = "",
        work_state: str | None = "",
        date_of_birth: datetime.date | None = None,
        eligibility_member_id: int | None = None,
        dependent_id: str | None = None,
        policy_used: str | None = None,
        additional_fields: dict | None = None,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityVerificationAttempt | None:
        """Generate a failed verification attempt for a user"""

        verified_at = datetime.datetime.utcnow()

        return self.grpc.create_failed_verification_attempt(
            user_id=user_id,
            verification_type=verification_type,
            organization_id=organization_id,
            unique_corp_id=unique_corp_id,
            dependent_id=dependent_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            work_state=work_state,
            date_of_birth=date_of_birth,
            eligibility_member_id=eligibility_member_id,
            additional_fields=additional_fields,
            verified_at=verified_at,
            policy_used=policy_used,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )

    def get_verification_for_user(
        self,
        *,
        user_id: int,
        organization_id: int | None = None,
        active_eligibility_only: bool | None = False,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibilityVerification | None:
        """
        Get a verification for a user, with optional filtering by organization and active status.

        Args:
            user_id: The user ID to get verifications for
            organization_id: Optional organization ID to filter by
            active_eligibility_only: Whether to only return verifications where the member record is currently eligible
            timeout: Optional timeout for the gRPC call
            metadata: Optional metadata for the gRPC call

        Returns:
            Optional[EligibilityVerification]: The verification if found, None otherwise
        """
        metric_name = (
            "api.eligibility.enterpriseverificationservice.get_verification_for_user"
        )
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.ELIGIBILITY,
        )

        with stats.timed(metric_name=metric_name, pod_name=stats.PodNames.ELIGIBILITY):
            try:
                # Try to get from cache first
                if verification := self.verification_cache.get(
                    self._build_single_verification_cache_key(
                        user_id=user_id,
                        active_eligibility_only=active_eligibility_only
                        if active_eligibility_only is not None
                        else False,
                    )
                ):
                    return verification
            except Exception as e:
                logger.exception(
                    "Error retrieving item from get_verification_for_user cache",
                    error=e,
                )

            stats.increment(
                metric_name=f"{metric_name}.cache_miss",
                pod_name=stats.PodNames.ELIGIBILITY,
            )

            # If not in cache, get from gRPC service
            verification = self.grpc.get_verification(
                user_id=user_id,
                organization_id=organization_id,
                active_eligibility_only=active_eligibility_only,
                timeout=timeout,
                grpc_connection=self.grpc_connection,
                metadata=metadata,
            )

            if verification is not None:
                self._update_single_verification_cache(
                    user_id=user_id,
                    verification=verification,
                )
            return verification

    def get_all_verifications_for_user(
        self,
        user_id: int,
        *,
        organization_ids: List[int] | None = None,
        active_verifications_only: bool | None = False,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> List[model.EligibilityVerification]:
        """
        Get all verifications for a user, with optional filtering by organizations and active status.

        Args:
            user_id: The user ID to get verifications for
            organization_ids: Optional list of organization IDs to filter by
            active_verifications_only: Whether to only return verifications where the member record is currently eligible
            timeout: Optional timeout for the gRPC call
            metadata: Optional metadata for the gRPC call

        Returns:
            List[EligibilityVerification]: List of verifications
        """
        if organization_ids is None:
            organization_ids = []

        metric_name = "api.eligibility.enterpriseverificationservice.get_all_verifications_for_user"
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.ELIGIBILITY,
        )

        with stats.timed(metric_name=metric_name, pod_name=stats.PodNames.ELIGIBILITY):
            try:
                # Try to get from cache first
                if cached := self.verification_overeligibility_cache.get(
                    self._build_multiple_verifications_cache_key(
                        user_id=user_id,
                        organization_ids=organization_ids,
                        active_verifications_only=active_verifications_only
                        if active_verifications_only is not None
                        else False,
                    )
                ):
                    return cached
            except Exception as e:
                logger.exception(
                    "Error retrieving item from get_all_verifications_for_user cache",
                    error=e,
                )

            stats.increment(
                metric_name=f"{metric_name}.cache_miss",
                pod_name=stats.PodNames.ELIGIBILITY,
            )

            # If not in cache, get from gRPC service
            verifications = self.grpc.get_all_verifications(
                user_id=user_id,
                organization_ids=organization_ids,
                active_verifications_only=active_verifications_only,
                timeout=timeout,
                grpc_connection=self.grpc_connection,
                metadata=metadata,
            )

            if verifications:
                self._update_multiple_verifications_cache(
                    user_id=user_id,
                    verifications=verifications,
                    organization_ids=organization_ids,
                    skip_live_check=False,
                )
            return verifications

    @trace_wrapper
    def get_other_user_ids_in_family(
        self,
        *,
        user_id: int,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> List[int]:
        """Send a request to the e9y service to retrieve the user_ids within the family for a user"""
        return self.grpc.get_other_user_ids_in_family(
            user_id=user_id,
            timeout=timeout,
            metadata=metadata,
        )

    def deactivate_verification_for_user(
        self,
        *,
        user_id: int,
        verification_id: int,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> int:
        """
        Deactivate a verification for a user.

        Args:
            user_id: The user ID whose verification should be deactivated
            verification_id: The ID of the verification to deactivate
            timeout: Optional timeout for the gRPC call
            metadata: Optional metadata for the gRPC call

        Returns:
            int: 1 if successful, -1 if failed
        """
        metric_name = "api.eligibility.enterpriseverificationservice.deactivate_verification_for_user"
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.ELIGIBILITY,
        )

        with stats.timed(metric_name=metric_name, pod_name=stats.PodNames.ELIGIBILITY):
            deactivated_verification = self.grpc.deactivate_verification(
                user_id=user_id,
                verification_id=verification_id,
                timeout=timeout,
                grpc_connection=self.grpc_connection,
                metadata=metadata,
            )

            if deactivated_verification is None:
                return -1

            # Update caches with the deactivated verification
            self._update_single_verification_cache(
                user_id=user_id,
                verification=deactivated_verification,
            )

            return 1

    def create_test_member_records_for_organization(
        self,
        *,
        organization_id: int,
        test_member_records: List[dict[str, str]],
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> List[str]:
        """Create test member records for an organization.

        Args:
            organization_id: The ID of the organization for which test member records will be created.
            test_member_records: A list of dictionaries containing test member records.
            timeout: Optional timeout value for the gRPC call.
            metadata: Optional metadata to be included in the gRPC call.

        Returns:
            A list of dictionaries representing the created test member records.
        """

        return self.grpc.create_test_members_records_for_org(
            organization_id=organization_id,
            test_member_records=test_member_records,
            timeout=timeout,
            grpc_connection=self.grpc_connection,
            metadata=metadata,
        )


class FeatureEligibilityRepository:
    """A lightweight repository wrapper for determining feature eligibility."""

    def __init__(self) -> None:
        self.grpc = grpc_service

    @trace_wrapper
    def get_eligible_features_for_user(
        self,
        *,
        user_id: int,
        feature_type: int,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibleFeaturesForUserResponse | None:
        """Send a request to the e9y service to retrieve the eligible features for a user"""
        return self.grpc.get_eligible_features_for_user(
            user_id=user_id,
            feature_type=feature_type,
            timeout=timeout,
            metadata=metadata,
        )

    @trace_wrapper
    def get_eligible_features_for_user_and_org(
        self,
        *,
        user_id: int,
        organization_id: int,
        feature_type: int,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibleFeaturesForUserAndOrgResponse | None:
        """Send a request to the e9y service to retrieve the eligible features for a user"""
        return self.grpc.get_eligible_features_for_user_and_org(
            user_id=user_id,
            organization_id=organization_id,
            feature_type=feature_type,
            timeout=timeout,
            metadata=metadata,
        )

    @trace_wrapper
    def get_eligible_features_by_sub_population_id(
        self,
        *,
        sub_population_id: int,
        feature_type: int,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.EligibleFeaturesBySubPopulationIdResponse | None:
        """Send a request to the e9y service to retrieve the eligible features for a user"""
        return self.grpc.get_eligible_features_by_sub_population_id(
            sub_population_id=sub_population_id,
            feature_type=feature_type,
            timeout=timeout,
            metadata=metadata,
        )

    @trace_wrapper
    def get_sub_population_id_for_user(
        self,
        *,
        user_id: int,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> int | None:
        """Send a request to the e9y service to retrieve the eligible features for a user"""
        sub_population_id = self.grpc.get_sub_population_id_for_user(
            user_id=user_id,
            timeout=timeout,
            metadata=metadata,
        )

        if sub_population_id is not None:
            # Unwrap Int64Value to int
            sub_population_id = sub_population_id.value  # type: ignore[assignment] # Incompatible types in assignment (expression has type "int", variable has type "Optional[Int64Value]")
        return sub_population_id  # type: ignore[return-value] # Incompatible return value type (got "Optional[Int64Value]", expected "Optional[int]")

    @trace_wrapper
    def get_sub_population_id_for_user_and_org(
        self,
        *,
        user_id: int,
        organization_id: int,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> int | None:
        """Send a request to the e9y service to retrieve the eligible features for a user and org"""
        sub_population_id = self.grpc.get_sub_population_id_for_user_and_org(
            user_id=user_id,
            organization_id=organization_id,
            timeout=timeout,
            metadata=metadata,
        )

        if sub_population_id is not None:
            # Unwrap Int64Value to int
            sub_population_id = sub_population_id.value  # type: ignore[assignment] # Incompatible types in assignment (expression has type "int", variable has type "Optional[Int64Value]")
        return sub_population_id  # type: ignore[return-value] # Incompatible return value type (got "Optional[Int64Value]", expected "Optional[int]")


class WalletEnablementRepository:
    """A repository for locating an E9y Member record's corresponding wallet enablement."""

    def __init__(self) -> None:
        self.grpc = grpc_service

    def get_by_member_id(
        self,
        *,
        member_id: int,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.WalletEnablement | None:
        """Locate a wallet enablement configuration by E9y Member ID."""
        return self.grpc.wallet_enablement_by_id_search(
            member_id=member_id,
            timeout=timeout,
            metadata=metadata,
        )

    def get_by_org_identity(
        self,
        *,
        organization_id: int,
        unique_corp_id: str,
        dependent_id: str = "",
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.WalletEnablement | None:
        """Locate a wallet enablement configuration by org identity."""
        return self.grpc.wallet_enablement_by_org_identity_search(
            unique_corp_id=unique_corp_id,
            dependent_id=dependent_id,
            organization_id=organization_id,
            timeout=timeout,
            metadata=metadata,
        )

    def get_by_user_id(
        self,
        *,
        user_id: int,
        timeout: Optional[float] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
    ) -> model.WalletEnablement | None:
        """Locate a wallet enablement configuration by Maven userID"""
        return self.grpc.wallet_enablement_by_user_id_search(
            user_id=user_id,
            timeout=timeout,
            metadata=metadata,
        )


class EnterpriseEligibilitySettings(NamedTuple):
    organization_id: int
    organization_name: str
    organization_shortname: str
    organization_logo: str
    eligibility_type: OrganizationEligibilityType
    employee_only: bool
    medical_plan_only: bool
    fields: list[EligibilityField]
    email_domains: list[EmailDomain]
    activated_at: datetime.datetime | None = None


class EligibilityField(NamedTuple):
    name: str
    label: str


class EmailDomain(NamedTuple):
    domain: str
    eligibility_type: OrganizationEligibilityType


class OrganizationMeta(NamedTuple):
    organization_id: int
    organization_name: str
    external_id: str | None = None
    identity_provider_id: int | None = None


@dataclasses.dataclass
class ProductEnablement:
    product: str
    active: bool
    launch_date: datetime.date | None = None
    length_in_days: int | None = None


class OrgIdentity(NamedTuple):
    unique_corp_id: str
    dependent_id: str
    organization_id: int


@dataclasses.dataclass(frozen=True)
class EmployeeInfo:
    employee: OrganizationEmployee
    associated_to_user: bool
    member_id: int | None = None
