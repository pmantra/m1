from flask import request
from flask_restful import abort

from common.services.api import PermissionedUserResource
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from wallet.models.constants import CardStatus, WalletState
from wallet.resources.common import WalletResourceMixin
from wallet.schemas.reimbursement_wallet_debit_card import (
    ReimbursementWalletDebitCardPOSTRequestSchema,
    ReimbursementWalletDebitCardPOSTRequestSchemaV3,
    ReimbursementWalletDebitCardResponseSchema,
    ReimbursementWalletDebitCardResponseSchemaV3,
)
from wallet.utils.alegeus.debit_cards.manage import (
    add_phone_number_to_alegeus,
    report_lost_stolen_debit_card,
    request_debit_card,
    update_alegeus_demographics_for_debit_card,
)
from wallet.utils.alegeus.enrollments.enroll_wallet import check_hdhp_status


class UserReimbursementWalletDebitCardResource(
    PermissionedUserResource, WalletResourceMixin
):
    def get(self, wallet_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        wallet = self._wallet_or_404(self.user, wallet_id)

        if wallet.debit_card:
            data = {"data": wallet.debit_card}
            schema = ReimbursementWalletDebitCardResponseSchema()
            return schema.dump(data).data

        abort(404, message="You do not have a current debit card!")

    def post(self, wallet_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-user-reimbursement-wallet-debit-card-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        if experiment_enabled:
            schema = ReimbursementWalletDebitCardPOSTRequestSchemaV3()
            args = schema.load(request.json if request.is_json else None)
        else:
            schema = ReimbursementWalletDebitCardPOSTRequestSchema()
            args = schema.load(request.json if request.is_json else None).data

        wallet = self._wallet_or_404(self.user, wallet_id)

        # Org-level checks
        org_settings = wallet.reimbursement_organization_settings
        if not org_settings.debit_card_enabled:
            abort(
                403, message="Debit cards are not enabled for this Wallet Organization."
            )

        # Wallet-level checks
        if wallet.debit_card and wallet.debit_card.card_status != CardStatus.CLOSED:
            abort(
                409,
                message="Whoops! You already have a debit card.",
            )

        if wallet.state != WalletState.QUALIFIED:
            abort(
                403,
                message="Wallet must be qualified before a debit card may be requested.",
            )

        if not wallet.debit_card_eligible:
            abort(403, message="You are not eligible for a debit card.")

        hdhp_status = check_hdhp_status(wallet)
        if hdhp_status is False:
            abort(402, message="Please confirm you have met your HDHP deductible.")

        request_success = False
        try:
            address = self.user.addresses and self.user.addresses[0]
            update_success = update_alegeus_demographics_for_debit_card(
                wallet, self.user.id, address
            )
            sms_opt_in = args["sms_opt_in"] if args.get("sms_opt_in") else False
            if sms_opt_in:
                add_phone_number_to_alegeus(wallet, self.user)
            if update_success:
                request_success = request_debit_card(wallet, self.user)

        except Exception as error:
            abort(500, message=f"Could not complete request {error}")

        if not request_success:
            abort(500, message="Could not issue debit card")

        data = {"data": wallet.debit_card}
        if experiment_enabled:
            schema = ReimbursementWalletDebitCardResponseSchemaV3()
            return schema.dump(data)
        else:
            schema = ReimbursementWalletDebitCardResponseSchema()
            return schema.dump(data).data


class UserReimbursementWalletDebitCardLostStolenResource(
    PermissionedUserResource, WalletResourceMixin
):
    def post(self, wallet_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        wallet = self._wallet_or_404(self.user, wallet_id)
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-user-reimbursement-wallet-debit-card-lost-stolen-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        if not wallet.debit_card:
            abort(404, message="No debit card found for this wallet.")

        if wallet.debit_card.card_status == CardStatus.CLOSED:
            abort(
                409,
                message=("Whoops! This debit card is already closed."),
            )
        try:
            report_lost_stolen_debit_card(wallet)

        except Exception as error:
            abort(500, message=f"Could not complete request {error}")

        if wallet.debit_card.card_status != CardStatus.CLOSED:
            abort(500, message="Could not report card lost/stolen.")

        data = {"data": wallet.debit_card}
        if experiment_enabled:
            schema = ReimbursementWalletDebitCardResponseSchemaV3()
            return schema.dump(data)
        else:
            schema = ReimbursementWalletDebitCardResponseSchema()
            return schema.dump(data).data
