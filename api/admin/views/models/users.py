from __future__ import annotations

import datetime
import json
import os
import uuid
from typing import Any, Type

import flask_login as login
import pytz
import sqlalchemy
from flask import Markup, abort, flash, jsonify, redirect, request, url_for
from flask_admin import expose
from flask_admin.actions import action
from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader
from flask_admin.contrib.sqla.fields import QuerySelectMultipleField
from flask_admin.contrib.sqla.filters import (
    BooleanEqualFilter,
    DateTimeBetweenFilter,
    FilterInList,
)
from flask_admin.form import DatePickerWidget, rules, upload
from flask_admin.model.ajax import DEFAULT_PAGE_SIZE
from flask_admin.model.helpers import get_mdict_item_or_list
from maven import feature_flags
from sqlalchemy import String, and_, cast, func, or_, orm, true
from sqlalchemy.exc import InternalError, ProgrammingError
from sqlalchemy.orm import aliased, joinedload, load_only
from wtforms import fields, form, validators

from admin.common import Select2MultipleField, https_url
from admin.contants import DOULA_ONLY_BANNER_MESSAGE
from admin.views.base import (
    USER_AJAX_REF,
    AdminCategory,
    AdminViewT,
    BulkUpdateForm,
    ContainsFilter,
    DictToJSONField,
    InlineCollectionView,
    IsFilter,
    MavenAuditedView,
    ModalUpdateMixin,
    SimpleSortViewMixin,
)
from admin.views.models.images import ImageUploadField
from admin.views.models.member_risks import MemberRisksAdminModel
from admin.views.models.phone import PhoneNumberFilter
from admin.views.models.practitioner import (
    PractitionerAvailabilityView,
    PractitionerHelpers,
)
from appointments.models.appointment import Appointment
from appointments.models.needs_and_categories import (
    Need,
    NeedAppointment,
    NeedCategory,
    NeedCategoryTrack,
    NeedRestrictedVertical,
    NeedTrack,
    NeedVertical,
)
from appointments.models.payments import Credit
from appointments.models.reschedule_history import RescheduleHistory
from appointments.models.schedule import Schedule
from appointments.models.schedule_event import ScheduleEvent
from appointments.services.schedule import update_practitioner_profile_next_availability
from assessments.utils.assessment_exporter import (
    AssessmentExporter,
    AssessmentExportTopic,
)
from audit_log.utils import (
    emit_audit_log_update,
    emit_bulk_audit_log_read,
    emit_bulk_audit_log_update,
)
from authn.domain.service import authn
from authn.models.email_domain_denylist import EmailDomainDenylist
from authn.models.sso import ExternalIdentity
from authn.models.user import User
from authn.resources.admin import BaseClassicalMappedView
from authz.models.roles import ROLES
from care_advocates.models.assignable_advocates import AssignableAdvocate
from care_advocates.models.matching_rules import (
    MatchingRuleEntityType,
    MatchingRuleSet,
    MatchingRuleType,
)
from common.health_data_collection.question_api import get_question_slug_user_answers
from common.health_data_collection.user_assessment_status_api import (
    get_user_assessments_by_user_id,
)
from common.health_profile.health_profile_service_models import Modifier
from common.payments_gateway import get_client
from common.services.stripe import StripeCustomerClient
from common.services.stripe_constants import PAYMENTS_STRIPE_API_KEY
from direct_payment.billing.constants import INTERNAL_TRUST_PAYMENT_GATEWAY_URL
from eligibility import service as e9y_service
from eligibility.e9y import model as e9y_model
from geography.repository import CountryRepository, SubdivisionRepository
from health.data_models.member_risk_flag import MemberRiskFlag
from health.data_models.risk_flag import RiskFlag
from health.models.health_profile import HealthProfile
from health.services.health_profile_service import HealthProfileService
from members.models.async_encounter_summary import AsyncEncounterSummary
from models import tracks
from models.enterprise import (
    OnboardingState,
    Organization,
    UserAsset,
    UserAssetState,
    UserOnboardingState,
)
from models.gdpr import GDPRDeletionBackup, GDPRUserRequest
from models.products import Product, add_products
from models.profiles import (
    Address,
    Agreement,
    AgreementAcceptance,
    AgreementNames,
    CareTeamTypes,
    Certification,
    Characteristic,
    Device,
    Language,
    MemberPractitionerAssociation,
    MemberProfile,
    OrganizationAgreement,
    PractitionerProfile,
    PractitionerSubdivision,
    State,
    agreement_admin_display_name,
    practitioner_verticals,
)
from models.programs import Module
from models.referrals import PractitionerInvite, ReferralCodeUse
from models.tracks import ChangeReason, MemberTrack, TrackLifecycleError, TrackName
from models.tracks.client_track import ClientTrack, TrackModifiers
from models.verticals_and_specialties import (
    Specialty,
    SpecialtyKeyword,
    Vertical,
    VerticalAccessByTrack,
    VerticalGroup,
    VerticalGroupTrack,
    VerticalGroupVersion,
    is_cx_vertical_name,
)
from preferences.repository import MemberPreferencesRepository, PreferenceRepository
from provider_matching.services.matching_engine import state_match_not_permissible
from providers.service.provider import ProviderService
from storage.connection import RoutingSQLAlchemy, db
from tasks.assets import complete_upload
from tasks.braze import sync_practitioner_with_braze
from tasks.marketing import track_user_in_braze
from tasks.users import send_password_reset
from tracks import service as tracks_service
from tracks.utils.common import get_active_member_track_modifiers
from utils.exceptions import ProgramLifecycleError
from utils.gdpr_backup_data import GDPRDataDelete
from utils.log import logger
from utils.slack_v2 import notify_provider_ops_alerts_channel
from utils.user_assessments import get_user_track_and_started_needs_assessments
from views.schemas.vertical import ValidationError, VerticalProductSchema
from wallet.models.constants import MemberType
from wallet.models.member_benefit import MemberBenefit
from wallet.models.models import WalletBalance
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)
from wallet.services.reimbursement_benefits import get_member_type_details
from wallet.services.reimbursement_wallet import ReimbursementWalletService
from wallet.tasks.alegeus import remove_member_number, update_member_demographics
from wallet.utils.eligible_wallets import qualified_reimbursement_wallet

log = logger(__name__)


class DateOfBirthFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        stripped_value = value.strip().lower()
        if stripped_value in ("none", "null"):
            stripped_value = None
        return query.join(
            HealthProfile,
            HealthProfile.user_id == MemberProfile.user_id,
        ).filter(HealthProfile.date_of_birth == stripped_value)


class WalletBenefitIdFilter(IsFilter):
    def apply(self, query, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.outerjoin(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.user_id == MemberProfile.user_id,
            )
            .outerjoin(
                ReimbursementWalletBenefit,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWalletBenefit.reimbursement_wallet_id,
            )
            .outerjoin(MemberBenefit, MemberBenefit.user_id == MemberProfile.user_id)
            .filter(
                or_(
                    ReimbursementWalletBenefit.maven_benefit_id == value,
                    func.lower(MemberBenefit.benefit_id) == func.lower(value),
                )
            )
        )


class RestrictedVerticalInlineCollection(InlineCollectionView):
    parent_attribute = "specialty_restricted_verticals"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "InlineCollectionView" defined the type as "None")
    child_pk = "need_vertical_id"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "InlineCollectionView" defined the type as "None")

    def get_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        class RVForm(form.Form):
            vertical_id = fields.SelectField(
                "Vertical",
                validators=[validators.InputRequired()],
                choices=[
                    (v.id, str(v))
                    for v in db.session.query(Vertical)
                    .filter(Vertical.deleted_at == None)
                    .all()
                ],
                coerce=int,
            )
            specialties = QuerySelectMultipleField(
                label="Specialties",
                query_factory=lambda: Specialty.query,
            )
            need_vertical_id = fields.HiddenField()

        return RVForm

    def get_collection(self, need: Need):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return need.get_restricted_verticals()

    def set_collection(self, need: Need, collection):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        restricted_verticals = []
        for ele in collection:
            if ele["should_delete"]:
                # delete vertical
                db.session.query(NeedVertical).filter(
                    NeedVertical.vertical_id == ele["data"].get("vertical_id")
                ).delete(synchronize_session="fetch")
                db.session.commit()
                continue

            # Add one restricted vertical for each specialty listed
            for specialty in ele["data"].get("specialties", []):
                # Add vertical to need if it doesn't exist
                vertical = (
                    db.session.query(Vertical)
                    .filter(
                        Vertical.id == ele["data"]["vertical_id"],
                    )
                    .one()
                )

                if vertical not in need.verticals:
                    need.verticals.append(vertical)

                restricted_verticals.append(
                    NeedRestrictedVertical.create(
                        need.id, ele["data"]["vertical_id"], specialty.id
                    )
                )

        need.put_restricted_verticals(restricted_verticals)

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
            RestrictedVerticalInlineCollection,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


def _member_note_display_info(view, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    p = model.member_profile
    if not p:
        return ""
    return "Followup send time: {}\nNote: {}".format(
        (
            p.follow_up_reminder_send_time.isoformat()
            if p.follow_up_reminder_send_time
            else None
        ),
        p.note[:75] + "..." if p.note and len(p.note) > 120 else p.note,
    )


def _risk_flags(view, context, model: User, name) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return ", ".join(f.name for f in model.current_risk_flags())


def _login_cc_email():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    email = login.current_user.email
    if "+prac" not in email:
        name, domain = email.split("@")
        email = f"{name}+prac@{domain}"
    return email


CAPACITY_FORMATTING_HTML = (
    '<div class="control-group">'
    '    <div class="control-label">'
    "        Daily Capacity:"
    "    </div>"
    '    <div class="controls">'
    "        <ul>"
)

CAPACITY_INFO_TEXT = "<i>*Capacity for matching is calculated per availability block. Capacity for booking is calculated per calendar day based on the practitioner's timezone as set in their user profile.</i>"


class UserView(MavenAuditedView):
    read_permission = "read:user"
    edit_permission = "edit:user"

    edit_template = "user_edit_template.html"

    column_sortable_list = ("created_at", "email", "username")
    column_list = ("id", "created_at", "email", "username", "esp_id", "active_tracks")
    column_labels = {
        "esp_id": "Member Hash Id",
        "active_tracks": "Program Module Name",
        "sms_phone_number": "Phone Number",
    }
    column_searchable_list = ("username", "email", "first_name", "last_name")
    column_filters = (User.id, User.email, User.active)
    column_descriptions = {
        "phone_number": "Please note: This is the phone number used for 2FA."
    }

    form_excluded_columns = [
        "assets",
        "codes",
        "posts",
        "bookmarks",
        "votes",
        "products",
        "health_profile",
        "modified_at",
        "schedule",
        "profiles",
        "password",
        "api_key",
        "otp_secret",
        "credits",
        "message_credits",
        "addresses",
        "organizations",
        "plan_purchases",
        "administrative_fees",
        "files",
        "managed_organizations",
        "program_history",
        "assessments",
        "practitioner_associations",
        "onboarding_state",  # this field will be added below in scaffold_form()
        "country",
        "member_benefit",
    ]

    column_formatters = {
        "active_tracks": lambda v, c, m, p: (
            ", ".join(track.name for track in m.active_tracks)
            if m.active_tracks
            else ""
        )
    }

    form_ajax_refs = {
        "devices": {"fields": ("id",), "page_size": 10},
        "install_attribution": {"fields": ("id",), "page_size": 10},
        "care_programs": {"fields": ("id",), "page_size": 10},
        "member_profile": {"fields": ("user_id",), "page_size": 10},
        "practitioner_profile": {"fields": ("user_id",), "page_size": 10},
        "reimbursement_wallets": {"fields": ("id",), "page_size": 10},
        "image": {"fields": ("id",), "page_size": 10},
        "user_organization_employees": {"fields": ("id",), "page_size": 10},
        "organization_employee": {"fields": ("id",), "page_size": 10},
        "member_tracks": {"fields": ("id", "name"), "page_size": 10},
        "current_member_track": {"fields": ("id", "name"), "page_size": 10},
        "active_tracks": {"fields": ("id", "name"), "page_size": 10},
        "inactive_tracks": {"fields": ("id", "name"), "page_size": 10},
        "scheduled_tracks": {"fields": ("id", "name"), "page_size": 10},
        "current_program": {
            "fields": ("id", "user_id", "organization_employee_id"),
            "page_size": 10,
        },
        "external_identities": {"fields": ("id",), "page_size": 10},
        "invite": {"fields": ("id",), "page_size": 10},
        "partner_invite": {"fields": ("id",), "page_size": 10},
    }

    form_widget_args = {
        "api_key": {"disabled": True},
        "esp_id": {"readonly": True},
        "password": {"disabled": True},
        "created_at": {"disabled": True},
        "external_identities": {"readonly": True},
    }

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        model = db.session.query(self.model).get(id)
        if model.onboarding_state:
            form.onboarding_state_options.data = model.onboarding_state.state

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form_onboarding_state_options = form.onboarding_state_options.data

        if form_onboarding_state_options:
            if (
                model.onboarding_state
                and form_onboarding_state_options != model.onboarding_state
            ):
                model.onboarding_state.state = form_onboarding_state_options
            else:
                model.onboarding_state = UserOnboardingState(
                    user_id=model.id,
                    state=OnboardingState(form_onboarding_state_options),
                )
        super().on_model_change(form, model, is_created)
        track_user_in_braze.delay(model.id, caller=self.__class__.__name__)
        if model.is_practitioner:
            sync_practitioner_with_braze.delay(model.id)

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.image_id = ImageUploadField(
            label="Image", allowed_extensions=["jpg", "jpeg", "png"]
        )

        # create a new field for this so we can set the values to the OnboardingState values,
        # rather than having one option for each row in the database
        onboarding_state_options = [("", None)] + [(x, x) for x in OnboardingState]
        form_class.onboarding_state_options = fields.SelectField(
            "Onboarding State", choices=onboarding_state_options
        )
        return form_class

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        id = get_mdict_item_or_list(request.args, "id")
        model = None
        if id:
            model = self.get_one(id)

        if request.method == "POST":
            auth_service = authn.AuthenticationService()
            # On Email changes we also want to update the user's email in the IDP
            new_email = request.form.get("email")
            model_email = model.email if model else None
            auth0_email = model_email
            if new_email and new_email != model_email:
                result = auth_service.update_email(
                    user_id=id, email=model_email, new_email=new_email
                )
                if not result:
                    # TODO: change back to 500 once address the https://mavenclinic.atlassian.net/browse/CPCS-2444
                    abort(400, "Something went wrong. Please try again.")
                auth0_email = new_email
            # On user status change, we also update the user status on Auth0
            new_user_status = request.form.get("active")
            is_user_active = new_user_status == "y"
            log.info(f"New user status is {is_user_active}")
            model_user_status = model.active if model else None
            log.info(f"Current user status is {model_user_status}")
            if new_user_status != model_user_status:
                auth_service.user_access_control(user_id=id, is_active=is_user_active)
            # On user mfa state change, we also update the status and phone number on Auth0
            new_mfa_state = request.form.get("mfa_state")
            new_sms_phone_number = request.form.get("sms_phone_number")
            model_mfa_state = model.mfa_state if model else None
            model_sms_phone_number = (
                model.sms_phone_number if (model and model.sms_phone_number) else ""
            )
            if model_mfa_state:
                model_mfa_state = str(model_mfa_state).split(".")[1]
            log.info(
                f"mfa_state new {new_mfa_state} current {model_mfa_state} for user {id}"
            )
            log.info(
                f"sms_phone_number new {new_sms_phone_number[-4:]} current {model_sms_phone_number[-4:]} for user {id}"  # type: ignore[index] # Value of type "Optional[Any]" is not indexable
            )
            if (
                new_mfa_state == "ENABLED"
                and len(new_sms_phone_number) > 0  # type: ignore[arg-type] # Argument 1 to "len" has incompatible type "Optional[Any]"; expected "Sized"
                and (
                    new_mfa_state != model_mfa_state
                    or new_sms_phone_number != model_sms_phone_number
                )
            ):
                # update mfa_state to ENABLED, or sms phone number, or both
                auth_service.update_user_mfa(
                    user_id=id,
                    enable_mfa=True,
                    phone_number=new_sms_phone_number,  # type: ignore[arg-type] # Argument "phone_number" to "update_user_mfa" of "AuthenticationService" has incompatible type "Optional[Any]"; expected "str"
                    email=auth0_email,
                )
            elif new_mfa_state != "ENABLED" and model_mfa_state == "ENABLED":
                # update mfa_state from ENABLED to DISABLED or PENDING_VERIFICATION
                auth_service.update_user_mfa(user_id=id, enable_mfa=False)

        if model:
            devices = db.session.query(Device).filter(Device.user_id == model.id).all()
            self._template_args["devices"] = devices

        return super().edit_view()

    @action("reset_password", "Send Reset Password Email", "You Sure?")
    def reset_password(self, user_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for _id in user_ids:
            user = db.session.query(User).filter(User.id == _id).first()
            if user:
                send_password_reset.delay(user.id)
                log.debug("Triggered reset password for %s", user)

    @action(
        "rotate_api_key",
        "Rotate API Key",
        "You Sure? This will force a logout from the app.",
    )
    def rotate_api_key(self, user_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for _id in user_ids:
            user = db.session.query(User).filter(User.id == _id).first()
            if user:
                user.rotate_api_key()
                db.session.commit()
                log.debug("Triggered API key reset for %s", user)

    @action(
        "expire_credits",
        "Expire All Credits",
        "You Sure? This will expire all unused credits for a user.",
    )
    def expire_credits(self, user_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(user_ids) != 1:
            flash("Only use for one user at a time!")
            return redirect(https_url("admin.index"))

        user = db.session.query(User).filter(User.id == user_ids[0]).first()
        if user:
            credits = Credit.available_for_user(user).all()
            for credit in credits:
                credit.expires_at = datetime.datetime.utcnow()
                db.session.add(credit)
            db.session.commit()

            flash(f"All set expiring {len(credits)} credits")
        else:
            flash(f"Bad User ID: {user_ids[0]}")
            return redirect(https_url("admin.index"))

    @action(
        "reset_otp_secret",
        "Reset 2-Factor Authentication",
        "You sure? Your previous one time pass code will not work after reset "
        "and you must re-setup 2-factor authentication to access admin again.",
    )
    def reset_otp_secret(self, user_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for _id in user_ids:
            user = User.query.get(_id)
            if user:
                user.otp_secret = None
                db.session.commit()
                log.debug("Otp secret is reset for %s", user)
        flash("All done!")
        return redirect(https_url("user.index_view"))

    @action(
        "deactivate_users",
        "Deactivate Users",
        "You Sure? This will deactivate all selected users.",
    )
    def deactivate_users(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._update_active(ids, False)

    @action(
        "activate_users",
        "Activate Users",
        "You Sure? This will activate all selected users.",
    )
    def activate_users(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._update_active(ids, True)

    def _update_active(self, ids, active=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        auth_service = authn.AuthenticationService()
        for user_id in ids:
            auth_service.user_access_control(user_id=user_id, is_active=active)
        db.session.bulk_update_mappings(
            User,
            [{"id": id, "active": active} for id in ids],
        )
        db.session.commit()
        log.info(f"User(s) {ids} active flag set to {active}")
        flash(f"{len(ids)} Users active flag set to {active}.")

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
            User,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AgreementViewLanguageFilter(IsFilter):
    def get_options(self, view):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return tuple((str(l.id), l.name) for l in Language.query.all())
        except (ProgrammingError, RuntimeError, InternalError):
            # The schema has not been initialized yet. It should be soon.
            return ()

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(Agreement.language).filter(Language.id == value)


class AgreementViewNameFilter(IsFilter):
    def get_options(self, view):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return tuple(
                (n.value, agreement_admin_display_name(n)) for n in AgreementNames
            )
        except (ProgrammingError, RuntimeError, InternalError):
            # The schema has not been initialized yet. It should be soon.
            return ()

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.filter(Agreement.name == value)


class AgreementView(MavenAuditedView):
    read_permission = "read:agreement"
    delete_permission = "delete:agreement"
    create_permission = "create:agreement"
    edit_permission = "edit:agreement"

    column_list = ("admin_display_name", "version", "language")
    column_descriptions = {
        "accept_on_registration": "Automatically accept this agreement when a new User is registered.",
        "optional": "Whether acceptance of the agreement is required or can be skipped by the user",
    }
    column_filters = (
        AgreementViewNameFilter(None, "Name"),
        AgreementViewLanguageFilter(None, "Language"),
    )
    form_overrides = {"html": fields.TextAreaField}

    inline_models = (OrganizationAgreement,)

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)

        agreement = db.session.query(self.model).get(id)
        if agreement is None:
            return

        form.name.data = agreement.name.value

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.name = fields.SelectField(
            label="Name",
            choices=[
                (name.value, agreement_admin_display_name(name))
                for name in AgreementNames
            ],
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
            Agreement,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AgreementAcceptanceView(MavenAuditedView):
    read_permission = "read:agreement-acceptance"
    delete_permission = "delete:agreement-acceptance"
    edit_permission = "edit:agreement-acceptance"

    edit_template = "agreement_acceptance_edit_template.html"

    column_filters = (
        AgreementAcceptance.user_id,
        AgreementAcceptance.agreement_id,
        AgreementAcceptance.accepted,
    )

    form_ajax_refs = {"user": USER_AJAX_REF}
    form_widget_args = {
        "agreement": {"disabled": True},
        "user": {"disabled": True},
        "modified_at": {"disabled": True},
        "created_at": {"disabled": True},
    }

    def edit_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form = super().edit_form(obj=obj)
        if not form.agreement.data.optional:
            if form.accepted.render_kw:
                form.accepted.render_kw["disabled"] = True
            else:
                form.accepted.render_kw = {"disabled": True}

        return form

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)

        log.info(
            "Updating member agreement consent status",
            agreement_id=model.agreement_id,
            user_id=model.user_id,
            new_acceptance_status=form.accepted.data,
            modified_by=login.current_user.id,  # Admin user ID (e.g. CA)
        )

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not form.agreement.data.optional:
            db.session.rollback()
            flash(
                "Accepted status cannot be updated on required agreements",
                "error",
            )
            return

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
            AgreementAcceptance,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class PreferenceView(BaseClassicalMappedView):
    read_permission = "read:preference"
    delete_permission = "delete:preference"
    create_permission = "create:preference"
    edit_permission = "edit:preference"

    repo = PreferenceRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[PreferenceRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")
    can_view_details = True
    column_display_pk = True
    column_list = ("name", "type", "default_value")
    column_filters = ("name",)
    form_excluded_columns = ("created_at", "modified_at")

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.type = fields.SelectField(
            label="Type",
            choices=["bool", "str", "int"],
        )
        return form_class


class MemberPreferenceView(BaseClassicalMappedView):
    read_permission = "read:member-preference"
    delete_permission = "delete:member-preference"
    edit_permission = "edit:member-preference"

    repo = MemberPreferencesRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[MemberPreferencesRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")
    column_list = ("member_id", "preference_id", "value")
    column_filters = ("member_id", "preference_id")
    form_columns = ("member_id", "preference_id", "value")
    form_widget_args = {
        "member_id": {"readonly": True},
        "preference_id": {"readonly": True},
    }

    def _member_formatter(self, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        url = url_for("user.edit_view", id=model.member_id)
        return Markup(f"<a href='{url}'>User[{model.member_id}]</a>")

    def _preference_formatter(self, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        url = url_for("preference.edit_view", id=model.preference_id)
        return Markup(
            f"<a href='{url}'>Preference[{model.preference_id}]: {model.name}</a>"
        )

    column_formatters = {
        "member_id": _member_formatter,
        "preference_id": _preference_formatter,
    }

    def get_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if sqlalchemy.inspect(PreferenceRepository.model, raiseerr=False) is None:
            mapper = orm.mapper(PreferenceRepository.model, PreferenceRepository.table)
            PreferenceRepository.model.__mapper__ = mapper  # type: ignore[attr-defined] # "Type[Preference]" has no attribute "__mapper__"

        return self.session.query(
            self.model.id,
            self.model.member_id,
            self.model.preference_id,
            self.model.value,
            PreferenceRepository.model.name,
        ).join(
            PreferenceRepository.model,
            self.model.preference_id == PreferenceRepository.model.id,
        )


class ExternalIdentityView(MavenAuditedView):
    read_permission = "read:external-identity"
    can_view_details = True

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
            ExternalIdentity,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class DeviceView(MavenAuditedView):
    read_permission = "read:device"
    delete_permission = "delete:device"

    column_display_pk = False

    form_rules = ("device_id", "is_active")
    form_excluded_columns = ("created_at", "modified_at", "user_id", "application_name")

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
            Device,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class PractitionerProfileViewNextAvailabilityFilter(DateTimeBetweenFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        start, end = value
        return query.filter(PractitionerProfile.next_availability.between(start, end))


class PractitionerProfileViewVerticalFilter(ContainsFilter):
    def get_options(self, view):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return tuple(
                (str(v.id), v.name)
                for v in Vertical.query.filter(Vertical.deleted_at == None).all()
            )
        except (ProgrammingError, RuntimeError, InternalError):
            # The schema has not been initialized yet. It should be soon.
            return ()

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(PractitionerProfile.verticals).filter(Vertical.id == value)


class PractitionerProfileViewVerticalInFilter(FilterInList):
    def get_options(self, view):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return tuple(
                (str(v.id), v.name)
                for v in Vertical.query.filter(Vertical.deleted_at == None).all()
            )
        except (ProgrammingError, RuntimeError, InternalError):
            # The schema has not been initialized yet. It should be soon.
            return ()

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(PractitionerProfile.verticals).filter(Vertical.id.in_(value))


class PractitionerProfileViewLanguageFilter(ContainsFilter):
    def get_options(self, view):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return tuple((str(l.id), l.name) for l in Language.query.all())
        except (ProgrammingError, RuntimeError, InternalError):
            # The schema has not been initialized yet. It should be soon.
            return ()

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(PractitionerProfile.languages).filter(Language.id == value)


class PractitionerProfileViewStateFilter(IsFilter):
    def get_options(self, view):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return tuple(
                (str(s.id), s.abbreviation)
                for s in State.query.order_by("abbreviation").all()
            )
        except (ProgrammingError, RuntimeError, InternalError):
            # The schema has not been initialized yet. It should be soon.
            return ()

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(PractitionerProfile.certified_states).filter(
            State.id == value
        )


class PractitionerProfileViewPrescriberFilter(BooleanEqualFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _query = query.join(PractitionerProfile.verticals)
        if value == "1":
            return _query.filter(
                Vertical.can_prescribe.is_(True), PractitionerProfile.dosespot != {}
            )
        else:
            return _query.filter(
                Vertical.can_prescribe.is_(False), PractitionerProfile.dosespot == {}
            )


class PractitionerProfileViewCharacteristicFilter(IsFilter):
    def __init__(self) -> None:
        super().__init__(None, "Characteristic")

    def get_options(self, view):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return tuple((str(c.id), c.name) for c in Characteristic.query.all())
        except (ProgrammingError, RuntimeError, InternalError):
            # The schema has not been initialized yet. It should be soon.
            return ()

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(PractitionerProfile.characteristics).filter(
            Characteristic.id == value
        )


class PractitionerProfileViewSpecialtyFilter(IsFilter):
    def __init__(self) -> None:
        super().__init__(None, "Specialty")

    def get_options(self, view):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return tuple((str(c.id), c.name) for c in Specialty.query.all())
        except (ProgrammingError, RuntimeError, InternalError):
            # The schema has not been initialized yet. It should be soon.
            return ()

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(PractitionerProfile.specialties).filter(Specialty.id == value)


class PractitionerProfileViewSpecialtyContainsFilter(ContainsFilter):
    def __init__(self) -> None:
        super().__init__(None, "Specialty")

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(PractitionerProfile.specialties).filter(
            Specialty.name.like(f"%{value}%")
        )


class PractitionerProfileViewSpecialtyInFilter(FilterInList):
    def __init__(self) -> None:
        super().__init__(None, "Specialty")

    def get_options(self, view):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return tuple((str(c.id), c.name) for c in Specialty.query.all())
        except (ProgrammingError, RuntimeError, InternalError):
            # The schema has not been initialized yet. It should be soon.
            return ()

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(PractitionerProfile.specialties).filter(
            Specialty.id.in_(value)
        )


class PractitionerAvailabilityFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            value = int(value)
        except ValueError:
            value = 0
        events_query = (
            db.session.query(ScheduleEvent)
            .join(Schedule)
            .filter(
                Schedule.user_id == PractitionerProfile.user_id,
                ScheduleEvent.starts_at
                >= (datetime.datetime.utcnow() - datetime.timedelta(value)),
            )
        )
        return query.filter(events_query.exists())


class PractitionerProfileCertificationFilter(ContainsFilter):
    def __init__(self) -> None:
        super().__init__(None, "Certification")

    def get_options(self, view):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return tuple((str(c.id), c.name) for c in Certification.query.all())
        except (ProgrammingError, RuntimeError, InternalError):
            # The schema has not been initialized yet. It should be soon.
            return ()

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(PractitionerProfile.certifications).filter(
            Certification.id == value
        )


class SpecialtyBulkUpdateForm(BulkUpdateForm):
    specialties = QuerySelectMultipleField(
        validators=[validators.InputRequired()], query_factory=lambda: Specialty.query
    )

    def take_action(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        prac_profile_ids = self.ids.data.split(",")
        specialties = self.specialties.data
        for practitioner in db.session.query(PractitionerProfile).filter(
            PractitionerProfile.user_id.in_(prac_profile_ids)
        ):
            practitioner.specialties.extend(specialties)
        db.session.commit()
        flash(
            f"Set specialties {specialties} for practitioners: {prac_profile_ids}",
            category="info",
        )


class VerticalBulkUpdateForm(BulkUpdateForm):
    verticals = QuerySelectMultipleField(
        validators=[validators.InputRequired()],
        query_factory=lambda: Vertical.query.filter(Vertical.deleted_at == None),
    )

    def take_action(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        prac_profile_ids = self.ids.data.split(",")
        verticals = self.verticals.data
        for practitioner in db.session.query(PractitionerProfile).filter(
            PractitionerProfile.user_id.in_(prac_profile_ids)
        ):
            practitioner.verticals.extend(verticals)
        db.session.commit()
        flash(
            f"Set vertical id {verticals} for practitioners: {prac_profile_ids}",
            category="info",
        )


class LanguageBulkUpdateForm(BulkUpdateForm):
    languages = QuerySelectMultipleField(
        validators=[validators.InputRequired()], query_factory=lambda: Language.query
    )

    def take_action(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        prac_profile_ids = self.ids.data.split(",")
        languages = self.languages.data
        for practitioner in db.session.query(PractitionerProfile).filter(
            PractitionerProfile.user_id.in_(prac_profile_ids)
        ):
            practitioner.languages.extend(languages)
        db.session.commit()
        flash(
            f"Set language id {languages} for practitioners: {prac_profile_ids}",
            category="info",
        )


class PractitionerProfileView(
    ModalUpdateMixin, MavenAuditedView, PractitionerAvailabilityView
):
    read_permission = "read:practitioner-profile"
    create_permission = "create:practitioner-profile"
    edit_permission = "edit:practitioner-profile"

    selected_time_zone = "America/New_York"
    edit_template = "practitioner_profile_edit_template.html"
    list_template = "practitioner_list_template.html"
    column_list = (
        "user.id",
        "user.full_name",
        "user.email",
        "admin_verticals",
        "next_availability",
        "credential_start",
        "created_at",
    )

    column_descriptions = {
        "phone_number": "Please note: This is the phone number used for SMS notifications. To change the phone number used for 2FA, update the phone number in the user profile.",
    }

    column_labels = {
        "user.id": "ID",
        "user.full_name": "Name",
        "user.email": "Email",
        "admin_verticals": "Verticals",
    }
    column_sortable_list = ("created_at", "next_availability", "credential_start")
    column_default_sort = ("next_availability", False)
    column_searchable_list = (User.email,)

    column_filters = (
        PractitionerProfile.active,
        PractitionerProfile.user_id,
        PhoneNumberFilter(PractitionerProfile.phone_number, "Phone Number"),
        User.first_name,
        User.last_name,
        User.email,
        PractitionerProfileViewVerticalFilter(None, "Verticals"),
        PractitionerProfileViewVerticalInFilter(None, "Verticals"),
        PractitionerProfileViewLanguageFilter(None, "Languages"),
        PractitionerProfileViewSpecialtyFilter(),
        PractitionerProfileViewSpecialtyContainsFilter(),
        PractitionerProfileViewSpecialtyInFilter(),
        PractitionerProfileCertificationFilter(),
        PractitionerProfileViewStateFilter(None, "Licensed State Abbreviation"),
        PractitionerProfileViewPrescriberFilter(None, "Can Prescribe"),
        PractitionerProfile.is_staff,
        PractitionerProfile.anonymous_allowed,
        PractitionerProfileViewCharacteristicFilter(),
        PractitionerAvailabilityFilter(None, "Set availability in past x days"),
        PractitionerProfileViewNextAvailabilityFilter(None, "Next Availability"),
    )
    form_rules = [
        rules.FieldSet(("user", "active", "is_staff", "zendesk_email"), "User"),
        rules.FieldSet(
            (
                "state",
                "country_",
                "country_code",
                "subdivision_code",
                "languages",
                "note",
                "reference_quote",
                "awards",
                "work_experience",
                "phone_number",
                "education",
                "next_availability",
                "credential_start",
                "stripe_account_id",
                "messaging_enabled",
                "response_time",
                "anonymous_allowed",
            ),
            "Profile",
        ),
        rules.FieldSet(
            (
                "categories",
                "experience_started",
                "certifications",
                "certified_states",
                "default_cancellation_policy",
                "verticals",
                "specialties",
                "booking_buffer",
                "default_prep_buffer",
                "alert_about_availability",
                "ent_national",
                "malpractice_opt_out",
                "hourly_rate",
                "percent_booked",
                "show_in_marketplace",
                "show_in_enterprise",
                "billing_org",
            ),
            "Professional",
        ),
        rules.FieldSet(("characteristics",), "Internal"),
    ]

    form_widget_args = {
        "country_code": {"disabled": True},
        "subdivision_code": {"disabled": True},
    }

    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "user": USER_AJAX_REF,
                "allowed_modules": QueryAjaxModelLoader(
                    "allowed_modules",
                    db.session,
                    Module,
                    fields=("name",),
                    page_size=10,
                ),
                "assigned_organizations": QueryAjaxModelLoader(
                    "assigned_organizations",
                    db.session,
                    Organization,
                    fields=["name"],
                    page_size=10,
                ),
                "characteristics": {"fields": ("name",), "page_size": 10},
            }
        return self._form_ajax_refs

    modal_change_forms = {
        "update_specialties": SpecialtyBulkUpdateForm,
        "update_verticals": VerticalBulkUpdateForm,
        "update_languages": LanguageBulkUpdateForm,
    }

    """
    As part of the hacky solution to edit "Next Availability" filter values (read comments in def index_view()),
    we need to save time zones selected by users. This endpoint serves that purpose.
    It will be hit every time a user selects a new timezone.
    """

    @expose("/new_time_zone")
    def post_new_timezone(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        view_args = self._get_list_extra_args()
        tz = view_args.extra_args["tz"]

        if tz in pytz.all_timezones:
            self.selected_time_zone = tz
            log.info("Updated selected time zone", selected_tz=tz)
            return {"success": True}
        else:
            raise ValueError(f"Selected timezone not a pytz timezone: {tz}")

    @expose("/list_view_practitioners")
    def get_list_view_practitioners(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        view_args = self._get_list_extra_args()
        sort_column = self._get_column_by_idx(view_args.sort)
        if sort_column is not None:
            sort_column = sort_column[0]

        page_size = view_args.page_size or self.page_size

        count, data = self.get_list(
            view_args.page,
            sort_column,
            view_args.sort_desc,
            view_args.search,
            view_args.filters,
            page_size=page_size,
        )

        practitioners = [
            {
                "ID": p.user.id if p.user else "",
                "Name": p.user.full_name if p.user else "",
                "Email": p.user.email if p.user else "",
                "Verticals": p.admin_verticals,
                "Next Availability": p.next_availability,
                "Created At": p.created_at,
                "EditURL": url_for(
                    "practitionerprofile.edit_view", id=p.user.id if p.user else 0
                ),
            }
            for p in data
        ]

        emit_bulk_audit_log_read(data)
        return {
            "data": {
                "items": practitioners,
                "pagination": {
                    "limit": view_args.page_size,
                    "total": count,
                },
            }
        }

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
        # Default to only showing active practitioner profiles
        if all(name != "Active" for _, name, _ in filters):
            filters.append((0, "Active", "1"))
        return super().get_list(
            page, sort_column, sort_desc, search, filters, execute, page_size
        )

    def transform_datetime_str_with_tz_to_utc_str(self, datetime_str):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        datetime_tz_unaware = datetime.datetime.strptime(
            datetime_str, "%Y-%m-%d %H:%M:%S"
        )
        datetime_tz_aware = pytz.timezone(self.selected_time_zone).localize(
            datetime_tz_unaware, is_dst=None
        )
        datetime_utc_date = datetime_tz_aware.astimezone(pytz.utc)
        datetime_utc_date_str = datetime_utc_date.strftime("%Y-%m-%d %H:%M:%S")
        return datetime_utc_date_str

    def transform_datetime_f_value_to_utc(self, datetime_f_value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # date_f_value comes in the format 2022-06-30 05:17:00 to 2022-06-30 11:02:00
        start_datetime_str, end_datetime_str = datetime_f_value.split(" to ")

        start_datetime_str_utc = self.transform_datetime_str_with_tz_to_utc_str(
            datetime_str=start_datetime_str
        )
        end_datetime_str_utc = self.transform_datetime_str_with_tz_to_utc_str(
            datetime_str=end_datetime_str
        )

        datetime_f_value_utc = f"{start_datetime_str_utc} to {end_datetime_str_utc}"

        return datetime_f_value_utc

    @expose("/")
    def index_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # to get sorting working you need to use the name of the field in the column_list, like the created_at here
        # also you need to set the field in the column_sortable_list matching the column_list
        columns = [col[0] for col in self.get_list_columns()]
        self._template_args["columns_conf"] = [
            {"label": "ID"},
            {"label": "Name"},
            {"label": "Email"},
            {"label": "Verticals"},
            {"label": "Next Availability", "formatterType": "dateWithTimezone"},
            {
                "label": "Created At",
                "formatterType": "dateWithTimezone",
                "sort": columns.index("created_at"),
            },
        ]

        # this are the values used by flask-admin
        self._template_args["can_delete"] = self.can_delete
        self._template_args["delete_conf"] = {
            "deleteFormUrl": "/admin/practitionerprofile/delete/",
            "hiddenUrl": "/admin/practitionerprofile/",
        }

        view_args = self._get_list_extra_args()

        """
        This is a bit of a hacky piece of code.

        In the case of the 'Next Availability' filter, users will choose 'begin' and 'end' values
        with the selected time zone as a reference. We know that availability values are saved in our database
        in UTC. Hence, we will transform 'begin' and 'end' from the selected time zone to UTC.

        Here is an example of how filter values come in view_args.filters
        [(0, 'Active', '1'), (38, 'Next Availability', '2017-06-08 to 2022-06-15'), (24, 'User / Email', 'test')]

        Ideally, the filter values should be edited in the frontend considering the selected time zone. Once we complete this ticket https://app.shortcut.com/maven-clinic/story/87662/adminjs-migrate-filter-from-practitioner-profile-list-to-reactjs
        we will remove this hack.
        """
        for f_index, filter in enumerate(view_args.filters):
            f_number, f_name, f_value = filter
            if f_name == "Next Availability":
                new_f_value = self.transform_datetime_f_value_to_utc(f_value)
                view_args.filters[f_index] = (f_number, f_name, new_f_value)
                log.info(
                    "Changing Next Availability filter param values according to selected timezone",
                    selected_time_zone=self.selected_time_zone,
                    original_date_range=f_value,
                    new_date_range=new_f_value,
                )

        self._template_args["view_args"] = {
            "page_size": view_args.page_size or 20,
            "page": view_args.page or 0,
            "filters": self._get_filters(view_args.filters),
            "search": view_args.search,
            "sort": view_args.sort or "",
            "desc": view_args.sort_desc or "",
            "time_zone_value": self.selected_time_zone,
        }

        sort_column = self._get_column_by_idx(view_args.sort)
        if sort_column is not None:
            sort_column = sort_column[0]

        actions, _ = self.get_actions_list()
        self._template_args["has_actions"] = len(actions) > 0

        return super().index_view()

    def _order_by(self, query, joins, sort_joins, sort_field, sort_desc):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if sort_field.key == "next_availability":
            query = query.order_by(
                func.isnull(PractitionerProfile.next_availability).asc()
            )
        return super()._order_by(query, joins, sort_joins, sort_field, sort_desc)

    def validate_verticals(self, form, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(form.verticals.data) > 1:
            raise validators.ValidationError(
                "Practitioner cannot have more than one vertical."
            )

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.alert_about_availability = fields.BooleanField()
        form_class.malpractice_opt_out = fields.BooleanField()
        form_class.hourly_rate = fields.IntegerField(validators=[validators.Optional()])
        form_class.percent_booked = fields.IntegerField(
            validators=[validators.Optional()]
        )
        country_repo = CountryRepository(session=db.session)
        countries = [(None, None)] + [(x.alpha_2, x.name) for x in country_repo.all()]
        form_class.country_ = fields.SelectField(
            label="Country", choices=countries, coerce=str
        )
        form_class.verticals = QuerySelectMultipleField(
            validators=[self.validate_verticals],
            query_factory=lambda: Vertical.query.filter(Vertical.deleted_at == None),
        )
        return form_class

    def init_search(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        r = super().init_search()
        self._search_joins = [User.__table__]
        return r

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)

        # Update next_availability if active field is modified
        if form.active.object_data != form.active.data:
            log.info(
                "The active field in the practitioner profile model has been modified, triggering an update of the next_availability field",
                user_id=model.user_id,
            )
            update_practitioner_profile_next_availability(model)

        # Alert if is_staff is modified
        if form.is_staff.object_data != form.is_staff.data:
            text = (
                f"Practitioner ID: {model.user.id}\n"
                f"is_staff Value: {form.is_staff.data}\n"
                f"Requester ID: {login.current_user.id}"
            )
            notify_provider_ops_alerts_channel(
                notification_title="Practitioner `is_staff` Updated",
                notification_body=text,
                production_only=True,
            )

        countries = CountryRepository(session=db.session)
        subdivisions = SubdivisionRepository()

        if not form.country_.data:
            model.country_code = None
        else:
            verified_country = countries.get(country_code=form.country_.data)
            model.country_code = verified_country and verified_country.alpha_2

        if form.state.data:
            verified_subdivision = subdivisions.get_by_country_code_and_state(
                country_code=model.country_code,  # type: ignore[arg-type] # Argument "country_code" to "get_by_country_code_and_state" of "SubdivisionRepository" has incompatible type "Union[Country, None, str]"; expected "str"
                state=form.state.data.abbreviation,
            )
            model.subdivision_code = verified_subdivision and verified_subdivision.code
        else:
            model.subdivision_code = None

        if certified_states := form.certified_states.data:
            # Make sure there is a PractitionerSubdivision for each of the selected subdivisions
            for certified_state in certified_states:
                practitioner_subdivision = PractitionerSubdivision.query.filter_by(
                    practitioner_id=model.user_id,
                    subdivision_code=f"US-{certified_state.abbreviation}",
                ).one_or_none()

                if not practitioner_subdivision:
                    practitioner_subdivision = PractitionerSubdivision(
                        practitioner_id=model.user_id,
                        subdivision_code=f"US-{certified_state.abbreviation}",
                    )
                    db.session.add(practitioner_subdivision)

            subdivision_codes = {f"US-{s.abbreviation}" for s in certified_states}
            for practitioner_subdivision in model.certified_practitioner_subdivisions:
                if practitioner_subdivision.subdivision_code not in subdivision_codes:
                    db.session.delete(practitioner_subdivision)

        else:
            # Delete all PractitionerSubdivisions if there are none selected when saving
            for practitioner_subdivision in model.certified_practitioner_subdivisions:
                db.session.delete(practitioner_subdivision)

        sync_practitioner_with_braze.delay(model.user.id)

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        model = db.session.query(self.model).get(id)
        if model is None:
            return

        if model.country_code:
            form.country_.data = model.country_code

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if hasattr(form, "state") and (
            hasattr(form, "country_") or hasattr(form, "country_code")
        ):
            if not _is_valid_state_and_country(
                form.state.data, form.country_.data or form.country_code.data
            ):
                db.session.rollback()
                flash(
                    "Practitioner cannot have a state if their country is not the US.",
                    "error",
                )
                return

        return super().validate_form(form)

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        id = get_mdict_item_or_list(request.args, "id")
        model = None
        if id:
            model = self.get_one(id)

        if model:
            availabilities = PractitionerHelpers.get_availability(model)
            active_products = PractitionerHelpers.get_active_products(model)
            appointments = PractitionerHelpers.get_appointments(model)

            products_count = (
                db.session.query(Product)
                .filter(Product.practitioner == model.user)
                .count()
            )

            self._template_args["availabilities"] = availabilities
            self._template_args["active_products"] = active_products
            self._template_args["products_count"] = products_count
            self._template_args["appointments"] = appointments
            self._template_args[
                "BOOKABLE_TIMES_MIN_DAYS"
            ] = PractitionerHelpers.BOOKABLE_TIMES_MIN_DAYS
            self._template_args[
                "BOOKABLE_TIMES_MAX_DAYS"
            ] = PractitionerHelpers.BOOKABLE_TIMES_MAX_DAYS
            if ProviderService().enabled_for_prescribing(id):
                self._template_args["show_dosespot_info"] = True
        return super().edit_view()

    @expose("/list/", methods=("GET",))
    def list(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        practitioners = (
            db.session.query(PractitionerProfile)
            .filter(PractitionerProfile.active == true())
            .all()
        )

        practitioners = [
            {
                "name": p.user.full_name,
                "id": p.user_id,
            }
            for p in practitioners
        ]

        return {"practitioners": practitioners}

    @action("sync_products", "Add Products", "You sure?")
    def sync_products(self, practitioner_profile_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        users = User.query.filter(User.id.in_(practitioner_profile_ids)).all()

        log.info("Adding products for %s practitioners.", len(users))
        emit_bulk_audit_log_update(users)
        for user in users:
            add_products(user)
        log.debug("All set with adding products.")

    @action("reset_dosespot_info", "Reset DoseSpot Info", "You Sure?")
    def reset_dosespot_info(self, practitioner_profile_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(practitioner_profile_ids) != 1:
            flash("Please reset only one practitioner dosespot info at a time!")
            return

        practitioners = PractitionerProfile.query.filter(
            PractitionerProfile.user_id.in_(practitioner_profile_ids)
        ).all()
        for p in practitioners:
            p.dosespot = {}
        db.session.add_all(practitioners)
        if practitioners[0]:
            emit_audit_log_update(practitioners[0])
        db.session.commit()
        log.debug("DoseSpot info reset for %s", p)
        flash(f"DoseSpot info reset for {p}")

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
            PractitionerProfile,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ScheduleEventView(MavenAuditedView):
    read_permission = "read:schedule-event"
    delete_permission = "delete:schedule-event"
    edit_permission = "edit:schedule-event"

    column_filters = ("schedule.user_id", "state")
    form_rules = ("schedule", "state", "starts_at", "ends_at")
    column_list = form_rules

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
            ScheduleEvent,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    @db.from_app_replica
    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return super().edit_view()


class PractitionerInviteView(MavenAuditedView):
    read_permission = "read:practitioner-invite"
    delete_permission = "delete:practitioner-invite"
    create_permission = "create:practitioner-invite"
    edit_permission = "edit:practitioner-invite"

    column_exclude_list = ("modified_at", "json")
    column_sortable_list = ("created_at", "claimed_at")
    column_searchable_list = ("email",)
    form_excluded_columns = ("modified_at", "json", "created_at")

    form_ajax_refs = {"image": {"fields": ("id",), "page_size": 10}}

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
            PractitionerInvite,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class VerticalView(MavenAuditedView):
    read_permission = "read:vertical"
    delete_permission = "delete:vertical"
    create_permission = "create:vertical"
    edit_permission = "edit:vertical"

    edit_template = "vertical.html"

    column_sortable_list = ("name", "filter_by_state")
    column_list = ("created_at", "name", "filter_by_state")
    column_searchable_list = ("name",)

    form_excluded_columns = ["practitioners"]
    form_overrides = dict(products=DictToJSONField)

    form_rules = [
        "name",
        "description",
        "long_description",
        "display_name",
        "pluralized_display_name",
        "slug",
        "products",
        "filter_by_state",
        "can_prescribe",
        "groups",
        "promote_messaging",
        "region",
    ]

    form_args = {
        "description": {
            "validators": [validators.DataRequired()],
        },
        "long_description": {
            "validators": [validators.DataRequired()],
        },
        "slug": {
            "validators": [validators.DataRequired()],
        },
    }

    form_widget_args = {
        "name": {"readonly": True},
        "long_description": {"readonly": True},
        "pluralized_display_name": {"readonly": True},
        "slug": {"readonly": True},
    }

    column_descriptions = {
        "name": "<i>Submit JIRA ticket to update this field</i>",
        "long_description": "<i>Submit JIRA ticket to update this field</i>",
        "pluralized_display_name": "<i>Submit JIRA ticket to update this field</i>",
        "slug": "<i>Submit JIRA ticket to update this field</i>",
    }

    def _validate_vertical_products_input(self, request):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = VerticalProductSchema()
        request_json = request.json if request.is_json else None
        validated_input = schema.load(request_json)
        vertical_id = validated_input["vertical_id"]
        vertical = Vertical.query.get(vertical_id)

        if not vertical:
            raise ValidationError("no matching vertical found")

        return vertical, validated_input["product"]

    # soft deletes. only gets verticals with no "deleted_at" date
    def get_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.session.query(self.model).filter(Vertical.deleted_at == None)

    # this needs to be here too otherwise the count is wrong
    def get_count_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            self.session.query(func.count("*"))
            .select_from(self.model)
            .filter(Vertical.deleted_at == None)
        )

    @expose("/deactivate_products/", methods=("POST",))
    def deactivate_products(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            vertical, product = self._validate_vertical_products_input(request)
        except ValidationError as e:
            return jsonify({"errors": e.messages}), 400

        vertical.products.remove(product)

        products = Product.query.filter(
            Product.vertical_id == vertical.id,
            Product.minutes == product["minutes"],
            Product.price == product["price"],
            Product.is_active == True,
        ).all()

        if not products:
            db.session.commit()
            return (
                jsonify(
                    {
                        "errors": [
                            "no matching practitioner products found, removing the vertical product only."
                        ]
                    }
                ),
                400,
            )

        for product in products:
            product.is_active = False

        db.session.commit()

        return jsonify({"count": len(products)})

    @expose("/create_products/", methods=("POST",))
    def create_products(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            vertical, product = self._validate_vertical_products_input(request)
        except ValidationError as e:
            return jsonify({"errors": e.messages}), 400

        if not vertical.products:
            vertical.products = [product]
        else:
            vertical.products.append(product)

        profiles = (
            PractitionerProfile.query.join(PractitionerProfile.verticals)
            .filter(Vertical.id == vertical.id)
            .all()
        )

        new_products = []

        for profile in profiles:
            # first check if they already have a product with this minute / price / vertical combo
            count = Product.query.filter(
                Product.minutes == product["minutes"],
                Product.vertical == vertical,
                Product.price >= product["price"],
                Product.practitioner == profile.user,
            ).count()

            if count == 0:
                new_product = Product(
                    minutes=product["minutes"],
                    vertical=vertical,
                    price=product["price"],
                    practitioner=profile.user,
                )
                new_products.append(new_product)

                db.session.add(new_product)

        db.session.commit()

        return jsonify({"count": len(new_products)})

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.products = fields.StringField(
            label="Products", id="override-with-react"
        )

        return form_class

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        id = get_mdict_item_or_list(request.args, "id")
        model = None
        if id:
            model = self.get_one(id)

        if model:
            products = model.products or []
            for p in products:
                prac_products_count = Product.query.filter(
                    Product.vertical_id == model.id,
                    Product.minutes == p["minutes"],
                    Product.price == p["price"],
                    Product.is_active == True,
                ).count()
                p["count"] = prac_products_count

            self._template_args["products_json"] = json.dumps(products)
            self._template_args["vertical_id"] = json.dumps(model.id)

        return super().edit_view()

    def delete_model(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Delete model.

        :param model:
            Model to delete
        """
        self.on_model_delete(model)
        # these are now soft deletes. Just need to add a datestamp to "deleted_by" column
        model.deleted_at = datetime.datetime.now()
        model.name = self.give_prefixed_name_if_deleted(model)
        db.session.commit()
        self.after_model_delete(model)

    def give_prefixed_name_if_deleted(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model.deleted_at and not model.name.startswith("Deleted at"):
            return f"Deleted at {model.deleted_at} -- {model.name}"
        return model.name

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
            Vertical,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class PractitionerQueryAjaxModelLoader(QueryAjaxModelLoader):
    def format(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model is None:
            return ""
        if isinstance(model, PractitionerProfile):
            return (
                getattr(model, self.pk),
                f"<User [{model.user_id}] {model.user.full_name} [{model.user.email}]>",
            )
        return super(PractitionerQueryAjaxModelLoader).format(model)

    def get_list(self, term, offset=0, limit=DEFAULT_PAGE_SIZE):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        query = self.session.query(self.model).join(User)

        filters = (field.ilike("%%%s%%" % term) for field in self._cached_fields)
        query = query.filter(or_(*filters))

        if self.order_by:
            query = query.order_by(self.order_by)

        return query.offset(offset).limit(limit).all()


class SpecialtyView(MavenAuditedView):
    read_permission = "read:specialty"
    delete_permission = "delete:specialty"
    create_permission = "create:specialty"
    edit_permission = "edit:specialty"

    edit_template = "specialty_edit_template.html"
    form_excluded_columns = ("vertical_groups",)
    _form_ajax_refs = None

    form_widget_args = {
        "name": {"readonly": True},
        "slug": {"readonly": True},
    }

    form_args = {
        "slug": {
            "validators": [validators.DataRequired()],
        },
    }

    column_descriptions = {
        "name": "<i>Submit JIRA ticket to update this field</i>",
        "slug": "<i>Submit JIRA ticket to update this field</i>",
    }

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "practitioners": PractitionerQueryAjaxModelLoader(
                    "practitioners",
                    self.session,
                    PractitionerProfile,
                    fields=("user_id", User.email, User.first_name, User.last_name),
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
            Specialty,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class SpecialtyKeywordView(MavenAuditedView):
    read_permission = "read:specialty-keyword"
    delete_permission = "delete:specialty-keyword"
    create_permission = "create:specialty-keyword"
    edit_permission = "edit:specialty-keyword"

    column_list = ("id", "name")
    form_columns = ("name", "specialties")

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
            SpecialtyKeyword,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class MemberProfileChildren(InlineCollectionView):
    parent_attribute = "children"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "InlineCollectionView" defined the type as "None")
    child_pk = "id"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "InlineCollectionView" defined the type as "None")
    form_field_args = {"label": "Children"}

    def get_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        class ChildForm(form.Form):
            id = fields.HiddenField()
            name = fields.StringField(label="Name")
            birthday = fields.DateField(label="Birthday", widget=DatePickerWidget())

        return ChildForm

    def get_collection(self, member_profile):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return member_profile.user.health_profile.children_with_age

    def set_collection(self, member_profile, collection):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        hp = member_profile.user.health_profile
        hp.json = {
            **hp.json,
            "children": [
                {
                    "id": c["data"]["id"] or str(uuid.uuid4()),
                    "name": c["data"]["name"],
                    "birthday": c["data"]["birthday"].strftime("%Y-%m-%d"),
                }
                for c in collection
                if not c["should_delete"]
            ],
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
            MemberProfileChildren,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


def get_wallet_info(view, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user_id = model.user.id
    query = """
        SELECT rwu.reimbursement_wallet_id, rw.state, rwu.status
        FROM reimbursement_wallet_users rwu
        JOIN reimbursement_wallet rw on rwu.reimbursement_wallet_id = rw.id
        WHERE rwu.user_id = :user_id
        AND rwu.status in ('ACTIVE', 'PENDING');
        """
    data = db.session.execute(query, {"user_id": user_id})
    result = []
    for wallet_id, state, rwu_status in data:
        result.append(
            f"[User is a {rwu_status} user of Wallet<{wallet_id=}, {state=}>]"
        )
    return ", ".join(result)


def _is_doula_only_member(model: Any) -> bool:
    active_tracks = model.user.active_tracks
    member_track_modifiers = get_active_member_track_modifiers(active_tracks)
    return TrackModifiers.DOULA_ONLY in member_track_modifiers


class MemberProfileView(MavenAuditedView):
    create_permission = "create:member-profile"
    read_permission = "read:member-profile"
    edit_permission = "edit:member-profile"

    can_view_details = True
    edit_template = "member_profile_edit_template.html"
    details_template = "member_profile_details_template.html"
    column_sortable_list = ("created_at",)
    column_list = (
        "user.id",
        "user.full_name",
        "user.email",
        "user.health_profile.birthday",
        "wallet_info",
        "created_at",
    )
    column_searchable_list = (User.email,)
    column_filters = (
        User.id,
        User.username,
        User.email,
        User.first_name,
        User.last_name,
        PhoneNumberFilter(MemberProfile.phone_number, "Phone Number"),
        DateOfBirthFilter(None, "Date of Birth (YYYY-MM-DD)"),
        WalletBenefitIdFilter(None, "Benefit Id"),
    )

    column_labels = {"user.health_profile.birthday": "Date of Birth"}

    column_formatters = {"wallet_info": get_wallet_info}

    column_descriptions = {
        "phone_number": "Please note: This is the phone number used for SMS notifications. To change the phone number used for 2FA, update the phone number in the user profile.",
    }

    form_create_rules = (
        "user",
        "phone_number",
        "state",
        "country_",
        "country_code",
        "stripe_customer_id",
        "note",
        "follow_up_reminder_send_time",
    )
    form_edit_rules = (
        rules.FieldSet(
            (
                "user",
                "phone_number",
                "state",
                "country_",
                "country_code",
                "subdivision_code",
                "stripe_customer_id",
                "stripe_account_id",
                "note",
                "follow_up_reminder_send_time",
            ),
            "Member Profile",
        ),
        rules.FieldSet(("dob", "due_date", "children"), "Health Profile"),
    )

    form_widget_args = {
        "dob": {"disabled": True},
        "country_code": {"disabled": True},
        "subdivision_code": {"disabled": True},
    }

    form_ajax_refs = {"user": USER_AJAX_REF}
    form_extra_fields = {
        "dob": fields.DateField(label="DOB", widget=DatePickerWidget()),
        "due_date": fields.DateField(
            label="Due Date",
            widget=DatePickerWidget(),
            validators=[validators.Optional()],
        ),
    }
    _inline_models = None

    @property
    def inline_models(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._inline_models is None:
            self._inline_models = (MemberProfileChildren(),)
        return self._inline_models

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        country_repo = CountryRepository(session=db.session)
        countries = [(None, None)] + [(x.alpha_2, x.name) for x in country_repo.all()]
        form_class.country_ = fields.SelectField(
            label="Country", choices=countries, coerce=str
        )
        return form_class

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        model = db.session.query(self.model).get(id)
        if model is None:
            return
        form.dob.data = model.user.health_profile.birthday
        form.due_date.data = model.user.health_profile.due_date

        if model.country_code:
            form.country_.data = model.country_code

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        hp = model.user.health_profile
        existing_due_date = hp.due_date
        super().on_model_change(form, model, is_created)
        hp.due_date = form.due_date.data

        countries = CountryRepository(session=db.session)
        subdivisions = SubdivisionRepository()

        if not form.country_.data:
            model.country_code = None
        else:
            verified_country = countries.get(country_code=form.country_.data)
            model.country_code = verified_country and verified_country.alpha_2

        if form.state.data:
            verified_subdivision = subdivisions.get_by_country_code_and_state(
                country_code=model.country_code,  # type: ignore[arg-type] # Argument "country_code" to "get_by_country_code_and_state" of "SubdivisionRepository" has incompatible type "Union[Country, None, str]"; expected "str"
                state=form.state.data.abbreviation,
            )
            model.subdivision_code = verified_subdivision and verified_subdivision.code
        else:
            model.subdivision_code = None

        try:
            tracks.on_health_profile_update(
                user=model.user,
                modified_by=str(login.current_user.id or ""),
                change_reason=ChangeReason.ADMIN_MEMBER_PROFILE_UPDATE,
            )
            db.session.commit()
        except TrackLifecycleError as e:
            log.error(e)
            db.session.rollback()
            flash(str(e), "error")
        # TODO: [Track] Phase 3 - drop this.
        except ProgramLifecycleError as e:
            log.log(e.log_level, e)
            db.session.rollback()
            flash(str(e), "error")

        if form.phone_number.object_data != form.phone_number.data:
            # Check this user for any wallet, past or present; let the
            # updating logic worry about if it's active, has a debit card, etc.
            if len(model.user.reimbursement_wallets) > 0:
                remove_member_number.delay(
                    user_id=model.user.id,
                    old_phone_number=form.phone_number.object_data,
                )

        try:
            if form.due_date.data and form.due_date.data != existing_due_date:
                accessing_user = login.current_user
                health_profile_svc = HealthProfileService(
                    user=model.user, accessing_user=accessing_user
                )
                modifier = Modifier(
                    id=accessing_user.id,
                    name=accessing_user.full_name,
                    role=ROLES.staff,
                )
                health_profile_svc.update_due_date_in_hps(form.due_date.data, modifier)
        except Exception as e:
            log.error(
                f"Failed to update due date for member {model.user.id} in health profile service from member profile view in admin",
                error=str(e),
            )

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not _is_valid_state_and_country(
            form.state.data, form.country_.data or form.country_code.data
        ):
            db.session.rollback()
            flash("User cannot have a state if their country is not the US.", "error")
            return

        return super().validate_form(form)

    @expose("/details/", methods=["GET"])
    def details_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        id = get_mdict_item_or_list(request.args, "id")
        model = None
        if id:
            model = self.get_one(id)

        if model:
            # Get preferred languages
            assessment_exporter = AssessmentExporter.for_user_assessments(model.user)
            mono_assessment_dict = assessment_exporter.most_recent_answers_for(
                user=model.user,
                topic=AssessmentExportTopic.ANALYTICS,
                question_names=["preferred_language"],
            )
            mono_language_answer = mono_assessment_dict.get("preferred_language", None)
            hdc_question = get_question_slug_user_answers(
                user_id=model.user.id, question_slug="preferred_languages"
            )

            language_set: set[str | None] = set()  # Deduplicate languages

            if mono_language_answer:
                mono_languages = {
                    lang.title().replace("_", " ")
                    for lang in mono_language_answer.exported_answer
                    if isinstance(lang, str) and lang is not None and lang != ""
                }

                language_set.update(mono_languages)

            if hdc_question:
                hdc_languages = {
                    answer.value.title().replace("_", " ")  # type: ignore[union-attr] # Item "float" of "Union[float, str, int, datetime, Any]" has no attribute "title" #type: ignore[union-attr] # Item "int" of "Union[float, str, int, datetime, Any]" has no attribute "title" #type: ignore[union-attr] # Item "datetime" of "Union[float, str, int, datetime, Any]" has no attribute "title"
                    for answer in hdc_question.user_answers  # type: ignore[union-attr] # Item "None" of "Optional[List[HDCUserAnswer]]" has no attribute "__iter__" (not iterable)
                }

                language_set.update(hdc_languages)

            language_set.discard(None)

            if language_set:
                self._template_args["preferred_language"] = ", ".join(language_set)  # type: ignore[arg-type] # Argument 1 to "join" of "str" has incompatible type "Set[Optional[str]]"; expected "Iterable[str]"
            else:
                self._template_args["preferred_language"] = "Not set"

            # if the member is doula only, display a banner
            if _is_doula_only_member(model):
                self._template_args[
                    "track_modifiers_banner"
                ] = DOULA_ONLY_BANNER_MESSAGE

            # Add all potential assessments related to a track and all assessments the user started
            (
                needs_assessments,
                track_assessments,
            ) = get_user_track_and_started_needs_assessments(model.user)
            user_assessments = [
                {"title": ta.title, "id": str(ta.id), "status": "Not started"}
                for ta in track_assessments
            ]
            for na in needs_assessments:
                assessment_template = na.assessment_template
                assessment_dict = {
                    "title": assessment_template.title,
                    "id": str(assessment_template.id),
                    "status": "Completed" if na.completed else "Started, not completed",
                }
                user_assessments.append(assessment_dict)

            benefit_ids = (
                model.user.member_benefit and model.user.member_benefit.benefit_id
            )

            self._template_args["user_assessments"] = user_assessments
            self._template_args["benefit_ids"] = (
                benefit_ids if benefit_ids is not None else ""
            )

            # Grab completed UserAssessmentStatus from HDC service
            user_assessments_hdc = get_user_assessments_by_user_id(model.user.id)
            user_assessments_hdc_formatted = []
            if user_assessments_hdc:
                for ua in user_assessments_hdc:
                    ua_dict = {
                        "title": ua.assessment_slug,
                        "id": str(ua.assessment_id),
                        "status": (
                            "Completed"
                            if ua.completed_assessment
                            else "Started, not completed"
                        ),
                    }
                    user_assessments_hdc_formatted.append(ua_dict)

            self._template_args["user_assessments_hdc"] = user_assessments_hdc_formatted

        return super().details_view()

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        class AppointmentLink:
            def __init__(self, appointment):  # type: ignore[no-untyped-def] # Function is missing a type annotation
                self.a = appointment
                self.id = appointment.id

            def __repr__(self) -> str:
                return f"Appointment {self.a.id} [{self.a.state} @ {self.a.scheduled_start}] with {self.a.practitioner.full_name} ({self.a.product and self.a.product.vertical.name})"

        id = get_mdict_item_or_list(request.args, "id")
        model = None
        if id:
            model = self.get_one(id)

        if model:
            stripe = StripeCustomerClient(PAYMENTS_STRIPE_API_KEY)
            self._template_args["cards"] = stripe.list_cards(user=model.user)

            total_credits = Credit.available_amount_for_user(model.user)
            self._template_args["total_credits"] = total_credits

            schedule = model.user.schedule
            appointments = (
                []
                if schedule is None
                else (
                    db.session.query(Appointment)
                    .filter(Appointment.member_schedule_id == schedule.id)
                    .all()
                )
            )

            # Key is appointment.id, value is scheduled_start
            last_reschedule_record_dic = {}
            for appointment in appointments:
                record = (
                    db.session.query(RescheduleHistory)
                    .filter(RescheduleHistory.appointment_id == appointment.id)
                    .order_by(RescheduleHistory.id.desc())
                    .first()
                )
                if record is not None:
                    last_reschedule_record_dic[appointment.id] = record.scheduled_start
            self._template_args[
                "last_reschedule_record_dic"
            ] = last_reschedule_record_dic

            self._template_args["appointments"] = appointments
            self._template_args["appointment_links"] = [
                AppointmentLink(a) for a in appointments
            ]

            used_codes = (
                db.session.query(ReferralCodeUse)
                .filter(ReferralCodeUse.user_id == model.user.id)
                .all()
            )
            self._template_args["used_codes"] = used_codes
            self._template_args["member"] = model.user
            self._template_args["member_edit_view"] = True

            if _is_doula_only_member(model):
                self._template_args[
                    "track_modifiers_banner"
                ] = DOULA_ONLY_BANNER_MESSAGE

            practitioners = (
                db.session.query(PractitionerProfile)
                .options(load_only("first_name", "last_name", "user_id"))
                .options(joinedload("verticals"))
                .join(MemberPractitionerAssociation)
                .filter(MemberPractitionerAssociation.user_id == model.user_id)
                .all()
            )

            self._template_args["care_team"] = [
                {
                    "url": url_for("practitionerprofile.edit_view", id=p.user_id),
                    "full_name": f"{p.first_name} {p.last_name}",
                    "verticals": ", ".join(
                        v.display_name or v.name for v in p.verticals
                    ),
                }
                for p in practitioners
            ]
            self._template_args["member_risks"] = MemberRisksAdminModel(model.user)

            track_svc = tracks_service.TrackSelectionService()
            organization = track_svc.get_organization_for_user(user_id=model.user.id)
            if organization:
                e9y_svc = e9y_service.EnterpriseVerificationService()
                verification: e9y_model.EligibilityVerification = (
                    e9y_svc.get_verification_for_user(
                        user_id=model.user_id, organization_id=organization.id
                    )
                )
                if verification:
                    plan_carrier = verification.record.get("plan_carrier", "Unknown")
                    plan_name = verification.record.get("plan_name", "Unknown")
                    state = verification.record.get("state", "Unknown")
                    employee_status_code = verification.record.get(
                        "employee_status_code", "Unknown"
                    )
                    union_status = verification.record.get("union_status", "Unknown")
                    eligibility_member_id = verification.eligibility_member_id
                    self._template_args["verification_data"] = {
                        "Plan Carrier": plan_carrier,
                        "Plan Name": plan_name,
                        "State": state,
                        "Employee Status Code": employee_status_code,
                        "Union Status": union_status,
                        "Eligibility Member Id": eligibility_member_id,
                    }

            braze_bulk_message_keys = []
            for n in range(10):
                key = f"braze_pause_message_{n + 1}"
                braze_bulk_message_keys.append(key)
            self._template_args["braze_bulk_message_keys"] = braze_bulk_message_keys

            member_type_details = get_member_type_details(model.user)
            payments_customer = None
            if member_type_details.member_type == MemberType.MAVEN_GOLD:
                if member_type_details.active_wallet.payments_customer_id:  # type: ignore[union-attr] # Item "None" of "Optional[ReimbursementWallet]" has no attribute "payments_customer_id"
                    try:
                        gateway_client = get_client(INTERNAL_TRUST_PAYMENT_GATEWAY_URL)  # type: ignore[arg-type] # Argument 1 to "get_client" has incompatible type "Optional[str]"; expected "str"
                        payments_customer = gateway_client.get_customer(
                            member_type_details.active_wallet.payments_customer_id  # type: ignore[union-attr] # Item "None" of "Optional[ReimbursementWallet]" has no attribute "payments_customer_id"
                        )
                    except Exception:
                        payments_customer = False  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bool", variable has type "Optional[Customer]")

            self._template_args["MemberType"] = MemberType
            self._template_args["member_type_details"] = member_type_details
            self._template_args["payments_customer"] = payments_customer
            self._template_args["benefit_id"] = (
                model.user.member_benefit and model.user.member_benefit.benefit_id
            )

            wallet_service = ReimbursementWalletService()
            # get employer health plan for current wallet if it exists
            employer_health_plan = None
            if (
                feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
                != OLD_BEHAVIOR
            ):
                wallet = wallet_service.wallet_repo.get_wallet_by_active_user_id(
                    user_id=model.user_id
                )
                if wallet:
                    health_plan_repo = HealthPlanRepository(db.session)
                    employer_health_plan = (
                        health_plan_repo.get_employer_plan_by_wallet_and_member_id(
                            member_id=model.user_id,
                            wallet_id=wallet.id,
                            effective_date=datetime.datetime.now(datetime.timezone.utc),
                        )
                    )
            else:
                member_health_plan = (
                    MemberHealthPlan.query.filter(
                        MemberHealthPlan.member_id == model.user_id
                    )
                    .order_by(MemberHealthPlan.created_at.desc())
                    .first()
                )
                if member_health_plan:
                    employer_health_plan = member_health_plan.employer_health_plan

            self._template_args["employer_health_plan"] = employer_health_plan

            # Fetch wallet balances
            wallet_balances: list[WalletBalance] = wallet_service.get_wallet_balances(
                user=model.user
            )
            self._template_args["wallets_balances"] = wallet_balances

        return super().edit_view()

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
            MemberProfile,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class MemberPractitionerAssociationView(MavenAuditedView):
    read_permission = "read:member-practitioner-association"
    delete_permission = "delete:member-practitioner-association"
    create_permission = "create:member-practitioner-association"
    edit_permission = "edit:member-practitioner-association"

    column_list = [
        "user",
        "practitioner_profile",
        "practitioner_profile.user.full_name",
        "practitioner_profile.admin_verticals",
        "type",
    ]
    column_filters = [
        "user_id",
        "practitioner_id",
        "user.email",
        "practitioner_profile.user.email",
    ]
    column_labels = {
        "practitioner_profile.user.full_name": "Practitioner Name",
        "practitioner_profile.user.email": "Practitioner Email",
        "practitioner_profile.admin_verticals": "Verticals",
        "user.email": "Member Email",
    }
    form_excluded_columns = ("created_at", "modified_at")
    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "user": USER_AJAX_REF,
                "practitioner_profile": PractitionerQueryAjaxModelLoader(
                    "practitioner_profile",
                    self.session,
                    PractitionerProfile,
                    fields=("user_id", User.email, User.first_name, User.last_name),
                    page_size=10,
                ),
            }
        return self._form_ajax_refs

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if (
            hasattr(form, "practitioner_profile")
            and form.practitioner_profile.data
            and hasattr(form, "user")
            and form.user.data
        ):
            # We would like to prevent adding out-of-state practitioners to Care Teams
            log.info(
                "Validating MPA form to prevent adding out-of-state practitions to Care Team"
            )
            practitioner_profile = form.practitioner_profile.data
            user = form.user.data

            try:
                bad_state_match = state_match_not_permissible(
                    practitioner_profile, user
                )
                if bad_state_match:
                    db.session.rollback()
                    flash(
                        f"This provider is not licensed in the user’s state. Please find a provider that is licensed in {user.member_profile.state}."
                    )
                    return
            except Exception as e:
                db.session.rollback()
                flash(f"Could not create MemberPractitionerAssociation. {e}")
                return
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
            MemberPractitionerAssociation,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AdvocateQueryAjaxModelLoader(QueryAjaxModelLoader):
    def format(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model is None:
            return ""
        assert isinstance(model, PractitionerProfile)
        return getattr(model, self.pk), f"[{model.user_id}] {model.user.full_name}"

    def get_list(self, term, offset=0, limit=DEFAULT_PAGE_SIZE):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        query = (
            self.session.query(self.model)
            .join(User)
            .join(practitioner_verticals)
            .join(Vertical)
            .filter(is_cx_vertical_name(Vertical.name))
        )

        filters = (
            cast(field, String).ilike("%%%s%%" % term) for field in self._cached_fields
        )
        query = query.filter(or_(*filters))

        if self.filters:
            filters = [  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[str]", variable has type "Generator[Any, None, None]")
                f"{self.model.__tablename__.lower()}.{value}" for value in self.filters
            ]
            query = query.filter(and_(*filters))

        if self.order_by:
            query = query.order_by(self.order_by)

        return query.offset(offset).limit(limit).all()


class AssignableAdvocateView(MavenAuditedView):
    create_permission = "create:advocate-patient-assignment"
    read_permission = "read:advocate-patient-assignment"
    edit_permission = "edit:advocate-patient-assignment"
    delete_permission = "delete:advocate-patient-assignment"

    edit_template = "assignable_advocate.html"
    create_template = "assignable_advocate.html"

    column_filters = (
        "practitioner_id",
        "practitioner.user.first_name",
        "practitioner.user.last_name",
        "practitioner.user.email",
    )
    form_rules = [
        "practitioner",
        "ca_timezone",
        "vacation_started_at",
        "vacation_ended_at",
        "marketplace_allowed",
        "matching_rules",
        rules.Text(CAPACITY_FORMATTING_HTML, escape=False),
        rules.NestedRule(rules=["max_capacity", "daily_intro_capacity"]),
        rules.Text(CAPACITY_INFO_TEXT, escape=False),
    ]

    column_labels = {
        "practitioner": "Care Advocate",
        "vacation_started_at": "Vacation Start Date (UTC)",
        "vacation_ended_at": "Vacation End Date (UTC)",
        "admin_name": "Care Advocate",
        "admin_assignments": "Patients From",
        "admin_vacation": "Vacation Status",
        "max_capacity": "Daily Total Capacity",
        "daily_intro_capacity": "Daily Intro Capacity",
    }
    column_list = (
        "admin_name",
        "admin_assignments",
        "admin_vacation",
        "max_capacity",
        "daily_intro_capacity",
    )

    column_descriptions = {
        "daily_intro_capacity": "<i>If Daily Intro Capacity is not relevant to this CA, please set Daily Intro Capacity = Daily Total Capacity</i>"
    }

    _form_ajax_refs = None

    @property
    def form_ajax_refs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._form_ajax_refs is None:
            self._form_ajax_refs = {
                "practitioner": AdvocateQueryAjaxModelLoader(
                    "practitioner",
                    self.session,
                    PractitionerProfile,
                    fields=("user_id", User.email, User.first_name, User.last_name),
                    page_size=10,
                ),
                "organization": QueryAjaxModelLoader(
                    "organization",
                    self.session,
                    Organization,
                    fields=("id", "name"),
                    page_size=10,
                ),
                "module": QueryAjaxModelLoader(
                    "module", self.session, Module, fields=("name",), page_size=10
                ),
            }
        return self._form_ajax_refs

    _inline_models = None

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        model = db.session.query(self.model).get(id)

        if model.practitioner:
            form.ca_timezone.data = model.practitioner.user.timezone
            form.ca_timezone.description = f"<i>*To update this field, please navigate to the CA's <a href='/admin/user/edit/?id={id}'>user profile</a>.</i>"

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)

        # Update next_availability if vacation fields or capacity fields are modified
        fields_that_trigger_next_availability_update = [
            "vacation_started_at",
            "vacation_ended_at",
            "daily_intro_capacity",
            "max_capacity",
        ]
        for field in fields_that_trigger_next_availability_update:
            if (
                form[field].object_data != form[field].data
            ):  # New field data is different to old field data
                log.info(
                    "A field in the assignable advocate model has been modified, triggering an update of the next_availability field",
                    field_updated=field,
                    user_id=model.practitioner_id,
                )
                update_practitioner_profile_next_availability(model.practitioner)
                break  # No need to keep looping over other fields

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.matching_rules = fields.StringField(
            label="Matching Rules", id="matching-rule-override-with-react"
        )
        form_class.ca_timezone = fields.StringField(
            label="CA Timezone",
            render_kw={"readonly": True},
        )

        return form_class

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if (
            form.daily_intro_capacity.data
            and form.max_capacity.data
            and (form.daily_intro_capacity.data > form.max_capacity.data)
        ) or (form.daily_intro_capacity.data and not form.max_capacity.data):
            db.session.rollback()
            flash(
                "Daily Intro Capacity cannot exceed Daily Total Capacity.",
                "error",
            )
            return

        return super().validate_form(form)

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        id = get_mdict_item_or_list(request.args, "id")
        model = None

        country_repo = CountryRepository()

        countries = [
            {"label": c.name, "value": c.alpha_2}
            for c in sorted(country_repo.all(), key=lambda x: x.name)
        ]
        self._template_args["countries_json"] = json.dumps(countries)

        organizations = [
            {"label": o.name, "value": str(o.id)}
            for o in Organization.query.order_by(Organization.name.asc()).all()
        ]
        self._template_args["organizations_json"] = json.dumps(organizations)

        tracks = [
            {"label": t.frontend_name or t.name, "value": str(t.id)}
            for t in Module.query.order_by(Module.frontend_name.asc()).all()
        ]
        self._template_args["tracks_json"] = json.dumps(tracks)

        risk_factors = [
            {"label": u.name, "value": str(u.id)}
            for u in RiskFlag.query.order_by(RiskFlag.name.asc()).all()
        ]
        self._template_args["risk_factors_json"] = json.dumps(risk_factors)

        if id:
            model = self.get_one(id)

        if model:
            matching_rule_sets = []
            for mrs in (
                MatchingRuleSet.query.filter(
                    MatchingRuleSet.assignable_advocate_id == model.practitioner_id
                )
                .order_by(MatchingRuleSet.id.asc())
                .all()
            ):
                rule_set_dict = {
                    "id": mrs.id,
                    "rules": {
                        "country_rule": [],
                        "organization_rule": [],
                        "organization_exclude_rule": [],
                        "track_rule": [],
                        "risk_factor_rule": [],
                    },
                }

                for r in mrs.matching_rules:
                    rule_dict = {
                        "id": r.id,
                        "entity": r.entity.value,
                        "type": r.type.value,
                        "all": r.all,
                        "identifiers": [],
                    }
                    if r.entity == MatchingRuleEntityType.COUNTRY:
                        matching_countries = [
                            c for c in country_repo.all() if c.alpha_2 in r.identifiers
                        ]
                        rule_dict["identifiers"] = [
                            {"label": c.name, "value": c.alpha_2}
                            for c in matching_countries
                        ]
                        rule_set_dict["rules"]["country_rule"].append(rule_dict)

                        continue
                    if (
                        r.entity == MatchingRuleEntityType.ORGANIZATION
                        and r.type == MatchingRuleType.INCLUDE
                    ):
                        rule_dict["identifiers"] = [
                            {"label": o.name, "value": str(o.id)}
                            for o in Organization.query.filter(
                                Organization.id.in_(r.identifiers)
                            )
                        ]

                        rule_set_dict["rules"]["organization_rule"].append(rule_dict)

                        continue
                    if (
                        r.entity == MatchingRuleEntityType.ORGANIZATION
                        and r.type == MatchingRuleType.EXCLUDE
                    ):
                        rule_dict["identifiers"] = [
                            {"label": o.name, "value": str(o.id)}
                            for o in Organization.query.filter(
                                Organization.id.in_(r.identifiers)
                            )
                        ]

                        rule_set_dict["rules"]["organization_exclude_rule"].append(
                            rule_dict
                        )

                        continue
                    if r.entity == MatchingRuleEntityType.MODULE:
                        rule_dict["identifiers"] = [
                            {
                                "label": m.frontend_name if m.frontend_name else m.name,
                                "value": str(m.id),
                            }
                            for m in Module.query.filter(Module.id.in_(r.identifiers))
                        ]

                        rule_set_dict["rules"]["track_rule"].append(rule_dict)
                        continue
                    if r.entity == MatchingRuleEntityType.USER_FLAG:
                        rule_dict["identifiers"] = [
                            {"label": uf.name, "value": str(uf.id)}
                            for uf in RiskFlag.query.filter(
                                RiskFlag.id.in_(r.identifiers)
                            )
                        ]
                        rule_set_dict["rules"]["risk_factor_rule"].append(rule_dict)
                        continue

                matching_rule_sets.append(rule_set_dict)
            self._template_args["matching_rule_sets_json"] = json.dumps(
                matching_rule_sets
            )

            self._template_args["assignable_advocate_id"] = model.practitioner_id

        return super().edit_view()

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
            AssignableAdvocate,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class VerticalGroupVersionView(MavenAuditedView):
    read_permission = "read:vertical-group-version"
    delete_permission = "delete:vertical-group-version"
    create_permission = "create:vertical-group-version"
    edit_permission = "edit:vertical-group-version"

    column_exclude_list = ("verticals",)
    edit_template = "vertical_group_version_edit_template.html"

    column_labels = {"verticals": "Vertical Groups"}

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
            VerticalGroupVersion,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class VerticalGroupView(MavenAuditedView):
    read_permission = "read:vertical-group"
    delete_permission = "delete:vertical-group"
    create_permission = "create:vertical-group"
    edit_permission = "edit:vertical-group"

    edit_template = "vertical_group_edit_template.html"

    column_labels = {"title": "Title (display name)"}

    # We want to use just Track names for selection. Hide "Modules" to preven confusion.
    # Hide "allowed_tracks" to not expose the VerticalGroupTrack implementation detail.
    form_excluded_columns = ("hero_image", "allowed_tracks", "modules")

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)

        vertical_group = db.session.query(self.model).get(id)
        if vertical_group is None:
            return

        form.tracks.process_formdata(
            [n.value for n in vertical_group.allowed_track_names]
        )

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.hero_image_id = ImageUploadField(
            label="Hero image", allowed_extensions=["jpg", "jpeg", "png"]
        )
        form_class.tracks = Select2MultipleField(
            label="Allowed tracks",
            choices=[(track.value, track.value) for track in TrackName],
        )
        return form_class

    def on_model_change(self, form, vertical_group, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        vertical_group.allowed_tracks = [
            VerticalGroupTrack(track_name=track, vertical_group_id=vertical_group.id)
            for track in request.form.getlist("tracks")  # support multiple tracks
        ]
        super().on_model_change(form, vertical_group, is_created)

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
            VerticalGroup,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class CharacteristicView(MavenAuditedView):
    read_permission = "read:characteristic"
    delete_permission = "delete:characteristic"
    create_permission = "create:characteristic"
    edit_permission = "edit:characteristic"

    audit_model_view = True  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bool", base class "MavenAuditedView" defined the type as "None")

    form_columns = ("name", "modified_at")

    def delete_model(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().delete_model(model)
        flash(
            "The characteristic has been deleted and removed from all practitioners. "
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
            Characteristic,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class LanguageView(MavenAuditedView):
    read_permission = "read:language"
    create_permission = "create:language"
    edit_permission = "edit:language"

    audit_model_view = True  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bool", base class "MavenAuditedView" defined the type as "None")

    column_searchable_list = ["name"]

    form_columns = ("name", "abbreviation", "inverted_name", "iso_639_3")
    form_edit_rules = ("name", "abbreviation", "slug")

    form_args = {
        "slug": {
            "validators": [validators.DataRequired()],
        },
    }

    form_widget_args = {
        "name": {"readonly": True},
        "slug": {"readonly": True},
    }

    column_descriptions = {
        "name": "<i>Submit JIRA ticket to update this field</i>",
        "slug": "<i>Submit JIRA ticket to update this field</i>",
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
            Language,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class HasRiskFactorFilter(BooleanEqualFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "1":
            exists_clause = MemberRiskFlag.query.filter(
                MemberRiskFlag.user_id == User.id
            ).exists()
            query = query.filter(exists_clause)
        return query


class CAEmailFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_alias = aliased(User)
        return (
            query.join(MemberPractitionerAssociation)
            .join(MemberPractitionerAssociation.practitioner_profile)
            .join(user_alias)
            .filter(
                user_alias.email == value,
                MemberPractitionerAssociation.type == CareTeamTypes.CARE_COORDINATOR,
            )
        )


class TrackFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.filter(MemberTrack.name.ilike("%" + value + "%"))


class HighRiskUsersView(SimpleSortViewMixin, MavenAuditedView):
    read_permission = "read:cc-high-risk-users-dashboard"
    edit_permission = "edit:cc-high-risk-users-dashboard"

    list_template = "high_risk_user_dash.html"

    column_filters = (
        HasRiskFactorFilter(None, "Must Have Risk Flag"),
        CAEmailFilter(None, "Care Advocate Email"),
        TrackFilter(None, "Track Name"),
    )

    column_list = [
        "id",
        "email",
        "full_name",
        "user_flags",
        "member_note",
        "last_message_activity",
        "last_appointment_activity",
    ]

    column_sortable_list = ["id", "email"]

    simple_sorters = {
        "full_name": lambda u: (u.last_name, u.first_name),
        "member_note": lambda u: (
            u.member_profile.follow_up_reminder_send_time
            or datetime.datetime(datetime.MINYEAR, 1, 1)
        ),
        "last_message_activity": lambda u: (
            u.last_message_activity or datetime.datetime(datetime.MINYEAR, 1, 1)
        ),
        "last_appointment_activity": lambda u: (
            u.last_appointment_activity or datetime.datetime(datetime.MINYEAR, 1, 1)
        ),
    }

    column_formatters = {
        "user_flags": _risk_flags,
        "member_note": _member_note_display_info,
    }

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
        if all(name != "Must Have Risk Flag" for _, name, _ in filters):
            filters.append((len(filters), "Must Have Risk Flag", "1"))
        if all(name != "Care Advocate Email" for _, name, _ in filters):
            filters.append((len(filters), "Care Advocate Email", _login_cc_email()))
        count, result = super().get_list(
            page, sort_column, sort_desc, search, filters, execute, page_size
        )
        if self._simple_sort_column not in [
            "last_message_activity",
            "last_appointment_activity",
        ]:
            self._get_last_activity_info(result)
        return count, result

    def _apply_pagination(self, query, page, page_size):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self._simple_sort_column in [
            "last_message_activity",
            "last_appointment_activity",
        ]:
            query = query.all()
            self._get_last_activity_info(query)
        return super()._apply_pagination(query, page, page_size)

    def _get_last_activity_info(self, users):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not users:
            return
        user_ids = [u.id for u in users]
        msg_results = db.session.execute(
            """
            SELECT cu.user_id, MAX(m.created_at)
            FROM message m
            JOIN channel_users cu ON cu.channel_id = m.channel_id
            WHERE cu.user_id in :user_ids
            GROUP BY cu.user_id
        """,
            {"user_ids": user_ids},
        )
        appt_results = db.session.execute(
            """
            SELECT s.user_id, MAX(a.scheduled_start)
            FROM appointment a
            JOIN schedule s ON s.id = a.member_schedule_id
            WHERE s.user_id in :user_ids
            GROUP BY s.user_id
        """,
            {"user_ids": user_ids},
        )
        msg_activity = {k: v for k, v in msg_results}
        appt_activity = {k: v for k, v in appt_results}
        for u in users:
            u.last_message_activity = (
                msg_activity[u.id] if u.id in msg_activity else None
            )
            u.last_appointment_activity = (
                appt_activity[u.id] if u.id in appt_activity else None
            )

    def get_url(self, endpoint, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # this prevents the edit link from being 'high_risk_dashboard/edit'
        if endpoint == ".edit_view":
            endpoint = "user" + endpoint
        return super().get_url(endpoint, **kwargs)

    def get_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.session.query(self.model).join(MemberTrack)

    def get_count_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            self.session.query(func.count("*"))
            .select_from(self.model)
            .join(MemberTrack)
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
            User,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class CertificationView(MavenAuditedView):
    read_permission = "read:certification"
    delete_permission = "delete:certification"
    create_permission = "create:certification"
    edit_permission = "edit:certification"

    form_rules = ["name"]
    column_searchable_list = ["name"]

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
            Certification,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


def _is_valid_state_and_country(state, country_code) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    if country_code != "US" and state and state.abbreviation != "ZZ":
        return False
    return True


class UserAssetView(MavenAuditedView):
    read_permission = "read:user-asset"
    delete_permission = "delete:user-asset"
    create_permission = "create:user-asset"

    column_list = (
        "id",
        "user",
        "state",
        "file_name",
        "content_type",
        "content_length",
        "modified_at",
    )
    column_filters = ("user_id", "state")
    column_sortable_list = ("id", "user", "state")

    form_columns = ("user",)

    form_ajax_refs = {
        "user": {"fields": ("id",), "page_size": 10},
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
            UserAsset,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.asset = UserAssetUploadField(
            label="Asset", allowed_extensions=["jpg", "jpeg", "png", "pdf"]
        )
        return form_class

    def after_model_change(self, form, model, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if is_created:
            # Model must be saved and have an id before the upload can be done
            model.blob.upload_from_file(form.asset.data.stream)
            complete_upload.delay(model.id)
        super().after_model_change(form, model, is_created)


class UserAssetUploadField(upload.FileUploadField):
    def populate_obj(self, obj, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self._is_uploaded_file(self.data):
            content_length = self.data.content_length
            if not content_length:
                self.data.stream.seek(0, os.SEEK_END)
                content_length = self.data.stream.tell()
                self.data.stream.seek(0, os.SEEK_SET)

            setattr(  # noqa  B010  TODO:  Do not call setattr with a constant attribute value, it is not any safer than normal property access.
                obj, "file_name", self.data.filename
            )
            setattr(  # noqa  B010  TODO:  Do not call setattr with a constant attribute value, it is not any safer than normal property access.
                obj, "state", UserAssetState.UPLOADING
            )
            setattr(  # noqa  B010  TODO:  Do not call setattr with a constant attribute value, it is not any safer than normal property access.
                obj, "content_type", "application/octet-stream"
            )
            setattr(  # noqa  B010  TODO:  Do not call setattr with a constant attribute value, it is not any safer than normal property access.
                obj, "content_length", content_length
            )


class AddressView(MavenAuditedView):
    # Don't show Address in the navigation
    def is_visible(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return False

    # Limit this to only User-linked addresses
    def get_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return super().get_query().filter(Address.user_id > 0)

    def get_count_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return super().get_count_query().filter(Address.user_id > 0)

    def get_one(self, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self.get_query().filter(self.model.id == id).one()

    # Show, but don't allow editing of, the user
    form_widget_args = {
        "user": {"disabled": True},
    }
    # Even though the widget is disabled, must set user to ajax or else it loads all users into the disabled select
    form_ajax_refs = {"user": USER_AJAX_REF}

    form_excluded_columns = (
        "created_at",
        "modified_at",
        "shipments",
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
            Address,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    def after_model_change(self, form, model, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().after_model_change(form, model, is_created)

        # Trigger demographics update for members with debit cards
        if model.user_id:
            qualified_wallet = qualified_reimbursement_wallet(model.user_id)
            if qualified_wallet and qualified_wallet.debit_card:
                update_member_demographics.delay(qualified_wallet.id)


class NeedsView(ModalUpdateMixin, MavenAuditedView):
    read_permission = "read:need"
    delete_permission = "delete:need"
    create_permission = "create:need"
    edit_permission = "edit:need"

    selected_time_zone = "America/New_York"
    edit_template = "needs_edit_template.html"
    create_template = "needs_create_template.html"

    column_list = ("id", "name", "description", "categories", "hide_from_multitrack")

    column_labels = {
        "id": "Id",
        "name": "Name",
        "description": "Description",
    }

    column_sortable_list = (
        "id",
        "name",
    )
    column_default_sort = ("id", False)
    column_searchable_list = (Need.name,)
    column_filters = (Need.id, Need.slug, Need.name, Need.description)

    form_columns = (
        "name",
        "slug",
        "description",
        "display_order",
        "categories",
        "non_restricted_verticals",
        "keywords",
        "specialties",
        "promote_messaging",
        "hide_from_multitrack",
    )
    form_args = {
        "name": {
            "validators": [validators.DataRequired()],
        },
        "description": {
            "validators": [validators.DataRequired()],
        },
        "categories": {
            "validators": [validators.InputRequired()],
        },
        "slug": {
            "validators": [validators.DataRequired()],
        },
    }

    form_excluded_columns = (
        "allowed_tracks",
        "restricted_verticals",
        "created_at",
        "modified_at",
    )
    form_extra_fields = {
        "non_restricted_verticals": QuerySelectMultipleField(
            label="Verticals",
            query_factory=lambda: Vertical.query.filter(Vertical.deleted_at == None),
        )
    }
    form_widget_args = {
        "name": {"readonly": True},
        "description": {"readonly": True},
        "slug": {"readonly": True},
        "categories": {"class": "queryselect_required"},
        "tracks": {"class": "queryselect_required"},
        "created_at": {"disabled": True},
        "modified_at": {"disabled": True},
    }

    column_descriptions = {
        "name": "<i>Submit JIRA ticket to update this field</i>",
        "description": "<i>Submit JIRA ticket to update this field</i>",
        "slug": "<i>Submit JIRA ticket to update this field</i>",
    }

    _inline_models = None

    @property
    def inline_models(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._inline_models is None:
            self._inline_models = (RestrictedVerticalInlineCollection(),)
        return self._inline_models

    _form_ajax_refs = None

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)

        need = db.session.query(self.model).get(id)
        if need is None:
            return

        form.tracks.process_formdata([n.value for n in need.allowed_track_names])
        form.non_restricted_verticals.choices = [
            (v.id, str(v))
            for v in db.session.query(Vertical)
            .filter(Vertical.deleted_at == None)
            .all()
        ]

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.tracks = Select2MultipleField(
            label="Allowed tracks",
            choices=[(track.value, track.value) for track in TrackName],
            validators=[validators.DataRequired()],
        )
        return form_class

    def on_model_change(self, form, need, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        need.allowed_tracks = [
            NeedTrack(track_name=track, need_id=need.id)
            for track in request.form.getlist("tracks")
        ]
        super().on_model_change(form, need, is_created)

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # Skip validation on delete
        if type(form).__name__ == "DeleteForm":
            # Manually "cascade" delete
            db.session.query(NeedVertical).filter(
                NeedVertical.need_id == form.id.data
            ).delete(synchronize_session="fetch")
            db.session.query(NeedAppointment).filter(
                NeedAppointment.need_id == form.id.data
            ).delete(synchronize_session="fetch")
            db.session.commit()
            return True

        # validators.InputRequired does not work for these, as wtforms sets `display: none`, and then can't display the error because it's "unfocusable"
        if not form.categories.data:
            flash("Categories must not be empty")
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
            Need,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class NeedCategoryView(ModalUpdateMixin, MavenAuditedView):
    read_permission = "read:need-category"
    delete_permission = "delete:need-category"
    create_permission = "create:need-category"
    edit_permission = "edit:need-category"

    selected_time_zone = "America/New_York"
    edit_template = "need_category_edit_template.html"
    create_template = "need_category_create_template.html"

    column_list = (
        "id",
        "name",
        "display_order",
        "allowed_tracks",
        "hide_from_multitrack",
    )

    column_labels = {
        "id": "Id",
        "name": "Name",
        "display_order": "Display Order",
    }

    column_sortable_list = (
        "id",
        "name",
        "display_order",
    )
    column_default_sort = ("id", False)
    column_searchable_list = (NeedCategory.name,)
    column_filters = (NeedCategory.id, NeedCategory.name)

    form_columns = (
        "name",
        "needs",
        "slug",
        "display_order",
        "image_id",
        "hide_from_multitrack",
    )

    form_args = {
        "name": {
            "validators": [validators.DataRequired()],
        },
        "slug": {
            "validators": [validators.DataRequired()],
        },
    }

    form_widget_args = {
        "name": {"readonly": True},
        "slug": {"readonly": True},
        "needs": {"class": "queryselect_required"},
        "tracks": {"class": "queryselect_required"},
        "created_at": {"disabled": True},
        "modified_at": {"disabled": True},
    }

    column_descriptions = {
        "name": "<i>Submit JIRA ticket to update this field</i>",
        "slug": "<i>Submit JIRA ticket to update this field</i>",
    }

    _form_ajax_refs = None

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)

        need_category = db.session.query(self.model).get(id)
        if need_category is None:
            return

        form.tracks.process_formdata(
            [n.value for n in need_category.allowed_track_names]
        )

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.tracks = Select2MultipleField(
            label="Allowed tracks",
            choices=[(track.value, track.value) for track in TrackName],
            validators=[validators.DataRequired()],
        )
        return form_class

    def on_model_change(self, form, need_category, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        need_category.allowed_tracks = [
            NeedCategoryTrack(track_name=track, need_category_id=need_category.id)
            for track in request.form.getlist("tracks")
        ]
        super().on_model_change(form, need_category, is_created)

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
            NeedCategory,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class EmailDomainDenylistView(MavenAuditedView):
    read_permission = "read:email-domain-denylist"
    delete_permission = "delete:email-domain-denylist"
    create_permission = "create:email-domain-denylist"
    edit_permission = "edit:email-domain-denylist"

    edit_template = "email_domain_denylist_edit.html"
    create_template = "email_domain_denylist_edit.html"

    column_list = (
        "id",
        "domain",
        "created_at",
        "modified_at",
    )

    column_sortable_list = (
        "id",
        "domain",
        "created_at",
        "modified_at",
    )
    column_default_sort = ("id", False)

    form_widget_args = {
        "created_at": {"disabled": True},
        "modified_at": {"disabled": True},
    }

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)

        log.info(
            f"{'Creating' if is_created else 'Updating'} email domain denylist item",
            id=model.id,
            domain=model.domain,
            modified_by=login.current_user.id,
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
            EmailDomainDenylist,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class GDPRDeletionBackupView(MavenAuditedView):
    read_permission = "read:gdpr-deletion-backup"
    delete_permission = "delete:gdpr-deletion-backup"
    create_permission = "create:gdpr-deletion-backup"
    edit_permission = "edit:gdpr-deletion-backup"

    column_list = (
        "id",
        "user_id",
        "created_at",
        "data",
        "requested_date",
        "restoration_errors",
    )
    column_sortable_list = ("id", "user_id", "created_at", "requested_date")
    column_searchable_list = ("id", "user_id", "created_at", "data")
    column_filters = ("id", "user_id", "created_at", "data", "requested_date")
    column_default_sort = ("requested_date", True)

    def delete_model(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Perform pre-delete actions and then delete the model.
        :param model: The model that is going to be deleted.
        :return: True if the model was successfully deleted, False otherwise.
        """
        try:
            user_id = model.user_id

            gdpr_data_delete = GDPRDataDelete()
            gdpr_data_delete.delete(user_id)

            super().on_model_delete(model)
            super().delete_model(model)

            return True
        except Exception as e:
            flash(f"Error deleting record: {e}", "error")
            return False

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
            GDPRDeletionBackup,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class GDPRUserRequestView(MavenAuditedView):
    read_permission = "read:gdpr-user-request"
    delete_permission = "delete:gdpr-user-request"
    create_permission = "create:gdpr-user-request"
    edit_permission = "edit:gdpr-user-request"

    column_list = (
        "id",
        "user_id",
        "user_email",
        "status",
        "source",
        "created_at",
        "modified_at",
    )
    column_sortable_list = ("id", "user_id", "user_email", "created_at")
    column_searchable_list = (
        "id",
        "user_id",
        "user_email",
        "status",
        "source",
        "created_at",
        "modified_at",
    )
    column_filters = (
        "id",
        "user_id",
        "user_email",
        "status",
        "source",
        "created_at",
        "modified_at",
    )
    column_default_sort = ("created_at", False)

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
            GDPRUserRequest,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AsyncEncounterSummaryView(MavenAuditedView):
    read_permission = "read:non-appointment-notes"

    can_view_details = True
    details_template = "async_encounter_summaries_details_template.html"
    column_filters = [
        "user_id",
        "provider_id",
        "questionnaire.oid",
    ]
    column_list = (
        "user_id",
        "provider_id",
        "questionnaire.oid",
        "encounter_date",
    )
    column_labels = {
        "user_id": "Subject User Id",
        "provider_id": "Author User Id",
        "questionnaire.oid": "Questionnaire Type",
        "encounter_date": "Encounter Date (UTC)",
    }
    column_details_list = (
        "provider_id",
        "user_id",
        "questionnaire_id",
        "encounter_date",
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
            AsyncEncounterSummary,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class VerticalAccessByTrackView(MavenAuditedView):
    read_permission = "read:vertical-access-by-track"
    delete_permission = "delete:vertical-access-by-track"
    create_permission = "create:vertical-access-by-track"
    edit_permission = "edit:vertical-access-by-track"

    column_list = ("client_track_id", "vertical_id", "track_modifiers")
    form_columns = ("client_track_id", "vertical_id", "track_modifiers")

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # All validation & etc must happen before we commit the new model
        vertical_id = form.vertical_id.data
        client_track_id = form.client_track_id.data

        # Validate vertical_id
        vertical = (
            db.session.query(Vertical).filter(Vertical.id == vertical_id).one_or_none()
        )
        if not vertical:
            flash("Vertical with given id does not exist")
            return None

        # Validate client_track_id
        client_track = (
            db.session.query(ClientTrack)
            .filter(ClientTrack.id == client_track_id)
            .one_or_none()
        )
        if not client_track:
            flash("Client Track with given id does not exist")
            return None

        # Proceed with creating the model
        model = super().create_model(form)

        # If the model is False, super().create_model failed
        if not model:
            return model

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
            VerticalAccessByTrack,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
