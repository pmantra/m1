from traceback import format_exc

import stripe
from flask import request
from flask_restful import abort
from marshmallow import fields as v3_fields
from marshmallow_v1 import Schema, fields
from sqlalchemy import func

from appointments.models.appointment import Appointment
from appointments.models.payments import new_stripe_customer
from authn.models.user import User
from authz.models.roles import ROLES
from authz.services.block_list import BlockList
from common.services.api import PermissionedUserResource, UnauthenticatedResource
from common.services.stripe import (
    CannotEditBusinessTypeException,
    NoStripeAccountFoundException,
    StripeConnectClient,
    StripeCustomerClient,
)
from common.services.stripe_constants import (
    PAYMENTS_STRIPE_API_KEY,
    REIMBURSEMENTS_STRIPE_API_KEY,
)
from emails import gift_delivery, gift_receipt
from messaging.services.zendesk import send_general_ticket_to_zendesk
from models.actions import ACTIONS, audit
from models.profiles import MemberProfile
from models.referrals import ReferralCode, ReferralCodeValue
from storage.connection import db
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from views.schemas.base import NestedWithDefaultV3, SchemaV3, StringWithDefaultV3
from views.schemas.common import BooleanField, MavenSchema, PaginableOutputSchema
from views.schemas.common_v3 import (
    IntegerWithDefaultV3,
    MavenSchemaV3,
    PaginableOutputSchemaV3,
    V3BooleanField,
)
from wallet.models.constants import ReimbursementRequestState
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


class PaymentMethodSchema(Schema):
    id = fields.String()
    brand = fields.String()
    last4 = fields.String()


class PaymentMethodsSchema(PaginableOutputSchema):
    data = fields.Nested(PaymentMethodSchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class PaymentMethodSchemaV3(SchemaV3):
    id = StringWithDefaultV3()
    brand = StringWithDefaultV3()
    last4 = StringWithDefaultV3()


class PaymentMethodsSchemaV3(PaginableOutputSchemaV3):
    data = NestedWithDefaultV3(PaymentMethodSchemaV3, many=True, default=[])  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class NewPaymentSchema(MavenSchema):
    stripe_token = fields.String(required=True)

    class Meta:
        strict = True


class _PaymentMethodsResource(PermissionedUserResource):
    def _stripe_client(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return StripeCustomerClient(api_key=PAYMENTS_STRIPE_API_KEY)


class UserPaymentMethodsResource(_PaymentMethodsResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-user-payment-methods-resource",
            user.esp_id if self.user else None,
            user.email if self.user else None,
            default=False,
        )
        stripe_client = self._stripe_client()
        schema = (
            PaymentMethodsSchemaV3() if experiment_enabled else PaymentMethodsSchema()
        )
        if experiment_enabled:
            return schema.dump({"data": stripe_client.list_cards(user=user)})  # type: ignore[attr-defined]
        else:
            return schema.dump({"data": stripe_client.list_cards(user=user)}).data  # type: ignore[attr-defined]

    def get_post_request(self, request_json: dict) -> dict:
        return {"stripe_token": str(request_json["stripe_token"])}

    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)
        stripe_client = self._stripe_client()
        args = self.get_post_request(request.json if request.is_json else None)

        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-user-payment-methods-resource",
            user.esp_id if self.user else None,
            user.email if self.user else None,
            default=False,
        )

        if (
            user.profile
            and isinstance(user.profile, MemberProfile)
            and user.profile.stripe_customer_id is None
        ):
            log.warning("Adding missing stripe_customer_id for member", user=user.id)
            user.profile.stripe_customer_id = new_stripe_customer(user)
            db.session.add(user.profile)
            db.session.commit()

        card_list = stripe_client.list_cards(user=user)
        if card_list is None:
            abort(400, message="Contact Maven support please!")
        if len(card_list):
            abort(400, message="Remove the existing card to add a new one!")

        try:
            card = stripe_client.add_card(token=args["stripe_token"], user=user)
        except stripe.error.CardError as e:
            log.info("Stripe CardError", error=str(e), user_id=user_id)
            abort(400, message="Card was declined!")
        except stripe.error.InvalidRequestError as e:
            log.info("Stripe InvalidRequestError", error=str(e), user_id=user_id)
            abort(400, message="Use a new stripe token!")
        except stripe.error.StripeError as e:
            log.info("Generic Stripe Error", error=str(e), user_id=user_id)
            abort(400, message="Problem with stripe, try again.")

        if card:
            # The BlockList tracks credit card "fingerprints". This exposes when a credit card number is reused across accounts
            # If one of those re-used numbers is in our BlockList, we will abort and disable the User
            if card.fingerprint:
                BlockList().validate_access(
                    user_id=user_id,
                    attribute="credit_card",
                    check_values=card.fingerprint,
                )

            mp = self.user.member_profile
            if mp.json.get("payment_collection_failed"):
                audit_data = {
                    "payment_collection_failed": mp.json.get(
                        "payment_collection_failed"
                    )
                }
                audit(
                    "reset_payment_failed", user_id=self.user.id, audit_data=audit_data
                )

                del mp.json["payment_collection_failed"]
                db.session.add(mp)
                db.session.commit()

            schema = (
                PaymentMethodsSchemaV3()
                if experiment_enabled
                else PaymentMethodsSchema()
            )
            if experiment_enabled:
                return schema.dump({"data": stripe_client.list_cards(user=user)}), 201  # type: ignore[attr-defined]
            else:
                return (
                    schema.dump({"data": stripe_client.list_cards(user=user)}).data,  # type: ignore[attr-defined]
                    201,
                )
        else:
            log.warning("Should not return without a card!")
            abort(500)


class UserPaymentMethodResource(_PaymentMethodsResource):
    def delete(self, user_id, card_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)
        stripe_client = self._stripe_client()

        card_list = stripe_client.list_cards(user=user)
        if len(card_list) == 1 and card_id in [c.id for c in card_list]:
            if Appointment.pending_for_user(self.user):
                mp = self.user.member_profile
                if not mp.json.get("payment_collection_failed"):
                    abort(400, message="Cannot delete if appointment is pending.")
                else:
                    log.debug(
                        (
                            "Allowing user with failed pymt collection to delete "
                            "card: %s"
                        ),
                        self.user,
                    )

            deleted = stripe_client.delete_card(card_id=card_id, user=user)
            if deleted is None:
                return "", 204
            elif deleted is False:
                abort(400, message="Card does not exist!")

        elif len(stripe_client.list_cards(user=user)) == 1:
            abort(403, message="You can only delete a card you own!")


class BankAccountSchema(Schema):
    bank_name = fields.String()
    last4 = fields.String()
    country = fields.String()


class BankAccountSchemaV3(SchemaV3):
    bank_name = StringWithDefaultV3(default="")
    last4 = StringWithDefaultV3(default="")
    country = StringWithDefaultV3(default="")


class StripeDOBSchema(Schema):
    month = fields.String(required=True)
    day = fields.String(required=True)
    year = fields.String(required=True)


class StripeDOBSchemaV3(SchemaV3):
    month = StringWithDefaultV3(required=True, default="")
    day = StringWithDefaultV3(required=True, default="")
    year = StringWithDefaultV3(required=True, default="")


class StripeAddressSchema(Schema):
    line1 = fields.String(required=True)
    city = fields.String(required=True)
    state = fields.String(required=True)
    postal_code = fields.String(required=True)


class StripeAddressSchemaV3(SchemaV3):
    line1 = StringWithDefaultV3(required=True, default="")
    city = StringWithDefaultV3(required=True, default="")
    state = StringWithDefaultV3(required=True, default="")
    postal_code = StringWithDefaultV3(required=True, default="")


class StripeDocumentSchema(Schema):
    back = fields.String(allow_none=True)
    front = fields.String(allow_none=True)
    details = fields.String(allow_none=True)
    details_code = fields.String(allow_none=True)


class StripeDocumentSchemaV3(SchemaV3):
    back = StringWithDefaultV3(allow_none=True, default="")
    front = StringWithDefaultV3(allow_none=True, default="")
    details = StringWithDefaultV3(allow_none=True, default="")
    details_code = StringWithDefaultV3(allow_none=True, default="")


class StripeVerificationSchema(Schema):
    document = fields.Nested(StripeDocumentSchema, allow_none=True)
    additional_document = fields.Nested(StripeDocumentSchema, allow_none=True)


class StripeVerificationSchemaV3(SchemaV3):
    document = NestedWithDefaultV3(StripeDocumentSchemaV3, allow_none=True, default=[])
    additional_document = NestedWithDefaultV3(
        StripeDocumentSchemaV3, allow_none=True, default=[]
    )


class LegalEntityIndividualSchema(Schema):
    dob = fields.Nested(StripeDOBSchema, required=True)
    address = fields.Nested(StripeAddressSchema, required=True)
    first_name = fields.String()
    last_name = fields.String()
    type = fields.String(missing="individual")
    ssn_last_4 = fields.String(allow_null=True)
    ssn_last_4_provided = BooleanField()
    id_number = fields.String(allow_null=True)
    id_number_provided = BooleanField()
    verification = fields.Nested(StripeVerificationSchema, allow_null=True)


class LegalEntityIndividualSchemaV3(SchemaV3):
    dob = NestedWithDefaultV3(StripeDOBSchemaV3, required=True)
    address = NestedWithDefaultV3(StripeAddressSchemaV3, required=True)
    first_name = StringWithDefaultV3(default="")
    last_name = StringWithDefaultV3(default="")
    type = StringWithDefaultV3(missing="individual", default="")
    ssn_last_4 = StringWithDefaultV3(allow_null=True, default="")
    ssn_last_4_provided = V3BooleanField()
    id_number = StringWithDefaultV3(allow_null=True, default="")
    id_number_provided = V3BooleanField()
    verification = NestedWithDefaultV3(StripeVerificationSchemaV3, allow_null=True)


class LegalEntityCompanySchema(Schema):
    address = fields.Nested(StripeAddressSchema, required=True)
    name = fields.String(required=True)
    tax_id = fields.String(allow_null=True)
    tax_id_provided = fields.Boolean(allow_null=True)
    type = fields.String(required=True)
    verification = fields.Nested(
        StripeVerificationSchema, allow_null=True, exclude=["additional_document"]
    )


class LegalEntityCompanySchemaV3(SchemaV3):
    address = NestedWithDefaultV3(StripeAddressSchemaV3, required=True)
    name = StringWithDefaultV3(required=True, default="")
    tax_id = StringWithDefaultV3(allow_null=True, default="")
    tax_id_provided = v3_fields.Boolean(allow_null=True)
    type = StringWithDefaultV3(required=True, default="")
    verification = NestedWithDefaultV3(
        StripeVerificationSchemaV3, allow_null=True, exclude=["additional_document"]
    )


class TermsOfServiceSchema(Schema):
    date = fields.Int(required=True)
    ip = fields.String(required=True)
    user_agent = fields.String(required=True, allow_null=True)


class TermsOfServiceSchemaV3(SchemaV3):
    date = IntegerWithDefaultV3(required=True, default=0)
    ip = StringWithDefaultV3(required=True, default="")
    user_agent = StringWithDefaultV3(required=True, allow_null=True, default="")


class ConnectAccountSchema(MavenSchema):
    payouts_enabled = BooleanField(attribute="payouts_enabled")
    external_accounts = fields.Nested(
        BankAccountSchema,
        allow_null=True,
        many=True,
        attribute="external_accounts.data",
    )
    individual = fields.Nested(
        LegalEntityIndividualSchema, allow_null=True, exclude=["type"]
    )
    company = fields.Nested(
        LegalEntityCompanySchema, allow_null=True, exclude=["type", "tax_id"]
    )
    tos_acceptance = fields.Nested(TermsOfServiceSchema, allow_nulls=True)


class ConnectAccountSchemaV3(MavenSchemaV3):
    payouts_enabled = V3BooleanField(attribute="payouts_enabled")
    external_accounts = NestedWithDefaultV3(
        BankAccountSchemaV3,
        allow_null=True,
        many=True,
        attribute="external_accounts.data",
        default=[],
    )
    individual = NestedWithDefaultV3(
        LegalEntityIndividualSchemaV3, allow_null=True, exclude=["type"]
    )
    company = NestedWithDefaultV3(
        LegalEntityCompanySchemaV3, allow_null=True, exclude=["type", "tax_id"]
    )
    tos_acceptance = NestedWithDefaultV3(TermsOfServiceSchemaV3, allow_nulls=True)


class RecipientInformationResource(PermissionedUserResource):
    """Endpoint that sets the information allowing a stripe connect account to accept transfers and bank accounts.
    Assigns different stripe keys depending on if it's dealing with practitioner funds or reimbursement funds.
    """

    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)
        stripe_client = self._stripe_client(user)

        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-recipient-information-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )

        account = None
        if stripe_client:
            account = stripe_client.get_connect_account_for_user(user)
        else:
            abort(400, message="Cannot get Stripe account!")

        if account:
            if experiment_enabled:
                schema = ConnectAccountSchemaV3()
                return schema.dump(account)
            else:
                schema = ConnectAccountSchema()
                return schema.dump(account).data
        else:
            return {}

    def put(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)
        stripe_client = self._stripe_client(user)
        connected_account = stripe_client.get_connect_account_for_user(user)

        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-recipient-information-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )

        if not connected_account:
            abort(400, message="Cannot get Stripe account!")

        try:
            # Pass the ip to accept/update terms of service
            account = stripe_client.edit_connect_account_for_user(
                user,
                self._legal_entity(stripe_id_info=True),
                self._get_request_ip(),
            )
        except CannotEditBusinessTypeException:
            # When users attempt to change from a business to an individual account or visa versa
            # We create new accounts for them to get around the inability to make that change in Stripe.
            profile = user.practitioner_profile or user.member_profile
            new_account = stripe_client.create_connect_account(
                self._legal_entity(stripe_id_info=True),
                source_ip=self._get_request_ip(),
                metadata={"previous_account": profile.stripe_account_id},
                user_id=user.id,
            )
            if not new_account:
                # TODO: We should be more informative about why did we fail to create the account. We could get that from log.warning that exist inside create_connect_account. We should probably raise an exception with details rather than returning None
                # TODO: Add test that would capture this 400
                abort(
                    400,
                    message=(
                        "Could not add recipient account - please check all "
                        "info and try again."
                    ),
                )
            profile.stripe_account_id = new_account.stripe_id
            db.session.add(profile)
            db.session.commit()
            account = new_account
        except NoStripeAccountFoundException:
            abort(400, message="No stripe account found for user")

        if account:
            if experiment_enabled:
                schema = ConnectAccountSchemaV3()
                return schema.dump(account)
            else:
                schema = ConnectAccountSchema()
                return schema.dump(account).data
        else:
            abort(400, message="Could not edit - check info and try again")

    # TODO: this endpoint is not covered by tests.
    # https://mavenclinic.atlassian.net/browse/VIRC-1770
    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)
        stripe_client = self._stripe_client(user)

        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-recipient-information-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )

        profile = user.practitioner_profile or user.member_profile
        if profile:
            if profile.stripe_account_id:
                abort(400, message="You already have an account!")
            else:
                connected_account = stripe_client.create_connect_account(
                    self._legal_entity(),
                    source_ip=self._get_request_ip(),
                    user_id=user.id,
                )
                if not connected_account:
                    abort(
                        400,
                        message=(
                            "Could not add recipient account - please check all "
                            "info and try again."
                        ),
                    )

                profile.stripe_account_id = connected_account.id
                profile.json["stripe_keys"] = connected_account.get("keys")

                db.session.add(profile)
                db.session.commit()

                if connected_account:
                    if experiment_enabled:
                        schema = ConnectAccountSchemaV3()
                        return schema.dump(connected_account), 201
                    else:
                        schema = ConnectAccountSchema()
                        return schema.dump(connected_account).data, 201
                else:
                    abort(
                        400,
                        message=(
                            "Please ensure the name and tax_id are"
                            " correct and try again"
                        ),
                    )
        else:
            abort(403, message=f"You cannot add a recipient as a {user.role_name}!")

    def _legal_entity(self, schema=None, stripe_id_info=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        raw_data = request.json if request.is_json else None
        if not raw_data:
            abort(400, message="No JSON provided")

        legal_entity = self.get_legal_entity_information_from_json(
            raw_data, schema, stripe_id_info
        )
        if not legal_entity:
            abort(400, message="Provide a legal_entity!")

        return legal_entity

    def _get_request_ip(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return request.headers.get("X-Real-IP")

    @classmethod
    def get_legal_entity_information_from_json(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        cls, raw_data, schema=None, stripe_id_info=None
    ):
        if "legal_entity" not in raw_data or not isinstance(
            raw_data["legal_entity"], dict
        ):
            return None

        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-recipient-information-resource",
            None,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
            default=False,
        )

        if experiment_enabled:
            schema = schema or (
                LegalEntityCompanySchemaV3(exclude=["tax_id_provided"])
                if (
                    "type" in raw_data["legal_entity"]
                    and raw_data["legal_entity"]["type"] == "company"
                )
                else LegalEntityIndividualSchemaV3(
                    exclude=["ssn_last_4_provided", "id_number_provided"]
                )
            )
        else:
            schema = schema or (
                LegalEntityCompanySchema(exclude=["tax_id_provided"])
                if (
                    "type" in raw_data["legal_entity"]
                    and raw_data["legal_entity"]["type"] == "company"
                )
                else LegalEntityIndividualSchema(
                    exclude=["ssn_last_4_provided", "id_number_provided"]
                )
            )

        legal_entity = {}
        raw_data = (
            schema.dump(raw_data["legal_entity"])
            if experiment_enabled
            else schema.dump(raw_data["legal_entity"]).data
        )
        for k, v in raw_data.items():
            if v:
                legal_entity[k] = v

        if stripe_id_info:
            legal_entity.pop("ssn_last_4", None)
            legal_entity.pop("business_tax_id", None)

        return legal_entity

    def _stripe_client(self, user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        stripe_client = None
        if user.practitioner_profile:
            stripe_client = StripeConnectClient(api_key=PAYMENTS_STRIPE_API_KEY)
        elif user.member_profile:
            log.info("Created Stripe Connect Client")
            stripe_client = StripeConnectClient(api_key=REIMBURSEMENTS_STRIPE_API_KEY)
        else:
            log.warning(
                f"No profile found while trying to create a stripe client for {user}",
                profiles=(user.practitioner_profile, user.member_profile),
            )
            abort(403, message="You cannot access this!")
        return stripe_client


class UserBankAccountsResource(PermissionedUserResource):
    """Endpoint that lets a user attach a bank account to their stripe connect account.
    Assigns different stripe keys depending on if it's dealing with practitioner funds or reimbursement funds.
    """

    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)
        stripe_client = self._stripe_client_or_404(user)
        account = stripe_client.get_bank_account_for_user(user)
        if account:
            schema = BankAccountSchema()
            return schema.dump(account).data
        else:
            abort(403, message="You do not have an attached bank account!")

    def get_post_request(self, request_json: dict) -> dict:
        return {"stripe_token": str(request_json["stripe_token"])}

    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)
        stripe_client = self._stripe_client_or_404(user)
        schema = NewPaymentSchema()
        request_json = request.json if request.is_json else None
        args = schema.load(request_json).data
        try:
            python_request = self.get_post_request(request_json)
            if python_request == args:
                log.info("FM - UserBankAccountsResource identical")
            else:
                log.info("FM - UserBankAccountsResource diff")
        except Exception:
            log.info(
                "FM - UserBankAccountsResource error",
                exc_info=True,
                traces=format_exc(),
            )

        get_account_info = stripe_client.get_bank_account_for_user(user)
        if get_account_info:
            abort(
                400,
                message=(
                    "Whoops! You already have a bank account on file. "
                    "To update it, please email "
                    "practitionersupport@mavenclinic.com"
                ),
            )

        account = stripe_client.set_bank_account_for_user(user, args["stripe_token"])
        try:
            if not account:
                raise ValueError(
                    "Missing account information after trying to set a bank account."
                )
            account_data = (
                account.external_accounts.data[0]
                if account.external_accounts.data
                else None
            )
            if not account_data:
                raise ValueError(
                    "Missing account data after trying to set a bank account"
                )
            schema = BankAccountSchema()
            return schema.dump(account_data).data, 201
        except ValueError as e:
            log.warning("Error setting a bank account via stripe_token", error=str(e))
            abort(400, message="Check the stripe_token and try again!")

    def get_put_request(self, request_json: dict) -> dict:
        return {"stripe_token": str(request_json["stripe_token"])}

    def put(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)
        stripe_client = self._stripe_client_or_404(user)
        args = self.get_put_request(request.json if request.is_json else None)

        account = stripe_client.set_bank_account_for_user(
            user, args["stripe_token"], overwrite_allowed=True
        )
        if account:
            account_data = (
                account.external_accounts.data[0]
                if account.external_accounts.data
                else None
            )
            schema = BankAccountSchema()
            return schema.dump(account_data).data
        else:
            abort(400, message="Check the stripe_token and try again!")

    def delete(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Removes stripe token from our code if allowed. Does _not_ remove it from Stripe."""
        user = self._user_or_404(user_id)
        profile = user.practitioner_profile or user.member_profile
        if (
            profile.stripe_account_id is not None
            and user.reimbursement_wallets is not None
            and len(user.reimbursement_wallets) > 0
        ):
            requests_in_flight = (
                db.session.query(func.count(ReimbursementRequest.id))
                .join(ReimbursementRequest.wallet)
                .filter(
                    ReimbursementWallet.user_id == self.user.id,
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
                    user=self.user,
                    ticket_subject=f"Request to remove Maven Wallet Bank Account for {self.user}",
                    content="This bank account cannot be removed automatically due to reimbursement requests in flight.",
                    called_by=["maven_wallet"],
                )
                return (
                    {
                        "data": None,
                        "errors": [
                            {
                                "code": "REMOVE_PAYMENT_METHOD_INCOMPLETE",
                                "message": "Your Maven Care Advocate will contact you shortly "
                                "to unlink your bank account from Maven Wallet.",
                            }
                        ],
                    },
                    200,
                )
        remove_stripe_acct = StripeConnectClient.unset_bank_account_for_user(user)
        if remove_stripe_acct is False:
            return (
                {
                    "data": None,
                    "errors": [
                        {
                            "code": "NOT_FOUND",
                            "message": "No attached bank account found to remove.",
                        }
                    ],
                },
                400,
            )
        else:
            return {"data": "Removed a bank account.", "errors": []}, 200

    def _stripe_client_or_404(self, user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        stripe_client = None
        if user.practitioner_profile:
            stripe_client = StripeConnectClient(api_key=PAYMENTS_STRIPE_API_KEY)
        elif user.member_profile:
            stripe_client = StripeConnectClient(api_key=REIMBURSEMENTS_STRIPE_API_KEY)
        else:
            abort(403, message="You cannot access this!")

        account = stripe_client.get_connect_account_for_user(user=user)  # type: ignore[union-attr] # Item "None" of "Optional[StripeConnectClient]" has no attribute "get_connect_account_for_user"
        if stripe_client is None or account is None:
            abort(400, message="Add Stripe account legal info first, please!")

        return stripe_client


class GiftPOSTArgs(MavenSchema):
    gift_amount = fields.Integer(required=True)
    gift_email = fields.Email(required=True)
    gift_name = fields.String(required=True)
    gift_message = fields.String()
    sender_name = fields.String(required=True)
    sender_email = fields.Email(required=True)
    stripe_token = fields.String(required=True)

    class Meta:
        strict = True


class GiftingResource(UnauthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = GiftPOSTArgs()
        args = schema.load(request.json if request.is_json else None).data
        log.debug("Gifting: %s", args)

        try:
            charge = stripe.Charge.create(
                amount=args["gift_amount"],  # amount in cents
                currency="usd",
                source=args["stripe_token"],
                description="Gifting Maven",
                api_key=PAYMENTS_STRIPE_API_KEY,
            )
        except stripe.error.CardError as e:
            log.error("Card most likely declined. Error: %s", e)
            abort(400, message="Card was declined!")
        except stripe.error.StripeError as e:
            log.info("Generic Stripe Error", error=str(e))
            abort(400, message="Problem with stripe, try again.")
        else:
            log.info("Charge successful - adding credits and sending emails.")
            audit_data = {"charge": charge, "args": args}
            action_type = ACTIONS.gift_purchased

            amount_uplifts = {
                # NOTE: these are for mental health packages
                19_500: 21_000,
                30_000: 35_000,
                55_000: 70_000,
                # NOTE: these are for nutritionist packages
                7_000: 7_500,
                11_500: 12_500,
                22_500: 25_000,
            }

            if args["gift_amount"] in amount_uplifts:
                log.info(
                    "Uplifting %s to %s",
                    args["gift_amount"],
                    amount_uplifts[args["gift_amount"]],
                )
                gift_amount = amount_uplifts[args["gift_amount"]]
            else:
                gift_amount = args["gift_amount"]

            audit_data["paid_amount"] = args["gift_amount"]
            audit_data["final_amount"] = gift_amount

            log.info("Raw amount: %s", gift_amount)
            # this depends on divison settings for decimal precision that are
            # imported as a side effect from payment models
            amount = gift_amount / 100
            log.info("Converted amount: %s", amount)

            paid_amount = args["gift_amount"] / 100

            code = add_referral_code_for_gift(amount)
            audit_data["code"] = code.code
            audit_data["amount"] = amount
            audit(action_type, **audit_data)
            log.info("Code added & audit comitted.")

            gift_delivery(
                args["gift_email"],
                args["gift_name"],
                args["sender_name"],
                amount,
                paid_amount,
                args.get("gift_message"),
                code.code,
            )
            gift_receipt(
                args["sender_email"],
                args["sender_name"],
                amount,
                paid_amount,
                args["gift_name"],
            )

            log.info("All set - delivery & receipt sent...")
            return "", 204


def add_referral_code_for_gift(amount) -> ReferralCode:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    log.info("Adding a credit ($%s)", amount)
    code = ReferralCode(allowed_uses=1, only_use_before_booking=False)
    db.session.add(code)
    db.session.commit()

    # This is a hack because i cannot figure out how to get None instead of the
    # default on inserting a new record here
    code.expires_at = None
    db.session.add(code)
    db.session.commit()

    for_member = ReferralCodeValue(code=code, value=amount, for_user_type=ROLES.member)

    db.session.add(for_member)
    db.session.commit()

    # This is a hack because i cannot figure out how to get None instead of the
    # default on inserting a new record here
    for_member.expires_at = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "datetime")
    db.session.add(for_member)
    db.session.commit()

    log.info("Added code: %s", code)
    return code
