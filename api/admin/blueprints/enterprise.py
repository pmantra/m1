from __future__ import annotations

import contextlib
import dataclasses
import datetime
from typing import Any, Literal

import datadog
import ddtrace
import flask
import flask_login
import inflection

import eligibility
from admin.common import _get_referer_path, https_url
from authn.models import user
from authn.models.user import User
from authz.models.roles import ROLES
from common.health_profile.health_profile_service_models import Modifier
from eligibility.e9y import model as e9y_model
from eligibility.utils import verification_utils
from health.services.health_profile_service import HealthProfileService
from models import tracks
from models.enterprise import Organization
from models.tracks import ChangeReason
from storage import connection
from tasks import enterprise
from tracks import service as tracks_svc
from utils import log

URL_PREFIX = "enterprise_setup"

logger = log.logger(__name__)
enterprise_setup = flask.Blueprint(URL_PREFIX, __name__)


@enterprise_setup.route("/", methods=("POST",))
@flask_login.login_required
@ddtrace.tracer.wrap()
def onboard_member():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if "cancel" in flask.request.form:
        return flask.redirect(https_url("admin.enterprise_setup"))
    form: ManualOnboardingForm = parse_form_data(flask.request.form)
    if not form.confirmation:
        flask.flash(
            "Information was not confirmed. Please try again.", category="error"
        )
        return flask.redirect(https_url("admin.enterprise_setup"))
    with handle_manual_onboarding_errors():
        verification, track = do_manual_onboarding(form=form)

        flask.flash(
            f"✅ Associated User {form.user_id} "
            f"to Organization {verification.organization_id} "
            f"(Eligibility Member Versioned {verification.eligibility_member_id})",
            category="success",
        )

        if track:
            flask.flash(
                f"✅ Enrolled User {form.user_id} into "
                f"{inflection.titleize(track.name)} Track (MemberTrack {track.id}).",
                category="success",
            )

    return flask.redirect(https_url("admin.enterprise_setup"))


@enterprise_setup.route("/enroll_track", methods=("POST",))
@flask_login.login_required
@ddtrace.tracer.wrap()
def enroll_track():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if "cancel" in flask.request.form:
        return flask.redirect(https_url("admin.enterprise_setup"))
    form: TrackEnrollmentForm = parse_track_enrollment_form_data(flask.request.form)

    if form.organization_id:
        track_svc = tracks_svc.TrackSelectionService()
        existing_organization_id = (
            track_svc.get_organization_id_for_user_via_active_tracks(
                user_id=form.user_id
            )
        )
        if (
            existing_organization_id is not None
            and existing_organization_id != form.organization_id
        ):
            flask.flash(
                f"❌ Cannot enroll track from organization {form.organization_id}.  "
                f"User {form.user_id} currently has active track with organization: {existing_organization_id} .",
                category="error",
            )
            return flask.redirect(https_url("admin.enterprise_setup"))

    with handle_manual_track_enrollment_errors():
        track = do_manual_track_enrollment(form)

        if track:
            flask.flash(
                f"✅ Enrolled User {form.user_id} into "
                f"{inflection.titleize(track.name)} Track (MemberTrack {track.id}).",
                category="success",
            )

    return flask.redirect(https_url("admin.enterprise_setup"))


@enterprise_setup.route("/msft_setup", methods=("POST",))
@flask_login.login_required
@ddtrace.tracer.wrap()
def enable_microsoft_user():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    redirect_path = _get_referer_path()

    user_id = flask.request.form.get("user_id")
    unique_corp_id = flask.request.form.get("unique_corp_id")
    date_of_birth = flask.request.form.get("date_of_birth")
    is_employee = bool(flask.request.form.get("is_employee"))
    dependent_date_of_birth = flask.request.form.get("dependent_date_of_birth")
    zendesk_id = flask.request.form.get("zendesk_id")
    try:
        current_user_email = flask_login.current_user.email
    except Exception:
        current_user_email = ""

    if not user_id or not unique_corp_id or not date_of_birth:
        flask.flash(
            "User ID, Employee ID and Date of Birth must be provided", category="danger"
        )
        return flask.redirect(redirect_path)

    try:
        parsed_dob = datetime.datetime.strptime(date_of_birth, "%Y-%m-%d")
    except ValueError:
        flask.flash(
            f"Invalid Date of Birth '{date_of_birth}' cannot parsed as 'YYYY-MM-DD'",
            category="danger",
        )
        return flask.redirect(redirect_path)

    try:
        parsed_user_id = int(user_id)
    except ValueError:
        flask.flash(
            f"User ID must be an integer: '{user_id}' cannot parsed as integer",
            category="danger",
        )
        return flask.redirect(redirect_path)

    parsed_dependent_dob = None
    if not is_employee:
        if not dependent_date_of_birth:
            flask.flash(
                "Dependent Date of Birth must be provided in case of dependent",
                category="danger",
            )
            return flask.redirect(redirect_path)
        try:
            parsed_dependent_dob = datetime.datetime.strptime(
                dependent_date_of_birth, "%Y-%m-%d"
            )
        except ValueError:
            flask.flash(
                f"Invalid Dependent Date of Birth '{dependent_date_of_birth}' cannot parsed as 'YYYY-MM-DD'",
                category="danger",
            )
            return flask.redirect(redirect_path)

    svc = eligibility.get_verification_service()
    try:
        organization = Organization.query.filter_by(
            display_name="Microsoft",
            eligibility_type="CLIENT_SPECIFIC",
        ).first()
        if not organization:
            flask.flash("Microsoft Organization not found", category="danger")
            return flask.redirect(redirect_path)
        member = svc.verify_member_client_specific(
            organization_id=organization.id,
            unique_corp_id=unique_corp_id,
            date_of_birth=parsed_dob,
            is_employee=is_employee,
            dependent_date_of_birth=parsed_dependent_dob,
        )

        if not member:
            flask.flash(
                (
                    f"Eligibility record not found: user_id={parsed_user_id}, unique_corp_id={unique_corp_id}, "
                    f"date_of_birth={parsed_dob}, is_employee={is_employee}, "
                    f"dependent_date_of_birth={parsed_dependent_dob}"
                ),
                category="danger",
            )
            return flask.redirect(redirect_path)
        verification = svc.generate_verification_for_user(
            user_id=parsed_user_id,
            verification_type="CLIENT_SPECIFIC",
            organization_id=member.organization_id,
            unique_corp_id=member.unique_corp_id,
            date_of_birth=member.date_of_birth,
            additional_fields={
                "is_employee": True,
                "date_of_birth": parsed_dob.strftime("%Y-%m-%d"),
                "verification_creator": current_user_email or None,
                "zendesk_id": zendesk_id or None,
            },
        )

        if verification_utils.no_oe_creation_enabled():
            logger.info("No OE creation enabled, skipping OE creation", user_id=user_id)
        else:
            # Associate the user to this member record.
            _ = svc.associate_user_id_to_members(
                user_id=user_id,
                members=[member],
                verification_type="CLIENT_SPECIFIC",
            )

        logger.info(
            "Verification created for Microsoft user",
            user_id=parsed_user_id,
            eligibility_member_id=member.id,
            verification_id=verification.verification_id if verification else "",
            organization_id=verification.organization_id if verification else "",
        )

        flask.flash(
            (
                f"Verification(id={verification.verification_id}) created for User(id={verification.user_id} "
                f"via eligibility member(id={member.id})"
            ),
            category="success",
        )
    except Exception as e:
        logger.error(
            f"Failed to create verification for Microsoft user: exception={str(e)}",
            user_id=parsed_user_id,
            exception=e,
        )
        flask.flash(
            (
                f"Failed to create verification for Microsoft user: user_id={parsed_user_id}, "
                f"unique_corp_id={unique_corp_id}, date_of_birth={parsed_dob}, is_employee={is_employee}, "
                f"dependent_date_of_birth={parsed_dependent_dob}, exception={e}"
            ),
            category="danger",
        )
    return flask.redirect(redirect_path)


@contextlib.contextmanager
def handle_manual_onboarding_errors():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        yield
    except ManualVerificationError as e:
        flask.flash(f"❌ Couldn't validate submission:\n{e}", category="error")
    except eligibility.EnterpriseVerificationError as e:
        if e.details:
            flask.flash(
                f"❌ Failed to verify user for target organization:\n{e.details}",
                category="error",
            )
        else:
            flask.flash(
                f"❌ Failed to verify user for target organization:\n{e}",
                category="error",
            )
    except tracks.TrackLifecycleError as e:
        connection.db.session.rollback()
        flask.flash(f"❌ Failed to place user in target track:\n{e}", category="error")
    except Exception as e:
        flask.flash(
            f"😬 Got an unhandled error: {e.__class__.__name__}({str(e)!r})",
            category="danger",
        )


@contextlib.contextmanager
def handle_manual_track_enrollment_errors():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        yield
    except eligibility.EnterpriseVerificationFailedError as e:
        flask.flash(f"❌ User is not an enterprise member:\n{e}", category="error")
    except tracks.TrackLifecycleError as e:
        flask.flash(f"❌ Failed to place user in target track:\n{e}", category="error")
    except Exception as e:
        flask.flash(
            f"😬 Got an unhandled error: {e.__class__.__name__}({str(e)!r})",
            category="danger",
        )


@ddtrace.tracer.wrap()
def do_manual_onboarding(form: ManualOnboardingForm):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    track: tracks.MemberTrack | None = None
    with connection.db.session.no_autoflush:
        verification = do_enterprise_verification(form)
        if form.track_name:
            context = ddtrace.tracer.get_log_correlation_context()
            datadog.statsd.increment(
                "mvn.manual_onboarding_with_track",
                tags=[f"{k}:{v}" for k, v in context.items()],
            )
            track = do_track_selection(form, verification)
        connection.db.session.commit()
        enterprise.enterprise_user_post_setup.delay(form.user_id)

        try:
            if form.life_event_type == "due_date":
                _update_due_date_in_hps(form)
        except Exception as e:
            logger.error(
                "Failed to update due date in HPS during manual onboarding", error=e
            )

    return verification, track


@ddtrace.tracer.wrap()
def do_manual_track_enrollment(form: TrackEnrollmentForm) -> tracks.MemberTrack:
    enterprise_service = eligibility.EnterpriseVerificationService()
    verifications = enterprise_service.get_enterprise_associations(
        user_id=form.user_id, verification_type="lookup"
    )

    if not verifications:
        raise ManualVerificationError(
            f"No verifications found for user_id={form.user_id}."
        )

    # Find the verification that matches the organization_id if specified
    if form.organization_id and len(verifications) > 1:
        verification = next(
            (v for v in verifications if v.organization_id == form.organization_id),
            None,
        )
        if not verification:
            raise ManualVerificationError(
                f"No matching verification found for user_id={form.user_id}, organization_id={form.organization_id}."
            )
    else:
        # Just use the first one if there's only one or no organization_id specified
        verification = verifications[0]

    with connection.db.session.no_autoflush:
        track: tracks.MemberTrack | None = do_track_selection(form, verification)
        connection.db.session.commit()

    try:
        if form.life_event_type == "due_date":
            _update_due_date_in_hps(form)
    except Exception as e:
        logger.error(
            "Failed to update due date in HPS during manual track enrollment", error=e
        )

    return track  # type: ignore[return-value] # Incompatible return value type (got "Optional[MemberTrack]", expected "MemberTrack")


def _find_matching_verification_data(
    user_id: int,
    verification_data: list[e9y_model.EligibilityVerification],
    organization_id: int | None,
) -> e9y_model.EligibilityVerification:
    if not verification_data:
        raise ManualVerificationError(f"No verifications found for user_id={user_id}.")

    if len(verification_data) == 1:
        return verification_data[0]

    if not organization_id:
        raise ManualVerificationError(
            f"Multiple verifications found for user_id={user_id}, please specify organization id."
        )

    matching_verification = next(
        (
            verification
            for verification in verification_data
            if verification.organization_id == organization_id
        ),
        None,
    )

    if not matching_verification:
        raise ManualVerificationError(
            f"No matching verification found for user_id={user_id}, organization_id={organization_id}."
        )

    return matching_verification


@ddtrace.tracer.wrap()
# TODO: Rewrite this when we move to deprecating OE/UOE
def do_enterprise_verification(
    form: ManualOnboardingForm,
) -> e9y_model.EligibilityVerification:
    svc = eligibility.get_verification_service()
    # Utilize E9y records to perform validation

    if form.source == "e9y":
        try:
            current_user_email = flask_login.current_user.email
        except Exception:
            current_user_email = ""

        verification: e9y_model.EligibilityVerification = eligibility.verify_member(
            user_id=form.user_id,
            client_params=dict(
                eligibility_member_id=form.member_id,
                is_employee=form.is_employee,
                verification_type="lookup",
                verification_creator=current_user_email,
                zendesk_id=form.zendesk_id,
            ),
            commit=False,
            svc=svc,
        )

    else:
        raise ManualVerificationError(
            f"Unrecognized association source {form.source!r}."
        )

    return verification


@ddtrace.tracer.wrap()
def do_track_selection(
    form: ManualOnboardingForm | TrackEnrollmentForm,
    verification: e9y_model.EligibilityVerification,
) -> tracks.MemberTrack:
    u = connection.db.session.query(user.User).get(form.user_id)
    hp = u.health_profile
    # Make sure the health profile data is up-to-date.
    if form.life_event_date and form.life_event_type:
        if form.life_event_type == "due_date":
            hp.due_date = form.life_event_date
        elif form.life_event_type == "child_birthday":
            hp.add_a_child(form.life_event_date)

    # TODO: Modify tracks.initiate to accept verification as arg
    # TODO: it currently fetches the user's EligibilityVerification in another call
    track = tracks.initiate(
        user=u,
        track=form.track_name,
        is_employee=form.is_employee,
        modified_by=str(flask_login.current_user.id or ""),
        change_reason=ChangeReason.ADMIN_MANUAL_TRACK_SELECTION,
        eligibility_organization_id=verification.organization_id,
    )
    return track


def parse_form_data(form: dict[str, Any]) -> ManualOnboardingForm:
    user_id = int(form["user_id"])
    member_id = int(form["member_id"])
    source = form["association_source"]
    is_employee = bool(form.get("is_employee"))
    confirmation = bool(form.get("confirmation"))
    track_name = None
    if form["track_name"]:
        track_name = tracks.TrackName(form["track_name"])
    life_event_date, life_event_type = None, None
    if form["life_event_date"] and form["life_event_type"]:
        life_event_date = datetime.datetime.fromisoformat(
            form["life_event_date"]
        ).date()
        life_event_type = form["life_event_type"]
    zendesk_id = form["zendesk_id"]

    return ManualOnboardingForm(
        user_id,
        member_id,
        source,
        is_employee,
        confirmation,
        track_name,
        life_event_date,
        life_event_type,
        zendesk_id,
    )


def parse_track_enrollment_form_data(form: dict[str, Any]) -> TrackEnrollmentForm:
    user_id = int(form["user_id"])
    is_employee = bool(form.get("is_employee"))
    track_name = None
    if form["track_name"]:
        track_name = tracks.TrackName(form["track_name"])
    life_event_date, life_event_type = None, None
    if form["life_event_date"] and form["life_event_type"]:
        life_event_date = datetime.datetime.fromisoformat(
            form["life_event_date"]
        ).date()
        life_event_type = form["life_event_type"]

    organization_id = form.get("organization_id")
    if organization_id:
        organization_id = int(organization_id)

    return TrackEnrollmentForm(
        user_id,
        is_employee,
        track_name,
        life_event_date,
        life_event_type,
        organization_id,
    )


def _update_due_date_in_hps(form: ManualOnboardingForm | TrackEnrollmentForm) -> None:
    member = connection.db.session.query(User).get(form.user_id)
    accessing_user = flask_login.current_user
    health_profile_svc = HealthProfileService(
        user=member, accessing_user=accessing_user
    )
    modifier = Modifier(
        id=accessing_user.id, name=accessing_user.full_name, role=ROLES.staff
    )
    health_profile_svc.update_due_date_in_hps(form.life_event_date, modifier)


@dataclasses.dataclass
class ManualOnboardingForm:
    user_id: int
    member_id: int
    source: AssociationTypeT
    is_employee: bool
    confirmation: bool | None = None
    track_name: tracks.TrackName | None = None
    life_event_date: datetime.date | None = None
    life_event_type: LifeEventTypeT | None = None
    zendesk_id: str | None = None


@dataclasses.dataclass
class TrackEnrollmentForm:
    user_id: int
    is_employee: bool
    track_name: tracks.TrackName | None = None
    life_event_date: datetime.date | None = None
    life_event_type: LifeEventTypeT | None = None
    organization_id: int | None = None


AssociationTypeT = Literal["e9y", "org_emp"]
LifeEventTypeT = Literal["due_date", "child_birthday"]


class ManualVerificationError(Exception):
    ...
