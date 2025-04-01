import datetime
from decimal import Decimal
from typing import Iterable, Optional, Tuple

import factory

from conftest import BaseMeta
from direct_payment.clinic.pytests.factories import FertilityClinicLocationFactory
from models.enterprise import UserAssetState
from pytests.factories import (
    EnterpriseUserFactory,
    OrganizationFactory,
    ResourceFactory,
    UserAssetFactory,
)
from utils.random_string import generate_random_string
from wallet.models.annual_insurance_questionnaire_response import (
    AnnualInsuranceQuestionnaireResponse,
)
from wallet.models.constants import (
    BenefitTypes,
    CoverageType,
    FamilyPlanType,
    MemberHealthPlanPatientRelationship,
    WalletReportConfigCadenceTypes,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.models import MemberWalletSummary
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent
from wallet.models.reimbursement import (
    ReimbursementAccount,
    ReimbursementAccountType,
    ReimbursementClaim,
    ReimbursementPlan,
    ReimbursementRequest,
    ReimbursementRequestCategory,
    ReimbursementRequestCategoryExpenseTypes,
    ReimbursementRequestExchangeRates,
    ReimbursementServiceCategory,
    ReimbursementTransaction,
    ReimbursementWalletPlanHDHP,
    WalletExpenseSubtype,
)
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlan,
    EmployerHealthPlanCoverage,
    FertilityClinicLocationEmployerHealthPlanTier,
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
    ReimbursementOrgSettingDxRequiredProcedures,
    ReimbursementOrgSettingExcludedProcedures,
    ReimbursementOrgSettingsAllowedCategoryRule,
    ReimbursementOrgSettingsExpenseType,
)
from wallet.models.reimbursement_request_source import (
    ReimbursementRequestSource,
    ReimbursementRequestSourceRequests,
)
from wallet.models.reimbursement_wallet import (
    CountryCurrencyCode,
    MemberHealthPlan,
    ReimbursementWallet,
    ReimbursementWalletAllowedCategorySettings,
    ReimbursementWalletCategoryRuleEvaluationFailure,
    ReimbursementWalletCategoryRuleEvaluationResult,
)
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.models.reimbursement_wallet_billing import ReimbursementWalletBillingConsent
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.models.reimbursement_wallet_credit_transaction import (
    ReimbursementCycleMemberCreditTransaction,
)
from wallet.models.reimbursement_wallet_dashboard import (
    ReimbursementWalletDashboard,
    ReimbursementWalletDashboardCard,
    ReimbursementWalletDashboardCards,
)
from wallet.models.reimbursement_wallet_debit_card import ReimbursementWalletDebitCard
from wallet.models.reimbursement_wallet_global_procedures import (
    ReimbursementWalletGlobalProcedures,
)
from wallet.models.reimbursement_wallet_report import (
    WalletClientReportConfiguration,
    WalletClientReportConfigurationFilter,
    WalletClientReportConfigurationReportColumns,
    WalletClientReportConfigurationReportTypes,
    WalletClientReports,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.models.wallet_user_consent import WalletUserConsent
from wallet.models.wallet_user_invite import WalletUserInvite
from wallet.services.wallet_client_reporting_constants import (
    WalletReportConfigFilterType,
)

SQLAlchemyModelFactory = factory.alchemy.SQLAlchemyModelFactory


class ReimbursementOrgSettingCategoryAssociationFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementOrgSettingCategoryAssociation


class ReimbursementOrganizationSettingsFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementOrganizationSettings

    survey_url = "fake-url"
    benefit_faq_resource = factory.SubFactory(
        ResourceFactory, slug=factory.Sequence(lambda n: f"benefit-faq-{n}")
    )
    benefit_overview_resource = factory.SubFactory(
        ResourceFactory, slug=factory.Sequence(lambda n: f"benefit-resource-{n}")
    )
    started_at = datetime.datetime.now() - datetime.timedelta(minutes=10)
    organization_id = int(
        generate_random_string(
            15,
            include_lower_case_char=False,
            include_upper_case_char=False,
            include_digit=True,
        )
    )

    @factory.post_generation
    def allowed_reimbursement_categories(
        self: ReimbursementOrganizationSettings,
        create,
        allowed_reimbursement_categories: Optional[
            Iterable[Tuple[str, Optional[int], Optional[str]]]
        ],
        **kwargs,
    ):
        if kwargs.get("no_categories"):
            return

        if create and allowed_reimbursement_categories:
            for (
                category_label,
                maximum,
                currency_code,
            ) in allowed_reimbursement_categories:
                category = ReimbursementRequestCategory.query.filter(
                    ReimbursementRequestCategory.label == category_label
                ).first()
                if not category:
                    category = ReimbursementRequestCategoryFactory.create(
                        label=category_label
                    )
                ReimbursementOrgSettingCategoryAssociationFactory.create(
                    reimbursement_organization_settings_id=self.id,
                    reimbursement_request_category_id=category.id,
                    reimbursement_request_category_maximum=maximum,
                    currency_code=currency_code,
                    benefit_type=BenefitTypes.CURRENCY,
                )
        else:
            category = ReimbursementRequestCategoryFactory.create(label="fertility")
            if kwargs.get("cycle_based"):
                ReimbursementOrgSettingCategoryAssociationFactory.create(
                    reimbursement_organization_settings_id=self.id,
                    reimbursement_request_category_id=category.id,
                    benefit_type=BenefitTypes.CYCLE,
                    num_cycles=5,
                )
            else:
                ReimbursementOrgSettingCategoryAssociationFactory.create(
                    reimbursement_organization_settings_id=self.id,
                    reimbursement_request_category_id=category.id,
                    reimbursement_request_category_maximum=5000,
                    benefit_type=BenefitTypes.CURRENCY,
                )


class ReimbursementRequestCategoryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementRequestCategory


class ReimbursementWalletFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWallet

    reimbursement_organization_settings = factory.SubFactory(
        ReimbursementOrganizationSettingsFactory,
        organization=factory.SelfAttribute("..member.organization"),
        allowed_reimbursement_categories=[
            ("fertility", 5000, "USD")
        ],  # [(label, amount, currency_code)]
    )
    member = factory.SubFactory(EnterpriseUserFactory)
    state = WalletState.PENDING
    initial_eligibility_member_id = None
    initial_eligibility_verification_id = None
    initial_eligibility_member_2_id = None
    initial_eligibility_member_2_version = None
    initial_eligibility_verification_2_id = None


class WalletUserInviteFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = WalletUserInvite

    date_of_birth_provided = "2020-01-01"
    claimed = False
    has_info_mismatch = False


class WalletUserConsentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = WalletUserConsent


class ReimbursementWalletBenefitFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletBenefit

    incremental_id = 404
    rand = 42
    checksum = 6
    maven_benefit_id = "424046"


class ReimbursementWalletBillingConsentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletBillingConsent

    version = 1
    ip_address = "127.0.0.1"


class ReimbursementRequestFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementRequest

    label = "reimbursement for service"
    service_provider = "Dr. Smith"
    person_receiving_service = ""
    description = "Treatment of the condition"
    service_start_date = datetime.date.today()


class ReimbursementRequestSourceFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementRequestSource

    document_mapping_uuid = factory.Faker("uuid4")


class ReimbursementRequestSourceRequestsFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementRequestSourceRequests


class ReimbursementClaimFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementClaim


class ReimbursementPlanFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementPlan


class ReimbursementWalletPlanHDHPFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletPlanHDHP


class ReimbursementAccountFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementAccount


class ReimbursementAccountTypeFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementAccountType


class ReimbursementWalletDebitCardFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletDebitCard
        exclude = ("card_number",)

    card_number = factory.Faker("credit_card_number", card_type="mastercard")
    card_proxy_number = factory.LazyAttribute(lambda obj: "1001" + obj.card_number[4:])
    card_last_4_digits = factory.LazyAttribute(lambda obj: obj.card_number[-4:])
    created_date = datetime.date.today()


class WalletUserAssetFactory(UserAssetFactory):
    state = UserAssetState.COMPLETE
    file_name = "img.png"
    content_type = "image/png"
    content_length = 1000
    appointment = None
    message = None


class ReimbursementWalletDashboardFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletDashboard


class ReimbursementWalletDashboardCardFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletDashboardCard

    require_debit_eligible = False


class ReimbursementWalletDashboardCardsFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletDashboardCards


class ReimbursementTransactionFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementTransaction

    service_start_date = datetime.date.today()
    alegeus_plan_id = "ABC123"
    alegeus_transaction_key = factory.Faker(
        "numerify", text="###########-########-########"
    )
    sequence_number = 1
    settlement_date = datetime.date.today()


class WalletClientReportConfigurationFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = WalletClientReportConfiguration

    cadence = WalletReportConfigCadenceTypes.WEEKLY
    organization = factory.SubFactory(OrganizationFactory)


class WalletClientReportsFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = WalletClientReports

    start_date = datetime.datetime.today().replace(month=1, day=1)
    end_date = datetime.datetime.today().replace(month=2, day=1)
    organization = factory.SubFactory(OrganizationFactory)
    configuration_id = factory.SubFactory(
        WalletClientReportConfigurationFactory,
        organization=factory.SelfAttribute("..organization"),
    )


class WalletClientReportConfigurationFilterFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = WalletClientReportConfigurationFilter

    filter_type = WalletReportConfigFilterType.COUNTRY
    filter_value = "US"


class WalletClientReportConfigurationReportColumnsFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = WalletClientReportConfigurationReportColumns


class WalletClientReportConfigurationReportTypesFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = WalletClientReportConfigurationReportTypes


class ReimbursementWalletGlobalProceduresFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletGlobalProcedures

    name = "Fresh IVF"
    credits = 12


class CountryCurrencyCodeFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = CountryCurrencyCode

    country_alpha_2 = "JP"
    currency_code = "JPY"
    minor_unit = 0


class ReimbursementRequestExchangeRatesFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementRequestExchangeRates

    source_currency = "USD"
    target_currency = "JPY"
    trading_date = datetime.date(2023, 1, 1)
    exchange_rate = Decimal(143.2843)


class ReimbursementServiceCategoryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementServiceCategory


class WalletExpenseSubtypeFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = WalletExpenseSubtype

    global_procedure_id = factory.Faker("uuid4")


class ReimbursementRequestCategoryExpenseTypesFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementRequestCategoryExpenseTypes


class ReimbursementCycleMemberCreditTransactionFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementCycleMemberCreditTransaction

    created_at = datetime.datetime.now()


class ReimbursementCycleCreditsFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementCycleCredits


class EmployerHealthPlanFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = EmployerHealthPlan

    reimbursement_organization_settings = factory.SubFactory(
        ReimbursementOrganizationSettingsFactory
    )
    reimbursement_org_settings_id = factory.SelfAttribute(
        "reimbursement_organization_settings.id"
    )
    ind_deductible_limit = 200_000
    ind_oop_max_limit = 400_000
    fam_deductible_limit = 400_000
    fam_oop_max_limit = 600_000
    rx_integrated = True
    is_oop_embedded = False
    is_deductible_embedded = False
    start_date = datetime.date(2010, 1, 1)
    end_date = datetime.date(2050, 1, 1)
    benefits_payer_id = 1
    group_id = "GROUPID"
    carrier_number = "123456"


class EmployerHealthPlanCoverageFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = EmployerHealthPlanCoverage

    employer_health_plan = factory.SubFactory(EmployerHealthPlanFactory)
    employer_health_plan_id = factory.SelfAttribute("employer_health_plan.id")
    individual_deductible = 100_000
    individual_oop = 200_000
    family_deductible = 300_000
    family_oop = 500_000
    is_oop_embedded = False
    is_deductible_embedded = False
    plan_type = FamilyPlanType.INDIVIDUAL
    coverage_type = CoverageType.MEDICAL


class FertilityClinicLocationEmployerHealthPlanTierFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = FertilityClinicLocationEmployerHealthPlanTier

    employer_health_plan = factory.SubFactory(EmployerHealthPlanFactory)
    employer_health_plan_id = factory.SelfAttribute("employer_health_plan.id")
    fertility_clinic_location = factory.SubFactory(FertilityClinicLocationFactory)
    start_date = datetime.datetime.strptime("2024-01-15", "%Y-%m-%d").date()
    end_date = datetime.datetime.strptime("2024-12-15", "%Y-%m-%d").date()


class MemberHealthPlanFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MemberHealthPlan

    subscriber_insurance_id = "abcdefg"
    subscriber_first_name = "alice"
    subscriber_last_name = "paul"
    subscriber_date_of_birth = datetime.date(2000, 1, 1)
    employer_health_plan = factory.SubFactory(EmployerHealthPlanFactory)
    patient_first_name = "lucia"
    patient_last_name = "paul"
    patient_date_of_birth = datetime.date(2000, 1, 1)
    patient_relationship = MemberHealthPlanPatientRelationship.SPOUSE
    reimbursement_wallet = factory.SubFactory(ReimbursementWalletFactory)
    plan_type = FamilyPlanType.INDIVIDUAL
    member_id = factory.SelfAttribute("reimbursement_wallet.user_id")
    plan_start_at = datetime.datetime(year=2025, month=1, day=1)


class ReimbursementWalletUsersFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletUsers

    type = WalletUserType.EMPLOYEE
    status = WalletUserStatus.ACTIVE
    alegeus_dependent_id = "TEST_ALEGEUS_ID"


class ReimbursementWalletNonMemberDependentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = OrganizationEmployeeDependent


class ReimbursementOrgSettingExcludedProceduresFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementOrgSettingExcludedProcedures


class ReimbursementOrgSettingDxRequiredProceduresFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementOrgSettingDxRequiredProcedures


class AnnualInsuranceQuestionnaireResponseFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AnnualInsuranceQuestionnaireResponse

    wallet_id = 100
    questionnaire_id = "long_2024"
    user_response_json = '{"key": "value"}'
    submitting_user_id = 1000
    sync_status = None
    sync_attempt_at = None
    survey_year = 2024


class ReimbursementWalletAllowedCategorySettingsFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletAllowedCategorySettings

    updated_by = factory.Faker("name")


class ReimbursementOrgSettingsAllowedCategoryRuleFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementOrgSettingsAllowedCategoryRule

    started_at = datetime.datetime.today()
    rule_name = factory.Sequence(lambda n: f"Rule {n}")


class MemberWalletSummaryFactory(factory.Factory):
    class Meta:
        model = MemberWalletSummary

    wallet_id = 1
    wallet_state = WalletState.QUALIFIED
    wallet_user_status = WalletUserStatus.ACTIVE
    is_shareable = True
    channel_id = 1
    org_settings_id = 1
    org_id = 1
    direct_payment_enabled = False
    org_survey_url = "fake-url"
    overview_resource_title = "Your Benefit Overview"
    overview_resource_id = 1
    faq_resource_title = "Your Benefit FAQ"
    faq_resource_content_type = ""
    faq_resource_slug = ""
    member_id_hash = ""


class ReimbursementWalletCategoryRuleEvaluationResultFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletCategoryRuleEvaluationResult

    failed_category_rule = factory.Sequence(lambda n: f"Rule {n}")
    executed_category_rule = factory.Sequence(lambda n: f"Rule {n}")


class ReimbursementWalletCategoryRuleEvaluationFailureFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletCategoryRuleEvaluationFailure

    rule_name = factory.Faker("text", max_nb_chars=10)


class ReimbursementOrgSettingsExpenseTypeFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementOrgSettingsExpenseType

    expense_type = 1
    taxation_status = 1
