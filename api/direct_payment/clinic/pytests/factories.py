import uuid

import factory
from factory.alchemy import SQLAlchemyModelFactory

from conftest import BaseMeta
from direct_payment.clinic.models.clinic import (
    FertilityClinic,
    FertilityClinicAllowedDomain,
    FertilityClinicLocation,
    FertilityClinicLocationContact,
)
from direct_payment.clinic.models.fee_schedule import (
    FeeSchedule,
    FeeScheduleGlobalProcedures,
)
from direct_payment.clinic.models.user import (
    AccountStatus,
    FertilityClinicUserProfile,
    FertilityClinicUserProfileFertilityClinic,
)


class FeeScheduleFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = FeeSchedule

    name = factory.Faker("name")


class FeeScheduleGlobalProceduresFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = FeeScheduleGlobalProcedures

    fee_schedule = factory.SubFactory(FeeScheduleFactory)


class FertilityClinicAllowedDomainFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = FertilityClinicAllowedDomain

    domain = "mavenclinic.com"


class FertilityClinicLocationContactFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = FertilityClinicLocationContact


class FertilityClinicLocationFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = FertilityClinicLocation

    name = "name"
    address_1 = "123 Main St"
    city = "New York City"
    subdivision_code = "US-NY"
    postal_code = "11111"
    country_code = "US"
    fertility_clinic = factory.SubFactory(
        "direct_payment.clinic.pytests.factories.FertilityClinicFactory"
    )


class FertilityClinicFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = FertilityClinic

    name = factory.Faker("name")
    affiliated_network = "network"
    payments_recipient_id = str(uuid.uuid4())
    fee_schedule = factory.SubFactory(
        "direct_payment.clinic.pytests.factories.FeeScheduleFactory"
    )
    notes = factory.Faker("text")

    @factory.post_generation
    def default_locations(self, create, _, **__):
        FertilityClinicLocationFactory(fertility_clinic=self)

    @factory.post_generation
    def default_allowed_domains(self, create, _, **__):
        FertilityClinicAllowedDomainFactory(fertility_clinic=self)


class FertilityClinicUserProfileFertilityClinicFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = FertilityClinicUserProfileFertilityClinic


class FertilityClinicUserProfileFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = FertilityClinicUserProfile

    first_name = factory.Faker("name")
    last_name = factory.Faker("name")
    user_id = factory.Sequence(lambda n: n + 1)
    status = AccountStatus.ACTIVE
