from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Optional

import factory

from eligibility import repository, web
from eligibility.e9y import model
from eligibility.utils import verification_utils
from models.enterprise import MatchType, OrganizationEligibilityType


class DummyIdentityFactory(factory.Factory):
    class Meta:
        model = SimpleNamespace

    identity_provider_id = factory.Sequence(lambda n: n + 1)
    external_user_id = factory.Faker("swift11")
    external_organization_id = factory.Faker("swift11")
    unique_corp_id = factory.Faker("swift11")


class VerificationParams(factory.Factory):
    class Meta:
        model = verification_utils.VerificationParams

    user_id = factory.Faker("swift11")
    verification_type = "multistep"
    organization_id = factory.Faker("swift11")
    is_employee = factory.Faker("boolean")
    date_of_birth = factory.Faker("date")
    dependent_date_of_birth = factory.Faker("date")
    company_email = factory.Faker("email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    work_state = factory.Faker("state")
    unique_corp_id = factory.Faker("swift11")
    employee_first_name = factory.Faker("first_name")
    employee_last_name = factory.Faker("last_name")
    verification_type_v2 = "multistep"

    @classmethod
    def create(cls, **kwargs):
        # Allow overriding verification types
        verification_type = kwargs.pop("verification_type", "multistep")
        verification_type_v2 = kwargs.pop("verification_type_v2", "multistep")

        # Create the instance with updated verification types
        return super().create(
            verification_type=verification_type or verification_type_v2,
            verification_type_v2=verification_type_v2,
            **kwargs,
        )


class BasicVerificationParams(factory.Factory):
    class Meta:
        model = dict

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    date_of_birth = factory.Faker("date_of_birth")


class EmployerVerificationParams(factory.Factory):
    class Meta:
        model = dict

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    date_of_birth = factory.Faker("date_of_birth")
    company_email = factory.Faker("company_email")
    work_state = factory.Faker("state_abbr")


class HealthPlanVerificationParams(factory.Factory):
    class Meta:
        model = dict

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    date_of_birth = factory.Faker("date_of_birth")
    unique_corp_id = factory.Faker("swift11")


class AlternateVerificationParams(factory.Factory):
    class Meta:
        model = dict

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    work_state = factory.Faker("state_abbr")
    date_of_birth = factory.Faker("date_of_birth")
    unique_corp_id = factory.Faker("swift11")


class StandardVerificationParams(factory.Factory):
    class Meta:
        model = dict

    company_email = factory.Faker("company_email")
    date_of_birth = factory.Faker("date_of_birth")


class ClientSpecificParams(factory.Factory):
    class Meta:
        model = dict

    organization_id = factory.Sequence(lambda n: str(n + 1))
    unique_corp_id = factory.Faker("swift11")
    is_employee = True
    date_of_birth = factory.Faker("date_of_birth")
    dependent_date_of_birth = None


class OvereligibilityVerificationParams(factory.Factory):
    class Meta:
        model = dict

    date_of_birth = factory.Faker("date_of_birth")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    unique_corp_id = factory.Faker("swift11")
    company_email = factory.Faker("company_email")
    user_id = factory.Sequence(lambda n: str(n + 1))


class NoDOBVerificationParams(factory.Factory):
    class Meta:
        model = dict

    company_email = factory.Faker("company_email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")


class FilelessInviteVerificationParams(factory.Factory):
    class Meta:
        model = dict

    user_id = factory.Faker("swift11")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    date_of_birth = factory.Faker("date_of_birth")
    company_email = factory.Faker("company_email")
    is_dependent = False


class EnterpriseEligibilitySettingsFactory(factory.Factory):
    class Meta:
        model = repository.EnterpriseEligibilitySettings

    organization_id = factory.Sequence(lambda n: n + 1)
    organization_name = factory.Faker("company")
    organization_shortname = factory.Faker("company")
    organization_logo = "company.img"
    eligibility_type = OrganizationEligibilityType.STANDARD
    employee_only = False
    medical_plan_only = False
    fields = factory.SubFactory(factory.ListFactory)
    email_domains = factory.SubFactory(factory.ListFactory)


class ServiceVerificationParametersFactory(factory.Factory):
    class Meta:
        model = web.ServiceVerificationParameters

    date_of_birth = None
    dependent_date_of_birth = None
    company_email = None
    work_state = None
    first_name = None
    last_name = None
    unique_corp_id = None
    organization_id = None
    is_employee = None
    eligibility_member_id = None
    verification_creator = None
    verification_type_v2 = None
    zendesk_id = None
    employee_first_name = None
    employee_last_name = None


class DateRangeFactory(factory.Factory):
    class Meta:
        model = model.DateRange

    upper = factory.Faker("date_object")
    lower = factory.Faker("date_object")
    lower_inc = False
    upper_inc = False


class RecordFactory(factory.Factory):
    class Meta:
        model = dict

    address_1 = factory.Faker("street_address")
    address_2 = "Floor 3"
    city = factory.Faker("city")
    state = factory.Faker("state_abbr")
    country = factory.Faker("country_code")
    work_country = factory.Faker("country_code")
    zip_code = factory.Faker("postcode")
    beneficiaries_enabled = factory.Faker("boolean")
    can_get_pregnant = factory.Faker("boolean")
    cobra_coverage = factory.Faker("boolean")
    company_couple = factory.Faker("boolean")
    wallet_enabled = factory.Faker("boolean")
    dependent_relationship_code = "self"
    lob = factory.Faker("word")
    office_id = factory.Faker("swift11")
    option = factory.Faker("catch_phrase")
    plan_carrier = factory.Faker("company")
    salary_tier = "Ultimate"


class EligibilityMemberFactory(factory.Factory):
    class Meta:
        model = model.EligibilityMember

    id = factory.Sequence(lambda n: n + 1)
    organization_id = factory.Sequence(lambda n: n + 2)
    file_id = factory.Sequence(lambda n: n + 3)
    first_name: str = factory.Faker("first_name")
    last_name: str = factory.Faker("last_name")
    date_of_birth = factory.Faker("date_of_birth")
    created_at = factory.Faker("date_time")
    updated_at = factory.Faker("date_time")
    record = factory.SubFactory(RecordFactory)
    custom_attributes = factory.Faker("pydict", value_types=["str"])
    work_state = factory.Faker("state_abbr")
    work_country = factory.Faker("country_code")
    email: str = factory.Faker("ascii_company_email")
    unique_corp_id: str = factory.Faker("swift11")
    dependent_id: str = factory.Faker("swift11")
    employer_assigned_id: str = factory.Faker("swift11")
    effective_range = factory.SubFactory(DateRangeFactory)
    is_v2: bool = factory.Faker("boolean")
    member_1_id: Optional[int] = None
    member_2_id: Optional[int] = None
    member_2_version: Optional[int] = None


class WalletEnablementFactory(factory.Factory):
    class Meta:
        model = model.WalletEnablement

    member_id = factory.Sequence(int)
    organization_id = factory.Sequence(int)
    enabled = factory.Faker("boolean")
    insurance_plan = factory.Faker("bs")
    start_date = factory.Faker("past_date")
    eligibility_date = factory.Faker("date_this_month")
    eligibility_end_date = factory.Faker("future_date")
    created_at = factory.Faker("date_time")
    updated_at = factory.Faker("date_time")


class OrganizationMetaFactory(factory.Factory):
    class Meta:
        model = repository.OrganizationMeta

    organization_id = factory.Sequence(lambda n: n + 1)
    organization_name = factory.Faker("company")
    external_id = factory.Faker("swift11")


class VerificationFactory(factory.Factory):
    class Meta:
        model = model.EligibilityVerification

    verification_id = factory.Sequence(int)
    user_id = factory.Sequence(int)
    organization_id = factory.Sequence(int)
    unique_corp_id = factory.Faker("swift11")
    date_of_birth = factory.Faker("date_of_birth")
    verification_type = factory.Faker("word")
    effective_range = factory.SubFactory(DateRangeFactory)
    created_at = factory.Faker("date_time")
    verified_at = factory.Faker("date_time")
    deactivated_at = factory.Faker("date_time")
    dependent_id = factory.Faker("swift11")
    eligibility_member_id = factory.Sequence(int)
    work_state = factory.Faker("state_abbr")
    email = factory.Faker("ascii_company_email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    record = factory.SubFactory(RecordFactory)
    is_active = True
    deactivated_at = None
    additional_fields = {"is_employee": True}
    verification_session = factory.Faker("uuid4")
    is_v2: bool = factory.Faker("boolean")
    verification_1_id: Optional[int] = None
    verification_2_id: Optional[int] = None
    eligibility_member_2_id: Optional[int] = None
    eligibility_member_2_version: Optional[int] = None

    @factory.post_generation
    def active_effective_range(
        self: model.EligibilityVerification, create, is_active, **kwargs
    ):
        if create:
            upper = (
                datetime.now(timezone.utc).date() + timedelta(days=365)
                if is_active
                else datetime.now(timezone.utc).date() - timedelta(days=1)
            )
            self.effective_range = model.DateRange(
                lower=datetime.now(timezone.utc).date() - timedelta(days=365),
                upper=upper,
                upper_inc=True,
                lower_inc=True,
            )


class VerificationAttemptFactory(factory.Factory):
    class Meta:
        model = model.EligibilityVerificationAttempt

    user_id = factory.Sequence(int)
    organization_id = factory.Sequence(int)
    unique_corp_id = factory.Faker("swift11")
    dependent_id = factory.Faker("swift11")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    date_of_birth = factory.Faker("date_of_birth")
    email = factory.Faker("ascii_company_email")
    work_state = factory.Faker("state_abbr")
    policy_used = ""
    verified_at = factory.Faker("date_time")
    created_at = factory.Faker("date_time")
    verification_type = factory.Faker("word")
    successful_verification = False
    id = factory.Sequence(int)
    eligibility_member_id = factory.Sequence(int)
    additional_fields = {"is_employee": True}


class PreEligibilityOrganizationFactory(factory.Factory):
    class Meta:
        model = model.PreEligibilityOrganization

    organization_id = factory.Sequence(int)
    eligibility_end_date = factory.Faker("date_time")


class PreEligibilityResponseFactory(factory.Factory):
    class Meta:
        model = model.PreEligibilityResponse

    match_type = MatchType.UNKNOWN_ELIGIBILITY
    pre_eligibility_organizations = []


def build_verification_from_oe(user_id: int, employee) -> model.EligibilityVerification:
    verification = VerificationFactory.create(
        user_id=user_id,
        organization_id=employee.organization_id,
        unique_corp_id=(
            employee.unique_corp_id if employee.unique_corp_id is not None else ""
        ),
        dependent_id=employee.dependent_id,
        eligibility_member_id=employee.eligibility_member_id,
        first_name=employee.first_name if employee.first_name is not None else "",
        last_name=employee.last_name if employee.last_name is not None else "",
        date_of_birth=employee.date_of_birth,
        email=employee.email if employee.email is not None else "",
        work_state=employee.work_state,
        record=employee.json,
        created_at=employee.created_at,
        verified_at=employee.created_at,
        verification_type="MOCKED_VERIFICATION_TYPE",
        is_active=employee.deleted_at is None,
        effective_range=model.DateRange(
            lower=datetime.utcnow().date() - timedelta(days=365),
            upper=datetime.utcnow().date() + timedelta(days=365),
            upper_inc=True,
            lower_inc=True,
        ),
    )
    return verification


def build_verification_from_member(user_id: int, member):
    verification = VerificationFactory.create(
        user_id=user_id,
        organization_id=member.organization_id,
        unique_corp_id=member.unique_corp_id,
        dependent_id=member.dependent_id,
        eligibility_member_id=member.id,
        first_name=member.first_name,
        last_name=member.last_name,
        date_of_birth=member.date_of_birth,
        email=member.email,
        work_state=member.work_state,
        record=member.record,
        created_at=member.created_at,
        verified_at=member.created_at,
        verification_type="MOCKED_VERIFICATION_TYPE",
        is_active=True,
        effective_range=None,
    )
    return verification


def build_verification_from_wallet(wallet, created_at=None):
    verification = VerificationFactory.create(
        user_id=wallet.user_id,
        organization_id=wallet.reimbursement_organization_settings.organization_id,
        unique_corp_id="",
        dependent_id="",
        created_at=created_at if created_at else wallet.created_at,
        verified_at=created_at if created_at else wallet.created_at,
        verification_type="MOCKED_VERIFICATION_TYPE",
        effective_range=model.DateRange(
            lower=datetime.utcnow().date() - timedelta(days=365),
            upper=datetime.utcnow().date() + timedelta(days=365),
            upper_inc=True,
            lower_inc=True,
        ),
    )
    return verification


def build_dependent_verification(user_id: int, organization_id: int):
    verificaiton = VerificationFactory.create(
        user_id=user_id,
        organization_id=organization_id,
        record={"dependent_relationship_code": "Dependent"},
        effective_range=model.DateRange(
            lower=datetime.utcnow().date() - timedelta(days=365),
            upper=datetime.utcnow().date() + timedelta(days=365),
            upper_inc=True,
            lower_inc=True,
        ),
    )
    return verificaiton
