from __future__ import annotations

import datetime
import typing
from abc import ABC, abstractmethod
from typing import Optional

from dateutil.relativedelta import relativedelta

import eligibility
from storage.connection import db
from utils.log import logger
from wallet.constants import INTERNAL_TRUST_WHS_URL
from wallet.models.constants import CategoryRuleAccessLevel, WalletState
from wallet.models.reimbursement_wallet import (
    ReimbursementWalletAllowedCategorySettings,
)
from wallet.services.wallet_historical_spend import WalletHistoricalSpendService
from wallet.utils.common import get_verification_record_data, has_tenure_exceeded

if typing.TYPE_CHECKING:
    from wallet.models.reimbursement_organization_settings import (
        ReimbursementOrgSettingCategoryAssociation,
    )
    from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


class AbstractCategoryRule(ABC):
    @classmethod
    @abstractmethod
    def execute(
        cls,
        wallet: "ReimbursementWallet",
        association: Optional["ReimbursementOrgSettingCategoryAssociation"] = None,
    ) -> bool:
        raise NotImplementedError


class TOCCategoryRule(AbstractCategoryRule):
    transition_start_date: datetime.date
    transition_end_date: datetime.date
    rule_name: str

    @classmethod
    def execute(
        cls,
        wallet: "ReimbursementWallet",
        association: Optional["ReimbursementOrgSettingCategoryAssociation"] = None,
    ) -> bool:
        # Fetch the existing visibility record
        visibility_record = (
            db.session.query(ReimbursementWalletAllowedCategorySettings)
            .filter_by(
                reimbursement_wallet_id=wallet.id,
                reimbursement_organization_settings_allowed_category_id=association.id,
            )
            .one_or_none()
        )
        existing_visibility = (
            visibility_record.access_level if visibility_record else None
        )
        log.info(
            f"{cls.rule_name}: existing visibility",
            existing_visibility=visibility_record,
            wallet_id=str(wallet.id),
        )
        historical_spend_service = WalletHistoricalSpendService(
            whs_base_url=INTERNAL_TRUST_WHS_URL
        )
        # Determine if the member is eligible for the fertility category
        (
            visibility_result,
            reason,
        ) = historical_spend_service.determine_category_eligibility(
            wallet=wallet,
            category_association=association,
            transition_start_date=cls.transition_start_date,
            transition_end_date=cls.transition_end_date,
            rule_name=cls.rule_name,
        )
        log.info(
            f"{cls.rule_name}: WHS Rule eligibility results",
            result=visibility_result,
            reason=reason,
            wallet_id=str(wallet.id),
        )

        # If the member gains visibility we need to run a historical spend file only for qualified wallets since they didn't get processed during wallet qualification.
        if (
            existing_visibility == CategoryRuleAccessLevel.NO_ACCESS
            and visibility_result
            and wallet.state == WalletState.QUALIFIED
        ):
            try:
                visibility_record.access_level = CategoryRuleAccessLevel.FULL_ACCESS
                error_messages = historical_spend_service.process_historical_spend_wallets(
                    file_id=None,
                    reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
                    wallet_ids=[wallet.id],
                    messages=None,
                )
                if error_messages:
                    log.exception(
                        "Historical spend error when processing rules. Setting visibility to False.",
                        wallet_id=str(wallet.id),
                        rule=cls.rule_name,
                    )
                    return False

            except Exception as e:
                log.exception(
                    "Historical spend exception when processing rules. Setting visibility to False.",
                    wallet_id=str(wallet.id),
                    error=str(e),
                    rule=cls.rule_name,
                )
                return False

        return visibility_result


class AmazonProgenyTOCRule(TOCCategoryRule):
    transition_start_date = datetime.date(2024, 1, 1)
    transition_end_date = datetime.date(2025, 7, 1)
    rule_name = "AMAZON_PROGENY_TOC_PERIOD"


class LowesProgenyTOCRule(TOCCategoryRule):
    transition_start_date = datetime.date(2024, 10, 1)
    transition_end_date = datetime.date(2025, 4, 1)
    rule_name = "LOWES_PROGENY_TOC_PERIOD"


class TenureCategoryRule(AbstractCategoryRule):
    tenure_days: int
    tenure_years: int
    rule_name: str

    @classmethod
    def execute(
        cls,
        wallet: "ReimbursementWallet",
        association: Optional["ReimbursementOrgSettingCategoryAssociation"] = None,
    ) -> bool:
        if not hasattr(cls, "tenure_years") and not hasattr(cls, "tenure_days"):
            log.error(f"{cls.__name__} must define either tenure_days or tenure_years.")
            return False

        user_id = wallet.all_active_users[0].id if wallet.all_active_users else None
        org_id = wallet.reimbursement_organization_settings.organization_id

        if not user_id:
            log.info(
                f"{cls.rule_name}: Wallet user record not found.",
                wallet_id=str(wallet.id),
            )
            return False

        # Get eligibility verification data
        eligibility_service = eligibility.get_verification_service()
        verification = get_verification_record_data(
            user_id=user_id,
            organization_id=org_id,
            eligibility_service=eligibility_service,
        )
        if not verification:
            log.info(
                f"{cls.rule_name}: Eligibility verification record not found.",
                wallet_id=str(wallet.id),
            )
            return False

        start_date = verification.record.get("employee_start_date")
        if not start_date:
            log.info(
                f"{cls.rule_name}: Eligibility verification record missing start_date.",
                wallet_id=str(wallet.id),
                user_id=user_id,
                organization_id=org_id,
            )
            return False

        # Determine tenure check type
        if hasattr(cls, "tenure_years"):
            return has_tenure_exceeded(start_date, years=cls.tenure_years)
        else:
            return has_tenure_exceeded(start_date, days=cls.tenure_days)

    def add_tenure_to_start_date(self, date: datetime.date) -> datetime.date:
        if hasattr(self, "tenure_years"):
            tenure = relativedelta(years=self.tenure_years)
        else:
            tenure = relativedelta(days=self.tenure_days)
        return date + tenure


class Tenure30DaysCategoryRule(TenureCategoryRule):
    rule_name = "TENURE_30_DAYS"
    tenure_days = 30


class Tenure90DaysCategoryRule(TenureCategoryRule):
    rule_name = "TENURE_90_DAYS"
    tenure_days = 90


class Tenure180DaysCategoryRule(TenureCategoryRule):
    rule_name = "TENURE_180_DAYS"
    tenure_days = 180


class TenureOneCalendarYearCategoryRule(TenureCategoryRule):
    rule_name = "TENURE_ONE_CALENDAR_YEAR"
    tenure_years = 1


class CategoryActivationException(Exception):
    pass


class ActionableCategoryActivationException(CategoryActivationException):
    def __init__(self, message: str):
        self.message = message

    def __repr__(self) -> str:
        return f"Need Ops Action: {self.message}"

    __str__ = __repr__
