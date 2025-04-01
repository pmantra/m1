import io
from unittest.mock import patch

import pytest

from payer_accumulator.common import PayerName
from payer_accumulator.edi.errors import EDI276ClaimStatusRequestGeneratorException
from payer_accumulator.pytests.factories import PayerFactory
from payer_accumulator.tasks.edi_276_claim_status_request_job import (
    EDI276ClaimStatusRequestJob,
)
from utils.sftp import SSHError


@pytest.fixture(scope="function")
def aetna_payer(app_context):
    return PayerFactory.create(id=1, payer_name=PayerName.AETNA, payer_code="01234")


class TestEDI276ClaimStatusRequestJob:
    def test_success(self, aetna_payer):
        with patch(
            "payer_accumulator.tasks.edi_276_claim_status_request_job.get_sftp_from_secret",
        ) as get_sftp_from_secret, patch(
            "payer_accumulator.tasks.edi_276_claim_status_request_job.EDI276ClaimStatusRequestFileGenerator.generate_file_contents",
        ) as generate_file_contents:
            generate_file_contents.return_value = io.StringIO("276 file")
            job = EDI276ClaimStatusRequestJob(PayerName.AETNA)
            job.run()
            generate_file_contents.assert_called_once()
            get_sftp_from_secret.return_value.putfo.assert_called_once()

    def test_failed_to_connect_to_sftp(self, aetna_payer):
        with patch(
            "payer_accumulator.tasks.edi_276_claim_status_request_job.get_sftp_from_secret",
            return_value=None,
        ), patch(
            "payer_accumulator.tasks.edi_276_claim_status_request_job.EDI276ClaimStatusRequestFileGenerator.generate_file_contents",
        ) as generate_file_contents, pytest.raises(
            SSHError
        ):
            generate_file_contents.return_value = io.StringIO("276 file")
            job = EDI276ClaimStatusRequestJob(PayerName.AETNA)
            job.run()
            generate_file_contents.assert_called_once()

    def test_file_generation_error(self, aetna_payer):
        with patch(
            "payer_accumulator.tasks.edi_276_claim_status_request_job.EDI276ClaimStatusRequestFileGenerator.generate_file_contents",
        ) as generate_file_contents, pytest.raises(
            EDI276ClaimStatusRequestGeneratorException
        ):
            generate_file_contents.side_effect = (
                EDI276ClaimStatusRequestGeneratorException()
            )
            job = EDI276ClaimStatusRequestJob(PayerName.AETNA)
            job.run()
            generate_file_contents.assert_called_once()

    def test_empty_file_generated(self, aetna_payer):
        with patch(
            "payer_accumulator.tasks.edi_276_claim_status_request_job.EDI276ClaimStatusRequestFileGenerator.generate_file_contents",
            return_value=io.StringIO(),
        ), patch(
            "payer_accumulator.tasks.edi_276_claim_status_request_job.get_sftp_from_secret",
        ) as get_sftp_from_secret:
            job = EDI276ClaimStatusRequestJob(PayerName.AETNA)
            job.run()
            get_sftp_from_secret.assert_not_called()
