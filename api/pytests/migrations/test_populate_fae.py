from appointments.models.payments import FeeAccountingEntryTypes
from utils.migrations.populate_fae_type import populate_fae_type_values


class TestPopulateFaeTypes:
    def test_populate_fae_types(self, factories, default_user):

        appointment_fee = factories.AppointmentFactory()
        fee_appt = factories.FeeAccountingEntryFactory(
            appointment=appointment_fee, type=FeeAccountingEntryTypes.UNKNOWN
        )
        assert fee_appt.appointment_id is not None

        message = factories.MessageFactory()
        fee_msg = factories.FeeAccountingEntryFactory(
            message=message, type=FeeAccountingEntryTypes.UNKNOWN
        )
        assert fee_msg.message.id is not None

        practitioner_fee = factories.FeeAccountingEntryFactory(
            practitioner=default_user, type=FeeAccountingEntryTypes.UNKNOWN
        )
        practitioner_fee.amount = 9900
        assert practitioner_fee.practitioner_id is not None

        malpractice_fee = factories.FeeAccountingEntryFactory(
            practitioner=default_user, type=FeeAccountingEntryTypes.UNKNOWN
        )
        assert malpractice_fee.practitioner_id is not None
        malpractice_fee.amount = -10.00

        # run the populate script; make assertions
        populate_fae_type_values()

        assert fee_msg.type == FeeAccountingEntryTypes.MESSAGE
        assert fee_appt.type == FeeAccountingEntryTypes.APPOINTMENT
        assert practitioner_fee.type == FeeAccountingEntryTypes.ONE_OFF
        assert malpractice_fee.type == FeeAccountingEntryTypes.MALPRACTICE
