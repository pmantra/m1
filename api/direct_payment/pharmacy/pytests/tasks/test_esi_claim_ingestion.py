from unittest.mock import Mock, patch

import pytest
from freezegun import freeze_time
from google.cloud.exceptions import GoogleCloudError
from paramiko import SFTPError
from tenacity import RetryError

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.pharmacy.health_plan_ytd_service import (
    HealthPlanYearToDateSpendService,
)
from direct_payment.pharmacy.models.ingestion_meta import TaskType
from direct_payment.pharmacy.tasks.esi_claim_ingestion_job import (
    _convert_and_store,
    _download,
    _find_files_to_process,
    _get_decrypted_path,
    _process_file,
    _upload,
)
from direct_payment.pharmacy.tasks.esi_parser.schema_extractor import FixedWidthSchema
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.file_generators import ESIAccumulationFileGenerator
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)


@pytest.fixture(scope="function")
def health_plan_year_to_date_svc():
    return HealthPlanYearToDateSpendService()


@pytest.fixture(scope="function")
def esi_payer():
    return PayerFactory.create(payer_name=PayerName.ESI, payer_code="esi")


@pytest.fixture(scope="function")
# @freeze_time("2023-01-01 00:00:00")
def esi_file_generator(esi_payer):
    return ESIAccumulationFileGenerator()


ESI_COST_BREAKDOWN_ID = 123456789
ESI_TREATMENT_MAPPING_ID = 987654321


@pytest.fixture(scope="function")
def esi_cost_breakdown():
    return CostBreakdownFactory.create(
        id=ESI_COST_BREAKDOWN_ID, deductible=0, oop_applied=2000
    )


@pytest.fixture(scope="function")
def esi_treatment_procedure(esi_cost_breakdown):
    return TreatmentProcedureFactory.create(
        cost_breakdown_id=esi_cost_breakdown.id,
    )


@pytest.fixture(scope="function")
@freeze_time("2024-09-20 00:00:00")
def mock_acc_treatment_mapping(esi_file_generator, esi_treatment_procedure):
    AccumulationTreatmentMappingFactory.create(
        id=ESI_TREATMENT_MAPPING_ID,
        payer_id=esi_file_generator.payer_id,
        treatment_procedure_uuid=esi_treatment_procedure.uuid,
        accumulation_unique_id=f"20240920000000#cd_{ESI_COST_BREAKDOWN_ID}",
        accumulation_transaction_id=str(esi_treatment_procedure.id),
        # completed_at=datetime.strptime("13/09/2024 14:30", "%d/%m/%Y %H:%M"),
        treatment_accumulation_status=TreatmentAccumulationStatus.WAITING,
    )


@pytest.fixture(scope="function")
def record_factory():
    """
    Creates raw records to be parsed by ESIParser.
    - See FixedWidthSchema class for the required structure of each raw row
    - See ESIRecord class to add a new column name (e.g. "date_of_service") and which ones are required
    - See pharmacy/tasks/esi_parser/README.md for more details
    - See pharmacy/tasks/esi_parser/esi_schema/esi_schema_v3.8.csv for csv format and details
    """

    def _record_factory(transmission_id: str, transaction_id: str):
        return [
            {
                FixedWidthSchema("transmission_file_type", 129, 2, "string"): (b"DR",),
                FixedWidthSchema("transaction_response_status", 131, 1, "string"): (
                    b"R",
                ),
                FixedWidthSchema("reject_code", 132, 3, "string"): (b"081",),
                FixedWidthSchema("date_of_service", 0, 8, "string"): (b"04012024",),
                FixedWidthSchema("transmission_id", 8, 20, "string"): (
                    transmission_id.encode(),
                ),
                FixedWidthSchema("accumulator_action_code", 49, 68, "string"): (
                    b"acc_action_code_666",
                ),
                FixedWidthSchema(
                    "accumulator_balance_benefit_type", 90, 23, "string"
                ): (b"acc_ba_benefit_type_777",),
                FixedWidthSchema("transaction_id", 135, 9, "string"): (
                    transaction_id.encode(),
                ),
                FixedWidthSchema("cardholder_id", 20, 34, "string"): (
                    b"card_id_333444",
                ),
                FixedWidthSchema("patient_first_name", 68, 5, "string"): (b"Bruce",),
                FixedWidthSchema("patient_last_name", 73, 5, "string"): (b"Wayne",),
                FixedWidthSchema("date_of_birth", 82, 8, "string"): (b"07011980",),
                FixedWidthSchema("cardholder_id_alternate", 34, 49, "string"): (
                    b"card_alt_id_555",
                ),
                FixedWidthSchema("accumulator_balance_count", 113, 16, "string"): (
                    b"acc_ba_count_888",
                ),
            }
        ]

    return _record_factory


class MockTempFile:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_download():
    mock_sftp = Mock()
    mock_file_name = "test_file.txt"
    mock_temp_file_name = "/tmp/test_file.txt"

    mock_temp_file = Mock()
    mock_temp_file.name = mock_temp_file_name
    mock_sftp.get.return_value = None

    with patch("paramiko.SFTPClient", return_value=mock_sftp):
        _download(mock_file_name, mock_temp_file_name, mock_sftp)
        mock_sftp.get.assert_called_once_with(mock_file_name, mock_temp_file_name)


def test_download_retries():
    mock_sftp, mock_file_name, mock_temp_file = Mock(), "test.txt", Mock()
    mock_temp_file.name = "/tmp/test.txt"
    mock_sftp.get.side_effect = [IOError, SFTPError, None]

    with patch("paramiko.SFTPClient", return_value=mock_sftp):
        _download(mock_file_name, mock_temp_file.name, mock_sftp)

    assert mock_sftp.get.call_count == 3


def test_downloads_failed():
    mock_sftp, mock_file_name, mock_temp_file = Mock(), "test.txt", Mock()
    mock_temp_file.name = "/tmp/test.txt"
    mock_sftp.get.side_effect = SFTPError
    with patch("paramiko.SFTPClient", return_value=mock_sftp):
        with pytest.raises(SFTPError):
            _download(mock_file_name, mock_temp_file.name, mock_sftp)
    assert mock_sftp.get.call_count == 3


def test_upload():
    mock_bucket, mock_blob = Mock(), Mock()
    mock_bucket.blob.return_value = mock_blob
    mock_remote_file = "test.txt"
    mock_local_file = "/tmp/test.txt"
    mock_blob.upload_from_filename.return_value = None

    _upload(mock_local_file, mock_remote_file, mock_bucket)
    mock_bucket.blob.assert_called_once_with(mock_remote_file)
    mock_blob.upload_from_filename.assert_called_once_with(mock_local_file)


def test_upload_retries():
    mock_bucket, mock_blob = Mock(), Mock()
    mock_bucket.blob.return_value = mock_blob
    mock_remote_file = "test.txt"
    mock_local_file = "/tmp/test.txt"

    mock_blob.upload_from_filename.side_effect = [
        GoogleCloudError("foo"),
        GoogleCloudError("bar"),
        None,
    ]

    _upload(mock_local_file, mock_remote_file, mock_bucket)

    assert mock_blob.upload_from_filename.call_count == 3


def test_find_files_to_execute():
    files = [
        "MAVN_RxAccum_20231001_090000.pgp",
        "MAVN_RxAccum_20231111_090000.pgp",
        "MAVN_RxAccum_20231012_090000.pgp",
        "MAVN_RxAccum_20241001_111100.pgp",
    ]
    expected_result = [
        "MAVN_RxAccum_20241001_111100.pgp",
        "MAVN_RxAccum_20231111_090000.pgp",
        "MAVN_RxAccum_20231012_090000.pgp",
    ]
    ret = _find_files_to_process(files, TaskType.INCREMENTAL, 20231011)
    assert expected_result == ret


def test_find_files_to_execute_fixup():
    files = [
        "MAVN_RxAccum_20231001_090000.pgp",
        "MAVN_RxAccum_20231111_090000.pgp",
        "MAVN_RxAccum_20231012_090000.pgp",
        "MAVN_RxAccum_20241001_111100.pgp",
    ]
    expected_result = ["MAVN_RxAccum_20231111_090000.pgp"]
    ret = _find_files_to_process(files, TaskType.FIXUP, 20231111)
    assert expected_result == ret


def test_get_decrypted_filepath():
    raw = "raw/MAVN_RxAccum_20231001_0900.pgp"
    assert "decrypted/MAVN_RxAccum_20231001_0900.txt" == _get_decrypted_path(raw)


@patch("direct_payment.pharmacy.tasks.esi_claim_ingestion_job._download")
@patch("direct_payment.pharmacy.tasks.esi_claim_ingestion_job._upload")
@patch("tempfile.NamedTemporaryFile", return_value=MockTempFile(name="temp"))
def test_process_file(mock_tempfile, mock_upload, mock_download):
    mock_sftp, mock_bucket = Mock(), Mock()
    assert _process_file("dummy", mock_sftp, mock_bucket) is True
    mock_download.assert_called_once_with("From_ESI/dummy", "temp", mock_sftp)
    mock_upload.assert_called_once_with("temp", "raw/dummy", mock_bucket)


def test_convert_and_store__successful_rejection_update(
    health_plan_year_to_date_svc, mock_acc_treatment_mapping, record_factory
):
    # Given
    acc_trtmnt_mapping = AccumulationTreatmentMapping.query.get(
        ESI_TREATMENT_MAPPING_ID
    )
    records = record_factory(
        transmission_id=acc_trtmnt_mapping.accumulation_unique_id,
        transaction_id=acc_trtmnt_mapping.accumulation_transaction_id,
    )
    expected_status = TreatmentAccumulationStatus.REJECTED
    # When
    result, process_stats = _convert_and_store(
        service=health_plan_year_to_date_svc, records=records, remote_file_path=""
    )
    # Then
    assert result is False
    assert process_stats["dr_count"] == 1
    assert process_stats["dr_reject_count"] == 1
    assert process_stats["dr_missing_tm_count"] == 0
    assert acc_trtmnt_mapping.treatment_accumulation_status is expected_status


def test_convert_and_store__failed_with_no_transaction_id(
    health_plan_year_to_date_svc, mock_acc_treatment_mapping, record_factory
):
    # Given
    accumulation_treatment_mapping = AccumulationTreatmentMapping.query.get(
        ESI_TREATMENT_MAPPING_ID
    )
    records = record_factory(transmission_id="", transaction_id="")
    expected_status = TreatmentAccumulationStatus.WAITING
    # When
    result, process_stats = _convert_and_store(
        service=health_plan_year_to_date_svc, records=records, remote_file_path=""
    )
    # Then
    assert result is False
    assert process_stats["dr_count"] == 1
    assert process_stats["dr_reject_count"] == 1
    assert process_stats["dr_missing_tm_count"] == 0
    assert (
        accumulation_treatment_mapping.treatment_accumulation_status is expected_status
    )


def test_convert_and_store__failed_with_transaction_id_in_record_not_mapped(
    health_plan_year_to_date_svc, mock_acc_treatment_mapping, record_factory
):
    # Given
    records = record_factory(
        transmission_id="20240920000000#cd_404404404", transaction_id="911911911"
    )
    # When
    result, process_stats = _convert_and_store(
        service=health_plan_year_to_date_svc, records=records, remote_file_path=""
    )
    # Then
    assert result is False
    assert process_stats["dr_count"] == 1
    assert process_stats["dr_reject_count"] == 1
    assert process_stats["dr_missing_tm_count"] == 1


@patch(
    "direct_payment.pharmacy.tasks.esi_claim_ingestion_job._download",
    side_effect=IOError(),
)
@patch("direct_payment.pharmacy.tasks.esi_claim_ingestion_job._upload")
@patch("tempfile.NamedTemporaryFile", return_value=MockTempFile(name="temp"))
def test_process_file_download_error(_, mock_upload, mock_download):
    mock_sftp, mock_bucket = Mock(), Mock()
    assert _process_file("dummy", mock_sftp, mock_bucket) is False


@patch("direct_payment.pharmacy.tasks.esi_claim_ingestion_job._download")
@patch(
    "direct_payment.pharmacy.tasks.esi_claim_ingestion_job._upload",
    side_effect=RetryError(last_attempt=Mock()),
)
@patch("tempfile.NamedTemporaryFile", return_value=MockTempFile(name="temp"))
def test_process_file_upload_error(_, mock_upload, mock_download):
    mock_sftp, mock_bucket = Mock(), Mock()
    assert _process_file("dummy", mock_sftp, mock_bucket) is False
    mock_download.assert_called_once_with("From_ESI/dummy", "temp", mock_sftp)
