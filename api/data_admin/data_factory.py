import datetime
import random
import uuid
from contextlib import contextmanager
from typing import Optional
from unittest.mock import patch

from app import create_app
from appointments.models.appointment import Appointment
from appointments.models.cancellation_policy import CancellationPolicy
from appointments.models.payments import Credit
from appointments.models.schedule import Schedule, add_schedule_for_user
from appointments.models.schedule_event import ScheduleEvent
from authn.domain.service import authn
from authn.models.user import User
from authz.models.roles import ROLES
from care_advocates.models.assignable_advocates import DEFAULT_CARE_COORDINATOR_EMAIL
from direct_payment.clinic.models.clinic import FertilityClinicAllowedDomain
from direct_payment.clinic.models.user import (
    AccountStatus,
    FertilityClinicUserProfile,
    FertilityClinicUserProfileFertilityClinic,
)
from eligibility.e9y import model
from health.domain.add_profile import (
    add_profile_to_user,
    set_country_and_state,
    set_date_of_birth,
)
from health.models.health_profile import HealthProfile
from health.services.member_risk_service import MemberRiskService
from models.common import PrivilegeType
from models.enterprise import (
    BMS_ORDER_RESOURCE,
    OrganizationEmployee,
    UserOrganizationEmployee,
)
from models.marketing import Resource, ResourceTypes
from models.profiles import (
    CareTeamTypes,
    PractitionerProfile,
    PractitionerSubdivision,
    RoleProfile,
    State,
)
from models.programs import Module
from models.referrals import ReferralCode, ReferralCodeValue, add_referral_code_for_user
from models.tracks import TrackName
from models.tracks.client_track import ClientTrack
from models.verticals_and_specialties import CX_VERTICAL_NAME, Specialty, Vertical
from provider_matching.models.constants import StateMatchType
from storage.connection import db
from utils import braze
from utils.api_interaction_mixin import APIInteractionMixin
from utils.fixtures import create_user_factory
from utils.log import logger
from utils.passwords import encode_password
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent

log = logger(__name__)


# mypy: ignore-errors
class DataFactory(APIInteractionMixin):
    def __init__(self, test_case: Optional[str], client: Optional[str] = None) -> None:
        if not client:
            self.app = create_app()
            self.app.test_request_context().push()
            self.client = self.app.test_client(use_cookies=False)
        else:
            self.client = client
        self.test_case = test_case
        self.UserFactory = create_user_factory()

    def add_default_care_coordinator(self):
        return self.new_user(
            ROLES.practitioner, CX_VERTICAL_NAME, email=DEFAULT_CARE_COORDINATOR_EMAIL
        )

    def add_organization(
        self,
        name=None,
        display_name=None,
        add_tracks=True,
        vertical_group_version="foobar123",
        medical_plan_only=None,
        employee_only=None,
        bms_enabled=False,
        data_provider=False,
        alternate_verification=None,
        rx_enabled=True,
        US_restricted=False,
        associated_care_coordinator=None,
        activated_at=datetime.datetime.utcnow().replace(  # noqa  B008  TODO:  Do not perform function calls in argument defaults.  The call is performed only once at function definition time. All calls to your function will reuse the result of that definition-time function call.  If this is intended, assign the function call to a module-level variable and use that variable as a default value. # noqa  B008  TODO:  Do not perform function calls in argument defaults.  The call is performed only once at function definition time. All calls to your function will reuse the result of that definition-time function call.  If this is intended, assign the function call to a module-level variable and use that variable as a default value.
            microsecond=0
        ),
        # Specify just track names
        allowed_track_names=None,
        # Specify client track name and length_in_days
        client_tracks=None,
        alegeus_employer_id=None,
    ):
        from pytests.factories import ClientTrackFactory, OrganizationFactory

        # TODO: move this into OrganizationFactory
        if bms_enabled:
            resource = (
                db.session.query(Resource)
                .filter(Resource.slug == BMS_ORDER_RESOURCE)
                .scalar()
            )
            if not resource:
                bms_resource = Resource(
                    slug=BMS_ORDER_RESOURCE,
                    resource_type=ResourceTypes.ENTERPRISE,
                    content_type="test content",
                    title="",
                    body="",
                )
                db.session.add(bms_resource)
                db.session.flush()
        if allowed_track_names is None:
            allowed_track_names = [*TrackName]
        kwargs = dict(
            name=name,
            display_name=display_name,
            vertical_group_version=vertical_group_version,
            medical_plan_only=medical_plan_only,
            employee_only=employee_only,
            bms_enabled=bms_enabled,
            data_provider=data_provider,
            rx_enabled=rx_enabled,
            activated_at=activated_at,
            allowed_tracks=allowed_track_names if add_tracks else [],
            alegeus_employer_id=alegeus_employer_id,
        )
        if name is None:
            kwargs.pop("name")
        org = OrganizationFactory.create(**kwargs)
        if alternate_verification is not None:
            org.alternate_verification = alternate_verification

        if client_tracks:
            for client_track in client_tracks:
                ct = ClientTrackFactory(
                    track=client_track["track"],
                    length_in_days=client_track["length_in_days"],
                    organization=org,
                )
                db.session.add(ct)
                db.session.flush()
        return org

    def allow_tracks_for_org(self, org, track_names=None):
        if track_names:
            modules = Module.query.filter(Module.name.in_(track_names)).all()
        else:
            modules = Module.query.all()
        existing = {ct.track for ct in org.client_tracks}
        tracks = track_names or [*TrackName]
        org.client_tracks.extend(
            ClientTrack(track=n, length_in_days=365)
            for n in tracks
            if n not in existing
        )
        added = []
        for module in modules:
            if module not in org.allowed_modules:
                org.allowed_modules.append(module)
                added.append(module)
            else:
                continue
        db.session.flush()
        return added

    def add_organization_employee(
        self,
        corp_email="test@mavenclinic.com",
        dob="1989-04-01",
        unique_corp_id="random",
        organization=None,
        dependent_id=None,
        work_state=None,
        first_name=None,
        last_name=None,
        beneficiaries_enabled=None,
        can_get_pregnant=None,
        address=None,
        wallet_enabled=True,
        json=None,
    ):
        if corp_email == "random":
            corp_email = f"test+{uuid.uuid4()}@mavenclinic.com"
        if unique_corp_id == "random":
            unique_corp_id = f"{uuid.uuid4()}"

        if not dob:
            dob = datetime.date.today() - datetime.timedelta(
                days=random.choice(range(20, 500))
            )

        org = organization or self.test_case.org or self.org

        employee = OrganizationEmployee(
            date_of_birth=dob,
            email=corp_email,
            organization=org,
            organization_id=org.id if org else None,
            unique_corp_id=unique_corp_id,
            dependent_id=dependent_id,
            work_state=work_state,
            first_name=first_name,
            last_name=last_name,
            wallet_enabled=wallet_enabled,
        )
        if beneficiaries_enabled is not None:
            employee.beneficiaries_enabled = beneficiaries_enabled
        if can_get_pregnant is not None:
            employee.can_get_pregnant = can_get_pregnant
        if address is not None:
            employee.address = address
        if json is not None:
            employee.json = json
        db.session.add(employee)
        db.session.flush()
        return employee

    def add_organization_employee_dependent(
        self,
        organization_employee=None,
        first_name=None,
        middle_name=None,
        last_name=None,
    ):
        dependent = OrganizationEmployeeDependent(
            organization_employee=organization_employee,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
        )
        dependent.create_alegeus_dependent_id()
        db.session.add(dependent)
        db.session.flush()
        return dependent

    def add_user_organization_employee(self, user, organization_employee):
        user_organization_employee = UserOrganizationEmployee(
            user=user,
            organization_employee=organization_employee,
        )
        db.session.add(user_organization_employee)
        db.session.flush()
        return user_organization_employee

    def new_user(  # noqa: C901
        self,
        role=ROLES.member,
        vertical="Wellness Coach",
        password="simpleisawesome1*",
        active=True,
        state=None,
        username=None,
        user_id=None,
        first_name=None,
        last_name=None,
        email=None,
        created_at=None,
        otp_secret=None,
        api_key=None,
        country=None,
        show_when_unavailable=None,
        address=None,
        birthday=None,
        last_child_birthday=None,
        phone_number=None,
        care_team=None,
        user_flags=None,
        email_prefix=None,
        **practitioner_kwargs,
    ):
        user: User = self.UserFactory(email_prefix=email_prefix)
        user.password = encode_password(password)
        if username:
            user.username = username
        else:
            # make sure the factory username is unique:
            user.username += self._get_random_string(min_chars=5, max_chars=6)
        if user_id:
            user.id = username
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if email:
            user.email = email
        if created_at:
            user.created_at = created_at
        if otp_secret:
            user.otp_secret = otp_secret
        if api_key:
            user.api_key = api_key
        if active is not True:
            user.active = False

        add_profile_to_user(user=user, role_name=role, state=state, **vars(user))

        if birthday:
            set_date_of_birth(
                health_profile=user.health_profile, date_of_birth=birthday
            )

        if country or state:
            set_country_and_state(
                member_profile=user.member_profile, country=country, state=state
            )

        braze.track_user(user)

        if role not in {
            ROLES.member,
            ROLES.banned_member,
            ROLES.fertility_clinic_user,
            ROLES.fertility_clinic_billing_user,
        }:
            add_profile_to_user(user, ROLES.member, None, **vars(user))

        if user.practitioner_profile and role == ROLES.member:
            user.practitioner_profile = None

        db.session.add(user)
        db.session.flush()
        auth_service = authn.AuthenticationService()
        auth_service.create_auth_user(
            email=user.email,
            password=password,
            user_id=user.id,
        )

        if address:
            mp = user.member_profile
            mp.add_or_update_address(address)
            db.session.add(mp)
            db.session.flush()

        add_referral_code_for_user(user.id)
        add_schedule_for_user(user)

        h = HealthProfile(user=user, json={})
        if birthday:
            h.birthday = birthday
        if last_child_birthday:
            h.add_a_child(last_child_birthday)
        db.session.add(h)
        db.session.flush()

        if phone_number is not None:
            member_profile = user.member_profile
            member_profile.phone_number = phone_number
            db.session.add(member_profile)
            db.session.flush()

        if role == ROLES.practitioner:
            profile = user.practitioner_profile
            _vert = Vertical.query.filter_by(name=vertical).one_or_none()
            if not _vert:
                log.debug("No vertical named '%s'   .", vertical)

            assert _vert is not None

            profile.verticals.append(_vert)
            db.session.add(profile)
            db.session.flush()

            policy = CancellationPolicy.query.filter(
                CancellationPolicy.name == "moderate"
            ).first()
            profile.default_cancellation_policy = policy

            if show_when_unavailable:
                profile.show_when_unavailable = True

            profile.booking_buffer = 0
            db.session.add(profile)
            db.session.flush()

            if certified_subdivision_codes := practitioner_kwargs.get(
                "certified_subdivision_codes"
            ):
                for subdivision_code in certified_subdivision_codes:
                    profile.certified_states.append(
                        db.session.query(State)
                        .filter(State.abbreviation == subdivision_code.split("-")[-1])
                        .one()
                    )

                    practitioner_subdivision = PractitionerSubdivision.query.filter_by(
                        practitioner_id=user.id,
                        subdivision_code=subdivision_code,
                    ).one_or_none()

                    if not practitioner_subdivision:
                        practitioner_subdivision = PractitionerSubdivision(
                            practitioner_id=user.id,
                            subdivision_code=subdivision_code,
                        )
                        db.session.add(practitioner_subdivision)
                        db.session.flush()
            if (
                messaging_enabled := practitioner_kwargs.get("messaging_enabled")
                is not None
            ):
                profile.messaging_enabled = messaging_enabled
                db.session.add(profile)
                db.session.flush()
            if (
                anonymous_allowed := practitioner_kwargs.get("anonymous_allowed")
                is not None
            ):
                profile.anonymous_allowed = anonymous_allowed
                db.session.add(profile)
                db.session.flush()
            if (
                show_when_unavailable := practitioner_kwargs.get(
                    "show_when_unavailable"
                )
                is not None
            ):
                profile.show_when_unavailable = show_when_unavailable
                db.session.add(profile)
            if practitioner_kwargs.get("can_prescribe"):
                # This is our info on dosespot QA system
                profile.dosespot = {
                    "clinic_key": "DG9UMXALAS7MNXC9MNK6EF6F96MCEF2A",
                    "user_id": 482,
                    "clinic_id": 123977,
                }
                db.session.add(profile)
                db.session.flush()
            if (
                messaging_enabled := practitioner_kwargs.get("messaging_enabled")
                is not None
            ):
                profile.messaging_enabled = messaging_enabled
                db.session.add(profile)
                db.session.flush()
            if specialty_ids := practitioner_kwargs.get("specialty_ids"):
                specialties = db.session.query(Specialty).filter(
                    Specialty.id.in_(specialty_ids)
                )
                for specialty in specialties:
                    profile.specialties.append(specialty)
                db.session.add(profile)
                db.session.flush()
            if phone_number is not None:
                profile.phone_number = phone_number
                db.session.add(profile)
                db.session.flush()
            if experience_started := practitioner_kwargs.get("experience_started"):
                profile.experience_started = experience_started
            if education := practitioner_kwargs.get("education"):
                profile.education = education
            if reference_quote := practitioner_kwargs.get("reference_quote"):
                profile.reference_quote = reference_quote
            if awards := practitioner_kwargs.get("awards"):
                profile.awards = awards
            if work_experience := practitioner_kwargs.get("work_experience"):
                profile.work_experience = work_experience

        if care_team:
            for email in care_team:
                pp = (
                    db.session.query(PractitionerProfile)
                    .join(User)
                    .filter(User.email == email)
                    .one_or_none()
                )
                if not pp:
                    raise ValueError(
                        f"Invalid practitioner email provided for member care team: {email}"
                    )
                # NOTE: These Care Advocates can be overwritten when starting a new phase.
                # NOTE: See 'replace_care_coordinator_for_member' for replacement logic.
                user.add_practitioner_to_care_team(
                    pp.user_id, CareTeamTypes.CARE_COORDINATOR
                )

        for user_flag_name in user_flags or []:
            MemberRiskService(user).set_risk(user_flag_name)

        # upload the identities information to Auth0 app_metadata
        log.info(f"Start uploading the user [{user.id}] role information to Auth0")
        auth_service.update_user_roles(user_id=user.id, email=user.email)

        return user

    def add_event(self, practitioner, start=None, end=None):
        """
        Practitioner add availability
        :param practitioner:
        :param start:
        :param end:
        :return:
        """
        start = start or self.test_case.now
        end = end or self.test_case.p60

        data = {
            "state": "AVAILABLE",
            "starts_at": start.isoformat(),
            "ends_at": end.isoformat(),
        }

        res = self.client.post(
            f"/api/v1/practitioners/{practitioner.id}/schedules/events",
            data=self.json_data(data),
            headers=self.json_headers(practitioner),
        )

        return res

    def add_and_return_event(self, schedule=None, starts_at=None, ends_at=None):
        starts_at = starts_at or self.test_case.now
        ends_at = ends_at or starts_at + datetime.timedelta(minutes=60)

        if not schedule:
            if hasattr(self.test_case, "practitioner"):
                schedule = self.test_case.practitioner.schedule
            else:
                log.warning("Cannot add event without a schedule!")
                return

        e = ScheduleEvent(starts_at=starts_at, ends_at=ends_at, schedule=schedule)

        db.session.add(e)
        db.session.flush()
        return e

    def add_appointment(
        self,
        schedule_event=None,
        product=None,
        member_schedule=None,
        scheduled_start=None,
        cancellation_policy=None,
        privacy="full_access",
        privilege_type=PrivilegeType.STANDARD.value,
        state_match_type=StateMatchType.MISSING.value,
        purpose=None,
        **kwargs,
    ):
        if not schedule_event:
            schedule = kwargs.get("schedule")
            if not schedule:
                if kwargs.get("practitioner"):
                    schedule = kwargs["practitioner"].schedule

            schedule_event = (
                ScheduleEvent.query.first()
                or self.add_and_return_event(  # todo find matching schedule event?
                    schedule=schedule,
                    starts_at=kwargs.get("starts_at"),
                    ends_at=kwargs.get("ends_at"),
                )
            )

        if not schedule_event:
            log.info("No schedule event in add_appointment!")
            return

        if self.test_case:
            now = self.test_case.now
        else:
            now = datetime.datetime.utcnow().replace(microsecond=0)
        start = now + datetime.timedelta(minutes=10)
        scheduled_start = scheduled_start or start

        if not product:
            if kwargs.get("practitioner"):
                product = kwargs["practitioner"].products[0]
            elif hasattr(self.test_case, "practitioner"):
                product = self.test_case.practitioner.products[0]
            else:
                log.warning("Cannot add appt without a product!")
                return

        if not member_schedule:
            if hasattr(self.test_case, "member"):
                member_schedule = self.test_case.member.schedule
            else:
                log.warning("Cannot add appt without a member_schedule!")
                return

        if not cancellation_policy:
            cancellation_policy = CancellationPolicy.query.filter_by(
                name="moderate"
            ).one()

        if ("created_at" not in kwargs) and kwargs.get("create_in_past"):
            kwargs["created_at"] = self.test_case.m15
        if "create_in_past" in kwargs:
            del kwargs["create_in_past"]
        if "practitioner" in kwargs:
            del kwargs["practitioner"]

        a = Appointment(
            scheduled_start=scheduled_start,
            product=product,
            member_schedule=member_schedule,
            schedule_event=schedule_event,
            cancellation_policy=cancellation_policy,
            privilege_type=privilege_type,
            state_match_type=state_match_type,
            privacy=privacy,
            purpose=purpose,
            **kwargs,
        )
        db.session.add(a)
        db.session.flush()
        return a

    def new_credit(
        self,
        amount,
        user=None,
        expires_at=None,
        appointment=None,
        activated_at=None,
        used_at=None,
        referral_code_use=None,
        verification=None,
    ):
        user = user or self.test_case.member
        activated_at = activated_at or self.test_case.now

        credit = Credit(
            amount=amount,
            user=user,
            expires_at=expires_at,
            appointment=appointment,
            activated_at=activated_at,
            used_at=used_at,
            referral_code_use=referral_code_use,
            eligibility_verification_id=verification.verification_id
            if verification
            else None,
            eligibility_member_id=(
                verification.eligibility_member_id if verification else None
            ),
            eligibility_member_2_id=(
                verification.eligibility_member_2_id if verification else None
            ),
            eligibility_member_2_version=(
                verification.eligibility_member_2_version if verification else None
            ),
        )
        db.session.add(credit)
        return credit

    def add_address(self, user, address: dict):
        member_profile = user.member_profile
        address = member_profile.add_or_update_address(address)
        db.session.add(address)
        db.session.flush()

    def add_fertility_clinic_user_profile(self, user_id, first_name, last_name):
        fc_user_profile = FertilityClinicUserProfile(
            first_name=first_name,
            last_name=last_name,
            user_id=user_id,
            status=AccountStatus.ACTIVE,
        )
        db.session.add(fc_user_profile)
        db.session.flush()
        return fc_user_profile

    def add_fertility_clinic_user_profile_mapping(
        self, fertility_clinic_id, fertility_clinic_user_profile_id
    ):
        mapping = FertilityClinicUserProfileFertilityClinic(
            fertility_clinic_user_profile_id=fertility_clinic_user_profile_id,
            fertility_clinic_id=fertility_clinic_id,
        )
        db.session.add(mapping)
        db.session.flush()
        return mapping

    def add_and_map_fertility_clinic_user_profile_and_user(
        self, first_name, last_name, role, fertility_clinic_id, email_prefix, password
    ):
        user = self.new_user(
            role=role,
            email_prefix=email_prefix,
            first_name=first_name,
            last_name=last_name,
            password=password,
        )
        try:
            self._verify_email_domain_allowed(user.email, fertility_clinic_id)
        except ValueError as error:
            HealthProfile.query.filter(HealthProfile.user_id == user.id).delete()
            referral_code_ids = (
                ReferralCode.query.filter(ReferralCode.user_id == user.id)
                .with_entities(ReferralCodeValue.id)
                .subquery()
            )
            ReferralCodeValue.query.filter(
                ReferralCodeValue.code_id.in_(referral_code_ids)
            ).delete(synchronize_session="fetch")
            ReferralCode.query.filter(ReferralCode.user_id == user.id).delete()
            RoleProfile.query.filter(RoleProfile.user_id == user.id).delete()
            Schedule.query.filter(Schedule.user_id == user.id).delete()
            User.query.filter(User.id == user.id).delete()
            raise error

        profile = self.add_fertility_clinic_user_profile(
            user.id, user.first_name, user.last_name
        )
        return self.add_fertility_clinic_user_profile_mapping(
            fertility_clinic_id, profile.id
        )

    def _verify_email_domain_allowed(self, email, fertility_clinic_id):
        fc_allowed_domains = [
            ad.domain
            for ad in FertilityClinicAllowedDomain.query.filter(
                FertilityClinicAllowedDomain.fertility_clinic_id == fertility_clinic_id
            ).all()
        ]

        if email.partition("@")[-1] not in fc_allowed_domains:
            raise ValueError(
                f"Cannot create profile for {email} - it is not on an allowed domain for clinic {fertility_clinic_id} ({fc_allowed_domains})"
            )


@contextmanager
def e9y_get_verification(
    user, employee, active_verification_only: bool = False, effective_range=None
):
    if active_verification_only and effective_range is None:
        verification = None
    else:
        verification = (
            model.EligibilityVerification(
                user_id=user.id,
                organization_id=employee.organization_id,
                unique_corp_id=employee.unique_corp_id,
                dependent_id=employee.dependent_id,
                eligibility_member_id=employee.eligibility_member_id,
                first_name=employee.first_name,
                last_name=employee.last_name,
                date_of_birth=employee.date_of_birth,
                email=employee.email,
                work_state=employee.work_state,
                record=employee.json,
                created_at=employee.created_at,
                verified_at=employee.created_at,
                verification_type="ORGANIZATION_EMPLOYEE",
                is_active=employee.deleted_at is None,
                effective_range=effective_range,
                verification_id=1,
            )
            if employee and user
            else None
        )
    with patch(
        "eligibility.e9y.grpc_service.get_verification", return_value=verification
    ) as p:
        yield p


@contextmanager
def e9y_no_population():
    with patch(
        "eligibility.e9y.grpc_service.get_sub_population_id_for_user_and_org",
        return_value=None,
    ), patch(
        "eligibility.e9y.grpc_service.get_eligible_features_for_user_and_org",
        return_value=model.EligibleFeaturesForUserAndOrgResponse(
            features=[],
            has_population=False,
        ),
    ), patch(
        "eligibility.e9y.grpc_service.get_eligible_features_by_sub_population_id",
        return_value=model.EligibleFeaturesBySubPopulationIdResponse(
            features=[],
            has_definition=False,
        ),
    ):
        yield
