from __future__ import annotations

from datetime import date, datetime
from urllib.parse import quote

import ddtrace
import magic
from dateutil.relativedelta import relativedelta
from ddtrace import tracer
from flask import request
from flask_restful import abort
from marshmallow import ValidationError as ValidationErrorV3
from marshmallow import fields as ma_fields
from marshmallow_v1 import UnmarshallingError, ValidationError, fields
from maven import feature_flags
from sqlalchemy import and_, asc, desc, exc, func

from appointments.models.appointment import Appointment
from appointments.models.appointment_meta_data import AppointmentMetaData
from appointments.models.constants import PRIVACY_CHOICES
from appointments.models.schedule import Schedule
from appointments.schemas.appointments import PractitionerNotesAppointmentSchema
from appointments.schemas.appointments_v3 import PractitionerNotesAppointmentSchemaV3
from appointments.services.common import deobfuscate_appointment_id, get_platform
from appointments.utils.appointment_utils import enable_get_my_patients_marshmallow_v3
from authn.models.user import User
from authn.resources.user import UserGetArgs, UsersSchema, UsersSchemaV3
from authz.models.roles import ROLES, Role
from authz.services.permission import only_specialists_and_me_or_only_me
from common import stats
from common.services import ratelimiting
from common.services.api import (
    AuthenticatedResource,
    PermissionedCareTeamResource,
    PermissionedUserResource,
)
from geography.repository import CountryRepository, SubdivisionRepository
from l10n.db_strings.schema import TranslatedV2VerticalSchemaV3
from models.enterprise import OnboardingState, UserAsset, UserAssetState
from models.forum import Post, post_categories
from models.products import Product
from models.profiles import (
    CareTeamTypes,
    Category,
    CategoryVersion,
    PractitionerProfile,
    category_versions,
    practitioner_verticals,
)
from models.questionnaires import (
    ASYNC_ENCOUNTER_QUESTIONNAIRE_OID,
    COACHING_NOTES_COACHING_PROVIDERS_OID,
    Questionnaire,
    RecordedAnswer,
    RecordedAnswerSet,
    questionnaire_vertical,
)
from models.verticals_and_specialties import Vertical
from providers.service.provider import ProviderService
from storage.connection import db
from tasks.braze import sync_practitioner_with_braze
from tasks.forum import invalidate_posts_cache_for_user
from tasks.notifications import notify_birth_plan_pdf_availability
from utils import launchdarkly
from utils.launchdarkly import user_context
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from utils.onboarding_state import update_onboarding_state
from utils.service_owner_mapper import service_ns_team_mapper
from views.schemas.base import (
    BooleanWithDefault,
    DataTimeWithDefaultV3,
    IntegerWithDefaultV3,
    ListWithDefaultV3,
    MemberProfileSchemaV3,
    NestedWithDefaultV3,
    PaginableArgsSchemaV3,
    PaginableOutputSchemaV3,
    SchemaV3,
    StringWithDefaultV3,
    UserSchemaV3,
    V2VerticalGetSchemaV3,
    V2VerticalSchemaV3,
)
from views.schemas.common import (
    CSVStringField,
    MavenSchema,
    MemberProfileSchema,
    PaginableArgsSchema,
    PaginableOutputSchema,
    PractitionerProfileSchema,
    UserMeSchema,
)
from views.schemas.common import UserSchema as UserSchemaV1
from wallet.schemas.constants import WalletApprovalStatus
from wallet.tasks.alegeus import remove_member_number
from wallet.utils.eligible_wallets import get_eligible_wallet_org_settings

log = logger(__name__)

DEFAULT_LIMIT = 20
DEFAULT_OFFSET = 0
DEFAULT_ORDER_DIRECTION = "desc"

MeSchemaFieldGroups = {
    "agreements": ["pending_agreements", "all_pending_agreements"],
    "care_coordinators": ["care_coordinators"],
    "deprecated": [
        "country",
        "has_available_tracks",
        "subscription_plans",
        "test_group",
        "use_alegeus_for_reimbursements",
    ],
    "flags": ["flags"],
    "mfa": ["mfa_enforcement_info"],
    "organization": ["organization"],
    "profiles": ["profiles"],
    "tracks": [
        "active_tracks",
        "inactive_tracks",
        "scheduled_tracks",
    ],
    "unclaimed_invite": [
        "unclaimed_invite",
    ],
    "user": [
        "id",
        "email",
        "first_name",
        "middle_name",
        "last_name",
        "name",
        "username",
        "date_of_birth",
        "role",
        "onboarding_state",
        "avatar_url",
        "image_url",
        "image_id",
        "esp_id",
        "encoded_id",
        "mfa_state",
        "sms_phone_number",
        "bright_jwt",
    ],
    "wallet": ["wallet"],
}


def _resolve_me_fields(exclude: list):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return tuple(
        [
            item
            for sublist in [
                MeSchemaFieldGroups[e] for e in exclude if e in MeSchemaFieldGroups
            ]
            for item in sublist
        ]
    )


class MeResource(PermissionedUserResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        platform = get_platform(request.user_agent.string)
        include_only = ",".join(request.args.getlist("include_only")) or None
        exclude = ",".join(request.args.getlist("exclude")) or None
        with stats.timed(
            metric_name="api.enrollments.me",
            pod_name=stats.PodNames.ENROLLMENTS,
            use_ms=True,
            tags=[
                f"platform:{platform}",
                f"include_only:{include_only}",
                f"exclude:{exclude}",
            ],
        ):
            return self._get()

    def _get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = UserGetArgs()
        args = schema.load(request.args).data

        include_only = request.args.getlist("include_only")
        exclude = request.args.getlist("exclude")
        include_care_team = True
        include_wallet = True

        if include_only:
            included = _resolve_me_fields(include_only)
            include_care_team = "care_coordinators" in included
            include_wallet = "wallet" in included
            schema = UserMeSchema(only=included)
        elif exclude:
            excluded = _resolve_me_fields(exclude)
            include_care_team = "care_coordinators" not in excluded
            include_wallet = "wallet" not in excluded
            schema = UserMeSchema(exclude=("created_at",) + excluded)
        else:
            schema = UserMeSchema(exclude=("created_at",))

        schema.context["user"] = self.user
        schema.context["include_esp_id"] = True
        schema.context["include_profile"] = args["include_profile"]

        if include_care_team:
            self._populate_care_team_context(schema)
        if include_wallet:
            self._populate_wallet_context(schema)

        return schema.dump(self.user).data

    @tracer.wrap()
    def _populate_care_team_context(self, schema: UserGetArgs):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema.context["care_team"] = {
            ct.id: [CareTeamTypes.CARE_COORDINATOR.value]
            for ct in self.user.care_coordinators
        }

    @tracer.wrap()
    def _populate_wallet_context(self, schema: UserGetArgs):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.user.is_enterprise:
            wallet_approval = WalletApprovalStatus.from_user(self.user)
            # get eligible wallets:
            # org settings active, user employed by org, wallet not activated yet
            reimbursement_settings = get_eligible_wallet_org_settings(self.user.id)
            schema.context["organization_settings"] = [
                {
                    "id": str(settings.id),
                    "wallet_id": None,
                    # Need the organization_id to check the flag for
                    # whether we will use the automated wallet survey workflow.
                    "organization_id": str(settings.organization_id),
                    "survey_url": (
                        settings.survey_url
                        if wallet_approval == WalletApprovalStatus.PENDING
                        else None
                    ),
                    "benefit_overview_resource": settings.benefit_overview_resource
                    and {
                        "title": settings.benefit_overview_resource.title,
                        "url": settings.benefit_overview_resource.custom_url,
                    },
                    "benefit_faq_resource": {
                        "title": settings.benefit_faq_resource.title,
                        "url": settings.benefit_faq_resource.content_url,
                    },
                }
                for settings in reimbursement_settings
            ]


class PractitionersSchemaV3(PaginableOutputSchemaV3):
    data = ma_fields.Method(serialize="get_data")  # type: ignore[assignment]

    def get_data(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = UserSchemaV3(
            context={
                "include_profile": True,
                "care_team": self.context.get("care_team"),
                "user": self.context.get("user"),
                # NB: this is additionally gated by the release-care-discovery-provider-field-localization flag
                # at the schema level
                "localize_provider_fields": self.context.get(
                    "localize_provider_fields"
                ),
            },
            exclude=("created_at",),
        )
        return schema.dump(obj["data"], many=True)


class PractitionersSchema(PaginableOutputSchema):
    data = fields.Method("get_data")  # type: ignore[assignment]

    def get_data(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = UserSchemaV1(
            context={
                "include_profile": True,
                "care_team": context.get("care_team"),
                "user": context.get("user"),
            },
            exclude=("created_at",),
        )
        return schema.dump(obj["data"], many=True).data


def validate_practitioner_order(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if value == "next_availability":
        return value
    else:
        raise ValidationError("Invalid practitioner order_by!")


class PractitionersResource(AuthenticatedResource):
    @property
    def launchdarkly_context(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return launchdarkly.marshmallow_context(self.user.esp_id, self.user.email)

    @ratelimiting.ratelimited(attempts=15, cooldown=60)
    @tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.init_timer()

        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            user_context(self.user),
            default=False,
        )

        from views.schemas.common_v3 import PractitionerGetSchema

        schema = PractitionerGetSchema()
        args = schema.load(request.args)

        log.info("Loading practitioners from DB")
        all_practitioners, total = self._load_from_db(args)

        data = {
            "data": all_practitioners,
            "pagination": {
                "total": total,
                "limit": args.setdefault("limit", DEFAULT_LIMIT),
                "offset": args.setdefault("offset", DEFAULT_OFFSET),
                "order_direction": args.setdefault(
                    "order_direction", DEFAULT_ORDER_DIRECTION
                ),
            },
        }
        self.timer("db_data_time")
        output_schema = PractitionersSchemaV3(
            context={
                "include_profile": True,
                "user": self.user,
                "care_team": {
                    ct.id: [CareTeamTypes.CARE_COORDINATOR.value]
                    for ct in self.user.care_coordinators
                },
                "localize_provider_fields": l10n_flag,
            }
        )

        user_ids = args.get("user_ids")
        platform = get_platform(request.user_agent.string)
        if user_ids and len(user_ids) == 1:
            # Increment stats metrics
            stats.increment(
                metric_name="api.views.profiles",
                tags=[
                    f"platform:{platform}",
                    "variant:original",
                    "event:provider_profile",
                ],
                pod_name=stats.PodNames.CARE_DISCOVERY,
            )
        else:
            # Increment stats metrics
            stats.increment(
                metric_name="api.views.profiles",
                tags=[
                    f"platform:{platform}",
                    "variant:original",
                    "event:provider_search_results",
                ],
                pod_name=stats.PodNames.CARE_DISCOVERY,
            )

        data = output_schema.dump(data)
        self.timer("schema_time")

        data["data"] = only_specialists_and_me_or_only_me(self.user, data["data"])
        self.timer("clean_data_time")
        self.timer("finish_time")
        return data

    def _load_from_db(self, kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        kwargs["current_user"] = self.user
        return ProviderService().search(**kwargs)


class CareTeamPOSTArgs(MavenSchema):
    practitioner_ids = fields.List(fields.Integer(), required=True)


class CareTeamGETArgs(PaginableArgsSchema):
    types = CSVStringField(required=False)


class CareTeamsResource(AuthenticatedResource):
    @classmethod
    def _ct_type_precedence(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return [
            CareTeamTypes.FREE_FOREVER_CODE.value,
            CareTeamTypes.MESSAGE.value,
            CareTeamTypes.APPOINTMENT.value,
            CareTeamTypes.QUIZ.value,
            CareTeamTypes.CARE_COORDINATOR.value,
        ]

    @property
    def launchdarkly_context(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return launchdarkly.marshmallow_context(self.user.esp_id, self.user.email)

    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.user.id == user_id:
            abort(403, message="You can only view your own care team!")

        args = CareTeamGETArgs().load(request.args).data
        selected_types = args.get("types")

        practitioners = []
        care_team_types = {}
        precedence = self._ct_type_precedence()
        for pa in sorted(
            self.user.practitioner_associations,
            # avoid exceptions when pa.created_at is None
            key=lambda pa: (pa.created_at or datetime.min),
            reverse=True,
        ):
            # ct type with higher precedence wins
            if care_team_types.get(pa.practitioner_id):
                existing = care_team_types[pa.practitioner_id][0]
                if precedence.index(pa.type.value) > precedence.index(existing):
                    care_team_types[pa.practitioner_id] = [pa.type.value]
            else:
                care_team_types[pa.practitioner_id] = [pa.type.value]

            # not adding dupe users
            if pa.practitioner_profile.user not in practitioners:
                if selected_types:
                    if pa.type.value in selected_types:
                        practitioners.append(pa.practitioner_profile.user)
                else:
                    practitioners.append(pa.practitioner_profile.user)

        l10n_flag = feature_flags.bool_variation(
            "release-care-discovery-provider-field-localization",
            user_context(self.user),
            default=False,
        )

        total = len(practitioners)
        offset = args["offset"]
        limit = args["limit"]

        schema_cls = PractitionersSchemaV3
        schema = schema_cls(
            context={
                "include_profile": True,
                "care_team": care_team_types,
                "user": self.user,
                "localize_provider_fields": l10n_flag,
            }
        )

        return_dict = {
            "data": practitioners[offset : offset + limit],
            "pagination": {"total": total, "offset": offset, "limit": limit},
        }

        return schema.dump(return_dict)


class CareTeamResource(AuthenticatedResource):
    def delete(self, user_id, practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = User.query.get(user_id)
        if user is None:
            abort(404, message="Member does not exist!")
        if self.user.id != user_id:
            abort(403, message="You can only delete your own care team!")

        profile = PractitionerProfile.query.get(practitioner_id)
        if profile is None:
            abort(404, message="Practitioner does not exist!")
        if profile not in self.user.care_team:
            abort(404, message="Practitioner does not exist in your care team!")

        user.care_team.remove(profile)
        db.session.add(user)
        db.session.commit()

        return "", 204


class PatientSearchGetSchema(PaginableArgsSchema):
    first_name = fields.String(required=False)
    last_name = fields.String(required=False)


class MyPatientsResource(AuthenticatedResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.user.is_practitioner:
            abort(403, message="You are not a practitioner!")
        if self.user.id != user_id:
            abort(403, message="You can only view your own patients!")
        with ddtrace.tracer.trace(name=f"{__name__}.db_query"):
            results = (
                db.session.query(Schedule.user_id)
                .join(Appointment)
                .join(Product)
                .filter(
                    Product.user_id == user_id,
                    Appointment.privacy != PRIVACY_CHOICES.anonymous,
                )
                .all()
            )
            user_ids = {r[0] for r in results}

            members = (
                db.session.query(User)
                .filter(User.id.in_(user_ids))
                .order_by(User.first_name.asc())
            )

            args = PatientSearchGetSchema().load(request.args).data
            if args.get("first_name"):
                members = members.filter(User.first_name.contains(args["first_name"]))
            if args.get("last_name"):
                members = members.filter(User.last_name.contains(args["last_name"]))

            users = members.limit(args["limit"]).offset(args["offset"]).all()
            total_users = members.count()

        with ddtrace.tracer.trace(name=f"{__name__}.serialize_dict"):
            schema_cls = (
                UsersSchemaV3
                if enable_get_my_patients_marshmallow_v3(self.user)
                else UsersSchema
            )
            schema = schema_cls(
                context={
                    "include_profile": True,
                    "include_country_info": True,
                    "user": self.user,
                }
            )
            return_dict = {
                "data": users,
                "pagination": {
                    "total": total_users,
                    "offset": args["offset"],
                    "limit": args["limit"],
                },
            }

            return (
                schema.dump(return_dict)
                if enable_get_my_patients_marshmallow_v3(self.user)
                else schema.dump(return_dict).data
            )


class PractitionerProfileResource(PermissionedUserResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_abort(user_id)

        schema = PractitionerProfileSchema()
        return schema.dump(user.practitioner_profile).data

    def put(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_abort(user_id)

        schema = PractitionerProfileSchema(exclude=("verticals", "certified_states"))
        try:
            args = schema.load(request.json if request.is_json else None).data
        except UnmarshallingError as ue:
            abort(400, message=str(ue))

        countries = CountryRepository(session=db.session)
        subdivisions = SubdivisionRepository()

        profile = user.practitioner_profile
        if args.get("categories"):
            profile.categories = args["categories"]
        if args.get("certifications") is not None:
            profile.certifications = args["certifications"]
        if args.get("languages") is not None:
            profile.languages = args["languages"]
        if args.get("phone_number") not in (None, ""):
            profile.phone_number = args["phone_number"]
        if args.get("years_experience") is not None:
            profile.experience_started = date.today() - relativedelta(
                years=int(args["years_experience"])
            )
        if args.get("cancellation_policy") is not None:
            profile.default_cancellation_policy = args["cancellation_policy"]
        if args.get("education") is not None:
            profile.education = args["education"]
        if args.get("work_experience") is not None:
            profile.work_experience = args["work_experience"]
        if args.get("awards") is not None:
            profile.awards = args["awards"]
        if args.get("subdivision_code") is not None:
            profile.subdivision_code = args["subdivision_code"]
            if country := countries.get_by_subdivision_code(
                subdivision_code=profile.subdivision_code
            ):
                profile.country_code = country.alpha_2
        if args.get("country") is not None:
            if country := countries.get_by_name(name=args["country"]):
                profile.country_code = country.alpha_2
        if args.get("state") is not None:
            profile.state = args["state"]
            if country_code := profile.user.country_code or "US":
                if subdivision := subdivisions.get_by_country_code_and_state(
                    country_code=country_code,
                    state=args["state"].abbreviation,
                ):
                    profile.subdivision_code = subdivision.code
                    profile.country_code = subdivision.country_code
        if args.get("agreements"):
            agreements = args["agreements"]
            if agreements.get("subscription") != profile.agreed_service_agreement:
                profile.agreed_service_agreement = agreements["subscription"]
        if args.get("address") is not None:
            profile.add_or_update_address(args["address"])
        if args.get("messaging_enabled") is not None:
            profile.messaging_enabled = args["messaging_enabled"]
            if profile.response_time is None:
                profile.response_time = 24  # default response time is 24hrs.
        if args.get("response_time") is not None:
            if not profile.messaging_enabled:
                abort(403, message="You must turn on messaging capability first!")
            profile.response_time = args["response_time"]

        db.session.add(profile)
        db.session.commit()

        service_ns_tag = "practitioner_profile"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)

        invalidate_posts_cache_for_user.delay(
            user.id,
            service_ns="community_forum",
            team_ns=service_ns_team_mapper.get("community_forum"),
        )
        sync_practitioner_with_braze.delay(
            user.id, service_ns=service_ns_tag, team_ns=team_ns_tag
        )

        schema = PractitionerProfileSchema()
        return schema.dump(profile).data

    def _user_or_abort(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)

        if user.practitioner_profile:
            return user
        else:
            abort(403, message=f"User {user_id} not a practitioner!")


class CurrentUserPractitionerProfileResource(AuthenticatedResource):
    """
    Return the current user's PractitionerProfile, if they have one
    """

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not self.user.practitioner_profile:
            return {}, 200

        schema = PractitionerProfileSchema()
        return schema.dump(self.user.practitioner_profile).data


class PractitionerNotesSchema(PaginableOutputSchema):
    data = fields.Nested(  # type: ignore[assignment]
        PractitionerNotesAppointmentSchema,
        many=True,
    )


class PractitionerNotesSchemaV3(PaginableOutputSchemaV3):
    data = NestedWithDefaultV3(  # type: ignore[assignment]
        PractitionerNotesAppointmentSchemaV3, many=True, default=[]
    )


class V2PractitionerNotesArgsSchema(PaginableArgsSchema):
    all_appointments = fields.Boolean(default=False, required=False)
    scheduled_start = fields.DateTime()
    scheduled_end = fields.DateTime()
    my_encounters = fields.Boolean(default=False, required=False)
    completed_appointments = fields.Boolean(default=False, required=False)
    verticals = fields.List(fields.String())


class V2PractitionerNotesArgsSchemaV3(PaginableArgsSchemaV3):
    all_appointments = BooleanWithDefault(default=False, required=False)
    scheduled_start = DataTimeWithDefaultV3()
    scheduled_end = DataTimeWithDefaultV3()
    my_encounters = BooleanWithDefault(default=False, required=False)
    completed_appointments = BooleanWithDefault(default=False, required=False)
    verticals = ListWithDefaultV3(StringWithDefaultV3, default=[])


class PractitionerNotesArgsSchema(PaginableArgsSchema):
    all_appointments = fields.Boolean(default=False, required=False)
    scheduled_start = fields.DateTime()
    scheduled_end = fields.DateTime()
    my_appointments = fields.Boolean(default=False, required=False)
    completed_appointments = fields.Boolean(default=False, required=False)
    verticals = fields.List(fields.String())


class PractitionerNotesArgsSchemaV3(PaginableArgsSchemaV3):
    all_appointments = BooleanWithDefault(default=False, required=False)
    scheduled_start = DataTimeWithDefaultV3()
    scheduled_end = DataTimeWithDefaultV3()
    my_appointments = BooleanWithDefault(default=False, required=False)
    completed_appointments = BooleanWithDefault(default=False, required=False)
    verticals = ListWithDefaultV3(StringWithDefaultV3, default=[])


class PractitionerNotesResource(PermissionedCareTeamResource):
    @db.from_app_replica
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-practitioner-notes-resource-get",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        patient = User.query.get(user_id)
        current_user_id = self.user.id
        if not patient:
            abort(403, message=f"Patient {user_id} does not exist")
        self._user_has_access_to_user_or_403(self.user, patient)

        # TODO cleanup flags MPC-3795
        async_encounter_summaries_enabled = feature_flags.bool_variation(
            "release-mpractice-async-encounters",
            launchdarkly.user_context(self.user),
            default=False,
        )

        if async_encounter_summaries_enabled:
            in_schema = (
                V2PractitionerNotesArgsSchemaV3()
                if experiment_enabled
                else V2PractitionerNotesArgsSchema()
            )
        else:
            in_schema = (
                PractitionerNotesArgsSchemaV3()
                if experiment_enabled
                else PractitionerNotesArgsSchema()
            )
        verticals = request.args.getlist("provider_types")
        args = (
            in_schema.load(request.args)  # type: ignore[attr-defined]
            if experiment_enabled
            else in_schema.load(request.args).data  # type: ignore[attr-defined]
        )

        appointments = (
            db.session.query(Appointment)
            .join(Schedule)
            .filter(
                Appointment.member_schedule_id == Schedule.id,
                Schedule.user_id == patient.id,
            )
            .order_by(desc(Appointment.scheduled_start))
        )

        if args.get("scheduled_start"):
            appointments = appointments.filter(
                Appointment.scheduled_start >= args.get("scheduled_start")
            )
        if args.get("scheduled_end"):
            appointments = appointments.filter(
                Appointment.scheduled_end <= args.get("scheduled_end")
            )

        if args.get("completed_appointments"):
            appointments = appointments.filter(
                Appointment.member_started_at.isnot(None),
                Appointment.member_ended_at.isnot(None),
                Appointment.practitioner_started_at.isnot(None),
                Appointment.practitioner_ended_at.isnot(None),
                Appointment.cancelled_at.is_(None),
            )

        if not args.get("all_appointments"):
            appointments.join(
                AppointmentMetaData,
                Appointment.id == AppointmentMetaData.appointment_id,
            ).filter(
                AppointmentMetaData.content.isnot(None),
                AppointmentMetaData.content != "",
            )

        # Comes from front-end via Provider Type option
        if verticals:
            appointments = (
                appointments.join(Product, Appointment.product_id == Product.id)
                .join(
                    PractitionerProfile, Product.user_id == PractitionerProfile.user_id
                )
                .join(PractitionerProfile.verticals)
                .filter(Vertical.name.in_(verticals))
            )

        # If patient has opted out of note-sharing
        # or provider has filtered to "my_appointments"
        # limit appointments to just the logged in user's (unless user is patient)
        if async_encounter_summaries_enabled:
            if (
                (
                    not patient.member_profile
                    or not patient.member_profile.opted_in_notes_sharing
                )
                and current_user_id != patient.id
            ) or args.get("my_encounters"):
                appointments = appointments.filter(
                    Appointment.product_id == Product.id,
                    Product.user_id == current_user_id,
                )
        else:
            if (
                (
                    not patient.member_profile
                    or not patient.member_profile.opted_in_notes_sharing
                )
                and current_user_id != patient.id
            ) or args.get("my_appointments"):
                appointments = appointments.filter(
                    Appointment.product_id == Product.id,
                    Product.user_id == current_user_id,
                )

        total = appointments.count()
        appointments = appointments.limit(args["limit"]).offset(args["offset"])

        schema = (
            PractitionerNotesSchemaV3()
            if experiment_enabled
            else PractitionerNotesSchema()
        )
        appointments = appointments.all()
        appointment_ids = [a.id for a in appointments]

        # Get all the RecordedAnswerSets and any associated Questionnaires for each Appointment
        answer_set_questionnaires_by_appt_id = self._recorded_answer_set_questionnaires(
            appointment_ids
        )

        # Determine which appointments didn't have a Questionnaire or RecordedAnswerSet
        # And we'll fetch that data via alternative means below
        practitioner_ids = []
        appts_missing_answer_sets = []
        appts_missing_questionnaires = []
        for appointment in appointments:
            answer_set, questionnaire = answer_set_questionnaires_by_appt_id.get(
                appointment.id, (None, None)
            )
            if answer_set is None:
                appts_missing_answer_sets.append(appointment.id)
            if questionnaire is None:
                appts_missing_questionnaires.append(appointment.id)
                # If the RecordedAnswerSet didn't have a Questionnaire we will find a Questionnaire
                # for these specific practitioners below
                if appointment.practitioner_id:
                    practitioner_ids.append(appointment.practitioner_id)

        # For any Appointment without a RecordedAnswerSet, fetch the RecordedAnswers instead
        recorded_answers_by_appt_id = self._legacy_recorded_answers(
            appts_missing_answer_sets, current_user_id
        )

        # Find any missing Questionnaires now for Practitioners who didn't have one from an above step
        questionnaires_by_pract_id = self._get_questionnaires_for_practitioners(
            list(set(practitioner_ids))
        )

        structured_internal_note = {}
        for appointment in appointments:
            structured_internal_note[appointment.id] = {
                "recorded_answer_set": self._recorded_answer_set(
                    appointment, answer_set_questionnaires_by_appt_id
                ),
                "recorded_answers": recorded_answers_by_appt_id.get(appointment.id),
                "questionnaire": self._questionnaire(
                    appointment,
                    answer_set_questionnaires_by_appt_id,
                    questionnaires_by_pract_id,
                ),
            }

        schema.context["structured_internal_note"] = structured_internal_note  # type: ignore[attr-defined]
        schema.context["user"] = self.user  # type: ignore[attr-defined]

        results = {
            "data": appointments,
            "pagination": {
                "total": total,
                "limit": args["limit"],
                "offset": args["offset"],
                "order_direction": "desc",
            },
        }
        with ddtrace.tracer.trace(name=f"{__name__}.serialization"):
            return (
                schema.dump(results)  # type: ignore[attr-defined]
                if experiment_enabled
                else schema.dump(results).data  # type: ignore[attr-defined]
            )

    @tracer.wrap()
    def _recorded_answer_set(self, appointment, answer_set_questionnaires):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        recorded_answer_set = answer_set_questionnaires[appointment.id][0]
        if (
            recorded_answer_set
            and recorded_answer_set.source_user_id == appointment.practitioner_id
        ):
            return recorded_answer_set
        else:
            return None

    @tracer.wrap()
    def _questionnaire(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, appointment, answer_set_questionnaires, questionnaires_by_pract_id
    ):
        return (
            answer_set_questionnaires[appointment.id][1]
            or questionnaires_by_pract_id.get(appointment.practitioner_id)
            or self._standard_questionnaire()
        )

    @tracer.wrap()
    def _recorded_answer_set_questionnaires(self, appointment_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        result = {appt_id: (None, None) for appt_id in appointment_ids}
        data = (
            db.session.query(RecordedAnswerSet, Questionnaire)
            .filter(RecordedAnswerSet.appointment_id.in_(appointment_ids))
            .outerjoin(
                Questionnaire, RecordedAnswerSet.questionnaire_id == Questionnaire.id
            )
            .order_by(RecordedAnswerSet.submitted_at.desc())
            .all()
        )
        for row in data:
            appt_id = row[0].appointment_id
            result[appt_id] = row
        return result

    @tracer.wrap()
    def _legacy_recorded_answers(self, appointment_ids, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        result = {appt_id: [] for appt_id in appointment_ids}
        recorded_answers = (
            db.session.query(RecordedAnswer)
            .filter(
                and_(
                    RecordedAnswer.appointment_id.in_(appointment_ids),
                    RecordedAnswer.user_id == user_id,
                )
            )
            .all()
        )
        for ans in recorded_answers:
            result[ans.appointment_id].append(ans)
        return result

    @tracer.wrap()
    def _get_questionnaires_for_practitioners(self, practitioner_ids, oid=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        questionnaires = (
            db.session.query(Questionnaire, practitioner_verticals.c.user_id)
            .join(questionnaire_vertical)
            .join(
                practitioner_verticals,
                questionnaire_vertical.c.vertical_id
                == practitioner_verticals.c.vertical_id,
            )
            .filter(practitioner_verticals.c.user_id.in_(practitioner_ids))
            .filter(~Questionnaire.roles.any(Role.name == ROLES.member))
        )

        if oid:
            questionnaires = questionnaires.filter(Questionnaire.oid == oid)

        questionnaires = (
            questionnaires.group_by(Questionnaire.id, practitioner_verticals.c.user_id)
            .order_by(desc(Questionnaire.id))
            .all()
        )

        # Exclude async encounter questionnaires from being pulled here
        # since they're pulled in GET /members/:member_id/async_encounter_summaries
        return {
            q.user_id: q.Questionnaire
            for q in questionnaires
            if not q.Questionnaire.oid
            or not (q.Questionnaire.oid.startswith(ASYNC_ENCOUNTER_QUESTIONNAIRE_OID))
        }

    @tracer.wrap()
    def _standard_questionnaire(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return Questionnaire.query.filter_by(
            oid=COACHING_NOTES_COACHING_PROVIDERS_OID
        ).first()


class MemberProfileResource(PermissionedUserResource):
    @property
    def launchdarkly_context(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return launchdarkly.marshmallow_context(self.user.esp_id, self.user.email)

    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_abort(user_id)
        experiment_enabled = feature_flags.bool_variation(
            "experiment-marshmallow-member-profile-upgrade",
            self.launchdarkly_context,
            default=False,
        )

        schema = (
            MemberProfileSchema() if not experiment_enabled else MemberProfileSchemaV3()
        )
        return (
            schema.dump(user.member_profile).data  # type: ignore[attr-defined] # "object" has no attribute "dump"
            if not experiment_enabled
            else schema.dump(user.member_profile)  # type: ignore[attr-defined] # "object" has no attribute "dump"
        )

    def put(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_abort(user_id)
        experiment_enabled = feature_flags.bool_variation(
            "experiment-marshmallow-member-profile-upgrade",
            self.launchdarkly_context,
            default=False,
        )
        schema = (
            MemberProfileSchema() if not experiment_enabled else MemberProfileSchemaV3()
        )
        try:
            request_json = request.json if request.is_json else None
            args = (
                schema.load(request_json).data  # type: ignore[attr-defined] # "object" has no attribute "load"
                if not experiment_enabled
                else schema.load(request_json)  # type: ignore[attr-defined] # "object" has no attribute "load"
            )
        except (UnmarshallingError, ValidationErrorV3) as ue:
            abort(400, message=str(ue))

        countries = CountryRepository(session=db.session)
        subdivisions = SubdivisionRepository()

        profile = user.member_profile
        old_phone_number = None
        if args.get("phone_number") is not None:
            old_phone_number = profile.phone_number
            profile.phone_number = args["phone_number"]

        if args.get("subdivision_code") is not None:
            profile.subdivision_code = args["subdivision_code"]
            if country := countries.get_by_subdivision_code(
                subdivision_code=profile.subdivision_code
            ):
                profile.country_code = country.alpha_2

        if args.get("country") is not None:
            if country := countries.get(country_code=args["country"]):
                profile.country_code = country.alpha_2

        if args.get("state") is not None:
            profile.state = args["state"]
            if country_code := profile.user.country_code or "US":
                if subdivision := subdivisions.get_by_country_code_and_state(
                    country_code=country_code,
                    state=args["state"].abbreviation,
                ):
                    profile.subdivision_code = subdivision.code
                    profile.country_code = subdivision.country_code
                else:
                    profile.subdivision_code = None

        if any(args.get("address", {}).values()):
            if not profile.add_or_update_address(args["address"]):
                abort(
                    400,
                    message="Could not update address, please make sure all fields are properly filled out",
                )

        if args.get("opted_in_notes_sharing") is not None:
            profile.opted_in_notes_sharing = args["opted_in_notes_sharing"]

        if args.get("color_hex") is not None:
            profile.json["color_hex"] = args.get("color_hex")

        if profile.state and not args.get("state"):
            abort(400, message="State cannot be emptied out.")

        db.session.add(profile)
        db.session.commit()

        service_ns_tag = "community_forum"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)

        invalidate_posts_cache_for_user.delay(
            user.id, service_ns=service_ns_tag, team_ns=team_ns_tag
        )

        if args.get("phone_number") is not None:
            # Check this user for any wallet, past or present; let the
            # updating logic worry about if it's active, has a debit card, etc.
            if len(user.reimbursement_wallets) > 0:
                remove_member_number.delay(
                    user_id=user.id,
                    old_phone_number=old_phone_number,
                    service_ns=service_ns_tag,
                    team_ns=team_ns_tag,
                )

        return (
            schema.dump(profile).data  # type: ignore[attr-defined] # "object" has no attribute "dump"
            if not experiment_enabled
            else schema.dump(profile)  # type: ignore[attr-defined] # "object" has no attribute "dump"
        )

    def _user_or_abort(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)

        if user.member_profile:
            return user
        else:
            abort(403, message=f"User {user.id} not a member!")


class CurrentUserMemberProfileResource(AuthenticatedResource):
    """
    Return the current user's MemberProfile, if they have one
    """

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not self.user.member_profile:
            return {}, 200

        schema = MemberProfileSchema(exclude=("dashboard",))
        return schema.dump(self.user.member_profile).data


class UserOnboardingStateResource(PermissionedUserResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self._user_or_404(user_id)
        state = None
        # handle the case where there is no state yet
        if user.onboarding_state:
            state = user.onboarding_state.state
        # return the user's onboarding state
        return {"onboarding_state": state}, 200

    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self.update_onboarding_state(user_id, OnboardingState.USER_CREATED), 201

    def put(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        args = request.json if request.is_json else {}
        new_state = args.get("onboarding_state")
        if not new_state:
            abort(400, message="New onboarding state is required")

        try:
            state = OnboardingState(new_state)
            return self.update_onboarding_state(user_id, state), 200
        except ValueError as e:
            log.error(str(e))
            abort(400, message=f"{new_state} does not exist")

    def update_onboarding_state(
        self, user_id: int, new_state: OnboardingState
    ) -> dict[str, OnboardingState] | None:
        user = self._user_or_404(user_id)

        try:
            update_onboarding_state(user, new_state)
            db.session.commit()
            return {"onboarding_state": new_state}

        except exc.SQLAlchemyError as e:
            log.error(str(e))
            db.session.rollback()
            abort(
                400,
                message="Sorry, we ran into an issue. Please contact your care advocate.",
            )
        return None


class CategorySchema(SchemaV3):
    id = ma_fields.Integer()
    name = ma_fields.String()
    image_url = ma_fields.Method(serialize="get_image_url")
    display_name = StringWithDefaultV3(dump_default="")
    ordering_weight = IntegerWithDefaultV3(dump_default=0)
    post_count = ma_fields.Method(serialize="get_post_count")

    def get_image_url(self, obj: Category) -> str | None:
        return obj.image_url()

    def get_post_count(self, obj: Category) -> int:
        return (
            db.session.query(Post)
            .join(post_categories, Post.id == post_categories.c.post_id)
            .join(Category)
            .filter(Category.id == obj.id, Post.parent_id.is_(None))
            .count()
        )


class CategoriesSchema(PaginableOutputSchemaV3):
    data = ma_fields.Nested(CategorySchema, many=True)  # type: ignore[assignment]


class CategoriesResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        base = db.s_replica1.query(Category).order_by(Category.ordering_weight.asc())

        client_name = request.args.get("client_name")
        if client_name:
            categories = (
                base.join(category_versions)
                .join(CategoryVersion)
                .filter(CategoryVersion.name == client_name)
                .all()
            )
        else:
            categories = base.all()

        data = {"data": categories, "pagination": {"total": len(categories)}}

        schema = CategoriesSchema()
        return schema.dump(data)


class VerticalsResource(AuthenticatedResource):
    @property
    def launchdarkly_context(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return launchdarkly.marshmallow_context(self.user.esp_id, self.user.email)

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        l10n_flag = feature_flags.bool_variation(
            "release-care-discovery-provider-field-localization",
            self.launchdarkly_context,
            default=False,
        )
        args = V2VerticalGetSchemaV3().load(request.args)
        if ids := args.get("ids"):
            verticals = (
                db.session.query(Vertical)
                .filter(
                    Vertical.deleted_at == None,
                    Vertical.id.in_(ids),
                )
                .order_by(asc(func.lower(Vertical.name)))
                .all()
            )
        else:
            verticals = (
                db.session.query(Vertical)
                .filter(Vertical.deleted_at == None)
                .order_by(asc(func.lower(Vertical.name)))
                .all()
            )
        if l10n_flag:
            schema = TranslatedV2VerticalSchemaV3(context={"user": self.user})
        else:
            schema = V2VerticalSchemaV3()  # type: ignore[assignment]
        return schema.dump(verticals, many=True)  # type: ignore[attr-defined] # "object" has no attribute "dump"


class UserFileGetSchema(PaginableArgsSchema):
    type = fields.String(required=False)
    appointment_id = fields.Integer(required=False)


class UserFileSchema(MavenSchema):
    id = fields.Integer()
    type = fields.Function(lambda _f: "BIRTH_PLAN")
    content_type = fields.String()
    signed_url = fields.Function(lambda f: f.direct_download_url())


class UserFilesSchema(PaginableOutputSchema):
    data = fields.Nested(UserFileSchema, many=True)  # type: ignore[assignment]


class UserFilesResource(AuthenticatedResource):
    def _get_and_verify_appointment(self, appointment_id, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        appointment_id = deobfuscate_appointment_id(appointment_id)
        appt = Appointment.query.get_or_404(appointment_id)

        if appt.purpose != "birth_planning":
            abort(403, message="Wrong Appointment purpose.")

        # ensure specified appointment belongs to the specified user
        if appt.member.id != user_id:
            abort(403, message="Mismatching user and appointment!")

        return appt

    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        args = UserFileGetSchema().load(request.args).data
        user = User.query.get_or_404(user_id)

        files = [f for f in user.assets if f.appointment is not None]

        if args.get("type"):
            if args["type"] != "BIRTH_PLAN":
                abort(400, message="Invalid UserFile type!")

        if args.get("appointment_id"):
            appt = self._get_and_verify_appointment(args.get("appointment_id"), user_id)
            files = [f for f in files if f.appointment.id == appt.id]

        if files:
            allowed = []
            for file in files:
                f_appt = file.appointment
                if f_appt and self.user in (f_appt.practitioner, f_appt.member):
                    allowed.append(file)

            if not allowed:
                abort(403, message="Not authorized!")

            files = allowed

        results = {
            "data": files,
            "pagination": {
                "total": len(files),
                # 'limit': args['limit'],
                # 'offset': args['offset'],
                "order_direction": args["order_direction"],
            },
        }
        return UserFilesSchema().dump(results).data

    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        args = UserFileGetSchema().load(request.form).data
        user = User.query.get_or_404(user_id)

        if not args.get("appointment_id"):
            abort(400, message='Missing required request property, "appointment_id".')

        appointment = self._get_and_verify_appointment(
            args.get("appointment_id"), user_id
        )

        # Only BP appointment's practitioner is allowed to POST
        if appointment.practitioner.id != self.user.id:
            abort(403, message="Not authorized!")

        file_type = args.get("type")
        if file_type != "BIRTH_PLAN" or file_type not in request.files:
            abort(400, message="Not a supported type.")

        file_storage = request.files[file_type]
        content_type = magic.from_buffer(file_storage.stream.read(1024), mime=True)

        if not content_type.endswith("/pdf"):
            abort(400, message="Birth plan user files must be a pdf.")

        file_storage.stream.seek(0)  # reset file pointer to the beginning

        ua = UserAsset(
            state=UserAssetState.UPLOADING,
            file_name="MAVEN_BIRTH_PLAN.pdf",
            content_type=content_type,
            content_length=0,
            user=user,
            appointment=appointment,
        )
        db.session.add(ua)
        db.session.flush()

        blob = ua.blob
        blob.upload_from_file(file_storage.stream)
        blob.content_type = ua.content_type
        blob.content_disposition = f"attachment;filename*=utf-8''{quote(ua.file_name)}"
        blob.patch()
        ua.content_length = blob.size
        ua.state = UserAssetState.COMPLETE
        db.session.commit()

        notify_birth_plan_pdf_availability.delay(appointment.id)

        return UserFileSchema().dump(ua).data, 201
