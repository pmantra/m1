from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Mapping, Optional, Set, Tuple

import ddtrace
from maven import feature_flags
from sqlalchemy import and_, exists

from common.global_procedures.procedure import MissingProcedureData, ProcedureService
from common.payments_gateway import Customer, get_client
from direct_payment.billing.constants import INTERNAL_TRUST_PAYMENT_GATEWAY_URL
from direct_payment.clinic.models.portal import (
    BodyVariant,
    ClinicPortalFertilityProgram,
    ClinicPortalMember,
    ClinicPortalOrganization,
    ClinicPortalProcedure,
    MemberBenefit,
    MemberLookupResponse,
    PortalContent,
    PortalMessage,
    PortalMessageLevel,
    WalletBalance,
    WalletOverview,
)
from direct_payment.notification.lib.tasks.rq_send_notification import (
    send_notification_event,
)
from direct_payment.notification.models import (
    EventName,
    EventSourceSystem,
    UserIdType,
    UserType,
)
from eligibility import EnterpriseVerificationService
from storage import connection
from tracks import TrackSelectionService
from utils.log import logger
from wallet.models.constants import MemberType
from wallet.models.models import (
    CategoryBalance,
    MemberBenefitProfile,
    MemberWalletSummary,
    OrganizationWalletSettings,
)
from wallet.models.reimbursement import (
    ReimbursementPlan,
    ReimbursementRequestCategory,
    ReimbursementWalletPlanHDHP,
)
from wallet.models.reimbursement_wallet import (
    ReimbursementWallet,
    ReimbursementWalletCategoryRuleEvaluationFailure,
)
from wallet.repository.health_plan import HealthPlanRepository
from wallet.repository.member_benefit import MemberBenefitRepository
from wallet.repository.reimbursement_category_activation import (
    CategoryActivationRepository,
)
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.services.annual_questionnaire_lib import has_survey_been_taken
from wallet.services.reimbursement_category_activation_constants import TOC_RULES
from wallet.services.reimbursement_wallet import ReimbursementWalletService

log = logger(__name__)


CLINIC_PORTAL_CHECK_FOR_MHP_AND_PAYMENT_METHOD_PRESENCE = (
    "clinic-portal-check-for-mhp-and-payment-method-presence"
)


class MemberLookupService:
    def __init__(
        self,
        member_benefit_repo: MemberBenefitRepository | None = None,
        wallet_repo: ReimbursementWalletRepository | None = None,
        category_repo: CategoryActivationRepository | None = None,
        health_plan_repo: HealthPlanRepository | None = None,
    ):
        self.member_benefit_repo: MemberBenefitRepository = (
            member_benefit_repo or MemberBenefitRepository()
        )
        self.wallet_repo: ReimbursementWalletRepository = (
            wallet_repo or ReimbursementWalletRepository()
        )
        self.category_repo: CategoryActivationRepository = (
            category_repo or CategoryActivationRepository()
        )
        self.health_plan_repo = health_plan_repo or HealthPlanRepository(
            connection.db.session
        )

    def find_member(
        self, last_name: str, date_of_birth: date, benefit_id: str
    ) -> MemberBenefitProfile | None:
        # Sanitize the inputs
        last_name = last_name.strip()
        benefit_id = benefit_id.strip()

        is_member_level_lookup: bool = benefit_id.startswith(("m", "M"), 0, 1)
        is_wallet_level_lookup: bool = benefit_id.isnumeric()

        if is_member_level_lookup:
            log.info(
                "find_member breakdown",
                benefit_id=str(benefit_id),
                benefit_id_type="member_level",
            )
            # attempt to find the member by the member-level benefit_id
            member = self.member_benefit_repo.search_by_member_benefit_id(
                last_name=last_name, date_of_birth=date_of_birth, benefit_id=benefit_id
            )
        elif is_wallet_level_lookup:
            log.info(
                "find_member breakdown",
                benefit_id=str(benefit_id),
                benefit_id_type="wallet_level",
            )
            # Fallback to trying to find by the wallet-level benefit_id
            member = self.wallet_repo.search_by_wallet_benefit_id(
                last_name=last_name, date_of_birth=date_of_birth, benefit_id=benefit_id
            )
        else:
            log.info(
                "find_member breakdown",
                benefit_id=str(benefit_id),
                benefit_id_type="invalid",
            )
            return None

        if not member:
            log.info(
                "find_member result",
                benefit_id=str(benefit_id),
                is_found=bool(member is not None),
                benefit_id_type="member_level"
                if is_member_level_lookup
                else "wallet_level",
            )
            return None

        log.info(
            "find_member result",
            benefit_id=str(benefit_id),
            is_found=bool(member is not None),
            benefit_id_type="member_level"
            if is_member_level_lookup
            else "wallet_level",
            user_id=str(member.user_id),
        )
        return member

    def match_wallet_summary_and_setting(
        self, user_id: int, org_wallet_settings: list[OrganizationWalletSettings]
    ) -> Optional[Tuple[MemberWalletSummary, OrganizationWalletSettings]]:
        member_wallets: List[
            MemberWalletSummary
        ] = ReimbursementWalletService.get_enrolled_wallets(
            wallets=self.wallet_repo.get_clinic_portal_wallet_summaries(user_id=user_id)
        )

        if not member_wallets:
            log.info(
                "No active wallets with categories found for GREEN/GOLD member",
                user_id=user_id,
            )
            return None

        wallet_summary = member_wallets[0]

        matched_org_wallet_setting = next(
            (
                w
                for w in org_wallet_settings
                if w.org_settings_id == wallet_summary.org_settings_id
            ),
            None,
        )

        if not matched_org_wallet_setting:
            log.info(
                "Wallet found for member does not correspond with any offered wallets",
                user_id=user_id,
                wallet_org_setting=str(wallet_summary.org_settings_id),
            )
            return None

        return wallet_summary, matched_org_wallet_setting

    @ddtrace.tracer.wrap()
    def lookup(
        self,
        last_name: str,
        date_of_birth: date,
        benefit_id: str,
        headers: Mapping[str, str],
    ) -> Optional[MemberLookupResponse]:
        # Initial validation of input
        if None in (last_name, date_of_birth, benefit_id):
            raise TypeError("last_name, date_of_birth, benefit_id can't be None")

        if (
            profile := self.find_member(
                last_name=last_name, date_of_birth=date_of_birth, benefit_id=benefit_id
            )
        ) is None:
            log.info("Member not found", benefit_id=benefit_id)
            return None

        # Get the current member type, if it's MARKETPLACE, return not found
        if (
            current_member_type := self.wallet_repo.get_member_type(
                user_id=profile.user_id
            )
        ) == MemberType.MARKETPLACE:
            log.info(
                "Member is MARKETPLACE - returning not found",
                benefit_id=benefit_id,
                user_id=profile.user_id,
            )
            return None

        # Fetch the eligible member type and eligible org wallet settings if there are any
        (
            offered_member_type,
            offered_org_wallet_settings,
        ) = self.get_eligible_member_type(user_id=profile.user_id)

        if not offered_org_wallet_settings:
            log.info(
                "This is not an enterprise member - returning None",
                user_id=profile.user_id,
                benefit_id=benefit_id,
            )
            return None
        elif current_member_type == MemberType.MAVEN_ACCESS:
            wallet_setting: OrganizationWalletSettings = offered_org_wallet_settings[0]
            return self._build_access_response(
                profile=profile,
                current_member_type=current_member_type,
                offered_member_type=offered_member_type,
                wallet_setting=wallet_setting,
            )

        if (
            eligible_wallet_and_settings := self.match_wallet_summary_and_setting(
                user_id=profile.user_id, org_wallet_settings=offered_org_wallet_settings
            )
        ) is not None:
            wallet_summary = eligible_wallet_and_settings[0]
            wallet_setting = eligible_wallet_and_settings[1]
        else:
            return None

        log.info(
            "Member found",
            benefit_id=benefit_id,
            member_type=str(current_member_type.value),
            user_id=str(profile.user_id),
        )

        # Build the response based on the member type
        if current_member_type == MemberType.MAVEN_GREEN:
            return self._build_green_response(
                profile=profile,
                current_member_type=current_member_type,
                offered_member_type=offered_member_type,
                wallet_summary=wallet_summary,
                wallet_setting=wallet_setting,
            )
        elif current_member_type == MemberType.MAVEN_GOLD:
            # Get the direct payment category offered by the organization, but the member may or may not have access to
            if (
                offered_direct_payment_category := wallet_summary.wallet.get_org_direct_payment_category
            ) is None:
                log.info(
                    "No direct payment category found for GOLD member",
                    user_id=profile.user_id,
                    benefit_id=benefit_id,
                )
                return None

            category_balance: Optional[CategoryBalance] = None

            if (
                enrolled_direct_payment_category := wallet_summary.wallet.get_direct_payment_category
            ) is not None:
                if (
                    category_association := enrolled_direct_payment_category.get_category_association(
                        reimbursement_wallet=wallet_summary.wallet  # type: ignore[arg-type]
                    )
                ) is None:
                    log.info(
                        "No category association found for DP category",
                        user_id=profile.user_id,
                        benefit_id=benefit_id,
                    )
                else:
                    log.info(
                        "Category association found for DP category",
                        user_id=profile.user_id,
                        benefit_id=benefit_id,
                        category_association_id=category_association.id,
                    )
                    category_balance = (
                        ReimbursementWalletService().get_wallet_category_balance(
                            wallet=wallet_summary.wallet,
                            category_association=category_association,
                            include_procedures_without_cb=True,
                        )
                    )

            # Check if payment method is on file
            is_payment_method_on_file: bool = (
                MemberLookupService.is_payment_method_on_file(
                    payments_customer_id=wallet_summary.payments_customer_id,
                    headers=headers,
                )
            )
            self._send_gold_notifications(
                profile=profile,
                wallet_summary=wallet_summary,
                missing_payment_information=not is_payment_method_on_file,
            )
            return self._build_gold_response(
                profile=profile,
                current_member_type=current_member_type,
                offered_member_type=offered_member_type,
                wallet_summary=wallet_summary,
                wallet_setting=wallet_setting,
                category_balance=category_balance,
                offered_direct_payment_category=offered_direct_payment_category,
                is_payment_method_on_file=is_payment_method_on_file,
                headers=headers,
            )
        else:
            return None

    @staticmethod
    def _build_access_response(
        profile: MemberBenefitProfile,
        current_member_type: MemberType,
        offered_member_type: MemberType,
        wallet_setting: OrganizationWalletSettings,
    ) -> MemberLookupResponse:
        return MemberLookupResponse(
            member=ClinicPortalMember(
                user_id=profile.user_id,
                first_name=profile.first_name,
                last_name=profile.last_name,
                date_of_birth=profile.date_of_birth.strftime("%Y-%m-%d"),
                phone=profile.phone,
                email=profile.email,
                benefit_id=profile.benefit_id,
                current_type=current_member_type.value,
                eligible_type=offered_member_type.value,
                eligibility_start_date=None,
                eligibility_end_date=None,
            ),
            benefit=MemberBenefit(
                organization=ClinicPortalOrganization(
                    name=wallet_setting.organization_name,
                    fertility_program=None,
                ),
                wallet=None,
            ),
            content=None,
        )

    @staticmethod
    def _build_green_response(
        profile: MemberBenefitProfile,
        current_member_type: MemberType,
        offered_member_type: MemberType,
        wallet_summary: MemberWalletSummary,
        wallet_setting: OrganizationWalletSettings,
    ) -> MemberLookupResponse:
        return MemberLookupResponse(
            member=ClinicPortalMember(
                user_id=profile.user_id,
                first_name=profile.first_name,
                last_name=profile.last_name,
                date_of_birth=profile.date_of_birth.strftime("%Y-%m-%d"),
                phone=profile.phone,
                email=profile.email,
                benefit_id=profile.benefit_id,
                current_type=current_member_type.value,
                eligible_type=offered_member_type.value,
                eligibility_start_date=None,
                eligibility_end_date=None,
            ),
            benefit=MemberBenefit(
                organization=ClinicPortalOrganization(
                    name=wallet_setting.organization_name,
                    fertility_program=None,
                ),
                wallet=WalletOverview(
                    wallet_id=wallet_summary.wallet_id,  # type: ignore[typeddict-item]
                    benefit_type=None,
                    state=wallet_summary.wallet_state.value,
                    balance=WalletBalance(
                        total=0,
                        available=0,
                        is_unlimited=False,
                    ),
                    allow_treatment_scheduling=False,
                    payment_method_on_file=False,
                ),
            ),
            content=None,
        )

    def _build_gold_response(
        self,
        profile: MemberBenefitProfile,
        current_member_type: MemberType,
        offered_member_type: MemberType,
        wallet_summary: MemberWalletSummary,
        wallet_setting: OrganizationWalletSettings,
        category_balance: Optional[CategoryBalance],
        offered_direct_payment_category: ReimbursementRequestCategory,
        is_payment_method_on_file: bool,
        headers: Mapping[str, str],
    ) -> MemberLookupResponse:
        (
            eligibility_start_date,
            eligibility_end_date,
        ) = self.wallet_repo.get_wallet_eligibility_dates(
            user_id=profile.user_id, wallet_id=wallet_summary.wallet_id
        )

        portal_content = self.get_portal_content(
            wallet=wallet_summary.wallet,
            offered_direct_payment_category=offered_direct_payment_category,
        )

        allow_treatment_scheduling = self.resolve_allow_treatment_scheduling(
            direct_payment_category=wallet_summary.wallet.get_direct_payment_category,
            payment_method_on_file=is_payment_method_on_file,
        )

        if not category_balance:
            # If the category balance is None, the member does not have access to the direct payment category
            total = 0
            available = 0
            is_unlimited = False
            benefit_type = None
        elif category_balance.is_unlimited:
            # Balance response for unlimited benefits
            total = None
            available = None
            is_unlimited = True
            benefit_type = category_balance.benefit_type.value
        else:
            # Balance response for limited benefits
            total = category_balance.limit_amount
            available = category_balance.available_balance
            is_unlimited = False
            benefit_type = category_balance.benefit_type.value

        return MemberLookupResponse(
            member=ClinicPortalMember(
                user_id=profile.user_id,
                first_name=profile.first_name,
                last_name=profile.last_name,
                date_of_birth=profile.date_of_birth.strftime("%Y-%m-%d"),
                phone=profile.phone,
                email=profile.email,
                benefit_id=profile.benefit_id,
                current_type=current_member_type.value,
                eligible_type=offered_member_type.value,
                eligibility_start_date=eligibility_start_date.strftime("%Y-%m-%d")
                if eligibility_start_date
                else None,
                eligibility_end_date=eligibility_end_date.strftime("%Y-%m-%d")
                if eligibility_end_date
                else None,
            ),
            benefit=MemberBenefit(
                organization=ClinicPortalOrganization(
                    name=wallet_setting.organization_name,
                    fertility_program=ClinicPortalFertilityProgram(
                        program_type=wallet_setting.fertility_program_type.value,  # type: ignore[typeddict-item]
                        allows_taxable=wallet_setting.fertility_allows_taxable,  # type: ignore[typeddict-item]
                        direct_payment_enabled=wallet_setting.direct_payment_enabled,  # type: ignore[typeddict-item]
                        dx_required_procedures=wallet_setting.dx_required_procedures,
                        excluded_procedures=self.get_procedures_by_ids(
                            procedure_ids=wallet_setting.excluded_procedures,
                            headers=headers,
                        ),
                    ),
                ),
                wallet=WalletOverview(
                    wallet_id=wallet_summary.wallet_id,  # type: ignore[typeddict-item]
                    benefit_type=benefit_type,
                    state=wallet_summary.wallet_state.value,
                    balance=WalletBalance(
                        total=total, available=available, is_unlimited=is_unlimited
                    ),
                    allow_treatment_scheduling=allow_treatment_scheduling,
                    payment_method_on_file=is_payment_method_on_file,
                ),
            ),
            content=portal_content,
        )

    def _send_gold_notifications(
        self,
        profile: MemberBenefitProfile,
        wallet_summary: MemberWalletSummary,
        missing_payment_information: bool,
    ) -> None:
        if feature_flags.bool_variation(
            CLINIC_PORTAL_CHECK_FOR_MHP_AND_PAYMENT_METHOD_PRESENCE,
            default=False,
        ):
            missing_health_plan = self.fails_member_health_plan_check(
                member_id=profile.user_id,
                wallet=wallet_summary.wallet,
                effective_date=datetime.now(timezone.utc).date(),
            )
            log.info(
                "Checking for missing health plan and missing payment info",
                wallet_id=str(wallet_summary.wallet_id),
                missing_payment_information=missing_payment_information,
                missing_health_plan=missing_health_plan,
            )
            if missing_health_plan or missing_payment_information:
                log.info(
                    "Sending Notification",
                    event_name=EventName.MMB_CLINIC_PORTAL_MISSING_INFO.value,
                )
                # Send delayed email reminder to add payment method and/or health plan
                send_notification_event.delay(
                    user_id=str(wallet_summary.wallet_id),
                    user_id_type=UserIdType.WALLET_ID.value,
                    user_type=UserType.MEMBER.value,
                    event_source_system=EventSourceSystem.WALLET.value,
                    event_name=EventName.MMB_CLINIC_PORTAL_MISSING_INFO.value,
                    event_properties={
                        "benefit_id": profile.benefit_id,
                        "missing_payment_information": missing_payment_information,
                        "missing_health_plan_information": missing_health_plan,
                    },
                )
        # remove the else block when the feature flag is removed
        else:
            log.info(
                "Checking for missing payment info",
                wallet_id=str(wallet_summary.wallet_id),
                missing_payment_information=missing_payment_information,
            )
            if missing_payment_information:
                # Send delayed email reminder to add payment method
                log.info(
                    "Sending Notification",
                    event_name=EventName.MMB_PAYMENT_METHOD_REQUIRED.value,
                )
                send_notification_event.delay(
                    user_id=str(wallet_summary.wallet_id),
                    user_id_type=UserIdType.WALLET_ID.value,
                    user_type=UserType.MEMBER.value,
                    event_source_system=EventSourceSystem.WALLET.value,
                    event_name=EventName.MMB_PAYMENT_METHOD_REQUIRED.value,
                    event_properties={"benefit_id": profile.benefit_id},
                )

    @ddtrace.tracer.wrap()
    def get_portal_content(
        self,
        wallet: ReimbursementWallet,
        offered_direct_payment_category: ReimbursementRequestCategory,
    ) -> Optional[PortalContent]:
        """
        If the member has a direct payment category, we should return None since the `content` obj only handles
        If the member does not have a direct payment category because of TOC rule failure, return appropriate content
        """
        if wallet.get_direct_payment_category is not None:
            # Note: This will be expanded as we migrate content rendering logic from the FE to the BE
            return None

        # If there is no direct_payment category available, fetch the reasons why
        category_failures: list[
            ReimbursementWalletCategoryRuleEvaluationFailure
        ] = self.category_repo.get_evaluation_failures(
            wallet_id=wallet.id, category_id=offered_direct_payment_category.id
        )

        log.info(
            "No direct payment category found during clinic portal lookup",
            category_failures=str(category_failures),
            wallet_id=str(wallet.id),
        )
        return self.build_portal_content_from_category_failures(
            category_failures=category_failures
        )

    @staticmethod
    @ddtrace.tracer.wrap()
    def build_portal_content_from_category_failures(
        category_failures: list[ReimbursementWalletCategoryRuleEvaluationFailure],
    ) -> PortalContent:
        # There should be only a single rule failure but let's prioritize TOC over tenure
        if any(failure.rule_name in TOC_RULES for failure in category_failures):
            return PortalContent(
                messages=[
                    PortalMessage(
                        text="Please submit authorizations for this member to Progyny through 4/30/2025.",
                        level=PortalMessageLevel.ATTENTION,
                    )
                ],
                body_variant=BodyVariant.PROGYNY_TOC,
            )
        else:
            log.error(
                "Unhandled rule evaluation failure encountered while building portal content",
                category_failures=str(category_failures),
            )
            raise ClinicPortalException("Unhandled rule evaluation failure")

    @staticmethod
    @ddtrace.tracer.wrap()
    def resolve_allow_treatment_scheduling(
        payment_method_on_file: bool,
        direct_payment_category: ReimbursementRequestCategory | None = None,
    ) -> bool:
        return bool(direct_payment_category and payment_method_on_file)

    @ddtrace.tracer.wrap()
    def get_eligible_member_type(
        self, user_id: int
    ) -> Tuple[MemberType, List[OrganizationWalletSettings]]:
        # Check if member is org sponsored
        e9y_service = EnterpriseVerificationService()
        eligible_org_ids: Set[int] = e9y_service.get_eligible_organization_ids_for_user(
            user_id=user_id
        )

        if not eligible_org_ids:
            return MemberType.MARKETPLACE, []

        # Check if member has an active track, if not, they are eligible for MAVEN_ACCESS
        tracks = TrackSelectionService()
        is_enterprise: bool = tracks.is_enterprise(user_id=user_id)
        enrolled_org_id: int = tracks.get_organization_id_for_user(user_id=user_id)

        if is_enterprise is False or enrolled_org_id is None:
            return MemberType.MAVEN_ACCESS, []

        organization_wallet_settings: List[
            OrganizationWalletSettings
        ] = self.wallet_repo.get_eligible_org_wallet_settings(
            user_id=user_id, organization_id=enrolled_org_id
        )

        if not organization_wallet_settings:
            log.info(
                "No org settings found for user",
                user_id=str(user_id),
                organization_id=str(enrolled_org_id),
            )
            return MemberType.MAVEN_ACCESS, []

        log.info(
            "user eligible org settings",
            user_id=str(user_id),
            eligible_org_settings=organization_wallet_settings,
        )

        # No wallet org settings were found
        if all(
            setting.org_settings_id is None for setting in organization_wallet_settings
        ):
            return MemberType.MAVEN_ACCESS, organization_wallet_settings

        # At least one direct payment enabled org setting was found
        if any(
            setting.direct_payment_enabled for setting in organization_wallet_settings
        ):
            return MemberType.MAVEN_GOLD, organization_wallet_settings

        # Standard reimbursement wallet settings were found
        return MemberType.MAVEN_GREEN, organization_wallet_settings

    @ddtrace.tracer.wrap()
    def fails_member_health_plan_check(
        self, member_id: int, wallet: ReimbursementWallet, effective_date: datetime.date
    ) -> bool:
        if MemberLookupService._needs_mhp_info_check(
            member_id=member_id, wallet=wallet, effective_date=effective_date
        ):
            to_return = not self.health_plan_repo.has_member_health_plan_by_wallet_and_member_id(
                member_id=member_id,
                wallet_id=wallet.id,
                effective_date=effective_date,
            )
            log.info(
                "Checked if member health plan is missing.",
                missing_plan=to_return,
                member_id=str(member_id),
                wallet_id=str(wallet.id),
                effective_date=str(effective_date),
            )
            return to_return
        else:
            log.info(
                "Member Health Plan check not needed.",
                member_id=str(member_id),
                wallet_id=str(wallet.id),
                effective_date=str(effective_date),
            )
            return False

    @staticmethod
    def get_procedures_by_ids(
        procedure_ids: List[str], headers: Mapping[str, str]
    ) -> List[ClinicPortalProcedure]:
        if not procedure_ids:
            return []

        service = ProcedureService()

        procedures = service.get_procedures_by_ids(
            procedure_ids=procedure_ids, headers=headers
        )

        if not procedures:
            raise MissingProcedureData("Failed to retrieve procedures for org.")

        return [
            ClinicPortalProcedure(
                procedure_id=p["id"], procedure_name=p["name"]
            )  # noqa
            for p in procedures
        ]

    @staticmethod
    def is_payment_method_on_file(
        payments_customer_id: str | None, headers: Mapping[str, str]
    ) -> bool:
        if not payments_customer_id:
            return False

        try:
            gateway_client = get_client(INTERNAL_TRUST_PAYMENT_GATEWAY_URL)  # type: ignore[arg-type] # Argument 1 to "get_client" has incompatible type "Optional[str]"; expected "str"
            payments_customer: Customer | None = gateway_client.get_customer(
                customer_id=payments_customer_id,
                headers=headers,
            )
        except Exception as e:
            log.exception(
                "Exception encountered while fetching payment method",
                payments_customer_id=payments_customer_id,
                error=e,
            )
            # Default to True if there is an exception
            # We will allow and then alert/log on treatment procedure creation
            return True
        else:
            if not payments_customer:
                return False

            return bool(payments_customer.payment_methods)

    @staticmethod
    def _needs_mhp_info_check(
        member_id: int, wallet: ReimbursementWallet, effective_date: datetime.date
    ) -> bool:
        # FDC = ROS deductible accumulation not enabled and member not on HDHP (no need for MHP)
        # HDHP = ROS deductible accumulation not enabled and member on HDHP (need MHP)
        # DA (need a better name for this) = ROS deductible accumulation enabled
        # (need MHP regardless of what type of plan they’re on)
        event_name = "Health plan check needed."
        if wallet.reimbursement_organization_settings.deductible_accumulation_enabled:
            log.info(
                event_name,
                reason="Deductible accumulation enabled on wallet ROS.",
                wallet_id=str(wallet.id),
            )
            return True
        # if we are here - it's FDC. Data model does not reflect it but they are mutually exclusive
        # check if the user has an HDHP plan in the reimbursement plan table (unlikely that MHP does not exist but possible)
        if MemberLookupService._check_hdhp_exists_for_wallet_date(
            wallet_id=wallet.id, effective_date=effective_date
        ):
            log.info(
                event_name,
                reason="HDHP plan exists for wallet and effective date.",
                wallet_id=str(wallet.id),
                effective_date=str(effective_date),
            )
            return True
        # An HDHP plan exists for the org, but they did not take the annual survey.
        organization_id = wallet.reimbursement_organization_settings.organization_id
        if start_date := MemberLookupService._get_active_hdhp_plan_start_date(
            effective_date=effective_date,
            organization_id=organization_id,
        ):
            if not has_survey_been_taken(
                user_id=member_id, wallet_id=wallet.id, survey_year=start_date.year
            ):
                log.info(
                    event_name,
                    reason="Org has an HDHP plan but the user has not yet responded to the annual survey.",
                    wallet_id=str(wallet.id),
                    org_id=str(organization_id),
                    survey_year=start_date.year,
                )
                return True

        log.info(
            "Health plan check not needed",
            user_id=str(member_id),
            wallet_id=str(wallet.id),
            org_id=str(organization_id),
            effective_date=str(effective_date),
        )
        return False

    @staticmethod
    def _check_hdhp_exists_for_wallet_date(
        wallet_id: int, effective_date: datetime.date
    ) -> bool:
        return connection.db.session.query(
            exists().where(
                and_(
                    ReimbursementWalletPlanHDHP.reimbursement_plan_id
                    == ReimbursementPlan.id,
                    ReimbursementPlan.is_hdhp == True,
                    ReimbursementPlan.start_date <= effective_date,
                    ReimbursementPlan.end_date >= effective_date,
                    ReimbursementWalletPlanHDHP.reimbursement_wallet_id == wallet_id,
                )
            )
        ).scalar()

    @staticmethod
    def _get_active_hdhp_plan_start_date(
        organization_id: int, effective_date: datetime.date
    ) -> datetime.date | None:
        res = (
            connection.db.session.query(ReimbursementPlan.start_date)
            .filter(
                ReimbursementPlan.is_hdhp == True,
                ReimbursementPlan.start_date <= effective_date,
                ReimbursementPlan.end_date >= effective_date,
                ReimbursementPlan.organization_id == organization_id,
            )
            .one_or_none()
        )
        return res.start_date if res else None


class MemberTypeException(Exception):
    pass


class ClinicPortalException(Exception):
    pass
