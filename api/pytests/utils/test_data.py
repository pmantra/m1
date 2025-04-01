import pytest
from marshmallow_v1.exceptions import ValidationError

from utils.data import normalize_phone_number


# use fake numbers only!
class TestDomesticNormalizePhoneNumber:

    normalized_domestic = "tel:+1-202-555-0000"
    domestic_national_number = 2025550000

    def assert_domestic_success(self, normalized, phone_number):
        assert normalized == self.normalized_domestic
        assert phone_number.country_code == 1
        assert phone_number.national_number == self.domestic_national_number

    def test_domestic_with_standard_input(self):
        # this is the standard format all phone numbers should be
        # coming in from the frontend with
        num = "12025550000"
        normalized, phone_number = normalize_phone_number(num, None)

        self.assert_domestic_success(normalized, phone_number)

    def test_domestic_with_plusareacode(self):
        num = "+12025550000"
        normalized, phone_number = normalize_phone_number(num, None)

        self.assert_domestic_success(normalized, phone_number)

    def test_domestic_with_dashes(self):
        num = "+1-202-555-0000"
        normalized, phone_number = normalize_phone_number(num, None)

        self.assert_domestic_success(normalized, phone_number)

    def test_domestic_with_parenthesis(self):
        num = "+1 (202) 555-0000"
        normalized, phone_number = normalize_phone_number(num, None)

        self.assert_domestic_success(normalized, phone_number)

    def test_domestic_with_tel(self):
        num = "tel:+12025550000"
        normalized, phone_number = normalize_phone_number(num, None)

        self.assert_domestic_success(normalized, phone_number)

    def test_domestic_without_countrycode(self):
        num = "2025550000"
        normalized, phone_number = normalize_phone_number(num, None)

        self.assert_domestic_success(normalized, phone_number)

    def test_new_area_code(self):
        num = "6569983939"
        normalized, phone_number = normalize_phone_number(num, None)

        assert normalized == "tel:+1-656-998-3939"


class TestInternationalNormalizePhoneNumber:
    def assert_international_success(
        self,
        normalized,
        phone_number,
        expected_normalized,
        expected_country_code,
        expected_national_number,
    ):
        assert normalized == expected_normalized
        assert phone_number.country_code == expected_country_code
        assert phone_number.national_number == expected_national_number

    def test_international_with_tel(self):
        num = "tel:+610491570006"

        normalized, phone_number = normalize_phone_number(num, None)

        self.assert_international_success(
            normalized, phone_number, "tel:+61-491-570-006", 61, 491570006
        )

    def test_international_with_formatting(self):
        num = "+61 0491-570-006"

        normalized, phone_number = normalize_phone_number(num, None)

        self.assert_international_success(
            normalized, phone_number, "tel:+61-491-570-006", 61, 491570006
        )

    @pytest.mark.parametrize(
        argnames="standard_input, expected_normalized, expected_country_code, expected_national_number",
        argvalues=[
            ["610491570006", "tel:+61-491-570-006", 61, 491570006],  # australia
            ["559558887398", "tel:+55-95-5888-7398", 55, 9558887398],  # brazil
            ["16135550162", "tel:+1-613-555-0162", 1, 6135550162],  # canada
            ["8613013828142", "tel:+86-130-1382-8142", 86, 13013828142],  # china
            ["201055539339", "tel:+20-10-55539339", 20, 1055539339],  # egypt
            ["4930702914820", "tel:+49-30-702914820", 49, 30702914820],  # germany
            ["9102228403221", "tel:+91-22-2840-3221", 91, 2228403221],  # india
            ["528885178328", "tel:+52-888-517-8328", 52, 8885178328],  # mexico
            ["2347061525901", "tel:+234-706-152-5901", 234, 7061525901],  # nigeria
            ["442083661177", "tel:+44-20-8366-1177", 44, 2083661177],  # uk
        ],
    )
    def test_international_numbers_with_standard_input(
        self,
        standard_input,
        expected_normalized,
        expected_country_code,
        expected_national_number,
    ):
        normalized, phone_number = normalize_phone_number(standard_input, None)

        self.assert_international_success(
            normalized,
            phone_number,
            expected_normalized,
            expected_country_code,
            expected_national_number,
        )


class TestNormalizePhoneNumberErrors:
    def test_no_areacode(self):
        num = "5550000"

        with pytest.raises(ValidationError):
            normalize_phone_number(num, None)

    def test_fake_areacode(self):
        num = "15555550000"

        with pytest.raises(ValidationError):
            normalize_phone_number(num, None)

    def test_international_with_tel_without_plus(self):
        # weird edge case i thought I'd document here -
        # "tel:" without a "+"" before the area code is invalid on international numbers
        num = "tel:610491570006"

        with pytest.raises(ValidationError):
            normalize_phone_number(num, None)
