from __future__ import annotations

import datetime
import io
import json
from concurrent.futures import ThreadPoolExecutor, wait

import ddtrace
import flask
import flask_login as login
import qrcode
from flask import Response, abort, flash, request, send_file, url_for
from flask_admin import AdminIndexView, expose, helpers
from flask_admin.model.helpers import get_mdict_item_or_list
from otpauth import OtpAuth
from sqlalchemy.orm import Load
from werkzeug.utils import redirect, secure_filename

from admin.common import (
    SPEED_DATING_VERTICALS,
    https_url,
    is_enterprise_cc_appointment,
    totp_secret,
)
from admin.login import LoginForm
from admin.views.base import ViewExtras
from admin.views.metrics import load_metric, load_metric_names
from appointments.models.appointment import Appointment
from appointments.tasks.availability import update_practitioners_next_availability
from audit_log.utils import (
    emit_audit_log_login,
    emit_audit_log_logout,
    emit_audit_log_read,
    emit_bulk_audit_log_update,
)
from authn.domain.service import authn
from authn.models.user import User
from authz.services.block_list import BlockableAttributes, BlockList
from authz.utils.permissions import get_permission_dictionary
from authz.utils.rbac_permissions import (
    CREATE_BLOCK_LIST,
    DELETE_BLOCK_LIST,
    EDIT_BLOCK_LIST,
)
from care_advocates.models.assignable_advocates import AssignableAdvocate
from common.payments_gateway import get_client
from common.services import ratelimiting
from direct_payment.billing.constants import INTERNAL_TRUST_PAYMENT_GATEWAY_URL
from direct_payment.reconciliation.constants import ALL_REPORT_CLINIC_NAMES
from eligibility import get_verification_service
from eligibility import service as e9y_service
from eligibility.e9y import model as e9y_model
from eligibility.utils import sub_populations as sub_population_utils
from geography.repository import CountryRepository
from models.enterprise import Organization
from models.profiles import Agreement, Language, PractitionerProfile
from models.tracks.track import TrackName
from models.verticals_and_specialties import Vertical
from storage.connection import db
from utils.log import logger
from utils.survey_monkey import get_results_for_all_surveys
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.services.reimbursement_benefits import find_maven_gold_wallet_user_objs
from wallet.services.wallet_client_reporting import (
    download_client_report,
    download_client_report_audit,
    download_transactional_client_report,
)

log = logger(__name__)

GLOBAL_BOOKING_BUFFER_MAX = 10_000
GLOBAL_MAX_CAPACITY_MAX = 20
GLOBAL_PREP_BUFFER_MAX = 500
GLOBAL_MAX_CAPACITY_ERROR = "One or more CA has a Daily Intro Capacity greater than this Total Daily Capacity. Please ensure Daily Intro Capacity is less than the Total Daily Capacity that you are trying to set for each CA"

TEMPLATE_EDIT_VARIABLE = "can_edit"
TEMPLATE_CREATE_VARIABLE = "can_create"
TEMPLATE_DELETE_VARIABLE = "can_delete"

BLOCK_LIST_PERMISSIONS = {
    EDIT_BLOCK_LIST: TEMPLATE_EDIT_VARIABLE,
    CREATE_BLOCK_LIST: TEMPLATE_CREATE_VARIABLE,
    DELETE_BLOCK_LIST: TEMPLATE_DELETE_VARIABLE,
}

READ_ADMIN_PERMISSION = "read:admin"

MAX_RETRIES = 3
BASE_RETRY_DELAY_IN_SECONDS = 2
RETRIABLE_STATUS_CODES = [429, 502, 503]


class MavenIndexView(AdminIndexView, ViewExtras):
    def __init__(self) -> None:
        super().__init__()
        self.e9y_service = get_verification_service()

    @expose("/")
    def index(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        return self.render("index.html")

    @expose(
        "/block_list",
        methods=(
            "GET",
            "POST",
        ),
    )
    def block_list(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        block_list = BlockList()
        permissions_dict = self.get_block_list_permissions()
        # set the template variables for permissions
        self._template_args.update(permissions_dict)

        if request.method == "GET":
            attributes = []
            for attribute in BlockableAttributes:
                values = block_list.get_block_list(attribute)
                if values:
                    attributes.append((attribute, values))
            self._template_args["blockable_attributes"] = BlockableAttributes
            self._template_args["attributes"] = attributes
            return self.render("block_list_index.html")

        if request.method == "POST":
            form = flask.request.form
            attribute = form.get("attribute")  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[Any]", variable has type "str")
            value = form.get("value")

            if form.get("unblock") and permissions_dict[TEMPLATE_DELETE_VARIABLE]:
                block_list.unblock_attribute(attribute, value)  # type: ignore[arg-type] # Argument 2 to "unblock_attribute" of "BlockList" has incompatible type "Optional[Any]"; expected "str"
            elif permissions_dict[TEMPLATE_CREATE_VARIABLE]:
                block_list.block_attribute(attribute, value)  # type: ignore[arg-type] # Argument 2 to "block_attribute" of "BlockList" has incompatible type "Optional[Any]"; expected "str"
            else:
                abort(403, "You do not have the permissions to make these changes.")
            return redirect("/admin/block_list")

        return self.render("block_list_index.html")

    @staticmethod
    def get_block_list_permissions() -> dict[str, bool]:
        # get permission value (permission, value) for the given user
        if login.current_user.is_authenticated:
            user_permissions = get_permission_dictionary(
                login.current_user.id, *BLOCK_LIST_PERMISSIONS.keys()
            )
            log.info("Located permissions for user.", permissions=user_permissions)
            # transform the permission mapping to template variables
            permission_dict = {
                BLOCK_LIST_PERMISSIONS[permission_name]: has_permission
                for permission_name, has_permission in user_permissions.items()
            }
            return permission_dict
        return {}

    @expose(
        "/authz_bulk_insert",
        methods=("GET",),
    )
    def authz_bulk_insert(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        permissions_dict = self.get_block_list_permissions()
        # set the template variables for permissions
        self._template_args.update(permissions_dict)
        # abort(403, "You do not have the permissions to make these changes.")
        return self.render("rbac_bulk_insert.html")

    @expose("/enterprise_setup")
    def enterprise_setup(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))

        # Find the languages used for all agreements.
        # If no languages are set, default to English
        agreement_languages = (
            db.session.query(Language)
            .join(Agreement, Agreement.language_id == Language.id)
            .filter(Language.name != Language.ENGLISH)
            .distinct()
            .all()
        )

        english = Language.query.filter_by(name=Language.ENGLISH).one()
        languages = [english] + agreement_languages

        return self.render(
            "enterprise_setup.html",
            tracks=[(track.value, track.name) for track in TrackName],
            languages=[(language.id, language.name) for language in languages],
        )

    @expose("/enterprise_setup_confirm", methods=("POST",))
    def enterprise_setup_confirm(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Associate a Maven user with an E9Y record- results in generating a verification record for a user
        """

        form = flask.request.form
        user_id = int(form["user_id"])
        member_id = int(form["member_id"])
        user = User.query.get(user_id)
        zendesk_id = form["zendesk_id"]

        member = self.e9y_service.get_eligibility_record_by_member_id(
            member_id=member_id
        )
        source = "Eligibility Service Member"
        association_source = "e9y"

        if not member:
            flash(f"Member not found for id: {member_id}", category="error")
        if not user:
            flash(f"User not found for id: {user_id}", category="error")
        if not user or not member:
            return self.render(
                "enterprise_setup.html",
                tracks=[(track.value, track.name) for track in TrackName],
                languages=[
                    (language.id, language.name) for language in Language.query.all()
                ],
            )
        return self.render(
            "enterprise_setup_confirm.html",
            initial_form=form,
            source=source,
            user=user,
            member=member,
            association_source=association_source,
            zendesk_id=zendesk_id,
        )

    @expose("/backfill_org_sub_populations", methods=("POST",))
    def backfill_org_sub_populations(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Backfill the sub-population information for active member tracks in the organization
        """
        form = flask.request.form
        organization_id = int(form["organization_id"])

        new_sub_pop_values = sub_population_utils.backfill_org_sub_populations(
            organization_id=organization_id,
            overwrite_all=False,
            no_op=False,
        )
        log.info(
            f"Backfilled organization sub-populations: {new_sub_pop_values}",
            organization_id=organization_id,
        )
        flash_messages = flask.session.get("_flashes", [])
        users_without_sub_pops = [
            user_id
            for user_id in new_sub_pop_values
            if new_sub_pop_values.get(user_id, None) is None
        ]
        num_valid_sub_pop_values = len(new_sub_pop_values) - len(users_without_sub_pops)
        if num_valid_sub_pop_values > 0:
            grammarized_string = (
                "member tracks have"
                if num_valid_sub_pop_values != 1
                else "member track has"
            )
            flash_messages.append(
                (
                    "success",
                    f"{num_valid_sub_pop_values} {grammarized_string} been backfilled with sub-population information.",
                )
            )
        else:
            flash_messages.append(
                ("danger", "No sub-population information was backfilled.")
            )
        if len(users_without_sub_pops) > 0:
            flash_messages.append(
                (
                    "info",
                    f"The following users could not be matched to a sub-population: {', '.join(map(str, users_without_sub_pops))}",
                )
            )
        flask.session["_flashes"] = flash_messages

        return redirect(f"/admin/organization/edit/?id={organization_id}")

    @expose("/fastfind")
    def fastfind(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        query = get_mdict_item_or_list(request.args, "q")
        users = User.query.filter(User.email == query)

        if users.count() > 0:
            user = users.one()
            if user.practitioner_profile:
                return redirect(f"/admin/practitionerprofile/edit/?id={user.id}")
            elif user.member_profile:
                return redirect(f"/admin/memberprofile/edit/?id={user.id}")

        abort(404, "Not found")

    @expose("/service_metrics")
    def service_metrics(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.render("service_metrics.html", all_metric_names=load_metric_names())

    @expose("/service_metrics/metric", methods=["GET"])
    def service_metric_data(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        name = get_mdict_item_or_list(request.args, "id")
        if name:
            response = load_metric(name.split(","))
            return json.dumps(response, default=json_converter)

    @expose("/marketing_tools")
    def marketing_tools(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        return self.render("marketing.html")

    @expose("/survey_responses")
    @login.login_required
    def survey_responses(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        survey_responses = get_results_for_all_surveys()
        return self.render("survey_responses.html", survey_responses=survey_responses)

    @expose("/payment_tools")
    def payment_tools(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        return self.render("payments.html")

    @expose("/delete_user")
    def delete_user_admin_page(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        return self.render("delete_user.html")

    @expose("/wallet_tools")
    def wallet_tools(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        wallet_orgs = (
            ReimbursementOrganizationSettings.query.join(
                ReimbursementOrganizationSettings.organization
            )
            .with_entities(
                Organization.id, Organization.name, ReimbursementOrganizationSettings.id
            )
            .order_by(
                ReimbursementOrganizationSettings.id.desc()
            )  # Order by id in descending order
            .all()
        )
        wallet_orgs_deduped = _dedupe_wallet_orgs(wallet_orgs)
        reconciliation_report_clinics = ALL_REPORT_CLINIC_NAMES
        return self.render(
            "wallet.html",
            wallet_organizations=wallet_orgs,
            wallet_organizations_deduped=wallet_orgs_deduped,
            reconciliation_report_clinics=reconciliation_report_clinics,
        )

    @expose("/direct_payment_tools")
    def direct_payment_tools(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        dp_wallet_orgs = (
            Organization.query.join(ReimbursementOrganizationSettings)
            .with_entities(Organization.id, Organization.name)
            .filter(ReimbursementOrganizationSettings.direct_payment_enabled == True)
            .order_by(Organization.id.desc())  # Order by id in descending order
            .all()
        )
        return self.render(
            "direct_payment.html",
            dp_wallet_organizations=dp_wallet_orgs,
        )

    @expose(
        "/direct_payment_tools/wallet_configuration_report",
        [
            "POST",
        ],
    )
    def wallet_configuration_report(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))

        org_ids = request.form.getlist("org_id")
        query_results = find_maven_gold_wallet_user_objs(
            filters=[Organization.id.in_(org_ids)]
        )
        gateway_client = get_client(INTERNAL_TRUST_PAYMENT_GATEWAY_URL)  # type: ignore[arg-type] # Argument 1 to "get_client" has incompatible type "Optional[str]"; expected "str"
        report_data = []

        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(populate_payments_customer, gateway_client, query_objs)
                for query_objs in query_results
            }
            wait(futures)
            for future in futures:
                report_data.append(future.result())

        return self.render(
            "direct_payment__wallet_configuration_report.html", report_data=report_data
        )

    @expose("/wallet_client_report", methods=("POST",))
    def download_wallet_client_report(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        report_id = request.form.get("wallet_client_report_id")
        org_name = request.form.get("org_name")
        if not report_id:
            flash("Invalid Request: Missing report id")
            return
        report = download_client_report(report_id)
        fp = io.BytesIO()
        fp.write(report.getvalue().encode())
        fp.seek(0)
        report.close()

        today = datetime.datetime.today().strftime("%Y%m%d")
        filename = secure_filename(f"{org_name}_Wallet_Report_{today}.csv")
        return send_file(  # type: ignore[call-arg] # Unexpected keyword argument "download_name" for "send_file"
            fp, mimetype="text/csv", as_attachment=True, download_name=filename
        )

    @expose("/wallet_client_report_audit", methods=("POST",))
    def download_wallet_client_report_audit(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        report_id = request.form.get("wallet_client_report_id")
        org_name = request.form.get("org_name")
        if not report_id:
            flash("Invalid Request: Missing report id")
            return

        report = download_client_report_audit(report_id)
        fp = io.BytesIO()
        fp.write(report.getvalue().encode())
        fp.seek(0)
        report.close()

        today = datetime.datetime.today().strftime("%Y%m%d")
        filename = secure_filename(f"{org_name}_Wallet_Report_Audit_{today}.csv")
        return send_file(  # type: ignore[call-arg] # Unexpected keyword argument "download_name" for "send_file"
            fp, mimetype="text/csv", as_attachment=True, download_name=filename
        )

    @expose("/wallet_client_report_transactional", methods=("POST",))
    def download_wallet_client_report_transactional(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        report_id = request.form.get("wallet_client_report_id")
        org_name = request.form.get("org_name")
        if not report_id:
            flash("Invalid Request: Missing report id")
            return

        report = download_transactional_client_report(report_id)
        fp = io.BytesIO()
        fp.write(report.getvalue().encode())
        fp.seek(0)
        report.close()

        today = datetime.datetime.today().strftime("%Y%m%d")
        filename = secure_filename(
            f"{org_name}_Wallet_Report_transactional_{today}.csv"
        )
        return send_file(  # type: ignore[call-arg] # Unexpected keyword argument "download_name" for "send_file"
            fp, mimetype="text/csv", as_attachment=True, download_name=filename
        )

    @expose("/bulk_practitioner_mfa_tools")
    def bulk_mfa_tools(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))

        return self.render("practitioner_mfa.html")

    @expose("/affected_appointments")
    def get_affected_appointments(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        return self.render("affected_appointments.html")

    @ratelimiting.ratelimited(attempts=10, cooldown=60)
    @expose("/login/", methods=("GET", "POST"))
    def login_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # handle user login
        form = LoginForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = form.get_user()
            # "remember" is False by default, as we want it to be
            login.login_user(user)
            emit_audit_log_login(user)

        if login.current_user.is_authenticated:
            return redirect(https_url(".index"))

        self._template_args["form"] = form
        return self.render("login.html")

    @expose("/logout/")
    def logout_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        current_user = login.current_user  # werkzeug.local.LocalProxy
        if current_user.is_authenticated:
            emit_audit_log_logout(current_user)
            login.logout_user()

        return redirect(https_url(".index"))

    @ratelimiting.ratelimited(attempts=2, cooldown=60)
    @expose("/qr/", methods=("POST",))
    def qr_code(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        email = request.form.get("email")
        password = request.form.get("password")
        user = db.session.query(User).filter_by(email=email).first()
        has_admin_permission = get_permission_dictionary(
            user.id, READ_ADMIN_PERMISSION
        ).get(READ_ADMIN_PERMISSION, False)

        if (user is None) or (not has_admin_permission):
            log.debug("No user or not admin for: %s", email)
            abort(403, "User not found or user doesn't have the admin permission")

        if not authn.AuthenticationService().check_password(
            hashed_password=user.password,
            email=user.email,
            plaintext_password=password,  # type: ignore[arg-type] # Argument "plaintext_password" to "check_password" of "AuthenticationService" has incompatible type "Optional[Any]"; expected "str"
            user_id=user.id,
            forwarded_for=request.headers.get("X-Real-IP"),  # type: ignore[arg-type] # Argument "forwarded_for" to "check_password" of "AuthenticationService" has incompatible type "Optional[str]"; expected "str"
        ):
            log.debug("Bad password for %s", user)
            abort(400, "Bad Password or Email!")

        if user.otp_secret:
            abort(400, "2fa already activated!")
        else:
            log.debug("Activating 2fa for %s", user)
            user.otp_secret = totp_secret()
            db.session.add(user)
            db.session.commit()

        auth = OtpAuth(user.otp_secret)
        img = qrcode.make(auth.to_uri("totp", "MavenAdmin", user.email))
        fp = io.BytesIO()
        img.save(fp, "PNG")
        fp.seek(0)

        return send_file(fp, mimetype="image/png")

    @expose("/practitioner_tools")
    def auto_practitioner_invite(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        verticals = (
            db.session.query(Vertical)
            .filter(Vertical.name.in_(SPEED_DATING_VERTICALS))
            .all()
        )
        promo_time_ranges = []
        for vertical in verticals:
            start, end = None, None
            if vertical.promo_start is not None:
                start = vertical.promo_start.isoformat()
            if vertical.promo_end is not None:
                end = vertical.promo_end.isoformat()
            promo_time_ranges.append(f"{vertical.name}: {start} to {end}")
        return self.render("practitioner.html", promo_time_ranges=promo_time_ranges)

    @expose("/appointment/cc_dashboard/<int:appt_id>")
    def appointment_dashboard(self, appt_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))
        appointment = db.session.query(Appointment).get(appt_id)
        if not appointment:
            flash(f"Appointment {appt_id} not found...", category="error")
            return redirect(https_url("admin.index"))
        if not is_enterprise_cc_appointment(appointment):
            flash(
                f"Appointment {appt_id} is not an enterprise care advocate "
                "appointment...",
                category="error",
            )
            return redirect(https_url("admin.index"))

        user = appointment.member
        user_url = url_for("user.edit_view", id=user.id)
        member_profile_url = url_for("memberprofile.edit_view", id=user.id)
        hp = user.health_profile

        # Avoid circular import
        from tracks import service as tracks_svc

        track_svc = tracks_svc.TrackSelectionService()
        organization = track_svc.get_organization_for_user(
            user_id=appointment.member.id
        )

        ca_mapped_fields = {}
        if organization:
            # Redirecting to the verification page for a user
            employee_url = (
                f"/eligibility-admin/user-verification/{user.id}?id={user.id}"
            )

            # build ca_mapped_fields from verification
            e9y_svc = e9y_service.EnterpriseVerificationService()
            verification: e9y_model.EligibilityVerification = (
                e9y_svc.get_verification_for_user_and_org(
                    user_id=user.id, organization_id=organization.id
                )
            )
            if verification:
                raw_fields = {
                    "Plan Carrier": verification.record.get("plan_carrier"),
                    "Plan Name": verification.record.get("plan_name"),
                    "State": verification.record.get("state"),
                    "Employee Status Code": verification.record.get(
                        "employee_status_code"
                    ),
                    "Subcompany Code": verification.record.get("subcompany_code"),
                    "Union Status": verification.record.get("union_status"),
                    "Eligibility Member Id": verification.eligibility_member_id,
                    "Verification Id": verification.verification_id,
                }
                ca_mapped_fields = {
                    k: v for k, v in raw_fields.items() if v is not None
                }

        else:
            employee_url = None
            organization = None
        active_tracks = [
            {
                "name": track.name,
                "phase_name": track.current_phase.name,
                "edit_url": url_for("membertrack.edit_view", id=track.id),
                "extended": track.is_extended,
            }
            for track in user.active_tracks
        ]
        care_team = [
            {
                "url": url_for("practitionerprofile.edit_view", id=p.user_id),
                "full_name": p.user.full_name,
                "verticals": ", ".join(v.display_name or v.name for v in p.verticals),
            }
            for p in user.care_team
        ]

        country_metadata = user.country and CountryRepository(
            session=db.session
        ).get_metadata(country_code=user.country.alpha_2)

        emit_audit_log_read(appointment)
        return self.render(
            "appointment_cc_dashboard.html",
            appointment=appointment,
            member=user,
            user_url=user_url,
            member_profile_url=member_profile_url,
            employee_url=employee_url,
            organization=organization,
            health_profile=hp,
            care_team=care_team,
            active_tracks=active_tracks,
            user_flags=", ".join(f.name for f in user.current_risk_flags()),
            country_metadata=country_metadata,
            ca_mapped_fields=ca_mapped_fields,
        )

    @expose("/care_team_control_center")
    def care_team_control_center(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))

        all_aa_and_prac_profiles = (
            db.session.query(AssignableAdvocate, PractitionerProfile)
            .join(AssignableAdvocate.practitioner)
            .order_by(PractitionerProfile.first_name.asc())
            .options(
                Load(AssignableAdvocate).load_only(  # type: ignore[attr-defined]
                    AssignableAdvocate.max_capacity,
                    AssignableAdvocate.daily_intro_capacity,
                ),
                Load(PractitionerProfile).load_only(  # type: ignore[attr-defined]
                    PractitionerProfile.first_name,
                    PractitionerProfile.last_name,
                    PractitionerProfile.booking_buffer,
                    PractitionerProfile.default_prep_buffer,
                ),
            )
            .all()
        )

        all_assignable_cx = [
            {
                "practitioner_id": aa.practitioner_id,
                "full_name": prac_profile.full_name,
                "booking_buffer": prac_profile.booking_buffer,
                "prep_buffer": prac_profile.default_prep_buffer,
                "max_capacity": aa.max_capacity,
                "daily_intro_capacity": aa.daily_intro_capacity,
            }
            for (aa, prac_profile) in all_aa_and_prac_profiles
        ]

        return self.render(
            "care_team_control_center.html",
            all_assignable_cx=json.dumps(all_assignable_cx, default=json_converter),
            GLOBAL_BOOKING_BUFFER_MAX=GLOBAL_BOOKING_BUFFER_MAX,
            GLOBAL_MAX_CAPACITY_MAX=GLOBAL_MAX_CAPACITY_MAX,
            GLOBAL_PREP_BUFFER_MAX=GLOBAL_PREP_BUFFER_MAX,
        )

    @expose("/care_team_control_center/global_prep_buffer", methods=("POST",))
    def global_prep_buffer(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))

        request_json = request.json if request.is_json else {}
        global_prep_buffer = request_json.get("global_prep_buffer", 0)
        if global_prep_buffer > 500:
            abort(400, "global_prep_buffer must be between 0 and 500")

        count = 0
        for aa in AssignableAdvocate.query.all():
            aa.practitioner.default_prep_buffer = global_prep_buffer
            count += 1

        db.session.commit()

        return json.dumps({"count": count})

    @expose("/care_team_control_center/global_booking_buffer", methods=("POST",))
    def global_booking_buffer(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))

        request_json = request.json if request.is_json else {}
        global_booking_buffer = request_json.get("global_booking_buffer", 0)
        if global_booking_buffer > 10_000:
            abort(400, "global_booking_buffer must be between 0 and 10000")

        count = 0
        assignable_advocates = AssignableAdvocate.query.all()
        for aa in assignable_advocates:
            aa.practitioner.booking_buffer = global_booking_buffer
            count += 1

        emit_bulk_audit_log_update(assignable_advocates)
        db.session.commit()

        return json.dumps({"count": count})

    @expose("/care_team_control_center/global_max_capacity", methods=("POST",))
    def global_max_capacity(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return redirect(https_url(".login_view"))

        request_json = request.json if request.is_json else None
        global_max_capacity = request_json.get("global_max_capacity", 0)
        if global_max_capacity > 20:
            abort(400, "global_max_capacity must be between 0 and 20")

        count = 0
        all_assignable_advocates = AssignableAdvocate.query.all()
        for aa in all_assignable_advocates:
            if global_max_capacity < aa.daily_intro_capacity:
                log.info(GLOBAL_MAX_CAPACITY_ERROR, user_id=aa.practitioner_id)
                return {"error": GLOBAL_MAX_CAPACITY_ERROR}, 400
            aa.max_capacity = global_max_capacity
            count += 1
        db.session.commit()

        # Given that max capacity has changed for all care advocates, we need to update their next_availability
        all_assignable_advocates_ids = [
            aa.practitioner_id for aa in all_assignable_advocates
        ]
        update_practitioners_next_availability.delay(
            all_assignable_advocates_ids, team_ns="care_discovery"
        )

        return json.dumps({"count": count})

    @expose(
        "/me",
        methods=("GET",),
    )
    def fetch_current_user_info(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not login.current_user.is_authenticated:
            return abort(401)

        final_user_to_check_ca_status = get_ca_user_if_exists(login.current_user)
        is_cx = final_user_to_check_ca_status.is_care_coordinator

        return Response(
            json.dumps(
                {
                    "user_id": login.current_user.id,
                    "is_cx": is_cx,
                }
            ),
            mimetype="application/json",
        )

    @expose(
        "/logging/",
        methods=("POST",),
    )
    def post_client_log(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        json_body = request.get_json()
        if json_body and json_body.get("message"):
            msg_str = "admin_client_log: " + json_body["message"]
            log.info(msg_str)
        else:
            log.info("admin_client_log: no message body found in logging request.")

        return Response(
            json.dumps(""),
            200,
            mimetype="application/json",
        )


@ddtrace.tracer.wrap()
def get_ca_user_if_exists(current_user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    admin_user_email = current_user.email
    admin_user_email_prefix = admin_user_email.split("@")[0]
    is_maven_email = admin_user_email.endswith("@mavenclinic.com")
    possible_cx_user_email = f"{admin_user_email_prefix}+prac@mavenclinic.com"

    # fetch the corresponding Care Advocate account for this user, if one exists
    possible_cx_user = (
        User.query.filter(User.email == possible_cx_user_email).first()
        if is_maven_email
        else None
    )

    final_user_result = possible_cx_user or current_user
    return final_user_result


@ddtrace.tracer.wrap()
def replace_id_path_params(val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    partial = val.split("/")
    mapped = map(lambda x: ":id" if x.isnumeric() else x, partial)
    transformed = list(mapped)
    output_str = "/".join(transformed)
    if val[:-1] == "/":
        output_str = output_str + "/"
    return output_str


@ddtrace.tracer.wrap()
def json_converter(o):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if isinstance(o, datetime.datetime):
        return o.__str__()


@ddtrace.tracer.wrap()
def _dedupe_wallet_orgs(wallet_orgs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    seen_ids = set()
    deduplicated = []

    for org in wallet_orgs:
        if org[0] not in seen_ids:
            seen_ids.add(org[0])
            deduplicated.append(org)

    return deduplicated


def populate_payments_customer(gateway_client, query_objs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    payments_customer = None
    if query_objs.ReimbursementWallet.payments_customer_id:
        try:
            payments_customer = gateway_client.get_customer(
                query_objs.ReimbursementWallet.payments_customer_id
            )
        except Exception:
            payments_customer = False
    return {"query_objs": query_objs, "payments_customer": payments_customer}
