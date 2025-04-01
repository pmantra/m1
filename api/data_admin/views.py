import collections
import enum
import importlib
import io
import json
import os
import os.path
import sys
from traceback import format_exc
from typing import Any, List, Tuple

import structlog.contextvars
from flask import flash, redirect, request, send_file, url_for
from flask_admin import AdminIndexView, expose
from markupsafe import Markup
from otpauth import OtpAuth
from sqlalchemy import inspect
from sqlalchemy.orm import load_only

import configuration
from authn.domain.service import authn
from authn.models.user import User
from authz.models.roles import ROLES, Capability
from common.constants import Environment
from data_admin.common import check_environment, types_to_dropdown_options
from data_admin.makers import appointments, care_advocates, cost_breakdown
from data_admin.makers import fertility_clinic as fertility_clinic_maker
from data_admin.makers import forum, health_plans, marketing, messaging, mmb
from data_admin.makers import organization as org_maker
from data_admin.makers import payer as payer_maker
from data_admin.makers import payer_accumulation, payments, provider_matching
from data_admin.makers import questionnaire as questionnaire_maker
from data_admin.makers import role, tracks, user, wallet
from data_admin.utils import (
    extract_fixture_metadata,
    extract_parameters_from_form,
    get_accumulation_report_details,
    substitute_parameters,
)
from health.data_models.risk_flag import RiskFlag
from models.enterprise import Organization, OrganizationEmployee
from models.tracks import TrackName
from models.tracks.phase import generate_phase_names
from models.verticals_and_specialties import Vertical
from payer_accumulator.file_handler import AccumulationFileHandler
from storage.connection import db
from storage.dev import reset_schemas
from utils.exceptions import log_exception
from utils.fixtures import restore_fixtures
from utils.log import logger
from utils.service_owner_mapper import (
    data_admin_maker_ns_mapper,
    service_ns_team_mapper,
)

log = logger(__name__)


TASK_NAMES = frozenset(
    (
        "appointments.tasks.availability.update_practitioners_next_availability",
        "appointments.tasks.availability_requests.find_stale_request_availability_messages",
        "tasks.messaging.create_zd_ticket_for_unresponded_promoted_messages",
    )
)


def check_db_schema() -> int:
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    return len(tables)


class MavenDataAdminHomeView(AdminIndexView):
    default_fixtures = None
    admin_emails = None
    v_options = None
    risk_flags = None

    @expose("/")
    def index(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.fetch_fixture_names()
        self.fetch_db_options()
        self.fetch_admin_emails()

        return self.render(
            "admin/index.html",
            default_fixtures=self.default_fixtures,
            parameterizable_fixtures=self.parameterizable_fixtures,  # Pass to template
            admin_emails=self.admin_emails,
            task_names=TASK_NAMES,
            roles=types_to_dropdown_options(ROLES),
            vertical_options=self.v_options,
            track_options={
                # mapping of track_name to the track's phase_names
                track_name.value: generate_phase_names(track_name)
                for track_name in TrackName
            },
            risk_flags=self.risk_flags,
            allow_db_reset=(os.environ.get("ALLOW_DATABASE_RESET") != "false"),
        )

    def fetch_fixture_names(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        config = configuration.get_data_admin_config()
        fixtures = []
        parameterizable_fixtures = {}  # Track which fixtures are parameterizable

        for dirpath, _, filenames in os.walk(config.fixture_directory):
            if dirpath != config.fixture_directory:
                subdirectory = dirpath.split(config.fixture_directory)[1]
            else:
                subdirectory = ""
            for file in filenames:
                fullpath = os.path.join(dirpath, file)
                if not os.path.isfile(fullpath):
                    continue

                name, ext = os.path.splitext(file)
                if ext != ".json":
                    continue

                with open(fullpath, "r") as handle:
                    content = handle.read()
                    extract_fixture_metadata(
                        content, name, parameterizable_fixtures, subdirectory
                    )

                if subdirectory:
                    full_name = (subdirectory + ":_" + name).lstrip("/")
                    fixtures.append((full_name, content))
                else:
                    fixtures.append((name, content))

        self.default_fixtures = []
        # Sort fixtures by name, but put default first
        for fixture in sorted(fixtures, key=lambda f: f[0]):
            if fixture[0] == "default":
                self.default_fixtures.insert(0, fixture)
            else:
                self.default_fixtures.append(fixture)

        self.parameterizable_fixtures = parameterizable_fixtures

    def fetch_db_options(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if check_db_schema():
            try:
                self.v_options = [
                    v.name for v in Vertical.query.options(load_only("name"))
                ]
                self.risk_flags = [f.name for f in RiskFlag.query.all()]
                return
            except Exception as e:
                log.warn(
                    "Could not fetch data admin database options due to error.", error=e
                )

        self.v_options = []
        self.risk_flags = []

    def fetch_admin_emails(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if check_db_schema():
            try:
                # TODO: move to RBAC permissions instead
                admin_cap = Capability.query.filter_by(
                    method="get", object_type="admin"
                ).one()
                self.admin_emails = [
                    u.email
                    for u in User.query.filter(User.otp_secret.isnot(None)).all()
                    if admin_cap in u.capabilities()
                ]
                return
            except Exception as e:
                log.warn(
                    "Could not fetch data admin user emails due to error.", error=e
                )

        self.admin_emails = []

    @expose("/cross_site_login", methods=["POST"])
    def cross_site_login(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        email = request.form.get("user_email")
        ip_address = request.headers.get("X-Real-IP")
        user = User.query.filter_by(email=email).one()
        password = next(
            (
                p
                for p in ("simpleisawesome1*", "foo")
                if self.check_password(user=user, password=p, forwarded_for=ip_address)  # type: ignore[arg-type] # Argument "forwarded_for" to "check_password" of "MavenDataAdminHomeView" has incompatible type "Optional[str]"; expected "str"
            ),
            None,
        )
        # TODO: move to RBAC permissions
        admin_cap = Capability.query.filter_by(method="get", object_type="admin").one()
        assert (
            admin_cap in user.capabilities()
        ), "Chosen user must have the admin capability."
        assert user.otp_secret is not None, "Chosen user must have an otp secret."
        assert password is not None, "Chosen user must have a known default password."
        db.session.commit()
        return self.render(
            "admin/cross_login.html",
            admin_host=self.determine_admin_host(request.host),
            email=user.email,
            password=password,
            totp=OtpAuth(user.otp_secret).totp(),
        )

    def check_password(self, user: User, password: str, forwarded_for: str = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "forwarded_for" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "forwarded_for" (default has type "None", argument has type "str")
        service = authn.AuthenticationService()
        return service.check_password(
            hashed_password=user.password,
            email=user.email,
            plaintext_password=password,
            user_id=user.id,
            forwarded_for=forwarded_for,
        )

    def determine_admin_host(self, data_admin_host):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return f"//{data_admin_host.replace('30007', '30004').replace('8082', '8081')}"

    # --- data admin functionality ---
    @expose("/reset/database", methods=["POST"])
    def reset_database(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not check_environment() or not (
            os.environ.get("ALLOW_DATABASE_RESET") != "false"
        ):
            print("Resetting database is not allowed!")
            sys.exit(2)

        # explicitly call drop tables rather than truncate to ensure clean rebuild
        reset_schemas()
        restore_fixtures()
        flash("Database tables have been reset!")
        return redirect(url_for("data-admin.index"))

    @expose("/publish/spec", methods=["POST"])
    def post_spec(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            spec = request.get_json(force=True)
        except Exception as e:
            return {"created": None, "errors": [f"Problem with request: {e}"]}, 400

        if isinstance(spec, list):
            return {
                "created": None,
                "errors": ["spec should be single json object"],
            }, 400

        created, errors = apply_specs_in_transaction([spec])
        if errors:
            for error_message in errors:
                flash(error_message, "error")

        if not created:
            return {"created": None, "errors": errors}, 500

        # only accepting 1 spec at a time, so only 1 can be created
        created_spec = created[0]
        spec_info = {
            "type": type(created_spec).__name__,
            "id": inspect(created_spec).identity[0],
        }
        return {"created": spec_info, "errors": errors}, 200

    @expose("/upload/spec", methods=["POST"])
    def upload_spec(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        _home = redirect(url_for("data-admin.index"))
        config = configuration.get_data_admin_config()
        specs = []
        if "spec" in request.files:
            f = request.files.get("spec")
            if f.read():  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "read"
                f.seek(0)  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "seek"
                try:
                    specs = json.loads(f.read().decode("utf-8"))  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "read"
                except json.JSONDecodeError as e:
                    flash(f"Not a JSON file: {e}", "error")
                    return _home
                if not isinstance(specs, list):
                    flash("Spec JSON malformed! It expects an array of objects.")
                    return _home

        fixture = request.form.get("fixture_name")
        if fixture and fixture != "None" and not specs:
            try:
                fixture = fixture.replace("__", "/")  # handle subdirectories
                with open(f"{config.fixture_directory}/{fixture}.json") as f:
                    specs = json.loads(f.read())

                if isinstance(specs, dict):
                    # Handle fixture selection with parameters
                    try:
                        parameters = extract_parameters_from_form(request.form, specs)
                        specs = substitute_parameters(specs["objects"], parameters)
                    except KeyError as e:
                        flash(f"Missing required parameter: {e}", "error")
                        return _home
                    except Exception as e:
                        flash(f"Error processing parameters: {e}", "error")
                        return _home

            except Exception as e:
                log_exception(e, service="data-admin")
                flash(f"Error processing fixture: {e}", "error")
                return _home

        raw_fixture_json = request.form.get("raw_fixture")
        if raw_fixture_json and raw_fixture_json != "" and not specs:
            try:
                specs = json.loads(raw_fixture_json)
            except json.JSONDecodeError as e:
                flash(f"Invalid JSON: {e}", "error")
                return _home
            if not isinstance(specs, list):
                flash("Spec JSON malformed! It expects an array of objects.")
                return _home

        created, errors = apply_specs_in_transaction(specs)

        if created:
            flash_message = "Fixture Applied: {}".format(
                ", ".join(
                    "{} ({})".format(t, c)
                    for t, c in sorted(
                        collections.Counter(
                            type(m).__name__ for m in created if m
                        ).items(),
                        key=lambda kv: kv[1],
                    )
                )
            )
            users = [m for m in created if isinstance(m, User)]
            if users:

                def render_user_email(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
                    return f"<li><span>[{user.id}] </span><span class='generated-email' data-password='{user._data_admin_password}'>{user.email}</span></li>"

                emails = "".join(render_user_email(u) for u in users)
                flash_message += f"<br><br>Users created:<ul>{emails}</ul>"
            employees = [m for m in created if isinstance(m, OrganizationEmployee)]
            if employees:
                emails = "".join(
                    [
                        f"<li>DOB: {str(e.date_of_birth)} &nbsp; "
                        f"Email: <span class='generated-email'>{e.email}</span></li>"
                        for e in employees
                    ]
                )
                flash_message += (
                    f"<br><br>Organization employees created:<ul>{emails}</ul>"
                )

            organizations = [m for m in created if isinstance(m, Organization)]
            if organizations:
                organization_names = "".join(
                    [f"<li>{o.name}</li>" for o in organizations]
                )
                flash_message += (
                    f"<br><br>Organizations created:<ul>{organization_names}</ul>"
                )

            flash_message += get_accumulation_report_details(created)

            flash(Markup(flash_message))
        if errors:
            for error_message in errors:
                flash(error_message, "error")
        return _home

    @expose("/actions/run_task", methods=["POST"])
    def run_task(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        task_name = request.form.get("task_name")
        if task_name not in TASK_NAMES:
            flash(f"unknown task name: {task_name}", category="error")
            return redirect(url_for("data-admin.index"))
        path, method = task_name.rsplit(".", 1)
        getattr(importlib.import_module(path), method).delay()
        flash(f"triggered task {task_name} successfully")
        return redirect(url_for("data-admin.index"))

    @expose("/download/<bucket>/<path:filename>")
    def download_file(self, bucket: str, filename: str) -> Any:
        try:
            file_handler = AccumulationFileHandler(
                force_local=Environment.current() == Environment.LOCAL
            )
            content = file_handler.download_file(filename=filename, bucket=bucket)

            return send_file(  # type: ignore[call-arg]
                io.BytesIO(content.encode("utf-8")),
                mimetype="application/octet-stream",
                as_attachment=True,
                download_name=filename.split("/")[-1],
            )
        except Exception as e:
            flash(f"Error downloading file: {str(e)}", "error")
            return redirect(url_for("data-admin.index"))


# --- common view/endpoint functionality ---
def apply_specs_in_transaction(specs: list[dict]) -> tuple[Any, list[str]]:
    # Apply all fixtures in a transaction so that all data admin code can be rolled back on failure
    try:
        created, errors = apply_specs(specs)
    except Exception as e:
        log.exception("apply_specs encountered exception", exc=format_exc())
        db.session.rollback()
        raise e
    else:
        if errors:
            db.session.rollback()
            return [], errors
        else:
            db.session.commit()

    return created, errors


def apply_specs(specs: List) -> Tuple[List, List]:
    created = []
    errors = []

    fixture_spec_names = frozenset(fs.name for fs in FixtureSpecs)
    for spec in specs:
        if spec.get("type") not in fixture_spec_names:
            flash(f"Invalid spec type: {spec.get('type')}", "error")
            break
        try:
            result = FixtureDataMaker(spec).create()
        except Exception as e:
            log_exception(e, service="data-admin")
            error_msg = (
                f"Got error applying fixture:<br><br>"
                f"<pre style='white-space: pre-wrap; background: #f5f5f5; padding: 10px; margin: 10px 0;'>"
                f"{json.dumps(spec, indent=2)}\n\n"
                f"{format_exc()}"
                f"</pre>"
            )
            errors.append(Markup(error_msg))
            break
        if result:
            # Allow multiple records to be created from one spec
            if isinstance(result, list):
                for record in result:
                    created.append(record)
            else:
                created.append(result)

    return created, errors


# --- data manager ---
class FixtureSpecs(enum.Enum):
    # Map a type string to a class
    user = user.UserMaker
    organization = org_maker.OrganizationMaker
    organization_external_id = org_maker.OrganizationExternalIDMaker
    organization_module_extension = org_maker.OrganizationModuleExtensionMaker
    reimbursement_organization_settings = wallet.ReimbursementOrganizationSettingsMaker
    reimbursement_request = wallet.ReimbursementRequestMaker
    reimbursement_wallet = wallet.ReimbursementWalletMaker
    reimbursement_category = wallet.ReimbursementCategoryMaker
    reimbursement_wallet_hdhp_plan = wallet.ReimbursementWalletPlanHDHPMaker
    country_currency_code = wallet.CountryCurrencyCodeMaker
    role = role.RoleMaker
    treatment_procedure = mmb.TreatmentProcedureMaker
    member_bill = mmb.MemberBillMaker
    fee_schedule = mmb.FeeScheduleMaker
    recorded_answer_set = questionnaire_maker.RecordedAnswerSetMaker
    questionnaire = questionnaire_maker.QuestionnaireMaker
    question_set = questionnaire_maker.QuestionSetMaker
    question = questionnaire_maker.QuestionMaker
    answer = questionnaire_maker.AnswerMaker
    fertility_clinic = fertility_clinic_maker.FertilityClinicMaker
    fertility_clinic_location = fertility_clinic_maker.FertilityClinicLocationMaker
    fertility_clinic_allowed_domain = (
        fertility_clinic_maker.FertilityClinicAllowedDomainMaker
    )
    fertility_clinic_user_profile = (
        fertility_clinic_maker.FertilityClinicUserProfileMaker
    )
    text_copy = marketing.TextCopyMaker
    popular_topic = marketing.PopularTopicMaker
    schedule_event = appointments.ScheduleEventMaker
    appointment = appointments.AppointmentMaker
    pooled_calendar_max = appointments.PooledCalendarMaxMaker
    pooled_calendar_min = appointments.PooledCalendarMinMaker
    cas_with_availability = appointments.CareAdvocatesAvailabilityMaker
    forum_post = forum.ForumPostMaker
    invoice = payments.InvoiceMaker
    fee_accounting_entry = payments.FeeAccountingEntryMaker
    message = messaging.MessageMaker
    ca_member_transition_template = (
        care_advocates.CareAdvocateMemberTransitionTemplateMaker
    )
    ca_members = care_advocates.CareAdvocateMembersMaker
    practitioner_track_vgc = provider_matching.PractitionerTrackVGCMaker
    track_change_reason = tracks.TrackChangeReasonMaker
    employer_health_plan = health_plans.EmployerHealthPlanMaker
    member_health_plan = health_plans.MemberHealthPlanMaker
    cost_breakdown = cost_breakdown.CostBreakdownMaker
    payer = payer_maker.PayerMaker
    accumulation_mapping = payer_accumulation.AccumulationMappingMaker
    accumulation_report = payer_accumulation.AccumulationReportMaker


class FixtureDataMaker:
    spec_class = None

    def __init__(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not spec:
            raise ValueError("No spec!")

        # spec is the dictionary of data translated from the JSON
        self.spec = spec

        # raise a KeyError if 'type' not in spec
        _obj_type = self.spec["type"]

        # raise a KeyError if 'type' is bad
        self.maker = FixtureSpecs[_obj_type].value()

    def _set_team_tag(self, team_ns_tag):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        structlog.contextvars.unbind_contextvars("request.team_ns")
        structlog.contextvars.bind_contextvars(**{"request.team_ns": team_ns_tag})

    def _override_team_tag(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        service_ns_tag = data_admin_maker_ns_mapper[self.spec["type"]]
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        self._set_team_tag(team_ns_tag)

    def _reset_team_tag(self) -> None:
        service_ns_tag = "data-admin"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        self._set_team_tag(team_ns_tag)

    def validate(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            self._override_team_tag()
            errors = self.maker.spec_class.validate(spec)
            self._reset_team_tag()
        except Exception as e:
            flash(f"Schema errors: {e}", "error")
            return redirect(url_for("data-admin.index"))
        else:
            if errors:
                flash(f"Schema errors: {errors}", "error")
                return redirect(url_for("data-admin.index"))

    def create(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.maker.spec_class:
            _bad = self.validate(self.spec)
            if _bad:
                return _bad

        self._override_team_tag()
        obj = self.maker.create_object_and_flush(self.spec)
        # Note: tag does not reset if create_object triggers an exception.
        self._reset_team_tag()

        return obj
