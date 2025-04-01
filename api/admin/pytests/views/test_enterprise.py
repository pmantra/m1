import pytest

from admin.views.models.enterprise import normalize_phone_number


@pytest.mark.parametrize(
    "phone_number,expected_normalized_phone_number",
    [
        ("407-727-7231", "14077277231"),
        ("1-407-727-7231", "14077277231"),
        ("(407) 727-7231", "14077277231"),
        ("tel:+1-407-727-7231", "14077277231"),
    ],
)
def test_normalize_phone_number(phone_number, expected_normalized_phone_number):
    normalized_phone_number = normalize_phone_number(phone_number)
    assert normalized_phone_number == expected_normalized_phone_number
