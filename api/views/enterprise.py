from __future__ import annotations

import datetime
import json
from typing import Optional, Tuple

import datadog
import ddtrace
from flask import request
from flask_restful import abort
from httpproblem import problem
from marshmallow import Schema, fields
from marshmallow_v1 import fields as fields_v1
from maven import feature_flags
from sqlalchemy import not_, or_

import eligibility
from authn.models.user import User
from common import stats
from common.services.api import (
    AuthenticatedResource,
    PermissionedUserResource,
    UnauthenticatedResource,
)
from eligibility import (
    EligibilityTestMemberCreationError,
    EnterpriseVerificationService,
)
from eligibility.e9y import model as e9y_model
from eligibility.utils.verification_utils import is_over_eligibility_enabled
from eligibility.web import ClientVerificationParameters
from incentives.services.incentive_organization import get_and_mark_incentive_as_seen
from messaging.services import zendesk
from models import tracks
from models.enterprise import (
    Invite,
    InviteType,
    OnboardingState,
    Organization,
    OrganizationEligibilityField,
    OrganizationEligibilityType,
    OrganizationEmailDomain,
)
from models.programs import ModuleRequiredInformation
from models.tracks import ChangeReason
from phone_support.schemas.phone_support_schema import InboundPhoneNumberInfo
from phone_support.service.phone_support import get_inbound_phone_number
from storage.connection import db
from tasks.enterprise import enterprise_user_post_setup
from tasks.messaging import create_cx_message
from tracks import service as track_svc
from tracks.service.feature import build_tracks_data
from utils import braze
from utils.exceptions import (
    DueDateRequiredError,
    LastChildBirthdayRequiredError,
    ProgramLifecycleError,
)
from utils.lock import prevent_concurrent_requests
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from utils.onboarding_state import update_onboarding_state
from utils.org_search_autocomplete import OrganizationSearchAutocomplete
from utils.service_owner_mapper import service_ns_team_mapper
from views.schemas.common import (
    MavenSchema,
    PhoneNumber,
    TelNumber,
    TelRegion,
    format_json_as_error,
    validate_phone_number,
)
from views.schemas.common_v3 import TRUTHY
from views.schemas.enterprise_v3 import CreateInviteSchemaV3

log = logger(__name__)


def _get_org_info(data) -> Tuple[Optional[int], Optional[str]]:  # type: ignore[no-untyped-def] # Function is missing a return type annotation

    org_name, source_field = next(
        (
            (data[key], key)
            for key in ["organizationFromSearchPage", "externallySourcedOrganization"]
            if data.get(key)
        ),
        (None, None),
    )

    log.info(
        "unsuccessful verification for user",
        source_field=source_field,
        organization_name=org_name,
    )

    if org_name is None:
        return (None, None)

    try:
        org_id = int(str(org_name))
    except (ValueError, TypeError):
        org_id = None

    svc = eligibility.EnterpriseVerificationService()
    if org_id is not None:
        organization = svc.orgs.get_by_organization_id(org_id=org_id)
    elif org_name is not None:
        organization = svc.orgs.get_organization_by_name(name=org_name)
    else:
        organization = None

    organization_id = organization.id if organization else None
    organization_name = (
        organization.display_name or organization.name if organization else org_name
    )

    return organization_id, organization_name


class CensusVerificationEndpoint(AuthenticatedResource):
    @prevent_concurrent_requests(lambda self: f"enterprise_verification:{self.user.id}")
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        _data = request.json if request.is_json else None
        _data["user_id"] = self.user.id

        health_profile = self.user.health_profile
        _data["due_date"] = str(health_profile.due_date)
        _data["last_child_birthday"] = str(health_profile.last_child_birthday)

        organization_id, organization_name = _get_org_info(_data)
        _data["organization"] = {
            "organization_id": organization_id,
            "organization_name": organization_name,
        }

        content = json.dumps(_data)

        log.info("Logging census verification to Zendesk.", user_id=self.user.id)

        # add a public comment
        public_comment_body = (
            f"Enterprise Verification request created for {self.user.id}"
        )
        zendesk.EnterpriseValidationZendeskTicket.comment(
            user=self.user, comment_body=public_comment_body, comment_public=True
        )

        # add a private comment
        zendesk.EnterpriseValidationZendeskTicket.comment(
            user=self.user, comment_body=content
        )
        db.session.commit()

    def _get_org_name_from_external_identity(
        self,
    ) -> eligibility.OrganizationMeta | None:
        svc = eligibility.EnterpriseVerificationService()
        identity, org_meta = svc.orgs.get_organization_by_user_external_identities(
            user_id=self.user.id,
        )
        return org_meta


class CreateEligibilityTestMemberRecordsEndpoint(AuthenticatedResource):
    @prevent_concurrent_requests(
        lambda self: f"create_e9y_test_member_records_for_organization:{self.user.id}"
    )
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        _data = request.json if request.is_json else None
        organization_id = _data.get("organization_id")
        test_member_records = _data.get("test_member_records")
        log.info(
            "Creating test member eligibility records for organization.",
            organization_id=organization_id,
            test_member_records=test_member_records,
        )
        try:
            svc = eligibility.EnterpriseVerificationService()
            return svc.create_test_eligibility_member_records(
                organization_id=organization_id,
                test_member_records=test_member_records,
            )
        except EligibilityTestMemberCreationError as e:
            log.exception(
                "Bad request for test member eligibility record creation",
                message=e,
            )
            return {
                "errors": [problem(400, detail=str(e))],
            }, 400
        except Exception as e:
            log.exception(
                "Error creating test member eligibility records for organization",
                e=e,
                organization_id=organization_id,
                test_member_records=test_member_records,
            )
            return {
                "errors": [problem(500, detail=str(e))],
            }, 500


class ReportVerificationFailureEndpoint(AuthenticatedResource):
    @prevent_concurrent_requests(
        lambda self: f"reported_enterprise_verification_failure:{self.user.id}"
    )
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        _data = request.json if request.is_json else None
        user_id = self.user.id
        log_ = log.bind(user_id=user_id)

        # default verification type to manual if not in request
        verification_type = _data.get("verification_type", "manual")

        # translate verification type to e9y verification type
        if verification_type == "healthplan":
            e9y_verification_type = "multistep"
        else:
            e9y_verification_type = verification_type

        try:
            org_id, org_name = _get_org_info(_data)
            organization_id = org_id if org_id else "null"
            organization_name = org_name if org_name else "null"

            log_.info(
                "verification failed for user",
                user_id=user_id,
                organization_id=organization_id,
                organization_name=organization_name,
                verification_type=e9y_verification_type,
                verification_status="failure",
            )

            stats.increment(
                metric_name="api.eligibility.verification",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[
                    f"organization_id:{organization_id}",
                    f"organization_name:{organization_name}",
                    f"verification_type:{e9y_verification_type}",
                    "verification_status:failure",
                ],
            )

        except Exception as e:
            log.exception(e=e)


class UserOrganizationSetupResource(PermissionedUserResource):
    @prevent_concurrent_requests(
        lambda self, user_id: f"enterprise_verification:{user_id}"
    )
    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)

        args = user_org_setup_post_request(request.json if request.is_json else None)
        provided_track = args.get("verification_reason", "pregnancy")
        client_params = {"verification_type": "lookup"}

        provided_org_id = args.get("organization_id")
        if (
            feature_flags.bool_variation(
                "overeligibility-create-tracks",
                default=False,
            )
            and provided_org_id != None
        ):
            client_params["organization_id"] = str(provided_org_id)

        with eligibility.handle_verification_errors():
            if is_over_eligibility_enabled():
                verification_association_list = eligibility.verify_members(
                    user_id=user_id, client_params=client_params
                )
                verification = verification_association_list[0]

            else:
                verification = eligibility.verify_member(
                    user_id=user_id, client_params=client_params
                )

        try:
            intended_track = tracks.TrackName(provided_track)
        except ValueError:
            log.warn(
                "Could not find track with name matching verification reason.",
                verification_reason=provided_track,
            )
            self._increment_rejection_metric("invalid_track_name", "201")
            return self.setup_rejected_enterprise_user()

        try:
            track = tracks.initiate(
                user=user,
                track=intended_track,
                is_employee=args.get("is_employee"),
                change_reason=ChangeReason.API_ASSOCIATE_USER_WITH_ORG,
                eligibility_organization_id=verification.organization_id,
            )
            update_onboarding_state(user, OnboardingState.ASSESSMENTS)

            if args.get("scheduled_end_date") and feature_flags.bool_variation(
                "enable-configure-track-scheduled-end-date",
                default=False,
            ):
                track.set_scheduled_end_date(args.get("scheduled_end_date"))

            db.session.commit()

            # if member has incentive, mark it as seen
            service_ns = "incentive"
            get_and_mark_incentive_as_seen.delay(
                user_id=user_id,
                track_name=track.name,
                member_track_id=track.id,
                call_from="post_organizations",
                service_ns=service_ns,
                team_ns=service_ns_team_mapper.get(service_ns),
            )

            service_ns_tag = "tracks"
            team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
            enterprise_user_post_setup.delay(
                user.id, service_ns=service_ns_tag, team_ns=team_ns_tag
            )

            track_service = track_svc.TrackSelectionService()
            available_tracks = track_service.get_enrollable_tracks_for_verification(
                verification=verification,
            )
            tracks_data = build_tracks_data(client_tracks=available_tracks)

            return (
                {
                    "can_invite_partner": _check_can_invite_partner(
                        track=track, verification=verification
                    ),
                    "eligible_features": tracks_data,
                },
                201,
            )
        # TODO: [verification]
        #  org logic should be handled during enterprise verification.
        #  NOT track selection...
        except (
            tracks.InvalidOrganizationError,
            tracks.InvalidEmployeeError,
        ) as e:
            log.error(e)
            db.session.rollback()
            update_onboarding_state(user, OnboardingState.FAILED_TRACK_SELECTION)
            self._increment_rejection_metric(type(e).__name__, "400")
            return {"message": str(e)}, 400
        except tracks.MissingEmployeeError as e:
            log.error(e)
            db.session.rollback()
            update_onboarding_state(user, OnboardingState.FAILED_TRACK_SELECTION)
            self._increment_rejection_metric(type(e).__name__, "422")
            return {"message": str(e)}, 422
        except tracks.MissingInformationError as e:
            log.error(e)
            db.session.rollback()
            self._update_verification_ticket(user, e)
            self._increment_rejection_metric(type(e).__name__, "201")
            return self.setup_rejected_enterprise_user()
        except tracks.TrackLifecycleError as e:
            log.error(e)
            db.session.rollback()
            self._increment_rejection_metric(type(e).__name__, "201")
            return self.setup_rejected_enterprise_user()
        # TODO: [Track] Phase 3 - drop this.
        except ProgramLifecycleError as e:
            context = ddtrace.tracer.get_log_correlation_context()
            tags = [f"{k}:{v}" for k, v in context.items()]
            tags.extend(
                (
                    f"error.type:{e.__class__.__name__}",
                    f"error.message:{e}",
                    "category:programs",
                )
            )
            datadog.statsd.increment("mvn.deprecated", tags=tags)
            log.log(e.log_level, e)
            if isinstance(e, (DueDateRequiredError, LastChildBirthdayRequiredError)):
                self._update_verification_ticket(user, e)
            db.session.rollback()
            self._increment_rejection_metric(type(e).__name__, "201")
            return self.setup_rejected_enterprise_user()

    @staticmethod
    def _update_verification_ticket(user, e):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        request_json = request.json if request.is_json else None
        zendesk.EnterpriseValidationZendeskTicket.comment(
            user,
            "User tried to sign up for enterprise program "
            "with the following information:\n\n"
            f"{json.dumps(request_json, indent=4)}\n\n"
            f"Encountered error: {e}.",
        )

    def setup_rejected_enterprise_user(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.debug(
            "Setting up temp for validation-needed enterprise user.",
            user_id=self.user.id,
        )

        copy_name = "cx-admin-validate-enterprise"
        message = create_cx_message(self.user, copy_name=copy_name)
        if message:
            log.debug(
                f"Saved a {copy_name} message for user.",
                message_id=message.id,
                user_id=self.user.id,
            )
        else:
            log.info(
                "No CX message created in enterprise setup for user.",
                user_id=self.user.id,
            )

        self.user.member_profile.pending_enterprise_verification = True
        update_onboarding_state(self.user, OnboardingState.FAILED_TRACK_SELECTION)
        db.session.commit()

        return {"can_invite_partner": False}, 201

    @staticmethod
    def _increment_rejection_metric(reason: str, status_code: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        stats.increment(
            metric_name="track_creation.rejection",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=[f"reason:{reason}", f"status_code:{status_code}"],
        )


def user_org_setup_post_request(request_json: dict) -> dict:
    result = {}
    if not request_json:
        return result
    if "verification_reason" in request_json:
        result["verification_reason"] = str(request_json["verification_reason"])
    if "is_employee" in request_json:
        result["is_employee"] = request_json["is_employee"] in TRUTHY  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bool", target has type "str")
    if "organization_id" in request_json:
        result["organization_id"] = str(request_json["organization_id"])
    if "scheduled_end_date" in request_json:
        result["scheduled_end_date"] = datetime.date.fromisoformat(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "date", target has type "str")
            request_json["scheduled_end_date"]
        )
    return result


def _check_can_invite_partner(
    track: tracks.MemberTrack,
    verification: e9y_model.EligibilityVerification,
) -> bool:
    user = track.user

    # read organization based on flag
    organization = user.organization_v2

    is_org_medical_plan_only = organization.medical_plan_only
    is_beneficiaries_enabled = bool(
        verification.record
        and isinstance(verification.record, dict)
        and verification.record.get("beneficiaries_enabled", False)
    )
    is_employee_only = organization.employee_only

    org_settings_check = (
        track.partner_track_enabled
        and not (is_org_medical_plan_only and not is_beneficiaries_enabled)
        and not is_employee_only
    )

    if not org_settings_check and verification.unique_corp_id is not None:
        # check for 'sibling' org employees that can be invited
        try:
            evs = EnterpriseVerificationService()
            other_eligible_user_ids = evs.get_other_user_ids_in_family(user_id=user.id)
            return bool(other_eligible_user_ids)
        except Exception as e:
            log.error(f"Failed to check partner invitation for user {user.id}: {e}")
            return False

    return True


class CanInvitePartnerResource(PermissionedUserResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)

        organization_id = (
            user.organization_v2.id if user and user.organization_v2 else None
        )

        with eligibility.handle_verification_errors():
            client_params = ClientVerificationParameters(
                verification_type="lookup",
            )
            if organization_id is not None:
                client_params["organization_id"] = organization_id

            verification_associations = eligibility.verify_members(
                user_id=user_id, client_params=client_params
            )

            # if user not already verified, user cannot invite a partner
            if not verification_associations:
                return {"can_invite_partner": False}, 200

            # get the first record - there will only be one
            verification = verification_associations[0]

            can_invite_partner_any_track = any(
                _check_can_invite_partner(
                    track=track,
                    verification=verification,
                )
                for track in user.active_tracks
            )

        return {"can_invite_partner": can_invite_partner_any_track}, 200


class CreateInviteSchema(MavenSchema):
    __validators__ = [validate_phone_number(required=True)]
    id = fields_v1.String()
    email = fields_v1.Email(required=True)
    name = fields_v1.String(required=True)
    date_of_birth = fields_v1.Date(required=True)
    phone_number = PhoneNumber()
    tel_number = TelNumber()
    tel_region = TelRegion()
    due_date = fields_v1.Date()
    last_child_birthday = fields_v1.Date()
    claimed = fields_v1.Boolean()


# Older Invite system
class CreateInviteResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-create-invite-upgrade",
            self.user.esp_id,
            self.user.email,
            default=False,
        )

        svc = track_svc.TrackSelectionService()
        org: int | None = svc.get_organization_for_user(user_id=self.user.id)

        if org is None:
            log.info(
                "Non-enterprise users are not allowed to create invites",
                user_id=self.user.id,
            )
            abort(400, message=f"User {self.user.id} is not an enterprise user.")

        is_enterprise: bool = svc.is_enterprise(user_id=self.user.id)

        if not is_enterprise:
            log.info(
                "User cannot create invite when not in active track",
                user_id=self.user.id,
            )
            abort(400, message=f"User {self.user.id} is not an enterprise user.")

        existing_invite_id = (
            db.session.query(Invite.id)
            .filter(
                Invite.created_by_user == self.user, Invite.type == InviteType.PARTNER
            )
            .scalar()
        )
        if existing_invite_id is not None:
            log.info(
                "User cannot create a second invite.",
                user_id=self.user.id,
                invite_id=existing_invite_id,
            )
            abort(400, message="User has already created an invite.")

        schema = CreateInviteSchemaV3() if experiment_enabled else CreateInviteSchema()

        request_json = request.json if request.is_json else None
        data = (
            schema.load(request_json)  # type: ignore[attr-defined] # "object" has no attribute "load"
            if experiment_enabled
            else schema.load(request_json).data  # type: ignore[attr-defined] # "object" has no attribute "load"
        )
        user = self.user

        hp = user.health_profile
        # TODO: [multitrack] should this endpoint take a track as an argument? What
        #  if the user is in multiple tracks that allow invites? (pregnancy and P&P)
        partner_track = user.current_member_track.partner_track
        required_partner_information = (
            partner_track.required_information if partner_track else []
        )

        due_date = None
        if ModuleRequiredInformation.DUE_DATE in required_partner_information:
            if "due_date" in data:
                due_date = data["due_date"]
            elif hp.due_date:
                due_date = hp.due_date
            else:
                log.warn(
                    "Member cannot create an invite for partner module "
                    "without required information, due date.",
                    user_id=self.user.id,
                )
                abort(
                    400,
                    message="Must provide due date when current user has partner_pregnant module",
                )

        last_child_birthday = None
        if ModuleRequiredInformation.CHILD_BIRTH in required_partner_information:
            if "last_child_birthday" in data:
                last_child_birthday = data["last_child_birthday"]
            elif hp.last_child_birthday:
                last_child_birthday = hp.last_child_birthday
            else:
                log.warn(
                    "Member cannot create an invite for partner module "
                    "without required information, last child birthday.",
                    user_id=self.user.id,
                )
                abort(
                    400,
                    message="Must provide last child birthday when current user has partner_newparent module",
                )

        invite = Invite(
            created_by_user=self.user,
            name=data["name"],
            email=data["email"],
            phone_number=data["phone_number"],
            date_of_birth=data["date_of_birth"],
            due_date=due_date,
            last_child_birthday=last_child_birthday,
            type=InviteType.PARTNER,
        )
        db.session.add(invite)
        db.session.commit()

        braze.track_email_from_invite(
            invite,
            alternate_verification=org.alternate_verification,  # type: ignore[union-attr] # Item "int" of "Optional[int]" has no attribute "alternate_verification" #type: ignore[union-attr] # Item "None" of "Optional[int]" has no attribute "alternate_verification"
            track=user.current_member_track.name,
        )
        response = (
            schema.dump(invite) if experiment_enabled else schema.dump(invite).data  # type: ignore[attr-defined] # "object" has no attribute "dump"
        )
        return response, 201


class GetInviteResource(UnauthenticatedResource):
    def get(self, invite_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        invite: Invite = Invite.query.filter(
            Invite.id == invite_id, Invite.type == InviteType.PARTNER
        ).one_or_none()
        if invite is None:
            abort(404, message="Invalid invite id")
        user: "User" = invite.created_by_user
        mod = user.current_member_track.partner_track
        if not mod:
            abort(400, message="Could not determine partner module")
        return {"name": invite.name, "module": {"name": mod.name}}


class UnclaimedInviteResource(AuthenticatedResource):
    @ddtrace.tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        invite = self._get_invite()
        if invite is None:
            abort(404, message="No unclaimed invite")
        return {
            "invite_id": invite.id,
            "type": invite.type.value,
            "email": invite.email,
        }

    def _get_invite(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            Invite.query.filter(
                Invite.created_by_user_id == self.user.id, Invite.claimed.is_(False)
            )
            .order_by(Invite.created_at.desc())
            .first()
        )


class CreateFilelessInviteSchema(Schema):
    company_email = fields.Email(required=True)
    is_employee = fields.Boolean(required=True)


class CreateFilelessInviteResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log_ = log.bind(user_id=self.user.id)

        schema = CreateFilelessInviteSchema()
        data = schema.load(request.json if request.is_json else {})
        company_email = data["company_email"]
        is_employee = data["is_employee"]

        org_email_domain = OrganizationEmailDomain.for_email(company_email)
        if not org_email_domain:
            log_.info("User requested an invited for a non fileless email domain.")
            return _invite_requested_for_non_fileless_email_domain()

        existing_invite = self._get_existing_invite(is_employee)
        if existing_invite and existing_invite.email == company_email:
            log_.info("An invite with the provided email already exists. Resending.")
            braze.fileless_invite_requested(existing_invite)
            return None, 201
        elif existing_invite and existing_invite.email != company_email:
            log_.info(
                "An invite with a different provided email already exists. Sending invite to new email."
            )
            updated_invite = self._add_or_update_invite(
                is_employee, company_email, existing_invite
            )
            db.session.commit()
            braze.request_and_track_fileless_invite(updated_invite)
            return None, 201

        log_.info("Creating a new fileless invite for user.")
        invite = self._add_or_update_invite(is_employee, company_email)

        update_onboarding_state(
            self.user,
            (
                OnboardingState.FILELESS_INVITED_EMPLOYEE
                if is_employee
                else OnboardingState.FILELESS_INVITED_DEPENDENT
            ),
        )
        log_.info("Updating user state to invited.")

        db.session.commit()

        braze.request_and_track_fileless_invite(invite)

        return None, 201

    def _get_existing_invite(self, is_employee: bool) -> Optional[Invite]:
        current_time = datetime.datetime.utcnow()
        return (
            Invite.query.filter(
                Invite.created_by_user_id == self.user.id,
                Invite.type
                == (
                    InviteType.FILELESS_EMPLOYEE
                    if is_employee
                    else InviteType.FILELESS_DEPENDENT
                ),
                not_(Invite.claimed),
                or_(Invite.expires_at.is_(None), Invite.expires_at > current_time),
            )
            .order_by(Invite.created_at.desc())
            .first()
        )

    def _add_or_update_invite(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, is_employee: bool, company_email: str, existing_invite: Invite = None  # type: ignore[assignment] # Incompatible default for argument "existing_invite" (default has type "None", argument has type "Invite")
    ):
        invite_type = (
            InviteType.FILELESS_EMPLOYEE
            if is_employee
            else InviteType.FILELESS_DEPENDENT
        )
        if existing_invite:
            existing_invite.email = company_email
            existing_invite.type = invite_type
            return existing_invite

        invite = Invite(
            type=invite_type,
            created_by_user=self.user,
            email=company_email,
            name=self.user.first_name,
            claimed=False,
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
        )
        db.session.add(invite)
        return invite


def _invite_requested_for_non_fileless_email_domain():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 403
    code = "INVALID_EMAIL_DOMAIN"
    message = "Provided email domain invalid for fileless invites."
    return format_json_as_error(status, code, message)


class ClaimFilelessInviteSchema(Schema):
    invite_id = fields.String(required=True)


class ClaimFilelessInviteResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = ClaimFilelessInviteSchema()
        data = schema.load(request.json if request.is_json else {})
        invite_id = data["invite_id"]

        log_ = log.bind(user_id=self.user.id, invite_id=invite_id)

        invite = Invite.query.filter(
            Invite.id == invite_id,
            Invite.type.in_(
                (InviteType.FILELESS_EMPLOYEE, InviteType.FILELESS_DEPENDENT)
            ),
        ).one_or_none()

        if not invite:
            return _fileless_invite_invalid()
        if invite.expires_at and invite.expires_at < datetime.datetime.utcnow():
            return _fileless_invite_expired()
        if invite.claimed:
            return _fileless_invite_already_claimed()

        log_.info("Claiming invite for user.")
        svc = eligibility.get_verification_service()

        date_of_birth = self.user.health_profile.birthday
        if not date_of_birth:
            return _fileless_invite_invalid_date_of_birth()

        try:
            verification: e9y_model.EligibilityVerification = (
                svc.create_fileless_verification(
                    user_id=self.user.id,
                    first_name=self.user.first_name,
                    last_name=self.user.last_name,
                    date_of_birth=date_of_birth,
                    company_email=invite.email,
                    is_dependent=invite.type == InviteType.FILELESS_DEPENDENT,
                )
            )
        except Exception as e:
            log.exception(
                "Exception encountered while trying to create verification",
                verification_type="fileless",
                user_id=self.user.id,
                error=e,
            )
        else:
            log.info(
                "Fileless verification successfully created",
                org_id=verification.organization_id,
                user_id=verification.user_id,
            )

        with db.session.no_autoflush:
            with eligibility.handle_verification_errors():
                svc = eligibility.get_verification_service()
                emp = svc.get_fileless_enterprise_association(
                    user_id=self.user.id,
                    first_name=self.user.first_name,
                    last_name=self.user.last_name,
                    date_of_birth=self.user.health_profile.birthday,
                    company_email=invite.email,
                    is_dependent=invite.type == InviteType.FILELESS_DEPENDENT,
                )

            log_ = log_.bind(organization_employee_id=emp.id)
            log_.info("Organization employee linked to user.")
            self.user.onboarding_state.state = OnboardingState.TRACK_SELECTION
            invite.claimed = True

            log.info(
                "updating verification success metric on datadog",
                user_id=self.user.id,
                organization_id=emp.organization_id,
                organization_name=emp.organization.name,
                verification_type="fileless",
                verification_status="success",
            )

            # replace this custom metric with log-based metric
            stats.increment(
                metric_name="api.eligibility.verification",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[
                    f"organization_id:{emp.organization_id}",
                    f"organization_name:{emp.organization.name}",
                    "verification_type:fileless",
                    "verification_status:success",
                ],
            )

        db.session.commit()

        braze.track_fileless_email_from_invite(invite)

        return None, 204


def _fileless_invite_invalid():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 404
    code = "FILELESS_INVITE_INVALID"
    message = "Given fileless invite ID is invalid."
    return format_json_as_error(status, code, message)


def _fileless_invite_expired():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 410
    code = "FILELESS_INVITE_EXPIRED"
    message = "Fileless invite has expired"
    return format_json_as_error(status, code, message)


def _fileless_invite_already_claimed():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 400
    code = "FILELESS_INVITE_ALREADY_CLAIMED"
    message = "Fileless invite already claimed."
    return format_json_as_error(status, code, message)


def _fileless_invite_invalid_date_of_birth():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 400
    code = "FILELESS_INVITE_INVALID_DATE_OF_BIRTH"
    message = "Fileless invite invalid date of birth."
    return format_json_as_error(status, code, message)


class OrganizationSearchAutocompleteResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Provide an autocomplete feature for users looking up the organization in the onboarding flow.

        A query param of `name` will take an organization name as input and the endpoint will return
        a list of dictionaries containing the ID and organization name
        for each organization name that matches the input.
        """
        if query := request.args.get("name"):
            if not query or len(query) < 2:
                return {
                    "errors": [
                        problem(
                            400, detail="Must include query of at least two characters"
                        )
                    ]
                }, 400

        else:
            return {
                "errors": [
                    problem(400, detail="Required query parameter 'name' not found")
                ]
            }, 400

        search = OrganizationSearchAutocomplete()
        results = search.get_autocomplete_results(query.lower())

        return {"results": results}, 200


class OrganizationEligibilityResource(UnauthenticatedResource):
    def get(self, organization_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Look up an organization and return its corresponding eligibility type
        along with information about other fields the frontend needs to direct
        the user to the appropriate eligibility flow.
        :param organization_id: the Organization ID
        :return: eligibility and organization information
        """
        org = Organization.query.get(organization_id)

        if not org:
            return {
                "eligibility": {"type": OrganizationEligibilityType.UNKNOWN.value},
                "errors": [problem(400, detail="Invalid organization")],
            }, 400

        return format_eligibility_info(org), 200


class OrganizationsEligibilityResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Return organizations' eligibility type
        along with information about other fields the frontend needs to direct
        the user to the appropriate eligibility flow for that organization.
        :return: eligibility and organization information
        """

        # Look for a specific organization
        if org_name := request.args.get("name"):
            org = (
                Organization.query.filter_by(display_name=org_name).first()
                or Organization.query.filter_by(name=org_name).first()
            )

            if not org:
                return {
                    "eligibility": {"type": OrganizationEligibilityType.UNKNOWN.value},
                    "errors": [problem(400, detail="Invalid organization")],
                }, 400

            return format_eligibility_info(org), 200

        # Look at all organizations
        else:
            orgs = Organization.query.all()
            data = [format_eligibility_info(org) for org in orgs]

            return data, 200


class UserOrganizationInBoundPhoneNumberResource(PermissionedUserResource):
    def get(self, organization_id: int) -> tuple[dict[str, str], int]:
        """
        Given a member's organization id and user_id, return their organization's phone number to enable phone support.
        """
        user_id = None
        if user_id_param := request.args.get("user_id"):
            user_id = int(user_id_param)
        try:
            inbound_phone_number_info = InboundPhoneNumberInfo(
                org_id=organization_id, user_id=user_id, user=self.user
            )
        except (ValueError, AttributeError) as e:
            return {"message": str(e)}, 400
        log.info(
            "Retrieving organization's inbound phone number for member",
            org_id=organization_id,
            user_id=inbound_phone_number_info.user_id,
        )
        inbound_phone_number = get_inbound_phone_number(
            user=inbound_phone_number_info.user
        )
        if inbound_phone_number:
            return {
                "user_id": inbound_phone_number_info.user_id,
                "organization_id": inbound_phone_number_info.org_id,
                "inbound_phone_number": inbound_phone_number,
            }, 200
        log.info(
            "No existing inbound phone number for user",
            org_id=inbound_phone_number_info.org_id,
            user_id=inbound_phone_number_info.user_id,
        )
        return {}, 204


def format_eligibility_info(organization: Organization) -> dict:
    """
    Get the eligibility and organization info for the given Organization.
    :param organization: the Organization to use
    :return: a dictionary containing the eligibility information for the organization
    as well as the name, ID, and icon/logo for the organization.
    """
    eligibility_type = organization.eligibility_type
    eligibility_info = {
        "type": eligibility_type.value,  # type: ignore[attr-defined] # "str" has no attribute "value"
    }

    if eligibility_type == OrganizationEligibilityType.CLIENT_SPECIFIC:
        additional_eligibility_info = {
            "code": "CLIENT_SPECIFIC_ELIGIBILITY_ENABLED",
            "fields": get_organization_eligibility_fields(organization),
        }
        eligibility_info = {**eligibility_info, **additional_eligibility_info}

    elif eligibility_type == OrganizationEligibilityType.FILELESS:
        additional_eligibility_info = {
            "code": "FILELESS_ELIGIBILITY_ENABLED",
        }
        eligibility_info = {**eligibility_info, **additional_eligibility_info}

    return {
        "eligibility": eligibility_info,
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "marketing_name": organization.marketing_name,
            "logo": organization.icon,
        },
    }


def get_organization_eligibility_fields(
    organization: Organization,
) -> list[dict[str, str]]:
    """
    Get any OrganizationEligibilityField info for the given Organization.
    :param organization: the Organization to use
    :return: a list of dictionaries containing the OrganizationEligibilityField.name
    and OrganizationEligibilityField.label for each OrganizationEligibilityField
    related to the given Organization.
    """
    org_eligibility_fields = (
        db.session.query(
            OrganizationEligibilityField.name.label("name"),
            OrganizationEligibilityField.label.label("label"),
        )
        .outerjoin(Organization)
        .filter(OrganizationEligibilityField.organization_id == organization.id)
        .all()
    )

    return [
        {"name": org_eligibility_field.name, "label": org_eligibility_field.label}
        for org_eligibility_field in org_eligibility_fields
    ]
