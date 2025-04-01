import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Type

import flask_login as login
from dateutil.relativedelta import relativedelta
from flask import abort, flash, request
from flask_admin import BaseView, expose
from flask_admin.actions import action
from flask_admin.babel import lazy_gettext
from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader
from flask_admin.contrib.sqla.filters import FilterEmpty
from flask_admin.form import rules
from flask_admin.model.helpers import get_mdict_item_or_list
from marshmallow_v1 import fields
from redset.exceptions import LockTimeout
from sqlalchemy import or_
from sqlalchemy.orm import aliased
from werkzeug.utils import redirect

from admin.views.auth import AdminAuth
from admin.views.base import (
    USER_AJAX_REF,
    AdminCategory,
    AdminViewT,
    ContainsFilter,
    IsFilter,
    MavenAuditedView,
    ReadOnlyFieldRule,
    ViewExtras,
)
from appointments.models.appointment import Appointment
from appointments.models.payments import (
    AppointmentFeeCreator,
    Credit,
    FeeAccountingEntry,
    FeeAccountingEntryTypes,
    Invoice,
    PaymentAccountingEntry,
)
from audit_log.utils import (
    emit_audit_log_create,
    emit_audit_log_delete,
    emit_audit_log_read,
    emit_audit_log_update,
    emit_bulk_audit_log_create,
    emit_bulk_audit_log_read,
)
from authn.models.user import User
from common.services.stripe import StripeConnectClient
from common.services.stripe_constants import PAYMENTS_STRIPE_API_KEY
from messaging.models.messaging import Channel, ChannelUsers, Message
from models.actions import audit
from models.products import Product
from models.profiles import PractitionerProfile
from models.referrals import IncentivePayment
from models.verticals_and_specialties import Vertical, is_cx_vertical_name
from payments.models.contract_validator import (
    InvalidPractitionerContractInputsException,
)
from payments.models.practitioner_contract import PractitionerContract
from payments.services.practitioner_contract import PractitionerContractService
from storage.connection import RoutingSQLAlchemy, db
from tasks.payments import generate_invoices_from_fees
from utils.cache import RedisLock
from utils.log import logger
from utils.payments import FeeRecipientException, add_fees_to_invoices
from utils.reporting import _get_account_status
from views.schemas.common import MavenSchema, PaginableArgsSchema

log = logger(__name__)


class CreditUserQueryAjaxModelLoader(QueryAjaxModelLoader):
    def format(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(model, User):
            return (
                getattr(model, self.pk),
                f"<User [{model.id}] {model.full_name} [{model.email}]>",
            )
        else:
            return super().format(model)


class CreditView(MavenAuditedView):
    create_permission = "create:credit"
    edit_permission = "edit:credit"
    delete_permission = "delete:credit"
    read_permission = "read:credit"

    can_view_details = True
    edit_template = "credit_edit_template.html"

    column_exclude_list = (
        "practitioners",
        "referral_code_use",
        "json",
        "modified_at",
        "message_billing",
        "organization_package",
        "organization_employee",
    )
    column_sortable_list = ("created_at", "activated_at", "used_at", "expires_at")
    column_filters = ("expires_at", "activated_at", User.email)

    form_rules = ["user", "expires_at", "activated_at", "amount"]

    form_excluded_columns = [
        "appointment",
        "referral_code_use",
        "message_billing",
        "organization_package",
        "organization_employee",
    ]
    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "user": CreditUserQueryAjaxModelLoader(
                    "user", self.session, User, **USER_AJAX_REF
                )
            }
        return self._form_ajax_refs

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            Credit,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class PaymentAccountingEntryView(MavenAuditedView):
    read_permission = "read:payment-accounting-entry"
    edit_permission = "edit:payment-accounting-entry"

    edit_template = "payment_and_fee_edit_template.html"

    column_exclude_list = (
        "cancelled_at",
        "stripe_id",
        "amount",
        "amount_captured",
        "modified_at",
    )
    column_sortable_list = ("created_at", "appointment", "captured_at")

    column_filters = ("captured_at", "cancelled_at", "appointment_id")
    form_rules = []
    form_widget_args = {}

    for f in ("amount", "amount_captured", "stripe_id", "cancelled_at", "captured_at"):
        form_rules.append(f)
        form_widget_args[f] = {"disabled": True}

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            PaymentAccountingEntry,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class DistributedNetworkPractitionerFilter(FilterEmpty):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        non_distributed_practitioner_ids = (
            db.session.query(PractitionerProfile.user_id)
            .join(PractitionerProfile.verticals)
            .filter(
                or_(
                    is_cx_vertical_name(Vertical.name),
                    PractitionerProfile.is_staff == True,
                )
            )
            .subquery()
        )

        practitioner = aliased(PractitionerProfile)
        query = (
            query.outerjoin(Appointment, Product)
            .outerjoin(Message, Channel, ChannelUsers)
            .outerjoin(practitioner, ChannelUsers.user_id == practitioner.user_id)
        )
        if value == "1":
            return query.filter(
                or_(
                    Product.user_id.notin_(non_distributed_practitioner_ids),
                    practitioner.user_id.notin_(non_distributed_practitioner_ids),
                    FeeAccountingEntry.practitioner_id.notin_(
                        non_distributed_practitioner_ids
                    ),
                )
            )
        else:
            return query.filter(
                or_(
                    Product.user_id.in_(non_distributed_practitioner_ids),
                    practitioner.user_id.in_(non_distributed_practitioner_ids),
                    FeeAccountingEntry.practitioner_id.in_(
                        non_distributed_practitioner_ids
                    ),
                )
            )

    def operation(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return lazy_gettext("is Distributed")


class FeeAccountingEntryView(MavenAuditedView):
    read_permission = "read:fee-accounting-entry"
    edit_permission = "edit:fee-accounting-entry"

    required_capability = "admin_fee_accounting_entry"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    edit_template = "payment_and_fee_edit_template.html"

    column_exclude_list = (
        "modified_at",
        "appointment_id",
        "message_id",
        "practitioner_id",
    )
    column_filters = (
        "created_at",
        "appointment_id",
        "message_id",
        "practitioner_id",
        "invoice_id",
        DistributedNetworkPractitionerFilter(None, "Distributed Network Practitioner"),
    )
    form_rules = []
    form_widget_args = {}

    for f in ("amount", "created_at", "invoice"):
        form_rules.append(f)
        form_widget_args[f] = {"disabled": True}

    def get_sortable_columns(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return {
            "created_at": FeeAccountingEntry.created_at,
            "invoice": FeeAccountingEntry.invoice_id,
        }

    @action("delete_fee", "Delete Fee", "You Sure !?")
    def delete_fee(self, fee_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.info("Starting to delete fees: %s", fee_ids)

        if len(fee_ids) != 1:
            log.error("Only one fee ID allowed", fee_ids=fee_ids)
            abort(400)
        else:
            fee = FeeAccountingEntry.query.get(fee_ids[0])
            db.session.delete(fee)
            db.session.commit()
            emit_audit_log_delete(fee)
            log.info("All done with fee deletion for %s", fee_ids)
            flash("All set deleting fee!")

    @action("add_to_invoice", "Add to Invoice", "You Sure?")
    def add_to_invoice(self, fee_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        db.session.expunge_all()

        fees = (
            db.session.query(FeeAccountingEntry)
            .filter(FeeAccountingEntry.id.in_(fee_ids))
            .all()
        )
        if fees:
            try:
                add_fees_to_invoices(fees)
            except FeeRecipientException as e:
                abort(400, message=str(e))
        else:
            log.warning("No fees for IDs %s", fee_ids)
            abort(400)

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            FeeAccountingEntry,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class InvoicePractitionerIDFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # We don't want the resultant queryset to be joined on the FeeAccountingEntry table,
        # otherwise the cardinality of the queryset would be equal to the number of FeeAccountingEntry
        # rows, rather than the number of Invoice entries. This will screw up pagination, which
        # is based on the cardinality of the queryset (e.g. the result of `query.count()`) rather
        # than the number of returned Python objects (e.g. the result of `len([e for e in query])`).
        # To accomplish this, we'll make a subquery to join the tables and find the valid IDs, and
        # then use the outer query to just fetch entries from the table that are in that list of IDs.
        id_subquery = (
            Invoice.query.with_entities(Invoice.id)
            .join(
                FeeAccountingEntry,
            )
            .filter(FeeAccountingEntry.practitioner_id == value)
        ).subquery()

        return query.filter(
            Invoice.id.in_(id_subquery),
        )


class InvoicePractitionerIDEmptyFilter(FilterEmpty):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # We don't want the resultant queryset to be joined on the FeeAccountingEntry table,
        # otherwise the cardinality of the queryset would be equal to the number of FeeAccountingEntry
        # rows, rather than the number of Invoice entries. This will screw up pagination, which
        # is based on the cardinality of the queryset (e.g. the result of `query.count()`) rather
        # than the number of returned Python objects (e.g. the result of `len([e for e in query])`).
        # To accomplish this, we'll make a subquery to join the tables and find the valid IDs, and
        # then use the outer query to just fetch entries from the table that are in that list of IDs.
        id_subquery = Invoice.query.with_entities(Invoice.id).join(
            FeeAccountingEntry,
        )

        if value == "1":
            id_subquery = id_subquery.filter(
                FeeAccountingEntry.practitioner_id.is_(None)
                & FeeAccountingEntry.appointment_id.is_(None)
                & FeeAccountingEntry.message_id.is_(None)
            ).subquery()
        else:
            id_subquery = id_subquery.filter(
                FeeAccountingEntry.practitioner_id.isnot(None)
                | FeeAccountingEntry.appointment_id.isnot(None)
                | FeeAccountingEntry.message_id.isnot(None)
            ).subquery()

        return query.filter(Invoice.id.in_(id_subquery))


class InvoiceForDistributedPractitionersFilter(FilterEmpty):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        non_distributed_practitioner_ids = (
            db.session.query(PractitionerProfile.user_id)
            .join(PractitionerProfile.verticals)
            .filter(
                or_(
                    is_cx_vertical_name(Vertical.name),
                    PractitionerProfile.is_staff == True,
                )
            )
            .subquery()
        )

        practitioner = aliased(PractitionerProfile)

        # We don't want the resultant queryset to be joined on the FeeAccountingEntry table,
        # otherwise the cardinality of the queryset would be equal to the number of FeeAccountingEntry
        # rows, rather than the number of Invoice entries. This will screw up pagination, which
        # is based on the cardinality of the queryset (e.g. the result of `query.count()`) rather
        # than the number of returned Python objects (e.g. the result of `len([e for e in query])`).
        # To accomplish this, we'll make a subquery to join the tables and find the valid IDs, and
        # then use the outer query to just fetch entries from the table that are in that list of IDs.
        id_subquery = (
            Invoice.query.join(Invoice.entries)
            .with_entities(Invoice.id)
            .outerjoin(
                FeeAccountingEntry.appointment,
                Appointment.product,
                FeeAccountingEntry.message,
                Message.channel,
                Channel.participants,
                ChannelUsers.user,
            )
            .outerjoin(practitioner, ChannelUsers.user_id == practitioner.user_id)
        )

        if value == "1":
            id_subquery = id_subquery.filter(
                or_(
                    Product.user_id.notin_(non_distributed_practitioner_ids),
                    practitioner.user_id.notin_(non_distributed_practitioner_ids),
                    FeeAccountingEntry.practitioner_id.notin_(
                        non_distributed_practitioner_ids
                    ),
                )
            )
        else:
            id_subquery = id_subquery.filter(
                or_(
                    Product.user_id.in_(non_distributed_practitioner_ids),
                    practitioner.user_id.in_(non_distributed_practitioner_ids),
                    FeeAccountingEntry.practitioner_id.in_(
                        non_distributed_practitioner_ids
                    ),
                )
            )

        return query.filter(Invoice.id.in_(id_subquery))

    def operation(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return lazy_gettext("is Distributed")


class ProviderInvoiceSchema(MavenSchema):
    # camelCase to be consistent with ValidateInvoices frontend
    invoiceId = fields.Integer(required=True)
    invoiceCreatedAt = fields.Date(required=True)
    practitionerId = fields.Integer(required=True)
    isStaff = fields.Boolean(required=True)
    total = fields.String(required=True)
    fees = fields.Integer(required=True)


class ProviderInvoiceListSchema(MavenSchema):
    invoices = fields.Nested(ProviderInvoiceSchema, many=True)


class ProviderFeeSchema(MavenSchema):
    fae_id = fields.Integer(required=True)
    practitioner_id = fields.Integer(required=True)
    practitioner_name = fields.String(required=True)
    amount = fields.String(required=True)
    status = fields.String(required=True)


class ProviderFeeListSchema(MavenSchema):
    fees = fields.Nested(ProviderFeeSchema, many=True)


class MonthlyPaymentsView(AdminAuth, BaseView, ViewExtras):
    read_permission = "read:monthly-payments"
    delete_permission = "delete:monthly-payments"
    create_permission = "create:monthly-payments"
    edit_permission = "edit:monthly-payments"

    @expose("/")
    def index(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.render("monthly_payments.html")

    @expose("/existing_invoice", methods=("POST",))
    def existing_invoice(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        providers_csv = request.files.get("providers_csv")
        if not providers_csv:
            return {
                "error": "You need to upload a csv file with the validated payments info."
            }, 400

        provider_ids = []
        with io.StringIO(providers_csv.stream.read().decode()) as stream:
            reader = csv.DictReader(stream)
            if "ID" not in reader.fieldnames:
                return {"error": "Invalid csv file, file header should be 'ID'"}, 400
            for row in reader:
                provider_ids.append(row["ID"])

        invoices = check_for_old_invoices(provider_ids)  # type: ignore[arg-type] # Argument 1 to "check_for_old_invoices" has incompatible type "List[Union[str, Any]]"; expected "List[int]"

        return_schema = ProviderInvoiceListSchema()
        invoice_response = {"invoices": invoices}
        marshmallow_response = return_schema.dump(invoice_response).data
        if invoice_response != marshmallow_response:
            # There's PII, so I'm not logging that.
            log.info("FM - existing_invoice result discrepancy")
        else:
            log.info("FM - existing_invoice identical result")
        return marshmallow_response

    @expose("/generate_fees", methods=("POST",))
    def generate_fees(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        providers_validated_payments_csv = request.files.get(
            "providers_validated_payments_csv"
        )
        if not providers_validated_payments_csv:
            return {
                "error": "You need to upload a csv file with the validated payments info."
            }, 400

        payment_date_string = request.form.get("payment_date")
        payment_date = datetime.strptime(payment_date_string, "%m/%d/%Y").date()  # type: ignore[arg-type] # Argument 1 to "strptime" of "datetime" has incompatible type "Optional[Any]"; expected "str"
        if not payment_date:
            return {"error": "Please provide a date for this payment."}, 400

        date_delta = date.today() - payment_date
        if date_delta.days > 31:
            return {
                "error": "Please provide a date no more than one month prior to today for this payment."
            }, 400

        provider_amounts = {}
        with io.StringIO(
            providers_validated_payments_csv.stream.read().decode()
        ) as stream:
            reader = csv.DictReader(stream)
            required_headers = ["ID", "Final Payment Amount"]
            id_header, amount_header = required_headers
            if not set(map(str, required_headers)).issubset(reader.fieldnames):  # type: ignore[arg-type] # Argument 1 to "issubset" of "set" has incompatible type "Optional[Sequence[str]]"; expected "Iterable[Any]"
                return {
                    "error": f"Invalid csv file, file headers should be '{id_header}' and '{amount_header}' Found {reader.fieldnames}."
                }, 400
            log.info(
                "Create Fees - Starting generate fees from CSV",
                payment_date=payment_date,
            )

            errors = []
            for row in reader:
                try:
                    prac_id = row[id_header]
                    amount = row[amount_header]
                    processed_amount = self._generate_fees_process_row(
                        prac_id, amount, reader.line_num, provider_amounts
                    )
                except ValueError as ex:
                    errors.append(str(ex))
                    continue
                except Exception as ex:
                    # Log the actual exception as well as in the overall error log
                    log.error(
                        "Unknown exception in the generate_fees csv file",
                        line_num=reader.line_num,
                        exception=ex,
                    )
                    errors.append(f"An unknown error occured on row {reader.line_num}")
                    continue

                # Success
                if processed_amount:
                    provider_amounts[prac_id] = processed_amount

            # Validate prac_ids
            try:
                PractitionerProfile.validate_prac_ids_exist(
                    list(provider_amounts.keys())  # type: ignore[arg-type] # Argument 1 to "list" has incompatible type "dict_keys[Union[str, Any], Decimal]"; expected "Iterable[int]"
                )
            except ValueError as ex:
                # Exception args contains text and ids
                ex_message, invalid_practitioner_ids = ex.args
                errors.append(f"{ex_message}: {invalid_practitioner_ids}")

        if errors:
            log.error("Generate Fees has encountered errors", errors=errors)
            return {"error": "\n".join(errors)}, 400

        payment_datetime = datetime.combine(payment_date, datetime.min.time())
        fees = create_fees_with_date(provider_amounts, payment_datetime)

        return_schema = ProviderFeeListSchema()
        return return_schema.dump({"fees": fees}).data

    @classmethod
    def _generate_fees_process_row(
        cls, prac_id: str, amount: str, line_num: int, provider_amounts: dict = None  # type: ignore[assignment] # Incompatible default for argument "provider_amounts" (default has type "None", argument has type "Dict[Any, Any]")
    ) -> Decimal:
        if provider_amounts is None:
            provider_amounts = {}

        # Empty row - skip
        if not prac_id and not amount:
            return  # type: ignore[return-value] # Return value expected
        # Missing provider
        elif not prac_id:
            raise ValueError(f"Missing practitioner on row {line_num}.")
        # Missing amount
        elif not amount:
            raise ValueError(
                f"Missing amount for practitioner {prac_id} on row {line_num}."
            )
        # Format prac_id format
        try:
            prac_id = int(prac_id)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "int", variable has type "str")
        except ValueError:
            raise ValueError(
                f"Invalid number for practitioner {prac_id} on row {line_num}."
            )

        # Format amount value
        try:
            # Customized https://stackoverflow.com/a/354216 for our needs
            # Optional dollar sign, commas, periods as long as the overall format is correct
            if re.search(r"^[$]?[0-9]{1,3}(?:,?[0-9]{3})*(?:\.[0-9]{1,2})?$", amount):
                payment_amount = Decimal(re.sub("[$,]", "", amount))
            else:
                raise InvalidOperation
        except InvalidOperation:
            raise ValueError(
                f"Invalid amount for practitioner {prac_id} on row {line_num}."
            )
        # Multiple entries
        if prac_id in provider_amounts:
            raise ValueError(f"practitioner {prac_id} cannot have multiple payments.")

        return payment_amount

    @expose("/generate_invoices", methods=("POST",))
    def generate_invoices(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        generate_invoices_from_fees.delay(
            service_ns="provider_payments",
            team_ns="payments_platform",
            job_timeout=30 * 60,
        )

        return {"success": True}

    @expose("/invoice/", methods=("POST",))
    def create_invoice(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            request_json = request.json if request.is_json else {}
            practitioner_id = int(request_json["practitioner_id"])
            fee_amount_cents = int(request_json["fee_amount_cents"])
            if practitioner_id < 1 or fee_amount_cents < 1:
                return {
                    "success": False,
                    "error": "The provider id and the fee amount should be greater than 0.",
                }, 400
        except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
            return {
                "success": False,
                "error": "You must provide a practitioner id and the fee amount in cents.",
            }, 400

        inv = create_invoice_with_single_fee(practitioner_id, fee_amount_cents)
        if not inv:
            return {
                "success": False,
                "error": "Make sure the provider has the stripe account id set.",
            }, 400

        return {"success": True, "invoice_id": inv.id}

    @classmethod
    def _build_incomplete_invoices_response(cls, incomplete_invoices):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        incomplete_invoices_response = []
        for invoice in incomplete_invoices:
            account_status = _get_account_status(invoice.practitioner)
            incomplete_invoices_response.append(
                {
                    "invoice_id": invoice.id,
                    "practitioner_id": invoice.practitioner.id,
                    "practitioner_email": invoice.practitioner.email,
                    "amount_due": invoice.value,
                    "bank_account_status": account_status,
                    "stripe_account_id": invoice.recipient_id,
                }
            )
        return incomplete_invoices_response

    @expose("/incomplete_invoices", methods=("GET",))
    def incomplete_invoices(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        paginable_schema = PaginableArgsSchema()
        args = paginable_schema.load(request.args).data

        incomplete_invoices = db.session.query(Invoice).filter(
            Invoice.started_at.isnot(None),
            Invoice.completed_at.is_(None),
            Invoice.created_at >= datetime.utcnow() - relativedelta(months=3),
        )
        emit_bulk_audit_log_read(incomplete_invoices)

        total_incomplete_invoices = incomplete_invoices.count()

        offset = args.get("offset", 0)
        limit = args.get("limit", 10)
        incomplete_invoices = incomplete_invoices.offset(offset).limit(limit).all()

        order_direction = args.get("order_direction", "desc")
        if order_direction == "asc":
            incomplete_invoices = incomplete_invoices.order_by(Invoice.id)

        incomplete_invoices_response = (
            MonthlyPaymentsView._build_incomplete_invoices_response(incomplete_invoices)
        )

        pagination = {
            "limit": limit,
            "offset": offset,
            "total": total_incomplete_invoices,
            "order_direction": order_direction,
        }
        return {
            "pagination": pagination,
            "incomplete_invoices": incomplete_invoices_response,
            "success": True,
        }

    @expose("/sign_stripe_tos", methods=("POST",))
    def sign_stripe_tos(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        user_id = request.form.get("practitioner_id")
        account = self.sign_stripe_tos_with_user_id(user_id)

        if account and account.tos_acceptance.date is not None:
            log.info(f"Signed TOS for practitioner ID: {user_id}")
            flash("Success! TOS accepted")
            return redirect("/admin/practitioner_tools")
        else:
            abort(400, message="Could not sign TOS - check info and try again")

    def sign_stripe_tos_with_user_id(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = db.session.query(User).filter(User.id == user_id).one()

        stripe_client = self._stripe_client(user)
        connected_account = stripe_client.get_connect_account_for_user(user)
        if not connected_account:
            abort(400, message="Cannot get Stripe account!")

        # Pass the ip to accept/update terms of service
        accept_tos_ip = self.get_client_ip()
        try:
            account = stripe_client.accept_terms_of_service(user, accept_tos_ip)
        except AttributeError as e:
            log.error(e)
            abort(500)

        return account

    def get_client_ip(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return request.headers.get("X-Real-IP")

    def _stripe_client(self, user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        stripe_client = None
        if user.practitioner_profile:
            stripe_client = StripeConnectClient(api_key=PAYMENTS_STRIPE_API_KEY)
        else:
            log.warning(
                f"No profile found while trying to create a stripe client for {user}",
                profiles=(user.practitioner_profile, user.member_profile),
            )
            abort(403, message="You cannot access this!")
        return stripe_client

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            None,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


CONTRACTS_FORMATTING_HTML = (
    '<div class="control-group">'
    '    <div class="control-label">'
    "        <b>Fixed Hourly, Fixed Hourly Overnight, Hybrid, and W2 only:</b>"
    "    </div>"
    '    <div class="controls">'
    "        <ul>"
)


class PractitionerContractViewFullNameFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        query = query.outerjoin(PractitionerProfile)
        return query.filter(PractitionerProfile.full_name.like(f"%{value}%"))  # type: ignore[attr-defined] # overloaded function has no attribute "like"


class PractitionerContractView(MavenAuditedView):
    read_permission = "read:provider-contracts"
    create_permission = "create:provider-contracts"
    edit_permission = "edit:provider-contracts"
    delete_permission = "delete:provider-contracts"

    required_capability = "admin_practitioner_contract"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_list = (
        "id",
        "active",
        "practitioner.user_id",
        "practitioner.full_name",
        "practitioner.email",
        "contract_type",
        "start_date",
        "end_date",
        "weekly_contracted_hours",
        "created_by_user_id",
        "practitioner.verticals",
        "practitioner.is_international",
        "practitioner.active",
    )

    column_sortable_list = (
        "id",
        "active",
        "practitioner.user_id",
        "created_at",
        "contract_type",
        "start_date",
        "end_date",
        "weekly_contracted_hours",
        "created_by_user_id",
    )

    column_filters = (
        "id",
        PractitionerContractViewFullNameFilter(None, "Full Name"),
        "active",
        "practitioner.active",
        "practitioner.user_id",
        "contract_type",
        "start_date",
        "end_date",
        "weekly_contracted_hours",
        "created_by_user_id",
    )

    column_searchable_list = (
        "id",
        "practitioner.user_id",
        "created_by_user_id",
    )
    form_create_rules = (
        "practitioner",
        "contract_type",
        "start_date",
        "end_date",
        rules.Text(CONTRACTS_FORMATTING_HTML, escape=False),
        rules.NestedRule(
            rules=[
                "weekly_contracted_hours",
                "fixed_hourly_rate",
            ]
        ),
        rules.Text("<b>Fixed Hourly Overnight only:</b>", escape=False),
        "rate_per_overnight_appt",
        rules.Text("<b>Hybrid + Non-Standard By Appt only:</b>", escape=False),
        "hourly_appointment_rate",
        rules.Text("<b>Non-Standard By Appt only:</b>", escape=False),
        "non_standard_by_appointment_message_rate",
    )
    form_edit_rules = (
        ReadOnlyFieldRule("Practitioner ID", lambda model: model.practitioner.user_id),
        ReadOnlyFieldRule(
            "Practitioner Name", lambda model: model.practitioner.full_name
        ),
        ReadOnlyFieldRule("Contract Type", lambda model: model.contract_type),
        ReadOnlyFieldRule("Start Date", lambda model: model.start_date),
        "end_date",
        ReadOnlyFieldRule(
            "Weekly contracted hours",
            lambda model: model.weekly_contracted_hours
            if model.weekly_contracted_hours
            else "NA",
        ),
        ReadOnlyFieldRule(
            "Fixed hourly rate",
            lambda model: model.fixed_hourly_rate if model.fixed_hourly_rate else "NA",
        ),
        ReadOnlyFieldRule("Created by user id", lambda model: model.created_by_user_id),
        ReadOnlyFieldRule(
            "Rate per overnight appointment",
            lambda model: model.rate_per_overnight_appt
            if model.rate_per_overnight_appt
            else "NA",
        ),
        ReadOnlyFieldRule(
            "Hourly appointment rate",
            lambda model: model.hourly_appointment_rate
            if model.hourly_appointment_rate
            else "NA",
        ),
        ReadOnlyFieldRule(
            "Message rate",
            lambda model: model.non_standard_by_appointment_message_rate
            if model.non_standard_by_appointment_message_rate
            else "NA",
        ),
    )

    column_labels = {
        "practitioner.user_id": "Practitioner ID",
        "practitioner.full_name": "Practitioner Name",
        "practitioner.email": "Practitioner Email",
        "practitioner.verticals": "Practitioner Verticals",
        "practitioner.is_international": "International Practitioner",
        "active": "Active Contract",
        "practitioner.active": "Active Practitioner",
    }

    # Override get_list to set default filters
    def get_list(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        page,
        sort_column,
        sort_desc,
        search,
        filters,
        execute=True,
        page_size=None,
    ):
        # Refresh the characteristic filter options.
        self._refresh_filters_cache()
        # Add default filters only if no filters are manually indicated in url
        # Default to only showing active contracts and active practitioner profiles
        # Tuple properties: idx, flt_name, value
        # 10 and 8 are currently the correct index for these fields
        if len(filters) == 0:
            filters.append((10, "Active Contract", "1"))
            filters.append((8, "Active Practitioner", "1"))
        return super().get_list(
            page, sort_column, sort_desc, search, filters, execute, page_size
        )

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)
        model.created_by_user_id = login.current_user.id

    def _form_has_all_provider_contract_fields(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            hasattr(form, "practitioner")
            and form.practitioner.data
            and hasattr(form, "contract_type")
            and form.contract_type.data
            and hasattr(form, "start_date")
            and form.start_date.data
            and hasattr(form, "end_date")
            and hasattr(form, "weekly_contracted_hours")
            and hasattr(form, "fixed_hourly_rate")
        )

    def _form_has_new_end_date_field(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            hasattr(form, "_obj")
            and form._obj is not None
            and hasattr(form, "end_date")
            and form.end_date.data
            and form._obj.end_date != form.end_date.data
        )

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            if self._form_has_all_provider_contract_fields(form):  # for Create
                PractitionerContractService().validate_inputs_to_create_contract(
                    practitioner_id=form.practitioner.data.user_id,
                    created_by_user_id=login.current_user.id,
                    contract_type_str=form.contract_type.data,
                    start_date=form.start_date.data,
                    end_date=form.end_date.data,
                    weekly_contracted_hours=form.weekly_contracted_hours.data,
                    fixed_hourly_rate=form.fixed_hourly_rate.data,
                    rate_per_overnight_appt=form.rate_per_overnight_appt.data,
                    hourly_appointment_rate=form.hourly_appointment_rate.data,
                    non_standard_by_appointment_message_rate=form.non_standard_by_appointment_message_rate.data,
                )
            elif self._form_has_new_end_date_field(form):  # for Edit
                PractitionerContractService().validate_new_end_date(
                    contract=form._obj,
                    new_end_date=form.end_date.data,
                )

        except InvalidPractitionerContractInputsException as e:
            db.session.rollback()
            flash(e.message)  # type: ignore[attr-defined] # "InvalidPractitionerContractInputsException" has no attribute "message"
            return

        return super().validate_form(form)

    def delete_model(self, model: PractitionerContract) -> bool:
        duplicate_contract_exists = bool(
            PractitionerContract.query.filter(
                PractitionerContract.practitioner_id == model.practitioner_id,
            ).count()
            > 0
        )
        if not duplicate_contract_exists:
            flash(
                "Only duplicate contracts may be deleted. "
                "No other contracts found with duplicate practitioner id, contract_type, and dates.",
                "error",
            )
            return False

        # If the contract is a duplicate of another contract, it may be deleted. (This state arises through contract imports via a file, I believe.)
        return super().delete_model(model)

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            PractitionerContract,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class InvoiceView(MavenAuditedView):
    read_permission = "read:invoice"
    edit_permission = "edit:invoice"

    required_capability = "admin_invoice"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    edit_template = "invoice_edit_template.html"
    column_sortable_list = ("id", "started_at", "created_at", "completed_at")
    column_list = column_sortable_list + ("practitioner", "value")
    column_labels = {"value": "Amount"}
    column_exclude_list = ("modified_at", "json", "transfer_id")
    column_filters = (
        "completed_at",
        "failed_at",
        "started_at",
        "id",
        InvoicePractitionerIDFilter(None, "Practitioner ID"),
        InvoicePractitionerIDEmptyFilter(None, "Practitioner ID"),
        InvoiceForDistributedPractitionersFilter(
            None, "Distributed Network Practitioner"
        ),
    )
    column_searchable_list = ("transfer_id", "recipient_id")

    form_rules = []
    form_widget_args = {}

    for f in (
        "recipient_id",
        "transfer_id",
        "created_at",
        "started_at",
        "completed_at",
        "failed_at",
    ):
        form_rules.append(f)
        form_widget_args[f] = {"disabled": True}

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        id = get_mdict_item_or_list(request.args, "id")
        model = None
        if id:
            model = self.get_one(id)

        if model:
            stripe = StripeConnectClient(PAYMENTS_STRIPE_API_KEY)
            if model.practitioner:
                self._template_args["account"] = stripe.get_bank_account_for_user(
                    model.practitioner
                )
            else:
                self._template_args["account"] = None

            self._template_args["can_be_pay"] = all(
                arg is None
                for arg in [
                    model.started_at,
                    model.failed_at,
                    model.completed_at,
                    model.transfer_id,
                ]
            )
            self._template_args["can_be_closed"] = all(
                arg is None for arg in [model.started_at]
            )

        return super().edit_view()

    @expose("/pay/", methods=("POST",))
    def pay(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_json = request.json if request.is_json else {}
        invoice_id = int(request_json["invoice_id"])
        try:
            with RedisLock(f"{invoice_id}_invoice_transfer_in_progress", expires=60):
                self._start_invoice_transfers([invoice_id])
        except LockTimeout:
            return {
                "success": False,
                "error": "This invoice transfer is already in progress",
            }, 423
        except Exception as e:
            return {"success": False, "error": str(e)}, 400

        return {"success": True}

    @expose("/close/", methods=("POST",))
    def close(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_json = request.json if request.is_json else {}
        invoice_id = int(request_json["invoice_id"])
        try:
            with RedisLock(f"{invoice_id}_close_invoice_in_progress", expires=60):
                invoice_closed = self._close_invoice(invoice_id)
        except LockTimeout:
            return {
                "success": False,
                "error": "Could not close invoice",
            }, 400
        except Exception as e:
            return {"success": False, "error": str(e)}, 400

        return {"success": invoice_closed}

    @action("start_transfers", "Start Transfers", "You Sure?")
    def start_transfers(self, invoice_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            with RedisLock("invoice_transfers_in_progress", expires=60):
                log.info("Starting invoice transfers", invoice_ids=invoice_ids)
                self._start_invoice_transfers(invoice_ids)
                return
        except LockTimeout:
            lock_timeout_msg = (
                "Other invoice transfers already in progress, wait a bit and try again."
            )
            flash(lock_timeout_msg)
            return lock_timeout_msg
        except Exception as e:
            log.error("Error when starting transfer(s)", exception=e)
            return f"Error when starting transfer. Errors per invoice id: {e}"

    def _close_invoice(self, invoice_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        invoice = db.session.query(Invoice).get(invoice_id)
        invoice_closed = invoice.close_invoice()
        if invoice_closed:
            db.session.add(invoice)
            emit_audit_log_update(invoice)
            db.session.commit()
        return invoice_closed

    def _start_invoice_transfers(self, invoice_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        invoices = db.session.query(Invoice).filter(Invoice.id.in_(invoice_ids)).all()
        transfer_errors = {}
        for invoice in invoices:
            try:
                invoice.start_transfer()
                db.session.add(invoice)
                emit_audit_log_update(invoice)
                db.session.commit()
            except Exception as e:
                transfer_errors[invoice.id] = str(e)
        if len(transfer_errors) > 0:
            raise Exception(str(transfer_errors))

    @action("reset_transfer", "Reset Transfer", "You Sure?")
    def reset_transfer(self, invoice_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(invoice_ids) != 1:
            log.error("Only one invoice ID allowed!")
            abort(400)

        invoice = db.session.query(Invoice).filter(Invoice.id.in_(invoice_ids)).one()

        _audit = {
            "transfer_id": invoice.transfer_id,
            "started_at": str(invoice.started_at),
            "completed_at": str(invoice.completed_at),
            "failed_at": str(invoice.failed_at),
            "json": invoice.json,
            "invoice_id": invoice.id,
        }

        invoice.transfer_id = None
        invoice.started_at = None
        invoice.completed_at = None
        invoice.failed_at = None
        invoice.json = {}

        audit("reset_invoice", **_audit)
        db.session.add(invoice)
        db.session.commit()

        log.info("All set resetting transfer for invoice: %s", invoice)

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            Invoice,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AppointmentFeeCreatorView(MavenAuditedView):
    read_permission = "read:appointment-fee-creator"
    delete_permission = "delete:appointment-fee-creator"
    create_permission = "create:appointment-fee-creator"
    edit_permission = "edit:appointment-fee-creator"

    required_capability = "admin_appointment_fee_creator"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_exclude_list = ("modified_at", "members")
    column_sortable_list = ("practitioner", "valid_from", "valid_to", "created_at")
    column_filters = ("valid_from", "valid_to", "user_id", "fee_percentage")

    form_rules = ["fee_percentage", "practitioner", "members", "valid_from", "valid_to"]

    form_ajax_refs = {
        "members": {
            "fields": ("first_name", "last_name", "username", "email"),
            "page_size": 10,
        },
        "practitioner": {
            "fields": ("first_name", "last_name", "username", "email"),
            "page_size": 10,
        },
    }

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            AppointmentFeeCreator,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class IncentivePaymentView(MavenAuditedView):
    create_permission = "create:incentive-payment"
    edit_permission = "edit:incentive-payment"
    read_permission = "read:incentive-payment"

    required_capability = "admin_referral_codes"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_filters = ("incentive_paid", "referral_code_use.user_id")
    column_list = (
        "referral_code_value.payment_rep",
        "referral_code_value.rep_email_address",
        "referral_code_value.code.user",
        "referral_code_value.payment_user",
        "referral_code_value.user_payment_type",
        "incentive_paid",
    )

    @action(
        "mark_incentives_paid",
        "Mark Incentives Paid",
        "This will mark the selected incentives as paid.",
    )
    def mark_incentive_payments_paid(self, incentive_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        ips = db.session.query(IncentivePayment).filter(
            IncentivePayment.id.in_(incentive_ids)
        )
        for ip in ips:
            ip.incentive_paid = True
        db.session.commit()

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            IncentivePayment,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


def check_for_old_invoices(practitioner_ids: List[int]) -> List[dict]:
    practitioner_invoices = []
    for practitioner_id in practitioner_ids:
        invoices_and_practitioner_profile = (
            db.session.query(Invoice, PractitionerProfile)
            .join(
                PractitionerProfile,
                Invoice.recipient_id == PractitionerProfile.stripe_account_id,
            )
            .filter(Invoice.started_at == None)
            .filter(PractitionerProfile.user_id == practitioner_id)
            .all()
        )

        for i_and_pp in invoices_and_practitioner_profile:
            i, pp = i_and_pp
            emit_audit_log_read(i)
            practitioner_invoices.append(
                {
                    "invoiceId": i.id,
                    "invoiceCreatedAt": i.created_at,
                    "practitionerId": practitioner_id,
                    "isStaff": pp.is_staff,
                    "total": i.value,
                    "fees": len(i.entries),
                }
            )
    return practitioner_invoices


def create_fees_with_date(
    practitioner_amounts: dict, payment_date: datetime
) -> List[dict]:
    fees = []
    new_entry_ids = []

    for prac_id, payment_amount in practitioner_amounts.items():
        if payment_amount <= 0:
            status = f"Skipping: row: {payment_date}, amount={payment_amount}"
            fees.append(
                {
                    "practitioner_id": prac_id,
                    "amount": payment_amount,
                    "status": status,
                }
            )
            continue

        if prac_id is None:
            status = f"Skipping: row: {payment_date}, amount={payment_amount}"
            fees.append(
                {
                    "practitioner_id": prac_id,
                    "amount": payment_amount,
                    "status": status,
                }
            )
            continue
        prac = PractitionerProfile.query.get(prac_id)

        if prac is None:
            status = f"Skipping: pract={prac} could not find"
            fees.append(
                {
                    "practitioner_id": prac_id,
                    "amount": payment_amount,
                    "status": status,
                }
            )
            continue

        fae = FeeAccountingEntry(
            amount=payment_amount,
            practitioner_id=prac.user_id,
            type=FeeAccountingEntryTypes.ONE_OFF,
        )
        fae.created_at = payment_date

        db.session.add(fae)

        log.info("Create Fees - Trying to create fee accounting entry", fee=fae)
        db.session.flush()
        new_entry_ids.append(fae.id)

        status = f"Fee accounting entry creation on {payment_date} successful"
        fees.append(
            {
                "fae_id": fae.id,
                "practitioner_id": fae.practitioner_id,
                "practitioner_name": fae.practitioner.full_name,
                "amount": fae.amount,
                "status": status,
            }
        )

    db.session.commit()
    new_entries = (
        db.session.query(FeeAccountingEntry)
        .filter(FeeAccountingEntry.id.in_(new_entry_ids))
        .all()
    )
    log.info("Create Fees - Fee accounting entries created", ids=new_entry_ids)

    emit_bulk_audit_log_create(new_entries)

    return fees


def create_invoice_with_single_fee(
    practitioner_id: int, fee_amount_cents: int
) -> Optional[Invoice]:
    practitioner = User.query.get(practitioner_id)
    if not (practitioner and practitioner.practitioner_profile):
        return  # type: ignore[return-value] # Return value expected

    fae = FeeAccountingEntry(
        amount=fee_amount_cents / 100,
        practitioner_id=practitioner.id,
        type=FeeAccountingEntryTypes.NON_STANDARD_HOURLY,
    )

    db.session.add(fae)
    db.session.commit()
    emit_audit_log_create(fae)

    inv = Invoice()
    inv.recipient_id = practitioner.practitioner_profile.stripe_account_id
    inv.add_entry(fae)
    if len(inv.entries) == 0:
        db.session.delete(fae)
        db.session.commit()
        emit_audit_log_delete(fae)
        return  # type: ignore[return-value] # Return value expected

    db.session.add(inv)
    db.session.commit()
    emit_audit_log_create(inv)

    return inv
