import string

import pytest

from utils.random_string import generate_random_string


class TestGenerateRandomString:
    def test_invalid_length(self):
        with pytest.raises(ValueError) as e_info:
            generate_random_string(0)

        assert str(e_info.value) == "Invalid string length"

    def test_invalid_request(self):
        with pytest.raises(ValueError) as e_info:
            generate_random_string(3, False, False, False)

        assert (
            str(e_info.value)
            == "Cannot generate a random string because no characters allowed"
        )

    def test_normal_case(self):
        result_one = generate_random_string(3, True, False, False)

        assert len(result_one) == 3
        for char in result_one:
            assert char in string.ascii_lowercase

        result_two = generate_random_string(5)
        assert len(result_two) == 5
        candidate = string.ascii_lowercase + string.ascii_uppercase + string.digits
        for char in result_two:
            assert char in candidate
