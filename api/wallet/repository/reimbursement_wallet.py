from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple, Union

import ddtrace.ext
import sqlalchemy
from sqlalchemy import func
from sqlalchemy.orm import aliased

from authn.models.user import User
from direct_payment.clinic.utils.aggregate_procedures_utils import (
    get_benefit_e9y_start_and_expiration_date,
)
from health.models.health_profile import HealthProfile
from models.enterprise import Organization
from models.marketing import Resource
from models.profiles import MemberProfile
from storage import connection
from storage.connector import RoutingSession
from utils.log import logger
from wallet.constants import APPROVED_REQUEST_STATES
from wallet.models.constants import (
    BenefitTypes,
    MemberType,
    ReimbursementRequestState,
    WalletState,
    WalletUserMemberStatus,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.models import (
    MemberBenefitProfile,
    MemberWalletSummary,
    OrganizationWalletSettings,
    UserWalletAndOrgInfo,
)
from wallet.models.reimbursement import (
    ReimbursementAccount,
    ReimbursementRequest,
    ReimbursementRequestCategory,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.models.reimbursement_wallet_credit_transaction import (
    ReimbursementCycleMemberCreditTransaction,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.services.currency import DEFAULT_CURRENCY_CODE
from wallet.services.reimbursement_benefits import get_member_type
from wallet.utils.eligible_wallets import get_eligible_wallet_org_settings

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)

log = logger(__name__)


class ReimbursementWalletRepository:
    def __init__(
        self,
        session: Union[
            sqlalchemy.orm.scoping.ScopedSession, RoutingSession, None
        ] = None,
    ):
        self.session = session or connection.db.session

    @trace_wrapper
    def get_active_user_in_wallet(
        self, user_id: int, wallet_id: int
    ) -> ReimbursementWalletUsers | None:
        """
        Checks if user is a wallet user in the wallet
        @param user_id: the `User` who is associated with the wallet to retrieve
        @param wallet_id: the wallet associated with the user
        @return: user or None if user does not exist or multiple users found
        """
        try:
            return ReimbursementWalletUsers.query.filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == wallet_id,
                ReimbursementWalletUsers.user_id == user_id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
            ).one()
        except Exception as e:
            log.warn(
                "Could not find the user in wallet",
                user_id=str(user_id),
                wallet_id=str(wallet_id),
                reason=str(e),
            )

            return None

    @trace_wrapper
    def get_wallet_user_member_status(
        self, user_id: int, wallet_id: int
    ) -> WalletUserMemberStatus:
        """
        Checks the user's member status for the provided wallet and user id
        @param user_id: the `User` who is associated with the wallet to retrieve
        @param wallet_id: the wallet associated with the user
        @return: `WalletUserMemberStatus`
        """

        query = f"""
                SELECT
                    CASE
                        WHEN reimbursement_wallet_users.id IS NOT NULL THEN '{WalletUserMemberStatus.MEMBER}'
                        WHEN organization_employee_dependent.id IS NOT NULL THEN '{WalletUserMemberStatus.NON_MEMBER}'
                        ELSE NULL
                    END
                FROM
                    reimbursement_wallet
                LEFT JOIN
                    reimbursement_wallet_users
                ON
                    reimbursement_wallet.id = reimbursement_wallet_users.reimbursement_wallet_id
                AND
                    reimbursement_wallet_users.user_id = :user_id
                AND
                    reimbursement_wallet_users.status = :status
                LEFT JOIN
                    organization_employee_dependent
                ON
                    reimbursement_wallet.id = organization_employee_dependent.reimbursement_wallet_id
                AND
                    organization_employee_dependent.id = :user_id
                WHERE
                    reimbursement_wallet.id = :wallet_id
                """

        return self.session.scalar(
            query,
            {
                "user_id": user_id,
                "wallet_id": wallet_id,
                "status": WalletUserStatus.ACTIVE,
            },
        )

    @trace_wrapper
    def get_num_existing_rwus(self, wallet_id: int) -> int:
        """Returns the number of PENDING or ACTIVE RWUs affiliated with a wallet."""
        return (
            self.session.query(ReimbursementWalletUsers)
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == wallet_id,
                ReimbursementWalletUsers.status.in_(
                    [WalletUserStatus.ACTIVE, WalletUserStatus.PENDING]
                ),
            )
            .count()
        )

    @trace_wrapper
    def get_users_in_wallet(self, wallet_id: int) -> List[Dict[str, Any]]:
        query = f"""(
                        SELECT
                            u.id,
                            u.first_name COLLATE utf8mb4_unicode_ci as first_name,
                            u.last_name COLLATE utf8mb4_unicode_ci as last_name,
                            wu.type COLLATE utf8mb4_unicode_ci as type,
                            '{WalletUserMemberStatus.MEMBER}' COLLATE utf8mb4_unicode_ci as membership_status
                        FROM
                            reimbursement_wallet w
                        INNER JOIN
                            reimbursement_wallet_users wu ON w.id = wu.reimbursement_wallet_id
                        INNER JOIN
                            user u ON u.id = wu.user_id
                        WHERE
                            w.id = :wallet_id
                        AND
                            wu.type IN ('{WalletUserType.DEPENDENT}', '{WalletUserType.EMPLOYEE}')
                        AND
                            wu.status = '{WalletUserStatus.ACTIVE}'
                    )
                    UNION
                    (
                        SELECT
                            d.id,
                            d.first_name COLLATE utf8mb4_unicode_ci as first_name,
                            d.last_name COLLATE utf8mb4_unicode_ci as last_name,
                            '{WalletUserType.DEPENDENT}' COLLATE utf8mb4_unicode_ci as type,
                            '{WalletUserMemberStatus.NON_MEMBER}' COLLATE utf8mb4_unicode_ci as membership_status
                        FROM
                            reimbursement_wallet w
                        INNER JOIN
                            organization_employee_dependent d ON w.id = d.reimbursement_wallet_id
                        WHERE
                            w.id = :wallet_id
                    )
                    ORDER BY membership_status desc
                """

        data = self.session.execute(
            query,
            {
                "wallet_id": wallet_id,
            },
        ).fetchall()

        return data

    @trace_wrapper
    def get_any_user_has_wallet(self, user_ids: list[int]) -> bool:
        """
        Returns whether any of the users is an ACTIVE RWU of
        a QUALIFIED or PENDING wallet.
        """
        query = f"""
            SELECT COUNT(*) FROM reimbursement_wallet_users rwu
            JOIN reimbursement_wallet rw
            ON rw.id = rwu.reimbursement_wallet_id
            WHERE rwu.user_id in :user_ids
            AND rwu.status = '{WalletUserStatus.ACTIVE}'
            AND rw.state in ('{WalletState.QUALIFIED}', '{WalletState.PENDING}')
            LIMIT 1;
        """
        return bool(self.session.scalar(query, {"user_ids": tuple(user_ids)}))

    @trace_wrapper
    def get_wallet_rwu_info(
        self, user_ids: list[int], reimbursement_org_settings_id: int
    ) -> List[WalletRWUInfo]:
        """
        Returns wallet info and RWUs for users in the list.
        """
        query = """
            SELECT
                rw.id,
                rw.state,
                rwu.status,
                rwu.user_id
            FROM reimbursement_wallet rw
            JOIN reimbursement_wallet_users rwu
            ON rw.id = rwu.reimbursement_wallet_id
            WHERE reimbursement_organization_settings_id = :reimbursement_org_settings_id AND rwu.user_id in :user_ids
        """
        results = self.session.execute(
            query,
            {
                "user_ids": tuple(user_ids),
                "reimbursement_org_settings_id": reimbursement_org_settings_id,
            },
        )
        return [
            WalletRWUInfo(
                wallet_id=result[0],
                state=result[1],
                rwu_status=result[2],
                user_id=result[3],
            )
            for result in results
        ]

    @trace_wrapper
    def get_wallet_and_rwu(
        self,
        wallet_id: int,
        user_id: int,
    ) -> WalletAndRWU:
        """
        Queries the Wallet with the wallet_id and (if it exists) the affiliated RWU.
        Note that it is possible to find a wallet without an RWU, and this is used to check
        the Share a Wallet workflows.

        ex. A partner is applying to join a wallet and is not currently a user of the wallet.
        In this case, we would find the wallet and no RWU.
        """
        wallet = (
            self.session.query(ReimbursementWallet)
            .filter(ReimbursementWallet.id == wallet_id)
            .one_or_none()
        )

        if wallet is None:
            return WalletAndRWU(wallet=None, rwu=None)
        rwu = (
            self.session.query(ReimbursementWalletUsers)
            .filter(
                ReimbursementWalletUsers.user_id == user_id,
                ReimbursementWalletUsers.reimbursement_wallet_id == wallet_id,
            )
            .one_or_none()
        )
        return WalletAndRWU(wallet=wallet, rwu=rwu)

    @trace_wrapper
    def get_wallet_by_active_user_id(self, user_id: int) -> ReimbursementWallet | None:
        wallets = (
            ReimbursementWallet.query.join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .filter(
                ReimbursementWalletUsers.user_id == user_id,
                ReimbursementWalletUsers.status.in_(
                    [WalletUserStatus.ACTIVE, WalletUserStatus.PENDING]
                ),
            )
            .order_by(ReimbursementWalletUsers.modified_at.desc())
            .all()
        )
        if len(wallets) > 1:
            wallet_ids = ", ".join(str(w.id) for w in wallets)
            log.warn(
                "Someone is an active user of multiple wallets",
                user_id=str(user_id),
                wallet_ids=wallet_ids,
            )
        return (wallets or None) and wallets[0]

    def get_current_wallet_by_active_user_id(
        self, user_id: int
    ) -> ReimbursementWallet | None:
        wallets = (
            ReimbursementWallet.query.join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .filter(
                ReimbursementWalletUsers.user_id == user_id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
                ReimbursementWallet.state.in_(
                    [WalletState.QUALIFIED, WalletState.RUNOUT]
                ),
            )
            .order_by()
            .all()
        )
        if len(wallets) > 1:
            wallet_ids = ", ".join(str(w.id) for w in wallets)
            log.warn(
                "Someone is an active user of multiple wallets",
                user_id=str(user_id),
                wallet_ids=wallet_ids,
            )
        return (wallets or None) and wallets[0]

    @trace_wrapper
    def get_wallet_states_for_user(self, user_id: int) -> set[str]:
        """
        Returns a set of the distinct states of all wallets for a user
        who is a PENDING or ACTIVE ReimbursementWalletUser of that wallet.
        """
        query = f"""
            SELECT DISTINCT(w.state)
            FROM reimbursement_wallet w
            JOIN reimbursement_wallet_users rw
            ON w.id = rw.reimbursement_wallet_id
            WHERE rw.user_id = :user_id AND rw.status in ('{WalletUserStatus.ACTIVE}', '{WalletUserStatus.PENDING}');
        """
        result = self.session.execute(query, {"user_id": user_id}).fetchall()
        return {state for state, in result}

    @trace_wrapper
    def get_eligible_wallets(self, user_id: int) -> List[MemberWalletSummary]:
        eligible_wallet_orgs: List[
            ReimbursementOrganizationSettings
        ] = get_eligible_wallet_org_settings(
            user_id=user_id, filter_out_existing_wallets=True
        )

        return [
            MemberWalletSummary(
                org_settings_id=org_settings.id,
                org_id=org_settings.organization_id,
                direct_payment_enabled=org_settings.direct_payment_enabled,
                org_survey_url=org_settings.survey_url,
                overview_resource_title=org_settings.benefit_overview_resource.title
                if org_settings.benefit_overview_resource
                else None,
                overview_resource_id=org_settings.benefit_overview_resource.id
                if org_settings.benefit_overview_resource
                else None,
                faq_resource_title=org_settings.benefit_faq_resource.title,
                faq_resource_content_type=org_settings.benefit_faq_resource.content_type,
                faq_resource_slug=org_settings.benefit_faq_resource.slug,
            )
            for org_settings in eligible_wallet_orgs
        ]

    @trace_wrapper
    def _get_member_wallet_settings_base_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        OverviewResource: Resource = aliased(Resource)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "AliasedClass", variable has type "Resource")
        FaqResource: Resource = aliased(Resource)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "AliasedClass", variable has type "Resource")

        query = (
            self.session.query(
                ReimbursementWallet,
                ReimbursementWallet.id.label("wallet_id"),
                ReimbursementWallet.payments_customer_id.label("payments_customer_id"),
                ReimbursementOrganizationSettings.id.label("org_setting_id"),
                ReimbursementOrganizationSettings.organization_id.label("org_id"),
                ReimbursementOrganizationSettings.survey_url.label("org_survey_url"),
                ReimbursementOrganizationSettings.direct_payment_enabled.label(
                    "direct_payment_enabled"
                ),
                ReimbursementWallet.state.label("wallet_state"),
                OverviewResource.title.label("overview_resource_title"),  # type: ignore[attr-defined] # "str" has no attribute "label"
                OverviewResource.id.label("overview_resource_id"),  # type: ignore[attr-defined] # "int" has no attribute "label"
                FaqResource.title.label("faq_resource_title"),  # type: ignore[attr-defined] # "str" has no attribute "label"
                FaqResource.content_type.label("faq_resource_content_type"),  # type: ignore[attr-defined] # "str" has no attribute "label"
                FaqResource.slug.label("faq_resource_slug"),  # type: ignore[attr-defined] # "str" has no attribute "label"
                ReimbursementWalletUsers.status.label("user_status"),
                ReimbursementWalletUsers.channel_id.label("channel_id"),
                User.esp_id.label("member_id_hash"),
            )
            .join(
                ReimbursementWallet,
                ReimbursementWallet.id
                == ReimbursementWalletUsers.reimbursement_wallet_id,
            )
            .join(
                ReimbursementOrganizationSettings,
                ReimbursementOrganizationSettings.id
                == ReimbursementWallet.reimbursement_organization_settings_id,
            )
            .join(User, User.id == ReimbursementWalletUsers.user_id)
            .join(
                OverviewResource,
                ReimbursementOrganizationSettings.benefit_overview_resource_id
                == OverviewResource.id,
                isouter=True,
            )
            .join(
                FaqResource,
                ReimbursementOrganizationSettings.benefit_faq_resource_id
                == FaqResource.id,
                isouter=True,
            )
        )

        return query

    @trace_wrapper
    def get_wallet_summaries(self, user_id: int) -> List[MemberWalletSummary]:
        results = (
            self._get_member_wallet_settings_base_query()
            .filter(
                ReimbursementWalletUsers.user_id == user_id,
            )
            .order_by(ReimbursementWallet.created_at.desc())
            .all()
        )

        summaries: List[MemberWalletSummary] = []

        for summary in results:
            summaries.append(
                MemberWalletSummary(
                    wallet=summary[0],
                    wallet_id=summary.wallet_id,
                    wallet_state=summary.wallet_state,
                    wallet_user_status=summary.user_status,
                    is_shareable=summary[0].is_shareable,
                    payments_customer_id=summary.payments_customer_id,
                    channel_id=summary.channel_id,
                    org_settings_id=summary.org_setting_id,
                    org_id=summary.org_id,
                    direct_payment_enabled=summary.direct_payment_enabled,
                    org_survey_url=summary.org_survey_url,
                    overview_resource_title=summary.overview_resource_title,
                    overview_resource_id=summary.overview_resource_id,
                    faq_resource_title=summary.faq_resource_title,
                    faq_resource_content_type=summary.faq_resource_content_type,
                    faq_resource_slug=summary.faq_resource_slug,
                    member_id_hash=summary.member_id_hash,
                )
            )

        return summaries

    @trace_wrapper
    def get_clinic_portal_wallet_summaries(
        self, user_id: int
    ) -> List[MemberWalletSummary]:
        results = (
            self._get_member_wallet_settings_base_query()
            .filter(
                ReimbursementWalletUsers.user_id == user_id,
            )
            .order_by(ReimbursementWallet.created_at.desc())
            .all()
        )

        summaries: List[MemberWalletSummary] = []

        for summary in results:
            summaries.append(
                MemberWalletSummary(
                    wallet=summary[0],
                    wallet_id=summary.wallet_id,
                    wallet_state=summary.wallet_state,
                    wallet_user_status=summary.user_status,
                    payments_customer_id=summary.payments_customer_id,
                    channel_id=summary.channel_id,
                    org_id=summary.org_id,
                    org_settings_id=summary.org_setting_id,
                    direct_payment_enabled=summary.direct_payment_enabled,
                    org_survey_url=summary.org_survey_url,
                    overview_resource_title=summary.overview_resource_title,
                    overview_resource_id=summary.overview_resource_id,
                    faq_resource_title=summary.faq_resource_title,
                    faq_resource_content_type=summary.faq_resource_content_type,
                    faq_resource_slug=summary.faq_resource_slug,
                    member_id_hash=summary.member_id_hash,
                )
            )

        return summaries

    @trace_wrapper
    def get_eligible_org_wallet_settings(
        self, user_id: int, organization_id: int
    ) -> List[OrganizationWalletSettings]:
        """
        Fetch a list of OrganizationWalletSettings which may or may not support wallet
        """
        # Fetch the wallet enabled orgs that someone is eligible for
        eligible_wallet_orgs: List[
            ReimbursementOrganizationSettings
        ] = get_eligible_wallet_org_settings(
            user_id=user_id,
            organization_id=organization_id,
            filter_out_existing_wallets=False,
        )

        # Case #1 - Member is eligible for a ROS
        if eligible_wallet_orgs:
            return [
                OrganizationWalletSettings(
                    direct_payment_enabled=setting.direct_payment_enabled,
                    organization_id=setting.organization_id,
                    organization_name=setting.organization.display_name
                    or setting.organization.name,
                    org_settings_id=setting.id,
                    fertility_program_type=setting.fertility_program_type,  # type: ignore[arg-type] # Argument "fertility_program_type" to "OrganizationWalletSettings" has incompatible type "str"; expected "Optional[FertilityProgramTypes]"
                    fertility_allows_taxable=setting.fertility_allows_taxable,
                    excluded_procedures=[
                        str(p.global_procedure_id) for p in setting.excluded_procedures
                    ],
                    dx_required_procedures=[
                        str(rp.global_procedure_id)
                        for rp in setting.dx_required_procedures
                    ],
                )
                for setting in eligible_wallet_orgs
            ]

        # Case #2 - Org offers wallet but Member is not eligible for a ROS
        # Case #3 - Org does not offer wallet
        # Case #4 - Org used to offer wallet
        settings = (
            self.session.query(
                Organization.id.label("organization_id"),
                Organization.name.label("organization_name"),
                Organization.display_name.label("organization_display_name"),
            )
            .filter(Organization.id == organization_id)
            .all()
        )

        return [
            OrganizationWalletSettings(
                organization_id=setting.organization_id,
                organization_name=setting.organization_display_name
                or setting.organization_name,
            )
            for setting in settings
        ]

    @trace_wrapper
    def get_member_type(self, user_id: int) -> MemberType:
        user: User = self.session.query(User).get(user_id)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Union[User, None, Any]", variable has type "User")
        return get_member_type(user=user)

    @trace_wrapper
    def get_wallet_eligibility_dates(
        self, user_id: int, wallet_id: int
    ) -> Tuple[datetime.date | None, datetime.date | None]:
        wallet: ReimbursementWallet = self.session.query(ReimbursementWallet).get(
            wallet_id
        )
        return get_benefit_e9y_start_and_expiration_date(wallet=wallet, user_id=user_id)

    @trace_wrapper
    def get_user_wallet_and_org_info_for_user_ids(
        self, user_ids: list[int]
    ) -> list[UserWalletAndOrgInfo]:
        query = f"""
                SELECT
                    rwu.user_id as user_id,
                    rwu.type as user_type,
                    rwu.status as user_status,
                    rw.id as wallet_id,
                    rw.state as wallet_state,
                    ros.id as ros_id,
                    ros.allowed_members as ros_allowed_members
                FROM
                    reimbursement_wallet_users rwu
                JOIN
                    reimbursement_wallet rw ON rw.id = rwu.reimbursement_wallet_id
                JOIN
                    reimbursement_organization_settings ros ON ros.id = rw.reimbursement_organization_settings_id
                WHERE
                    rwu.status = '{WalletUserStatus.ACTIVE}'
                    AND rw.state in ('{WalletState.QUALIFIED}', '{WalletState.PENDING}')
                    AND rwu.user_id in :user_id_tuple
        """
        rows = self.session.execute(
            query, {"user_id_tuple": tuple(user_ids)}
        ).fetchall()

        return [UserWalletAndOrgInfo(**dict(row)) for row in rows]

    @trace_wrapper
    def search_by_wallet_benefit_id(
        self, last_name: str, date_of_birth: datetime.date, benefit_id: str
    ) -> MemberBenefitProfile | None:

        members = (
            self.session.query(
                HealthProfile,
                User.id.label("user_id"),
                User.first_name.label("first_name"),
                User.last_name.label("last_name"),
                User.email.label("email"),
                ReimbursementWalletBenefit.maven_benefit_id.label("benefit_id"),
                HealthProfile.date_of_birth.label("date_of_birth"),
                MemberProfile.phone_number.label("phone_number"),
            )
            .join(ReimbursementWalletUsers, ReimbursementWalletUsers.user_id == User.id)
            .join(
                ReimbursementWallet,
                ReimbursementWallet.id
                == ReimbursementWalletUsers.reimbursement_wallet_id,
            )
            .join(
                ReimbursementWalletBenefit,
                ReimbursementWalletBenefit.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .join(HealthProfile, HealthProfile.user_id == User.id)
            .join(MemberProfile, MemberProfile.user_id == User.id)
            .filter(
                ReimbursementWalletBenefit.maven_benefit_id == benefit_id,
            )
            .all()
        )

        if not members:
            log.info(
                "[wallet level lookup] not found",
                benefit_id=benefit_id,
                not_found_reason="benefit_id_mismatch",
            )
            return None

        def filter_by_dob_and_last_name(member) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
            health_profile: HealthProfile = member[0]
            dob_matches: bool = date_of_birth == health_profile.birthday
            name_matches: bool = last_name.lower() == member.last_name.lower()

            if dob_matches is False and name_matches is False:
                log.info(
                    "[wallet level lookup] not found",
                    benefit_id=benefit_id,
                    user_id=member.user_id,
                    not_found_reason="dob_and_name_mismatch",
                )
                return False
            elif dob_matches is False:
                log.info(
                    "[wallet level lookup] not found",
                    benefit_id=benefit_id,
                    user_id=member.user_id,
                    not_found_reason="dob_mismatch",
                )
                return False
            elif name_matches is False:
                log.info(
                    "[wallet level lookup] not found",
                    benefit_id=benefit_id,
                    user_id=member.user_id,
                    not_found_reason="name_mismatch",
                )
                return False

            log.info(
                "[wallet level lookup] member found",
                benefit_id=benefit_id,
                user_id=member.user_id,
            )
            return True

        filtered_members = list(
            filter(lambda m: filter_by_dob_and_last_name(m), members)
        )

        if not filtered_members:
            return None
        elif len(filtered_members) > 1:
            log.info(
                "[wallet level lookup] not found",
                benefit_id=benefit_id,
                not_found_reason="multiple_matches",
            )
            return None

        member = filtered_members[0]
        member_health_profile: HealthProfile = member[0]

        return MemberBenefitProfile(
            first_name=member.first_name,
            last_name=member.last_name,
            user_id=member.user_id,
            benefit_id=member.benefit_id,
            date_of_birth=member_health_profile.birthday,
            phone=member.phone_number,
            email=member.email,
        )

    def get_wallets_and_rwus_for_user(
        self,
        user_id: int,
        wallet_states: Set[WalletState] = None,
        rwu_statuses: Set[WalletUserStatus] = None,
    ) -> List[Tuple[ReimbursementWallet, ReimbursementWalletUsers]]:
        """
        This method can be used to fetch for wallet and RWU pairs associated with the member

        Args:
            user_id int: The user ID to search for
            wallet_states Set[WalletState]: Filter for these specific wallet states - If None, no filter will be applied
            rwu_statuses Set[WalletUserStatus]: Filter for these specific wallet user statuses - if None, no filter will be applied

        Returns:
            A list of tuples Tuple[ReimbursementWallet, ReimbursementWalletUsers]

        """
        query = (
            self.session.query(ReimbursementWallet, ReimbursementWalletUsers)
            .join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .filter(ReimbursementWalletUsers.user_id == user_id)
            .order_by(ReimbursementWallet.created_at.desc())
        )
        if wallet_states:
            query = query.filter(ReimbursementWallet.state.in_(wallet_states))
        if rwu_statuses:
            query = query.filter(ReimbursementWalletUsers.status.in_(rwu_statuses))
        return query.all()

    @trace_wrapper
    def _get_wallet_balance_base_query(self) -> sqlalchemy.orm.Query:
        query = self.session.query(
            ReimbursementRequest.reimbursement_wallet_id.label("wallet_id"),
            ReimbursementRequest.reimbursement_request_category_id.label("category_id"),
            func.sum(ReimbursementRequest.amount).label("amount"),
        ).group_by(
            ReimbursementRequest.reimbursement_wallet_id,
            ReimbursementRequest.reimbursement_request_category_id,
        )
        return query

    def get_approved_amount_for_category(self, wallet_id: int, category_id: int) -> int:
        category = (
            self._get_wallet_balance_base_query()
            .filter(
                ReimbursementRequest.reimbursement_wallet_id == wallet_id,
                ReimbursementRequest.reimbursement_request_category_id == category_id,
                ReimbursementRequest.state.in_(APPROVED_REQUEST_STATES),
            )
            .one_or_none()
        )

        if category is None:
            return 0

        return int(category.amount)

    def get_reimbursed_amount_for_category(
        self, wallet_id: int, category_id: int
    ) -> int:
        category = (
            self._get_wallet_balance_base_query()
            .filter(
                ReimbursementRequest.reimbursement_wallet_id == wallet_id,
                ReimbursementRequest.reimbursement_request_category_id == category_id,
                ReimbursementRequest.state == ReimbursementRequestState.REIMBURSED,
            )
            .one_or_none()
        )

        if category is None:
            return 0

        return int(category.amount)

    def get_credit_balance_for_category(
        self, wallet_id: int, category_association_id: int
    ) -> int:
        category = (
            self.session.query(
                ReimbursementCycleCredits.reimbursement_wallet_id,
                ReimbursementCycleCredits.reimbursement_organization_settings_allowed_category_id,
                func.sum(ReimbursementCycleMemberCreditTransaction.amount).label(
                    "amount"
                ),
            )
            .join(
                ReimbursementCycleMemberCreditTransaction,
                ReimbursementCycleCredits.id
                == ReimbursementCycleMemberCreditTransaction.reimbursement_cycle_credits_id,
            )
            .group_by(
                ReimbursementCycleCredits.reimbursement_wallet_id,
                ReimbursementCycleCredits.reimbursement_organization_settings_allowed_category_id,
            )
            .filter(
                ReimbursementCycleCredits.reimbursement_wallet_id == wallet_id,
                ReimbursementCycleCredits.reimbursement_organization_settings_allowed_category_id
                == category_association_id,
            )
            .one_or_none()
        )

        if category is None:
            return 0

        return int(category.amount)

    @staticmethod
    def get_by_id(wallet_id: int) -> ReimbursementWallet:
        return ReimbursementWallet.query.get(wallet_id)

    def get_wallets_by_ros(
        self, ros_id: int, wallet_states: Set[WalletState] = None
    ) -> list[ReimbursementWallet]:
        """
        Get wallets based on the ROS, with optional filter for WalletState

        Args:
            ros_id int: The wallets to filter for which belong to the reimbursement organization setting ID
            wallet_states Set[WalletState]: Optional filter for wallet states

        Returns:
            list[ReimbursementWallet]
        """
        query = self.session.query(ReimbursementWallet).filter(
            ReimbursementWallet.reimbursement_organization_settings_id == ros_id
        )

        if wallet_states is not None:
            query = query.filter(ReimbursementWallet.state.in_(wallet_states))

        return query.all()

    def get_non_usd_wallets(
        self, wallet_ids: list[int] = None, ros_ids: list[int] = None
    ) -> list[ReimbursementWallet]:
        """
        Fetch list of ReimbursementWallet that have non-USD benefit currency
        which need to have Alegeus LTM adjusted

        Args:
            wallet_ids list[int]: List of wallet ID filters
            ros_ids list[int]: List of ROS ID filters

        Returns:
            ReimbursementWallet
        """
        query = (
            self.session.query(ReimbursementWallet)
            .join(
                ReimbursementOrganizationSettings,
                ReimbursementOrganizationSettings.id
                == ReimbursementWallet.reimbursement_organization_settings_id,
            )
            .join(
                ReimbursementOrgSettingCategoryAssociation,
                ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings_id
                == ReimbursementOrganizationSettings.id,
            )
            .filter(
                ReimbursementOrgSettingCategoryAssociation.benefit_type
                == BenefitTypes.CURRENCY,
                ReimbursementOrgSettingCategoryAssociation.currency_code
                != DEFAULT_CURRENCY_CODE,
                ReimbursementWallet.state.in_(
                    {WalletState.QUALIFIED, WalletState.RUNOUT}
                ),
            )
            .order_by(
                ReimbursementOrganizationSettings.id,
            )
        )
        if wallet_ids is not None:
            query = query.filter(ReimbursementWallet.id.in_(wallet_ids))
        if ros_ids is not None:
            query = query.filter(ReimbursementOrganizationSettings.id.in_(ros_ids))
        return query.all()

    def get_reimbursement_account(
        self, wallet: ReimbursementWallet, category: ReimbursementRequestCategory
    ) -> ReimbursementAccount | None:
        query = self.session.query(ReimbursementAccount).filter(
            ReimbursementAccount.reimbursement_wallet_id == wallet.id,
            ReimbursementAccount.reimbursement_plan_id
            == category.reimbursement_plan_id,
        )
        return query.one_or_none()


@dataclass(frozen=True)
class WalletRWUInfo:
    __slots__ = ("wallet_id", "state", "rwu_status", "user_id")

    wallet_id: int
    state: str
    """String version of the WalletState"""
    rwu_status: str
    """String version of the WalletUserStatus"""
    user_id: int


@dataclass(frozen=True)
class WalletAndRWU:

    __slots__ = ("wallet", "rwu")

    wallet: ReimbursementWallet | None
    """NULL if wallet_id does not exist."""
    rwu: ReimbursementWalletUsers | None
    """NULL if the user is not an RWU of the wallet."""
