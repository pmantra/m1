import datetime
from datetime import date

import factory
from factory.alchemy import SQLAlchemyModelFactory

from conftest import BaseMeta
from direct_payment.clinic.models.questionnaire_global_procedure import (
    QuestionnaireGlobalProcedure,
)
from direct_payment.clinic.pytests.factories import (
    FeeScheduleFactory,
    FertilityClinicFactory,
    FertilityClinicLocationFactory,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.models.treatment_proceedure_needing_questionnaire import (
    TreatmentProceduresNeedingQuestionnaires,
)
from pytests.factories import QuestionnaireFactory
from wallet.models.constants import PatientInfertilityDiagnosis
from wallet.pytests.factories import ReimbursementRequestCategoryFactory


class TreatmentProceduresNeedingQuestionnairesFactory(SQLAlchemyModelFactory):
    class Meta:
        model = TreatmentProceduresNeedingQuestionnaires


class TreatmentProcedureFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = TreatmentProcedure

    member_id = 1
    infertility_diagnosis = PatientInfertilityDiagnosis.MEDICALLY_INFERTILE
    reimbursement_wallet_id = 2
    reimbursement_request_category = factory.SubFactory(
        ReimbursementRequestCategoryFactory, label="fertility"
    )
    fee_schedule = factory.SubFactory(FeeScheduleFactory)
    fertility_clinic = factory.SubFactory(
        FertilityClinicFactory, fee_schedule=factory.SelfAttribute("..fee_schedule")
    )
    fertility_clinic_location = factory.SubFactory(
        FertilityClinicLocationFactory,
        fertility_clinic=factory.SelfAttribute("..fertility_clinic"),
    )
    procedure_name = "IVF"
    procedure_type = TreatmentProcedureType.MEDICAL
    global_procedure_id = "3438e493-8a48-476f-8c60-09cf73568eeb"
    cost = 10000
    status = TreatmentProcedureStatus.SCHEDULED
    start_date = date.today()
    created_at = datetime.datetime.now()


class QuestionnaireGlobalProcedureFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = QuestionnaireGlobalProcedure

    id = factory.Sequence(lambda n: n + 1)
    global_procedure_id = factory.Faker("uuid4")
    questionnaire = factory.SubFactory(QuestionnaireFactory)
