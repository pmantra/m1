import datetime
from unittest.mock import patch

import pytest
import pytz
from marshmallow import fields

from geography import Country
from pytests.factories import CountryMetadataFactory, DefaultUserFactory
from views.schemas.base import CountrySchemaV3, MavenDateTimeV3, UserSchemaV3


class TestFields:
    def test_maven_datetime_deserialize(self):
        field = MavenDateTimeV3()
        result = field._deserialize("2024-01-01T12:30:45", None, None)
        assert result == datetime.datetime(2024, 1, 1, 12, 30, 45)
        assert result.microsecond == 0

        result = field._deserialize("2024-01-01T12:30:45.123456", None, None)
        assert result.microsecond == 0

        with pytest.raises(fields.ValidationError):
            field._deserialize("invalid-date-time", None, None)

        # Test robustness of handling different ISO format
        result = field._deserialize("2024-02-01", None, None)
        assert result == datetime.datetime(2024, 2, 1, 0, 0, 0)
        assert result.microsecond == 0

        result = field._deserialize("2024-02-01T02:00", None, None)
        assert result == datetime.datetime(2024, 2, 1, 2, 0, 0)
        assert result.microsecond == 0

    def test_maven_datetime_serialize(self):
        field = MavenDateTimeV3()
        expected_result = "2024-01-01T12:30:45"
        naive_datetime = datetime.datetime(2024, 1, 1, 12, 30, 45, 123456)
        result = field._serialize(naive_datetime, None, None)
        assert result == expected_result

        aware_datetime = datetime.datetime(
            2024, 1, 1, 12, 30, 45, 123456, tzinfo=pytz.UTC
        )
        result = field._serialize(aware_datetime, None, None)
        assert result == expected_result


class TestSchema:
    def test_country_schema(self):
        mock_country = Country(
            name="baz",
            alpha_2="foo",
            alpha_3="bar",
            common_name="fib",
            official_name="fizz",
        )

        schema = CountrySchemaV3(exclude=("ext_info_link", "summary"))
        assert {"name": "baz", "abbr": "foo"} == schema.dump(mock_country)

        mock_meta = CountryMetadataFactory.create(country_code="US")
        with patch(
            "geography.repository.CountryRepository.get_metadata",
            return_value=mock_meta,
        ):
            schema = CountrySchemaV3()
            assert {
                "name": mock_country.name,
                "abbr": mock_country.alpha_2,
                "ext_info_link": mock_meta.ext_info_link,
                "summary": mock_meta.summary,
            } == schema.dump(mock_country)

    def test_user_schema(self):
        mock_user = DefaultUserFactory.create(
            id=1,
            created_at=datetime.datetime(2024, 1, 8, 20, 8, 5),
            first_name="Kyle",
            last_name="Blair",
        )
        schema = UserSchemaV3()
        expected_result = {
            "test_group": "",
            "username": None,
            "email": None,
            "avatar_url": "",
            "care_coordinators": [],
            "encoded_id": None,
            "country": None,
            "created_at": "2024-01-08T20:08:05",
            "last_name": "Blair",
            "first_name": "Kyle",
            "middle_name": "",
            "organization": None,
            "name": "Kyle Blair",
            "id": 1,
            "image_url": None,
            "esp_id": None,
            "subscription_plans": None,
            "role": "",
            "profiles": None,
            "image_id": 0,
        }

        assert expected_result == schema.dump(mock_user)
