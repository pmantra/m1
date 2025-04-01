import uuid
from datetime import datetime

import factory
from factory.alchemy import SQLAlchemyModelFactory

from conftest import BaseMeta
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
    PayerReportStatus,
)
from payer_accumulator.models.payer_list import Payer


class AccumulationTreatmentMappingFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AccumulationTreatmentMapping

    treatment_procedure_uuid = str(uuid.uuid4())
    payer_id = 123456


class PayerAccumulationReportsFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = PayerAccumulationReports

    filename = "test_file"
    report_date = datetime.now().strftime("%Y%m%d")
    status = PayerReportStatus.NEW


class PayerFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Payer

    id = factory.Faker("random_int", min=1)
