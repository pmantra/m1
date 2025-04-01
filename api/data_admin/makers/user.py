import datetime
import json

import dateparser
import pymysql
import sqlalchemy
from dateutil.relativedelta import relativedelta
from flask import flash

from authn.models.user import User
from authz.models.roles import ROLES
from care_advocates.models.assignable_advocates import AssignableAdvocate
from care_advocates.models.matching_rules import (
    MatchingRule,
    MatchingRuleEntityType,
    MatchingRuleSet,
    MatchingRuleType,
)
from data_admin.common import types_to_dropdown_options
from data_admin.data_factory import DataFactory
from data_admin.maker_base import _MakerBase
from data_admin.makers.organization import OrganizationMaker
from eligibility import service as e9y_service
from health.domain.add_profile import add_profile_to_user
from models import tracks
from models.enterprise import Organization
from models.products import Product
from models.programs import Module
from models.tracks import ChangeReason
from models.verticals_and_specialties import Vertical, is_cx_vertical_name
from storage.connection import db
from tasks.users import user_post_creation
from utils.log import logger
from views.schemas.common import (
    AddressSchema,
    BooleanField,
    CSVIntegerField,
    CSVStringField,
    MavenDateTime,
    MavenSchema,
)
from wallet.repository.member_benefit import MemberBenefitRepository
from wallet.services.member_benefit import MemberBenefitService
from wheelhouse.marshmallow_v1.marshmallow_v1 import fields

log = logger(__name__)


class ParsedDateTime(MavenDateTime):
    def _deserialize(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return dateparser.parse(value)


class CreditSchema(MavenSchema):
    amount = fields.Number()
    activated_at = fields.String()
    expires_at = fields.String()


class OrganizationEmployeeNestedSchema(MavenSchema):
    date_of_birth = fields.String(required=True)
    organization_name = fields.String(required=True)
    company_email = fields.String()
    unique_corp_id = fields.String()
    dependent_id = fields.String()
    beneficiaries_enabled = fields.Boolean()
    wallet_enabled = fields.Boolean()
    first_name = fields.String()
    last_name = fields.String()
    work_state = fields.String()
    can_get_pregnant = fields.Boolean(default=True)
    address = fields.Nested(AddressSchema)


class UserCreationSchema(MavenSchema):
    role = fields.Enum(types_to_dropdown_options(ROLES), default=ROLES.member)
    password = fields.String(default="simpleisawesome1*")
    username = fields.String()
    user_id = fields.Integer()
    first_name = fields.String(default="Jane")
    last_name = fields.String(default="Smith")
    email = fields.Email()
    created_at = MavenDateTime()
    date_of_birth = MavenDateTime()
    work_state = fields.String()
    country = fields.String()
    company_email = fields.String()
    spouse_email = fields.Email()
    module_name = fields.String()
    due_days = fields.Integer()
    had_child_days_ago = fields.Integer()
    track_created_days_ago = fields.Integer()
    organization_name = fields.String()
    care_team = fields.List(fields.String())
    user_flags = fields.List(fields.String())
    credit = fields.Nested(CreditSchema)
    address = fields.Nested(AddressSchema)
    birthday = MavenDateTime()
    phone_number = fields.String()
    tracks = fields.List(fields.String())
    track = fields.String()
    phase = fields.String()
    start_date = fields.Date()
    email_prefix = fields.String()
    auto_care_team = BooleanField()
    create_member_record = BooleanField()
    organization_employee = fields.Nested(
        OrganizationEmployeeNestedSchema
    )  # Organization name

    # practitioner specific
    messaging_enabled = BooleanField()
    anonymous_allowed = BooleanField()
    show_when_unavailable = BooleanField()
    can_prescribe = BooleanField()
    otp_secret = fields.String()
    api_key = fields.String()
    next_availability = ParsedDateTime()
    vertical = fields.String(default="Nutritionist")
    specialty_ids = CSVIntegerField()
    certified_subdivision_codes = CSVStringField()
    years_experience = fields.Integer()
    education = fields.String()
    reference_quote = fields.String()
    awards = fields.String()
    work_experience = fields.String()


def _activate_admin_for_user(user, kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if kwargs.get("otp_secret"):
        user.otp_secret = kwargs["otp_secret"]
        db.session.add(user)
        db.session.flush()


def _activate_enterprise_for_user(user, kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    factory = DataFactory(None, "no client")
    org_name = kwargs["organization_name"]
    org = Organization.query.filter_by(name=org_name).first()
    email = kwargs.get("company_email", user.email)
    dob = kwargs.get(
        "date_of_birth", datetime.datetime.strptime("1999-01-23", "%Y-%m-%d")
    )
    if not org:
        org_maker = OrganizationMaker()
        org = org_maker.create_object_and_flush(
            {"name": org_name, "activated_at": "1 minute ago"}
        )

    org_emp = factory.add_organization_employee(
        email,
        dob,
        organization=org,
    )
    factory.add_user_organization_employee(user, org_emp)

    verification_service = e9y_service.get_verification_service()
    member = _create_eligibility_member_record(
        verification_service, email, dob, org, user, org_emp, kwargs
    )

    verification_created = None
    if member:
        log.info("Creating verification for user from data-admin", user_id=user.id)
        verification_created = verification_service.generate_verification_for_user(
            user_id=user.id,
            organization_id=org.id,
            first_name=user.first_name,
            last_name=user.last_name,
            date_of_birth=dob,
            email=email,
            unique_corp_id=member["unique_corp_id"],
            dependent_id=member["dependent_id"],
            work_state=kwargs.get("work_state"),
            verification_type="MANUAL",
            eligibility_member_id=member["id"],
        )
        log.info(
            "Successfully created verification for user from data-admin",
            user_id=user.id,
        )
    else:
        log.info(
            "No verification created because no e9y member record created",
            user_id=user.id,
        )

    now = datetime.datetime.utcnow()

    due_days = kwargs.get("due_days")
    if due_days is not None:
        user.health_profile.due_date = now + datetime.timedelta(days=due_days)

    had_child_days_ago = kwargs.get("had_child_days_ago")
    if had_child_days_ago is not None:
        user.health_profile.add_a_child(
            now - datetime.timedelta(days=had_child_days_ago)
        )

    if kwargs.get("track"):
        _initiate_track_for_user(
            user,
            track_name=kwargs.get("track"),
            phase_name=kwargs.get("phase"),
            org=org,
            **kwargs,
        )
    elif kwargs.get("tracks"):
        # Multitrack
        for track_phase_name in kwargs.get("tracks"):
            track_name, phase_name = (
                track_phase_name.split(":")
                if ":" in track_phase_name
                else [track_phase_name, None]
            )
            _initiate_track_for_user(
                user,
                track_name=track_name,
                phase_name=phase_name,
                org=org,
                **kwargs,
            )

    return verification_created


def _create_eligibility_member_record(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    verification_service, email, dob, org, user, org_emp, kwargs
):
    member_id = None
    if kwargs.get("create_member_record"):
        log.info("Creating eligibility member record from data-admin")
        if not (kwargs.get("work_state") and kwargs.get("country") and dob):
            raise Exception(
                "==== ERROR: 'work_state' (ie: 'NY'), 'country' (ie: 'US'), and 'date_of_birth' (ie: '1999-01-23') are required when 'create_member_record' is True"
            )

        member_response = verification_service.create_test_eligibility_member_records(
            organization_id=org.id,
            test_member_records=[
                {
                    "email": email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "date_of_birth": dob.strftime("%Y-%m-%d"),
                    "work_state": kwargs["work_state"],
                    "work_country": kwargs["country"],
                    "unique_corp_id": org_emp.unique_corp_id,
                    "dependent_id": org_emp.dependent_id,
                },
            ],
        )

        if not member_response:
            raise Exception(
                "Organization does not exist - could not create eligibility record"
            )

        member = json.loads(member_response[0])
        log.info(
            "Successfully created eligibility member record from data-admin",
            user_id=user.id,
            member_id=member_id,
        )
        return member


def _initiate_track_for_user(user, track_name, phase_name, org, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    now = datetime.datetime.utcnow()
    created_at = now
    if kwargs.get("track_created_days_ago") is not None:
        created_at = now - datetime.timedelta(days=kwargs.get("track_created_days_ago"))  # type: ignore[arg-type] # Argument "days" to "timedelta" has incompatible type "Optional[Any]"; expected "float"
    if not phase_name:
        phase_name = "week-5"
    if not tracks.phase.WEEKLY_PHASE_NAME_REGEX.match(phase_name):
        raise ValueError(f"Invalid phase name {phase_name}")

    # TODO: this will all be easier when we can just force track.anchor_date
    one_day = datetime.timedelta(days=1)
    week_num = int(phase_name.split("-")[1])
    if track_name in ("postpartum", "partner_newparent"):
        had_child_weeks_ago = week_num - 39  # TODO: Don't do this?
        user.health_profile.add_a_child(
            now - datetime.timedelta(weeks=had_child_weeks_ago) + one_day
        )
    elif track_name in ("pregnancy", "partner_pregnant"):
        weeks_until_due_date = 39 - week_num
        user.health_profile.due_date = (
            now + datetime.timedelta(weeks=weeks_until_due_date) + one_day
        )
        if weeks_until_due_date < 0:
            created_at_date = user.health_profile.due_date - one_day
            # Convert date to datetime
            created_at = datetime.datetime(*created_at_date.timetuple()[:6])
    else:
        created_at = now - datetime.timedelta(weeks=week_num) + one_day

    if start_date := kwargs.get("start_date"):
        if start_date < created_at.date():
            raise ValueError(f"start_date ({start_date}) cannot be in the past")
    else:
        start_date = created_at.date()

    track = tracks.initiate(
        user=user,
        track=tracks.TrackName(track_name),
        is_employee=True,
        start_date=start_date,
        change_reason=ChangeReason.DATA_ADMIN_INITIATE_TRACK,
        eligibility_organization_id=org.id,
    )
    track.created_at = created_at
    track.activated_at = created_at

    # don't set activated_at if the start_date is in the future
    if start_date <= now.date():
        if start_date == created_at.date():
            activated_at = created_at
        else:
            activated_at = datetime.datetime(
                start_date.year,
                start_date.month,
                start_date.day,
            )

        track.activated_at = activated_at

    # With time = now, update program phase
    tracks.check_track_state(track)
    db.session.flush()


def _add_a_user(kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    email = kwargs.get("email")
    if email:
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash(f"Using existing user with email: {email}", "info")
            existing_user._data_admin_password = kwargs.get(
                "password", "simpleisawesome1*"
            )
            return existing_user

    role = kwargs.get("role", "member")
    password = kwargs.get("password", "simpleisawesome1*")
    experience_started = None
    if kwargs.get("years_experience"):
        experience_started = datetime.datetime.today() - relativedelta(
            years=kwargs.get("years_experience")
        )

    try:
        user = DataFactory(None, "no_client").new_user(
            role=role,
            experience_started=experience_started,
            vertical=kwargs.get("vertical"),
            password=password,
            api_key=kwargs.get("api_key"),
            username=kwargs.get("username"),
            user_id=kwargs.get("user_id"),
            first_name=kwargs.get("first_name"),
            last_name=kwargs.get("last_name"),
            email=kwargs.get("email"),
            created_at=kwargs.get("created_at"),
            specialty_ids=kwargs.get("specialty_ids"),
            certified_subdivision_codes=kwargs.get("certified_subdivision_codes"),
            messaging_enabled=kwargs.get("messaging_enabled"),
            anonymous_allowed=kwargs.get("anonymous_allowed"),
            show_when_unavailable=kwargs.get("show_when_unavailable"),
            can_prescribe=kwargs.get("can_prescribe"),
            education=kwargs.get("education"),
            reference_quote=kwargs.get("reference_quote"),
            awards=kwargs.get("awards"),
            work_experience=kwargs.get("work_experience"),
            care_team=kwargs.get("care_team"),
            user_flags=kwargs.get("user_flags"),
            birthday=kwargs.get("date_of_birth"),
            phone_number=kwargs.get("phone_number"),
            address=kwargs.get("address"),
            email_prefix=kwargs.get("email_prefix", "pre"),
            country=kwargs.get("country"),
            state=kwargs.get("work_state"),
        )
    except (pymysql.err.IntegrityError, sqlalchemy.exc.IntegrityError) as e:
        flash(f"User already existed: {kwargs}", "info")
        log.error(str(e))
        raise e

    # Keep this at the top because otherwise we run into
    # a SQL lock timeout error from the SQL below
    if kwargs.get("otp_secret"):
        _activate_admin_for_user(user, kwargs)

    _add_a_user_benefit_id(user.id)

    e9y_verification = None
    if kwargs.get("organization_name"):
        if role != "member":
            flash(
                f"Only member can be activated for enterprise. But it was {role}.",
                "error",
            )
            return
        e9y_verification = _activate_enterprise_for_user(user, kwargs)

    if kwargs.get("credit"):
        expires_at = kwargs["credit"].get("expires_at")
        activated_at = kwargs["credit"].get("activated_at")
        if expires_at:
            expires_at = dateparser.parse(expires_at)
        if activated_at:
            activated_at = dateparser.parse(activated_at)
        DataFactory(None, "no client").new_credit(
            amount=kwargs["credit"].get("amount"),
            user=user,
            expires_at=expires_at,
            activated_at=activated_at,
            verification=e9y_verification,
        )

    if kwargs.get("address"):
        DataFactory(None, "no client").add_address(user, kwargs.get("address"))

    user._data_admin_password = password
    return user


def _add_a_user_benefit_id(user_id: int) -> None:
    try:
        repo = MemberBenefitRepository(session=db.session)
        member_benefit_service = MemberBenefitService(member_benefit_repo=repo)
        member_benefit_service.add_for_user(user_id=user_id)
    except Exception as e:
        log.exception(f"Failed to assign a benefit ID for user_id: {user_id}", exc=e)
        raise e
    else:
        log.info(f"Successfully assigned benefit ID for user_id: {user_id}")


class UserMaker(_MakerBase):
    spec_class = UserCreationSchema(strict=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "UserCreationSchema", base class "_MakerBase" defined the type as "None")

    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"
        user = _add_a_user(spec_data)
        if not user:
            return

        user_post_creation.delay(user.id)

        if "is_care_coordinator" in spec.keys():
            raise ValueError("is_care_coordinator is deprecated. Use is_cx instead.")

        if spec.get("role") == "practitioner" and spec.get("is_cx"):
            v = Vertical.query.filter(is_cx_vertical_name(Vertical.name)).one()
            pp = user.practitioner_profile
            pp.next_availability = spec_data.get("next_availability")
            pp.verticals.append(v)
            db.session.add(pp)
            db.session.add(Product(minutes=10, vertical=v, price=10, practitioner=user))
            add_profile_to_user(user, "staff", **vars(user))
            if spec.get("featured_practitioner"):
                assignable_advocate = AssignableAdvocate(
                    practitioner=pp, max_capacity=10, daily_intro_capacity=5
                )
                db.session.add(assignable_advocate)

                def _create_extensive_matching_rule_set(assignable_advocate):  # type: ignore[no-untyped-def] # Function is missing a type annotation
                    """
                    Create a Matching Rule Set with Any Country, Any Org, No exceptions, All Tracks.
                    """
                    mrs = MatchingRuleSet(assignable_advocate=assignable_advocate)
                    country_mr = MatchingRule(
                        type=MatchingRuleType.INCLUDE.value,
                        entity=MatchingRuleEntityType.COUNTRY.value,
                        matching_rule_set=mrs,
                        all=True,
                    )
                    if "organization_id" in spec:
                        org_mr = MatchingRule(
                            type=MatchingRuleType.INCLUDE.value,
                            entity=MatchingRuleEntityType.ORGANIZATION.value,
                            matching_rule_set=mrs,
                            all=False,
                        )
                        org_mr.identifiers.append(str(spec["organization_id"]))
                    else:
                        org_mr = MatchingRule(
                            type=MatchingRuleType.INCLUDE.value,
                            entity=MatchingRuleEntityType.ORGANIZATION.value,
                            matching_rule_set=mrs,
                            all=True,
                        )
                    track_mr = MatchingRule(
                        type=MatchingRuleType.INCLUDE.value,
                        entity=MatchingRuleEntityType.MODULE.value,
                        matching_rule_set=mrs,
                    )
                    for module in db.session.query(Module).all():
                        track_mr.identifiers.append(module.id)

                    user_flag_mr = MatchingRule(
                        type=MatchingRuleType.INCLUDE.value,
                        entity=MatchingRuleEntityType.USER_FLAG.value,
                        matching_rule_set=mrs,
                        all=True,
                    )
                    user_none_flag_mr = MatchingRule(
                        type=MatchingRuleType.EXCLUDE.value,
                        entity=MatchingRuleEntityType.USER_FLAG.value,
                        matching_rule_set=mrs,
                        all=True,
                    )

                    for mr in [
                        country_mr,
                        org_mr,
                        track_mr,
                        user_flag_mr,
                        user_none_flag_mr,
                    ]:
                        db.session.add(mr)
                    db.session.add(mrs)

                _create_extensive_matching_rule_set(assignable_advocate)

            db.session.flush()

        return user
