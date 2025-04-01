from __future__ import annotations

import enum
import secrets
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    select,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, relationship, validates

from authn.models.user import User
from common import stats
from eligibility.service import get_verification_service
from models.base import TimeLoggedModelBase, TimeLoggedSnowflakeModelBase, db
from models.enterprise import Organization
from utils.braze_events import (
    debit_card_transaction_approved,
    debit_card_transaction_denied,
    debit_card_transaction_insufficient_docs,
    debit_card_transaction_needs_receipt,
)
from utils.log import logger
from utils.payments import convert_cents_to_dollars
from wallet.constants import APPROVED_REQUEST_STATES
from wallet.models.constants import (
    FERTILITY_EXPENSE_TYPES,
    AlegeusCoverageTier,
    CostSharingCategory,
    PlanType,
    ReimbursementAccountStatus,
    ReimbursementMethod,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    TaxationState,
    TaxationStateConfig,
    WalletState,
    WalletUserStatus,
    state_descriptions,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
    ReimbursementOrgSettingsExpenseType,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

log = logger(__name__)


class ReimbursementRequestCategoryExpenseTypes(TimeLoggedModelBase):
    __tablename__ = "reimbursement_request_category_expense_types"

    reimbursement_request_category_id = Column(
        BigInteger,
        ForeignKey("reimbursement_request_category.id"),
        nullable=False,
        primary_key=True,
    )
    reimbursement_request_category = relationship("ReimbursementRequestCategory")

    expense_type = Column(
        Enum(ReimbursementRequestExpenseTypes), nullable=False, primary_key=True
    )

    def __repr__(self) -> str:
        return f"Expense Type: {self.expense_type} for Category: {self.reimbursement_request_category}"


class ReimbursementRequestCategory(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_request_category"

    label = Column(String, nullable=False, doc="Reimbursement request category name")
    short_label = Column(
        String,
        nullable=True,
        doc="Label optionally set by Admin when Label is too long",
    )
    reimbursement_plan_id = Column(
        BigInteger,
        ForeignKey("reimbursement_plan.id"),
        doc="Reimbursement Plan to be associated with this Reimbursement Category",
    )

    reimbursement_plan = relationship(
        "ReimbursementPlan", back_populates="category", uselist=False
    )

    category_expense_types = relationship(
        "ReimbursementRequestCategoryExpenseTypes", cascade="all, delete-orphan"
    )

    reimbursement_requests = relationship(
        "ReimbursementRequest", back_populates="category"
    )

    @property
    def expense_types(self) -> list[ReimbursementRequestExpenseTypes]:
        return [
            ReimbursementRequestExpenseTypes(e.expense_type)
            for e in self.category_expense_types
        ]

    @property
    def organizations(self) -> list[Organization]:
        orgs = (
            db.session.query(Organization)
            .join(ReimbursementRequestCategory.allowed_reimbursement_organizations)
            .join(
                ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings
            )
            .join(ReimbursementOrganizationSettings.organization)
            .filter(ReimbursementRequestCategory.id == self.id)
            .all()
        )
        return orgs

    def get_category_association(
        self, reimbursement_wallet: ReimbursementWallet
    ) -> ReimbursementOrgSettingCategoryAssociation | None:
        association: ReimbursementOrgSettingCategoryAssociation | None = (
            db.session.query(ReimbursementOrgSettingCategoryAssociation)
            .filter(
                ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category_id
                == self.id,
                ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings_id
                == reimbursement_wallet.reimbursement_organization_settings_id,
            )
            .one_or_none()
        )
        return association

    def is_direct_payment_eligible(
        self, reimbursement_wallet: ReimbursementWallet
    ) -> bool:
        # Check if reimbursement_organization_settings exists if not return false
        # as check for direct_payment_enabled can't be done
        if not reimbursement_wallet.reimbursement_organization_settings:
            return False

        direct_payment_enabled = (
            reimbursement_wallet.reimbursement_organization_settings.direct_payment_enabled
        )

        if not direct_payment_enabled:
            return False

        active_wallet_users = reimbursement_wallet.all_active_users

        if all(
            user.member_profile.country_code != "US" for user in active_wallet_users
        ):
            return False

        if not self.expense_types:
            return False

        has_fertility_type = False
        non_fertility_types = []
        for e in self.expense_types:
            if e in FERTILITY_EXPENSE_TYPES:
                has_fertility_type = True
            else:
                non_fertility_types.append(e)

        # No fertility expenses in category
        if not has_fertility_type:
            return False

        # Only fertility expenses in category
        if len(non_fertility_types) == 0:
            return True

        # Both fertility and non-fertility expenses in category. The wallet's intended type must be fertility.
        if (
            len(non_fertility_types) > 0
            and reimbursement_wallet.primary_expense_type in FERTILITY_EXPENSE_TYPES
        ):
            return True

        # Try leaving this method to return false at the end in case the logic changes and something falls through.
        return False

    def has_fertility_expense_type(self) -> bool:
        """
        This is used to determine if a category includes fertility expense.
        """
        # Category must have a fertility type
        if not self.expense_types:
            return False

        overlapping_fertility_expense_types = set(self.expense_types) & set(
            FERTILITY_EXPENSE_TYPES
        )

        return bool(overlapping_fertility_expense_types)

    def __repr__(self) -> str:
        return (
            f"<ReimbursementRequestCategory {self.id} "
            f"[Label: {self.label}] "
            f"[Plan: {self.reimbursement_plan_id} {self.reimbursement_plan and self.reimbursement_plan.alegeus_plan_id}]>"
        )


class ReimbursementServiceCategory(TimeLoggedModelBase):
    __tablename__ = "reimbursement_service_category"

    id = Column(Integer, primary_key=True)

    category = Column(String(10), nullable=False)

    name = Column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"<Service Category: {self.category}>"


class WalletExpenseSubtype(TimeLoggedModelBase):
    __tablename__ = "wallet_expense_subtype"

    id = Column(Integer, primary_key=True)

    expense_type = Column(Enum(ReimbursementRequestExpenseTypes), nullable=False)

    code = Column(String(10), nullable=False)

    description = Column(String(255), nullable=False)

    visible = Column(Boolean, nullable=False, default=True)

    reimbursement_service_category_id = Column(
        Integer,
        ForeignKey("reimbursement_service_category.id"),
        nullable=False,
    )
    reimbursement_service_category = relationship("ReimbursementServiceCategory")

    global_procedure_id = Column(String(36), nullable=True)

    def __repr__(self) -> str:
        return f"<Expense Sub-Type: {self.expense_type} - {self.code}>"


class ReimbursementRequest(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_request"

    AUTO_LABEL_FLAG = "_AUTO_"

    label = Column(String, nullable=False, doc="Title of service to be reimbursed")
    service_provider = Column(String, nullable=False, doc="Service/Goods vendor")
    person_receiving_service = Column(
        String,
        nullable=True,
        doc="Account holder if null, or their partner or other qualifying party",
    )
    person_receiving_service_id = Column(
        BigInteger,
        nullable=True,
        doc="ID of the account holder or their partner or other qualifying party",
    )
    person_receiving_service_member_status = Column(
        String,
        nullable=True,
        doc="member status of the person receiving service, either MEMBER or NON_MEMBER",
    )
    description = Column(
        String,
        nullable=True,
        default="",
        doc="Description of service to be reimbursed, clinical and client notes",
    )
    amount = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Amount in the minor unit of the benefit currency",
    )
    benefit_currency_code = Column(
        String,
        nullable=True,
        default=None,
        doc="ISO 4217 currency code of the benefit currency, currency of `amount` column",
    )
    transaction_amount = Column(
        Integer,
        nullable=True,
        default=None,
        doc="Amount in the minor unit of the transaction currency",
    )
    transaction_currency_code = Column(
        String,
        nullable=True,
        default=None,
        doc="ISO 4217 currency code of the transaction currency, currency of `transaction_amount` column",
    )
    usd_amount = Column(
        Integer, nullable=True, default=None, doc="Amount to be reimbursed in USD cents"
    )
    use_custom_rate = Column(Boolean, nullable=False, default=False)
    transaction_to_benefit_rate: Decimal = Column(
        # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[Optional[Decimal]]", variable has type "Decimal")
        Numeric(precision=12, scale=6),
        nullable=True,
        default=None,
        doc="FX rate used to convert from `transaction_amount` to `amount`",
    )
    transaction_to_usd_rate: Decimal = Column(
        # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[Optional[Decimal]]", variable has type "Decimal")
        Numeric(precision=12, scale=6),
        nullable=True,
        default=None,
        doc="FX rate used to convert from `transaction_amount` to `usd_amount`",
    )
    state = Column(
        Enum(ReimbursementRequestState),
        nullable=False,
        default=ReimbursementRequestState.NEW,
        doc="State of reimbursement request in the approval process",
    )

    reimbursement_request_category_id = Column(
        BigInteger,
        ForeignKey("reimbursement_request_category.id"),
        nullable=False,
        doc="Type of service to be reimbursed such as a prescription or lab test",
    )
    category: ReimbursementRequestCategory = relationship(
        # type: ignore[assignment] # Incompatible types in assignment (expression has type "RelationshipProperty[ReimbursementRequestCategory]", variable has type "ReimbursementRequestCategory")
        "ReimbursementRequestCategory",
        back_populates="reimbursement_requests",
    )
    expense_type = Column(Enum(ReimbursementRequestExpenseTypes), nullable=True)
    original_expense_type = Column(
        Enum(ReimbursementRequestExpenseTypes), nullable=True
    )

    wallet_expense_subtype_id = Column(
        Integer,
        ForeignKey("wallet_expense_subtype.id"),
        nullable=True,
    )
    original_wallet_expense_subtype_id = Column(
        Integer,
        ForeignKey("wallet_expense_subtype.id"),
        nullable=True,
    )
    wallet_expense_subtype = relationship(
        "WalletExpenseSubtype", foreign_keys=wallet_expense_subtype_id
    )
    original_wallet_expense_subtype = relationship(
        "WalletExpenseSubtype", foreign_keys=original_wallet_expense_subtype_id
    )

    sources = relationship(
        "ReimbursementRequestSource",
        backref="reimbursement_requests",
        secondary="reimbursement_request_source_requests",
    )

    reimbursement_wallet_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet.id"),
        nullable=False,
        doc="User's reimbursement wallet settings associated with this request",
    )
    wallet: ReimbursementWallet = relationship(
        # type: ignore[assignment] # Incompatible types in assignment (expression has type "RelationshipProperty[ReimbursementWallet]", variable has type "ReimbursementWallet")
        "ReimbursementWallet",
        back_populates="reimbursement_requests",
    )

    service_start_date: datetime = Column(
        # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[datetime]", variable has type "datetime")
        DateTime,
        nullable=False,
        doc="Date when user purchased the service or item to be reimbursed",
    )
    service_end_date: datetime | None = Column(
        # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[Optional[datetime]]", variable has type "Optional[datetime]")
        DateTime,
        nullable=True,
        default=service_start_date,
        doc="Date when user purchased the service or item to be reimbursed",
    )

    reimbursement_transfer_date = Column(
        DateTime,
        nullable=True,
        doc="Date when Maven last attempted to transfer money to the user's connect account for this request."
        " Not user facing.",
    )

    reimbursement_payout_date = Column(
        DateTime,
        nullable=True,
        doc="Date when Maven last attempted to reimburse this request. Not user facing. "
        "Does not correspond to when the user receives the reimbursement.",
    )
    taxation_status = Column(
        Enum(TaxationState),
        nullable=True,
        doc="Taxable status of reimbursement request",
    )
    reimbursement_type = Column(
        Enum(ReimbursementRequestType),
        default=ReimbursementRequestType.MANUAL,
        nullable=False,
        doc="Represents whether a transaction was triggered from a manual receipt expense submission or debit card transaction",
    )
    reimbursement_method = Column(
        Enum(ReimbursementMethod),
        nullable=True,
        doc="Method in which the user will receive reimbursement",
    )
    is_prepaid = Column(Boolean, default=False, nullable=True)

    appeal_of = Column(
        BigInteger,
        ForeignKey("reimbursement_request.id"),
        nullable=True,
        doc="Reimbursement Request this request is appealing",
    )
    appealed_reimbursement_request = relationship(
        "ReimbursementRequest",
        backref=backref("appeal", uselist=False),
        remote_side="ReimbursementRequest.id",
    )

    erisa_workflow = Column(
        Boolean, default=False, nullable=False, doc="Use ERISA workflow"
    )

    cost_sharing_category = Column(
        Enum(CostSharingCategory),
        nullable=True,
        doc="Required for Cost Breakdown calculations. Optional otherwise.",
    )
    procedure_type = Column(
        Enum(
            "MEDICAL", "PHARMACY"
        ),  # TreatmentProcedureType without the circular import
        nullable=True,
        doc="Required for Cost Breakdown calculations. Optional otherwise.",
    )
    cost_credit = Column(
        Integer,
        nullable=True,
        doc="Required for cycle-based cost breakdown calculations. Optional otherwise.",
    )
    auto_processed = Column(
        Enum(ReimbursementRequestAutoProcessing),
        nullable=True,
        doc="Determines if reimbursement is auto processed.",
    )

    @validates("service_end_date")
    def validate_service_end_date(  # type: ignore[no-untyped-def]
        self, key, service_end_date
    ):
        if (
            service_end_date is not None
            and service_end_date.date() < self.service_start_date.date()
        ):
            raise ValueError(
                "Service end date needs to be the same as or later than the service start date."
            )
        return service_end_date

    @validates("reimbursement_wallet_id")
    def validate_reimbursement_wallet_id(  # type: ignore[no-untyped-def]
        self, key, wallet_id
    ):
        """Prevents adding a reimbursement request to an inactive wallet."""
        wallet = ReimbursementWallet.query.get(wallet_id)
        valid_wallet_states = {WalletState.QUALIFIED, WalletState.RUNOUT}
        if wallet and wallet.state in valid_wallet_states:
            return wallet_id
        if self.auto_processed != ReimbursementRequestAutoProcessing.RX:
            raise ValueError(
                "You can only add Reimbursement Requests to active qualified or runout Reimbursement Wallets."
            )
        if self.state != ReimbursementRequestState.DENIED:
            raise ValueError(
                "You can only create Denied Reimbursement Requests for non-active Reimbursement Wallets."
            )
        return wallet_id

    @property
    def employee_member_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Return the employee of the wallet the reimbursement request is associated with
        # Reporting is always done on the employee, regardless of the person receiving service.
        wallet = self.wallet
        if wallet.employee_member:
            return wallet.employee_member.id
        elif len(wallet.all_active_users) == 1:
            return wallet.all_active_users[0].id
        else:
            # Deprecated, but we need a fallback for now when we can't determine a wallet user.
            return wallet.user_id

    @property
    def formatted_label(self) -> str:
        """
        Return a label value where expense type and expense subtype can override the stored label
        """

        if self.label == self.AUTO_LABEL_FLAG:
            # expense_type can be the string or the enum depending on the point in the lifecycle
            expense_type = (
                self.expense_type.value
                if isinstance(self.expense_type, enum.Enum)
                else self.expense_type
            )

            type_label = (
                expense_type.capitalize().replace("_", " ")
                if expense_type
                else "Unknown"
            )
            subtype_label = (
                self.wallet_expense_subtype.description
                if self.wallet_expense_subtype
                else "Other"
            )
            return f"{type_label} - {subtype_label}"
        return self.label

    @property
    def state_description(self) -> str:
        if (
            self.reimbursement_type == ReimbursementRequestType.DEBIT_CARD
            and self.state == ReimbursementRequestState.APPROVED
        ):
            description = state_descriptions.get("DEBIT_CARD")
        else:
            description = state_descriptions.get(self.state)
        if description is None:
            log.error(
                f"Invalid Reimbursement Request state: {self.state}",
                reimbursement_request_id=self.id,
            )
            raise ValueError(
                "Requested an invalid Reimbursement Request state description."
            )
        return description

    @hybrid_property
    def wallet_user_info(self) -> str:
        """
        Returns a list of the user_ids, email_addresses, and zendesk_ticket_ids of the users using the wallet.
        This field is used in the ReimbursementRequestsView.
        """
        result = (
            db.session.query(
                ReimbursementWalletUsers.user_id,
                ReimbursementWalletUsers.zendesk_ticket_id,
                User.email,
            )
            .join(User, ReimbursementWalletUsers.user_id == User.id)
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id
                == self.reimbursement_wallet_id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
            )
            .all()
        )
        return "\n".join(
            f"[{user_id=}, {zendesk_ticket_id=}, {email=}]"
            for user_id, zendesk_ticket_id, email in result
        )

    @property
    def first_source(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.warning("Deprecated usage of ReimbursementRequest.first_source")
        return self.sources[0] if self.sources else None

    @property
    def usd_reimbursement_amount(self) -> int:
        """Get the USD amount used to send to Alegeus for reimbursement"""
        # if this category does not have a currency_code, then assume that the benefit currency is USD
        if (
            self.benefit_currency_code is None
            or self.benefit_currency_code.upper() == "USD"
        ):
            return self.amount

        return self.usd_amount  # type: ignore[return-value] # Incompatible return value type (got "Optional[int]", expected "int")

    def set_expense_type_configuration_attributes(
        self,
        allowed_category_ids: frozenset = frozenset(),
        user_id: int | None = None,
        infertility_dx: bool = False,
    ) -> None:
        """
        This function does not commit to the database.

        When creating a new Reimbursement Request, set values based on the set expense type.
        1) international expenses, ineligible debit expenses, and prepaid debit expenses are always taxable
        2) else fallback to Expense Type - Taxation status rule query.
        3) If taxation rule is split_dx_infertility, set taxation based on infertility diagnosis
        4) If expense type is adoption, check wallet taxation status before checking config
        """
        from wallet.utils.common import is_user_international

        expense_type = self.expense_type
        # When RR is not yet persisted, we may not have self.wallet so use reimbursement_wallet_id to query org settings
        # otherwise use self.wallet so the admin forms work correctly
        wallet_id = self.reimbursement_wallet_id or self.wallet.id
        wallet = ReimbursementWallet.query.get(wallet_id)
        org_settings = wallet.reimbursement_organization_settings

        # Intl and prepaid debit taxation checks, fallback to non-intl
        is_user_intl = False
        try:
            if not user_id and wallet.employee_member:
                user_id = wallet.employee_member.id
            if user_id:
                verification = get_verification_service()
                eligibility_verification = (
                    verification.get_verification_for_user_and_org(
                        user_id=user_id, organization_id=org_settings.organization_id
                    )
                )
                is_user_intl = is_user_international(
                    e9y_record=eligibility_verification, user=wallet.employee_member
                )
        except Exception as e:
            log.warning(
                "Cannot lookup user e9y for Reimbursement Request Creation Form",
                error=e,
            )

        is_debit_prepaid = (
            self.is_prepaid
            and self.reimbursement_type == ReimbursementRequestType.DEBIT_CARD
        )
        is_inelligible_debit = (
            self.reimbursement_type == ReimbursementRequestType.DEBIT_CARD
            and self.state == ReimbursementRequestState.INELIGIBLE_EXPENSE
        )
        if is_user_intl or is_debit_prepaid or is_inelligible_debit:
            self.taxation_status = TaxationState.TAXABLE  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TaxationState", variable has type "Optional[str]")
            self.reimbursement_method = ReimbursementMethod.PAYROLL
        # Otherwise check expense type to set taxation
        elif expense_type:
            taxation_status = None

            # Get expense type taxation configuration, and fallback if not found.
            expense_type_config = ReimbursementOrgSettingsExpenseType.query.filter_by(
                reimbursement_organization_settings_id=org_settings.id,
                expense_type=expense_type,
            ).one_or_none()

            if expense_type_config:
                # Get infertility diagnosis to determine taxation status for this expense type if needed
                if (
                    expense_type_config.taxation_status
                    == TaxationStateConfig.SPLIT_DX_INFERTILITY
                ):
                    if infertility_dx:
                        taxation_status = TaxationState.NON_TAXABLE
                    else:
                        taxation_status = TaxationState.TAXABLE
                else:
                    # convert TaxationStateConfig enum of expense_type_config to TaxationState enum
                    taxation_status = TaxationState(
                        expense_type_config.taxation_status.name
                    )
                # Set Reimbursment Method if available
                if expense_type_config.reimbursement_method:
                    self.reimbursement_method = expense_type_config.reimbursement_method

            # If adoption RR, if wallet taxation is Adoption non-qualified, use that expense type.
            if (
                self.wallet.taxation_status == TaxationState.ADOPTION_NON_QUALIFIED
                and expense_type == ReimbursementRequestExpenseTypes.ADOPTION
            ):
                self.taxation_status = TaxationState.ADOPTION_NON_QUALIFIED
            else:
                self.taxation_status = taxation_status  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TaxationState", variable has type "Optional[str]")

        if expense_type:
            # Get the correct reimbursement_request_category_id to set on the RR
            category_results = (
                db.session.query(ReimbursementRequestCategory)
                .join(
                    ReimbursementOrgSettingCategoryAssociation,
                    ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category_id
                    == ReimbursementRequestCategory.id,
                )
                .join(
                    ReimbursementRequestCategoryExpenseTypes,
                    ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category_id
                    == ReimbursementRequestCategoryExpenseTypes.reimbursement_request_category_id,
                )
                .filter(
                    ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings_id
                    == org_settings.id,
                    ReimbursementRequestCategoryExpenseTypes.expense_type
                    == expense_type,
                    ReimbursementRequestCategory.id.in_(allowed_category_ids),
                )
                .order_by(ReimbursementRequestCategory.id.desc())
                .all()
            )
            if not category_results:
                # If we find no results, throw an error
                log.error(
                    f"wallet {wallet.id} is missing expense type - category mappings"
                )
                stats.increment(
                    metric_name="api.wallet.reimbursement_requests.expense_types",
                    pod_name=stats.PodNames.PAYMENTS_POD,
                    tags=["error:True", "method:POST"],
                )
                raise ValueError("Missing category for expense type and organization.")
            elif len(category_results) == 1:
                # If we only have one match, use this result.
                self.category = category_results[0]
            else:
                # If we have multiple results, we want to check the reimbursement_plan of each category to see
                # which category is currently active. If we still have multiple results, default to any.
                active_categories = []
                for category in category_results:
                    plan = category.reimbursement_plan
                    if (
                        plan
                        and plan.start_date
                        and plan.end_date
                        and plan.start_date <= datetime.today().date() <= plan.end_date
                    ):
                        active_categories.append(category)

                if not active_categories:
                    # If we have no active categories, fall back to latest category result (non-active plan) and alert
                    log.error(
                        f"wallet {wallet.id} has no active expense type - category mappings for ROS {org_settings.id}"
                    )
                    stats.increment(
                        metric_name="api.wallet.reimbursement_requests.expense_types.no_active_category_expense_types",
                        pod_name=stats.PodNames.PAYMENTS_POD,
                        tags=["warning:True", "method:POST"],
                    )
                    self.category = category_results[0]
                elif len(active_categories) == 1:
                    # one active category found - set to that category
                    self.category = active_categories[0]
                else:
                    # If we have multiple active categories, default the latest category (active plan) and alert
                    log.error(
                        f"wallet {wallet.id} has multiple active expense type - category mappings for ROS {org_settings.id}"
                    )
                    stats.increment(
                        metric_name="api.wallet.reimbursement_requests.expense_types.multiple_active_category_expense_types",
                        pod_name=stats.PodNames.PAYMENTS_POD,
                        tags=["warning:True", "method:POST"],
                    )
                    self.category = active_categories[0]
        else:
            # If we don't have a valid expense type, and we also don't have a category set
            # We will not be able to persist the reimbursement request since category is not nullable.
            if not self.category:
                raise ValueError("Expense Type or Category is required.")

    def update_state(
        self, state: ReimbursementRequestState, transaction_data: Optional[dict] = None
    ) -> None:
        """
        Method for creating or updating a reimbursement_requests state attribute.

        This allows us to gather all the side effects of state changes in one place

        transaction_data: Dict representing reimbursement_transaction data.
        This is necessary because we create a reimbursement_request before reimbursement_transaction,
        and notifications require transaction data.
        """
        if self.reimbursement_type == ReimbursementRequestType.DEBIT_CARD:
            amount = None
            date = None
            if transaction_data:
                amount = convert_cents_to_dollars(transaction_data.get("amount"))
                date = transaction_data.get("date")
            if (amount is None or date is None) and self.transactions:
                transaction = self.transactions[0]
                amount = convert_cents_to_dollars(transaction.amount)
                date = transaction.date

            old_state = self.state
            if old_state != state:
                if state == ReimbursementRequestState.APPROVED:
                    debit_card_transaction_approved(self, amount, date)
                elif state == ReimbursementRequestState.NEEDS_RECEIPT:
                    debit_card_transaction_needs_receipt(self, amount, date)
                elif state == ReimbursementRequestState.INSUFFICIENT_RECEIPT:
                    debit_card_transaction_insufficient_docs(self, amount, date)
                elif state == ReimbursementRequestState.FAILED:
                    debit_card_transaction_denied(self)

        self.state = state  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ReimbursementRequestState", variable has type "str")

    def set_erisa_workflow(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Determine if the reimbursement request should be processed using the ERISA workflow.

        IMPORTANT: The ERISA workflow is a contractual determination. Do not update the logic
        or test cases without consulting Legal.

        This should be determined when the object is first created, and not updated after. The
        logic for when the ERISA workflow should be used is as follows:

        Reimbursement Organization is Direct Payment Enabled
        AND
        (
            Reimbursement Request type is Direct Payment
            OR
            Reimbursement Request category is DP eligible for this wallet
        )
        """
        if self.erisa_workflow is None:
            erisa_workflow = False

            # Because this method can be called early in the object lifecycle, related objects may not
            # be available. Load them as-needed.

            wallet = self.wallet or ReimbursementWallet.query.get(
                self.reimbursement_wallet_id
            )
            if not wallet:
                raise Exception("Unable to determine erisa_workflow without wallet.")

            if wallet.reimbursement_organization_settings.direct_payment_enabled:
                # admin and non-admin flows see different values here
                if (
                    self.reimbursement_type
                    == ReimbursementRequestType.DIRECT_BILLING.name
                    or self.reimbursement_type
                    == ReimbursementRequestType.DIRECT_BILLING
                ):
                    erisa_workflow = True
                else:
                    category = self.category or ReimbursementRequestCategory.query.get(
                        self.reimbursement_request_category_id
                    )
                    if not category:
                        raise Exception(
                            "Unable to determine erisa_workflow without category."
                        )
                    if category.is_direct_payment_eligible(wallet):
                        erisa_workflow = True

            self.erisa_workflow = erisa_workflow
        else:
            log.error(
                "Attempting to reset erisa_workflow", reimbursement_request_id=self.id
            )

    def __repr__(self) -> str:
        return (
            f"<ReimbursementRequest {self.id} [Wallet: {self.reimbursement_wallet_id}]>"
        )


def set_erisa_workflow(mapper, connect, target):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    target.set_erisa_workflow()


event.listen(ReimbursementRequest, "before_insert", set_erisa_workflow)


class ReimbursementPlanCoverageTier(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_plan_coverage_tier"

    single_amount = Column(Numeric(scale=2), nullable=False)
    family_amount = Column(Numeric(scale=2), nullable=False)

    def __repr__(self) -> str:
        return f"<ReimbursementPlanCoverageTier {self.id} Single: {self.single_amount}, Family: {self.family_amount}"


class ReimbursementPlan(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_plan"

    alegeus_plan_id = Column(
        String,
        nullable=True,
        doc="Alegeus Representation of the Reimbursement Category Label.",
    )
    is_hdhp = Column(
        Boolean, nullable=True, doc="Indicates if plan is a High Deductible Health Plan"
    )
    auto_renew = Column(Boolean, nullable=True)
    plan_type = Column(Enum(PlanType), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    reimbursement_account_type_id = Column(
        BigInteger,
        ForeignKey("reimbursement_account_type.id"),
        nullable=True,
        doc="The Reimbursement Account Type this plan is linked to.",
    )
    reimbursement_account_type = relationship("ReimbursementAccountType")

    reimbursement_plan_coverage_tier_id = Column(
        BigInteger,
        ForeignKey("reimbursement_plan_coverage_tier.id"),
        nullable=True,
        doc="The coverage tier info for this Reimbursement Plan.",
    )
    reimbursement_plan_coverage_tier = relationship(
        "ReimbursementPlanCoverageTier",
        backref="reimbursement_plans",
    )
    reimbursement_hdhp_plans = relationship(
        "ReimbursementWalletPlanHDHP", back_populates="reimbursement_plan"
    )
    reimbursement_accounts = relationship("ReimbursementAccount", back_populates="plan")
    category = relationship(
        "ReimbursementRequestCategory",
        back_populates="reimbursement_plan",
        uselist=False,
    )

    organization_id = Column(
        Integer,
        nullable=True,
        doc="The org id this plan is linked to.",
    )
    organization = relationship(
        "Organization",
        primaryjoin="foreign(ReimbursementPlan.organization_id) == Organization.id",
    )

    def __repr__(self) -> str:
        return f"<ReimbursementPlan {self.id} [{self.alegeus_plan_id}]>"

    @property
    def organizations(self) -> Organization:
        if self.organization_id and self.organization_id != 0 and self.organization:
            return self.organization
        else:
            # Maintain legacy functionality of showing the organization if the organization_id is None.
            orgs = (
                db.session.query(Organization)
                .join(Organization.reimbursement_organization_settings)
                .join(
                    ReimbursementOrganizationSettings.allowed_reimbursement_categories
                )
                .join(
                    ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category
                )
                .join(ReimbursementRequestCategory.reimbursement_plan)
                .filter(
                    ReimbursementPlan.id == self.id,
                )
                .all()
            )
            return orgs


class ReimbursementWalletPlanHDHP(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_wallet_plan_hdhp"

    reimbursement_plan_id = Column(
        BigInteger,
        ForeignKey("reimbursement_plan.id"),
        nullable=False,
        doc="The organization level plan that this HDHP plan associates with.",
    )
    reimbursement_plan = relationship(
        "ReimbursementPlan", back_populates="reimbursement_hdhp_plans"
    )

    reimbursement_wallet_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet.id"),
        nullable=False,
        doc="User's reimbursement wallet settings associated with this Reimbursement Plan.",
    )
    wallet = relationship("ReimbursementWallet", backref="reimbursement_hdhp_plans")

    alegeus_coverage_tier = Column(
        Enum(AlegeusCoverageTier),
        nullable=True,
        doc="Indicates the coverage tier for Alegeus",
    )


class ReimbursementAccountType(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_account_type"

    alegeus_account_type = Column(
        String(4),
        nullable=True,
        doc="Represents a code for the type of benefit plan such as FSA, DCA, or TRN. Collected for Alegeus.",
    )

    def __repr__(self) -> str:
        return f"<ReimbursementAccountType {self.id} [{self.alegeus_account_type}]>"


class ReimbursementAccount(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_account"

    reimbursement_wallet_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet.id"),
        nullable=False,
        doc="user's reimbursement wallet settings associated with this Reimbursement Account.",
    )
    wallet = relationship("ReimbursementWallet", backref="reimbursement_accounts")

    reimbursement_plan_id = Column(
        BigInteger,
        ForeignKey("reimbursement_plan.id"),
        nullable=False,
        doc="user's reimbursement plan settings ",
    )
    plan = relationship("ReimbursementPlan", back_populates="reimbursement_accounts")

    status = Column(
        Enum(ReimbursementAccountStatus),
        nullable=True,
        doc="Indicates whether a Reimbursement Account is Active or Inactive.",
    )
    alegeus_flex_account_key = Column(
        String, nullable=True, doc="The flex account key provided by Alegeus"
    )
    alegeus_account_type_id = Column(
        BigInteger,
        ForeignKey("reimbursement_account_type.id", ondelete="CASCADE"),
        nullable=False,
        doc="The Alegeus account type code for this Reimbursement Account.",
    )
    alegeus_account_type = relationship(
        "ReimbursementAccountType", backref="reimburement_accounts"
    )


class ReimbursementClaim(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_claim"

    reimbursement_request_id = Column(
        BigInteger, ForeignKey("reimbursement_request.id"), nullable=False
    )
    reimbursement_request = relationship("ReimbursementRequest", backref="claims")

    alegeus_claim_id = Column(
        String, nullable=True, doc="External Id for the Claim to be used by Alegeus"
    )

    alegeus_claim_key = Column(
        BigInteger,
        nullable=True,
        doc="External Id for the Claim in Alegeus used when submitting Attachments",
    )

    amount = Column(Numeric(scale=2), nullable=True)
    status = Column(
        String,
        nullable=True,
        doc="Status of the Reimbursement Claim. To be updated by Alegeus",
    )

    def create_alegeus_claim_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.alegeus_claim_id = secrets.token_hex(10)
        db.session.commit()


class ReimbursementTransaction(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_transaction"

    reimbursement_request_id = Column(
        BigInteger, ForeignKey("reimbursement_request.id"), nullable=False
    )
    reimbursement_request = relationship("ReimbursementRequest", backref="transactions")

    alegeus_transaction_key = Column(String)
    alegeus_plan_id = Column(String)

    date = Column(DateTime, nullable=True)
    amount = Column(
        Numeric(precision=8, scale=2), nullable=True, doc="Amount stored in cents."
    )
    description = Column(String, nullable=True)
    status = Column(String, nullable=True)
    service_start_date = Column(
        DateTime,
        nullable=False,
    )
    service_end_date = Column(
        DateTime,
        nullable=True,
        default=service_start_date,
    )
    settlement_date = Column(
        Date,
        nullable=True,
    )
    sequence_number = Column(Integer, nullable=True)
    notes = Column(Text)


select_request_amounts_by_category = select(
    [
        ReimbursementRequest.id,
        ReimbursementRequest.reimbursement_wallet_id,
        ReimbursementRequest.reimbursement_request_category_id,
        func.sum(ReimbursementRequest.amount).label("amount"),
    ]
).group_by(
    ReimbursementRequest.reimbursement_wallet_id,
    ReimbursementRequest.reimbursement_request_category_id,
)


class ApprovedRequestAmount(db.Model):  # type: ignore[name-defined] # Name "db.Model" is not defined
    """
    Virtual model representing the total amount with the appropriate reimbursement request states (e.g. APPROVED, NEEDS_RECEIPT, etc) for a particular
    wallet/category pair.

    This class is used to eagerly-load wallet amounts.
    """

    __table__ = select_request_amounts_by_category.where(
        ReimbursementRequest.state.in_(APPROVED_REQUEST_STATES)
    ).alias()

    category = relationship("ReimbursementRequestCategory")

    def __repr__(self) -> str:
        return f"<ApprovedRequestAmount wallet={self.reimbursement_wallet_id} category={self.reimbursement_request_category_id} amount={self.amount}>"


class ReimbursedRequestAmount(db.Model):  # type: ignore[name-defined] # Name "db.Model" is not defined
    """
    Virtual model representing the total amount reimbursed for a particular
    wallet/category pair.

    This class is used to eagerly-load wallet amounts.
    """

    __table__ = (
        select_request_amounts_by_category.where(
            ReimbursementRequest.state == ReimbursementRequestState.REIMBURSED
        )
    ).alias()

    category = relationship("ReimbursementRequestCategory")

    def __repr__(self) -> str:
        return f"<ReimbursedRequestAmount wallet={self.reimbursement_wallet_id} category={self.reimbursement_request_category_id} amount={self.amount}>"


class ReimbursementRequestExchangeRates(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_request_exchange_rates"
    constraints = (
        UniqueConstraint("source_currency", "target_currency", "trading_date"),
    )

    source_currency: str = Column(
        # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[str]", variable has type "str")
        String,
        nullable=False,
        doc="The ISO4217 code for the currency the amount originated from.",
    )
    target_currency: str = Column(
        # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[str]", variable has type "str")
        String,
        nullable=False,
        default="USD",
        doc="ISO4217 code for the currency the amount is converted into.",
    )
    trading_date: datetime.date = Column(
        # type: ignore[valid-type] # Function "datetime.datetime.date" is not valid as a type
        Date,
        nullable=False,
        doc="Date when the exchange rate is active.",
    )
    exchange_rate: Decimal = Column(
        Numeric(precision=12, scale=6), nullable=False
    )  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[Decimal]", variable has type "Decimal")

    def __repr__(self) -> str:
        return (
            "<ReimbursementRequestCurrencyConversion"
            f"source_currency={self.source_currency} target_currency={self.target_currency}"
            f"rate={self.exchange_rate} date={self.trading_date}>"
        )
