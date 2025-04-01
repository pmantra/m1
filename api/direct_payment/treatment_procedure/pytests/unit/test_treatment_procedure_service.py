from datetime import datetime

import pytest

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests import factories
from direct_payment.treatment_procedure.treatment_procedure_service import (
    TreatmentProcedureService,
)


@pytest.fixture
def test_procedures():
    dt_fmt = "%d/%m/%Y %H:%M"
    procedures = [
        factories.TreatmentProcedureFactory.create(
            uuid="9b2e178d-aaf7-47db-8ae7-d56c8efe8da2",
            status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
            reimbursement_wallet_id=1,
            completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
            procedure_type=TreatmentProcedureType.PHARMACY,
        ),
        factories.TreatmentProcedureFactory.create(
            uuid="29d597db-d657-4ba8-953e-c5999abf2cb5",
            status=TreatmentProcedureStatus.COMPLETED,
            reimbursement_wallet_id=1,
            completed_date=datetime.strptime("15/11/2018 16:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.SCHEDULED,
            reimbursement_wallet_id=1,
            completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
            reimbursement_wallet_id=2,
            completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED,
            reimbursement_wallet_id=2,
            completed_date=datetime.strptime("15/11/2018 16:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.SCHEDULED,
            reimbursement_wallet_id=2,
            completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
    ]
    return procedures


@pytest.fixture
def treatment_procedure_service(session):
    return TreatmentProcedureService(session=session)


def test_get_treatment_procedure_by_ids(test_procedures, treatment_procedure_service):
    tp_id_to_tp_map = {procedure.id: procedure for procedure in test_procedures}

    for procedure in test_procedures:
        tp_id = procedure.id
        expected_procedure = tp_id_to_tp_map.get(tp_id)

        results = treatment_procedure_service.get_treatment_procedure_by_ids([tp_id])

        assert len(results) == 1
        assert expected_procedure == results[0]
