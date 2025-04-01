from unittest import mock

from payer_accumulator.tasks.rq_payer_accumulation_data_sourcing import (
    cigna_data_sourcing,
    esi_data_sourcing,
    uhc_data_sourcing,
)


class TestRqPayerAccumulationDataSourcing:
    def test_cigna_data_sourcing_success(self, cigna_payer):
        with mock.patch(
            "payer_accumulator.accumulation_data_sourcer.AccumulationDataSourcer.data_source_preparation_for_file_generation"
        ) as data_sourcer:
            cigna_data_sourcing()
            data_sourcer.assert_called_once()

    def test_esi_data_sourcing_success(self, esi_payer):
        with mock.patch(
            "payer_accumulator.accumulation_data_sourcer_esi.AccumulationDataSourcerESI.data_source_preparation_for_file_generation"
        ) as data_sourcer:
            esi_data_sourcing()
            data_sourcer.assert_called_once()

    def test_uhc_data_sourcing_success(self, uhc_payer):
        with mock.patch(
            "payer_accumulator.accumulation_data_sourcer.AccumulationDataSourcer.data_source_preparation_for_file_generation"
        ) as data_sourcer:
            uhc_data_sourcing()
            data_sourcer.assert_called_once()
