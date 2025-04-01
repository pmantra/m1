from datetime import datetime
from unittest import mock
from unittest.mock import ANY

import factory
import pytest
from google.cloud.storage import Blob

from payer_accumulator.common import OrganizationName, PayerName
from payer_accumulator.constants import (
    ACCUMULATION_FILE_BUCKET,
    AETNA_QUATRIX_FOLDER,
    ANTHEM_QUATRIX_FOLDER,
    CIGNA_AMAZON_QUATRIX_FOLDER,
    CIGNA_FOLDER,
    CIGNA_GOLDMAN_QUATRIX_FOLDER,
    CREDENCE_QUATRIX_FOLDER,
    ESI_FOLDER,
    LUMINARE_QUATRIX_FOLDER,
    SUREST_QUATRIX_FOLDER,
    UHC_FOLDER,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
    PayerReportStatus,
)
from payer_accumulator.pytests.factories import (
    PayerAccumulationReportsFactory,
    PayerFactory,
)
from payer_accumulator.tasks.rq_payer_accumulation_file_transfer import (
    AccumulationFileTransferHandler,
)
from pytests.freezegun import freeze_time

TEST_FILE = "test.txt"
TEST_DATE = datetime(2023, 12, 7)
DATE_IN_FILE_PATH = TEST_DATE.strftime("%Y/%m/%d")
CIGNA_FILE_PATH_PREFIX = f"{PayerName.Cigna.value}/{DATE_IN_FILE_PATH}"


@pytest.fixture(scope="function")
@freeze_time("2023-12-07 00:00:00")
def cigna_accumulation_file_reports(cigna_payer):
    return PayerAccumulationReportsFactory.create_batch(
        size=2,
        payer_id=cigna_payer.id,
        filename=factory.Iterator(
            [
                "new_file",
                "submitted_file",
            ]
        ),
        status=factory.Iterator(
            [
                PayerReportStatus.NEW,
                PayerReportStatus.SUBMITTED,
            ]
        ),
    )


class TestAccumulationFileTransferHandler:
    def test_transfer_files(
        self, mock_accumulation_file_handler, cigna_accumulation_file_reports
    ):
        files = []
        for report in cigna_accumulation_file_reports:
            files.append(
                Blob(
                    name=report.file_path(),
                    bucket=ACCUMULATION_FILE_BUCKET,
                )
            )
        mock_accumulation_file_handler.get_many_from_gcp_bucket.return_value = files
        mock_accumulation_file_handler.get_from_gcp_bucket.return_value = "abc"

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_transfer.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            file_transfer_handler = AccumulationFileTransferHandler(
                payer_name=PayerName.Cigna, target_date=TEST_DATE
            )
            file_transfer_handler.transfer_files()

            mock_accumulation_file_handler.get_many_from_gcp_bucket.assert_called_once_with(
                prefix=f"{CIGNA_FILE_PATH_PREFIX}/", bucket=ACCUMULATION_FILE_BUCKET
            )
            mock_accumulation_file_handler.get_from_gcp_bucket.assert_called_once_with(
                filename=cigna_accumulation_file_reports[0].file_path(),
                bucket=ACCUMULATION_FILE_BUCKET,
            )
            mock_accumulation_file_handler.send_to_gcp_bucket.assert_called_once_with(
                content=ANY,
                filename="cigna_accumulation/new_file",
                bucket=ACCUMULATION_FILE_BUCKET,
            )

            updated_report = PayerAccumulationReports.query.filter_by(
                filename=cigna_accumulation_file_reports[0].filename
            ).one()
            assert updated_report.status == PayerReportStatus.SUBMITTED

    def test_get_eligible_filenames_from_source_bucket(
        self, mock_accumulation_file_handler, cigna_accumulation_file_reports
    ):
        files = []
        for report in cigna_accumulation_file_reports:
            files.append(
                Blob(
                    name=report.file_path(),
                    bucket=ACCUMULATION_FILE_BUCKET,
                )
            )
        mock_accumulation_file_handler.get_many_from_gcp_bucket.return_value = files

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_transfer.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            file_transfer_handler = AccumulationFileTransferHandler(
                payer_name=PayerName.Cigna, target_date=TEST_DATE
            )
            result = file_transfer_handler.get_eligible_filenames_from_source_bucket()
            assert len(result) == 1
            assert result[0] == f"{CIGNA_FILE_PATH_PREFIX}/new_file"

    def test_transfer_file_to_destination_bucket(self, mock_accumulation_file_handler):
        mock_accumulation_file_handler.get_from_gcp_bucket.return_value = "abc"
        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_transfer.AccumulationFileHandler",
        ) as mock_acc_file_handler, mock.patch(
            "payer_accumulator.models.payer_list"
        ) as mock_payer_list:
            mock_acc_file_handler.return_value = mock_accumulation_file_handler
            file_transfer_handler = AccumulationFileTransferHandler(
                payer_name=PayerName.Cigna, target_date=datetime.utcnow()
            )
            input_filename = f"{CIGNA_FILE_PATH_PREFIX}/{TEST_FILE}"
            mock_payer_list.return_value = PayerFactory.create(
                payer_name=file_transfer_handler.payer_name
            )
            file_transfer_handler.transfer_file_to_destination_bucket(input_filename)
            mock_accumulation_file_handler.get_from_gcp_bucket.assert_called_once_with(
                filename=input_filename, bucket=ACCUMULATION_FILE_BUCKET
            )
            mock_accumulation_file_handler.send_to_gcp_bucket.assert_called_once_with(
                content=ANY,
                filename=f"cigna_accumulation/{TEST_FILE}",
                bucket=ACCUMULATION_FILE_BUCKET,
            )

    @pytest.mark.parametrize(
        argnames="input_filename_prefix,output_filename_prefix,payer_name,organization_name",
        argvalues=[
            (PayerName.AETNA.name, AETNA_QUATRIX_FOLDER, PayerName.AETNA, None),
            (PayerName.ANTHEM.name, ANTHEM_QUATRIX_FOLDER, PayerName.ANTHEM, None),
            (PayerName.Cigna.name, CIGNA_FOLDER, PayerName.Cigna, None),
            (
                PayerName.CIGNA_TRACK_1.name,
                CIGNA_AMAZON_QUATRIX_FOLDER,
                PayerName.CIGNA_TRACK_1,
                OrganizationName.AMAZON,
            ),
            (
                PayerName.CIGNA_TRACK_1.name,
                CIGNA_GOLDMAN_QUATRIX_FOLDER,
                PayerName.CIGNA_TRACK_1,
                OrganizationName.GOLDMAN,
            ),
            (
                PayerName.CREDENCE.name,
                CREDENCE_QUATRIX_FOLDER,
                PayerName.CREDENCE,
                None,
            ),
            (PayerName.ESI.name, ESI_FOLDER, PayerName.ESI, None),
            (
                PayerName.LUMINARE.name,
                LUMINARE_QUATRIX_FOLDER,
                PayerName.LUMINARE,
                None,
            ),
            (PayerName.SUREST.name, SUREST_QUATRIX_FOLDER, PayerName.SUREST, None),
            (PayerName.UHC.name, UHC_FOLDER, PayerName.UHC, None),
        ],
        ids=[
            "aetna",
            "anthem",
            "cigna",
            "amazon_cigna_track_1",
            "goldman_cigna_track_1",
            "credence",
            "esi",
            "luminare",
            "surest",
            "uhc",
        ],
    )
    def test_generate_filename_for_destination_bucket(
        self,
        input_filename_prefix,
        output_filename_prefix,
        payer_name,
        organization_name,
    ):
        input_filename = f"{input_filename_prefix}/{DATE_IN_FILE_PATH}/{TEST_FILE}"
        output_filename = f"{output_filename_prefix}/{TEST_FILE}"
        result = (
            AccumulationFileTransferHandler.generate_filename_for_destination_bucket(
                input_filename, payer_name, organization_name
            )
        )
        assert result == output_filename

    def test_admin_transfer_report_file_job(
        self, mock_accumulation_file_handler, cigna_accumulation_file_reports
    ):
        report = cigna_accumulation_file_reports[0]
        filename = report.file_path()

        mock_accumulation_file_handler.get_from_gcp_bucket.return_value = "abc"
        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_file_transfer.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            file_transfer_handler = AccumulationFileTransferHandler(
                payer_name=PayerName.Cigna, target_date=datetime.utcnow()
            )
            file_transfer_handler.transfer_file_to_destination_bucket(filename)
        file_transfer_handler.update_status_after_file_submission(
            filename, is_success=True
        )
        updated_report = PayerAccumulationReports.query.get(report.id)
        assert updated_report.status.value == "SUBMITTED"
