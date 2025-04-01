from __future__ import annotations

import datetime
from collections import defaultdict
from traceback import format_exc
from typing import List, Optional

import pytz
import sqlalchemy
from maven import observability

import eligibility
from common import stats, wallet_historical_spend
from common.wallet_historical_spend import Adjustment, LedgerEntry
from common.wallet_historical_spend.client import WalletHistoricalSpendClient
from cost_breakdown.constants import ClaimType
from storage.connection import db
from tasks.queues import job
from utils import gcp_pubsub
from utils.log import logger
from wallet.constants import (
    HISTORICAL_SPEND_LABEL,
    INTERNAL_TRUST_WHS_URL,
    WHS_ADJUSTMENT_TOPIC,
    HistoricalSpendRuleResults,
)
from wallet.models.constants import (
    BenefitTypes,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletState,
)
from wallet.models.currency import Money
from wallet.models.reimbursement import (
    ReimbursementRequest,
    ReimbursementRequestCategory,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.services.currency import DEFAULT_CURRENCY_CODE, CurrencyService
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory
from wallet.utils.alegeus.claims.create import create_direct_payment_claim_in_alegeus

log = logger(__name__)


class HistoricalSpendProcessingError(Exception):
    def __init__(self, message: str, wallet_id: int) -> None:
        self.message = message
        self.wallet_id = wallet_id
        super().__init__(self.message)


class WalletHistoricalSpendService:
    def __init__(
        self,
        whs_base_url: Optional[str] = None,
        whs_client: Optional[WalletHistoricalSpendClient] = None,
        session: sqlalchemy.orm.scoping.ScopedSession = None,
    ):
        self.whs_client = whs_client or wallet_historical_spend.get_client(
            base_url=whs_base_url  # type: ignore[arg-type]
        )
        self.session = session or db.session

    @observability.wrap
    def process_historical_spend_wallets(
        self,
        file_id: Optional[str],
        reimbursement_organization_settings_id: int,
        wallet_ids: List,
        messages: Optional[List] = None,
    ) -> List:
        """
        Processes a historical spend file for the specified wallets and retrieves wallet ledger entries to process for
        account balance reconciliation.
        """
        if messages is None:
            messages = []
        log.info("Starting processing historical wallets", wallet_count=len(wallet_ids))
        wallets = self.get_wallets_by_ids(wallet_ids)
        if not wallets:
            log.error(
                "No qualified or run out wallets found for wallet historical spend.",
                reimbursement_organization_settings_id=str(
                    reimbursement_organization_settings_id
                ),
                file_id=file_id,
            )
            return messages

        # Get eligibility info for all wallet users and store them in a dict
        wallet_data_lookup = self.get_wallet_eligibility_data(wallets=wallets)

        # Build request body to call WHS
        request_body = self.format_request_body(
            lookup=wallet_data_lookup,
            file_id=file_id,
            reimbursement_organization_settings_id=reimbursement_organization_settings_id,
            exclude_adjusted=True,
        )
        log.info(
            "Submitted request for ledger entries to WHS.",
            reimbursement_organization_settings_id=str(
                reimbursement_organization_settings_id
            ),
            file_id=file_id,
        )
        # Call WHS for ledger entries
        wallet_ledger_entries = self.get_ledger_entries(request_body, file_id)
        if not wallet_ledger_entries:
            log.info(
                "No ledger entries found for wallet historical spend.",
                reimbursement_organization_settings_id=str(
                    reimbursement_organization_settings_id
                ),
                file_id=file_id,
                reason="No ledger entries returned.",
            )
            return messages
        log.info(
            "Processing WHS ledger entries.",
            ledger_entry_count=len(wallet_ledger_entries),
        )
        # Handle processing historical spend records for wallet qualification flow
        if file_id is None:
            messages = self._process_wallet_qualification_entries(
                wallet_ledger_entries=wallet_ledger_entries,
                wallet_data_lookup=wallet_data_lookup,
                messages=messages,
                reimbursement_organization_settings_id=reimbursement_organization_settings_id,
            )
        else:
            # Handle file processing flow
            messages = self._process_entries(
                entries=wallet_ledger_entries,
                wallet_data_lookup=wallet_data_lookup,
                messages=messages,
                file_id=file_id,
                reimbursement_organization_settings_id=reimbursement_organization_settings_id,
            )
        log.info("Historical wallet spend batch processed.")
        return messages

    def _process_wallet_qualification_entries(
        self,
        wallet_ledger_entries: list[LedgerEntry],
        wallet_data_lookup: dict,
        messages: list[FlashMessage],
        reimbursement_organization_settings_id: int,
    ) -> list[FlashMessage]:
        """
        Processes historical spend ledger entries for wallet qualification.  This handles
        the scenario where no file_id is provided, indicating entries are being processed
        during the wallet qualification flow for a single wallet.
        """
        category_map = self.create_category_map(wallet_ledger_entries)
        for category, entries in category_map.items():
            if any(entry.adjustment_id for entry in entries):
                log.info(
                    "Existing adjustments found skipping.",
                    category=category,
                    employee_id=entries[0].employee_id,
                )
            else:
                # Process the latest entries historical spend
                historical_spend_entry: LedgerEntry = entries.pop(0)
                log.info(
                    "Processing latest entry single wallet process.",
                    category=category,
                    balance_id=historical_spend_entry.balance_id,
                    employee_id=historical_spend_entry.employee_id,
                )
                messages = self._process_entries(
                    entries=[historical_spend_entry],
                    wallet_data_lookup=wallet_data_lookup,
                    messages=messages,
                    file_id=None,
                    reimbursement_organization_settings_id=reimbursement_organization_settings_id,
                )
                # Process remaining entries with override_amount 0 for acknowledgement purposes
                if entries:
                    log.info(
                        "Processing remaining entries single wallet process (zero value).",
                        entry_count=len(entries),
                        category=category,
                    )
                    messages = self._process_entries(
                        entries=entries,
                        wallet_data_lookup=wallet_data_lookup,
                        messages=messages,
                        file_id=None,
                        reimbursement_organization_settings_id=reimbursement_organization_settings_id,
                        override_amount=0,
                    )
        return messages

    def _process_entries(
        self,
        entries: List,
        wallet_data_lookup: dict,
        messages: List,
        file_id: Optional[str],
        reimbursement_organization_settings_id: int,
        override_amount: int | None = None,
    ) -> List:
        """
        Helper method to process wallet ledger entries.
        """
        processed_entries = 0
        for entry in entries:
            # Reference lookup map with ledger entry data that matches e9y record
            wallet = self.lookup_wallet(lookup=wallet_data_lookup, entry=entry)
            if wallet:
                try:
                    log.info(
                        "Found wallet starting to process entry.",
                        wallet_id=str(wallet.id),
                        ledger_entry_balance_id=entry.balance_id,
                        employee_id=entry.employee_id,
                    )
                    # Process the entry
                    self.process_wallet_historical_spend_entry(
                        ledger_entry=entry,
                        wallet=wallet,
                        file_id=file_id,
                        override_amount=override_amount,
                    )
                    processed_entries += 1
                except HistoricalSpendProcessingError as e:
                    log.error(
                        "Unable to process wallet ledger entry",
                        error=str(e),
                        wallet_id=str(wallet.id),
                        ledger_entry_balance_id=entry.balance_id,
                        employee_id=entry.employee_id,
                        reason=e.message,
                        file_id=file_id,
                    )
                    messages.append(
                        FlashMessage(
                            message=f"Error processing wallet historic spend entries. {e}",
                            category=FlashMessageCategory.ERROR,
                        )
                    )
            else:
                log.error(
                    "Wallet ledger entry not found in wallet lookup",
                    ledger_entry_balance_id=entry.balance_id,
                    reimbursement_organization_settings_id=str(
                        reimbursement_organization_settings_id
                    ),
                    file_id=file_id,
                    reason="Wallet ledger entry not found in wallet lookup.",
                )
        log.info(
            "Historical wallet entries processed.",
            processed_entries_count=processed_entries,
        )
        return messages

    @observability.wrap
    def process_wallet_historical_spend_entry(
        self,
        ledger_entry: LedgerEntry,
        wallet: ReimbursementWallet,
        file_id: Optional[str] = None,
        override_amount: int | None = None,
    ) -> None:
        """
        Processes a historical spend ledger entry for a reimbursement wallet by sending a transaction to Alegeus and
        editing credits if wallet is cycles. If successful, publishes to a WHS adjustments topic.
        """
        if override_amount is not None:
            amount_to_be_adjusted = override_amount
        else:
            amount_to_be_adjusted = (
                ledger_entry.calculated_spend
                if file_id
                else ledger_entry.historical_spend
            )

        # Determine if we need to make an adjustment based off of the amount.
        # If amount is zero, no adjustment necessary, but still acknowledge WHS
        reimbursement_request_id: int | None = None

        # Retrieve the category to deduct historical spend from
        spend_category = self.get_spend_category(
            wallet=wallet, category_string=ledger_entry.category
        )
        if not spend_category:
            return

        benefit_type = wallet.category_benefit_type(
            request_category_id=spend_category.id
        )
        if amount_to_be_adjusted != 0:
            if not benefit_type:
                log.error(
                    "No category benefit type found.",
                    ledger_category=ledger_entry.category,
                    wallet_id=str(wallet.id),
                )
                raise HistoricalSpendProcessingError(
                    message="No category benefit type found. Cannot determine adjustment",
                    wallet_id=wallet.id,
                )
            reimbursement_request = self.create_reimbursement_request(
                ledger_entry=ledger_entry,
                wallet=wallet,
                spend_category=spend_category,
                file_id=file_id,
            )
            log.info(
                "Historical spend reimbursement request created.",
                reimbursement_request_id=str(reimbursement_request.id),
                ledger_entry_balance_id=ledger_entry.balance_id,
                wallet_id=str(wallet.id),
            )
            # Deduct historical spend from Alegeus
            self.submit_claim_to_alegeus(
                wallet=wallet, reimbursement_request=reimbursement_request
            )
            if benefit_type == BenefitTypes.CYCLE:
                # Adjust credits after submission to Alegeus
                self.adjust_reimbursement_credits(
                    wallet=wallet,
                    ledger_entry=ledger_entry,
                    spend_category=spend_category,
                    reimbursement_request=reimbursement_request,
                    file_id=file_id,
                )
            reimbursement_request_id = reimbursement_request.id

        log.info(
            "WHS ledger adjustment amount for wallet.",
            wallet_id=str(wallet.id),
            amount_adjusted=amount_to_be_adjusted,
        )
        # Acknowledge in WHS the wallet balance was adjusted with historical spend record
        self.publish_adjustment_notification(
            ledger_entry=ledger_entry,
            wallet=wallet,
            benefit_type=benefit_type,
            reimbursement_request_id=reimbursement_request_id,
            file_id=file_id,
        )

    @staticmethod
    @observability.wrap
    def publish_adjustment_notification(
        ledger_entry: LedgerEntry,
        wallet: ReimbursementWallet,
        benefit_type: BenefitTypes,
        reimbursement_request_id: int | None = None,
        file_id: Optional[str] = None,
    ) -> None:
        try:
            log.info("Publishing adjustment to WHS")
            is_currency = benefit_type != BenefitTypes.CYCLE
            if is_currency:
                value = (
                    ledger_entry.calculated_spend
                    if file_id
                    else ledger_entry.historical_spend
                )
            else:
                value = (
                    ledger_entry.calculated_cycles
                    if file_id
                    else ledger_entry.historical_cycles_used
                )

            adjustment = Adjustment.create_adjustment_dict(
                entry=ledger_entry,
                wallet=wallet,
                is_currency=is_currency,
                reimbursement_request_id=str(reimbursement_request_id)
                if reimbursement_request_id
                else None,
                value=value,
            )
            mids = gcp_pubsub.publish(
                WHS_ADJUSTMENT_TOPIC,
                adjustment,
                pod_name=stats.PodNames.BENEFITS_EXP,
            )
            log.info(
                "Adjustment published to WHS",
                wallet_id=str(wallet.id),
                ledger_balance_id=ledger_entry.balance_id,
                message_id=mids[0],
            )
        except Exception:
            log.exception(
                "Failed to publish adjustment",
                wallet_id=str(wallet.id),
                ledger_balance_id=ledger_entry.balance_id,
                reimbursement_request_id=str(reimbursement_request_id)
                if reimbursement_request_id
                else None,
                benefit_type=benefit_type,
                reason=format_exc(),
            )

    @staticmethod
    @observability.wrap
    def create_category_map(entries: list[LedgerEntry]) -> dict:
        """Group ledger entries by category and sort them by created_at desc."""
        category_map = defaultdict(list)
        for entry in entries:
            category_map[entry.category].append(entry)
        for category in category_map:
            category_map[category].sort(key=lambda x: x.created_at, reverse=True)
        return category_map

    @staticmethod
    @observability.wrap
    def get_spend_category(
        wallet: ReimbursementWallet, category_string: str
    ) -> ReimbursementRequestCategory | None:
        """
        Finds the reimbursement request category corresponding to the ledger entry.
        """
        spend_category = None
        ledger_expense_type = None
        try:
            ledger_expense_type = ReimbursementRequestExpenseTypes(
                category_string.upper()
            )
        except ValueError as e:
            log.exception(
                "LedgerEntry category not mapped to a ReimbursementRequestExpenseTypes value",
                ledger_category=category_string,
                wallet_id=str(wallet.id),
                error=str(e),
            )

        if ledger_expense_type:
            for category_association in wallet.get_or_create_wallet_allowed_categories:
                if (
                    ledger_expense_type
                    in category_association.reimbursement_request_category.expense_types
                ):
                    spend_category = category_association.reimbursement_request_category

        if not spend_category:
            log.error(
                "Wallet user doesn't have category for the provided ledger entry category.",
                ledger_category=category_string,
                wallet_id=str(wallet.id),
            )
        return spend_category

    @observability.wrap
    def create_reimbursement_request(
        self,
        ledger_entry: LedgerEntry,
        wallet: ReimbursementWallet,
        spend_category: ReimbursementRequestCategory,
        file_id: Optional[str],
    ) -> ReimbursementRequest:
        """
        Creates and returns a reimbursement request based on the ledger entry data.
        """
        wallet_id = wallet.id
        try:
            rr_request_params = self.build_reimbursement_request_params(
                entry=ledger_entry, file_id=file_id
            )
            reimbursement_request = ReimbursementRequest(
                wallet=wallet, category=spend_category, **rr_request_params
            )
            currency_service = CurrencyService()
            transaction: Money = currency_service.to_money(
                amount=reimbursement_request.amount,
                currency_code=DEFAULT_CURRENCY_CODE,
            )
            currency_service.process_reimbursement_request(
                transaction=transaction, request=reimbursement_request
            )
            self.session.add(reimbursement_request)
            self.session.commit()
        except Exception as e:
            log.exception(
                "Failed to create historical spend Reimbursement Request",
                error=str(e),
            )
            self.session.rollback()
            raise HistoricalSpendProcessingError(
                message="Failed to create historical spend Reimbursement Request",
                wallet_id=wallet_id,
            )
        return reimbursement_request

    @staticmethod
    @observability.wrap
    def submit_claim_to_alegeus(
        wallet: ReimbursementWallet, reimbursement_request: ReimbursementRequest
    ) -> None:
        """
        Submits an non-adjudicated reimbursement request transaction or refund as a claim to Alegeus.
        """
        try:
            log.info(
                "Submitting historical wallet record to Alegeus",
                wallet_id=str(wallet.id),
            )
            create_direct_payment_claim_in_alegeus(
                wallet=wallet,
                reimbursement_request=reimbursement_request,
                claim_type=ClaimType.EMPLOYER,
                bypass_check_balance=True,
            )
        except Exception:
            log.exception(
                "Failed to create historical spend claim in Alegeus. Deleting Reimbursement Request",
                wallet_id=str(wallet.id),
            )
            db.session.delete(reimbursement_request)
            db.session.commit()
            raise HistoricalSpendProcessingError(
                message="Failed to create historical spend claim in Alegeus",
                wallet_id=wallet.id,
            )

    @observability.wrap
    def adjust_reimbursement_credits(
        self,
        wallet: ReimbursementWallet,
        ledger_entry: LedgerEntry,
        spend_category: ReimbursementRequestCategory,
        reimbursement_request: ReimbursementRequest,
        file_id: Optional[str],
    ) -> None:
        """
        Adjusts reimbursement credits for a cycle-based reimbursement request category.
        """
        try:
            spent_credits = (
                ledger_entry.calculated_cycles
                if file_id
                else ledger_entry.historical_cycles_used
            )

            reimbursement_credits = self.get_reimbursement_credits_from_category(
                wallet=wallet, reimbursement_request_category_id=spend_category.id
            )
            if not reimbursement_credits:
                log.error("Unable to deduct credits. No Reimbursement Credit found.")
                return
            if spent_credits > 0:
                amount = min(spent_credits, reimbursement_credits.amount) * -1
            else:
                amount = spent_credits * -1

            amount = reimbursement_credits.edit_credit_balance(
                amount=amount,
                reimbursement_request_id=reimbursement_request.id,
                notes="Wallet historical spend adjustment.",
            )
        except Exception as e:
            log.exception(
                "Failed to edit historical spend credits from wallet.",
                wallet_id=str(wallet.id),
                reimbursement_request_id=str(reimbursement_request.id),
                error=str(e),
            )
            return
        log.info(
            "Wallet historic spend credits adjusted.",
            wallet_id=str(wallet.id),
            amount=amount,
            request_category_id=str(spend_category.id),
            reimbursement_request_id=str(reimbursement_request.id),
        )

    @observability.wrap
    def get_ledger_entries(
        self, request_body: dict, file_id: Optional[str]
    ) -> Optional[List]:
        """Get ledger entries from the wallet historical spend API."""
        ledger_entries = self.whs_client.get_historic_spend_records(
            request_body=request_body
        )
        return ledger_entries

    @staticmethod
    @observability.wrap
    def get_wallets_by_ids(wallet_ids: List) -> List:
        """Returns wallets given a list of wallet ids"""
        wallets = (
            db.session.query(ReimbursementWallet)
            .filter(
                ReimbursementWallet.id.in_(wallet_ids),
            )
            .all()
        )
        return wallets

    @observability.wrap
    def get_wallet_eligibility_data(self, wallets: List[ReimbursementWallet]) -> dict:
        """
        Retrieves eligibility verification data for a list of reimbursement wallets and all active wallet users
        and constructs a lookup dictionary.
        Returns a dictionary where each key is a tuple (first_name, last_name, date_of_birth) and the
        value is the associated wallet ID.
        """
        lookup = {}
        eligibility_service = eligibility.get_verification_service()
        for wallet in wallets:
            org_id = wallet.reimbursement_organization_settings.organization_id
            wallet_user_ids = [rwu.user_id for rwu in wallet.reimbursement_wallet_users]
            family_lookup = {}
            for user_id in wallet_user_ids:
                try:
                    verification = (
                        eligibility_service.get_verification_for_user_and_org(
                            user_id=user_id, organization_id=org_id
                        )
                    )
                except Exception as e:
                    log.error(
                        "Eligibility verification record not found.",
                        wallet_id=str(wallet.id),
                        reason="Eligibility verification record not found",
                        error=str(e),
                    )
                    continue
                if not verification or not all(
                    [
                        verification.first_name,
                        verification.last_name,
                        verification.date_of_birth,
                    ]
                ):
                    log.error(
                        "Eligibility verification record not found or missing data.",
                        wallet_id=str(wallet.id),
                        reason="Eligibility verification record not found",
                    )
                    continue  # Skip to the next user if verification is missing

                dob = verification.date_of_birth
                if isinstance(dob, datetime.datetime):
                    dob = verification.date_of_birth.date()
                first_name = self.normalize_string(verification.first_name)
                last_name = self.normalize_string(verification.last_name)
                dob = dob.isoformat()
                key = (first_name, last_name, dob)
                if key in family_lookup:
                    log.info("Shared eligibility file.")
                    continue
                family_lookup[key] = wallet

            # Remove common keys and skip current wallet if conflicts are detected
            self.remove_common_keys(lookup, family_lookup, str(wallet.id))

            # Merge the cleaned family_lookup into the main lookup
            lookup = {**lookup, **family_lookup}
        return lookup

    @staticmethod
    @observability.wrap
    def remove_common_keys(
        existing_lookup: dict, new_lookup: dict, wallet_id: str
    ) -> None:
        """
        Remove common keys from both the existing lookup and the new lookup.
        Logs the keys and wallet IDs involved.
        """
        common_keys = set(existing_lookup.keys()) & set(new_lookup.keys())
        for dup_key in common_keys:
            log.error(
                "Duplicate key detected building historical spend lookup. Removing existing wallet "
                "and skipping new wallet.",
                existing_wallet_id=str(existing_lookup.get(dup_key)),
                duplicate_wallet_id=str(wallet_id),
                reason="Duplicate key detected building historical spend lookup.",
            )
            # Safely remove keys
            existing_lookup.pop(dup_key, None)
            new_lookup.pop(dup_key, None)

    @staticmethod
    @observability.wrap
    def lookup_wallet(lookup: dict, entry: LedgerEntry) -> ReimbursementWallet | None:
        """
        Given a historical file record (LedgerEntry), find the associated wallet from the given lookup dictionary.
        Returns: Reimbursement Wallet or None if no wallet is found.
        """

        def safe_upper(value: str | None) -> str:
            return value.upper() if value else ""

        keys = [
            (
                safe_upper(entry.dependent_first_name),
                safe_upper(entry.dependent_last_name),
                entry.dependent_date_of_birth,
            ),
            (
                safe_upper(entry.first_name),
                safe_upper(entry.last_name),
                entry.date_of_birth,
            ),
        ]
        for key in keys:
            if wallet := lookup.get(key):
                return wallet
        log.info("No wallet found for LedgerEntry", ledger_balance_id=entry.balance_id)
        return None

    @staticmethod
    @observability.wrap
    def create_members_from_lookup(lookup: dict) -> list:
        """
        Helper function that creates and returns a list of member dicts from the lookup dictionary
        """
        members = []

        for (first_name, last_name, dob) in lookup.keys():
            members.append(
                {"first_name": first_name, "last_name": last_name, "date_of_birth": dob}
            )

        return members

    def format_request_body(
        self,
        lookup: dict,
        reimbursement_organization_settings_id: int,
        file_id: Optional[str] = None,
        exclude_adjusted: bool = True,
        limit: int = 1000,
        sort_field: str = "created_at",
        category_filter: Optional[str] = None,
    ) -> dict:
        """
        Helper function that builds the request body for the WHS search ledgers endpoint
        """
        members = self.create_members_from_lookup(lookup)
        request_file_id = [file_id] if file_id else None
        request_body = {
            "sort": {
                "direction": "DESC",
                "field": sort_field,
            },
            "limit": limit,
            "exclude_adjusted": exclude_adjusted,
            "members": members,
        }
        if category_filter:
            request_body["category"] = category_filter
        if request_file_id:
            request_body["file_ids"] = request_file_id
        else:
            request_body["reimbursement_organization_settings_id"] = str(
                reimbursement_organization_settings_id
            )
            request_body["exclude_adjusted"] = False
        return request_body

    def build_reimbursement_request_params(
        self, entry: LedgerEntry, file_id: Optional[str]
    ) -> dict:
        """Helper function to create a historical spend reimbursement request"""
        utc_now = datetime.datetime.now(pytz.UTC)
        # Convert to Eastern Time (handles both EST and EDT automatically)
        eastern = pytz.timezone("America/New_York")
        eastern_time = utc_now.astimezone(eastern)
        expense_type = ReimbursementRequestExpenseTypes(entry.category.upper())
        amount = entry.calculated_spend if file_id else entry.historical_spend
        credits = entry.calculated_cycles if file_id else entry.historical_cycles_used
        return {
            "amount": amount,
            "transaction_amount": amount,
            "usd_amount": amount,
            "service_provider": "Balance adjustment",
            "label": HISTORICAL_SPEND_LABEL,
            "description": "We’ve updated your balance to reflect your benefits usage prior to joining Maven."
            " This adjustment ensures your remaining balance accurately represents the benefits"
            " you can use moving forward",
            "state": ReimbursementRequestState.REIMBURSED,
            "service_start_date": eastern_time,
            "service_end_date": eastern_time,
            "reimbursement_type": ReimbursementRequestType.MANUAL,
            "person_receiving_service": self.get_full_name(entry=entry),
            "cost_credit": credits,
            "expense_type": expense_type,
        }

    @staticmethod
    def normalize_string(s: str) -> Optional[str]:
        """Helper function to normalize strings for comparison."""
        return s.strip().upper() if s else None

    def get_full_name(self, entry: LedgerEntry) -> str:
        if entry.dependent_first_name and entry.dependent_last_name:
            return f"{self.normalize_string(entry.dependent_first_name)} {self.normalize_string(entry.dependent_last_name)}"
        else:
            return f"{self.normalize_string(entry.first_name)} {self.normalize_string(entry.last_name)}"

    @staticmethod
    def get_reimbursement_credits_from_category(
        reimbursement_request_category_id: int, wallet: ReimbursementWallet
    ) -> ReimbursementCycleCredits:
        reimbursement_credits = (
            ReimbursementCycleCredits.query.join(
                ReimbursementOrgSettingCategoryAssociation,
                ReimbursementOrgSettingCategoryAssociation.id
                == ReimbursementCycleCredits.reimbursement_organization_settings_allowed_category_id,
            )
            .filter(
                ReimbursementCycleCredits.reimbursement_wallet_id == wallet.id,
                ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category_id
                == reimbursement_request_category_id,
            )
            .first()
        )
        return reimbursement_credits

    @observability.wrap
    def determine_category_eligibility(
        self,
        wallet: ReimbursementWallet,
        category_association: ReimbursementOrgSettingCategoryAssociation,
        transition_start_date: datetime.date,
        transition_end_date: datetime.date,
        rule_name: str,
    ) -> tuple:
        """
        Determines if a wallet is eligible for a specific reimbursement category.
        Returns a tuple containing a boolean indicating eligibility and an instance of
                   `HistoricalSpendRuleResults`.
        """
        log.info(
            f"{rule_name}: Starting category rule eligibility check",
            wallet_id=str(wallet.id),
            category_association_id=str(category_association.id),
            rule_name=rule_name,
        )
        wallet_data_lookup = self.get_wallet_eligibility_data(wallets=[wallet])
        if not wallet_data_lookup:
            log.info(
                f"{rule_name}: Eligibility verification record not found.",
                wallet_id=str(wallet.id),
            )
            return False, HistoricalSpendRuleResults.MAVEN_ERROR
        request_body = self.format_request_body(
            lookup=wallet_data_lookup,
            file_id=None,
            reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
            exclude_adjusted=False,
            sort_field="most_recent_auth_date",
            limit=1,
            category_filter=ReimbursementRequestExpenseTypes.FERTILITY.value,
        )
        try:
            wallet_ledger_entries = self.get_ledger_entries(
                request_body=request_body, file_id=None
            )
            log.info(
                f" {rule_name}: Historic Rule ledger entries found.",
                count=len(wallet_ledger_entries),
                wallet_id=str(wallet.id),
            )
        except Exception as e:
            log.exception(
                f"{rule_name}: WHS search endpoint error.",
                wallet_id=str(wallet.id),
                error=str(e),
            )
            return False, HistoricalSpendRuleResults.MAVEN_ERROR

        if not wallet_ledger_entries:
            log.info(
                f"{rule_name}: No historical spend found.", wallet_id=str(wallet.id)
            )
            return True, HistoricalSpendRuleResults.ELIGIBLE

        log.info(
            f" {rule_name}: Historic rule category info.",
            category_association_id=str(category_association.id),
            wallet_id=str(wallet.id),
        )
        return self._evaluate_auth_date(
            wallet=wallet,
            entry=wallet_ledger_entries[0],
            transition_start_date=transition_start_date,
            transition_end_date=transition_end_date,
            rule_name=rule_name,
        )

    @staticmethod
    @observability.wrap
    def _evaluate_auth_date(
        wallet: ReimbursementWallet,
        entry: LedgerEntry,
        transition_start_date: datetime.date,
        transition_end_date: datetime.date,
        rule_name: str,
    ) -> tuple[bool, str]:
        """
        Evaluates the authorization date for a ledger entry.
        """
        is_today_before_transition_end_date = (
            True if datetime.date.today() < transition_end_date else False
        )
        most_recent_auth_date = (
            entry.most_recent_auth_date if entry.most_recent_auth_date else None
        )
        log.info(
            f"{rule_name}: Historical spend authorization data",
            wallet_id=str(wallet.id),
            auth_date=most_recent_auth_date,
        )
        if not most_recent_auth_date:
            log.error(
                f"{rule_name}: Missing most recent auth date from user.",
                wallet_id=str(wallet.id),
                whs_balance_id=entry.balance_id,
            )
            return False, HistoricalSpendRuleResults.MAVEN_ERROR

        if most_recent_auth_date < transition_start_date:
            log.info(
                "Historical spend auth date pre transition start date",
                wallet_id=str(wallet.id),
                auth_date=most_recent_auth_date,
            )
            return True, HistoricalSpendRuleResults.ELIGIBLE
        if (
            transition_start_date <= most_recent_auth_date < transition_end_date
            and is_today_before_transition_end_date
        ):
            log.info(
                f"{rule_name}: Historical spend within transition of care date range.",
                wallet_id=str(wallet.id),
                auth_date=most_recent_auth_date,
                before_auth_date=transition_start_date,
            )
            return False, HistoricalSpendRuleResults.AWAITING_TRANSITION
        else:
            log.info(
                f"{rule_name}: Historical spend date passed transition date.",
                wallet_id=str(wallet.id),
                auth_date=most_recent_auth_date,
                before_auth_date=transition_start_date,
            )
            return True, HistoricalSpendRuleResults.ELIGIBLE


@job("priority", service_ns="wallet-historical_spend", team_ns="benefits_experience")
def process_historical_spend_wallets_job(
    file_id: str, reimbursement_organization_settings_id: int, wallet_ids: List
) -> None:
    log.info(
        "Enqueuing task to process wallet historical spend records.",
        file_id=file_id,
        reimbursement_organization_settings_id=str(
            reimbursement_organization_settings_id
        ),
        wallet_count=len(wallet_ids),
    )
    try:
        historical_spend_service = WalletHistoricalSpendService(
            whs_base_url=INTERNAL_TRUST_WHS_URL
        )
        historical_spend_service.process_historical_spend_wallets(
            file_id=file_id,
            reimbursement_organization_settings_id=reimbursement_organization_settings_id,
            wallet_ids=wallet_ids,
        )
    except Exception:
        log.exception(
            "Unable to process batched wallet historical spend records.",
            file_id=file_id,
            reimbursement_organization_settings_id=str(
                reimbursement_organization_settings_id
            ),
            reason=format_exc(),
        )


@observability.wrap
def get_historical_spend_wallet_ids(reimbursement_org_settings_id: int) -> List:
    """Returns a list of wallet ids"""
    wallet_id_tups = (
        db.session.query(ReimbursementWallet.id)
        .filter(
            ReimbursementWallet.reimbursement_organization_settings_id
            == reimbursement_org_settings_id,
            ReimbursementWallet.state.in_([WalletState.QUALIFIED, WalletState.RUNOUT]),
        )
        .all()
    )
    return [wallet_id_tup[0] for wallet_id_tup in wallet_id_tups]
