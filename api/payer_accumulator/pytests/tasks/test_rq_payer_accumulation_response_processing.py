import os
from unittest import mock

import gnupg
import pytest

from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.file_generators import AccumulationFileGeneratorAnthem
from payer_accumulator.pytests.factories import AccumulationTreatmentMappingFactory
from payer_accumulator.tasks.rq_payer_accumulation_response_processing import (
    ARCHIVED_DIR,
    RECEIVED_DIR,
    AccumulationResponseProcessingJob,
)
from pytests.freezegun import freeze_time

GPG_PASSPHRASE = "foobar"
PLAINTEXT = "When zombies arrive, quickly fax Judge Pat."


@pytest.fixture(scope="function")
@freeze_time("2023-10-15 12:34:56")
def anthem_file_generator(anthem_payer):
    return AccumulationFileGeneratorAnthem()


@pytest.fixture
def gpg():
    return gnupg.GPG(gnupghome="/tmp")


@pytest.fixture
def gpg_key(gpg):
    key_input = gpg.gen_key_input(
        name_email="maven@example.com", passphrase=GPG_PASSPHRASE
    )
    key = gpg.gen_key(key_input)
    return key


@pytest.fixture
def gpg_private_key(gpg, gpg_key):
    return gpg.export_keys(gpg_key.fingerprint)


@pytest.fixture
def gpg_ciphertext(gpg, gpg_key):
    original_data = PLAINTEXT
    return str(gpg.encrypt(original_data, gpg_key.fingerprint))


def read_test_file_contents(test_file_name: str) -> str:
    file_path = os.path.join(
        os.path.dirname(__file__),
        f"../test_files/{test_file_name}",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


class TestAccumulationResponseProcessingJob:
    @pytest.mark.parametrize(
        argnames="payer_fixture, file_1_without_prefix, file_2_without_prefix",
        argvalues=[
            (
                "anthem_payer",
                "RESP_MVX_EH_MED_ACCUM_PROD_20241001_000000.TXT",
                "RESP_MVX_EH_MED_ACCUM_PROD_20241012_000000.TXT.pgp",
            ),
            (
                "credence_payer",
                "MAVEN_MED_ACK_20241001_000000",
                "MAVEN_MED_ACK_20241012_000000",
            ),
            (
                "luminare_payer",
                "Maven_Luminare_Accumulator_File_DR_20241001_000000.txt",
                "Maven_Luminare_Accumulator_File_DR_20241002_000000.txt",
            ),
            (
                "premera_payer",
                "AccmMdRsp_PBCtoMAVEN_20241001000000.txt",
                "AccmMdRsp_PBCtoMAVEN_20241002000000.txt",
            ),
        ],
    )
    def test_find_files_to_process(
        self,
        mock_accumulation_file_handler,
        payer_fixture,
        file_1_without_prefix,
        file_2_without_prefix,
        request,
    ):
        payer = request.getfixturevalue(payer_fixture)

        file_1 = f"{payer.payer_name.value}/{RECEIVED_DIR}/{file_1_without_prefix}"
        file_2 = f"{payer.payer_name.value}/{RECEIVED_DIR}/{file_2_without_prefix}"
        file_3 = f"{payer.payer_name.value}/{RECEIVED_DIR}/DEBUG.TXT"

        mock_accumulation_file_handler.list_files.return_value = [
            file_1,
            file_2,
            file_3,
        ]

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_response_processing.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            response_processing_job = AccumulationResponseProcessingJob(
                payer_name=payer.payer_name
            )
            result = response_processing_job.find_files_to_process()
            assert len(result) == 2
            assert result[0] == file_1
            assert result[1] == file_2

    @pytest.mark.parametrize(
        argnames="payer_fixture, file_name_without_prefix",
        argvalues=[
            ("anthem_payer", "RESP_MVX_EH_MED_ACCUM_PROD_20241001_000000.TXT"),
            ("credence_payer", "MAVEN_MED_ACK_20241001_000000"),
            (
                "luminare_payer",
                "Maven_Luminare_Accumulator_File_DR_20241001_000000.txt",
            ),
            ("premera_payer", "AccmMdRsp_PBCtoMAVEN_20241001000000.txt"),
        ],
    )
    def test_archive_response_file(
        self,
        mock_accumulation_file_handler,
        payer_fixture,
        file_name_without_prefix,
        request,
    ):
        payer = request.getfixturevalue(payer_fixture)
        file = f"{payer.payer_name.value}/{RECEIVED_DIR}/{file_name_without_prefix}"
        archived_file = f"{payer.payer_name.value}/{ARCHIVED_DIR}/2024/10/01/{file_name_without_prefix}"

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_response_processing.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            response_processing_job = AccumulationResponseProcessingJob(
                payer_name=payer.payer_name
            )
            response_processing_job.archive_response_file(file)
            assert (
                mock_accumulation_file_handler.move_file.call_args.kwargs[
                    "old_filename"
                ]
                == file
            )
            assert (
                mock_accumulation_file_handler.move_file.call_args.kwargs[
                    "new_filename"
                ]
                == archived_file
            )

    def test_process_accumulation_response_records(self, anthem_file_generator):
        records = [
            # accepted
            {
                "record_type": "DT",
                "transmission_file_type": "DR",
                "transaction_response_status": "A",
                "reject_code": "000",
                "transmission_id": "202410151234567890000001",
                "sender_reference_number": "12345",
            },
            # rejected
            {
                "record_type": "DT",
                "transmission_file_type": "DR",
                "transaction_response_status": "R",
                "reject_code": "999",
                "transmission_id": "202410151234567890000002",
                "sender_reference_number": "12345",
            },
            # rejected (unmapped)
            {
                "record_type": "DT",
                "transmission_file_type": "DR",
                "transaction_response_status": "R",
                "reject_code": "999",
                "transmission_id": "202410151234567890000003",
                "sender_reference_number": "12345",
            },
        ]

        AccumulationTreatmentMappingFactory.create(
            payer_id=anthem_file_generator.payer_id,
            treatment_procedure_uuid="00000000-0000-0000-0000-000000000001",
            accumulation_unique_id="202410151234567890000001",
            accumulation_transaction_id="1",
            treatment_accumulation_status=TreatmentAccumulationStatus.SUBMITTED,
        )
        AccumulationTreatmentMappingFactory.create(
            payer_id=anthem_file_generator.payer_id,
            treatment_procedure_uuid="00000000-0000-0000-0000-000000000002",
            accumulation_unique_id="202410151234567890000002",
            accumulation_transaction_id="2",
            treatment_accumulation_status=TreatmentAccumulationStatus.SUBMITTED,
        )

        response_processing_job = AccumulationResponseProcessingJob(
            payer_name=PayerName.ANTHEM
        )
        process_stats = response_processing_job.process_accumulation_response_records(
            records
        )

        assert process_stats["total_records"] == 3
        assert process_stats["response_count"] == 3
        assert process_stats["accepted_update_count"] == 1
        assert process_stats["rejected_record_count"] == 2
        assert process_stats["rejected_update_count"] == 1

    @pytest.mark.parametrize(
        argnames="payer_fixture,test_file_name",
        argvalues=[
            ("anthem_payer", "RESP_MVX_EH_MED_ACCUM_TEST_20241015_123456.TXT"),
            ("credence_payer", "MAVEN_MED_ACK_20241001_123456"),
            (
                "luminare_payer",
                "Maven_Luminare_Accumulator_File_DR_20241001_000000.txt",
            ),
            ("premera_payer", "AccmMdRsp_PBCtoMAVEN_20241015123456.txt"),
        ],
    )
    def test_process_responses(
        self, mock_accumulation_file_handler, payer_fixture, test_file_name, request
    ):
        payer = request.getfixturevalue(payer_fixture)
        test_file_contents = read_test_file_contents(test_file_name)

        mock_accumulation_file_handler.list_files.return_value = [test_file_name]
        mock_accumulation_file_handler.download_file.return_value = test_file_contents

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_response_processing.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            response_processing_job = AccumulationResponseProcessingJob(
                payer_name=payer.payer_name
            )
            processed_count = response_processing_job.process_responses()
            assert processed_count == 1
            assert mock_accumulation_file_handler.move_file.call_count == 1

    def test_decrypt(self, gpg_private_key, gpg_ciphertext, anthem_payer):
        response_processing_job = AccumulationResponseProcessingJob(
            payer_name=anthem_payer.payer_name
        )
        result = response_processing_job.decrypt(
            gpg_ciphertext, gpg_private_key, GPG_PASSPHRASE
        )
        assert result == PLAINTEXT

    def test_process_accumulation_response_file(self, anthem_payer):
        test_file_name = "RESP_MVX_EH_MED_ACCUM_TEST_20241015_123456.TXT"
        test_file_contents = read_test_file_contents(test_file_name)

        response_processing_job = AccumulationResponseProcessingJob(
            payer_name=anthem_payer.payer_name
        )

        with mock.patch.object(
            response_processing_job, "download_accumulation_response_file"
        ) as mock_download, mock.patch.object(
            response_processing_job,
            "get_decrypt_params",
        ) as mock_get_decrypt_params:
            mock_download.return_value = test_file_contents
            total_records = response_processing_job.process_accumulation_response_file(
                test_file_name
            )

            assert mock_get_decrypt_params.call_count == 0
            assert total_records == 2

    def test_process_accumulation_response_file__empty(self, anthem_payer):
        test_file_name = "RESP_MVX_EH_MED_ACCUM_TEST_20240913_000000.TXT"
        test_file_contents = "\r\n"

        response_processing_job = AccumulationResponseProcessingJob(
            payer_name=anthem_payer.payer_name
        )

        with mock.patch.object(
            response_processing_job, "download_accumulation_response_file"
        ) as mock_download, mock.patch.object(
            response_processing_job,
            "get_decrypt_params",
        ) as mock_get_decrypt_params:
            mock_download.return_value = test_file_contents
            total_records = response_processing_job.process_accumulation_response_file(
                test_file_name
            )

            assert mock_get_decrypt_params.call_count == 0
            assert total_records == 0

    def test_process_accumulation_response_file__encrypted(
        self, gpg, gpg_key, gpg_private_key, gpg_ciphertext, anthem_payer
    ):
        mock_decrypt_params = [gpg_private_key, GPG_PASSPHRASE]

        test_file_name = "RESP_MVX_EH_MED_ACCUM_TEST_20241015_123456.TXT"
        encrypted_file_name = f"{test_file_name}.pgp"
        test_file_contents = read_test_file_contents(test_file_name)
        encrypted_test_file_contents = str(
            gpg.encrypt(test_file_contents, gpg_key.fingerprint)
        )

        response_processing_job = AccumulationResponseProcessingJob(
            payer_name=anthem_payer.payer_name
        )

        with mock.patch.object(
            response_processing_job, "download_accumulation_response_file"
        ) as mock_download, mock.patch.object(
            response_processing_job,
            "get_decrypt_params",
        ) as mock_get_decrypt_params:
            mock_download.return_value = encrypted_test_file_contents
            mock_get_decrypt_params.return_value = mock_decrypt_params
            total_records = response_processing_job.process_accumulation_response_file(
                encrypted_file_name
            )

            assert mock_get_decrypt_params.call_count == 1
            assert total_records == 2
