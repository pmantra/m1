from unittest.mock import patch

import phonenumbers
import pytest

import utils.sms as sms
from pytests import factories
from utils.sms import country_accepts_url_in_sms


@pytest.fixture
def member_profiles(factories: factories):
    """
    Create member_profiles with varying phone_numbers
    """
    factories.MemberProfileFactory.create(
        user=factories.MemberFactory.create(id=1),
    )
    factories.MemberProfileFactory.create(
        user=factories.MemberFactory.create(id=2),
        phone_number="+12125555555",
    )


@pytest.mark.parametrize(
    [
        "user_id",
        "expected",
    ],
    [
        ("1", False),
        ("2", True),
    ],
    ids=["No Phone Number", "Valid Phone Number"],
)
@patch("messaging.services.twilio.twilio_client")
def test_permanently_delete_messages_for_user(
    mock_twilio_client, member_profiles, user_id, expected
):
    result = sms.permanently_delete_messages_for_user(user_id)
    assert result == expected


@pytest.mark.parametrize(
    "country,expected_accepts_url_in_sms",
    [
        ("US", True),
        ("CA", True),
        ("IN", False),
        ("MY", False),
        ("TW", False),
        ("DK", False),
        ("BR", False),
    ],
)
def test_country_accepts_url_in_sms(country, expected_accepts_url_in_sms):

    country_to_sample_phone_number = {
        "US": "+17733220000",
        "CA": "+14165551234",
        "IN": "+912228403221",
        "MY": "+60312345678",
        "TW": "+886223456789",
        "DK": "+4533210772",
        "BR": "+5511987654321",
    }

    # Given
    phone_number = country_to_sample_phone_number[country]
    parsed_phone_number = sms.parse_phone_number(phone_number)

    # When
    url_accepted = country_accepts_url_in_sms(parsed_phone_number)

    # Then
    assert url_accepted == expected_accepts_url_in_sms


def test_parse_phone_number():
    phone_number = "+17733220000"
    parsed_phone_number = sms.parse_phone_number(phone_number)
    assert parsed_phone_number == phonenumbers.PhoneNumber(
        country_code=1, national_number=7733220000
    )


def test_parse_phone_number__empty_str():
    parsed_phone_number = sms.parse_phone_number()
    assert parsed_phone_number is None
