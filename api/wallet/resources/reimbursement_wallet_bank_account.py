from typing import Dict, Optional

from flask import request
from flask_restful import abort
from marshmallow import ValidationError
from sqlalchemy import func

from authn.models.user import User
from common.services.api import PermissionedUserResource
from messaging.services.zendesk import send_general_ticket_to_zendesk
from storage.connection import db
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from views.payments import BankAccountSchema, BankAccountSchemaV3
from wallet.alegeus_api import AlegeusApi
from wallet.models.constants import (
    AlegeusBankAccountType,
    ReimbursementMethod,
    ReimbursementRequestState,
    WalletUserStatus,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.resources.common import WalletResourceMixin
from wallet.schemas.reimbursement_wallet_bank_account import (
    AddReimbursementWalletBankAccountSchema,
)
from wallet.utils.alegeus.enrollments.enroll_wallet import (
    get_eligibility_date_from_wallet,
)

log = logger(__name__)


class UserReimbursementWalletBankAccountResource(
    PermissionedUserResource, WalletResourceMixin
):
    """
    Endpoint that lets a user manage a bank account that is associated with their ReimbursementWallet in Alegeus.

    We need to be very careful with the bank account information that we send to/recieve from Alegeus
    to make sure we're following security best practices. Any variables that hold/held bank account
    information should be cleared and deleted after use and we should avoid any caching on our side.
    """

    @staticmethod
    def _get_bank_account_info(
        api: AlegeusApi, user_id: int, wallet: ReimbursementWallet
    ) -> Optional[Dict]:
        """
        Get a user's bank account information from Alegeus.
        @param api: an instance of `AlegeusApi`
        @param user_id: the ID of the user
        @param wallet: the user's `ReimbursementWallet`
        @return: a dictionary containing:
            - bank_name: assigned display name (could be bank name, user-supplied, or automatically set by client)
            - last4: last four digits of the bank account number
            - country: legacy value, would be the country where the bank is located, but blank since moving to Alegeus
        """
        # This response will return the full banking information for the user.
        # In order to protect the sensitivity of this data, we will only use
        # the last four digits of the bank account number and clear/delete
        # the variables where the full account number was stored.
        response = api.get_ach_accounts(wallet)
        if response.status_code != 200:
            abort(404, message=f"Could not find bank accounts for User ID={user_id}")

        ach_accounts_json = response.json()
        # explicitly clearing/deleting the variable to protect sensitive data
        response = None
        del response

        if len(ach_accounts_json) == 0:
            return  # type: ignore[return-value] # Return value expected

        # The endpoint returns a list but the application only supports one account
        ach_account = ach_accounts_json[0]

        bank_account_info = {
            "bank_name": ach_account.get("BankAccountName", ""),
            "last4": ach_account.get("BankAccountNumber", "")[-4:],
            "country": "",
        }
        # explicitly clearing/deleting the variable to protect sensitive data
        ach_accounts_json = None
        ach_account = None
        del ach_accounts_json
        del ach_account

        if bank_account_info["bank_name"] and bank_account_info["last4"]:
            return bank_account_info
        return  # type: ignore[return-value] # Return value expected

    @staticmethod
    def _set_bank_account_info(
        api: AlegeusApi, wallet: ReimbursementWallet, banking_info: Dict, user: User
    ) -> None:
        """
        Set the bank account information for a user in Alegeus.
        @param api: an instance of `AlegeusApi`
        @param wallet: the user's `ReimbursementWallet`
        @param banking_info: dictionary containing bank account information. Must contain the following keys:
            - BankAcctName
            - BankAccount
            - BankAccountTypeCode
            - BankRoutingNumber
        @return: None
        """
        if banking_info:
            banking_info["BankAccountTypeCode"] = AlegeusBankAccountType[
                banking_info["BankAccountTypeCode"].upper()
            ].value

        # All members with a debit card should have an address, but in case they don't allow the update to continue.
        member_address = (
            user.addresses[0]
            if (wallet.debit_card and user.addresses and user.addresses[0])
            else None
        )

        response = api.put_employee_services_and_banking(
            wallet=wallet,
            banking_info=banking_info,
            eligibility_date=get_eligibility_date_from_wallet(wallet),
            member_address=member_address,
        )
        if response.status_code != 200:
            # explicitly clearing/deleting the variables to protect sensitive data
            response = None
            del response
            banking_info = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "Dict[Any, Any]")
            del banking_info
            abort(
                400, message=f"Could not update banking info for Wallet ID={wallet.id}"
            )

    def get(self, wallet_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Fetch the user's bank account information.
        If the bank account information was not found, return a 404 status code.
        @param wallet_id: the ID of the user's wallet
        @return: A tuple of the form (``data``, ``errors``) where `data` contains the bank account information.
        """
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-user-reimbursement-wallet-bank-account-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        wallet = self._wallet_or_404(self.user, wallet_id)

        api = AlegeusApi()
        bank_account_info = self._get_bank_account_info(api, self.user.id, wallet)
        if bank_account_info:
            if experiment_enabled:
                schema = BankAccountSchemaV3()
                return schema.dump(bank_account_info)
            else:
                schema = BankAccountSchema()
                return schema.dump(bank_account_info)

        abort(404, message="You do not have an attached bank account!")

    def post(self, wallet_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Add user's bank account information in Alegeus.
        If bank account information is already set for this user, return a 409 status code.
        @param wallet_id: the ID of the user's wallet
        @return: A tuple of the form (``data``, ``errors``) where `data` contains the bank account information.
        """
        wallet = self._wallet_or_404(self.user, wallet_id)

        api = AlegeusApi()
        bank_account_info = self._get_bank_account_info(api, self.user.id, wallet)
        if bank_account_info:
            abort(
                409,
                message=(
                    "Whoops! You already have a bank account on file. "
                    "To update it, please email "
                    "practitionersupport@mavenclinic.com"
                ),
            )

        schema = AddReimbursementWalletBankAccountSchema()
        try:
            args = schema.load(request.json if request.is_json else {})
        except ValidationError as exc:
            abort(400, message=exc.messages)

        self._set_bank_account_info(api, wallet, args, self.user)
        # explicitly clearing/deleting the variable to protect sensitive data
        args = None
        del args

        bank_account_info = self._get_bank_account_info(api, self.user.id, wallet)
        if bank_account_info:
            return bank_account_info, 201

        abort(400, message="Error updating bank account!")

    def put(self, wallet_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Update a user's bank account information in Alegeus.
        @param wallet_id: the ID of the user's wallet
        @return: A tuple of the form (``data``, ``errors``) where `data` contains the bank account information.
        """
        wallet = self._wallet_or_404(self.user, wallet_id)
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-user-reimbursement-wallet-bank-account-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        schema = AddReimbursementWalletBankAccountSchema()
        try:
            args = schema.load(request.json if request.is_json else {})
        except ValidationError as exc:
            abort(400, message=exc.messages)

        api = AlegeusApi()
        self._set_bank_account_info(api, wallet, args, self.user)
        # explicitly clearing/deleting the variable to protect sensitive data
        args = None
        del args

        bank_account_info = self._get_bank_account_info(api, self.user.id, wallet)
        if bank_account_info:
            schema = (
                BankAccountSchemaV3() if experiment_enabled else BankAccountSchema()
            )
            return schema.dump(bank_account_info)

        abort(400, message="Error updating bank account!")

    def delete(self, wallet_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Remove a user's bank account information from Alegeus.
        NOTE: bank account information may only be removed if the member has a reimbursement method of payroll AND
        the member does not have any Approved or Pending reimnbursement requests.

        If the member is set to use direct deposit, return an error message with a 409 status code.
        If the member has any Approved or Pending reimbursement requests, return a message with a 200 status code.
        @param wallet_id: the ID of the user's wallet
        """
        wallet = self._wallet_or_404(self.user, wallet_id)

        if wallet.reimbursement_method == ReimbursementMethod.DIRECT_DEPOSIT:
            abort(
                409,
                message="Unable to remove a bank account when the reimbursement method is direct deposit.",
            )

        requests_in_flight = (
            db.session.query(func.count(ReimbursementRequest.id))
            .join(ReimbursementRequest.wallet)
            .join(ReimbursementWalletUsers)
            .filter(
                ReimbursementWalletUsers.user_id == self.user.id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
                ReimbursementRequest.state.in_(
                    [
                        ReimbursementRequestState.PENDING,
                        ReimbursementRequestState.APPROVED,
                    ]
                ),
            )
            .scalar()
        )

        log.info(
            f"Attempted to remove a bank account for {self.user}.",
            requests_in_flight=requests_in_flight,
        )

        if requests_in_flight > 0:
            send_general_ticket_to_zendesk(
                self.user,
                f"Request to remove Maven Wallet Bank Account for {self.user}",
                "This bank account cannot be removed automatically due to reimbursement requests in flight.",
                ["maven_wallet"],
            )
            return {
                "message": (
                    "This bank account cannot be removed automatically "
                    "due to reimbursement requests in flight. "
                    "Your Maven Care Advocate will contact you shortly "
                    "to unlink your bank account from Maven Wallet."
                ),
            }, 200

        api = AlegeusApi()
        self._set_bank_account_info(api, wallet, {}, self.user)
        bank_account_info = self._get_bank_account_info(api, self.user.id, wallet)
        # if the bank account still exists, then something went wrong.
        log.error(f"Bank account info was not deleted in Alegeus for {self.user}.")
        if bank_account_info:
            send_general_ticket_to_zendesk(
                self.user,
                f"Request to remove Maven Wallet Bank Account for {self.user}",
                "This bank account could not be removed in Alegeus due to an unknown error.",
                ["maven_wallet"],
            )
            return abort(
                400,
                message="Error updating bank account!",
            )

        return {"message": "Removed a bank account."}, 200
