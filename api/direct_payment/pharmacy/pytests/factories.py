import datetime

import factory

from direct_payment.pharmacy.models.health_plan_ytd_spend import (
    HealthPlanYearToDateSpend,
)
from direct_payment.pharmacy.models.pharmacy_prescription import (
    PharmacyPrescription,
    PrescriptionStatus,
)


class PharmacyPrescriptionFactory(factory.Factory):
    class Meta:
        model = PharmacyPrescription

    status = PrescriptionStatus.SCHEDULED
    rx_unique_id = factory.Faker("word")
    maven_benefit_id = factory.Faker("word")
    amount_owed = factory.Faker("random_int", min=1)
    ncpdp_number = factory.Faker("word")
    ndc_number = factory.Faker("word")
    rx_name = factory.Faker("word")
    rx_description = factory.Faker("text")
    rx_first_name = factory.Faker("first_name")
    rx_last_name = factory.Faker("last_name")
    rx_order_id = factory.Faker("word")
    rx_received_date = datetime.datetime.now()
    scheduled_ship_date = datetime.datetime.now()
    # default fields
    created_at = datetime.datetime.now()
    modified_at = datetime.datetime.now()


class HealthPlanYearToDateSpendFactory(factory.Factory):
    class Meta:
        model = HealthPlanYearToDateSpend

    id = factory.Faker("random_int", min=1)
    policy_id = factory.Faker("word")
    year = 2023
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    source = "MAVEN"
    plan_type = "INDIVIDUAL"
    deductible_applied_amount = 0
    oop_applied_amount = 0
    bill_id = factory.Faker("random_int", min=1)
    transmission_id = factory.Faker("random_int", min=1)
    transaction_filename = factory.Faker("word")
    created_at = datetime.datetime.now()
    modified_at = datetime.datetime.now()
