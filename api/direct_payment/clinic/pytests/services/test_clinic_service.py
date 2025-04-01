from direct_payment.clinic.services.clinic import FertilityClinicService


def test_get_global_procedure_ids_for_clinic(fertility_clinic, session):
    service = FertilityClinicService(session)
    global_procedures = service.get_global_procedure_ids_and_costs_for_clinic(
        fertility_clinic_id=fertility_clinic.id
    )
    expected = (
        fertility_clinic.fee_schedule.fee_schedule_global_procedures
        if fertility_clinic.fee_schedule
        else []
    )
    assert len(global_procedures) == len(expected)
    for gp in global_procedures:
        assert gp["procedure_id"] in expected
