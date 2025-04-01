from unittest import mock

import pytest

from payer_accumulator.constants import ACCUMULATION_FILE_BUCKET
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
    PayerReportStatus,
)
from payer_accumulator.pytests.factories import PayerAccumulationReportsFactory
from payer_accumulator.tasks.rq_payer_accumulation_file_generation import (
    aetna_accumulation_file_generation,
    cigna_accumulation_file_generation,
    esi_accumulation_file_generation,
    uhc_accumulation_file_generation,
)
from pytests.freezegun import freeze_time


@pytest.fixture(scope="function")
def mock_aetna_file_generator():
    with mock.patch(
        "payer_accumulator.edi.edi_837_accumulation_file_generator.EDI837AccumulationFileGenerator"
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_anthem_file_generator():
    with mock.patch(
        "payer_accumulator.file_generators.AccumulationFileGeneratorAnthem"
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_cigna_file_generator():
    with mock.patch(
        "payer_accumulator.file_generators.AccumulationFileGeneratorCigna"
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_esi_file_generator():
    with mock.patch(
        "payer_accumulator.file_generators.ESIAccumulationFileGenerator"
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_uhc_file_generator():
    with mock.patch(
        "payer_accumulator.file_generators.AccumulationFileGeneratorUHC"
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_accumulation_file_handler():
    with mock.patch("payer_accumulator.file_handler.AccumulationFileHandler") as m:
        yield m


class TestRqPayerAccumulation:
    @freeze_time("2023-01-01 00:00:00")
    def test_esi_payer_accumulation_success(
        self, esi_payer, mock_esi_file_generator, mock_accumulation_file_handler
    ):
        payer_accumulation_report = PayerAccumulationReportsFactory.create(
            payer_id=esi_payer.id
        )
        file_name = payer_accumulation_report.filename
        mock_esi_file_generator.file_name = file_name

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationReportService.get_generator_class_for_payer_name",
            return_value=mock_esi_file_generator,
        ), mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            esi_accumulation_file_generation()
            mock_esi_file_generator.generate_file_contents.assert_called_once()
            mock_accumulation_file_handler.upload_file.assert_called_once_with(
                content=mock_esi_file_generator.generate_file_contents(),
                filename=payer_accumulation_report.file_path(),
                bucket=ACCUMULATION_FILE_BUCKET,
            )
            self.validate_report_status(
                payer_accumulation_report.id, PayerReportStatus.NEW
            )

    def test_esi_payer_accumulation_generator_failed(self, esi_payer):
        upload_file = mock.MagicMock()
        with mock.patch(
            "payer_accumulator.file_generators.ESIAccumulationFileGenerator.generate_file_contents",
        ) as generate_file, mock.patch(
            "payer_accumulator.file_handler.AccumulationFileHandler",
            return_value=mock.Mock(upload_file=upload_file),
        ):
            generate_file.side_effect = Exception("error generating ESI report")
            esi_accumulation_file_generation()
            generate_file.assert_called_once()
            assert upload_file.call_count == 0

    @freeze_time("2023-01-01 00:00:00")
    def test_esi_payer_accumulation_gcs_upload_failed(
        self, esi_payer, mock_esi_file_generator, mock_accumulation_file_handler
    ):
        payer_accumulation_report = PayerAccumulationReportsFactory.create(
            payer_id=esi_payer.id
        )
        file_name = payer_accumulation_report.filename
        mock_esi_file_generator.file_name = file_name

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationReportService.get_generator_class_for_payer_name",
            return_value=mock_esi_file_generator,
        ), mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            mock_accumulation_file_handler.upload_file.side_effect = Exception(
                "error upload to ECS bucket"
            )
            esi_accumulation_file_generation()
            mock_esi_file_generator.generate_file_contents.assert_called_once()
            mock_accumulation_file_handler.upload_file.assert_called_once_with(
                content=mock_esi_file_generator.generate_file_contents(),
                filename=payer_accumulation_report.file_path(),
                bucket=ACCUMULATION_FILE_BUCKET,
            )
            self.validate_report_status(
                payer_accumulation_report.id, PayerReportStatus.FAILURE
            )

    @freeze_time("2023-11-21 01:23:45")
    def test_aetna_payer_accumulation_success(
        self, aetna_payer, mock_aetna_file_generator, mock_accumulation_file_handler
    ):
        payer_accumulation_report = PayerAccumulationReportsFactory.create(
            payer_id=aetna_payer.id
        )
        file_name = payer_accumulation_report.filename
        mock_aetna_file_generator.file_name = file_name

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationReportService.get_generator_class_for_payer_name",
            return_value=mock_aetna_file_generator,
        ), mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            aetna_accumulation_file_generation()
            mock_aetna_file_generator.generate_file_contents.assert_called_once()
            mock_accumulation_file_handler.upload_file.assert_called_once_with(
                content=mock_aetna_file_generator.generate_file_contents(),
                filename=payer_accumulation_report.file_path(),
                bucket=ACCUMULATION_FILE_BUCKET,
            )
            self.validate_report_status(
                payer_accumulation_report.id, PayerReportStatus.NEW
            )

    def test_aetna_empty_file_generated(
        self, aetna_payer, mock_accumulation_file_handler
    ):
        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            aetna_accumulation_file_generation()
            mock_accumulation_file_handler.upload_file.assert_not_called()

    @freeze_time("2023-11-21 01:23:45")
    def test_anthem_payer_accumulation_success(
        self, anthem_payer, mock_anthem_file_generator, mock_accumulation_file_handler
    ):
        payer_accumulation_report = PayerAccumulationReportsFactory.create(
            payer_id=anthem_payer.id
        )
        file_name = payer_accumulation_report.filename
        mock_anthem_file_generator.file_name = file_name

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationReportService.get_generator_class_for_payer_name",
            return_value=mock_anthem_file_generator,
        ), mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            cigna_accumulation_file_generation()
            mock_anthem_file_generator.generate_file_contents.assert_called_once()
            mock_accumulation_file_handler.upload_file.assert_called_once_with(
                content=mock_anthem_file_generator.generate_file_contents(),
                filename=payer_accumulation_report.file_path(),
                bucket=ACCUMULATION_FILE_BUCKET,
            )
            self.validate_report_status(
                payer_accumulation_report.id, PayerReportStatus.NEW
            )

    @freeze_time("2023-11-21 01:23:45")
    def test_cigna_payer_accumulation_success(
        self, cigna_payer, mock_cigna_file_generator, mock_accumulation_file_handler
    ):
        payer_accumulation_report = PayerAccumulationReportsFactory.create(
            payer_id=cigna_payer.id
        )
        file_name = payer_accumulation_report.filename
        mock_cigna_file_generator.file_name = file_name

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationReportService.get_generator_class_for_payer_name",
            return_value=mock_cigna_file_generator,
        ), mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            cigna_accumulation_file_generation()
            mock_cigna_file_generator.generate_file_contents.assert_called_once()
            mock_accumulation_file_handler.upload_file.assert_called_once_with(
                content=mock_cigna_file_generator.generate_file_contents(),
                filename=payer_accumulation_report.file_path(),
                bucket=ACCUMULATION_FILE_BUCKET,
            )
            self.validate_report_status(
                payer_accumulation_report.id, PayerReportStatus.NEW
            )

    @freeze_time("2023-11-21 01:23:45")
    def test_uhc_payer_accumulation_success(
        self, uhc_payer, mock_uhc_file_generator, mock_accumulation_file_handler
    ):
        payer_accumulation_report = PayerAccumulationReportsFactory.create(
            payer_id=uhc_payer.id
        )
        file_name = payer_accumulation_report.filename
        mock_uhc_file_generator.file_name = file_name

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationReportService.get_generator_class_for_payer_name",
            return_value=mock_uhc_file_generator,
        ), mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_generation.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            uhc_accumulation_file_generation()
            mock_uhc_file_generator.generate_file_contents.assert_called_once()
            mock_accumulation_file_handler.upload_file.assert_called_once_with(
                content=mock_uhc_file_generator.generate_file_contents(),
                filename=payer_accumulation_report.file_path(),
                bucket=ACCUMULATION_FILE_BUCKET,
            )
            self.validate_report_status(
                payer_accumulation_report.id, PayerReportStatus.NEW
            )

    @staticmethod
    def validate_report_status(report_id: int, expected_status: PayerReportStatus):
        report = PayerAccumulationReports.query.filter_by(id=report_id).one()
        assert report.status == expected_status
