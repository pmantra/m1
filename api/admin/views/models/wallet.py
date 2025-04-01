from __future__ import annotations

import datetime
import io
from decimal import Decimal
from functools import reduce
from re import compile
from traceback import format_exc
from typing import Any, Callable, List, Optional, Set, Type
from uuid import UUID

import flask_login as login
import pycountry
import pytz
import sqlalchemy
import wtforms
from flask import Response, abort, flash, jsonify, redirect, request, send_file, url_for
from flask_admin import expose
from flask_admin.actions import action
from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader
from flask_admin.contrib.sqla.filters import BooleanEqualFilter
from flask_admin.form import BaseForm, Select2Widget
from flask_admin.form.fields import Select2Field
from flask_admin.model import InlineFormAdmin
from flask_admin.model.helpers import get_mdict_item_or_list
from markupsafe import Markup
from sqlalchemy import func, or_, orm
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from werkzeug.routing import RequestRedirect
from wtforms import BooleanField, SelectField, fields, validators
from wtforms.validators import InputRequired

import eligibility
from admin.common import CustomFiltersAjaxModelLoader, SnowflakeQueryAjaxModelLoader
from admin.views.base import (
    AdminCategory,
    AdminViewT,
    AmountDisplayCentsInDollarsField,
    ContainsFilter,
    CustomFormField,
    IsFilter,
    MavenAuditedView,
    PerInlineModelConverterMixin,
    ReadOnlyFieldRule,
    cents_to_dollars_formatter,
)
from audit_log.utils import emit_bulk_audit_log_create, emit_bulk_audit_log_update
from authn.models.user import User
from authn.resources.admin import BaseClassicalMappedView
from common.document_mapper.helpers import (
    partial_ratio,
    receipt_validation_ops_view_enabled,
)
from cost_breakdown.constants import ClaimType
from cost_breakdown.models.cost_breakdown import (
    CostBreakdown,
    ReimbursementRequestToCostBreakdown,
)
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.models import PayorType
from direct_payment.pharmacy.automated_reimbursement_request_service import (
    AutomatedReimbursementRequestService,
)
from direct_payment.pharmacy.models.ingestion_meta import TaskType
from direct_payment.pharmacy.pharmacy_prescription_service import (
    PharmacyPrescriptionService,
)
from direct_payment.pharmacy.repository.health_plan_ytd_spend import (
    HealthPlanYearToDateSpendRepository,
)
from direct_payment.pharmacy.repository.ingestion_meta_repository import (
    IngestionMetaRepository,
)
from direct_payment.pharmacy.repository.pharmacy_prescription import (
    PharmacyPrescriptionRepository,
)
from direct_payment.pharmacy.tasks.esi_claim_ingestion_job import ingest
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureType,
)
from eligibility import e9y
from models.actions import ACTIONS
from models.actions import audit as model_audit
from models.enterprise import Organization, UserAsset
from payer_accumulator.accumulation_data_sourcer import AccumulationDataSourcer
from payer_accumulator.accumulation_data_sourcer_esi import AccumulationDataSourcerESI
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_list import Payer
from payer_accumulator.tasks.rq_payer_accumulation_file_generation import (
    AccumulationFileGenerationJob,
)
from storage.connection import RoutingSQLAlchemy, db
from utils.log import logger
from utils.slack_v2 import notify_payment_ops_channel
from wallet.constants import INTERNAL_TRUST_DOCUMENT_MAPPER_URL
from wallet.models.annual_insurance_questionnaire_response import (
    AnnualInsuranceQuestionnaireResponse,
)
from wallet.models.constants import (
    BenefitTypes,
    CardStatusReason,
    CategoryRuleAccessLevel,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestSourceUploadSource,
    ReimbursementRequestState,
    ReimbursementRequestType,
    SyncIndicator,
    WalletReportConfigCadenceTypes,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.currency import Money
from wallet.models.member_benefit import MemberBenefit
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent
from wallet.models.reimbursement import (
    ReimbursementAccount,
    ReimbursementAccountType,
    ReimbursementClaim,
    ReimbursementPlan,
    ReimbursementPlanCoverageTier,
    ReimbursementRequest,
    ReimbursementRequestCategory,
    ReimbursementRequestExchangeRates,
    ReimbursementServiceCategory,
    ReimbursementTransaction,
    ReimbursementWalletPlanHDHP,
    WalletExpenseSubtype,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
    ReimbursementOrgSettingsAllowedCategoryRule,
    ReimbursementOrgSettingsExpenseType,
)
from wallet.models.reimbursement_request_source import (
    ReimbursementRequestSource,
    ReimbursementRequestSourceRequests,
)
from wallet.models.reimbursement_wallet import (
    CountryCurrencyCode,
    MemberHealthPlan,
    ReimbursementWallet,
    ReimbursementWalletAllowedCategorySettings,
    ReimbursementWalletCategoryRuleEvaluationResult,
)
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.models.reimbursement_wallet_billing import ReimbursementWalletBillingConsent
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.models.reimbursement_wallet_dashboard import (
    ReimbursementWalletDashboard,
    ReimbursementWalletDashboardCard,
    ReimbursementWalletDashboardCards,
)
from wallet.models.reimbursement_wallet_debit_card import ReimbursementWalletDebitCard
from wallet.models.reimbursement_wallet_e9y_blacklist import (
    ReimbursementWalletBlacklist,
)
from wallet.models.reimbursement_wallet_eligibility_sync import (
    ReimbursementWalletEligibilitySyncMeta,
)
from wallet.models.reimbursement_wallet_global_procedures import (
    ReimbursementWalletGlobalProcedures,
)
from wallet.models.reimbursement_wallet_report import (
    WalletClientReportConfiguration,
    WalletClientReportConfigurationFilter,
    WalletClientReportReimbursements,
    WalletClientReports,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.models.wallet_user_consent import WalletUserConsent
from wallet.models.wallet_user_invite import WalletUserInvite
from wallet.repository.member_benefit import MemberBenefitRepository
from wallet.services.currency import CurrencyService
from wallet.services.document_mapper_service import DocumentMapperService
from wallet.services.reimbursement_category_activation_constants import (
    RULE_REGISTRATION_MAP,
)
from wallet.services.reimbursement_category_activation_visibility import (
    CategoryActivationService,
)
from wallet.services.reimbursement_request import create_appeal
from wallet.services.reimbursement_request_state_change import (
    handle_reimbursement_request_card_transaction_state_change,
    handle_reimbursement_request_state_change,
)
from wallet.services.reimbursement_wallet_e9y_service import WalletEligibilityService
from wallet.services.reimbursement_wallet_messaging import (
    get_or_create_rwu_channel,
    open_zendesk_ticket,
)
from wallet.services.reimbursement_wallet_state_change import (
    handle_wallet_settings_change,
    handle_wallet_state_change,
)
from wallet.services.wallet_client_reporting import (
    assign_reimbursements_to_report,
    download_selected_client_reports,
    download_zipped_client_reports,
)
from wallet.services.wallet_client_reporting_constants import (
    WalletReportConfigFilterCountry,
    WalletReportConfigFilterType,
)
from wallet.tasks.alegeus import update_or_create_dependent_demographics
from wallet.tasks.document_mapping import map_reimbursement_request_documents
from wallet.utils.admin_helpers import FlashMessageCategory
from wallet.utils.alegeus.debit_cards.manage import (
    report_lost_stolen_debit_card,
    request_debit_card,
)
from wallet.utils.alegeus.enrollments.enroll_wallet import (
    configure_wallet_allowed_category,
)
from wallet.utils.common import increment_reimbursement_request_field_update
from wallet.utils.currency import (
    format_display_amount_with_currency_code,
    format_display_amount_with_full_currency_name,
)

user_id_reg = compile(
    r"\[user_id=(\d+), email=(.*?), zendesk_ticket_id=(.*?), member_hash_id=(.*?), wallet_user_status=(.*?)]"
)

log = logger(__name__)


class HasDebitCardFilter(BooleanEqualFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "1":
            return query.filter(ReimbursementWallet.debit_card != None)
        else:
            return query.filter(ReimbursementWallet.debit_card == None)


class WalletBenefitIdFilter(IsFilter):
    def apply(self, query, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementWalletBenefit,
                ReimbursementWalletBenefit.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .join(
                MemberBenefit, MemberBenefit.user_id == ReimbursementWalletUsers.user_id
            )
            .filter(
                or_(
                    ReimbursementWalletBenefit.maven_benefit_id == value,
                    func.lower(MemberBenefit.benefit_id) == func.lower(value),
                )
            )
        )


class ReimbursementRequestSourceMemberEmailFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementRequestSource.reimbursement_wallet_id,
            )
            .join(User, ReimbursementWalletUsers.user_id == User.id)
            .filter(User.email == value)
        )


class ReimbursementRequestSourceUserIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            ReimbursementWalletUsers,
            ReimbursementWalletUsers.reimbursement_wallet_id
            == ReimbursementRequestSource.reimbursement_wallet_id,
        ).filter(ReimbursementWalletUsers.user_id == value)


class ReimbursementAccountUserIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            ReimbursementWalletUsers,
            ReimbursementWalletUsers.reimbursement_wallet_id
            == ReimbursementAccount.reimbursement_wallet_id,
        ).filter(
            ReimbursementWalletUsers.user_id == value,
            ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
        )


class ReimbursementRequestHasZendeskTicketIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            ReimbursementWalletUsers,
            ReimbursementWalletUsers.reimbursement_wallet_id
            == ReimbursementRequest.reimbursement_wallet_id,
        ).filter(ReimbursementWalletUsers.zendesk_ticket_id == value)


class ReimbursementRequestHasUserIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            ReimbursementWalletUsers,
            ReimbursementWalletUsers.reimbursement_wallet_id
            == ReimbursementRequest.reimbursement_wallet_id,
        ).filter(ReimbursementWalletUsers.user_id == value)


class ReimbursementRequestHasEmailAddress(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementRequest.reimbursement_wallet_id,
            )
            .join(User, User.id == ReimbursementWalletUsers.user_id)
            .filter(User.email == value)
        )


class ReimbursementRequestBenefitIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementWalletBenefit,
                ReimbursementWalletBenefit.reimbursement_wallet_id
                == ReimbursementRequest.reimbursement_wallet_id,
            )
            .join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementRequest.reimbursement_wallet_id,
            )
            .join(
                MemberBenefit, MemberBenefit.user_id == ReimbursementWalletUsers.user_id
            )
            .filter(
                or_(
                    ReimbursementWalletBenefit.maven_benefit_id == value,
                    func.lower(MemberBenefit.benefit_id) == func.lower(value),
                )
            )
        )


class WalletHasZendeskTicketIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            ReimbursementWalletUsers,
            ReimbursementWalletUsers.reimbursement_wallet_id == ReimbursementWallet.id,
        ).filter(ReimbursementWalletUsers.zendesk_ticket_id == value)


class ReimbursemenWalletUsersHasChannelIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(value, str) and value.strip().lower() == "none":
            value = None
        return query.filter(ReimbursementWalletUsers.channel_id == value)


class ReimbursemenWalletUsersHasZendeskTicketIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(value, str) and value.strip().lower() == "none":
            value = None
        return query.filter(ReimbursementWalletUsers.zendesk_ticket_id == value)


class WalletHasUserIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            ReimbursementWalletUsers,
            ReimbursementWalletUsers.reimbursement_wallet_id == ReimbursementWallet.id,
        ).filter(ReimbursementWalletUsers.user_id == value)


class WalletHasEmailAddressFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .join(User, User.id == ReimbursementWalletUsers.user_id)
            .filter(User.email == value)
        )


class WalletHasEspIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .join(User, User.id == ReimbursementWalletUsers.user_id)
            .filter(User.esp_id == value)
        )


def total_reimbursed_formatter(wallet: ReimbursementWallet):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    categories: List[
        ReimbursementOrgSettingCategoryAssociation
    ] = wallet.get_or_create_wallet_allowed_categories
    category_types: List[BenefitTypes] = [c.benefit_type for c in categories]

    if not category_types:
        return "NO CATEGORIES CONFIGURED"

    if all(c == BenefitTypes.CYCLE for c in category_types):
        return "CYCLE BASED"

    if BenefitTypes.CYCLE in category_types:
        return "CYCLE AND CURRENCY CATEGORIES CONFIGURED"

    # Categories are all BenefitTypes.CURRENCY at this point
    category_currencies: set[str] = set(
        str(c.currency_code or "USD") for c in categories
    )

    if len(category_currencies) > 1:
        return "MULTIPLE CURRENCIES CONFIGURED"

    wallet_currency: str = category_currencies.pop()

    currency_service = CurrencyService()

    reimbursed_amount: Money = currency_service.to_money(
        amount=wallet.total_reimbursed_amount, currency_code=wallet_currency
    )
    available_amount: Money = currency_service.to_money(
        amount=wallet.total_available_amount, currency_code=wallet_currency
    )
    reimbursed_formatted: str = format_display_amount_with_currency_code(
        money=reimbursed_amount
    )
    available_formatted: str = format_display_amount_with_currency_code(
        money=available_amount
    )

    return f"{reimbursed_formatted} of {available_formatted}"


class InlineOrganizationEmployeeDependentForm(InlineFormAdmin):
    form_columns = (
        "id",
        "first_name",
        "middle_name",
        "last_name",
        "alegeus_dependent_id",
        "reimbursement_wallet",
    )
    form_widget_args = {
        "alegeus_dependent_id": {"disabled": True},
    }
    form_ajax_refs = {
        "reimbursement_wallet": SnowflakeQueryAjaxModelLoader(
            "reimbursement_wallet",
            db.session,
            ReimbursementWallet,
            fields=("id",),
            page_size=10,
        ),
    }

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if is_created:
            model.create_alegeus_dependent_id()

        super().on_model_change(form, model, is_created)

        if (
            form.first_name.object_data != form.first_name.data
            or form.last_name.object_data != form.last_name.data
        ):
            update_or_create_dependent_demographics.delay(
                model.reimbursement_wallet.id,
                model.id,
                is_created,
                team_ns="payments_platform",
            )


class OrganizationEmployeeDependentView(MavenAuditedView):
    create_permission = "create:reimbursement-wallet-authorized-user-dependent"
    edit_permission = "edit:reimbursement-wallet-authorized-user-dependent"
    delete_permission = "delete:reimbursement-wallet-authorized-user-dependent"
    read_permission = "read:reimbursement-wallet-authorized-user-dependent"

    column_list = (
        "id",
        "alegeus_dependent_id",
        "first_name",
        "middle_name",
        "last_name",
        "reimbursement_wallet_id",
    )
    column_filters = (
        "id",
        "first_name",
        "last_name",
        "middle_name",
        "reimbursement_wallet_id",
    )
    form_excluded_columns = "alegeus_dependent_id"
    column_searchable_list = ("id", "reimbursement_wallet_id")

    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._form_ajax_refs = {
            "reimbursement_wallet": SnowflakeQueryAjaxModelLoader(
                "reimbursement_wallet",
                self.session,
                ReimbursementWallet,
                fields=("id",),
                page_size=10,
            ),
        }
        return self._form_ajax_refs

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        model = super().create_model(form)
        model.create_alegeus_dependent_id()
        return model

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
            OrganizationEmployeeDependent,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletView(MavenAuditedView):
    create_permission = "create:reimbursement-wallet"
    edit_permission = "edit:reimbursement-wallet"
    delete_permission = "delete:reimbursement-wallet"
    read_permission = "read:reimbursement-wallet"

    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    can_view_details = True
    create_template = "reimbursement_wallet_create_template.html"
    edit_template = "reimbursement_wallet_edit_template.html"
    column_list = (
        "id",
        "user_info",
        "reimbursement_organization_settings",
        "reimbursement_organization_settings.organization.name",
        "state",
        "created_at",
        # TODO: [multitrack] Use currentmember_track_formatter from views/models/profiles.py?
        "total_reimbursed",
        "reimbursement_method",
        "taxation_status",
    )
    column_labels = {
        "id": "Wallet Id",
        "user_info": "Wallet User Info",
        "reimbursement_organization_settings.organization.id": "Organization ID",
        "reimbursement_organization_settings.organization.name": "Organization Name",
        "reimbursement_organization_settings.id": "Reimbursement Organization Settings ID",
        "reimbursement_organization_settings.name": "Reimbursement Organization Settings Name",
        "note": "Note (record reason for any disqualified state here)",
        "reimbursement_hdhp_plans": "High Deductible Health Plans",
        "taxation_status": "Taxation Status",
        "reimbursement_wallet_benefit.maven_benefit_id": "Benefit ID",
        "member_health_plan": "Employee Health Plan",
        "authorized_users": "Wallet Authorized Users (Dependents)",
    }
    form_columns = (
        "reimbursement_organization_settings",
        "member",
        "state",
        "note",
        "reimbursement_method",
        "reimbursement_hdhp_plans",
        "member_health_plan",
        "taxation_status",
        "debit_card",
        "primary_expense_type",
        "payments_customer_id",
        "authorized_users",
    )
    column_sortable_list = (
        "reimbursement_organization_settings.organization.name",
        "state",
        "taxation_status",
    )
    column_filters = (
        "id",
        "state",
        "reimbursement_organization_settings.organization.id",
        "reimbursement_organization_settings.organization.name",
        "reimbursement_organization_settings.id",
        "reimbursement_organization_settings.name",
        "reimbursement_method",
        "taxation_status",
        HasDebitCardFilter(None, "Has Debit Card"),
        WalletHasZendeskTicketIdFilter(None, "Has Zendesk Ticket Id"),
        WalletHasUserIdFilter(None, "Has User Id"),
        WalletHasEmailAddressFilter(None, "Has Email Address"),
        WalletHasEspIdFilter(None, "Has ESP Id / Program Module Name"),
        "alegeus_id",
        WalletBenefitIdFilter(None, "Benefit Id"),
        "payments_customer_id",
    )

    def _user_info_formatter(self, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        text = model.user_info
        user_id_strings = user_id_reg.findall(text)
        output = Markup("")
        # This should rarely exceed 2 users
        for (
            user_id,
            email,
            zendesk_ticket_id,
            member_hash_id,
            wallet_user_status,
        ) in user_id_strings:
            user_url = url_for("user.index_view", flt0_0=user_id)
            rwu_url = url_for("reimbursementwalletusers.index_view", flt2_14=user_id)
            email = email.strip("\"'")
            zendesk_ticket_id = zendesk_ticket_id.strip("\"'")
            member_hash_id = member_hash_id.strip("\"'")
            wallet_user_status = wallet_user_status.strip("\"'")
            output += Markup(
                f'[<a href="{user_url}">User<{user_id}></a>, {email=}, {zendesk_ticket_id=}, {member_hash_id=}, '
                f'<a href="{rwu_url}">Wallet User</a>={wallet_user_status}]\n'
            )

        return output

    column_formatters = {
        "total_reimbursed": lambda v, c, m, p: total_reimbursed_formatter(wallet=m),
        "user_info": _user_info_formatter,
    }

    inline_models = (
        (
            ReimbursementWalletPlanHDHP,
            {"form_excluded_columns": ("created_at", "modified_at")},
        ),
        (MemberHealthPlan, {"form_excluded_columns": ("created_at", "modified_at")}),
        (InlineOrganizationEmployeeDependentForm(OrganizationEmployeeDependent)),
    )

    form_ajax_refs = {
        "member": {"fields": ("id", "email"), "page_size": 10},
        "reimbursement_organization_settings": CustomFiltersAjaxModelLoader(
            "reimbursement_organization_settings",
            db.session,
            ReimbursementOrganizationSettings,
            joins=[ReimbursementOrganizationSettings.organization],
            fields=(
                ReimbursementOrganizationSettings.id,
                ReimbursementOrganizationSettings.name,
                Organization.name,
            ),
            page_size=10,
        ),
    }

    _auto_joins = [
        ReimbursementOrganizationSettings,
        ReimbursementOrganizationSettings.organization,
    ]

    @db.from_app_replica
    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        model_id = get_mdict_item_or_list(request.args, "id")
        if not model_id:
            abort(404)
        model = self.get_one(model_id)
        if not model:
            abort(404)

        member_benefit_repository = MemberBenefitRepository(session=self.session)
        member_benefits: List[
            MemberBenefit
        ] = member_benefit_repository.get_by_wallet_id(wallet_id=model.id)
        self._template_args["member_benefits"] = member_benefits

        return super().edit_view()

    def edit_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form = super().edit_form(obj)
        # Only show debit cards linked to this wallet
        form.debit_card.query = self.session.query(ReimbursementWalletDebitCard).filter(
            ReimbursementWalletDebitCard.reimbursement_wallet_id == obj.id
        )
        return form

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # All validation & etc must happen before we commit the new model
        try:
            self.validate_new_data(form)
        except ValueError as error:
            flash(message=str(error), category=FlashMessageCategory.ERROR)
            return

        if hasattr(form, "member_health_plans") and form.member_health_plans.data:
            for plan in form.member_health_plans.data:
                if "plan_end_at" in plan and isinstance(
                    plan["plan_end_at"], datetime.datetime
                ):
                    plan["plan_end_at"] = datetime.datetime.combine(
                        plan["plan_end_at"].date(), datetime.time(23, 59, 59)
                    )
                if "plan_start_at" in plan and isinstance(
                    plan["plan_start_at"], datetime.datetime
                ):
                    plan["plan_start_at"] = datetime.datetime.combine(
                        plan["plan_start_at"].date(), datetime.time(00, 00, 00)
                    )

        # update the model to the new data
        model = super().create_model(form)

        verification_svc: eligibility.EnterpriseVerificationService = (
            eligibility.get_verification_service()
        )
        verification: Optional[
            e9y.EligibilityVerification
        ] = verification_svc.get_verification_for_user_and_org(
            user_id=model.member.id,
            organization_id=model.reimbursement_organization_settings.organization_id,
        )
        eligibility_member_id = (
            verification.eligibility_member_id if verification else None
        )

        # Todo: get initial_eligibility_verification_id
        #  once reading from new data model enabled in e9y

        model.initial_eligibility_member_id = eligibility_member_id
        # Handle audit and braze events
        # TODO: replace with call to new audit method (55854)

        # note: since there is no state change here (NONE), there will be no flash messages to handle, only an audit log
        handle_wallet_state_change(model, None, headers=request.headers)  # type: ignore[arg-type] # Argument "headers" to "handle_wallet_state_change" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
        user_id = form.member.data.id
        reimbursement_wallet_user = self.get_or_create_reimbursement_wallet_user(
            model, user_id
        )
        # add maven wallet channel
        get_or_create_rwu_channel(reimbursement_wallet_user)
        # create solved ticket in zendesk to enable communication
        open_zendesk_ticket(reimbursement_wallet_user)
        if hasattr(model, "member_health_plan") and model.member_health_plan:
            self.force_health_plan_dates(model.member_health_plan)
        return model

    def update_model(self, form, model: ReimbursementWallet):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # All validation & etc must happen before we commit the new model
        try:
            self.validate_new_data(form)
        except ValueError as error:
            flash(message=str(error), category=FlashMessageCategory.ERROR)
            return

        old_state = WalletState(model.state)
        new_state = WalletState(form.state.data)
        needs_state_change = new_state != old_state

        old_hdhp_plans_count = len(model.reimbursement_hdhp_plans)
        new_hdhp_plans_count = len(form.reimbursement_hdhp_plans.data)
        old_ros_id = model.reimbursement_organization_settings_id
        new_ros_id = form.reimbursement_organization_settings.data.id

        needs_alegeus_configuration = (
            new_hdhp_plans_count > old_hdhp_plans_count or old_ros_id != new_ros_id
        )

        # update the model to the new data
        model_updated = super().update_model(form, model)
        log.info(
            "Updating Wallet",
            old_state=old_state.value,  # type: ignore
            new_state=new_state.value,  # type: ignore
        )
        if needs_state_change:
            # Handle audit and braze events
            # TODO: call new audit method (55854)
            flash_messages = handle_wallet_state_change(
                model, old_state, headers=request.headers  # type: ignore[arg-type] # Argument "headers" to "handle_wallet_state_change" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
            )
            if flash_messages:
                for flash_message in flash_messages:
                    flash(
                        message=flash_message.message,
                        category=flash_message.category.value,
                    )
        elif needs_alegeus_configuration:
            flash_messages = handle_wallet_settings_change(model)
            if flash_messages:
                for flash_message in flash_messages:
                    flash(
                        message=flash_message.message,
                        category=flash_message.category.value,
                    )

        # add maven wallet channel if it is missing
        user_id = form.member.data.id
        reimbursement_wallet_user = self.get_or_create_reimbursement_wallet_user(
            model, user_id
        )
        get_or_create_rwu_channel(reimbursement_wallet_user)

        if hasattr(model, "member_health_plan") and model.member_health_plan:
            self.force_health_plan_dates(model.member_health_plan)
        db.session.commit()
        return model_updated

    def force_health_plan_dates(
        self, member_health_plans: List[MemberHealthPlan]
    ) -> None:
        for plan in member_health_plans:
            needs_new_end_time = plan.plan_end_at is not None and (
                plan.plan_end_at.hour != 23
                or plan.plan_end_at.minute != 59
                or plan.plan_end_at.second != 59
            )
            needs_new_start_time = plan.plan_start_at is not None and (
                plan.plan_start_at.hour != 00
                or plan.plan_start_at.minute != 00
                or plan.plan_start_at.second != 00
            )
            if needs_new_end_time or needs_new_start_time:
                log.info(
                    "Updating Member Health Plan Start/End Dates",
                    plan=plan,
                    new_start=needs_new_start_time,
                    new_end=needs_new_end_time,
                )
                if needs_new_end_time:
                    plan.plan_end_at = datetime.datetime.combine(
                        plan.plan_end_at.date(), datetime.time(23, 59, 59)
                    )
                if needs_new_start_time:
                    plan.plan_start_at = datetime.datetime.combine(
                        plan.plan_start_at.date(), datetime.time(00, 00, 00)
                    )
                flash(
                    f"Updating hour/minute/seconds for {plan} times to the required 00:00:00/23:59:59 values",
                    "info",
                )
                db.session.add(plan)
        db.session.commit()

    def get_or_create_reimbursement_wallet_user(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, model: ReimbursementWallet, user_id: int
    ):
        reimbursement_wallet_user = (
            db.session.query(ReimbursementWalletUsers)
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == model.id,
                ReimbursementWalletUsers.user_id == user_id,
            )
            .one_or_none()
        )
        if not reimbursement_wallet_user:
            user = db.session.query(User).filter(User.id == user_id).one_or_none()
            if not user:
                # This should not be possible given that the form requires the administrator
                # to select an existing user
                raise ValueError(f"Could not find a User with user_id: {user_id}")
            if user.is_employee_with_maven_benefit:
                user_type = WalletUserType.EMPLOYEE
            else:
                user_type = WalletUserType.DEPENDENT
            reimbursement_wallet_user = ReimbursementWalletUsers(
                reimbursement_wallet_id=model.id,
                user_id=user_id,
                type=user_type,
                status=WalletUserStatus.ACTIVE,
            )
        return reimbursement_wallet_user

    def validate_new_data(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if WalletState(form.state.data) == WalletState.DISQUALIFIED and (
            form.note.data is None or form.note.data == ""
        ):
            raise ValueError(
                "If marking a wallet as disqualified, you must provide a reason in the 'note' field."
            )

        user = form.member.data

        # Workaround for users who have multiple Organization Employees linked
        # and cannot rely on user.organization_employee
        reimbursement_organization_settings = (
            form.reimbursement_organization_settings.data
        )
        verification_svc: eligibility.EnterpriseVerificationService = (
            eligibility.get_verification_service()
        )
        verification: Optional[
            e9y.EligibilityVerification
        ] = verification_svc.get_verification_for_user_and_org(
            user_id=user.id,
            organization_id=reimbursement_organization_settings.organization_id,
        )
        if not verification:
            raise ValueError(
                "The user not associated with this with this reimbursement organization."
            )

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
            ReimbursementWallet,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


def _format_rwu_user_id_to_user(view, context, model, name) -> Markup:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user_id = str(model.user_id)
    user_url = url_for("user.index_view", flt0_0=user_id)
    return Markup(f'<a href="{user_url}">{user_id}</a>')


class ReimbursementWalletUsersView(MavenAuditedView):
    create_permission = "create:reimbursement-wallet-user-sharing"
    edit_permission = "edit:reimbursement-wallet-user-sharing"
    delete_permission = "delete:reimbursement-wallet-user-sharing"
    read_permission = "read:reimbursement-wallet-user-sharing"

    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    can_view_details = True

    column_list = (
        "id",
        "reimbursement_wallet_id",
        "user_id",
        "type",
        "status",
        "member.esp_id",
        "channel_id",
        "zendesk_ticket_id",
        "alegeus_dependent_id",
        "created_at",
    )
    column_labels = {
        "id": "Id",
        "reimbursement_wallet_id": "Wallet Id",
        "user_id": "User Id",
        "type": "Wallet User Type",
        "status": "Wallet User Status",
        "member.esp_id": "Member Hash Id",
        "channel_id": "Channel Id",
        "zendesk_ticket_id": "Zendesk Ticket Id",
        "alegeus_dependent_id": "Alegeus Dependent Id",
    }
    form_columns = (
        "reimbursement_wallet_id",
        "user_id",
        "type",
        "status",
        "channel_id",
        "zendesk_ticket_id",
        "alegeus_dependent_id",
    )

    column_filters = (
        "id",
        "reimbursement_wallet_id",
        "user_id",
        ReimbursemenWalletUsersHasChannelIdFilter(None, "Has Channel Id"),
        ReimbursemenWalletUsersHasZendeskTicketIdFilter(None, "Has Zendesk Ticket Id"),
    )

    form_excluded_columns = ("id", "created_at", "modified_at")

    column_formatters = {"user_id": _format_rwu_user_id_to_user}

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
            ReimbursementWalletUsers,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class WalletUserInviteView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    # The admin should be able to mark the invitation as claimed in some rare cases.

    create_permission = "create:wallet-user-invite"
    edit_permission = "edit:wallet-user-invite"
    delete_permission = "delete:wallet-user-invite"
    read_permission = "read:wallet-user-invite"

    can_view_details = True

    column_list = (
        "id",
        "created_by_user_id",
        "reimbursement_wallet_id",
        "date_of_birth_provided",
        "email",
        "claimed",
        "has_info_mismatch",
        "created_at",
        "modified_at",
    )

    column_filters = (
        "id",
        "created_by_user_id",
        "reimbursement_wallet_id",
        "email",
    )

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
            WalletUserInvite,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class WalletUserConsentView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:wallet-user-consent"
    delete_permission = "delete:wallet-user-consent"
    read_permission = "read:wallet-user-consent"

    can_view_details = True
    # We need to allow consent creation for the case where an admin
    # is adding a user to a wallet with 2+ users.
    # The admin should not be able to edit existing consent rows, ever.

    column_list = (
        "id",
        "consent_giver_id",
        "consent_recipient_id",
        "recipient_email",
        "reimbursement_wallet_id",
        "operation",
        "created_at",
        "modified_at",
    )

    column_filters = (
        "consent_giver_id",
        "consent_recipient_id",
        "reimbursement_wallet_id",
        "recipient_email",
    )

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
            WalletUserConsent,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletBillingConsentView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:direct-payment-billing-consent"
    delete_permission = "delete:direct-payment-billing-consent"

    can_view_details = True

    column_list = (
        "reimbursement_wallet_id",
        "version",
        "action",
        "acting_user_id",
        "created_at",
    )

    column_sortable_list = ("reimbursement_wallet_id", "version")
    column_filters = ("reimbursement_wallet_id", "version")

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
            ReimbursementWalletBillingConsent,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ConvertedReimbursementRequestForm(wtforms.Form):
    transaction_amount_with_currency = wtforms.StringField(
        "Transaction Amount",
        [validators.Optional()],
        default=None,
        render_kw={"readonly": True},
    )
    benefit_amount_with_currency = wtforms.StringField(
        "Benefit Amount",
        [validators.Optional()],
        default=None,
        render_kw={"readonly": True},
    )
    usd_amount = wtforms.StringField(
        "USD Amount",
        [validators.Optional()],
        default=None,
        render_kw={"readonly": True},
    )
    transaction_to_benefit_rate = wtforms.DecimalField(
        "Transaction to Benefit Rate",
        [validators.Optional()],
        places=6,
        default=None,
        render_kw={"readonly": True},
    )
    transaction_to_usd_rate = wtforms.DecimalField(
        "Transaction to USD Rate",
        [validators.Optional()],
        places=6,
        default=None,
        render_kw={"readonly": True},
    )

    def on_form_prefill(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        currency_service: CurrencyService,
        reimbursement_request: ReimbursementRequest,
    ):
        # Set transaction_amount_with_currency
        if None not in (
            reimbursement_request.transaction_amount,
            reimbursement_request.transaction_currency_code,
        ):
            transaction_money_amount: Money = currency_service.to_money(
                amount=reimbursement_request.transaction_amount,
                currency_code=reimbursement_request.transaction_currency_code,
            )
            self.transaction_amount_with_currency.data = (
                format_display_amount_with_full_currency_name(transaction_money_amount)
            )

        # Set benefit_amount_with_currency - these values will always exist
        benefit_money_amount: Money = currency_service.to_money(
            amount=reimbursement_request.amount,
            currency_code=reimbursement_request.benefit_currency_code or "USD",
        )
        self.benefit_amount_with_currency.data = (
            format_display_amount_with_full_currency_name(benefit_money_amount)
        )

        # Set usd_amount
        if reimbursement_request.usd_amount is not None:
            usd_money_amount: Money = currency_service.to_money(
                amount=reimbursement_request.usd_amount, currency_code="USD"
            )
            self.usd_amount.data = format_display_amount_with_full_currency_name(
                usd_money_amount
            )

        self.transaction_to_benefit_rate.data = (
            reimbursement_request.transaction_to_benefit_rate
        )
        self.transaction_to_usd_rate.data = (
            reimbursement_request.transaction_to_usd_rate
        )


class TransactionAmountForm(wtforms.Form):
    amount = wtforms.DecimalField("Amount", validators=[validators.DataRequired()])
    currency_code = wtforms.SelectField(
        "Currency Code",
        choices=[(c.alpha_3, f"{c.name} ({c.alpha_3})") for c in pycountry.currencies],
        default="USD",
    )

    def on_form_prefill(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        currency_service: CurrencyService,
        reimbursement_request: ReimbursementRequest,
    ):
        # Handle the existing transactions without transaction_amount
        if None in (
            reimbursement_request.transaction_amount,
            reimbursement_request.transaction_currency_code,
        ):
            money_amount: Money = currency_service.to_money(
                amount=reimbursement_request.amount,
                currency_code="USD",
            )
            self.amount.data = money_amount.amount
            self.currency_code.data = money_amount.currency_code
        else:
            transaction_money_amount: Money = currency_service.to_money(
                amount=reimbursement_request.transaction_amount,
                currency_code=reimbursement_request.transaction_currency_code,
            )
            self.amount.data = transaction_money_amount.amount
            self.currency_code.data = reimbursement_request.transaction_currency_code

    def get_money_amount(self) -> Money:
        if self.amount.data is None:
            raise ValueError("'Transaction Amount' is required")
        if self.currency_code.data is None:
            raise ValueError("'Transaction Currency Code' is required")

        return Money(
            amount=self.amount.data,
            currency_code=self.currency_code.data,
        )


class CustomRateForm(wtforms.Form):
    use_custom_rate = wtforms.BooleanField("Use Custom Rate")
    custom_rate = wtforms.DecimalField(
        label="Custom FX Rate (Transaction Currency → USD)",
        validators=[validators.Optional()],
    )

    def validate(self, extra_validators=None) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        is_valid = super().validate(extra_validators=extra_validators)

        # Validate that we have a custom rate if use_custom_rate is True
        use_custom_rate: bool = self.use_custom_rate.data
        custom_rate: Decimal | None = self.custom_rate.data

        if use_custom_rate is True and custom_rate is None:
            flash(
                "'Custom Rate' is required if 'Use Custom Rate' is selected",
                category="error",
            )
            is_valid = False

        return is_valid

    def on_form_prefill(self, reimbursement_request: ReimbursementRequest):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.use_custom_rate.data = reimbursement_request.use_custom_rate

        if reimbursement_request.use_custom_rate:
            self.custom_rate.data = reimbursement_request.transaction_to_usd_rate

    def get_custom_rate(self) -> Decimal | None:
        custom_rate: Decimal | None = (
            self.custom_rate.data if self.use_custom_rate.data is True else None
        )
        return custom_rate


class ReimbursementRequestsForm(BaseForm):
    def validate(self, *args: Any, **kwargs: Any) -> bool:
        is_valid = super().validate(*args, **kwargs)

        if (
            self.state
            and self.state.data
            and ReimbursementRequestState(self.state.data)
            == ReimbursementRequestState.DENIED
            and (self.description.data is None or self.description.data == "")
        ):
            flash(
                "If marking a request as denied, "
                "you must provide a reason in the 'description' field.",
                category="error",
            )
            is_valid = False

        category = self.category.data
        wallet = self.wallet.data
        if (
            wallet
            and category
            and wallet.reimbursement_organization_settings.id
            not in [
                allowed.reimbursement_organization_settings_id
                for allowed in category.allowed_reimbursement_organizations
            ]
        ):
            flash(
                f"This category {category} is not allowed "
                "for the associated wallet settings.",
                category="error",
            )
            is_valid = False

        expense_type = self.expense_type.data
        expense_subtype = self.wallet_expense_subtype.data
        if not expense_type:
            flash("Expense Type is required", category="error")
            is_valid = False
        elif (
            expense_type
            and expense_subtype
            and expense_type != expense_subtype.expense_type.name
        ):
            flash(
                f"SCC {expense_subtype.code} is not valid for Expense Type {expense_type}",
                category="error",
            )
            is_valid = False

        sources = self.sources.data
        for source in sources:
            if source.reimbursement_wallet_id != wallet.id:
                flash(
                    f"All sources for this request must be associated with wallet {wallet.id}",
                    category="error",
                )
                is_valid = False

        return is_valid


def transaction_amount_formatter(view, context, model: ReimbursementRequest, name):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    minor_unit_amount: int | None = model.transaction_amount
    currency_code: str | None = model.transaction_currency_code
    if None in (minor_unit_amount, currency_code):
        return ""
    currency_service = CurrencyService()
    money_amount: Money = currency_service.to_money(
        amount=minor_unit_amount, currency_code=currency_code
    )
    return format_display_amount_with_currency_code(money=money_amount)


def benefit_amount_formatter(view, context, model: ReimbursementRequest, name):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    minor_unit_amount: int = model.amount
    currency_code: str = model.benefit_currency_code or "USD"
    if None in (minor_unit_amount, currency_code):
        return ""
    currency_service = CurrencyService()
    money_amount: Money = currency_service.to_money(
        amount=minor_unit_amount, currency_code=currency_code
    )
    return format_display_amount_with_currency_code(money=money_amount)


def usd_amount_formatter(view, context, model: ReimbursementRequest, name):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    minor_unit_amount: int | None = model.usd_amount
    currency_code: str = "USD"
    if minor_unit_amount is None:
        return ""
    currency_service = CurrencyService()
    money_amount: Money = currency_service.to_money(
        amount=minor_unit_amount, currency_code=currency_code
    )
    return format_display_amount_with_currency_code(money=money_amount)


def reimbursement_type_formatter(view, context, model: ReimbursementRequest, name):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    result = model.reimbursement_type.name  # type: ignore[attr-defined] # "str" has no attribute "name"
    if model.reimbursement_type == ReimbursementRequestType.DIRECT_BILLING:
        result += "<br>" + reimbursement_type_bill_link(model)
    return Markup(result)


def reimbursement_type_bill_link(model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    result = ""
    try:
        claim_type, treatment_procedure_id = (
            db.session.query(
                ReimbursementRequestToCostBreakdown.claim_type,
                TreatmentProcedure.id,
            )
            .join(
                TreatmentProcedure,
                ReimbursementRequestToCostBreakdown.treatment_procedure_uuid
                == TreatmentProcedure.uuid,
            )
            .filter(
                ReimbursementRequestToCostBreakdown.reimbursement_request_id == model.id
            )
            .one()
        )

        payor_type = (
            PayorType.EMPLOYER
            if (claim_type == ClaimType.EMPLOYER)
            else PayorType.MEMBER
        )
        billing_service = BillingService()
        bills = billing_service.get_bills_by_procedure_ids(
            procedure_ids=list([treatment_procedure_id]),
            exclude_payor_types=[t for t in PayorType if t != payor_type],
        )
        matching_bills = [bill for bill in bills if bill.amount == model.amount]
        if len(matching_bills) == 1:
            bill_id = matching_bills[0].id
            result = f"<a href='/admin/bill/details/?id={bill_id}&url=%2Fadmin%2Fbill%2F'>Bill #{bill_id}</a>"
        elif len(matching_bills) == 0:
            result = "[Bill Not Found]"
        else:
            result = "[Multiple Bills Found]"
    except NoResultFound:
        result = "[CB Not Found]"
    except MultipleResultsFound:
        result = "[Multiple CBs Found]"
    return result


class ReimbursementRequestsView(MavenAuditedView):
    # Has to be form_base_class for sqla, but the standard delete and action form methods
    # use this to build their own forms, so override those below to use the generic base form.
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:reimbursement-request"
    edit_permission = "edit:reimbursement-request"
    create_permission = "create:reimbursement-request"
    delete_permission = "delete:reimbursement-request"

    form_base_class = ReimbursementRequestsForm
    # TODO: set this to true everywhere
    named_filter_urls = True
    create_template = "reimbursement_requests_create_template.html"
    edit_template = "reimbursement_requests_edit_template.html"
    can_view_details = True

    def create_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form = super().create_form()
        wallet = None
        if "wallet_id" in request.args and form.wallet.data is None:
            wallet = self._get_or_error_reimbursement_wallet(request.args["wallet_id"])
            form.wallet.data = wallet
        if "sources" in request.args and not form.sources.data:
            source_ids = request.args["sources"].split(",")
            sources = (
                db.session.query(ReimbursementRequestSource)
                .filter(ReimbursementRequestSource.id.in_(source_ids))
                .all()
            )
            if len(sources) < 1:
                flash("Invalid source IDs provided", category="error")
                raise RequestRedirect(url_for("reimbursementrequestsource.index_view"))
            if len({source.reimbursement_wallet_id for source in sources}) > 1:
                flash(
                    "Cannot create a request with sources from multiple wallets",
                    category="error",
                )
                raise RequestRedirect(url_for("reimbursementrequestsource.index_view"))
            form.sources.data = sources
            form.wallet.data = sources[0].wallet
        return form

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form=form, id=id)

        reimbursement_request: ReimbursementRequest = db.session.query(
            ReimbursementRequest
        ).get(id)

        currency_service = CurrencyService()

        # populate the transaction_amount_form
        transaction_amount_form: TransactionAmountForm = form.transaction_amount_form
        transaction_amount_form.on_form_prefill(
            currency_service=currency_service,
            reimbursement_request=reimbursement_request,
        )

        # populate the custom_rate_form
        custom_rate_form: CustomRateForm = form.custom_rate_form
        custom_rate_form.on_form_prefill(reimbursement_request=reimbursement_request)

        # Populate the converted_amounts_form
        converted_amounts_form: ConvertedReimbursementRequestForm = (
            form.converted_amounts_form
        )
        converted_amounts_form.on_form_prefill(
            currency_service=currency_service,
            reimbursement_request=reimbursement_request,
        )

        # Check to see if there is an existing reimbursement request that was auto-processed from SMP file processing
        # Allow RR to be created, but display a flash message with duplicate RR ids
        if self._is_smp_reimbursement(form):
            auto_rr_service = AutomatedReimbursementRequestService()
            auto_processed = (
                None
                if form.auto_processed.data
                == ReimbursementRequestAutoProcessing.RX.value
                else ReimbursementRequestAutoProcessing.RX
            )
            duplicates = auto_rr_service.check_for_duplicate_automated_rx_reimbursement(
                reimbursement_request=reimbursement_request,
                auto_processed=auto_processed,
            )
            if duplicates:
                flash(
                    f"Duplicate reimbursements found matching this reimbursements details: {duplicates}"
                )

    def get_delete_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Override to force the BaseForm
        class DeleteForm(BaseForm):
            id = fields.HiddenField(validators=[validators.InputRequired()])
            url = fields.HiddenField()

        return DeleteForm

    def get_action_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Override to force the BaseForm
        class ActionForm(BaseForm):
            action = fields.HiddenField()
            url = fields.HiddenField()
            # rowid is retrieved using getlist, for backward compatibility

        return ActionForm

    def _get_or_error_reimbursement_wallet(self, wallet_id: int) -> ReimbursementWallet:
        wallet = ReimbursementWallet.query.get(wallet_id)
        if wallet is None:
            raise ValueError("Requested Reimbursement Wallet not found.")
        return wallet

    column_list = (
        "id",
        "label",
        "service_provider",
        "amount",
        "benefit_currency_code",
        "transaction_amount",
        "transaction_currency_code",
        "category.label",
        "wallet",
        "total_reimbursed",
        "wallet_user_info",
        "state",
        "created_at",
        "expense_type",
        "wallet_expense_subtype",
        "reimbursement_method",
        "taxation_status",
        "reimbursement_type",
        "is_prepaid",
    )
    column_sortable_list = (
        "service_provider",
        "amount",
        "category.label",
        "state",
        "expense_type",
        "taxation_status",
        "reimbursement_method",
    )
    column_labels = {
        "id": "Id",
        "label": "Line Item Title",
        "amount": "Benefit Amount",
        "benefit_currency_code": "Benefit Currency",
        "transaction_amount": "Transaction Amount",
        "transaction_currency_code": "Transaction Currency",
        "service_start_date": "Start Date",
        "service_end_date": "End Date",
        "category.label": "Category",
        "wallet_user_info": "Wallet User Info",
        "description": "Member Facing Line Item Description",
        "total_reimbursed": "Already Reimbursed (Benefit Currency)",
        "taxation_status": "Taxation Status",
        "is_prepaid": "Is Pre-Paid",
        "reimbursement_type": "Reimbursement Request Type",
        "wallet_expense_subtype": "SCC",
        "original_wallet_expense_subtype": "Original SCC",
    }
    column_filters = [
        "id",
        "label",
        "service_provider",
        "wallet.state",
        ReimbursementRequestHasZendeskTicketIdFilter(None, "Has Zendesk Ticket Id"),
        "wallet.taxation_status",
        "wallet.reimbursement_method",
        ReimbursementRequestHasUserIdFilter(None, "Has User Id"),
        ReimbursementRequestHasEmailAddress(None, "Has Email Address"),
        "state",
        "category.label",
        "sources.id",
        "expense_type",
        "taxation_status",
        "reimbursement_method",
        "is_prepaid",
        "reimbursement_type",
        "auto_processed",
        ReimbursementRequestBenefitIdFilter(None, "Benefit Id"),
    ]
    column_formatters = {
        "label": lambda view, context, model, p: model.formatted_label,
        "amount": benefit_amount_formatter,
        "transaction_amount": transaction_amount_formatter,
        "usd_amount": usd_amount_formatter,
        "total_reimbursed": lambda view, context, model, p: total_reimbursed_formatter(
            wallet=model.wallet
        ),
        "reimbursement_type": reimbursement_type_formatter,
        "wallet_expense_subtype": lambda v, c, m, p: f"{m.wallet_expense_subtype.reimbursement_service_category.category}:{m.wallet_expense_subtype.code}"
        if m.wallet_expense_subtype
        else None,
        "original_wallet_expense_subtype": lambda v, c, m, p: f"{m.original_wallet_expense_subtype.reimbursement_service_category.category}:{m.original_wallet_expense_subtype.code}"
        if m.original_wallet_expense_subtype
        else None,
    }
    form_overrides = {"description": fields.TextAreaField}
    form_extra_fields = {
        "custom_rate_form": CustomFormField(CustomRateForm, label="Custom Rate"),
        "converted_amounts_form": CustomFormField(
            ConvertedReimbursementRequestForm, label="Converted Amounts"
        ),
        "transaction_amount_form": CustomFormField(
            TransactionAmountForm, label="Transaction"
        ),
    }

    def _get_source_image_links(request, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        sources = form.sources.data
        if not sources:
            return "(No sources)"
        links = Markup("")
        for source in sources:
            if not source.user_asset:
                links += Markup("Source {} does not have an image<br />").format(
                    source.id
                )
                continue
            links += Markup('<a href="{}" target="_blank">Source {}</a><br />').format(
                source.user_asset.direct_download_url(inline=True), source.id
            )
        return links

    def _get_stripe_status_if_present(request, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # We use form.wallet.data here instead of request.wallet so that the create form
        # can access the wallet object
        wallet = form.wallet.data
        if wallet:
            stripe_account_id = wallet.member.member_profile.stripe_account_id
            return f"Enabled: {stripe_account_id}" if stripe_account_id else "Disabled"
        else:
            return "(No wallet set)"

    def _get_wallet_reimbursed_amount_if_present(request, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # We use form.wallet.data here instead of request.wallet so that the create form
        # can access the wallet object
        wallet = form.wallet.data
        if wallet:
            return total_reimbursed_formatter(wallet=wallet)
        else:
            return "(No wallet set)"

    @staticmethod
    def _is_smp_reimbursement(rr_form) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        is_manual = (
            rr_form.reimbursement_type.data
            and rr_form.reimbursement_type.data == ReimbursementRequestType.MANUAL.name
        )
        is_pharmacy = (
            rr_form.procedure_type.data
            and rr_form.procedure_type.data
            == TreatmentProcedureType.PHARMACY.value  # procedure_type is not an enum
        )
        is_smp = (
            rr_form.service_provider.data
            and "SMP" in rr_form.service_provider.data.upper()
        ) or (rr_form.description.data and "SMP" in rr_form.description.data.upper())
        return is_manual and is_pharmacy and is_smp

    form_edit_rules = (
        ReadOnlyFieldRule("Id", lambda model: model.id),
        "category",
        "wallet",
        "sources",
        ReadOnlyFieldRule("Source images", _get_source_image_links),
        ReadOnlyFieldRule("Stripe Status", _get_stripe_status_if_present),
        ReadOnlyFieldRule(
            "Already Reimbursed (Benefit Currency)",
            _get_wallet_reimbursed_amount_if_present,
        ),
        "label",
        "service_provider",
        "person_receiving_service",
        "person_receiving_service_id",
        "description",
        "transaction_amount_form",
        "custom_rate_form",
        "converted_amounts_form",
        "state",
        "service_start_date",
        "service_end_date",
        "reimbursement_transfer_date",
        "reimbursement_payout_date",
        "expense_type",
        ReadOnlyFieldRule(
            "Original Expense Type",
            lambda model: model.original_expense_type,
        ),
        "wallet_expense_subtype",
        ReadOnlyFieldRule(
            "Original SCC",
            lambda model: f"{model.original_wallet_expense_subtype.reimbursement_service_category.category}:{model.original_wallet_expense_subtype.code}"
            if model.original_wallet_expense_subtype
            else None,
        ),
        "taxation_status",
        "reimbursement_method",
        "is_prepaid",
        "reimbursement_type",
        ReadOnlyFieldRule(
            "Bill",
            lambda model: (
                Markup(reimbursement_type_bill_link(model))
                if model.reimbursement_type == ReimbursementRequestType.DIRECT_BILLING
                else ""
            ),
        ),
        ReadOnlyFieldRule(
            "Appeal Of",
            lambda model: str(model.appeal_of) if model.appeal_of else "None",
        ),
        ReadOnlyFieldRule(
            "ERISA Workflow", lambda model: "Yes" if model.erisa_workflow else "No"
        ),
        "cost_sharing_category",
        "procedure_type",
        "cost_credit",
        "auto_processed",
    )

    form_args = {
        "label": {
            "default": ReimbursementRequest.AUTO_LABEL_FLAG,
            "description": f'"{ReimbursementRequest.AUTO_LABEL_FLAG}" generates a title based on Expense Type & SCC',
        },
        "wallet_expense_subtype": {
            "get_label": lambda m: f"({m.expense_type}) {m.reimbursement_service_category.category}:{m.code}"
        },
    }

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        reimbursement_request_id = request.args.get("id")
        self._template_args["mappings"] = AccumulationTreatmentMapping.query.filter(
            AccumulationTreatmentMapping.reimbursement_request_id
            == reimbursement_request_id
        ).all()
        self._template_args["cost_breakdowns"] = CostBreakdown.query.filter(
            CostBreakdown.reimbursement_request_id == reimbursement_request_id
        ).all()

        # Add validation info to template args
        if reimbursement_request_id:
            reimbursement_request = self.get_one(reimbursement_request_id)
            if receipt_validation_ops_view_enabled(
                reimbursement_request.service_provider,
                member_facing=False,
            ):
                self._template_args[
                    "reimbursement_field_validations"
                ] = self._get_reimbursement_field_validations(reimbursement_request)

        if reimbursement_request_id:
            pharmacy_prescription_service = PharmacyPrescriptionService(
                session=db.session
            )
            self._template_args[
                "pharmacy_prescriptions"
            ] = pharmacy_prescription_service.get_by_reimbursement_request_ids(
                reimbursement_request_ids=[reimbursement_request_id]
            )

            self._template_args[
                "reimbursement_claims"
            ] = ReimbursementClaim.query.filter(
                ReimbursementClaim.reimbursement_request_id == reimbursement_request_id
            ).all()
        return super().edit_view()

    form_create_rules = (
        "category",
        "wallet",
        "sources",
        ReadOnlyFieldRule("Source images", _get_source_image_links),
        ReadOnlyFieldRule("Stripe Status", _get_stripe_status_if_present),
        ReadOnlyFieldRule(
            "Already Reimbursed (Benefit Currency)",
            _get_wallet_reimbursed_amount_if_present,
        ),
        "label",
        "service_provider",
        "person_receiving_service",
        "description",
        "transaction_amount_form",
        "custom_rate_form",
        "state",
        "service_start_date",
        "service_end_date",
        "expense_type",
        "wallet_expense_subtype",
        "taxation_status",
        "reimbursement_method",
        "is_prepaid",
        "reimbursement_type",
        "auto_processed",
    )

    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "category.label": QueryAjaxModelLoader(
                    "category.label",
                    self.session,
                    ReimbursementRequestCategory,
                    fields=("label",),
                    page_size=10,
                ),
                "wallet": SnowflakeQueryAjaxModelLoader(
                    "wallet",
                    self.session,
                    ReimbursementWallet,
                    fields=("id",),
                    page_size=10,
                ),
                "sources": SnowflakeQueryAjaxModelLoader(
                    "sources",
                    self.session,
                    ReimbursementRequestSource,
                    fields=("id", "user_asset_id", "reimbursement_wallet_id"),
                    page_size=10,
                ),
            }
        return self._form_ajax_refs

    def audit_wallet_receipt(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        model_audit(
            action_type=ACTIONS.change_reimbursement_request_status,
            reimbursement_request_id=model.id,
            reimbursement_request_status=ReimbursementRequestState(model.state).value,
            wallet_id=model.wallet and model.wallet.id,
            label=model.label,
            service_provider=model.service_provider,
            amount=int(model.amount),
            category=model.category and model.category.label,
            receipt_id=model.first_source and model.first_source.source_id,
        )

    def on_model_change(self, form, model: ReimbursementRequest, is_created: bool) -> None:  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        super().on_model_change(form=form, model=model, is_created=is_created)

        if is_created:
            allowed_category_ids = frozenset(
                c.reimbursement_request_category_id
                for c in model.wallet.get_wallet_allowed_categories
            )
            model.set_expense_type_configuration_attributes(
                allowed_category_ids=allowed_category_ids, user_id=None
            )
        # Fetch the category association
        category_id = form.category.data.id or model.reimbursement_request_category_id
        category: ReimbursementOrgSettingCategoryAssociation = (
            db.session.query(ReimbursementOrgSettingCategoryAssociation)
            .filter(
                ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings_id
                == model.wallet.reimbursement_organization_settings_id,
                ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category_id
                == category_id,
            )
            .one_or_none()
        )

        if not category:
            raise Exception("ReimbursementOrgSettingCategoryAssociation not found")

        custom_rate_form: CustomRateForm = form.custom_rate_form
        custom_rate: Decimal | None = custom_rate_form.get_custom_rate()

        transaction_amount_form: TransactionAmountForm = form.transaction_amount_form
        transaction_amount: Money = transaction_amount_form.get_money_amount()

        currency_service = CurrencyService()
        # Exceptions are caught by flask-admin so the right alert can be displayed
        currency_service.process_reimbursement_request(
            transaction=transaction_amount,
            request=model,
            custom_rate=custom_rate,
        )

        # If reimbursement request ReimbursementMethod is set and not equal to expense type config ReimbursementMethod
        # Alert ops, and they can handle the reimbursement manually on alegeus.
        if model.reimbursement_method and model.expense_type and model.wallet:
            # Get ReimbursementOrgSettingsExpenseType row for the given expense_type
            expense_type_config = ReimbursementOrgSettingsExpenseType.query.filter_by(
                reimbursement_organization_settings_id=model.wallet.reimbursement_organization_settings_id,
                expense_type=model.expense_type,
            ).first()
            if (
                expense_type_config
                and expense_type_config.reimbursement_method
                and model.reimbursement_method
                != expense_type_config.reimbursement_method
            ):
                title = f"Reimbursement Method mismatch for Reimbursement Request: {model.id} for wallet: {model.wallet.id}"
                message = (
                    f"Request's Reimbursement method {model.reimbursement_method} doesn't match "
                    f"{model.expense_type} configured Reimbursement Method: {expense_type_config.reimbursement_method}"
                )
                notify_payment_ops_channel(title, message)

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # update the model to the new data
        model = super().create_model(form)

        # Only perform these actions if we have a model
        # on_model_change could raise an exception and model is not created
        if model:
            # copy these fields to store original values
            model.original_expense_type = model.expense_type
            model.original_wallet_expense_subtype = model.wallet_expense_subtype
            self.session.add(model)
            self.session.commit()

            # Send braze events for new states which require events.
            # All states are new in create_model.
            handle_reimbursement_request_state_change(model, model.state)
            self.audit_wallet_receipt(model)

        return model

    def update_model(self, form, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        old_category_id = model.reimbursement_request_category_id or model.category.id
        new_category_id = form.category.data.id
        old_state = ReimbursementRequestState(model.state)
        new_state = ReimbursementRequestState(form.state.data)
        old_expense_type = new_expense_type = None
        if model.expense_type is not None:
            old_expense_type = ReimbursementRequestExpenseTypes(model.expense_type)
        if form.expense_type.data is not None:
            new_expense_type = ReimbursementRequestExpenseTypes(form.expense_type.data)
        old_expense_subtype = model.wallet_expense_subtype
        new_expense_subtype = form.wallet_expense_subtype.data

        for new_source in form.sources.data:
            if new_source not in model.sources and new_source.upload_source is None:
                new_source.upload_source = ReimbursementRequestSourceUploadSource.ADMIN

        # update the model to the new data
        model_updated = super().update_model(form, model)

        if new_state != old_state:
            # Send braze events for changed states only.
            # Do not send events for other edits.
            # Handle debit card transactions created/updated in admin
            if model.reimbursement_type == ReimbursementRequestType.DEBIT_CARD:
                flash_messages = (
                    handle_reimbursement_request_card_transaction_state_change(
                        model.wallet, model, old_state
                    )
                )
            else:
                flash_messages = handle_reimbursement_request_state_change(
                    model, old_state
                )
            if flash_messages:
                for flash_message in flash_messages:
                    flash(
                        message=flash_message.message,
                        category=flash_message.category.value,
                    )
            # Only record changed states
            self.audit_wallet_receipt(model)

        # Run updates if this is a newly created Reimbursement Request or if state or expense type is updated
        if new_state != old_state or new_expense_type != old_expense_type:
            allowed_category_ids = frozenset(
                c.reimbursement_request_category_id
                for c in model.wallet.get_or_create_wallet_allowed_categories
            )
            model.set_expense_type_configuration_attributes(
                allowed_category_ids=allowed_category_ids, user_id=None
            )

        # Record metric for category, type, and subtype changes
        if old_category_id != new_category_id:
            increment_reimbursement_request_field_update(
                field="category", source="admin"
            )
        if old_expense_type != new_expense_type:
            increment_reimbursement_request_field_update(
                field="expense_type",
                source="admin",
                old_value=old_expense_type.value if old_expense_type else None,
                new_value=new_expense_type.value if new_expense_type else None,
            )
        if old_expense_subtype != new_expense_subtype:
            increment_reimbursement_request_field_update(
                field="wallet_expense_subtype",
                source="admin",
                old_value=old_expense_subtype.code if old_expense_subtype else None,
                new_value=new_expense_subtype.code if new_expense_subtype else None,
            )

        return model_updated

    def get_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Eagerly load previous reimbursement request amounts
        return self.session.query(self.model).options(
            joinedload(ReimbursementRequest.wallet).options(
                joinedload(ReimbursementWallet.approved_amounts),
                joinedload(ReimbursementWallet.reimbursed_amounts),
            )
        )

    @action(
        "create_appeal",
        "Create Appeal",
        "Are you sure you want to create an appeal request?",
    )
    def create_appeal(self, reimbursement_request_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(reimbursement_request_ids) > 1:
            flash(
                "Only a single Reimbursement Request can be appealed at a time.",
                category="error",
            )
            return redirect(self.get_url(".index_view"))

        original_reimbursement_request = self.get_one(reimbursement_request_ids[0])
        if not original_reimbursement_request:
            flash("Error loading reimbursement request.", category="error")
            return redirect(self.get_url(".index_view"))

        flash_messages, success, appeal_id = create_appeal(
            original_reimbursement_request
        )
        if flash_messages:
            for flash_message in flash_messages:
                flash(
                    message=flash_message.message,
                    category=flash_message.category.value,
                )
        if success:
            return redirect(self.get_url(".edit_view", id=appeal_id))
        else:
            return redirect(self.get_url(".index_view"))

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
            ReimbursementRequest,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    def _get_field_validation_status_and_message(
        self,
        extracted_value: Optional[str | int],
        request_value: Optional[str | int],
        field_name: str,
        format_value: Callable = str,
    ) -> dict:
        """Helper function to generate validation status and message for a field

        Args:
            extracted_value: Value extracted from document
            request_value: Value from reimbursement request
            field_name: Name of the field (e.g. "Provider name", "Service date")
            format_value: Optional function to format the value for display
        """
        if not extracted_value:
            return {
                "status": "error",
                "message": f"{field_name} could not be found in the source document(s)",
            }

        if format_value is None:
            format_value = str

        formatted_value = format_value(extracted_value)

        # For string values, normalize by trimming whitespace and converting to lowercase
        # before comparison to avoid false mismatches due to case or whitespace
        if isinstance(extracted_value, str) and isinstance(request_value, str):
            extracted_normalized = extracted_value.strip().lower()
            request_normalized = request_value.strip().lower()

            # Exact match after normalization
            if extracted_normalized == request_normalized:
                return {
                    "status": "info",
                    "message": f"{field_name} matches '{formatted_value}'",
                }

            # For service provider names, use partial matching to handle cases like "CCRM" vs "CCRM New York"
            if field_name == "Provider name":
                match_score1 = partial_ratio(extracted_normalized, request_normalized)
                match_score2 = partial_ratio(request_normalized, extracted_normalized)
                match_score = max(match_score1, match_score2)

                if (
                    match_score >= 80.0
                ):  # Using the same threshold as in receipt_validation_ops_view_enabled
                    return {
                        "status": "info",
                        "message": f"{field_name} matches '{formatted_value}'",
                    }
        elif extracted_value == request_value:
            return {
                "status": "info",
                "message": f"{field_name} matches '{formatted_value}'",
            }

        return {
            "status": "warning",
            "message": f"{field_name} appears to be '{formatted_value}' in the source document(s)",
        }

    def _get_reimbursement_field_validations(
        self, reimbursement_request: ReimbursementRequest
    ) -> dict:
        """Get field validations from document mapper service"""
        mappings = (
            self.session.query(
                ReimbursementRequestSource.document_mapping_uuid.distinct()
            )
            .join(
                ReimbursementRequestSourceRequests,
                ReimbursementRequestSourceRequests.reimbursement_request_source_id
                == ReimbursementRequestSource.id,
            )
            .filter(
                ReimbursementRequestSourceRequests.reimbursement_request_id
                == reimbursement_request.id
            )
            .all()
        )

        log.info(
            "Found document mappings",
            reimbursement_request_id=reimbursement_request.id,
            mappings=mappings,
        )

        if not mappings:
            log.warning(
                "No sources to validate",
                reimbursement_request_id=reimbursement_request.id,
            )
            return {
                "fields": {
                    "sources": {
                        "status": "error",
                        "message": "No documents to validate",
                    }
                }
            }
        document_mapping_uuids = [uuid[0] for uuid in mappings]
        if len(document_mapping_uuids) != 1:
            # TODO: PAY-6425 add button to re-trigger doc mapping when this occurs
            log.warning(
                "Document Mapping is stale - reimbursement sources have mismatched document mapping UUIDs and document mapper needs to be re-run",
                reimbursement_request_id=reimbursement_request.id,
            )
            return {
                "fields": {
                    "sources": {
                        "status": "error",
                        "message": "AI Validations are stale - AI Validation needs to be re-run",
                    }
                }
            }
        document_mapping_uuid = document_mapping_uuids[0]
        if not document_mapping_uuid:
            # TODO: PAY-6425 add button to re-trigger doc mapping when this occurs
            log.warning(
                "No document mapping validation exists on sources - missing validations and document mapper needs to be run",
                reimbursement_request_id=reimbursement_request.id,
            )
            return {
                "fields": {
                    "sources": {
                        "status": "error",
                        "message": "No AI validation exists on sources - Validation needs to be run",
                    }
                }
            }
        document_mapper_service = DocumentMapperService(
            document_mapper_base_url=INTERNAL_TRUST_DOCUMENT_MAPPER_URL
        )
        mapping = document_mapper_service.get_document_mapping(
            document_mapping_uuid=document_mapping_uuid
        )

        log.info(
            "Retrieved document mapping",
            document_mapping_uuid=document_mapping_uuid,
            mapping=mapping,
            reimbursement_request_id=reimbursement_request.id,
        )

        if not mapping:
            log.error(
                "No document mapping returned - validations not shown",
                reimbursement_request_id=reimbursement_request.id,
            )
            return {
                "fields": {
                    "sources": {
                        "status": "error",
                        "message": "No AI Validation returned - validations not shown",
                    }
                }
            }

        # Create feedback lookup dict for quick access
        feedback_lookup = {}
        if mapping.feedback:
            for feedback_entry in mapping.feedback:
                feedback_lookup[
                    feedback_entry.field_name
                ] = feedback_entry.feedback_accepted

        log.info(
            "Processing field validations",
            reimbursement_request_id=reimbursement_request.id,
            feedback_lookup=feedback_lookup,
            service_provider=mapping.document_mapping.service_provider,
            patient_name=mapping.document_mapping.patient_name,
            payment_amount=mapping.document_mapping.payment_amount,
            date_of_service=mapping.document_mapping.date_of_service,
            service_evidence=mapping.document_mapping.service_evidence,
        )

        validations = {
            "document_mapping_uuid": str(document_mapping_uuid),
            "fields": {
                "service_provider": {
                    **self._get_field_validation_status_and_message(
                        mapping.document_mapping.service_provider,
                        reimbursement_request.service_provider,
                        "Provider name",
                    ),
                    "prior_feedback": feedback_lookup.get("service_provider"),
                    "field_value": reimbursement_request.service_provider,
                },
                "person_receiving_service": {
                    **self._get_field_validation_status_and_message(
                        mapping.document_mapping.patient_name,
                        reimbursement_request.person_receiving_service,
                        "Patient name",
                    ),
                    "prior_feedback": feedback_lookup.get("person_receiving_service"),
                    "field_value": reimbursement_request.person_receiving_service,
                },
                "transaction_amount_form": {
                    **self._get_field_validation_status_and_message(
                        mapping.document_mapping.payment_amount,
                        reimbursement_request.amount,
                        "Payment amount",
                        format_value=lambda x: f"${x/100:.2f}",
                    ),
                    "prior_feedback": feedback_lookup.get("transaction_amount_form"),
                    "field_value": str(reimbursement_request.amount),
                },
                "service_start_date": {
                    **self._get_field_validation_status_and_message(
                        mapping.document_mapping.date_of_service,
                        reimbursement_request.service_start_date.strftime("%Y-%m-%d"),
                        "Service date",
                    ),
                    "prior_feedback": feedback_lookup.get("service_start_date"),
                    "field_value": reimbursement_request.service_start_date.strftime(
                        "%Y-%m-%d"
                    ),
                },
                "sources": {
                    "status": "info"
                    if mapping.document_mapping.service_evidence
                    else "error",
                    "message": (
                        "Service evidence found in sources"
                        if mapping.document_mapping.service_evidence
                        else "There does not appear to be service evidence in the sources"
                    ),
                    "prior_feedback": feedback_lookup.get("sources"),
                    "field_value": str(
                        reimbursement_request.sources[0].id
                        if reimbursement_request.sources
                        else ""
                    ),
                },
            },
        }

        return validations

    @expose("/document_mapping", methods=["POST"])
    def create_document_mapping(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Handle document mapping creation for receipt validation"""
        try:
            log.info("Creating document mapping")
            reimbursement_request_id = request.args.get("id")
            if not reimbursement_request_id:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Reimbursement request ID is required",
                        }
                    ),
                    400,
                )

            log.info(
                "Submitting document mapper request to create document mapping",
                reimbursement_request_id=reimbursement_request_id,
            )
            map_reimbursement_request_documents(
                reimbursement_request_id=reimbursement_request_id
            )
            return redirect(
                url_for("reimbursementrequest.edit_view", id=reimbursement_request_id)
            )
        except Exception as e:
            log.error(
                "Error creating document mapping for receipt validation",
                error=str(e),
                traceback=format_exc(),
            )
            return jsonify({"status": "error", "message": str(e)}), 500

    @expose("/document_mapper_feedback", methods=["POST"])
    def handle_document_mapper_feedback(self) -> tuple[Response, int]:
        """Handle feedback submission for document mapper validations"""
        try:
            log.info("Processing submit feedback request")
            data = request.get_json()
            document_mapping_uuid = UUID(data["document_mapping_uuid"])
            field_name = data["field_name"]
            is_correct = data["is_correct"]
            field_value = data["field_value"]

            document_mapper_service = DocumentMapperService(
                document_mapper_base_url=INTERNAL_TRUST_DOCUMENT_MAPPER_URL
            )

            log.info(
                "Submitting document mapper feedback",
                document_mapping_uuid=document_mapping_uuid,
            )
            feedback = document_mapper_service.create_feedback(
                document_mapping_uuid=document_mapping_uuid,
                field_name=field_name,
                updated_by=login.current_user.email,
                previous_value=field_value,
                feedback_accepted=is_correct,
            )

            if feedback:
                return jsonify({"status": "success"}), 200
            return (
                jsonify({"status": "error", "message": "Failed to create feedback"}),
                400,
            )

        except Exception as e:
            log.error(
                "Error handling document mapper feedback",
                error=str(e),
                traceback=format_exc(),
            )
            return jsonify({"status": "error", "message": str(e)}), 500


class ReimbursementRequestSourceView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:reimbursement-request-source"
    edit_permission = "edit:reimbursement-request-source"
    create_permission = "create:reimbursement-request-source"
    delete_permission = "delete:reimbursement-request-source"

    named_filter_urls = True

    column_list = (
        "id",
        "user_asset",
        "wallet",
        "document_mapping_uuid",
        "upload_source",
        "request_count",
        "user_asset.modified_at",
    )
    column_filters = (
        "wallet.id",
        ReimbursementRequestSourceUserIdFilter(None, "Member User Id"),
        ReimbursementRequestSourceMemberEmailFilter(None, "Member Email Address"),
        "request_count",
    )
    column_labels = {"user_asset.modified_at": "Date"}
    column_sortable_list = ("user_asset.modified_at",)
    column_default_sort = ("user_asset.modified_at", True)
    column_formatters = {
        "user_asset": lambda v, c, m, p: m.user_asset
        and Markup('{} <a href="{}" target="_blank">View Image</a>').format(
            str(m.user_asset), m.user_asset.direct_download_url(inline=True)
        ),
        "request_count": lambda v, c, m, p: m.request_count
        and Markup('{} <a href="{}">View</a>').format(
            m.request_count,
            url_for(
                "reimbursementrequest.index_view",
                flt1_sources_reimbursement_request_source_id_equals=m.id,
            ),
        ),
        "wallet": lambda v, c, m, p: m.wallet
        and Markup('{}<br /><a href="{}">Filter by this wallet</a>').format(
            str(m.wallet),
            url_for(
                "reimbursementrequestsource.index_view",
                flt1_wallet_reimbursement_wallet_id_equals=m.wallet.id,
            ),
        ),
    }

    form_excluded_columns = (
        "created_at",
        "modified_at",
    )
    _form_ajax_refs = None

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # update the model to the new data
        form.upload_source.data = ReimbursementRequestSourceUploadSource.ADMIN
        model = super().create_model(form)
        return model

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "user_asset": SnowflakeQueryAjaxModelLoader(
                    "user_asset",
                    self.session,
                    UserAsset,
                    fields=("id",),
                    page_size=10,
                ),
                "wallet": SnowflakeQueryAjaxModelLoader(
                    "wallet",
                    self.session,
                    ReimbursementWallet,
                    fields=("id",),
                    page_size=10,
                ),
            }
        return self._form_ajax_refs

    @action("create_request", "Create new request from receipts")
    def action_create_request(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        request_create_url = url_for(
            "reimbursementrequest.create_view", sources=",".join(ids)
        )
        audit_bulk_log_reads_rrs = []
        for i in ids:
            rrs = ReimbursementRequestSource.query.filter_by(id=i).one_or_none()
            audit_bulk_log_reads_rrs.append(rrs)
        emit_bulk_audit_log_create(audit_bulk_log_reads_rrs)
        return redirect(request_create_url)

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
            ReimbursementRequestSource,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementPlanViewOrganizationFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementRequestCategory,
                ReimbursementRequestCategory.reimbursement_plan_id
                == ReimbursementPlan.id,
            )
            .join(ReimbursementRequestCategory.allowed_reimbursement_organizations)
            .join(
                ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings
            )
            .join(ReimbursementOrganizationSettings.organization)
            .filter(Organization.name.contains(value))
        )


class ReimbursementPlanView(MavenAuditedView):
    create_permission = "create:alegeus-plan"
    edit_permission = "edit:alegeus-plan"
    delete_permission = "delete:alegeus-plan"
    read_permission = "read:alegeus-plan"

    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    edit_template = "reimbursement_plan_edit_template.html"

    column_filters = [
        "id",
        "is_hdhp",
        "reimbursement_plan_coverage_tier_id",
        "auto_renew",
        "plan_type",
        "alegeus_plan_id",
        "organization_id",
        ReimbursementPlanViewOrganizationFilter(None, "Organizations"),
    ]
    column_list = (
        "reimbursement_account_type",
        "alegeus_plan_id",
        "deductible_amount",
        "is_hdhp",
        "alegeus_coverage_tier",
        "auto_renew",
        "plan_type",
        "start_date",
        "end_date",
        "organizations",
    )
    column_labels = {"reimbursement_account_type": "Alegeus Plan Type"}
    form_excluded_columns = (
        "organization_id",
        "reimbursement_plan_coverage_tier",
        "category",
        "reimbursement_accounts",
        "reimbursement_hdhp_plans",
        "created_at",
        "modified_at",
    )

    form_ajax_refs = {"organization": {"fields": ("id", "name"), "page_size": 10}}

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
            ReimbursementPlan,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletPlanHDHPView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:reimbursement-wallet-hdhp-plan"
    edit_permission = "edit:reimbursement-wallet-hdhp-plan"
    delete_permission = "delete:reimbursement-wallet-hdhp-plan"
    read_permission = "read:reimbursement-wallet-hdhp-plan"

    column_exclude_list = (
        "created_at",
        "modified_at",
    )
    column_filters = [
        "id",
        "reimbursement_plan_id",
        "reimbursement_wallet_id",
        "alegeus_coverage_tier",
    ]

    form_excluded_columns = ("created_at", "modified_at")

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
            ReimbursementWalletPlanHDHP,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementPlanCoverageTierView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:alegeus-plan-coverage-tier"
    edit_permission = "edit:alegeus-plan-coverage-tier"
    create_permission = "create:alegeus-plan-coverage-tier"
    delete_permission = "delete:alegeus-plan-coverage-tier"

    column_exclude_list = ("created_at", "modified_at")
    form_excluded_columns = ("created_at", "modified_at")

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
            ReimbursementPlanCoverageTier,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementAccountTypeView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:alegeus-account-type"
    edit_permission = "edit:alegeus-account-type"
    create_permission = "create:alegeus-account-type"
    delete_permission = "delete:alegeus-account-type"

    column_list = ("id", "alegeus_account_type")

    form_excluded_columns = ("created_at", "modified_at")

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
            ReimbursementAccountType,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementAccountView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:reimbursement-wallet-alegeus-account"
    edit_permission = "edit:reimbursement-wallet-alegeus-account"
    create_permission = "create:reimbursement-wallet-alegeus-account"
    delete_permission = "delete:reimbursement-wallet-alegeus-account"

    column_exclude_list = ("created_at", "modified_at")

    column_filters = [
        "id",
        "reimbursement_wallet_id",
        ReimbursementAccountUserIdFilter(None, "User ID"),
        "reimbursement_plan_id",
        "status",
        "alegeus_account_type.alegeus_account_type",
    ]

    form_excluded_columns = ("created_at", "modified_at")

    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "wallet": SnowflakeQueryAjaxModelLoader(
                    "wallet",
                    self.session,
                    ReimbursementWallet,
                    fields=("id",),
                    page_size=10,
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
            ReimbursementAccount,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementClaimUserIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementRequest,
                ReimbursementRequest.id == ReimbursementClaim.reimbursement_request_id,
            )
            .join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementRequest.reimbursement_wallet_id,
            )
            .filter(ReimbursementWalletUsers.user_id == value)
        )


class ReimbursementClaimEmailFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementRequest,
                ReimbursementRequest.id == ReimbursementClaim.reimbursement_request_id,
            )
            .join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementRequest.reimbursement_wallet_id,
            )
            .join(User, ReimbursementWalletUsers.user_id == User.id)
            .filter(User.email == value)
        )


class ReimbursementClaimView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:reimbursement-claim"

    can_view_details = True

    column_list = (
        "id",
        "reimbursement_request",
        "alegeus_claim_id",
        "alegeus_claim_key",
        "amount",
        "status",
    )

    column_filters = [
        "id",
        "reimbursement_request_id",
        ReimbursementClaimUserIdFilter(None, "User Id Filter"),
        ReimbursementClaimEmailFilter(None, "Email Address Filter"),
        "alegeus_claim_id",
        "status",
    ]

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
            ReimbursementClaim,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementTransactionView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:reimbursement-transaction"

    column_exclude_list = (
        "created_at",
        "modified_at",
        "sequence_number",
        "description",
    )

    column_filters = [
        "id",
        "reimbursement_request_id",
        "reimbursement_request.wallet.member.id",
        "reimbursement_request.wallet.member.email",
        "alegeus_plan_id",
        "alegeus_transaction_key",
    ]

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
            ReimbursementTransaction,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletDebitCardView(MavenAuditedView):
    create_permission = "create:reimbursement-wallet-debit-card"
    edit_permission = "edit:reimbursement-wallet-debit-card"
    delete_permission = "delete:reimbursement-wallet-debit-card"
    read_permission = "read:reimbursement-wallet-debit-card"

    edit_template = "reimbursement_wallet_debit_card_edit_template.html"
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_list = (
        "reimbursement_wallet",
        "card_last_4_digits",
        "card_status",
        "created_date",
        "issued_date",
        "reimbursement_wallet.user_id",
        "reimbursement_wallet.reimbursement_organization_settings.organization.name",
    )

    column_labels = {
        "reimbursement_wallet.user_id": "User ID",
        "reimbursement_wallet.reimbursement_organization_settings.organization.name": "Organization Name",
    }

    column_filters = (
        "reimbursement_wallet_id",
        "card_status",
        "reimbursement_wallet.user_id",
        "reimbursement_wallet.reimbursement_organization_settings.organization.name",
    )

    form_excluded_columns = ("created_at", "modified_at")

    form_extra_fields = {
        # use the int-backed enum to populate the field
        "card_status_reason": Select2Field(
            "card_status_reason",
            choices=[
                (item[1].value, item[1].name)
                for item in CardStatusReason.__members__.items()
            ],
            coerce=lambda v: CardStatusReason(int(v)),
        )
    }

    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "reimbursement_wallet": SnowflakeQueryAjaxModelLoader(
                    "reimbursement_wallet",
                    self.session,
                    ReimbursementWallet,
                    fields=("id",),
                    page_size=10,
                )
            }
        return self._form_ajax_refs

    @action("report_lost_or_stolen", "Report Lost or Stolen & Request New Card")
    def report_lost_or_stolen(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        lost_or_stolen_wallets = (
            db.session.query(ReimbursementWallet)
            .filter(ReimbursementWallet.reimbursement_wallet_debit_card_id.in_(ids))
            .all()
        )
        for wallet in lost_or_stolen_wallets:
            report_lost_stolen_response = report_lost_stolen_debit_card(wallet)
            if report_lost_stolen_response:
                request_debit_card_reponse = request_debit_card(wallet)
                if request_debit_card_reponse:
                    flash(f"Success for wallet id: {wallet.id}", category="success")
                else:
                    flash(
                        f"Success report/lost stolen, failure issue new debit card for wallet id: {wallet.id}",
                        category="error",
                    )
            else:
                flash(
                    f"Failure report lost/stolen, can not request issue new debit card for wallet id: {wallet.id}",
                    category="error",
                )

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
            ReimbursementWalletDebitCard,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletDashboardView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:wallet-dashboard"
    edit_permission = "edit:wallet-dashboard"
    create_permission = "create:wallet-dashboard"
    delete_permission = "delete:wallet-dashboard"

    column_list = ("type",)

    form_excluded_columns = (
        "created_at",
        "modified_at",
        "cards",
    )

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
            ReimbursementWalletDashboard,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletDashboardCardView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:wallet-dashboard-card"
    edit_permission = "edit:wallet-dashboard-card"
    create_permission = "create:wallet-dashboard-card"
    delete_permission = "delete:wallet-dashboard-card"

    column_exclude_list = (
        "created_at",
        "modified_at",
    )
    column_sortable_list = ("title",)
    column_filters = ("title", "require_debit_eligible")

    form_excluded_columns = ("created_at", "modified_at")

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
            ReimbursementWalletDashboardCard,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletDashboardCardsView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:wallet-dashboard-cards"
    edit_permission = "edit:wallet-dashboard-cards"
    create_permission = "create:wallet-dashboard-cards"
    delete_permission = "delete:wallet-dashboard-cards"

    column_exclude_list = (
        "created_at",
        "modified_at",
    )
    column_sortable_list = ("order",)
    column_filters = (
        "reimbursement_wallet_dashboard_id",
        "reimbursement_wallet_dashboard_card_id",
        "order",
    )

    form_excluded_columns = (
        "created_at",
        "modified_at",
    )

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
            ReimbursementWalletDashboardCards,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletGlobalProceduresView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_exclude_list = (
        "created_at",
        "modified_at",
        "deleted_at",
    )
    column_sortable_list = ("name",)
    column_filters = ("name",)
    form_excluded_columns = ("created_at", "modified_at", "deleted_at")
    form_choices = {
        "credits": [(str(i), str(i)) for i in range(0, 13)],
    }

    def get_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return ReimbursementWalletGlobalProcedures.query.filter_by(deleted_at=None)

    def get_count_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # As per Flask admin documentation:
        #
        #   A ``query(self.model).count()`` approach produces an excessive
        #   subquery, so ``query(func.count('*'))`` should be used instead.
        return (
            self.session.query(func.count("*"))
            .select_from(self.model)
            .filter_by(deleted_at=None)
        )

    def delete_model(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.on_model_delete(model)
        # Soft delete by adding a datestamp to "deleted_at" column
        model.deleted_at = datetime.datetime.now()
        db.session.commit()
        self.after_model_delete(model)

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
            ReimbursementWalletGlobalProcedures,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class WalletClientReportView(MavenAuditedView):
    read_permission = "read:wallet-client-reports"
    edit_permission = "edit:wallet-client-reports"
    create_permission = "create:wallet-client-reports"
    delete_permission = "delete:wallet-client-reports"

    from flask_admin.actions import action

    create_template = "wallet_client_report_create_template.html"
    edit_template = "wallet_client_report_edit_template.html"
    column_list = (
        "id",
        "organization.name",
        "configuration",
        "start_date",
        "end_date",
        "client_submission_date",
        "client_approval_date",
        "payroll_date",
        "notes",
    )
    column_labels = {"organization.name": "Organization"}
    column_filters = (
        "id",
        "organization.name",
        "start_date",
        "end_date",
        "client_submission_date",
        "client_approval_date",
    )
    form_columns = (
        "organization",
        "configuration",
        "start_date",
        "end_date",
        "client_submission_date",
        "client_approval_date",
        "payroll_date",
        "notes",
        "reimbursement_requests",
    )
    form_edit_rules = (
        "organization",
        "start_date",
        "end_date",
        "client_submission_date",
        "client_approval_date",
        "payroll_date",
        "notes",
        "reimbursement_requests",
    )

    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "reimbursement_requests": SnowflakeQueryAjaxModelLoader(
                    "reimbursement_requests",
                    self.session,
                    ReimbursementRequest,
                    fields=("id",),
                    page_size=10,
                )
            }
        return self._form_ajax_refs

    def edit_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form = super().edit_form(obj=obj)
        org_id = form.organization.data.id
        # Only show reimbursement_requests linked to this org
        form.reimbursement_requests.query = (
            self.session.query(ReimbursementRequest)
            .join(ReimbursementWallet)
            .join(ReimbursementOrganizationSettings)
            .filter(ReimbursementOrganizationSettings.organization_id == org_id)
        )
        return form

    def after_model_change(self, form, model, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().after_model_change(form, model, is_created)
        # Assign Approved reimbursement_requests on report creation
        if is_created:
            assign_reimbursements_to_report(
                organization_id=model.organization.id,
                new_report_id=model.id,
                configuration_id=model.configuration_id,
            )
            db.session.commit()
            return

    @action("download_reports", "Download Reports in Zip File")
    def action_download_reports(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        reports = download_zipped_client_reports(ids)
        reports.seek(0)
        filename = f"wallet_reports_{datetime.datetime.today().date()}.zip"
        return send_file(  # type: ignore[call-arg] # Unexpected keyword argument "download_name" for "send_file"
            reports,
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename,
        )

    @action("download_ytd_reports", "Download YTD Report")
    def action_download_ytd_reports(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        configuration_ids = (
            db.session.query(self.model.configuration_id)
            .filter(self.model.id.in_(ids))
            .all()
        )

        if len(configuration_ids) > 1:
            flash("Please select reports with the same configurations!")
            return
        report, org_name = download_selected_client_reports(ids)
        report.seek(0)

        fp = io.BytesIO()
        fp.write(report.getvalue().encode())
        fp.seek(0)
        report.close()

        filename = (
            f"{org_name}_wallet_ytd_report_{datetime.datetime.today().date()}.csv"
        )
        return send_file(  # type: ignore[call-arg] # Unexpected keyword argument "download_name" for "send_file"
            fp,
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename,
        )

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
            WalletClientReports,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class WalletClientReportConfigurationFilterView(MavenAuditedView):
    form_columns = ["filter_type", "filter_value", "equal"]

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.id = fields.HiddenField()
        choices = [
            (t.value, f"Primary Expense: {t.value}")
            for t in ReimbursementRequestExpenseTypes
        ] + [(t.value, f"Country: {t.value}") for t in WalletReportConfigFilterCountry]
        form_class.filter_value = SelectField(
            "Filter Value",
            validators=[InputRequired()],
            widget=Select2Widget(),
            choices=choices,
        )
        return form_class

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
            WalletClientReportConfigurationFilter,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class WalletClientReportConfigurationView(
    PerInlineModelConverterMixin, MavenAuditedView
):
    read_permission = "read:wallet-client-report-configuration"
    edit_permission = "edit:wallet-client-report-configuration"
    create_permission = "create:wallet-client-report-configuration"
    delete_permission = "delete:wallet-client-report-configuration"

    column_list = (
        "id",
        "organization.name",
        "columns",
        "cadence",
        "day_of_week",
        "filters",
    )
    column_labels = {"organization.name": "Organization"}
    column_filters = ("id", "organization.name", "organization.id", "cadence")

    _inline_models = None

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if "columns" in form and not form.columns.data:
            flash("Select at least one column for the wallet report configuration")
            return False
        if "day_of_week" in form:
            day = form["day_of_week"].data
            if day < 1 or day > 31:
                flash("Please select valid day of week (1-31)")
                return False

            if "cadence" in form:
                cadence = form["cadence"].data
                if cadence == WalletReportConfigCadenceTypes.WEEKLY.name and day > 7:
                    flash("Please select valid day of week (1-7)")
                    return False

                if cadence == WalletReportConfigCadenceTypes.BIWEEKLY.name and day > 14:
                    flash("Please select valid day of week (1-14)")
                    return False

        if "filters" in form:
            valid_expense_types = {t.value for t in ReimbursementRequestExpenseTypes}
            valid_countries = {t.value for t in WalletReportConfigFilterCountry}

            all_countries: List[Set] = []
            all_expense_types: List[Set] = []

            for filter in form.filters.data:
                if (
                    filter["filter_type"]
                    == WalletReportConfigFilterType.PRIMARY_EXPENSE_TYPE.value
                ):
                    if filter["filter_value"].upper() not in valid_expense_types:
                        flash(
                            f"Please specify valid primary expense type, valid options are {valid_expense_types}"
                        )
                        return False
                    else:
                        value = {filter["filter_value"].upper()}
                        if filter["equal"]:
                            all_expense_types.append(value)
                        else:
                            all_expense_types.append(valid_expense_types - value)
                else:
                    if filter["filter_value"].upper() not in valid_countries:
                        flash(
                            f"Please specify valid country code, valid options are {valid_countries}"
                        )
                        return False
                    else:
                        value = {filter["filter_value"].upper()}
                        if filter["equal"]:
                            all_countries.append(value)
                        else:
                            all_countries.append(valid_countries - value)

            if reduce(lambda x, y: x.intersection(y), all_expense_types, set()):
                flash(
                    "Primary expense type has overlap, please don't specify duplicate or overlapped expense types"
                )
                return False
            if reduce(lambda x, y: x.intersection(y), all_countries, set()):
                flash(
                    "Country code has overlap, please don't specify duplicate or overlapped country codes"
                )
                return False
            if not self._check_filters_mutual_exclusive(
                expense_type_candidates=reduce(
                    lambda x, y: x.union(y), all_expense_types, set()
                ),
                country_candidates=reduce(
                    lambda x, y: x.union(y), all_countries, set()
                ),
                organization_id=form.organization.data.id,
                current_config_id=form._obj.id if form._obj else None,
            ):
                return False
        return super().validate_form(form)

    def _check_filters_mutual_exclusive(
        self,
        expense_type_candidates: Set[str],
        country_candidates: Set[str],
        organization_id: int,
        current_config_id: Optional[int] = None,
    ) -> bool:
        """
        This compares form filters with existing org configs to make sure they are mutually exclusive to each other,
        so that we make sure one reimbursement request should ONLY be included into one single client report.
        e.g. if one `US Fertility` configuration has been created for this org, then `US` should be rejected,
        but `US egg_freezing` should be accepted.
        """
        if not expense_type_candidates:
            expense_type_candidates = set(
                [t.value for t in ReimbursementRequestExpenseTypes]
            )
        if not country_candidates:
            country_candidates = {t.value for t in WalletReportConfigFilterCountry}

        org_configs = (
            db.session.query(self.model)
            .filter_by(organization_id=organization_id)
            .options(joinedload(self.model.filters))
            .all()
        )

        valid_expense_types = {t.value for t in ReimbursementRequestExpenseTypes}
        valid_countries = {t.value for t in WalletReportConfigFilterCountry}

        for org_config in org_configs:
            # if editing the form, ignore the current config in storage
            if current_config_id and org_config.id == current_config_id:
                continue

            filters = org_config.filters

            org_countries = set()
            org_expense_types = set()
            for fts in filters:
                if fts.filter_type == WalletReportConfigFilterType.COUNTRY:
                    if fts.equal:
                        org_countries.add(fts.filter_value)
                    else:
                        org_countries = org_countries.union(
                            valid_countries - {fts.filter_value}
                        )
                else:
                    if fts.equal:
                        org_expense_types.add(fts.filter_value)
                    else:
                        org_expense_types = org_expense_types.union(
                            valid_expense_types - {fts.filter_value}
                        )

            if not org_countries:
                org_countries = valid_countries
            if not org_expense_types:
                org_expense_types = valid_expense_types

            # if current org's any other configuration contains overlapped country and primary expense type,
            # the form creation or update should be rejected
            if (country_candidates & org_countries) and (
                expense_type_candidates & org_expense_types
            ):
                flash(
                    f"Conflict config with organization config: {org_config}, filters: {org_config.filters}"
                )
                return False
        return True

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # turn filter values to uppercase
        if model.filters:
            filters = model.filters
            for f in filters:
                f.filter_value = f.filter_value.upper()
            model.filters = filters
        super().on_model_change(form, model, is_created)

    @property
    def inline_models(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._inline_models is None:
            self._inline_models = (
                WalletClientReportConfigurationFilterView(
                    WalletClientReportConfigurationFilter, self.session
                ),
            )
        return self._inline_models

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
            WalletClientReportConfiguration,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class WalletClientReportReimbursementsView(MavenAuditedView):
    named_filter_urls = True
    read_permission = "read:wallet-client-report-reimbursement"
    edit_permission = "edit:wallet-client-report-reimbursement"
    create_permission = "create:wallet-client-report-reimbursement"
    delete_permission = "delete:wallet-client-report-reimbursement"

    list_template = "download_reimbursements_audit_file.html"
    column_list = (
        "wallet_client_report_id",
        "reimbursement_request_id",
        "reimbursement_request.wallet.user_id",
        "wallet_client_report.organization.name",
        "reimbursement_request.wallet.reimbursement_method",
        "reimbursement_request.reimbursement_type",
        "reimbursement_request.wallet.organization_employee.first_name",
        "reimbursement_request.wallet.organization_employee.last_name",
        "reimbursement_request.amount",
        "reimbursement_request.service_start_date",
        "wallet_client_report.client_approval_date",
        "peakone_sent_date",
        "wallet_client_report.payroll_date",
    )
    column_filters = [
        "reimbursement_request.reimbursement_type",
        "wallet_client_report.client_approval_date",
        "reimbursement_request_id",
        "reimbursement_request.wallet.user_id",
        "wallet_client_report.organization.name",
        "reimbursement_request.wallet.reimbursement_method",
        "reimbursement_request.service_start_date",
        "peakone_sent_date",
        "wallet_client_report.payroll_date",
    ]
    column_labels = {
        "wallet_client_report_id": "Report ID",
        "reimbursement_request.wallet.user_id": "User ID",
        "wallet_client_report.organization.name": "Organization",
        "reimbursement_request.wallet.reimbursement_method": "Reimbursement Method",
        "reimbursement_request.reimbursement_type": "Reimbursement Type",
        "reimbursement_request.wallet.organization_employee.first_name": "Employee First Name",
        "reimbursement_request.wallet.organization_employee.last_name": "Employee Last Name",
        "reimbursement_request.amount": "Amount ($)",
        "reimbursement_request.service_start_date": "Service Start Date",
        "wallet_client_report.client_approval_date": "Client Approval Date",
        "wallet_client_report.payroll_date": "Payroll Date",
    }
    column_formatters = {
        "reimbursement_request.amount": lambda v, c, m, p: cents_to_dollars_formatter(
            v, c, m.reimbursement_request, "amount"
        )
    }

    @expose("/")
    def index_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # A workaround to default a filter for reimbursement type = MANUAL that still allows
        # the admin user to change the parameters if necessary.
        if len(request.args) == 0 and request.path not in str(request.referrer):
            return redirect(request.path + "?flt1_reimbursement_type_equals=MANUAL")
        else:
            return super(WalletClientReportReimbursementsView, self).index_view()

    @action(
        "action_mark_sent",
        "Mark as Sent to Peakone",
        "Are you sure you want to set sent to peakone date as today?",
    )
    def action_mark_sent(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        report_reimbursements = WalletClientReportReimbursements.query.filter(
            WalletClientReportReimbursements.id.in_(ids)
        ).all()
        for rr in report_reimbursements:
            rr.peakone_sent_date = datetime.date.today()
        emit_bulk_audit_log_update(report_reimbursements)
        db.session.commit()
        flash(f"{len(report_reimbursements)} reimbursements updated")

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
            WalletClientReportReimbursements,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementRequestExchangeRatesView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:exchange-rates"
    edit_permission = "edit:exchange-rates"
    create_permission = "create:exchange-rates"
    delete_permission = "delete:exchange-rates"

    column_list = (
        "target_currency",
        "source_currency",
        "exchange_rate",
        "trading_date",
    )
    column_filters = ["target_currency", "trading_date"]
    column_sortable_list = ("trading_date", "target_currency")

    def _convert_date_to_utc(self, date_obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        date_value = datetime.datetime.combine(date_obj, datetime.time.min)
        utc_datetime = pytz.UTC.localize(date_value)
        return utc_datetime.strftime("%Y-%m-%d %H:%M:%S")

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model.trading_date:
            model.trading_date = self._convert_date_to_utc(model.trading_date)
        model.modified_at = self._convert_date_to_utc(model.modified_at)
        model.created_at = self._convert_date_to_utc(model.created_at)

        super().on_model_change(form, model, is_created)

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
            ReimbursementRequestExchangeRates,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class CountryCurrencyCodeView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:country-currency-code"
    edit_permission = "edit:country-currency-code"
    create_permission = "create:country-currency-code"
    delete_permission = "delete:country-currency-code"

    column_list = (
        "id",
        "country_alpha_2",
        "currency_code",
    )
    column_filters = ["country_alpha_2", "currency_code"]
    column_sortable_list = ("country_alpha_2", "currency_code")

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
            CountryCurrencyCode,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class MemberHealthPlanView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:member-health-plan"
    edit_permission = "edit:member-health-plan"
    create_permission = "create:member-health-plan"
    delete_permission = "delete:member-health-plan"

    column_list = (
        "id",
        "member_id",
        "employer_health_plan",
        "reimbursement_wallet",
        "is_subscriber",
        "subscriber_insurance_id",
        "subscriber_first_name",
        "subscriber_last_name",
        "subscriber_date_of_birth",
        "patient_first_name",
        "patient_last_name",
        "patient_date_of_birth",
        "patient_sex",
        "patient_relationship",
        "plan_type",
        "is_family_plan",
        "plan_start_at",
        "plan_end_at",
    )
    column_default_sort = ("id", True)
    column_filters = (
        "id",
        "employer_health_plan_id",
        "reimbursement_wallet_id",
        "member_id",
        "plan_start_at",
        "plan_end_at",
    )

    form_widget_args = {
        "id": {"readonly": True},
        "subscriber_first_name": {
            "placeholder": "required if member is the subscriber"
        },
        "subscriber_last_name": {"placeholder": "required if member is the subscriber"},
        "subscriber_date_of_birth": {
            "placeholder": "required if member is the subscriber"
        },
        "patient_first_name": {"placeholder": "required if member is the patient"},
        "patient_last_name": {"placeholder": "required if member is the patient"},
        "patient_date_of_birth": {"placeholder": "required if member is the patient"},
        "member_id": {"placeholder": "maven user id"},
    }

    form_excluded_columns = (
        "created_at",
        "modified_at",
        "is_family_plan",
    )

    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "reimbursement_wallet": SnowflakeQueryAjaxModelLoader(
                    "reimbursement_wallet",
                    self.session,
                    ReimbursementWallet,
                    fields=("id",),
                    page_size=10,
                )
            }
        return self._form_ajax_refs

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self._should_notify_of_dates(form):
            flash(
                "Consider setting the time for plan_end_at to 23:59:59, while plan_start_at should be 00:00:00, when creating a health plan.",
                "info",
            )
        return super().create_model(form)

    def update_model(self, form, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self._should_notify_of_dates(form):
            flash(
                f"While editing {model}, consider setting the time for plan_end_at to 23:59:59, while plan_start_at should be 00:00:00",
                "info",
            )
        return super().update_model(form, model)

    def _should_notify_of_dates(self, form) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            form.plan_end_at.data
            and (
                form.plan_end_at.data.hour != 23
                or form.plan_end_at.data.minute != 59
                or form.plan_end_at.data.second != 59
            )
        ) or (
            form.plan_start_at.data
            and (
                form.plan_start_at.data.hour != 0
                or form.plan_start_at.data.minute != 0
                or form.plan_start_at.data.second != 0
            )
        )

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
            MemberHealthPlan,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class HealthPlanYearToDateSpendView(BaseClassicalMappedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:health-plan-year-to-date-rx-spend"
    edit_permission = "edit:health-plan-year-to-date-rx-spend"
    delete_permission = "delete:health-plan-year-to-date-rx-spend"
    read_permission = "read:health-plan-year-to-date-rx-spend"

    repo = HealthPlanYearToDateSpendRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[HealthPlanYearToDateSpendRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")

    list_template = "list.html"

    can_view_details = True
    column_default_sort = ("id", True)
    column_list = (
        "id",
        "policy_id",
        "year",
        "first_name",
        "last_name",
        "source",
        "plan_type",
        "deductible_applied_amount",
        "oop_applied_amount",
        "bill_id",
        "transmission_id",
        "transaction_filename",
        "created_at",
        "modified_at",
    )
    column_filters = (
        "id",
        "policy_id",
        "year",
        "first_name",
        "last_name",
        "source",
        "bill_id",
    )
    column_labels = {
        "deductible_applied_amount": "Deductible Applied Amount ($)",
        "oop_applied_amount": "Oop Applied Amount ($)",
    }
    column_formatters = {
        "deductible_applied_amount": cents_to_dollars_formatter,
        "oop_applied_amount": cents_to_dollars_formatter,
    }
    form_overrides = {
        "deductible_applied_amount": AmountDisplayCentsInDollarsField,
        "oop_applied_amount": AmountDisplayCentsInDollarsField,
    }
    form_args = {
        "deductible_applied_amount": {"allow_negative": True},
        "oop_applied_amount": {"allow_negative": True},
    }
    form_excluded_columns = ("id", "created_at", "modified_at")

    @classmethod
    def instantiate_mapping(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if sqlalchemy.inspect(cls.repo.model, raiseerr=False) is None:  # type: ignore[has-type] # Cannot determine type of "repo"
            # Default value with dataclass break mapping, since SQLAlchemy detects class attribute value and
            # skip create a property for the column.
            # Having properties is a workaround for SQLAlchemy 1.3.x
            mapper = orm.mapper(
                cls.repo.model,  # type: ignore[has-type] # Cannot determine type of "repo"
                cls.repo.table,  # type: ignore[has-type] # Cannot determine type of "repo"
                properties={
                    "source": cls.repo.table.c.source,  # type: ignore[has-type] # Cannot determine type of "repo"
                    "plan_type": cls.repo.table.c.plan_type,  # type: ignore[has-type] # Cannot determine type of "repo"
                    "deductible_applied_amount": cls.repo.table.c.deductible_applied_amount,  # type: ignore[has-type] # Cannot determine type of "repo"
                    "oop_applied_amount": cls.repo.table.c.oop_applied_amount,  # type: ignore[has-type] # Cannot determine type of "repo"
                },
            )
            cls.repo.model.__mapper__ = mapper  # type: ignore[has-type] # Cannot determine type of "repo"


class ReimbursementCycleCreditsView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:reimbursement-wallet-cycle-credits"
    edit_permission = "edit:reimbursement-wallet-cycle-credits"
    delete_permission = "delete:reimbursement-wallet-cycle-credits"
    read_permission = "read:reimbursement-wallet-cycle-credits"

    edit_template = "reimbursement_cycle_credits_edit_template.html"
    column_list = (
        "reimbursement_wallet",
        "reimbursement_organization_settings_allowed_category",
        "amount",
    )
    column_filters = (
        "reimbursement_wallet_id",
        "reimbursement_organization_settings_allowed_category_id",
    )
    column_sortable_list = (
        "reimbursement_wallet",
        "reimbursement_organization_settings_allowed_category",
    )
    form_columns = (
        "reimbursement_wallet",
        "reimbursement_organization_settings_allowed_category",
        "amount",
    )

    form_widget_args = {
        "amount": {"readonly": True, "placeholder": 0},
    }

    def create_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form = super().create_form()
        if not form.amount.data:
            form.amount.data = 0
        return form

    def edit_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form = super().edit_form(obj)
        if "reimbursement_wallet" in form and form.reimbursement_wallet.data:
            wallet_org_setting_id = (
                form.reimbursement_wallet.data.reimbursement_organization_settings_id
            )
            form.reimbursement_organization_settings_allowed_category.query = (
                self.session.query(ReimbursementOrgSettingCategoryAssociation)
                .join(ReimbursementOrganizationSettings)
                .filter(ReimbursementOrganizationSettings.id == wallet_org_setting_id)
            )
        return form

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # Ensure wallet and org setting are valid
        wallet_org_setting_id = (
            form.reimbursement_wallet.data
            and form.reimbursement_wallet.data.reimbursement_organization_settings_id
        )
        wallet_allowed_category_org_setting_id = (
            form.reimbursement_organization_settings_allowed_category.data
            and form.reimbursement_organization_settings_allowed_category.data.reimbursement_organization_settings_id
        )
        if (
            wallet_org_setting_id
            and wallet_allowed_category_org_setting_id
            and wallet_org_setting_id != wallet_allowed_category_org_setting_id
        ):
            flash(
                "Reimbursement Wallet does not match Organization Allowed Category "
                f"{wallet_org_setting_id} != {wallet_allowed_category_org_setting_id}",
                category="error",
            )
            return False

        # Ensure this value doesn't already exist
        wallet_id = form.reimbursement_wallet.data and form.reimbursement_wallet.data.id
        org_settings_allowed_category_id = (
            form.reimbursement_organization_settings_allowed_category.data
            and form.reimbursement_organization_settings_allowed_category.data.reimbursement_organization_settings_id
        )
        rcc = ReimbursementCycleCredits.query.filter(
            ReimbursementCycleCredits.reimbursement_wallet_id == wallet_id,
            ReimbursementCycleCredits.reimbursement_organization_settings_allowed_category_id
            == org_settings_allowed_category_id,
        ).first()
        if rcc:
            flash(
                "ReimbursementCycleCredits row for this Wallet and Organization Allowed Category already exists:"
                f"id = {rcc.id}",
                category="error",
            )
            return False
        return super().validate_form(form)

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
            ReimbursementCycleCredits,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class PayerListView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:direct-payment-benefit-payer"
    edit_permission = "edit:direct-payment-benefit-payer"
    delete_permission = "delete:direct-payment-benefit-payer"
    read_permission = "read:direct-payment-benefit-payer"

    column_default_sort = ("id", True)
    column_filters = ("payer_name",)
    column_list = ["id", "payer_name", "payer_code"]

    @action("data_sourcing", "Payer Data Sourcing")
    def payer_data_sourcing(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        payers = db.session.query(Payer).filter(Payer.id.in_(ids)).all()
        for payer in payers:
            payer_name = payer.payer_name.value
            try:
                if payer_name.lower() == "esi":
                    AccumulationDataSourcerESI(
                        session=db.session
                    ).data_source_preparation_for_file_generation()
                else:
                    AccumulationDataSourcer(
                        payer_name, db.session
                    ).data_source_preparation_for_file_generation()
                flash(
                    f"Successfully processed data sourcing for {payer_name}", "success"
                )
            except Exception as e:
                flash(
                    f"Failed to process data sourcing for payer {payer_name}, {e}",
                    "error",
                )

    @action("file_generation", "Payer File Generation")
    def payer_file_generation(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        payers = db.session.query(Payer).filter(Payer.id.in_(ids)).all()
        for payer in payers:
            payer_name = payer.payer_name.value.lower()
            try:
                job = AccumulationFileGenerationJob(payer_name)
                job.run()
                flash(
                    f"Successfully processed file generation for {payer_name}",
                    "success",
                )
            except Exception as e:
                flash(
                    f"Failed to generate file for payer {payer_name}, {e}",
                    "error",
                )

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
            Payer,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class IngestionMetaView(BaseClassicalMappedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:esi-ingestion-meta-management"
    edit_permission = "edit:esi-ingestion-meta-management"
    delete_permission = "delete:esi-ingestion-meta-management"
    read_permission = "read:esi-ingestion-meta-management"

    repo = IngestionMetaRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[IngestionMetaRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")

    list_template = "list.html"
    can_view_details = True
    column_default_sort = ("task_id", True)

    column_list = (
        "task_id",
        "most_recent_raw",
        "most_recent_parsed",
        "task_started_at",
        "task_updated_at",
        "max_retries",
        "duration_in_secs",
        "target_file",
        "task_status",
        "task_type",
        "job_type",
        "created_at",
        "modified_at",
    )

    column_filters = ("task_status", "task_type", "job_type")

    form_columns = (
        "job_type",
        "target_file",
    )

    @classmethod
    def instantiate_mapping(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if sqlalchemy.inspect(cls.repo.model, raiseerr=False) is None:  # type: ignore[has-type] # Cannot determine type of "repo"
            # Default value with dataclass break mapping, since SQLAlchemy detects class attribute value and
            # skip create a property for the column.
            # Having properties is a workaround for SQLAlchemy 1.3.x
            mapper = orm.mapper(
                cls.repo.model,  # type: ignore[has-type] # Cannot determine type of "repo"
                cls.repo.table,  # type: ignore[has-type] # Cannot determine type of "repo"
                properties={
                    "task_status": cls.repo.table.c.task_status,  # type: ignore[has-type] # Cannot determine type of "repo"
                    "job_type": cls.repo.table.c.job_type,  # type: ignore[has-type] # Cannot determine type of "repo"
                    "task_type": cls.repo.table.c.task_type,  # type: ignore[has-type] # Cannot determine type of "repo"
                },
            )
            cls.repo.model.__mapper__ = mapper  # type: ignore[has-type] # Cannot determine type of "repo"

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        target_file = str(form.data["target_file"])
        job_type = str(form.data["job_type"])
        ingest.delay(
            job_type=job_type,
            task_type=TaskType.FIXUP,
            fixup_file=target_file,
            caller="create_model",
        )
        flash("Scheduled task!")
        return True


class AnnualInsuranceQuestionnaireResponseView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    edit_permission = "edit:annual-insurance-questionnaire-responses"
    delete_permission = "delete:annual-insurance-questionnaire-responses"
    read_permission = "read:annual-insurance-questionnaire-responses"

    can_view_details = True

    column_list = (
        "id",
        "wallet_id",
        "questionnaire_id",
        "user_response_json",
        "submitting_user_id",
        "sync_status",
        "sync_attempt_at",
        "survey_year",
        "created_at",
        "modified_at",
        "questionnaire_type",
    )

    column_sortable_list = (
        "wallet_id",
        "id",
        "submitting_user_id",
    )
    column_filters = (
        "wallet_id",
        "id",
        "submitting_user_id",
    )

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
            AnnualInsuranceQuestionnaireResponse,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class PharmacyPrescriptionView(BaseClassicalMappedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    edit_permission = "edit:smp-pharmacy-prescription"
    delete_permission = "delete:smp-pharmacy-prescription"
    read_permission = "read:smp-pharmacy-prescription"

    repo = PharmacyPrescriptionRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[PharmacyPrescriptionRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")

    list_template = "list.html"

    can_view_details = True
    column_default_sort = ("id", True)
    column_list = (
        "id",
        "user_id",
        "status",
        "treatment_procedure_id",
        "reimbursement_request_id",
        "user_benefit_id",
        "maven_benefit_id",
        "rx_unique_id",
        # TODO: BEX-3362
        "amount_owed",
        "ncpdp_number",
        "ndc_number",
        "rx_name",
        "rx_first_name",
        "rx_last_name",
        "rx_order_id",
        "rx_received_date",
        "scheduled_ship_date",
        "actual_ship_date",
        "rx_filled_date",
        "cancelled_date",
        "created_at",
        "modified_at",
    )
    column_filters = (
        "id",
        "rx_unique_id",
        "ndc_number",
        "treatment_procedure_id",
        "reimbursement_request_id",
        "user_id",
        # TODO: BEX-3362
        "maven_benefit_id",
        "user_benefit_id",
        "status",
    )
    column_labels = {
        "rx_first_name": "First Name",
        "rx_last_name": "Last Name",
        "rx_order_id": "Order ID",
        "rx_received_date": "Received Date",
        "rx_filled_date": "Filled Date",
        "maven_benefit_id": "Wallet Benefit ID",
    }
    form_excluded_columns = ("id", "created_at", "modified_at")


def _format_reimbursement_organization_settings_allowed_category(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    view, context, model, name
) -> str:
    category = model.reimbursement_organization_settings_allowed_category
    if category:
        org_settings = category.reimbursement_organization_settings
        org = org_settings.organization
        return f"Allowed Category ID: {category.id}  Org Settings ID: {category.reimbursement_organization_settings_id} for {org.name if org else '<No org configured for ROS>'} "
    else:
        return ""


class ReimbursementOrgSettingsAllowedCategoryRuleView(BaseClassicalMappedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = (
        "create:reimbursement-organization-settings-allowed-category-rule"
    )
    edit_permission = "edit:reimbursement-organization-settings-allowed-category-rule"
    delete_permission = (
        "delete:reimbursement-organization-settings-allowed-category-rule"
    )
    read_permission = "read:reimbursement-organization-settings-allowed-category-rule"

    can_view_details = True

    column_list = (
        "id",
        "reimbursement_organization_settings_allowed_category_id",
        "rule_name",
        "started_at",
    )

    column_filters = (
        "id",
        "reimbursement_organization_settings_allowed_category_id",
        "rule_name",
    )

    column_labels = {
        "reimbursement_organization_settings_allowed_category_id": "Reimbursement Org Setting Allowed Category",
        "rule_name": "Allowed Category Rule Name",
    }

    form_choices = {
        "rule_name": [(rule, rule) for rule in RULE_REGISTRATION_MAP.keys()]
    }
    column_formatters = {
        "reimbursement_organization_settings_allowed_category_id": _format_reimbursement_organization_settings_allowed_category
    }

    form_excluded_columns = ("created_at", "modified_at", "uuid")
    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "reimbursement_organization_settings_allowed_category_id": SnowflakeQueryAjaxModelLoader(
                    "reimbursement_organization_settings_allowed_category_id",
                    self.session,
                    ReimbursementOrgSettingCategoryAssociation,
                    fields=("id",),
                    page_size=10,
                ),
            }
        return self._form_ajax_refs

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[override] # Argument 1 of "factory" is incompatible with supertype "BaseClassicalMappedView"; supertype defines the argument type as "scoped_session" #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy") #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            ReimbursementOrgSettingsAllowedCategoryRule,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletAllowedCategoryRulesEvaluationResultView(
    BaseClassicalMappedView
):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:reimbursement-wallet-allowed-category-rules-eval-result"
    can_view_details = True

    column_list = (
        "id",
        "reimbursement_organization_settings_allowed_category_id",
        "reimbursement_wallet_id",
        "executed_category_rule",
        "failed_category_rule",
        "evaluation_result",
    )

    column_filters = (
        "id",
        "reimbursement_organization_settings_allowed_category_id",
        "reimbursement_wallet_id",
        "evaluation_result",
    )

    column_labels = {
        "reimbursement_organization_settings_allowed_category_id": "Reimbursement Org Setting Allowed Category ID",
    }

    form_excluded_columns = ("created_at", "modified_at")
    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "reimbursement_wallet": SnowflakeQueryAjaxModelLoader(
                    "reimbursement_wallet",
                    self.session,
                    ReimbursementWallet,
                    fields=("id",),
                    page_size=10,
                ),
                "reimbursement_organization_settings_allowed_category_id": SnowflakeQueryAjaxModelLoader(
                    "reimbursement_organization_settings_allowed_category_id",
                    self.session,
                    ReimbursementOrgSettingCategoryAssociation,
                    fields=("id",),
                    page_size=10,
                ),
            }
        return self._form_ajax_refs

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[override] # Argument 1 of "factory" is incompatible with supertype "BaseClassicalMappedView"; supertype defines the argument type as "scoped_session" #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy") #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            ReimbursementWalletCategoryRuleEvaluationResult,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletAllowedCategorySettingsView(BaseClassicalMappedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:reimbursement-wallet-allowed-category-settings"
    edit_permission = "edit:reimbursement-wallet-allowed-category-settings"
    delete_permission = "delete:reimbursement-wallet-allowed-category-settings"
    read_permission = "read:reimbursement-wallet-allowed-category-settings"

    can_view_details = True

    column_list = (
        "id",
        "reimbursement_organization_settings_allowed_category_id",
        "reimbursement_wallet_id",
        "access_level",
        "access_level_source",
    )

    column_filters = (
        "id",
        "reimbursement_organization_settings_allowed_category_id",
        "reimbursement_wallet_id",
        "access_level",
    )

    column_formatters = {
        "reimbursement_organization_settings_allowed_category_id": _format_reimbursement_organization_settings_allowed_category
    }

    column_labels = {
        "reimbursement_organization_settings_allowed_category_id": "Reimbursement Org Setting Allowed Category",
    }

    form_excluded_columns = ("created_at", "modified_at", "uuid", "updated_by")
    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "reimbursement_wallet": SnowflakeQueryAjaxModelLoader(
                    "reimbursement_wallet",
                    self.session,
                    ReimbursementWallet,
                    fields=("id",),
                    page_size=10,
                ),
                "reimbursement_organization_settings_allowed_category_id": SnowflakeQueryAjaxModelLoader(
                    "reimbursement_organization_settings_allowed_category_id",
                    self.session,
                    ReimbursementOrgSettingCategoryAssociation,
                    fields=("id",),
                    page_size=10,
                ),
            }
        return self._form_ajax_refs

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)
        model.updated_by = login.current_user.id

    @action(
        "enroll_wallet_in_alegeus",
        "Retry Enroll Wallet Category in Alegeus",
        "Did you confirm this wallet is not already enrolled in Alegeus for this category's plan?",
    )
    def action_enroll_wallet_in_alegeus(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(ids) != 1:
            flash(
                "Please enroll just one wallet category at a time...",
                category="warning",
            )
            return

        setting = (
            db.session.query(ReimbursementWalletAllowedCategorySettings)
            .filter(ReimbursementWalletAllowedCategorySettings.id.in_(ids))
            .one()
        )

        if setting.access_level != CategoryRuleAccessLevel.FULL_ACCESS:
            flash(
                "Allowed Category Settings access level must be FULL_ACCESS to enroll category plan.",
                category="error",
            )
            return

        success, messages = configure_wallet_allowed_category(
            wallet=setting.reimbursement_wallet,
            allowed_category_id=setting.reimbursement_organization_settings_allowed_category_id,
        )
        if success:
            flash(
                message=f"Successfully enrolled in Alegeus plan for wallet: {setting.reimbursement_wallet_id} into category: {setting.reimbursement_organization_settings_allowed_category_id}",
                category="success",
            )
        else:
            if messages:
                for flash_message in messages:
                    flash(
                        message=flash_message.message,
                        category=flash_message.category.value,
                    )
            flash(
                message=f"Failed to enroll in Alegeus plan for wallet: {setting.reimbursement_wallet_id} into category: {setting.reimbursement_organization_settings_allowed_category_id}.",
                category="error",
            )

    @action("wallet_rule_evaluation", "Process Wallet Category Settings")
    def evaluate_wallet_rules(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        settings = (
            db.session.query(ReimbursementWalletAllowedCategorySettings)
            .filter(ReimbursementWalletAllowedCategorySettings.id.in_(ids))
            .all()
        )
        category_activation_service = CategoryActivationService(session=db.session)
        for setting in settings:
            try:
                category_activation_service.process_wallet_category_rule(
                    allowed_category_id=setting.reimbursement_organization_settings_allowed_category.id,
                    wallet=setting.reimbursement_wallet,
                    process_delay=True,
                    bypass_alegeus=False,
                )
            except Exception as e:
                flash(
                    f"Failed to processed wallet category rules for setting ids {ids}, {e}",
                    "error",
                )
        try:
            category_activation_service.session.commit()
        except Exception as e:
            category_activation_service.session.rollback()
            flash(
                f"Failed to processed wallet category rules for setting ids {ids}, {e}",
                "error",
            )
        flash(
            f"Successfully processed wallet category rules for setting ids {ids}."
            f" Attempting to enroll wallet into new categories if applicable."
            f" (Watch for Alegeus alerts if unsuccessful.)",
            "success",
        )

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[override] # Argument 1 of "factory" is incompatible with supertype "BaseClassicalMappedView"; supertype defines the argument type as "scoped_session" #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy") #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            ReimbursementWalletAllowedCategorySettings,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementOrgSettingsExpenseTypeView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:expense-type-taxation-status-config"
    edit_permission = "edit:expense-type-taxation-status-config"
    delete_permission = "delete:expense-type-taxation-status-config"
    read_permission = "read:expense-type-taxation-status-config"

    column_default_sort = ("id", True)
    column_list = (
        "id",
        "reimbursement_organization_settings_id",
        "expense_type",
        "taxation_status",
        "reimbursement_method",
    )

    column_filters = (
        "reimbursement_organization_settings_id",
        "expense_type",
        "taxation_status",
        "reimbursement_method",
    )

    form_columns = (
        "reimbursement_organization_settings_id",
        "expense_type",
        "taxation_status",
        "reimbursement_method",
    )

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
            ReimbursementOrgSettingsExpenseType,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletE9YMetaView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:reimbursement-wallet-e9y-meta"
    edit_permission = "edit:reimbursement-wallet-e9y-meta"
    delete_permission = "delete:reimbursement-wallet-e9y-meta"
    read_permission = "read:reimbursement-wallet-e9y-meta"

    can_view_details = True

    column_list = (
        "id",
        "wallet_id",
        "sync_time",
        "sync_initiator",
        "change_type",
        "previous_end_date",
        "latest_end_date",
        "previous_ros_id",
        "latest_ros_id",
        "user_id",
        "dependents_ids",
        "is_dry_run",
        "previous_wallet_state",
    )

    column_filters = (
        "id",
        "wallet_id",
        "user_id",
        "is_dry_run",
    )

    form_excluded_columns = (
        "created_at",
        "modified_at",
        "uuid",
        "updated_by",
        "sync_time",
        "sync_initiator",
        "change_type",
        "previous_end_date",
        "latest_end_date",
        "previous_ros_id",
        "latest_ros_id",
        "user_id",
        "dependents_ids",
        "previous_wallet_state",
    )

    def scaffold_form(self):  # type: ignore[no-untyped-def]
        form_class = super().scaffold_form()
        form_class.bypass_alegeus = BooleanField(
            description="Check this box to bypass Alegeus processing"
        )
        return form_class

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        bypass_alegeus = form.bypass_alegeus.data
        wallet = db.session.query(ReimbursementWallet).get(int(form.wallet.raw_data[0]))
        super().on_model_change(form, model, is_created)
        dry_run = model.is_dry_run
        if is_created:
            service = WalletEligibilityService(
                db.session, dry_run=dry_run, bypass_alegeus=bypass_alegeus
            )
            if not wallet or wallet.state != WalletState.QUALIFIED:
                flash("Wallet not exist or state not equal to qualified")
                return None
            return service.process_wallet(wallet, sync_indicator=SyncIndicator.MANUAL)

    def create_model(self, form):  # type: ignore[no-untyped-def]
        try:
            model = self.model()
            bypass_alegeus = form.bypass_alegeus.data

            # Call on_model_change to populate and modify the model
            model = self.on_model_change(form, model, is_created=True)
            if model is None:
                # Handle the case where model update failed
                self.session.rollback()
                return False

            if form.is_dry_run.data:
                # Provide detailed information about what would happen
                message = f"""
                    Dry run completed successfully. If executed, would:
                    - Create sync record for wallet: {model.wallet_id}
                    - Sync initiator: {model.sync_initiator}
                    - Bypass Alegeus: {bypass_alegeus}
                    No changes were committed to database.
                """
                flash(message, "info")
                self.session.rollback()
                return True
            else:
                self.session.add(model)
                self.session.commit()
                self.after_model_change(form, model, is_created=True)
                return True

        except Exception as ex:
            self.session.rollback()
            flash(f"Error during operation: {str(ex)}", "error")
            return False

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[override] # Argument 1 of "factory" is incompatible with supertype "BaseClassicalMappedView"; supertype defines the argument type as "scoped_session" #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy") #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            ReimbursementWalletEligibilitySyncMeta,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementWalletE9YBlackListView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:reimbursement-wallet-e9y-black-list"
    edit_permission = "edit:reimbursement-wallet-e9y-black-list"
    delete_permission = "delete:reimbursement-wallet-e9y-black-list"
    read_permission = "read:reimbursement-wallet-e9y-black-list"

    can_view_details = True
    column_list = (
        "creator_id",
        "reimbursement_wallet_id",
        "reason",
        "deleted_at",
    )

    column_filters = (
        "reimbursement_wallet_id",
        "creator_id",
    )
    form_ajax_refs = {
        "creator": {"fields": ("id", "email"), "page_size": 10},
        "reimbursement_wallet": SnowflakeQueryAjaxModelLoader(
            "reimbursement_wallet",
            db.session,
            ReimbursementWallet,
            fields=("id",),
            page_size=10,
        ),
    }

    form_excluded_columns = ("created_at", "modified_at", "uuid", "updated_by")

    def create_form(self, obj=None):  # type: ignore[no-untyped-def]
        form = super().create_form(obj)
        if not form.creator.data:
            form.creator.data = db.session.query(User).get(login.current_user.id)
        return form

    def on_model_change(self, form, model, is_created):  # type: ignore[no-untyped-def]
        # Set the creator_id to the current user
        model.creator_id = login.current_user.id
        super().on_model_change(form, model, is_created)

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[override] # Argument 1 of "factory" is incompatible with supertype "BaseClassicalMappedView"; supertype defines the argument type as "scoped_session" #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy") #type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            ReimbursementWalletBlacklist,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReimbursementServiceCategoryView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:reimbursement-service-category"
    edit_permission = "edit:reimbursement-service-category"
    delete_permission = "delete:reimbursement-service-category"
    read_permission = "read:reimbursement-service-category"

    column_default_sort = "category"
    column_list = (
        "category",
        "name",
    )

    column_filters = ("category",)

    column_labels = {
        "category": "Service Category ID",
        "name": "Service Category Name",
    }

    form_excluded_columns = (
        "created_at",
        "modified_at",
    )

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
            ReimbursementServiceCategory,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class WalletExpenseSubtypeView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:wallet-expense-subtype"
    edit_permission = "edit:wallet-expense-subtype"
    delete_permission = "delete:wallet-expense-subtype"
    read_permission = "read:wallet-expense-subtype"

    column_default_sort = [("expense_type", False), ("code", False)]

    column_list = (
        "expense_type",
        "reimbursement_service_category",
        "code",
        "visible",
        "description",
        "global_procedure_id",
    )

    column_filters = (
        "expense_type",
        "reimbursement_service_category",
        "code",
        "visible",
        "global_procedure_id",
    )

    column_formatters = {
        "reimbursement_service_category": lambda v, c, m, p: m.reimbursement_service_category.category
    }

    column_labels = {
        "reimbursement_service_category": "Service Category",
        "code": "Service Category Code",
        "description": "Service Category Code Description",
    }

    form_columns = (
        "expense_type",
        "reimbursement_service_category",
        "code",
        "visible",
        "description",
        "global_procedure_id",
    )

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
            WalletExpenseSubtype,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
