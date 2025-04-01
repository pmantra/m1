from __future__ import annotations

import datetime
from typing import Any

import stripe
from stripe.stripe_object import StripeObject

from authn.models.user import User
from common import stats
from common.services.stripe_constants import (
    PAYMENTS_STRIPE_API_KEY,
    REIMBURSEMENTS_STRIPE_API_KEY,
    STRIPE_ACTION_TYPES,
)
from storage.connection import db
from utils.cache_memo import memodict
from utils.log import logger
from utils.payments import convert_cents_to_dollars, convert_dollars_to_cents

log = logger(__name__)


class StripeClient:
    """
    Abstraction layer between Maven code and the stripe client, allowing adjustments to how we make stripe calls
    without changes to business logic. Notably, the stripe client can be configured with multiple keys, allowing us
    more than one active Stripe account, but it cannot be configured with multiple api versions.
    """

    def __init__(self, api_key):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # all stripe calls from this client will be configured with key and version in the call itself
        self.api_key = api_key

    @staticmethod
    def audit(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        action_type: str,
        *,
        user_id: int | None = None,
        response_json: dict[str, Any] | None = None,
        error_json: dict[str, Any] | None = None,
    ):
        modified_fields = [*(response_json or ())]
        audit_log_info = {
            "user_id": user_id,
            "action_type": action_type,
            "action_target_type": "stripe",
            "modified_fields": modified_fields,
        }
        if error_json:
            audit_log_info["error_response"] = error_json  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, Any]", target has type "Union[List[Any], str, int, None]")
        log.info("audit_log_events", audit_log_info=audit_log_info)


class CannotEditBusinessTypeException(Exception):
    pass


class NoStripeAccountFoundException(Exception):
    pass


class StripeConnectClient(StripeClient):
    """
    Handle Stripe Connect accounts. We use Connect for paying providers and for reimbursing wallet users.
    """

    def create_connect_account(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        account_legal_entity,
        connect_account_type="custom",
        country="US",
        source_ip=None,
        metadata=None,
        user_id=None,
    ):
        product_description = (
            "Maven Wallet Reimbursement Client"
            if self.api_key is REIMBURSEMENTS_STRIPE_API_KEY
            else "Maven Clinic Practitioner"
        )

        if "type" not in account_legal_entity or account_legal_entity["type"] not in (
            "individual",
            "company",
        ):
            log.warning("Stripe account create Error: missing legal entity type")
            self.audit(
                STRIPE_ACTION_TYPES.connect_account_creation_failed, user_id=user_id
            )
            return None
        else:
            account_type = account_legal_entity["type"]
            account_legal_entity.pop("type")
            if type == "company" and "dob" in account_legal_entity:
                account_legal_entity.pop("dob")
        try:
            account = stripe.Account.create(
                type=connect_account_type,
                country=country,
                requested_capabilities=["transfers"],
                tos_acceptance={
                    "date": int(datetime.datetime.utcnow().timestamp()),
                    "ip": source_ip,
                    "user_agent": None,
                },
                business_type=account_type,
                business_profile={"product_description": product_description},
                individual=(
                    account_legal_entity if account_type == "individual" else None
                ),
                company=account_legal_entity if account_type == "company" else None,
                api_key=self.api_key,
                metadata=metadata,
            )
        except stripe.error.StripeError as e:
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.connect_account_creation_failed,
                user_id=user_id,
            )
            self.audit(
                STRIPE_ACTION_TYPES.connect_account_creation_failed,
                user_id=user_id,
                error_json=e.json_body,
            )
            return None
        except ValueError as e:
            log.warning(
                "Stripe account create ValueError",
                user_id=user_id,
                e=e,
            )
            self.audit(
                STRIPE_ACTION_TYPES.connect_account_creation_failed, user_id=user_id
            )
            return None
        else:
            self.audit(
                STRIPE_ACTION_TYPES.connect_account_creation,
                user_id=user_id,
                response_json=account,
            )
            return account

    def get_connect_account_for_user(self, user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if user is None:
            log.error("User not found")
            return None

        profile = user.profile

        if profile is None:
            log.error("Profile not found")
            return None

        try:
            account_id = profile.stripe_account_id
            if account_id is None:
                raise AttributeError(
                    f"Missing stripe_account_id for user {user.id}'s {user.role_name} profile"
                )
            account = stripe.Account.retrieve(account_id, api_key=self.api_key)
        except AttributeError:
            self.audit(STRIPE_ACTION_TYPES.get_connect_account_failed, user_id=user.id)
            log.error("Failed to retrieve stripe_account_id for user", user_id=user.id)
            return None
        except stripe.error.StripeError as e:
            self.audit(
                STRIPE_ACTION_TYPES.get_connect_account_failed,
                user_id=user.id,
                error_json=e.json_body,
            )
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.get_connect_account_failed,
                user_id=user.id,
            )
            return None
        self.audit(STRIPE_ACTION_TYPES.get_connect_account, user_id=user.id)
        return account

    def edit_connect_account_for_user(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, user, account_legal_entity, accept_tos_ip=None
    ):
        account = self.get_connect_account_for_user(user)
        if not account:
            log.warning("No stripe connect account found for user", user_id=user.id)
            raise NoStripeAccountFoundException()
        try:
            legal_entity_type = account_legal_entity.pop("type")
            account_type = account.get("business_type")
            if legal_entity_type != account_type:
                log.warning(
                    "Attempting to change Stripe connect account type for user",
                    user_id=user.id,
                    account_type=account_type,
                    new_requested_type=legal_entity_type,
                )
                # You cannot change `business_type` via API once an account has been activated.
                # Therefore in this case, we throw an error, catch it on the way up, and create a new account.
                self.audit(
                    STRIPE_ACTION_TYPES.recipient_edit_account_replaced, user_id=user.id
                )
                raise CannotEditBusinessTypeException()

            updated_account = stripe.Account.modify(
                account.id,
                individual=(
                    account_legal_entity if legal_entity_type == "individual" else None
                ),
                company=(
                    account_legal_entity if legal_entity_type == "company" else None
                ),
                tos_acceptance=(
                    {
                        "date": int(datetime.datetime.utcnow().timestamp()),
                        "ip": accept_tos_ip,
                        "user_agent": None,
                    }
                    if accept_tos_ip is not None
                    else None
                ),
                api_key=self.api_key,
            )
            log.info("Stripe account updated for user", user_id=user.id)
            self.audit(STRIPE_ACTION_TYPES.recipient_edit, response_json=account)
            return updated_account
        except stripe.error.StripeError as e:
            log.warning(
                "Problem editing account for user",
                user_id=user.id,
                stripe_error_message=e.json_body.get("error", {}).get("message"),
            )
            self.audit(
                STRIPE_ACTION_TYPES.recipient_edit_failed, error_json=e.json_body
            )
            return None
        except ValueError as e:
            log.warning(
                "Problem editing account for user", user_id=user.id, value_error=e
            )
            self.audit(STRIPE_ACTION_TYPES.recipient_edit_failed, user_id=user.id)
            return None

    def accept_terms_of_service(self, user, ip_address):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # https://stripe.com/docs/connect/updating-accounts#indicating-acceptance
        account = self.get_connect_account_for_user(user)
        if not account:
            log.debug("No stripe connect account found for user", user_id=user.id)
            return None
        try:
            # Required date format is unix timestamp
            updated_account = stripe.Account.modify(
                account.id,
                tos_acceptance={
                    "date": int(datetime.datetime.utcnow().timestamp()),
                    "ip": ip_address,
                },
                api_key=self.api_key,
            )
            self.audit(
                STRIPE_ACTION_TYPES.recipient_edit,
                user_id=user.id,
                response_json=updated_account,
            )
            return updated_account
        except stripe.error.StripeError as e:
            log.warning(
                "Problem accepting Stripe terms of service for user",
                user_id=user.id,
                stripe_error_message=e.json_body.get("error", {}).get("message"),
            )
            self.audit(
                STRIPE_ACTION_TYPES.recipient_sign_terms_failed,
                user_id=user.id,
                error_json=e.json_body,
            )
            return None
        except Exception as e:
            log.warning(
                "Generic problem accepting Stripe terms of service for user",
                user_id=user.id,
                value_error=e,
            )
            self.audit(STRIPE_ACTION_TYPES.recipient_edit_failed, user_id=user.id)
            return None

    def set_bank_account_for_user(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, user, bank_account_token, overwrite_allowed=False
    ):
        account = self.get_connect_account_for_user(user)
        if not account:
            log.debug("No stripe connect account found for user", user_id=user.id)
            return None
        if not bank_account_token:
            log.warning(
                "No bank_account_token in set_bank_account!",
                user_id=user.id,
                client=self,
            )
            return None
        try:
            try:
                has_external_account = (
                    account.external_accounts
                    and len(account.external_accounts.data) > 0
                )
            except AttributeError:
                log.warning(
                    "No external_accounts data on this stripe account. Have you created recipient information?",
                    id=account.id,
                    type=account.type,
                    user_id=user.id,
                )
                return None

            if has_external_account and overwrite_allowed is True:
                log.info(
                    "User already has a bank account. Overwriting!", user_id=user.id
                )
            elif has_external_account:
                log.info(
                    "User already has a bank account. No overwriting allowed!",
                    user_id=user.id,
                )
                return None
            account.external_account = bank_account_token
            account.save()
            self.audit(STRIPE_ACTION_TYPES.bank_account_set, user_id=user.id)
            return account
        except stripe.error.StripeError as e:
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.bank_account_set_failure,
                user_id=user.id,
            )
            self.audit(
                STRIPE_ACTION_TYPES.bank_account_set_failure,
                user_id=user.id,
                error_json=e.json_body,
            )

    def get_bank_account_for_user(self, user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        account = self.get_connect_account_for_user(user)
        if not account:
            log.debug("No stripe connect account found for user", user_id=user.id)
            return None
        try:
            ext_acct = account.external_accounts
            data = ext_acct.data
            if data and len(data) == 1:
                return data[0]
            elif data:
                log.info(
                    "User has >1 external_accounts, returning the first",
                    user_id=user.id,
                )
                return data[0]
        except AttributeError:
            log.warning(
                "No external_accounts attribute on this stripe account. Have you created recipient information?",
                id=account.id,
                type=account.type,
                user_id=user.id,
            )
            return None
        except stripe.error.StripeError:
            log.info(
                "Error getting bank account for user",
                user_id=user.id,
                profiles=user.user_types,
            )
            return None

    @classmethod
    def unset_bank_account_for_user(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Not to be confused with deleting the Stripe Connect bank account for a user. This removes the user's
        stripe token from our code. It does not remove their data from Stripe. In the case that they add a new
        account, this will actually create a new Stripe Connect Account as well as a new bank account.
        """
        profile = user.profile
        if profile is None:
            return False

        if profile.stripe_account_id is None:
            return False
        else:
            profile.stripe_account_id = None
            db.session.add(profile)
            db.session.commit()
            return True

    def get_connect_account_balance_for_user(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        account = self.get_connect_account_for_user(user)
        if not account:
            log.debug("No stripe connect account found for user", user_id=user.id)
            return None
        try:
            balance = stripe.Balance.retrieve(
                stripe_account=account.id, api_key=self.api_key
            )
            self.audit(STRIPE_ACTION_TYPES.get_connect_account_balance, user_id=user.id)
            return balance
        except stripe.error.StripeError as e:
            self.audit(
                STRIPE_ACTION_TYPES.get_connect_account_balance_failed,
                user_id=user.id,
                error_json=e.json_body,
            )
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.get_connect_account_balance_failed,
                user_id=user.id,
            )
            return None

    def create_transfer_to_connect_account_for_user(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, user, amount, metadata=None, description=None
    ):
        """Moves money from Maven's stripe account to the user's Stripe Connect account"""
        if metadata is None:
            metadata = {}
        if not description:
            description = f"Payment of {amount} from Maven"
        bank_account = self.get_bank_account_for_user(user)
        source_type = self.get_source_type_for_reimbursement_transfer(amount)
        if not bank_account:
            log.debug(
                "Attempted to make a stripe transfer to an unknown account",
                user_id=user.id,
            )
            return None
        try:
            log.debug(
                "Started stripe transfer",
                amount_in_cents=amount,
                bank_account=bank_account.account,
                user_id=user.id,
                source_type=source_type,
            )
            transfer = stripe.Transfer.create(
                amount=amount,
                currency="usd",
                destination=bank_account.account,
                source_type=source_type,
                description=description,
                metadata=metadata,
                api_key=self.api_key,
            )
            self.audit(
                STRIPE_ACTION_TYPES.transfer_creation,
                user_id=user.id,
                response_json=transfer,
            )
            return transfer
        except stripe.error.StripeError as e:
            self.audit(
                STRIPE_ACTION_TYPES.transfer_creation_failure,
                user_id=user.id,
                error_json=e.json_body,
            )
            log.error(
                "Error while trying to generate a stripe transfer",
                error=str(e),
                user_id=user.id,
                metadata=metadata,
                amount=amount,
            )
            return None

    def create_payout_to_connect_account_for_user(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, user, amount, metadata=None, description=None
    ):
        """Moves money from the user's Stripe Connect account to their bank account. The description here should
        show on the bank statement."""
        if metadata is None:
            metadata = {}
        if not description:
            description = f"Payment of {amount} from Maven"
        bank_account = self.get_bank_account_for_user(user)
        source_type = self.get_source_type_for_reimbursement_payout(
            bank_account.account, amount
        )
        if not bank_account:
            log.debug(
                "Attempted to make a stripe payout to an unknown account",
                user_id=user.id,
            )
            return None
        try:
            log.debug(
                "Started stripe payout",
                amount_in_cents=amount,
                user_id=user.id,
                bank_account=bank_account.account,
            )
            payout = stripe.Payout.create(
                amount=amount,
                currency="usd",
                stripe_account=bank_account.account,
                description=description,
                destination=bank_account.id,
                source_type=source_type,
                metadata=metadata,
                api_key=self.api_key,
            )
            self.audit(
                STRIPE_ACTION_TYPES.payout_creation,
                user_id=user.id,
                response_json=payout,
            )
            return payout
        except stripe.error.StripeError as e:
            self.audit(STRIPE_ACTION_TYPES.payout_creation_failure, user_id=user.id)
            log.error(
                "Error while trying to generate a stripe payout",
                error=str(e),
                user_id=user.id,
                metadata=metadata,
                amount=amount,
            )
            return None

    def get_source_type_for_reimbursement_transfer(self, reimbursement_amount):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        balance = stripe.Balance.retrieve(api_key=self.api_key)
        by_source_type = balance.get("available")[0].get("source_types")
        bank_account_balance = by_source_type.get("bank_account")
        # Default to bank_account, but use card balance if bank_account doesn't
        # have enough
        if bank_account_balance >= reimbursement_amount:
            return "bank_account"
        else:
            return "card"

    def get_source_type_for_reimbursement_payout(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, account_id, reimbursement_amount
    ):
        # Get customer's account balance to determine which source to pay out from
        balance = stripe.Balance.retrieve(
            api_key=self.api_key, stripe_account=account_id
        )
        by_source_type = balance.get("available")[0].get("source_types")
        bank_account_balance = by_source_type.get("bank_account")
        # Default to bank_account, but use card balance if bank_account doesn't
        # have enough
        if bank_account_balance >= reimbursement_amount:
            return "bank_account"
        else:
            return "card"


class StripeCustomerClient(StripeClient):
    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(*args, **kwargs)
        self._stripe_customer_cache = memodict(self._retrieve_customer)

    @property
    def stripe_customer_cache(self) -> memodict:
        return self._stripe_customer_cache

    def _retrieve_customer(self, stripe_customer_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        customer = stripe.Customer.retrieve(stripe_customer_id, api_key=self.api_key)
        return customer

    def create_customer_for_user(self, user, description=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not user.is_member:
            log.warning(
                "Can only create stripe customer records for members", user_id=user.id
            )
            return
        customer = stripe.Customer.create(
            description=description or user.full_name, api_key=self.api_key
        )
        self.stripe_customer_cache[customer.id] = customer
        self.audit(
            STRIPE_ACTION_TYPES.customer_creation,
            user_id=user.id,
            response_json=customer,
        )
        return customer

    def create_customer_by_description(self, description):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        customer = stripe.Customer.create(description=description, api_key=self.api_key)
        self.stripe_customer_cache[customer.id] = customer
        self.audit(STRIPE_ACTION_TYPES.customer_creation, response_json=customer)
        return customer

    def get_customer_by_stripe_id(self, stripe_customer_id, user=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_id = user.id if user else None
        try:
            customer = self.stripe_customer_cache[stripe_customer_id]
        except stripe.error.InvalidRequestError as e:
            self.audit(
                STRIPE_ACTION_TYPES.get_customer_failed,
                user_id=user_id,
                error_json=e.json_body,
            )
            log.warning(
                "Could not get stripe customer for user",
                user_id=user_id,
                stripe_error_message=e.json_body.get("error", {}).get("message"),
            )
            return
        except stripe.error.StripeError as e:
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.get_customer_failed,
                user_id=user.id,
            )
            self.audit(
                action_type=STRIPE_ACTION_TYPES.get_customer_failed,
                user_id=user_id,
                error_json=e.json_body,
            )
            return
        self.audit(STRIPE_ACTION_TYPES.get_customer, user_id=user_id)
        return customer

    def get_customer_for_user(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        profile = user.profile
        try:
            stripe_customer_id = profile.stripe_customer_id
            return self.get_customer_by_stripe_id(
                stripe_customer_id=stripe_customer_id, user=user
            )
        except AttributeError:
            self.audit(STRIPE_ACTION_TYPES.get_connect_account_failed, user_id=user.id)
            log.warning(
                "Failed to retrieve stripe_account_id for user", user_id=user.id
            )
            return

    def get_customer(self, user=None, stripe_customer_id=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if user:
            log.debug("Attempting to retrieve customer for user", user_id=user.id)
            return self.get_customer_for_user(user=user)
        elif stripe_customer_id:
            log.debug(
                "Attempting to retrieve customer by stripe id", id=stripe_customer_id
            )
            return self.get_customer_by_stripe_id(
                stripe_customer_id=stripe_customer_id, user=user
            )
        else:
            log.debug("Attempted to retrieve customer without user or stripe id")
            return None

    def delete_customer(self, user=None, stripe_customer_id=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        customer = self.get_customer(user=user, stripe_customer_id=stripe_customer_id)
        if not customer:
            log.warning("Failed to delete stripe customer for user", user_id=user.id)
            return
        if hasattr(customer, "deleted") and customer.deleted:
            log.warning(
                "Attempted to delete stripe customer for user, but the customer was already deleted",
                user_id=user.id,
            )
            return
        customer.delete()
        user_id = user.id if user else None
        # clear cache after a change to the customer
        del self.stripe_customer_cache[customer.stripe_id]
        self.audit(STRIPE_ACTION_TYPES.customer_deletion, user_id=user_id)

    def add_card(self, token, user=None, stripe_customer_id=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        customer = self.get_customer(user=user, stripe_customer_id=stripe_customer_id)
        user_id = user.id if user else None
        if not customer:
            log.warning(
                "Failed to add card to stripe customer for user", user_id=user.id
            )
            return
        try:
            card = stripe.Customer.create_source(
                customer.id, source=token, api_key=self.api_key
            )
            self.audit(
                STRIPE_ACTION_TYPES.card_creation, user_id=user_id, response_json=card
            )
            # clear cache after a change to the customer
            del self.stripe_customer_cache[customer.stripe_id]
            return card
        except stripe.error.StripeError as e:
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.card_creation_failed,
                user_id=user_id,
            )
            self.audit(
                action_type=STRIPE_ACTION_TYPES.card_creation_failed,
                user_id=user_id,
                error_json=e.json_body,
            )
            raise

    def list_cards(self, user: User | None = None, stripe_customer_id=None) -> list:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        # TODO: we must guard the possible None user before accessing user.id
        # update the type hint to user: User and add a guard for none
        log.debug(
            "listing cards for user", user_id=user.id  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
        )  # api/common/services/stripe.py:683: error: Item "None" of "Optional[User]" has no attribute "id"  [union-attr]
        customer = self.get_customer(user=user, stripe_customer_id=stripe_customer_id)
        if not customer:

            log.warning(
                "Failed to retrieve customer cards for user", user_id=user.id  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            )  # api/common/services/stripe.py:686: error: Item "None" of "Optional[User]" has no attribute "id"  [union-attr]
            return []
        self.audit(STRIPE_ACTION_TYPES.list_cards)
        return (
            customer and hasattr(customer, "sources") and customer.sources["data"]
        ) or []

    def delete_card(self, card_id, user=None, stripe_customer_id=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        customer = self.get_customer(user=user, stripe_customer_id=stripe_customer_id)
        user_id = user.id if user else None
        if not customer:
            log.warning(
                "Failed to delete customer card for user",
                user_id=user_id,
                stripe_customer_id=stripe_customer_id,
            )
            return
        try:
            card = customer.sources.retrieve(card_id)
        except stripe.error.StripeError as e:
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.card_deletion_failed,
                user_id=user.id,
            )
            self.audit(
                STRIPE_ACTION_TYPES.card_deletion_failed,
                user_id=user_id,
                error_json=e.json_body,
            )
            return

        res = card.delete()
        if res.deleted and (res.id == card_id):
            log.info(
                "Deleted card from Stripe", stripe_card_id=card_id, user_id=user.id
            )
            self.audit(
                STRIPE_ACTION_TYPES.card_deletion, user_id=user_id, response_json=res
            )
            # clear cache after a change to the customer
            del self.stripe_customer_cache[customer.stripe_id]
            return card_id
        else:
            log.info(
                "Could not delete card for customer",
                card=card,
                customer=customer,
                user_id=user.id,
            )

    def create_charge(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        amount_in_dollars,
        user=None,
        stripe_customer_id=None,
        capture=False,
        stripe_card_id=None,
    ):
        customer = self.get_customer(user=user, stripe_customer_id=stripe_customer_id)
        user_id = user.id if user else None
        if not customer:
            log.warning(
                "Failed to retrieve customer card for user",
                user_id=user.id,
                stripe_customer_id=stripe_customer_id,
            )
            return
        amount_in_cents = convert_dollars_to_cents(amount_in_dollars)
        charge = {
            "amount": amount_in_cents,
            "currency": "USD",
            "customer": customer,
            "capture": capture,
            "description": "Maven Clinic Billing",
        }
        if stripe_card_id:
            charge["card"] = stripe_card_id

        try:
            charge = stripe.Charge.create(**charge, api_key=self.api_key)
            self.audit(
                STRIPE_ACTION_TYPES.charge_creation,
                user_id=user_id,
                response_json=charge,
            )
            log.debug(
                "Successfully created stripe charge",
                charge=charge.id,
                user_id=user_id,
            )
            return charge
        except stripe.error.CardError as e:
            log.info(
                "Stripe charge declined",
                user_id=user.id,
                stripe_customer_id=stripe_customer_id,
                error_message=e.json_body.get("error", {}).get("message"),
            )
            self.audit(
                STRIPE_ACTION_TYPES.charge_creation_failed,
                user_id=user_id,
                error_json=e.json_body,
            )
            raise
        except stripe.error.StripeError as e:
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.charge_creation_failed,
                user_id=user.id,
            )
            self.audit(
                STRIPE_ACTION_TYPES.charge_creation_failed,
                user_id=user_id,
                error_json=e.json_body,
            )
            raise

    def capture_charge(self, user, stripe_charge_id, amount_in_dollars=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            charge = stripe.Charge.retrieve(stripe_charge_id, api_key=self.api_key)
        except stripe.error.StripeError as e:
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.charge_retrieval_failed,
                user_id=user.id,
            )
            self.audit(
                STRIPE_ACTION_TYPES.charge_retrieval_failed,
                user_id=user.id,
                error_json=e.json_body,
            )
            return
        amount_in_cents = 0
        try:
            amount_in_cents = convert_dollars_to_cents(amount_in_dollars)
            if amount_in_cents and amount_in_cents > charge["amount"]:
                log.warning(
                    "Cannot capture more than authorized!",
                    requested_amount=amount_in_cents,
                    authorized_amount=charge["amount"],
                )
                log.debug(f"Setting amount to {charge['amount']}")
                amount_in_cents = charge["amount"]
            elif amount_in_cents is None:
                amount_in_cents = charge["amount"]
            log.debug(f"Capturing {amount_in_cents} from {charge.id}")
            charge = charge.capture(amount=amount_in_cents)
            log.debug(f"Captured {amount_in_cents} from {charge.id}")
            self.audit(
                STRIPE_ACTION_TYPES.charge_capture,
                user_id=user.id,
                response_json=charge,
            )
            return charge
        except stripe.error.StripeError as e:
            if e.code == "charge_expired_for_capture":
                log.warning(
                    "Original charge expired, creating new charge",
                    charge_id=charge.id,
                    user_id=user.id,
                )
                return self.create_charge(
                    convert_cents_to_dollars(amount_in_cents), user, capture=True
                )
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.charge_capture_failed,
                user_id=user.id,
            )
            self.audit(
                STRIPE_ACTION_TYPES.charge_capture_failed,
                user_id=user.id,
                error_json=e.json_body,
            )

    def refund_charge(self, stripe_charge_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            charge = stripe.Charge.retrieve(stripe_charge_id, api_key=self.api_key)
        except stripe.error.StripeError as e:
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.charge_retrieval_failed,
            )
            self.audit(
                STRIPE_ACTION_TYPES.charge_retrieval_failed, error_json=e.json_body
            )
            return
        try:
            refund = charge.refunds.create()
        except stripe.error.StripeError as e:
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.refund_creation_failed,
            )
            self.audit(
                STRIPE_ACTION_TYPES.refund_creation_failed, error_json=e.json_body
            )
        else:
            log.debug(f"Refunded {charge.id}")
            self.audit(STRIPE_ACTION_TYPES.refund_creation, response_json=refund)
            return refund


class StripeTransferClient(StripeClient):
    TRANSFER_METADATA_USER_ID_FIELD = "user_id"

    def start_transfer(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        stripe_account_id,
        amount_in_dollars,
        user_id,
        invoice_id,
        description=None,
    ):
        if not description:
            description = f"Payment of ${amount_in_dollars} from Maven"
        amount_in_cents = convert_dollars_to_cents(amount_in_dollars)
        try:
            transfer = stripe.Transfer.create(
                amount=amount_in_cents,
                currency="usd",
                destination=stripe_account_id,
                description=description,
                api_key=self.api_key,
                metadata={
                    StripeTransferClient.TRANSFER_METADATA_USER_ID_FIELD: user_id
                },
                idempotency_key=str(invoice_id),
            )
            if not transfer:
                stats.increment(
                    metric_name="api.common.services.stripe.start_transfer",
                    pod_name=stats.PodNames.PAYMENTS_POD,
                    tags=["error:true", "error_cause:no_transfer_object"],
                )
                log.warning(
                    "No Stripe transfer object created",
                    action_type=STRIPE_ACTION_TYPES.transfer_creation_failure,
                    user_id=user_id,
                )
            log.info(
                f"Started transfer: {amount_in_cents} cents to {stripe_account_id}"
            )
            self.audit(
                STRIPE_ACTION_TYPES.transfer_creation,
                user_id=user_id,
                response_json=transfer,
            )
            return transfer
        except stripe.error.StripeError as e:
            stats.increment(
                metric_name="api.common.services.stripe.start_transfer",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:generic_stripe_error"],
            )
            log.warning(
                "Stripe Error",
                e=e,
                action_type=STRIPE_ACTION_TYPES.transfer_creation_failure,
                user_id=user_id,
            )
            self.audit(
                STRIPE_ACTION_TYPES.transfer_creation_failure,
                user_id=user_id,
                error_json=e.json_body,
            )
        except Exception as e:
            stats.increment(
                metric_name="api.common.services.stripe.start_transfer",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:unexpected_error"],
            )
            log.warning(
                "Exception while transferring invoice to Stripe",
                e=e,
                action_type=STRIPE_ACTION_TYPES.transfer_creation_failure,
                user_id=user_id,
            )
            self.audit(
                STRIPE_ACTION_TYPES.transfer_creation_failure,
                user_id=user_id,
            )


class StripeReimbursementHandler:
    """Code related to the process of reimbursing money to a user after the money has been transferred to Maven from
    the reimbursement organization. This handles the admin dashboard function and the webhook handler, but not the
    queue that the webhook passes valid events off to-- that code is in tasks/payments
    """

    PAYOUT_METADATA_ID_FIELD = "reimbursement_request_id"
    PAYOUT_METADATA_USER_ID_FIELD = "user_id"

    @classmethod
    def create_reimbursement_payout(cls, user, reimbursement_request):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Handles admin's Payment Dashboard function to reimburse money to a user,
        including the correct metadata for stripe, and marking the dates of transfer and payout in the maven record.
        """
        if user not in reimbursement_request.wallet.all_active_users:
            raise ValueError(
                "Request and User not compatible. Cannot reimburse this request for this user"
            )
        stripe_client = StripeConnectClient(api_key=REIMBURSEMENTS_STRIPE_API_KEY)

        if (
            not reimbursement_request.reimbursement_payout_date
            and not reimbursement_request.reimbursement_transfer_date
        ):
            transfer = stripe_client.create_transfer_to_connect_account_for_user(
                user=user,
                amount=reimbursement_request.amount,
                metadata={
                    StripeReimbursementHandler.PAYOUT_METADATA_ID_FIELD: reimbursement_request.id,
                    StripeReimbursementHandler.PAYOUT_METADATA_USER_ID_FIELD: user.id,
                },
            )
            if not transfer:
                log.error(
                    "Failed to transfer money to the stripe account",
                    user_id=user.id,
                    reimbursement_request_id=reimbursement_request.id,
                )
                raise ValueError(
                    "Error while transfering money for a Stripe reimbursement payout"
                    f" for user {user.id} and reimbursement request {reimbursement_request}"
                )
            else:
                reimbursement_request.reimbursement_transfer_date = (
                    datetime.datetime.fromtimestamp(transfer.created)
                )
                db.session.add(reimbursement_request)
                # FIXME: DO NOT COMMIT OUTSIDE VIEWS/RESOURCES
                db.session.commit()

        if reimbursement_request.reimbursement_payout_date:
            raise ValueError(
                "Reimbursement already exists, did not try to duplicate the transfer and payout of funds"
            )
        else:
            payout = stripe_client.create_payout_to_connect_account_for_user(
                user=user,
                amount=reimbursement_request.amount,
                metadata={
                    StripeReimbursementHandler.PAYOUT_METADATA_ID_FIELD: reimbursement_request.id
                },
            )
            if not payout:
                log.error(
                    "Missing stripe payout",
                    user_id=user.id,
                    reimbursement_request=reimbursement_request.id,
                )
                raise ValueError(
                    "Error while creating a Stripe reimbursement payout"
                    f" for user {user.id} and reimbursement request {reimbursement_request}"
                )
            else:
                reimbursement_request.reimbursement_payout_date = (
                    datetime.datetime.fromtimestamp(payout.created)
                )
                db.session.add(reimbursement_request)
                # FIXME: DO NOT COMMIT OUTSIDE VIEWS/RESOURCES
                db.session.commit()
                return payout

    @classmethod
    def read_webhook_event(cls, event_json, header_signature):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """validates an event from the Stripe webhook as it relates to reimbursements."""
        try:
            event = stripe.Event.construct_from(
                event_json, header_signature, REIMBURSEMENTS_STRIPE_API_KEY
            )
        except ValueError as e:
            log.error(
                "Reimbursements event handler received invalid data",
                error=str(e),
                event_id=event_json and event_json.id,
            )
            return
        except stripe.error.SignatureVerificationError as e:
            log.error(
                "Invalid stripe webhook signature",
                error=str(e),
                event_id=event_json and event_json.id,
            )
            return
        except stripe.error.StripeError as e:
            log.info(
                "Generic Stripe Error",
                error=str(e),
                event_id=event_json and event_json.id,
            )
            return

        return event


class StripeAccountClient:
    account_only = True

    def account_balance(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return sum(
            [
                a.amount / 100
                for a in stripe.Balance.retrieve(
                    api_key=PAYMENTS_STRIPE_API_KEY
                ).available
            ]
        )


def read_webhook_event(
    payload: list[str],
    raw_payload: str,
    header_signature: str | None = None,
    endpoint_secret: str | None = None,
) -> StripeObject | None:
    """validates an event from the Stripe webhook and return the event"""
    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(
                raw_payload, header_signature, endpoint_secret  # type: ignore[arg-type] # Argument 2 to "construct_event" of "Webhook" has incompatible type "Optional[str]"; expected "str"
            )  # api/common/services/stripe.py:1074: error: Argument 2 to "construct_event" of "Webhook" has incompatible type "Optional[str]"; expected "str"  [arg-type]
        else:
            event = stripe.Event.construct_from(payload, PAYMENTS_STRIPE_API_KEY)
    except ValueError as e:
        log.error(
            "event handler received invalid data",
            error=str(e),
            payload=payload,
        )
        return None
    except stripe.error.SignatureVerificationError as e:
        log.error(
            "Invalid stripe webhook signature",
            error=str(e),
            payload=payload,
        )
        return None
    except stripe.error.StripeError as e:
        log.info(
            "Generic Stripe Error",
            error=str(e),
            payload=payload,
        )
        return None

    return event
