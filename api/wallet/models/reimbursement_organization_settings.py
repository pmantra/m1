import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref, relationship

from models.base import (
    TimeLoggedExternalUuidModelBase,
    TimeLoggedModelBase,
    TimeLoggedSnowflakeModelBase,
)
from models.marketing import Resource
from models.programs import Module
from payer_accumulator.models.payer_list import Payer
from utils.log import logger
from wallet.constants import UNLIMITED_FUNDING_USD_CENTS, USD_DOLLARS_PER_CYCLE
from wallet.models.constants import (
    AllowedMembers,
    BenefitTypes,
    CostSharingCategory,
    CostSharingType,
    CoverageType,
    EligibilityLossRule,
    FamilyPlanType,
    FertilityProgramTypes,
    ReimbursementMethod,
    ReimbursementRequestExpenseTypes,
    TaxationState,
    TaxationStateConfig,
)

log = logger(__name__)


class ReimbursementOrganizationSettings(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_organization_settings"

    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    organization = relationship(
        "Organization", backref="reimbursement_organization_settings"
    )

    benefit_overview_resource_id = Column(
        Integer,
        ForeignKey("resource.id"),
        nullable=True,
        doc="Resource with a description of this organization's Maven Wallet Program",
    )
    benefit_overview_resource = relationship(
        Resource, foreign_keys=[benefit_overview_resource_id]
    )
    benefit_faq_resource_id = Column(
        Integer,
        ForeignKey("resource.id"),
        nullable=False,
        doc="Resource with frequently asked questions for the organization's Maven Wallet Program.",
    )
    benefit_faq_resource = relationship(
        Resource, foreign_keys=[benefit_faq_resource_id]
    )
    survey_url = Column(
        String,
        nullable=False,
        doc="Surveymonkey survey to check the user's wallet eligibility",
    )
    required_module_id = Column(
        Integer,
        ForeignKey("module.id"),
        nullable=True,
        doc="Required module for wallet, if any. Being deprecated for required_track.",
    )
    required_module = relationship(Module, foreign_keys=required_module_id)

    required_track = Column(
        String,
        nullable=True,
        doc="Required track for wallet, if any. Example: fertility.",
    )

    reimbursement_wallets = relationship(
        "ReimbursementWallet", back_populates="reimbursement_organization_settings"
    )

    started_at = Column(DateTime, default=datetime.datetime.utcnow())
    ended_at = Column(DateTime, default=None)
    taxation_status = Column(
        Enum(TaxationState), nullable=True, doc="Taxable status of org setting"
    )
    debit_card_enabled = Column(
        Boolean, default=False, nullable=False, doc="Is debit card enabled?"
    )
    direct_payment_enabled = Column(
        Boolean, default=False, nullable=False, doc="Is direct payment enabled?"
    )
    rx_direct_payment_enabled = Column(
        Boolean, default=False, nullable=False, doc="Is RX direct payment enabled?"
    )
    deductible_accumulation_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Is deductible accumulation enabled?",
    )
    closed_network = Column(
        Boolean, default=False, nullable=False, doc="Is closed network?"
    )
    fertility_program_type = Column(
        Enum(FertilityProgramTypes),
        default=FertilityProgramTypes.CARVE_OUT,
        nullable=False,
        doc="Represents whether a fertility_program is carve out or wrap around",
    )
    fertility_requires_diagnosis = Column(
        Boolean, default=False, nullable=False, doc="Does fertility require diagnosis?"
    )
    fertility_allows_taxable = Column(
        Boolean, default=False, nullable=False, doc="Does fertility allow taxable?"
    )

    payments_customer_id = Column(CHAR(36), nullable=True)

    allowed_members = Column(
        Enum(AllowedMembers),
        nullable=False,
        default=AllowedMembers.SINGLE_ANY_USER,
    )

    excluded_procedures = relationship("ReimbursementOrgSettingExcludedProcedures")
    dx_required_procedures = relationship("ReimbursementOrgSettingDxRequiredProcedures")
    expense_types = relationship(
        "ReimbursementOrgSettingsExpenseType",
        back_populates="reimbursment_organization_settings",
    )

    name = Column(String(50), nullable=True)

    run_out_days = Column(
        Integer,
        nullable=True,
        doc="Number of days after a wallet's end date where claims can still be submitted, "
        "not to be confused with number of days a claim can be backdated before a wallet's start date.",
    )
    eligibility_loss_rule = Column(
        Enum(EligibilityLossRule),
        nullable=True,
        default=EligibilityLossRule.TERMINATION_DATE,
        doc="Conditions by which a wallet's end date are set.",
    )
    required_tenure_days = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of days a user must be hired before they can be eligible for a wallet.",
    )

    first_dollar_coverage = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Is a first dollar coverage ros? Not mutually exclusive with deductible accumulation.",  # only 1 client
    )

    @property
    def is_active(self) -> bool:
        now = datetime.datetime.now()
        if self.ended_at is None:
            return now > self.started_at
        return self.started_at < now < self.ended_at

    def __repr__(self) -> str:
        value = f"<ReimbursementOrganizationSettings {self.id}"
        if self.name is not None:
            value += f" [{self.name}]"
        if self.organization is not None:
            value += f" [Organization: {self.organization.name}]"
        value += ">"
        return value


class ReimbursementOrgSettingCategoryAssociation(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_organization_settings_allowed_category"

    reimbursement_organization_settings_id = Column(
        BigInteger,
        ForeignKey("reimbursement_organization_settings.id"),
        doc="Set of organization wallets associated with this category",
    )
    reimbursement_request_category_id = Column(
        BigInteger,
        ForeignKey("reimbursement_request_category.id"),
        doc="Category to be associated with this set of organization wallets",
    )
    reimbursement_request_category_maximum = Column(
        Integer,
        nullable=True,
        doc="The max amount of funds that can be reimbursed for services in this category.",
    )
    currency_code = Column(
        String,
        nullable=True,
        default=None,
        doc="The benefit currency that the associated category is tracked with.",
    )
    benefit_type = Column(
        Enum(BenefitTypes),
        nullable=False,
        default=BenefitTypes.CURRENCY,
    )
    is_unlimited = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="True if a CURRENCY benefit does not have a limit",
    )
    num_cycles = Column(
        Integer,
        nullable=True,
        doc="Number of cycles covered by employer for each plan period.",
    )
    reimbursement_organization_settings = relationship(
        "ReimbursementOrganizationSettings",
        backref=backref("allowed_reimbursement_categories"),
    )
    reimbursement_request_category = relationship(
        "ReimbursementRequestCategory", backref="allowed_reimbursement_organizations"
    )
    allowed_category_rules = relationship(
        "ReimbursementOrgSettingsAllowedCategoryRule",
        back_populates="reimbursement_organization_settings_allowed_category",
    )
    label = association_proxy("reimbursement_request_category", "label")

    UniqueConstraint(
        "reimbursement_organization_settings_id", "reimbursement_request_category_id"
    )

    @property
    def usd_funding_amount(self) -> int:
        """
        USD amount (cents) the category will be funded for

        The defined maximum for currency categories and a per-cycle amount for cycles.
        """
        if self.benefit_type == BenefitTypes.CURRENCY:
            if self.is_unlimited:
                return UNLIMITED_FUNDING_USD_CENTS
            else:
                from wallet.services.currency import (
                    DEFAULT_CURRENCY_CODE,
                    CurrencyService,
                )

                currency_service = CurrencyService()
                currency_amount = self.reimbursement_request_category_maximum or 0
                usd_amount, _ = currency_service.convert(
                    amount=currency_amount,
                    source_currency_code=self.currency_code or DEFAULT_CURRENCY_CODE,
                    target_currency_code=DEFAULT_CURRENCY_CODE,
                )
                return usd_amount
        if self.benefit_type == BenefitTypes.CYCLE:
            if self.is_unlimited is True:
                log.error(
                    "Unlimited benefits configured for cycle-based benefits detected",
                    ros_id=str(self.reimbursement_organization_settings_id),
                    category_association_id=str(self.id),
                    category_id=str(self.reimbursement_request_category_id),
                )
                raise WalletOrganizationConfigurationError(
                    "Unlimited benefits can only be configured for CURRENCY benefits"
                )

            return USD_DOLLARS_PER_CYCLE * 100 * (self.num_cycles or 0)

        return 0

    def __repr__(self) -> str:
        return (
            f"<ReimbursementOrgSettingCategoryAssociation {self.id} "
            f"[Category: {self.label}] "
            f"[Plan: {self.reimbursement_request_category.reimbursement_plan_id}]>"
        )


class ReimbursementOrgSettingExcludedProcedures(TimeLoggedModelBase):
    __tablename__ = "reimbursement_organization_settings_excluded_procedures"
    constraints = (
        UniqueConstraint(
            "reimbursement_organization_settings_id", "global_procedure_id"
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    reimbursement_organization_settings_id = Column(
        BigInteger,
        ForeignKey("reimbursement_organization_settings.id"),
        nullable=False,
    )
    reimbursement_organization_settings = relationship(
        "ReimbursementOrganizationSettings"
    )

    global_procedure_id = Column(String, nullable=False)

    def __repr__(self) -> str:
        return f"Organization Setting: {self.reimbursement_organization_settings} Excluded Procedure: {self.global_procedure_id} "


class ReimbursementOrgSettingDxRequiredProcedures(TimeLoggedModelBase):
    __tablename__ = "reimbursement_organization_settings_dx_required_procedures"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    reimbursement_org_settings_id = Column(
        BigInteger,
        ForeignKey("reimbursement_organization_settings.id"),
        nullable=False,
    )
    global_procedure_id = Column(String, nullable=False)

    reimbursement_organization_settings = relationship(
        "ReimbursementOrganizationSettings"
    )

    def __repr__(self) -> str:
        return f"Organization Setting: {self.reimbursement_organization_settings} Dx Required Procedure: {self.global_procedure_id} "


class EmployerHealthPlan(TimeLoggedSnowflakeModelBase):
    __tablename__ = "employer_health_plan"

    name = Column(String, nullable=True)
    reimbursement_org_settings_id = Column(
        BigInteger,
        ForeignKey("reimbursement_organization_settings.id"),
        nullable=False,
        doc="ID of organization settings for wallets associated with an Employer health plan",
    )
    reimbursement_organization_settings = relationship(
        "ReimbursementOrganizationSettings", backref="employer_health_plan"
    )
    start_date = Column(
        Date,
        nullable=False,
        doc="The date when the employer's health plan is in effect",
    )
    end_date = Column(
        Date,
        nullable=False,
        doc="The date when the employer's health plan will be terminated",
    )
    ind_deductible_limit = Column(
        Integer, nullable=True, doc="Individual deductible amount in cents"
    )
    ind_oop_max_limit = Column(
        Integer, nullable=True, doc="Individual out-of-pocket maximum in cents"
    )
    fam_deductible_limit = Column(
        Integer, nullable=True, doc="Family deductible amount in cents"
    )
    fam_oop_max_limit = Column(
        Integer, nullable=True, doc="Family out-of-pocket maximum in cents"
    )
    max_oop_per_covered_individual = Column(
        Integer,
        nullable=True,
        doc="An individual can't spend beyond this limit even if their family OOP is not met",
    )
    rx_integrated = Column(Boolean, nullable=False, default=True)
    rx_ind_deductible_limit = Column(
        Integer, nullable=True, doc="Pharmacy individual deductible amount in cents"
    )
    rx_ind_oop_max_limit = Column(
        Integer, nullable=True, doc="Pharmacy individual out-of-pocket maximum in cents"
    )
    rx_fam_deductible_limit = Column(
        Integer, nullable=True, doc="Pharmacy family deductible amount in cents"
    )
    rx_fam_oop_max_limit = Column(
        Integer, nullable=True, doc="Pharmacy family out-of-pocket maximum in cents"
    )
    is_deductible_embedded = Column(
        Boolean, nullable=False, doc="Plan has deductible embedded for cost share"
    )
    is_oop_embedded = Column(
        Boolean, nullable=False, doc="Plan has OOP embedded for cost share"
    )
    is_hdhp = Column(Boolean, nullable=False, default=False)
    is_payer_not_integrated = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="This determines whether to run RTE check and send claim to payer or not",
    )
    hra_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="This determines whether to apply hra balance to member responsibility",
    )
    group_id = Column(String, nullable=True, doc="Health plan group identifier")
    carrier_number = Column(
        String, nullable=True, doc="Medical group policy number for an employer"
    )
    benefits_payer_id = Column(
        Integer, nullable=True, doc="Reference to benefits payer id from payer_list"
    )
    benefits_payer = relationship(
        Payer,
        primaryjoin="EmployerHealthPlan.benefits_payer_id == Payer.id",
        foreign_keys="Payer.id",
        uselist=False,
    )
    cost_sharings = relationship(
        "EmployerHealthPlanCostSharing",
        backref="employer_health_plan",
        cascade="all,delete",
    )
    member_health_plan = relationship(
        "MemberHealthPlan", backref="employer_health_plan", cascade="all,delete"
    )
    tiers = relationship(
        "FertilityClinicLocationEmployerHealthPlanTier",
        back_populates="employer_health_plan",
        cascade="all,delete",
    )
    coverage = relationship(
        "EmployerHealthPlanCoverage",
        back_populates="employer_health_plan",
        cascade="all,delete",
    )

    def __repr__(self) -> str:
        return f"<[name:{self.name}] [id:{self.id}]>"


class EmployerHealthPlanCoverage(TimeLoggedSnowflakeModelBase):
    __tablename__ = "employer_health_plan_coverage"
    employer_health_plan_id = Column(
        BigInteger,
        ForeignKey("employer_health_plan.id"),
        nullable=False,
        doc="ID of Employer health plan",
    )
    individual_deductible = Column(
        Integer, nullable=True, doc="Individual deductible amount in cents"
    )
    individual_oop = Column(
        Integer, nullable=True, doc="Individual out-of-pocket maximum in cents"
    )
    family_deductible = Column(
        Integer, nullable=True, doc="Family deductible amount in cents"
    )
    family_oop = Column(
        Integer, nullable=True, doc="Family out-of-pocket maximum in cents"
    )
    max_oop_per_covered_individual = Column(
        Integer,
        nullable=True,
        doc="An individual can't spend beyond this limit even if their family OOP is not met",
    )
    is_deductible_embedded = Column(
        Boolean, nullable=False, doc="Coverage has deductible embedded for cost share"
    )
    is_oop_embedded = Column(
        Boolean, nullable=False, doc="Coverage has OOP embedded for cost share"
    )
    plan_type = Column(
        Enum(FamilyPlanType),
        nullable=False,
        doc="Plan type, i.e. FAMILY, INDIVIDUAL, INDIVIDUAL_PLUS_ONE, etc.",
    )
    coverage_type = Column(
        Enum(CoverageType), nullable=False, doc="Type of cost, i.e. MEDICAL or RX"
    )
    tier = Column(
        SmallInteger,
        nullable=True,
        doc="Tier of the cost share. Default is null, for tiered plans can be 1, 2, etc.",
    )
    employer_health_plan = relationship("EmployerHealthPlan", back_populates="coverage")

    def __repr__(self) -> str:
        return f"<[id:{self.id}] [coverage:{self.coverage_type}] [type:{self.plan_type}] [tier:{self.tier}] [individual deductible:{Decimal(self.individual_deductible) / 100 if self.individual_deductible else None}] [individual oop:{Decimal(self.individual_oop) / 100 if self.individual_oop else None}] [family deductible:{Decimal(self.family_deductible) / 100 if self.family_deductible else None}] [family oop:{Decimal(self.family_oop) / 100 if self.family_oop else None}] [is deductible embedded:{self.is_deductible_embedded}] [is oop embedded:{self.is_oop_embedded}]>"


class EmployerHealthPlanCostSharing(TimeLoggedSnowflakeModelBase):
    __tablename__ = "employer_health_plan_cost_sharing"
    employer_health_plan_id = Column(
        BigInteger,
        ForeignKey("employer_health_plan.id"),
        nullable=False,
    )
    cost_sharing_type = Column(Enum(CostSharingType), nullable=False)
    cost_sharing_category = Column(Enum(CostSharingCategory), nullable=False)
    absolute_amount = Column(
        Integer,
        nullable=True,
        doc="The amount in cents for the cost sharing type. Typically used for co-pays. Optional",
    )
    second_tier_absolute_amount = Column(
        Integer,
        nullable=True,
        doc="The amount in cents for the second tier cost sharing type. Typically used for co-pays. Optional",
    )
    percent = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        doc="The percentage amount for the cost sharing type. Typically used for coinsurance. Optional",
    )
    second_tier_percent = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        doc="The percentage amount for the second tier cost sharing type. Typically used for coinsurance. Optional",
    )

    def __repr__(self) -> str:
        return (
            f"<id:{self.id} cost_sharing_type:{self.cost_sharing_type} "
            f"cost_sharing_category:{self.cost_sharing_category} "
            f"absolute_amount:{self.absolute_amount} percent:{self.percent}>"
        )


class ReimbursementOrgSettingsAllowedCategoryRule(TimeLoggedExternalUuidModelBase):
    __tablename__ = "reimbursement_organization_settings_allowed_category_rule"

    started_at = Column(
        Date,
        doc="The time from which this association is effective. Can be in the past, in the future or null. A null "
        "value or a future date implies this association is disabled",
    )
    reimbursement_organization_settings_allowed_category_id = Column(
        BigInteger,
        ForeignKey("reimbursement_organization_settings_allowed_category.id"),
        nullable=False,
    )
    rule_name = Column(String, nullable=False)
    reimbursement_organization_settings_allowed_category = relationship(
        "ReimbursementOrgSettingCategoryAssociation",
        back_populates="allowed_category_rules",
    )

    def __repr__(self) -> str:
        return f"<Org Settings Allowed Category Rule: {self.id}>"


class ReimbursementOrgSettingsExpenseType(TimeLoggedModelBase):
    __tablename__ = "reimbursement_organization_settings_expense_types"
    id = Column(Integer, primary_key=True)
    reimbursement_organization_settings_id = Column(
        BigInteger,
        ForeignKey("reimbursement_organization_settings.id"),
        nullable=False,
    )
    reimbursment_organization_settings = relationship(
        "ReimbursementOrganizationSettings", back_populates="expense_types"
    )
    expense_type = Column(Enum(ReimbursementRequestExpenseTypes), nullable=False)
    taxation_status = Column(
        Enum(TaxationStateConfig), nullable=False, default=TaxationStateConfig.TAXABLE
    )
    reimbursement_method = Column(Enum(ReimbursementMethod), nullable=True)


class FertilityClinicLocationEmployerHealthPlanTier(TimeLoggedModelBase):
    __tablename__ = "fertility_clinic_location_employer_health_plan_tier"

    id = Column(BigInteger, autoincrement=True, primary_key=True)

    fertility_clinic_location_id = Column(
        BigInteger,
        ForeignKey("fertility_clinic_location.id"),
        nullable=False,
        doc="Id of the fertility_clinic_location that is being configured as first tier",
    )
    employer_health_plan_id = Column(
        BigInteger,
        ForeignKey("employer_health_plan.id"),
        nullable=False,
        doc="Id of employer_health_plan under which the clinic location is being configured as first tier.",
    )
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    employer_health_plan = relationship(
        "EmployerHealthPlan",
        back_populates="tiers",
    )
    fertility_clinic_location = relationship("FertilityClinicLocation")

    def __repr__(self) -> str:
        return (
            f"<id:{self.id} fertility_clinic_location_id:{self.fertility_clinic_location_id} "
            f"employer_health_plan_id:{self.employer_health_plan_id} "
            f"start_date:{self.start_date} end_date:{self.end_date}>"
        )


class WalletOrganizationConfigurationError(Exception):
    pass
