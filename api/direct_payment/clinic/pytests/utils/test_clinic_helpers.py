from direct_payment.clinic.models.fee_schedule import FeeSchedule
from direct_payment.clinic.pytests.factories import FeeScheduleFactory
from direct_payment.clinic.utils.clinic_helpers import duplicate_fee_schedule


def test_duplicate_fee_schedule_success(fee_schedule_global_procedure):
    # Setup initial FeeSchedule and associated Global Procedures
    original_fee_schedule = fee_schedule_global_procedure.fee_schedule
    original_fsgp = original_fee_schedule.fee_schedule_global_procedures

    # Duplicate
    messages, success, cloned_fee_schedule_id = duplicate_fee_schedule(
        original_fee_schedule
    )
    cloned_fee_schedule = FeeSchedule.query.get(cloned_fee_schedule_id)
    cloned_fsgp = cloned_fee_schedule.fee_schedule_global_procedures

    # Assert success and duplicated FeeSchedule and associations have new ids and same data
    assert success
    assert original_fee_schedule.id != cloned_fee_schedule.id
    assert len(original_fsgp) == len(cloned_fsgp)
    assert cloned_fsgp[0].fee_schedule_id == cloned_fee_schedule.id
    assert cloned_fee_schedule.name == f"COPY {original_fee_schedule.name}"
    assert float(cloned_fsgp[0].cost) == fee_schedule_global_procedure.cost
    assert messages[0].message == "Successfully duplicated Fee Schedule!"


def test_duplicate_fee_schedule_fee_schedule_fails():
    # Test No fee schedule passed
    messages, success, cloned_fee_schedule_id = duplicate_fee_schedule(None)

    # Assert success is false and an error message is flashed
    assert success is False
    assert cloned_fee_schedule_id is None
    assert (
        messages[0].message
        == "Unable to duplicate Fee Schedule. Please check a copy doesn't already exist."
    )


def test_duplicate_fee_schedule_global_procedures_fails(fee_schedule_global_procedure):
    # Setup initial FeeSchedule and associated Global Procedures but remove cost to invalidate GP
    original_fee_schedule = fee_schedule_global_procedure.fee_schedule

    original_fsgps = original_fee_schedule.fee_schedule_global_procedures
    original_fsgps[0].cost = None

    # Duplicate
    messages, success, cloned_fee_schedule_id = duplicate_fee_schedule(
        original_fee_schedule
    )

    # Assert success is false and an error message is flashed
    assert success is False
    assert cloned_fee_schedule_id is None
    assert messages[0].message == "Unable to duplicate Global Procedures."


def test_duplicate_empty_fee_schedule_success(fee_schedule_global_procedure):
    original_fee_schedule = FeeScheduleFactory()

    # Duplicate
    messages, success, cloned_fee_schedule_id = duplicate_fee_schedule(
        original_fee_schedule
    )
    cloned_fee_schedule = FeeSchedule.query.get(cloned_fee_schedule_id)
    cloned_fsgp = cloned_fee_schedule.fee_schedule_global_procedures

    # Assert success and duplicated FeeSchedule and associations have new ids and same data
    assert success
    assert original_fee_schedule.id != cloned_fee_schedule.id
    assert len(cloned_fsgp) == 0
    assert cloned_fee_schedule.name == f"COPY {original_fee_schedule.name}"
    assert messages[0].message == "Successfully duplicated Fee Schedule!"
