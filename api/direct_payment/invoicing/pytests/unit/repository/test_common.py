import uuid

import pytest

from direct_payment.invoicing.repository.common import UUID

TEST_UUID = uuid.UUID("096ae9af-76b5-431e-937e-c7559056a796")
TEST_UUID_STR = str(TEST_UUID)


class TestUUID:
    @pytest.mark.parametrize(
        argnames="inp, exp",
        argvalues=((TEST_UUID, TEST_UUID_STR), (TEST_UUID_STR, TEST_UUID_STR)),
    )
    def test_process_bind_param(self, inp, exp):
        my_uuid = UUID()
        assert my_uuid.process_bind_param(inp) == exp

    @pytest.mark.parametrize(
        argnames="inp",
        argvalues=(None, "Not_Valid_UUID_String", 10),
    )
    def test_process_bind_param_error(self, inp):
        my_uuid = UUID()
        with pytest.raises(ValueError):
            _ = my_uuid.process_bind_param(inp)

    @pytest.mark.parametrize(
        argnames="inp, exp",
        argvalues=((TEST_UUID_STR, TEST_UUID), (None, None)),
    )
    def test_process_result_value(self, inp, exp):
        my_uuid = UUID()
        assert my_uuid.process_result_value(inp) == exp
