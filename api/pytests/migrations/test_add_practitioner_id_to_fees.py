from unittest import mock

from utils.migrations.add_practitioner_id_to_fees import (
    add_practitioner_id_to_fees,
    add_practitioner_id_to_fees_chunk,
)


class TestAddPractitionerIdToFees:
    def test_add_practitioner_id_to_all_fees(self, factories, default_user):
        with mock.patch(
            "utils.migrations.add_practitioner_id_to_fees.add_practitioner_id_to_fees_chunk"
        ) as add_practitioner_id_to_fees_chunk_mock:

            fee = factories.FeeAccountingEntryFactory(practitioner=default_user)
            fee.practitioner_id = None

            assert fee.recipient.id is not None
            assert fee.practitioner_id is None

            add_practitioner_id_to_fees()

            add_practitioner_id_to_fees_chunk_mock.delay.assert_called_with([fee.id])

    def test_add_practitioner_id_to_fees_chunk(self, factories, default_user):
        fee = factories.FeeAccountingEntryFactory(practitioner=default_user)
        fee.practitioner_id = None

        assert fee.recipient.id is not None
        assert fee.practitioner_id is None

        add_practitioner_id_to_fees_chunk(fees_ids=[fee.id])

        assert fee.practitioner_id is not None
        assert fee.recipient.id == fee.practitioner_id
