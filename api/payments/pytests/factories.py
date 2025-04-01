import factory
from factory import base

from conftest import BaseMeta
from payments.models.contract_validator import ContractValidator
from payments.models.practitioner_contract import ContractType, PractitionerContract
from pytests.factories import postiveint

SQLAlchemyModelFactory = factory.alchemy.SQLAlchemyModelFactory


class PractitionerContractFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = PractitionerContract

    created_by_user_id = factory.Sequence(postiveint)
    contract_type = ContractType.BY_APPOINTMENT
    start_date = factory.Faker("date_object")


class ContractValidatorFactory(base.Factory):
    class Meta(BaseMeta):
        model = ContractValidator
