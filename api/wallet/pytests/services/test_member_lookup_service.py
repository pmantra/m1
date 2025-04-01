from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest import mock

import pytest

from authn.models.user import User
from common.global_procedures.procedure import MissingProcedureData
from common.payments_gateway import Customer
from direct_payment.clinic.models.portal import (
    BodyVariant,
    ClinicPortalFertilityProgram,
    ClinicPortalMember,
    ClinicPortalOrganization,
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
from wallet.models.constants import BenefitTypes, FertilityProgramTypes, MemberType
from wallet.models.models import (
    MemberBenefitProfile,
    MemberWalletSummary,
    OrganizationWalletSettings,
)
from wallet.models.reimbursement_wallet import (
    ReimbursementWallet,
    ReimbursementWalletCategoryRuleEvaluationFailure,
)
from wallet.pytests.factories import MemberHealthPlanFactory
from wallet.pytests.services.conftest import BENEFIT_ID
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR
from wallet.services.member_lookup import (
    CLINIC_PORTAL_CHECK_FOR_MHP_AND_PAYMENT_METHOD_PRESENCE,
    ClinicPortalException,
    MemberLookupService,
)


@pytest.fixture()
def mock_wallet_repository():
    with mock.patch(
        "wallet.repository.reimbursement_wallet.ReimbursementWalletRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture()
def mock_member_benefit_repository():
    with mock.patch(
        "wallet.repository.member_benefit.MemberBenefitRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture
def member_lookup_service(mock_wallet_repository, mock_member_benefit_repository):
    return MemberLookupService(
        wallet_repo=mock_wallet_repository,
        member_benefit_repo=mock_member_benefit_repository,
    )


class TestGetEligibleMemberType:
    @staticmethod
    def test_get_eligible_member_type_marketplace(
        member_lookup_service: MemberLookupService, enterprise_user: User
    ):
        # Given

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user"
        ) as mock_get_org_id:
            mock_get_org_id.return_value = set()

            member_type, _ = member_lookup_service.get_eligible_member_type(
                user_id=enterprise_user.id
            )

        # Then
        assert member_type == MemberType.MARKETPLACE

    @staticmethod
    def test_get_eligible_member_type_maven_access_eligible_user_not_enrolled(
        member_lookup_service: MemberLookupService, enterprise_user: User
    ):
        # Given

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
            return_value={1},
        ), mock.patch(
            "tracks.service.tracks.TrackSelectionService.get_organization_id_for_user",
            return_value=None,
        ):
            member_type, _ = member_lookup_service.get_eligible_member_type(
                user_id=enterprise_user.id
            )

        # Then
        assert member_type == MemberType.MAVEN_ACCESS

    @staticmethod
    def test_get_eligible_member_type_maven_access(
        member_lookup_service: MemberLookupService,
        enterprise_user: User,
        org_wallet_settings_enterprise: OrganizationWalletSettings,
    ):
        # Given
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = [
            org_wallet_settings_enterprise
        ]

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user"
        ) as mock_get_org_id:
            mock_get_org_id.return_value = {1}

            member_type, _ = member_lookup_service.get_eligible_member_type(
                user_id=enterprise_user.id
            )

        # Then
        assert member_type == MemberType.MAVEN_ACCESS

    @staticmethod
    def test_get_eligible_member_type_maven_gold(
        member_lookup_service: MemberLookupService, enterprise_user: User
    ):
        # Given
        # No wallet org settings
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = [
            OrganizationWalletSettings(
                organization_id=1,
                org_settings_id=1,
                direct_payment_enabled=True,
                organization_name="",
                fertility_program_type=FertilityProgramTypes.CARVE_OUT,
                fertility_allows_taxable=True,
                excluded_procedures=[],
                dx_required_procedures=[],
            )
        ]

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user"
        ) as mock_get_org_id:
            mock_get_org_id.return_value = {1}

            member_type, _ = member_lookup_service.get_eligible_member_type(
                user_id=enterprise_user.id
            )

        # Then
        assert member_type == MemberType.MAVEN_GOLD

    @staticmethod
    def test_get_eligible_member_type_maven_green(
        member_lookup_service: MemberLookupService, enterprise_user: User
    ):
        # Given
        # No wallet org settings
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = [
            OrganizationWalletSettings(
                organization_id=1,
                org_settings_id=1,
                direct_payment_enabled=False,
                organization_name="",
                fertility_program_type=FertilityProgramTypes.CARVE_OUT,
                fertility_allows_taxable=True,
                excluded_procedures=[],
                dx_required_procedures=[],
            )
        ]

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user"
        ) as mock_get_org_id:
            mock_get_org_id.return_value = {1}

            member_type, _ = member_lookup_service.get_eligible_member_type(
                user_id=enterprise_user.id
            )

        # Then
        assert member_type == MemberType.MAVEN_GREEN

    @staticmethod
    def test_get_eligible_member_type_maven_gold_multiple_settings_available(
        member_lookup_service: MemberLookupService, enterprise_user: User
    ):
        # Given
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = [
            OrganizationWalletSettings(
                organization_id=1,
                org_settings_id=1,
                direct_payment_enabled=False,
                organization_name="",
                fertility_program_type=FertilityProgramTypes.CARVE_OUT,
                fertility_allows_taxable=True,
                excluded_procedures=[],
                dx_required_procedures=[],
            ),
            OrganizationWalletSettings(
                organization_id=1,
                org_settings_id=2,
                direct_payment_enabled=True,
                organization_name="",
                fertility_program_type=FertilityProgramTypes.CARVE_OUT,
                fertility_allows_taxable=True,
                excluded_procedures=[],
                dx_required_procedures=[],
            ),
        ]

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user"
        ) as mock_get_org_id:
            mock_get_org_id.return_value = {1}

            member_type, _ = member_lookup_service.get_eligible_member_type(
                user_id=enterprise_user.id
            )

        # Then
        assert member_type == MemberType.MAVEN_GOLD

    @staticmethod
    def test_get_eligible_member_type_no_org_wallet_settings(
        member_lookup_service: MemberLookupService, enterprise_user: User
    ):
        # Given
        # No wallet org settings
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = (
            []
        )

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user"
        ) as mock_get_org_id:
            mock_get_org_id.return_value = {1}

            member_type, org_settings = member_lookup_service.get_eligible_member_type(
                user_id=enterprise_user.id
            )

        # Then
        assert member_type == MemberType.MAVEN_ACCESS
        assert org_settings == []


class TestLookup:
    @staticmethod
    def test_lookup_member_not_found(
        member_lookup_service: MemberLookupService,
        enterprise_member_benefit_profile: MemberBenefitProfile,
    ):
        # Given
        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService.find_member"
        ) as mock_find_member:
            mock_find_member.return_value = None

            # When
            res = member_lookup_service.lookup(
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                headers={},
            )

        # Then
        assert res is None

    @staticmethod
    def test_lookup_marketplace_member(
        member_lookup_service: MemberLookupService,
        marketplace_member_benefit_profile: MemberBenefitProfile,
    ):
        # Given
        member_lookup_service.wallet_repo.get_member_type.return_value = (
            MemberType.MARKETPLACE
        )

        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService.find_member"
        ) as mock_find_member:
            mock_find_member.return_value = marketplace_member_benefit_profile

            # When
            res = member_lookup_service.lookup(
                last_name=marketplace_member_benefit_profile.last_name,
                date_of_birth=marketplace_member_benefit_profile.date_of_birth,
                benefit_id=marketplace_member_benefit_profile.benefit_id,
                headers={},
            )

        # Then
        assert not res

    @staticmethod
    def test_lookup_access_member(
        member_lookup_service: MemberLookupService,
        enterprise_user: User,
        enterprise_member_benefit_profile: MemberBenefitProfile,
    ):
        # Given
        org_wallet_setting = OrganizationWalletSettings(
            organization_id=enterprise_user.organization.id,
            organization_name=enterprise_user.organization.name,
            direct_payment_enabled=False,
            org_settings_id=None,
        )
        member_lookup_service.wallet_repo.get_member_type.return_value = (
            MemberType.MAVEN_ACCESS
        )
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = [
            org_wallet_setting
        ]

        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService.find_member"
        ) as mock_find_member, mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
            return_value={1},
        ):
            mock_find_member.return_value = enterprise_member_benefit_profile

            # When
            res = member_lookup_service.lookup(
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                headers={},
            )

        # Then
        assert res == MemberLookupResponse(
            member=ClinicPortalMember(
                user_id=enterprise_member_benefit_profile.user_id,
                first_name=enterprise_member_benefit_profile.first_name,
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth.strftime(
                    "%Y-%m-%d"
                ),
                phone=enterprise_member_benefit_profile.phone,
                email=enterprise_member_benefit_profile.email,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                current_type=MemberType.MAVEN_ACCESS.value,
                eligible_type=MemberType.MAVEN_ACCESS.value,
                eligibility_end_date=None,
                eligibility_start_date=None,
            ),
            benefit=MemberBenefit(
                organization=ClinicPortalOrganization(
                    name=enterprise_user.organization_v2.name, fertility_program=None
                ),
                wallet=None,
            ),
            content=None,
        )

    @staticmethod
    def test_lookup_access_member_no_org_settings(
        member_lookup_service: MemberLookupService,
        enterprise_user: User,
        enterprise_member_benefit_profile: MemberBenefitProfile,
    ):
        # Given
        member_lookup_service.wallet_repo.get_member_type.return_value = (
            MemberType.MAVEN_ACCESS
        )
        eligible_member_type = MemberType.MAVEN_ACCESS
        eligible_settings = []

        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService.find_member"
        ) as mock_find_member, mock.patch(
            "wallet.services.member_lookup.MemberLookupService.get_eligible_member_type"
        ) as mock_get_eligible_member_type:
            mock_find_member.return_value = enterprise_member_benefit_profile
            mock_get_eligible_member_type.return_value = (
                eligible_member_type,
                eligible_settings,
            )

            # When
            res = member_lookup_service.lookup(
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                headers={},
            )

        # Then
        assert not res

    @staticmethod
    def test_lookup_green_member(
        member_lookup_service: MemberLookupService,
        enterprise_member_benefit_profile: MemberBenefitProfile,
        active_clinic_portal_member_wallet_summary_reimbursement: MemberWalletSummary,
        org_wallet_settings_reimbursement: OrganizationWalletSettings,
    ):
        # Given
        member_lookup_service.wallet_repo.get_member_type.return_value = (
            MemberType.MAVEN_GREEN
        )
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = [
            org_wallet_settings_reimbursement
        ]
        member_lookup_service.wallet_repo.get_clinic_portal_wallet_summaries.return_value = [
            active_clinic_portal_member_wallet_summary_reimbursement
        ]

        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService.find_member"
        ) as mock_find_member, mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
            return_value={1},
        ):
            mock_find_member.return_value = enterprise_member_benefit_profile

            # When
            res = member_lookup_service.lookup(
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                headers={},
            )

        # Then
        assert res == MemberLookupResponse(
            member=ClinicPortalMember(
                user_id=enterprise_member_benefit_profile.user_id,
                first_name=enterprise_member_benefit_profile.first_name,
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth.strftime(
                    "%Y-%m-%d"
                ),
                phone=enterprise_member_benefit_profile.phone,
                email=enterprise_member_benefit_profile.email,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                current_type=MemberType.MAVEN_GREEN.value,
                eligible_type=MemberType.MAVEN_GREEN.value,
                eligibility_end_date=None,
                eligibility_start_date=None,
            ),
            benefit=MemberBenefit(
                organization=ClinicPortalOrganization(
                    name=org_wallet_settings_reimbursement.organization_name,
                    fertility_program=None,
                ),
                wallet=WalletOverview(
                    wallet_id=active_clinic_portal_member_wallet_summary_reimbursement.wallet_id,
                    benefit_type=None,
                    state=active_clinic_portal_member_wallet_summary_reimbursement.wallet_state.value,
                    balance=WalletBalance(total=0, available=0, is_unlimited=False),
                    payment_method_on_file=False,
                    allow_treatment_scheduling=False,
                ),
            ),
            content=None,
        )

    @staticmethod
    def test_lookup_gold_member(
        member_lookup_service: MemberLookupService,
        enterprise_member_benefit_profile: MemberBenefitProfile,
        active_clinic_portal_member_wallet_summary_direct_payment: MemberWalletSummary,
        org_wallet_settings_direct_payment: OrganizationWalletSettings,
    ):
        # Given
        member_lookup_service.wallet_repo.get_member_type.return_value = (
            MemberType.MAVEN_GOLD
        )
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = [
            org_wallet_settings_direct_payment
        ]
        member_lookup_service.wallet_repo.get_clinic_portal_wallet_summaries.return_value = [
            active_clinic_portal_member_wallet_summary_direct_payment
        ]
        eligibility_start_date = datetime(year=2020, month=1, day=1).date()
        eligibility_end_date = datetime(year=2023, month=12, day=31).date()
        member_lookup_service.wallet_repo.get_wallet_eligibility_dates.return_value = (
            eligibility_start_date,
            eligibility_end_date,
        )

        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService.find_member"
        ) as mock_find_member, mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
            return_value={1},
        ):
            mock_find_member.return_value = enterprise_member_benefit_profile

            # When
            res = member_lookup_service.lookup(
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                headers={},
            )

        # Then
        assert res == MemberLookupResponse(
            member=ClinicPortalMember(
                user_id=enterprise_member_benefit_profile.user_id,
                first_name=enterprise_member_benefit_profile.first_name,
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth.strftime(
                    "%Y-%m-%d"
                ),
                phone=enterprise_member_benefit_profile.phone,
                email=enterprise_member_benefit_profile.email,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                current_type=MemberType.MAVEN_GOLD.value,
                eligible_type=MemberType.MAVEN_GOLD.value,
                eligibility_start_date=eligibility_start_date.strftime("%Y-%m-%d"),
                eligibility_end_date=eligibility_end_date.strftime("%Y-%m-%d"),
            ),
            benefit=MemberBenefit(
                organization=ClinicPortalOrganization(
                    name=org_wallet_settings_direct_payment.organization_name,
                    fertility_program=ClinicPortalFertilityProgram(
                        allows_taxable=org_wallet_settings_direct_payment.fertility_allows_taxable,
                        direct_payment_enabled=org_wallet_settings_direct_payment.direct_payment_enabled,
                        program_type=org_wallet_settings_direct_payment.fertility_program_type.value,
                        dx_required_procedures=org_wallet_settings_direct_payment.dx_required_procedures,
                        excluded_procedures=mock.ANY,
                    ),
                ),
                wallet=WalletOverview(
                    wallet_id=active_clinic_portal_member_wallet_summary_direct_payment.wallet_id,
                    benefit_type=BenefitTypes.CURRENCY.value,
                    state=active_clinic_portal_member_wallet_summary_direct_payment.wallet_state.value,
                    balance=WalletBalance(
                        total=2500000, available=2500000, is_unlimited=False
                    ),
                    payment_method_on_file=False,
                    allow_treatment_scheduling=False,
                ),
            ),
            content=None,
        )

    @staticmethod
    def test_lookup_gold_member_without_dp_category_access(
        member_lookup_service: MemberLookupService,
        enterprise_member_benefit_profile: MemberBenefitProfile,
        active_clinic_portal_member_wallet_summary_direct_payment_without_dp_category_access: MemberWalletSummary,
        org_wallet_settings_direct_payment: OrganizationWalletSettings,
    ):
        # Given
        member_lookup_service.wallet_repo.get_member_type.return_value = (
            MemberType.MAVEN_GOLD
        )
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = [
            org_wallet_settings_direct_payment
        ]
        member_lookup_service.wallet_repo.get_clinic_portal_wallet_summaries.return_value = [
            active_clinic_portal_member_wallet_summary_direct_payment_without_dp_category_access
        ]
        member_lookup_service.wallet_repo.get_wallet_eligibility_dates.return_value = (
            None,
            None,
        )

        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService.find_member"
        ) as mock_find_member, mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
            return_value={1},
        ):
            mock_find_member.return_value = enterprise_member_benefit_profile

            # When
            res = member_lookup_service.lookup(
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                headers={},
            )

        # Then
        assert res == MemberLookupResponse(
            member=ClinicPortalMember(
                user_id=enterprise_member_benefit_profile.user_id,
                first_name=enterprise_member_benefit_profile.first_name,
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth.strftime(
                    "%Y-%m-%d"
                ),
                phone=enterprise_member_benefit_profile.phone,
                email=enterprise_member_benefit_profile.email,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                current_type=MemberType.MAVEN_GOLD.value,
                eligible_type=MemberType.MAVEN_GOLD.value,
                eligibility_start_date=None,
                eligibility_end_date=None,
            ),
            benefit=MemberBenefit(
                organization=ClinicPortalOrganization(
                    name=org_wallet_settings_direct_payment.organization_name,
                    fertility_program=ClinicPortalFertilityProgram(
                        allows_taxable=org_wallet_settings_direct_payment.fertility_allows_taxable,
                        direct_payment_enabled=org_wallet_settings_direct_payment.direct_payment_enabled,
                        program_type=org_wallet_settings_direct_payment.fertility_program_type.value,
                        dx_required_procedures=org_wallet_settings_direct_payment.dx_required_procedures,
                        excluded_procedures=mock.ANY,
                    ),
                ),
                wallet=WalletOverview(
                    wallet_id=active_clinic_portal_member_wallet_summary_direct_payment_without_dp_category_access.wallet_id,
                    benefit_type=None,
                    state=active_clinic_portal_member_wallet_summary_direct_payment_without_dp_category_access.wallet_state.value,
                    balance=WalletBalance(
                        total=0,
                        available=0,
                        is_unlimited=False,
                    ),
                    payment_method_on_file=False,
                    allow_treatment_scheduling=False,
                ),
            ),
            content=PortalContent(
                messages=[
                    PortalMessage(
                        text="Please submit authorizations for this member to Progyny through 4/30/2025.",
                        level=PortalMessageLevel.ATTENTION,
                    )
                ],
                body_variant=BodyVariant.PROGYNY_TOC,
            ),
        )

    @staticmethod
    def test_lookup_gold_member_calls_is_payment_method_on_file(
        member_lookup_service: MemberLookupService,
        enterprise_member_benefit_profile: MemberBenefitProfile,
        active_clinic_portal_member_wallet_summary_direct_payment: MemberWalletSummary,
        org_wallet_settings_direct_payment: OrganizationWalletSettings,
    ):
        # Given
        member_lookup_service.wallet_repo.get_member_type.return_value = (
            MemberType.MAVEN_GOLD
        )
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = [
            org_wallet_settings_direct_payment
        ]
        member_lookup_service.wallet_repo.get_clinic_portal_wallet_summaries.return_value = [
            active_clinic_portal_member_wallet_summary_direct_payment
        ]
        member_lookup_service.wallet_repo.get_wallet_eligibility_dates.return_value = (
            None,
            None,
        )

        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService.find_member"
        ) as mock_find_member, mock.patch(
            "wallet.services.member_lookup.MemberLookupService.is_payment_method_on_file"
        ) as mock_is_payment_method_on_file, mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
            return_value={1},
        ):
            mock_find_member.return_value = enterprise_member_benefit_profile

            # When
            member_lookup_service.lookup(
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                headers={},
            )

        # Then
        mock_is_payment_method_on_file.assert_called()

    @staticmethod
    def test_lookup_gold_member_calls_get_wallet_eligibility_dates(
        member_lookup_service: MemberLookupService,
        enterprise_member_benefit_profile: MemberBenefitProfile,
        active_clinic_portal_member_wallet_summary_direct_payment: MemberWalletSummary,
        org_wallet_settings_direct_payment: OrganizationWalletSettings,
    ):
        # Given
        member_lookup_service.wallet_repo.get_member_type.return_value = (
            MemberType.MAVEN_GOLD
        )
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = [
            org_wallet_settings_direct_payment
        ]
        member_lookup_service.wallet_repo.get_clinic_portal_wallet_summaries.return_value = [
            active_clinic_portal_member_wallet_summary_direct_payment
        ]
        member_lookup_service.wallet_repo.get_wallet_eligibility_dates.return_value = (
            None,
            None,
        )

        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService.find_member"
        ) as mock_find_member, mock.patch(
            "wallet.services.member_lookup.MemberLookupService.is_payment_method_on_file"
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
            return_value={1},
        ):
            mock_find_member.return_value = enterprise_member_benefit_profile

            # When
            member_lookup_service.lookup(
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                headers={},
            )

        # Then
        member_lookup_service.wallet_repo.get_wallet_eligibility_dates.assert_called()

    @staticmethod
    @pytest.mark.parametrize(
        "flag_val, exp_event_name, exp_event_properties",
        [
            (
                True,
                EventName.MMB_CLINIC_PORTAL_MISSING_INFO,
                {
                    "benefit_id": BENEFIT_ID,
                    "missing_health_plan_information": True,
                    "missing_payment_information": True,
                },
            ),
            (False, EventName.MMB_PAYMENT_METHOD_REQUIRED, {"benefit_id": BENEFIT_ID}),
        ],
    )
    def test_lookup_gold_member_payment_method_not_on_file_notification_triggered(
        member_lookup_service: MemberLookupService,
        enterprise_member_benefit_profile: MemberBenefitProfile,
        active_clinic_portal_member_wallet_summary_direct_payment: MemberWalletSummary,
        org_wallet_settings_direct_payment: OrganizationWalletSettings,
        ff_test_data,
        flag_val,
        exp_event_name,
        exp_event_properties,
    ):
        ff_test_data.update(
            ff_test_data.flag(
                CLINIC_PORTAL_CHECK_FOR_MHP_AND_PAYMENT_METHOD_PRESENCE
            ).variations(flag_val)
        )
        # Given
        active_clinic_portal_member_wallet_summary_direct_payment.wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            True
        )
        member_lookup_service.wallet_repo.get_member_type.return_value = (
            MemberType.MAVEN_GOLD
        )
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = [
            org_wallet_settings_direct_payment
        ]
        member_lookup_service.wallet_repo.get_clinic_portal_wallet_summaries.return_value = [
            active_clinic_portal_member_wallet_summary_direct_payment
        ]
        member_lookup_service.wallet_repo.get_wallet_eligibility_dates.return_value = (
            None,
            None,
        )

        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService.find_member"
        ) as mock_find_member, mock.patch(
            "direct_payment.notification.lib.tasks.rq_send_notification.send_notification_event.delay",
            side_effect=send_notification_event,
        ) as mock_send_notification_event, mock.patch(
            "wallet.services.member_lookup.MemberLookupService.is_payment_method_on_file"
        ) as mock_is_payment_method_on_file, mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
            return_value={1},
        ):
            mock_is_payment_method_on_file.return_value = False
            mock_find_member.return_value = enterprise_member_benefit_profile

            # When
            member_lookup_service.lookup(
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                headers={},
            )

        # Then
        mock_send_notification_event.assert_called_with(
            user_id=str(
                active_clinic_portal_member_wallet_summary_direct_payment.wallet_id
            ),
            user_id_type=UserIdType.WALLET_ID.value,
            user_type=UserType.MEMBER.value,
            event_source_system=EventSourceSystem.WALLET.value,
            event_name=exp_event_name.value,
            event_properties=exp_event_properties,
        )

    @staticmethod
    @pytest.mark.parametrize(
        argnames="arg_name", argvalues=["last_name", "date_of_birth", "benefit_id"]
    )
    def test_lookup_missing_params(
        member_lookup_service: MemberLookupService,
        enterprise_member_benefit_profile: MemberBenefitProfile,
        arg_name: str,
    ):
        # Given
        args = dict(
            last_name=enterprise_member_benefit_profile.last_name,
            date_of_birth=enterprise_member_benefit_profile.date_of_birth,
            benefit_id=enterprise_member_benefit_profile.benefit_id,
        )

        args.update({arg_name: None})

        # When - Then
        with pytest.raises(
            TypeError, match="last_name, date_of_birth, benefit_id can't be None"
        ):
            member_lookup_service.lookup(
                **args,
                headers={},
            )

    @staticmethod
    @pytest.mark.parametrize(argnames="arg_name", argvalues=["last_name", "benefit_id"])
    def test_lookup_params_are_empty_string(
        member_lookup_service: MemberLookupService,
        enterprise_member_benefit_profile: MemberBenefitProfile,
        arg_name: str,
    ):
        # Given
        args = dict(
            last_name=enterprise_member_benefit_profile.last_name,
            date_of_birth=enterprise_member_benefit_profile.date_of_birth,
            benefit_id=enterprise_member_benefit_profile.benefit_id,
        )

        args.update({arg_name: ""})

        # When
        found = member_lookup_service.lookup(
            **args,
            headers={},
        )

        # Then
        assert not found

    @staticmethod
    def test_lookup_gold_member_but_not_wallet_eligible_or_enterprise(
        member_lookup_service: MemberLookupService,
        enterprise_user: User,
        enterprise_member_benefit_profile: MemberBenefitProfile,
    ):
        """This handles an edge case in QA when a member could be missing a verification record but have a wallet"""
        # Given
        member_lookup_service.wallet_repo.get_member_type.return_value = (
            MemberType.MAVEN_GOLD
        )
        member_lookup_service.wallet_repo.get_eligible_org_wallet_settings.return_value = (
            []
        )

        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService.find_member"
        ) as mock_find_member, mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
            return_value={1},
        ):
            mock_find_member.return_value = enterprise_member_benefit_profile

            # When
            res = member_lookup_service.lookup(
                last_name=enterprise_member_benefit_profile.last_name,
                date_of_birth=enterprise_member_benefit_profile.date_of_birth,
                benefit_id=enterprise_member_benefit_profile.benefit_id,
                headers={},
            )

        # Then
        assert not res


class TestIsPaymentMethodOnFile:
    @staticmethod
    def test_is_payment_method_on_file_missing_payments_customer_id(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        payments_customer_id = None

        # When
        on_file: bool = member_lookup_service.is_payment_method_on_file(
            payments_customer_id=payments_customer_id, headers={}
        )

        # Then
        assert on_file is False

    @staticmethod
    def test_is_payment_method_on_file_success(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        payments_customer_id: str = "1111111"

        # When
        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.get_customer"
        ) as mock_get_customer:
            mock_get_customer.return_value = Customer(
                customer_id="",
                customer_setup_status=None,
                payment_method_types=[],
                payment_methods=[mock.MagicMock()],
            )
            on_file: bool = member_lookup_service.is_payment_method_on_file(
                payments_customer_id=payments_customer_id, headers={}
            )

        # Then
        assert on_file is True

    @staticmethod
    def test_is_payment_method_on_file_no_customer_found(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        payments_customer_id = "11111111"

        # When
        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.get_customer"
        ) as mock_get_customer:
            mock_get_customer.return_value = None
            on_file: bool = member_lookup_service.is_payment_method_on_file(
                payments_customer_id=payments_customer_id, headers={}
            )

        # Then
        assert on_file is False

    @staticmethod
    def test_is_payment_method_on_file_no_payment_method(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        payments_customer_id = "11111111"

        # When
        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.get_customer"
        ) as mock_get_customer:
            mock_get_customer.return_value = Customer(
                customer_id="",
                customer_setup_status=None,
                payment_method_types=[],
                payment_methods=[],
            )
            on_file: bool = member_lookup_service.is_payment_method_on_file(
                payments_customer_id=payments_customer_id, headers={}
            )

        # Then
        assert on_file is False

    @staticmethod
    def test_is_payment_method_on_file_exception(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        payments_customer_id = "1111111"

        # When
        with mock.patch(
            "common.payments_gateway.client.PaymentsGatewayClient.get_customer"
        ) as mock_get_customer:
            mock_get_customer.side_effect = Exception("payments gateway exception")
            on_file: bool = member_lookup_service.is_payment_method_on_file(
                payments_customer_id=payments_customer_id, headers={}
            )

        # Then
        assert on_file is True


class TestFindMember:
    @staticmethod
    def test_find_member_sanitizes_inputs(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        last_name = "Smith"
        dob = date(year=2000, month=5, day=21)
        benefit_id = "M9098938023"

        # When
        member_lookup_service.find_member(
            last_name=last_name + " ", date_of_birth=dob, benefit_id=" " + benefit_id
        )

        # Then
        member_lookup_service.member_benefit_repo.search_by_member_benefit_id.assert_called_with(
            last_name=last_name, date_of_birth=dob, benefit_id=benefit_id
        )

    @staticmethod
    def test_find_member_incorrect_format(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        last_name = "Smith"
        dob = date(year=2000, month=5, day=21)
        benefit_id = "C903932323"

        # When
        found = member_lookup_service.find_member(
            last_name=last_name, date_of_birth=dob, benefit_id=benefit_id
        )

        # Then
        assert not found

    @staticmethod
    def test_find_member_with_wallet_level_id_provided(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        last_name = "Smith"
        dob = date(year=2000, month=5, day=21)
        benefit_id = "1234567"

        # When
        member_lookup_service.find_member(
            last_name=last_name, date_of_birth=dob, benefit_id=benefit_id
        )

        # Then
        member_lookup_service.wallet_repo.search_by_wallet_benefit_id.assert_called_with(
            last_name=last_name, date_of_birth=dob, benefit_id=benefit_id
        )

    @staticmethod
    @pytest.mark.parametrize(argnames="benefit_id", argvalues=["m1234567", "M1234567"])
    def test_find_member_with_member_level_id_provided(
        member_lookup_service: MemberLookupService, benefit_id: str
    ):
        # Given
        last_name = "Smith"
        dob = date(year=2000, month=5, day=21)

        # When
        member_lookup_service.find_member(
            last_name=last_name, date_of_birth=dob, benefit_id=benefit_id
        )

        # Then
        member_lookup_service.member_benefit_repo.search_by_member_benefit_id.assert_called_with(
            last_name=last_name, date_of_birth=dob, benefit_id=benefit_id
        )

    @staticmethod
    def test_find_member_none_found(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        last_name = "Smith"
        dob = date(year=2000, month=5, day=21)
        benefit_id = "M9098938023"

        member_lookup_service.member_benefit_repo.search_by_member_benefit_id.return_value = (
            None
        )

        # When
        found = member_lookup_service.find_member(
            last_name=last_name, date_of_birth=dob, benefit_id=benefit_id
        )

        # Then
        assert not found


class TestGetProceduresByIds:
    @staticmethod
    def test_get_procedures_by_ids_empty(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        procedure_ids = []

        # When
        procedures = member_lookup_service.get_procedures_by_ids(
            procedure_ids=procedure_ids, headers={}
        )

        # Then
        assert not procedures

    @staticmethod
    def test_get_procedures_by_ids_not_empty(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        procedure_ids = ["123"]

        # When
        with mock.patch(
            "common.global_procedures.procedure.ProcedureService.get_procedures_by_ids"
        ) as mock_get_procedures:
            mock_get_procedures.return_value = [mock.MagicMock()]

            procedures = member_lookup_service.get_procedures_by_ids(
                procedure_ids=procedure_ids, headers={}
            )

        # Then
        assert procedures

    @staticmethod
    def test_get_procedures_by_ids_nothing_found(
        member_lookup_service: MemberLookupService,
    ):
        # Given
        procedure_ids = ["123"]

        # When
        with mock.patch(
            "common.global_procedures.procedure.ProcedureService.get_procedures_by_ids"
        ) as mock_get_procedures:
            mock_get_procedures.return_value = []

            # Then
            with pytest.raises(MissingProcedureData):
                member_lookup_service.get_procedures_by_ids(
                    procedure_ids=procedure_ids, headers={}
                )


class TestBuildPortalContentFromCategoryFailures:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("rule_name", "expected_messages", "expected_body_variant"),
        argvalues=[
            (
                "AMAZON_PROGENY_TOC_PERIOD",
                [
                    PortalMessage(
                        text="Please submit authorizations for this member to Progyny through 4/30/2025.",
                        level=PortalMessageLevel.ATTENTION,
                    )
                ],
                BodyVariant.PROGYNY_TOC,
            ),
        ],
    )
    def test_build_portal_content_from_category_failures(
        member_lookup_service: MemberLookupService,
        rule_name: str,
        expected_messages: list[PortalMessage],
        expected_body_variant: list[BodyVariant],
    ):
        # Given
        category_failures = [
            ReimbursementWalletCategoryRuleEvaluationFailure(
                evaluation_result_id=1, rule_name=rule_name
            )
        ]

        # When
        portal_content = (
            member_lookup_service.build_portal_content_from_category_failures(
                category_failures=category_failures
            )
        )

        # Then
        assert portal_content["messages"] == expected_messages
        assert portal_content["body_variant"] == expected_body_variant

    @staticmethod
    @pytest.mark.parametrize(
        argnames="category_failures",
        argvalues=[
            [
                ReimbursementWalletCategoryRuleEvaluationFailure(
                    evaluation_result_id=1, rule_name="THE_RULE"
                )
            ],
            [],
        ],
        ids=["unhandled-rule-failure", "no-failures"],
    )
    def test_build_portal_content_from_category_failures_no_rule_failures(
        member_lookup_service: MemberLookupService,
        category_failures: list[ReimbursementWalletCategoryRuleEvaluationFailure],
    ):
        # When - Then
        with pytest.raises(
            ClinicPortalException, match="Unhandled rule evaluation failure"
        ):
            member_lookup_service.build_portal_content_from_category_failures(
                category_failures=category_failures
            )


class TestGetPortalContent:
    @staticmethod
    def test_get_portal_content_has_dp_category(
        member_lookup_service: MemberLookupService, direct_payment_wallet
    ):
        # Given
        # When
        content = member_lookup_service.get_portal_content(
            wallet=direct_payment_wallet,
            offered_direct_payment_category=direct_payment_wallet.get_org_direct_payment_category,
        )

        # Then
        assert content is None

    @staticmethod
    def test_get_portal_content_no_dp_category(
        member_lookup_service: MemberLookupService,
        direct_payment_wallet_without_dp_category_access,
        category_service,
        session,
    ):
        # Given
        # When
        content = member_lookup_service.get_portal_content(
            wallet=direct_payment_wallet_without_dp_category_access,
            offered_direct_payment_category=direct_payment_wallet_without_dp_category_access.get_org_direct_payment_category,
        )

        # Then
        assert content


class TestResolveAllowTreatmentScheduling:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=(
            "payment_method_exists",
            "has_category_access",
            "expected_allow_treatment_scheduling",
        ),
        argvalues=[
            (True, True, True),
            (True, False, False),
            (False, True, False),
        ],
    )
    def test_resolve_allow_treatment_scheduling(
        member_lookup_service: MemberLookupService,
        direct_payment_wallet,
        payment_method_exists: bool,
        has_category_access: bool,
        expected_allow_treatment_scheduling: bool,
    ):
        # Given
        dp_category = None

        if has_category_access:
            dp_category = direct_payment_wallet.get_direct_payment_category

        # When
        allow_treatment_scheduling = (
            member_lookup_service.resolve_allow_treatment_scheduling(
                payment_method_on_file=payment_method_exists,
                direct_payment_category=dp_category,
            )
        )

        # Then
        assert allow_treatment_scheduling == expected_allow_treatment_scheduling


class TestHealthPlanCheck:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=" de_enabled, start_at_offset, end_at_offset, hdhp_exists, hdhp_reimb_start_date, exp",
        argvalues=[
            pytest.param(
                True,
                -5,
                10,
                None,
                None,
                True,
                id="1.Deductible accumulation enabled. MHP check fails - no MHP found",
            ),
            pytest.param(
                True,
                5,
                10,
                None,
                None,
                False,
                id="2.Deductible accumulation enabled. MHP check succeeds",
            ),
            pytest.param(
                False,
                -5,
                10,
                True,
                None,
                True,
                id="3.Non deductible accumulation enabled. HDHP health plan exists MHP missing",
            ),
            pytest.param(
                False,
                -5,
                10,
                False,
                datetime.today(),
                True,
                id="4.Non deductible accumulation enabled.  HDHP reimb plan, no survey taken, no MHP found.",
            ),
            pytest.param(
                False,
                -5,
                10,
                False,
                None,
                False,
                id="5.Non deductible accumulation enabled. No HDHP reimb plan, MHP not needed..",
            ),
        ],
    )
    def test_fails_member_health_plan_check(
        ff_test_data,
        member_lookup_service,
        qualified_wallet: ReimbursementWallet,
        de_enabled: bool,
        start_at_offset: int,
        end_at_offset: int,
        hdhp_exists: bool | None,
        hdhp_reimb_start_date,
        exp: bool,
    ):
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
        )
        qualified_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            de_enabled
        )
        _ = MemberHealthPlanFactory.create(
            member_id=qualified_wallet.user_id,
            reimbursement_wallet=qualified_wallet,
            plan_start_at=datetime.today() - timedelta(days=start_at_offset),
            plan_end_at=datetime.today() + timedelta(days=end_at_offset),
        )
        with mock.patch(
            "wallet.services.member_lookup.MemberLookupService._check_hdhp_exists_for_wallet_date",
            return_value=hdhp_exists,
        ), mock.patch(
            "wallet.services.member_lookup.MemberLookupService._get_active_hdhp_plan_start_date",
            return_value=hdhp_reimb_start_date,
        ):
            res = member_lookup_service.fails_member_health_plan_check(
                member_id=qualified_wallet.user_id,
                wallet=qualified_wallet,
                effective_date=datetime.today(),
            )

        assert res is exp
