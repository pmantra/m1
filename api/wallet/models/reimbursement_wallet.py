from __future__ import annotations

import datetime
import secrets
from traceback import format_exc
from typing import TYPE_CHECKING, Any, Optional, Tuple

import ddtrace
import sqlalchemy.orm
from maven import observability
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
    String,
    Text,
    event,
    func,
)
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import and_, or_

from authn.models.user import User
from eligibility import get_verification_service
from messaging.models.messaging import Message
from models.base import (
    ModelBase,
    TimeLoggedExternalUuidModelBase,
    TimeLoggedSnowflakeModelBase,
    db,
)
from utils.log import logger
from utils.primitive_threaded_cached_property import primitive_threaded_cached_property
from wallet.constants import NUM_CREDITS_PER_CYCLE
from wallet.models.constants import (
    FAMILY_PLANS,
    AllowedMembers,
    BenefitTypes,
    CardStatus,
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    DebitBannerStatus,
    FamilyPlanType,
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
    MemberType,
    ReimbursementMethod,
    ReimbursementRequestExpenseTypes,
    TaxationState,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlan,
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_request_source import ReimbursementRequestSource
from wallet.models.reimbursement_wallet_debit_card import ReimbursementWalletDebitCard
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.utils.debit_card import user_is_debit_card_eligible

log = logger(__name__)

if TYPE_CHECKING:
    from wallet.models.reimbursement import ReimbursementRequestCategory


class ReimbursementWallet(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_wallet"

    user_id = Column(
        Integer,
        ForeignKey("user.id"),
        nullable=True,
        default=None,
        doc="ReimbursementWallet.user_id has been deprecated. "
        "Please do not use it. Use the ReimbursementWalletUsers table instead.",
    )
    """
    Deprecated. Please use the ReimbursementWalletUsers table for future development.
    """

    member = relationship(
        "User",
        backref="reimbursement_wallets",
        doc="ReimbursementWallet.MEMBER has been deprecated. "
        "Please do not use it. Use the ReimbursementWalletUsers table instead.",
    )
    """
    Deprecated. Please use the ReimbursementWalletUsers table instead.
    """

    reimbursement_organization_settings_id = Column(
        BigInteger,
        ForeignKey("reimbursement_organization_settings.id"),
        nullable=False,
        doc="Organization reimbursement settings associated with this wallet, joins to categories",
    )

    reimbursement_organization_settings: ReimbursementOrganizationSettings = relationship(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "RelationshipProperty[ReimbursementOrganizationSettings]", variable has type "ReimbursementOrganizationSettings")
        "ReimbursementOrganizationSettings", back_populates="reimbursement_wallets"
    )

    reimbursement_requests = relationship(
        "ReimbursementRequest", back_populates="wallet"
    )

    state: WalletState = Column(
        Enum(WalletState),
        nullable=False,
        default=WalletState.PENDING,
        doc="Eligibility state of this user's Wallet",
    )

    taxation_status = Column(
        Enum(TaxationState), nullable=True, doc="Taxable status of this user's Wallet"
    )

    note = Column(
        String,
        default="",
        doc="Not client facing. Record of reasons a wallet was disqualified.",
    )

    approved_amounts = relationship(
        "ApprovedRequestAmount",
        primaryjoin="ReimbursementWallet.id"
        "== foreign(ApprovedRequestAmount.reimbursement_wallet_id)",
    )

    reimbursed_amounts = relationship(
        "ReimbursedRequestAmount",
        primaryjoin="ReimbursementWallet.id"
        "== foreign(ReimbursedRequestAmount.reimbursement_wallet_id)",
    )

    reimbursement_method = Column(
        Enum(ReimbursementMethod),
        nullable=False,
        default=ReimbursementMethod.DIRECT_DEPOSIT,
        doc="Method in which the user will receive reimbursement",
    )

    reimbursement_wallet_debit_card_id = Column(
        Integer,
        ForeignKey("reimbursement_wallet_debit_card.id"),
        nullable=True,
        doc="Current debit card, if any.",
    )
    debit_card = relationship(
        ReimbursementWalletDebitCard, foreign_keys=reimbursement_wallet_debit_card_id
    )

    primary_expense_type = Column(Enum(ReimbursementRequestExpenseTypes), nullable=True)

    payments_customer_id = Column(CHAR(36), nullable=True, unique=True)

    alegeus_id = Column(String(30))

    initial_eligibility_member_id = Column(
        Integer,
        nullable=True,
        doc="Initial eligibility member id",
    )

    initial_eligibility_verification_id = Column(
        Integer,
        nullable=True,
        doc="Initial verification member id",
    )

    initial_eligibility_member_2_id = Column(
        Integer,
        nullable=True,
        doc="Initial eligibility member 2.0 id",
    )

    initial_eligibility_member_2_version = Column(
        Integer,
        nullable=True,
        doc="Initial eligibility member 2.0 version",
    )

    initial_eligibility_verification_2_id = Column(
        Integer,
        nullable=True,
        doc="Initial verification 2.0 id",
    )

    authorized_users = relationship(
        OrganizationEmployeeDependent, back_populates="reimbursement_wallet"
    )

    reimbursement_wallet_users = relationship(ReimbursementWalletUsers, uselist=True)

    @property
    def is_enrolled(self) -> bool:
        return self.state in (
            WalletState.PENDING,
            WalletState.QUALIFIED,
            WalletState.RUNOUT,
        )
        # When a member loses eligibility, they enter a run-out period.
        # During that time, the member can still submit receipts for reimbursement if incurred before they lost eligibility.

    @hybrid_property
    def user_info(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        result = (
            db.session.query(
                ReimbursementWalletUsers.user_id,
                ReimbursementWalletUsers.zendesk_ticket_id,
                User.email,
                User.esp_id,
                ReimbursementWalletUsers.status,
            )
            .join(User, User.id == ReimbursementWalletUsers.user_id)
            .filter(ReimbursementWalletUsers.reimbursement_wallet_id == self.id)
            .all()
        )
        # Any changes to this string must be accompanied by
        # changes to the ReimbursementWalletView regex.
        return "\n".join(
            f"[{user_id=}, {email=}, {zendesk_ticket_id=}, member_hash_id={esp_id}, wallet_user_status={status.value}]"
            for user_id, zendesk_ticket_id, email, esp_id, status in result
        )

    @property
    def is_disqualified(self) -> bool:
        return self.state == WalletState.DISQUALIFIED

    def _create_alegeus_id(self) -> str:
        return secrets.token_hex(15)

    @property
    def debit_card_eligible(self) -> bool:
        return self.state != WalletState.RUNOUT and user_is_debit_card_eligible(
            self.member, self.reimbursement_organization_settings
        )

    @primitive_threaded_cached_property
    def approved_amount_by_category_alltime(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Get the amount, in cents, approved for reimbursement in each category.
        Returns a dictionary with category IDs as keys:
            {
                1: 1000,
                2: 500,
                3: 0
            }
        """
        return {
            amount.reimbursement_request_category_id: int(amount.amount)
            for amount in self.approved_amounts
        }

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Retrieves a single user by user ID.
        :param user_id: ID of the user to retrieve.
        """
        return (
            db.session.query(User)
            .join(
                ReimbursementWalletUsers,
                User.id == ReimbursementWalletUsers.user_id,
            )
            .filter(
                User.id == user_id,
                ReimbursementWalletUsers.reimbursement_wallet_id == self.id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
            )
            .one_or_none()
        )

    # instance level cache of all_active_users
    _cached_all_active_users: list[User] | None = None

    @property
    def all_active_users(self) -> list[User]:
        if self._cached_all_active_users:
            return self._cached_all_active_users

        # TODO: PAY-3437: Change to User ID and User ESP_ID
        user_list: list[User] = (
            db.session.query(User)
            .join(ReimbursementWalletUsers, User.id == ReimbursementWalletUsers.user_id)
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == self.id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
            )
            .order_by(ReimbursementWalletUsers.id)
            .all()
        )
        self._cached_all_active_users = user_list
        return self._cached_all_active_users

    # instance level cache of employee_member
    _cached_employee_member: User | None = None

    @property
    def employee_member(self) -> User | None:
        if self._cached_employee_member:
            return self._cached_employee_member

        # TODO: PAY-3437: Change to User ID
        users = (
            db.session.query(User)
            .join(
                ReimbursementWalletUsers,
                User.id == ReimbursementWalletUsers.user_id,
            )
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == self.id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
                ReimbursementWalletUsers.type == WalletUserType.EMPLOYEE,
            )
            .all()
        )
        # TODO: the _cached_employee_member usage below can be DRYed up
        if len(users) > 1:
            log.warning(
                "Wallet has multiple affiliated users who are employees.",
                wallet_id=self.id,
                user_ids=", ".join(str(user.id) for user in users),
            )
            self._cached_employee_member = users[0]
            return self._cached_employee_member
        elif len(users) == 1:
            self._cached_employee_member = users[0]
            return self._cached_employee_member
        return None

    @primitive_threaded_cached_property
    def approved_amount_by_category(self) -> dict[int, int]:
        """
        Get the amount, in cents, approved for reimbursement in each category.
        Returns a dictionary with category IDs as keys:
            {
                1: 1000,
                2: 500,
                3: 0
            }
        """
        amount_by_category = {}
        for amount in self.approved_amounts:
            category = amount.category
            plan = category.reimbursement_plan
            if plan and plan.start_date <= datetime.date.today() <= plan.end_date:
                amount_by_category[amount.reimbursement_request_category_id] = (
                    0 if int(amount.amount) < 0 else int(amount.amount)
                )
        return amount_by_category

    @primitive_threaded_cached_property
    def total_approved_amount_alltime(self) -> int:
        # TODO: add this to a hybrid/column property so it can be used in queries
        return sum(int(amount.amount) for amount in self.approved_amounts)

    @primitive_threaded_cached_property
    def total_approved_amount(self) -> int:
        total_reimbursed_amount: int = 0
        for amount in self.approved_amounts:
            category = amount.category
            plan = category.reimbursement_plan
            if plan and plan.start_date <= datetime.date.today() <= plan.end_date:
                total_reimbursed_amount += int(amount.amount)
        if total_reimbursed_amount < 0:
            log.error(f"Reimbursement amounts are negative for wallet {self.id}.")
            # Ensure balance does not go negative if a user was refunded more than they were initially charged.
            total_reimbursed_amount = 0
        return total_reimbursed_amount

    @primitive_threaded_cached_property
    def total_reimbursed_amount_alltime(self) -> int:
        # TODO: add this to a hybrid/column property so it can be used in queries
        return sum(int(amount.amount) for amount in self.reimbursed_amounts)

    @primitive_threaded_cached_property
    def total_reimbursed_amount(self) -> int:
        total_reimbursed_amount: int = 0
        for amount in self.reimbursed_amounts:
            category = amount.category
            plan = category.reimbursement_plan
            if plan and plan.start_date <= datetime.date.today() <= plan.end_date:
                total_reimbursed_amount += int(amount.amount)

        return total_reimbursed_amount

    @primitive_threaded_cached_property
    def total_available_amount_alltime(self) -> int:
        # TODO: add this to a hybrid/column property so it can be used in queries
        return sum(
            int(category.reimbursement_request_category_maximum)
            for category in self.get_or_create_wallet_allowed_categories
            if category.reimbursement_request_category_maximum
        )

    @primitive_threaded_cached_property
    def total_available_amount(self) -> int:
        total_available_amount: int = 0
        for category_assoc in self.get_or_create_wallet_allowed_categories:
            category = category_assoc.reimbursement_request_category
            plan = category.reimbursement_plan
            if plan and plan.start_date <= datetime.date.today() <= plan.end_date:
                if category_assoc.reimbursement_request_category_maximum:
                    total_available_amount += (
                        # `reimbursement_request_category_maximum` int(11) DEFAULT NULL,
                        category_assoc.reimbursement_request_category_maximum
                    )

        return total_available_amount

    @primitive_threaded_cached_property
    def available_currency_amount_by_category(self) -> dict[int, int]:
        """
        Returns:
            dict: [category.id: int, amount_remaining: int]
        """
        available_amount: dict[int, int] = {}
        for category_assoc in self.get_or_create_wallet_allowed_categories:
            category = category_assoc.reimbursement_request_category
            plan = category.reimbursement_plan
            if plan and plan.start_date <= datetime.date.today() <= plan.end_date:
                if category_assoc.reimbursement_request_category_maximum:
                    if category.id in self.approved_amount_by_category:
                        available_amount[category.id] = (
                            category_assoc.reimbursement_request_category_maximum
                            - self.approved_amount_by_category[category.id]
                        )
                    else:
                        available_amount[
                            category.id
                        ] = category_assoc.reimbursement_request_category_maximum
        return available_amount

    @primitive_threaded_cached_property
    def available_credit_amount_by_category(self) -> dict[int, int]:
        """
        Returns:
            dict: [category.id: int, num_credits_remaining: int]
        """
        available_amount: dict[int, int] = {}
        # Get current balances
        for cycle_credit in self.cycle_credits:
            category_id = (
                cycle_credit.reimbursement_organization_settings_allowed_category.reimbursement_request_category_id
            )
            available_amount[category_id] = cycle_credit.amount
        # If the account wasn't funded for some reason, show the total amount.
        # TODO: Figure out if this block is necessary - We should be funding all wallets on qualification with credits.
        for category_assoc in self.get_or_create_wallet_allowed_categories:
            category = category_assoc.reimbursement_request_category
            if (
                category_assoc.benefit_type != BenefitTypes.CYCLE
                or category.id in available_amount
            ):
                continue
            available_amount[category.id] = (
                category_assoc.num_cycles * NUM_CREDITS_PER_CYCLE
            )
        return available_amount

    # instance level cache of get_direct_payment_category
    _cached_get_direct_payment_category: ReimbursementRequestCategory | None = None

    @property
    def get_org_direct_payment_category(self) -> ReimbursementRequestCategory | None:
        """The direct payment category that is offered by the org but the member may or may not have access to"""
        for (
            category_assoc
        ) in self.reimbursement_organization_settings.allowed_reimbursement_categories:
            category: ReimbursementRequestCategory = (
                category_assoc.reimbursement_request_category
            )
            plan = category.reimbursement_plan
            if (
                plan
                and plan.start_date <= datetime.date.today() <= plan.end_date
                and category.is_direct_payment_eligible(self)
            ):
                return category

        return None

    @property
    def get_direct_payment_category(self) -> ReimbursementRequestCategory | None:
        """The direct payment category that the member currently has access to"""
        if self._cached_get_direct_payment_category:
            return self._cached_get_direct_payment_category

        # this assumes direct payment only has 2 categories(fertility & preservation)
        # and that a member cannot be enrolled in both at the same time
        for category_assoc in self.get_wallet_allowed_categories:
            category: ReimbursementRequestCategory = (
                category_assoc.reimbursement_request_category
            )
            plan = category.reimbursement_plan
            if (
                plan
                and plan.start_date <= datetime.date.today() <= plan.end_date
                and category.is_direct_payment_eligible(self)
            ):
                self._cached_get_direct_payment_category = category
                return self._cached_get_direct_payment_category

        log.debug("No direct payment category found for wallet", wallet_id=self.id)
        return None

    @property
    def is_shareable(self) -> bool:
        # local import to stop circular reference
        from wallet.services.reimbursement_benefits import (
            get_member_type_details_from_wallet,
        )

        to_return = (
            self.reimbursement_organization_settings.allowed_members
            == AllowedMembers.SHAREABLE
            and get_member_type_details_from_wallet(self).member_type
            == MemberType.MAVEN_GOLD
        )

        return bool(to_return)

    @observability.wrap
    def get_direct_payment_balances(
        self,
    ) -> Tuple[Optional[int], Optional[int], Optional[BenefitTypes]]:
        """
        Returns a triplet (total balance, available balance, BenefitsType) for direct payment category as cents or credits
        """
        category = self.get_direct_payment_category
        if not category:
            return None, None, None

        org_settings_category = None
        for allowed_category in self.get_or_create_wallet_allowed_categories:
            if allowed_category.reimbursement_request_category_id == category.id:
                org_settings_category = allowed_category
                break
        if not org_settings_category:
            return None, None, None

        benefit_type = org_settings_category.benefit_type
        if benefit_type == BenefitTypes.CURRENCY:
            total_balance = org_settings_category.reimbursement_request_category_maximum
            remaining_balance = self.available_currency_amount_by_category[category.id]
        else:
            total_balance = org_settings_category.num_cycles * NUM_CREDITS_PER_CYCLE
            remaining_balance = self.available_credit_amount_by_category[category.id]
        return total_balance, remaining_balance, benefit_type  # type: ignore[return-value] # Incompatible return value type (got "Tuple[int, int, str]", expected "Tuple[Optional[int], Optional[int], Optional[BenefitTypes]]")

    def category_benefit_type(self, request_category_id: int) -> BenefitTypes | None:
        """
        Returns: BenefitTypes | None
            Returns the BenefitType (CREDIT/CURRENCY) of the category
            if it is found. Otherwise, it returns None.
        """
        categories = self.get_or_create_wallet_allowed_categories
        category_benefit_type = None
        for category in categories:
            if category.reimbursement_request_category_id == request_category_id:
                category_benefit_type = category.benefit_type
                break

        if not category_benefit_type:
            log.debug("Category for reimbursement request category not found.")
            return None

        return category_benefit_type  # type: ignore[return-value] # Incompatible return value type (got "str", expected "Optional[BenefitTypes]")

    @ddtrace.tracer.wrap()
    def create_sources_from_message(self, message: Message):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        asset_ids = [asset.id for asset in message.attachments]
        existing_asset_ids = {
            id
            for id, in db.session.query(ReimbursementRequestSource)
            .with_entities(ReimbursementRequestSource.user_asset_id)
            .filter(
                ReimbursementRequestSource.wallet == self,
                ReimbursementRequestSource.user_asset_id.in_(asset_ids),
            )
        }
        new_sources = []
        for user_asset in message.attachments:
            if user_asset.id not in existing_asset_ids:
                new_sources.append(
                    ReimbursementRequestSource(wallet=self, user_asset=user_asset)
                )
        db.session.add_all(new_sources)
        db.session.commit()
        return new_sources

    def get_first_name_last_name_and_dob(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Call e9y service to get first name, last name and dob. If it doesn't exist, use organization employee's first name,
        last name and dob.  If that doesn't exist, use the profile member's first, last name.
        """
        e9y_service = get_verification_service()
        organization_id = self.reimbursement_organization_settings.organization_id
        eligibility_member = e9y_service.get_verification_for_user_and_org(
            user_id=self.user_id,
            organization_id=organization_id,
        )

        if not eligibility_member:
            log.error(
                f"No eligibility_member found for member ID {self.member.id} in org {organization_id}."
            )

        first_name = (
            eligibility_member and eligibility_member.first_name
        ) or self.member.first_name
        last_name = (
            eligibility_member and eligibility_member.last_name
        ) or self.member.last_name
        date_of_birth = (eligibility_member and eligibility_member.date_of_birth) or ""

        return [first_name, last_name, date_of_birth]

    def get_debit_banner(self, hdhp_status):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Returns FE debit banner type (REQUEST_DEBIT_BANNER, NEW_DEBIT_BANNER, HDHP_DEBIT_BANNER)
        """
        if self.debit_card_eligible:
            no_debit_card = self.debit_card is None
            if no_debit_card:
                if hdhp_status is False:
                    return DebitBannerStatus.HDHP_DEBIT_BANNER.value
                else:
                    return DebitBannerStatus.REQUEST_DEBIT_BANNER.value
            if self.debit_card.card_status is CardStatus.NEW:
                return DebitBannerStatus.NEW_DEBIT_BANNER.value

    # instance level cache of get_or_create_wallet_allowed_categories
    _cached_get_allowed_categories: list[
        ReimbursementOrgSettingCategoryAssociation
    ] | None = None

    @property
    def get_wallet_allowed_categories(
        self,
    ) -> list[ReimbursementOrgSettingCategoryAssociation]:
        """
        A version of get_or_create_wallet_allowed_categories that does not create Alegeus accounts
        """
        from wallet.services.reimbursement_category_activation_visibility import (
            CategoryActivationService,
        )

        category_activation_service = CategoryActivationService(session=db.session)
        try:
            allowed_categories = (
                category_activation_service.get_wallet_allowed_categories(
                    wallet=self, bypass_alegeus=True
                )
            )
        except Exception as e:
            log.exception(
                "Exception calling get_wallet_allowed_categories",
                wallet_id=str(self.id),
                error=str(e),
                traceback=format_exc(),
            )
            raise e

        return allowed_categories

    @property
    def get_or_create_wallet_allowed_categories(
        self,
    ) -> list[ReimbursementOrgSettingCategoryAssociation]:
        from wallet.services.reimbursement_category_activation_visibility import (
            CategoryActivationService,
        )

        if self._cached_get_allowed_categories is not None:
            return self._cached_get_allowed_categories

        allowed_categories = []
        category_activation_service = CategoryActivationService(session=db.session)
        try:
            try:
                allowed_categories = (
                    category_activation_service.get_wallet_allowed_categories(
                        wallet=self
                    )
                )
                category_activation_service.session.commit()
            except IntegrityError as e:
                log.error(
                    "Integrity error exception committing get_wallet_allowed_categories",
                    wallet_id=str(self.id),
                    error=str(e),
                    traceback=format_exc(),
                )
                db.session.rollback()
                allowed_categories = (
                    category_activation_service.get_wallet_allowed_categories(
                        wallet=self
                    )
                )
                category_activation_service.session.commit()
        except Exception as e:
            log.exception(
                "Exception committing get_wallet_allowed_categories",
                wallet_id=str(self.id),
                error=str(e),
                traceback=format_exc(),
            )
            db.session.rollback()

        self._cached_get_allowed_categories = allowed_categories
        return self._cached_get_allowed_categories

    def get_rwu_by_user_id(self, user_id: int) -> ReimbursementWalletUsers | None:
        return (
            db.session.query(ReimbursementWalletUsers)
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == self.id,
                ReimbursementWalletUsers.user_id == user_id,
            )
            .one_or_none()
        )

    def __repr__(self) -> str:
        return f"<ReimbursementWallet {self.id} [User:{self.user_id}] [{self.state}]>"


class CountryCurrencyCode(ModelBase):
    __tablename__ = "country_currency_code"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    country_alpha_2 = Column(
        String(2),
        nullable=False,
    )
    currency_code = Column(
        String,
        nullable=False,
        doc="The ISO4217 code for the currency",
    )
    minor_unit = Column(
        Integer,
        nullable=True,
        default=None,
        doc="The ISO4217 minor unit for the currency",
    )


class MemberHealthPlan(TimeLoggedSnowflakeModelBase):
    __tablename__ = "member_health_plan"

    employer_health_plan_id = Column(
        BigInteger,
        ForeignKey(
            "employer_health_plan.id",
        ),
        nullable=False,
        doc="An Employer Health Plan that the Employee's Health Plan is linked to. Required.",
    )
    reimbursement_wallet_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet.id"),
        nullable=False,
        doc="A reference to the reimbursement Wallet the patient's health plan is associated with. Required.",
    )
    member_id = Column(Integer, nullable=False)
    reimbursement_wallet = relationship(
        "ReimbursementWallet", backref="member_health_plan"
    )
    is_subscriber = Column(Boolean, nullable=False, default=True)
    subscriber_insurance_id = Column(
        String(50),
        nullable=False,
        doc="The primary policy holders insurance id",
    )
    subscriber_first_name = Column(String(50), nullable=True)
    subscriber_last_name = Column(String(50), nullable=True)
    subscriber_date_of_birth = Column(Date, nullable=True)
    patient_first_name = Column(String(50), nullable=True)
    patient_last_name = Column(String(50), nullable=True)
    patient_date_of_birth = Column(Date, nullable=True)
    patient_sex = Column(Enum(MemberHealthPlanPatientSex), nullable=True)
    patient_relationship = Column(
        Enum(MemberHealthPlanPatientRelationship), nullable=True
    )
    plan_start_at = Column(DateTime, nullable=False)
    plan_end_at = Column(DateTime, nullable=True)
    plan_type = Column(
        Enum(FamilyPlanType),
        nullable=False,
        doc="Plan type, i.e. FAMILY, INDIVIDUAL, EMPLOYEE_PLUS, etc.",
    )

    @hybrid_property
    def is_family_plan(self) -> bool:
        return self.plan_type in FAMILY_PLANS

    @is_family_plan.expression  # type: ignore[no-redef]
    def is_family_plan(cls):
        return cls.plan_type.in_([pt.value for pt in FAMILY_PLANS])

    def __repr__(self) -> str:
        return f"<MemberHealthPlan {self.id}>"


def has_valid_member_plan_dates(
    member_id: int,
    wallet_id: int,
    start_at: Optional[datetime.datetime],
    end_at: Optional[datetime.datetime],
    id_to_ignore: Optional[int] = None,
) -> bool:
    """
    SQLAlchemy equivalent of HealthPlanRepository.has_valid_member_plan_dates
    to avoid session issues around db.session.execute.
    """
    query = db.session.query(func.count(MemberHealthPlan.id)).filter(
        or_(
            # starts within the bounds of an existing plan
            and_(
                start_at > MemberHealthPlan.plan_start_at,
                start_at < MemberHealthPlan.plan_end_at,
            ),
            # ends within the bounds of an existing plan
            and_(
                end_at < MemberHealthPlan.plan_end_at,
                end_at > MemberHealthPlan.plan_start_at,
            ),
            # contains an existing plan within its' timespan
            and_(
                start_at <= MemberHealthPlan.plan_start_at,
                end_at >= MemberHealthPlan.plan_end_at,
            ),
            # starts during an open-ended plan
            and_(
                start_at >= MemberHealthPlan.plan_start_at,
                MemberHealthPlan.plan_end_at.is_(None),
            ),
        ),
        MemberHealthPlan.plan_start_at is not None,
        MemberHealthPlan.member_id == member_id,
        MemberHealthPlan.reimbursement_wallet_id == wallet_id,
    )
    if id_to_ignore is not None:
        # For updates, do not include the updated health plan
        query = query.filter(MemberHealthPlan.id != id_to_ignore)
    number_of_overlaps = query.scalar()
    return not bool(number_of_overlaps)


def has_valid_member_plan_start_date(
    member_id: int,
    wallet_id: int,
    start_at: Optional[datetime.datetime],
    id_to_ignore: Optional[int] = None,
) -> bool:
    """
    SQLAlchemy equivalent of HealthPlanRepository.has_valid_member_plan_start_date
    to avoid session issues around db.session.execute.
    """
    query = db.session.query(func.count(MemberHealthPlan.id)).filter(
        or_(
            and_(
                start_at < MemberHealthPlan.plan_start_at,
                MemberHealthPlan.plan_end_at is not None,
            ),
            and_(
                start_at > MemberHealthPlan.plan_start_at,
                start_at < MemberHealthPlan.plan_end_at,
            ),
            MemberHealthPlan.plan_end_at.is_(None),
        ),
        MemberHealthPlan.plan_start_at is not None,
        MemberHealthPlan.member_id == member_id,
        MemberHealthPlan.reimbursement_wallet_id == wallet_id,
    )
    if id_to_ignore is not None:
        # For updates, do not include the updated health plan
        query = query.filter(MemberHealthPlan.id != id_to_ignore)
    number_of_overlaps = query.scalar()
    return not bool(number_of_overlaps)


def validate_member_health_plan_dates(
    target: MemberHealthPlan, id_to_ignore: Optional[int] = None
) -> None:
    """
    Validation for sqlalchemy Member Health Plan inserts to go with validation in the HealthPlanRepository.
    Please use the HealthPlanRepository and not SQLAlchemy Member Health Plan queries.
    """

    def _not_none_or_blank(value: Any) -> bool:
        # Handle Flask Admin sending empty strings instead of nulls
        return value is not None and value != ""

    _validate_member_health_plan_dates(target)

    if _not_none_or_blank(target.plan_start_at) and _not_none_or_blank(
        target.plan_end_at
    ):
        if not has_valid_member_plan_dates(
            member_id=target.member_id,
            wallet_id=target.reimbursement_wallet_id,
            start_at=target.plan_start_at,
            end_at=target.plan_end_at,
            id_to_ignore=id_to_ignore,
        ):
            raise ValueError(
                "Invalid plan_start_at and plan_end_at provided. "
                "Plan dates must not overlap other existing health plans."
            )
    elif _not_none_or_blank(target.plan_start_at):
        if not has_valid_member_plan_start_date(
            member_id=target.member_id,
            wallet_id=target.reimbursement_wallet_id,
            start_at=target.plan_start_at,
            id_to_ignore=id_to_ignore,
        ):
            raise ValueError(
                "Invalid plan_start_at provided. Plan dates must not overlap other existing health plans."
            )
    elif _not_none_or_blank(target.plan_end_at):
        raise ValueError("Cannot provide a plan_end_at without a plan_start_at.")


def _validate_member_health_plan_dates(
    target: MemberHealthPlan,
) -> None:
    if (
        target.plan_start_at and target.plan_end_at
    ) and target.plan_start_at > target.plan_end_at:
        raise ValueError(
            "Invalid plan_start_at and plan_end_at provided. "
            "The plan start date must be before the plan end date."
        )
    try:
        res = (
            db.session.query(EmployerHealthPlan.start_date, EmployerHealthPlan.end_date)
            .filter_by(id=target.employer_health_plan_id)
            .one()
        )
        if (target.plan_end_at and (target.plan_end_at.date() > res.end_date)) or (
            target.plan_start_at and (target.plan_start_at.date() < res.start_date)
        ):
            e_st_str = res.start_date.strftime("%b %d, %Y")
            e_en_str = res.end_date.strftime("%b %d, %Y")
            raise ValueError(
                f"Member health plan dates must fit within the employer health plan "
                f"(id: {target.employer_health_plan_id}) dates which are {e_st_str} and {e_en_str}."
            )
    except NoResultFound:
        raise ValueError(
            f"Unable to find employer health plan for {target.employer_health_plan_id}."
        )


@event.listens_for(MemberHealthPlan, "before_insert")
def validate_dates_before_insert(
    mapper: sqlalchemy.orm.Mapper, connection: Connection, target: MemberHealthPlan
) -> None:
    validate_member_health_plan_dates(target)


@event.listens_for(MemberHealthPlan, "before_update")
def validate_dates_before_update(
    mapper: sqlalchemy.orm.Mapper, connection: Connection, target: MemberHealthPlan
) -> None:
    validate_member_health_plan_dates(target, id_to_ignore=target.id)


class ReimbursementWalletCategoryRuleEvaluationResult(TimeLoggedExternalUuidModelBase):
    __tablename__ = "reimbursement_wallet_allowed_category_rules_evaluation_result"

    reimbursement_organization_settings_allowed_category_id = Column(
        BigInteger,
        ForeignKey("reimbursement_organization_settings_allowed_category.id"),
        nullable=False,
    )
    reimbursement_wallet_id = Column(
        BigInteger, ForeignKey("reimbursement_wallet.id"), nullable=False
    )
    executed_category_rule = Column(
        Text,
        nullable=True,
        doc="All of the rules that returned True for this evaluation.",
    )
    failed_category_rule = Column(
        Text,
        nullable=True,
        doc="The rule that returned False upon evaluation. Null if the rule evaluated True.",
    )
    evaluation_result = Column(Boolean, nullable=False)
    reimbursement_organization_settings_allowed_category = relationship(
        "ReimbursementOrgSettingCategoryAssociation"
    )
    reimbursement_wallet = relationship("ReimbursementWallet")

    def __repr__(self) -> str:
        return f"<ReimbursementWalletCategoryRuleEvaluationResult {self.id}>"


class ReimbursementWalletCategoryRuleEvaluationFailure(TimeLoggedExternalUuidModelBase):
    __tablename__ = "reimbursement_wallet_allowed_category_rule_evaluation_failure"

    rule_name = Column(String, nullable=False)

    evaluation_result_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet_allowed_category_rules_evaluation_result.id"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ReimbursementWalletCategoryRuleEvaluationFailure {self.id} {self.rule_name}>"


class ReimbursementWalletAllowedCategorySettings(TimeLoggedExternalUuidModelBase):
    __tablename__ = "reimbursement_wallet_allowed_category_settings"

    updated_by = Column(
        String,
        nullable=False,
        doc="User that last updated this record.",
    )
    reimbursement_organization_settings_allowed_category_id = Column(
        BigInteger,
        ForeignKey("reimbursement_organization_settings_allowed_category.id"),
        nullable=False,
    )
    reimbursement_wallet_id = Column(
        BigInteger, ForeignKey("reimbursement_wallet.id"), nullable=False
    )
    access_level = Column(Enum(CategoryRuleAccessLevel), nullable=False)

    access_level_source = Column(Enum(CategoryRuleAccessSource), nullable=False)

    reimbursement_organization_settings_allowed_category = relationship(
        "ReimbursementOrgSettingCategoryAssociation"
    )
    reimbursement_wallet = relationship("ReimbursementWallet")

    def __repr__(self) -> str:
        return f"<ReimbursementWalletAllowedCategorySettings {self.id}>"
