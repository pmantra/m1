from unittest import mock

import pytest


@pytest.fixture(scope="function")
def mock_accumulation_file_handler():
    with mock.patch("payer_accumulator.file_handler.AccumulationFileHandler") as m:
        yield m
