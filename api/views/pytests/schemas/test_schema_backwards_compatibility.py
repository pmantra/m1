"""
This unit test module is the central places for marshmallow backwards compatibility tests.

The stub test can be generated via:

python scripts/ma_coverage_tool.py --schema-path "views.schemas.common:PractitionerProfileSchema" --v1-schema  --compare-schema-path "views.schemas.base:PractitionerProfileSchemaV3" --generate-test

"""
from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest

from authn.domain.model import User
from messaging.models.messaging import Channel
from pytests import factories
from pytests.factories import DefaultUserFactory


@pytest.fixture()
def make_channels():
    def _make_channels(
        num_channels: int = 10,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
    ) -> tuple[User, list[Channel]]:
        requesting_user = requesting_user_factory.create()
        now = datetime.datetime.utcnow()

        chans = []

        for i in range(num_channels):
            participant = participant_factory.create()

            org_1 = factories.OrganizationFactory.create(US_restricted=False)
            factories.MemberTrackFactory.create(
                user=requesting_user,
                client_track=factories.ClientTrackFactory(
                    organization=org_1,
                ),
            )

            channel = factories.ChannelFactory.create(
                name=f"{requesting_user.first_name}, {participant.first_name}",
                created_at=now + datetime.timedelta(minutes=i),
            )
            channel_user_member = factories.ChannelUsersFactory.create(
                channel_id=channel.id,
                user_id=requesting_user.id,
                channel=channel,
                user=requesting_user,
            )
            channel_user_prac = factories.ChannelUsersFactory.create(
                channel_id=channel.id,
                user_id=participant.id,
                channel=channel,
                user=participant,
            )
            channel.participants = [channel_user_member, channel_user_prac]

            chans.append(channel)
        return (requesting_user, chans)

    return _make_channels


class TestSchemaBackwardsCompatibility:
    """Auto generated class by scripts/ma_coverage_tool"""

    def test_user_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """

        from views.schemas.base import UserSchemaV3
        from views.schemas.common import UserSchema

        data = {
            "profiles": {
                "member": {
                    "dashboard": None,
                    "opted_in_notes_sharing": True,
                    "tel_region": "Sample text",
                    "has_care_plan": True,
                    "care_plan_id": 2,
                    "user_flags": None,
                    "country": None,
                    "can_book_cx": None,
                    "color_hex": "Sample text",
                    "state": None,
                    "subdivision_code": "Sample text",
                    "phone_number": "Sample text",
                    "tel_number": "Sample text",
                    "address": {
                        "country": "Sample text",
                        "state": "Sample text",
                        "zip_code": "Sample text",
                        "street_address": "Sample text",
                        "city": "Sample text",
                    },
                },
                "practitioner": {
                    "country_code": "Sample text",
                    "certifications": None,
                    "country": {
                        "summary": None,
                        "ext_info_link": None,
                        "name": None,
                        "abbr": None,
                    },
                    "state": None,
                    "rating": 57.25067656188169,
                    "reference_quote": "Sample text",
                    "certified_states": None,
                    "tel_number": "Sample text",
                    "awards": "Sample text",
                    "tel_region": "Sample text",
                    "specialties": None,
                    "is_cx": None,
                    "subdivision_code": "Sample text",
                    "verticals": None,
                    "years_experience": 1,
                    "can_prescribe_to_member": None,
                    "response_time": 1,
                    "categories": None,
                    "education": "Sample text",
                    "faq_password": None,
                    "work_experience": "Sample text",
                    "vertical_objects": [
                        {
                            "pluralized_display_name": "Sample text",
                            "filter_by_state": True,
                            "description": "Sample text",
                            "id": 2,
                            "can_prescribe": False,
                            "long_description": "Sample text",
                            "name": "Sample text",
                        }
                    ],
                    "languages": None,
                    "agreements": {"subscription": False},
                    "next_availability": datetime.datetime(
                        2024, 2, 14, 11, 59, 19, 371255, tzinfo=datetime.timezone.utc
                    ),
                    "cancellation_policy": None,
                    "phone_number": "Sample text",
                    "certified_subdivision_codes": None,
                    "user_id": 1,
                    "care_team_type": None,
                    "messaging_enabled": False,
                    "can_prescribe": None,
                    "address": {
                        "country": "Sample text",
                        "state": "Sample text",
                        "zip_code": "Sample text",
                        "street_address": "Sample text",
                        "city": "Sample text",
                    },
                },
            },
            "country": {
                "summary": None,
                "ext_info_link": None,
                "name": None,
                "abbr": None,
            },
            "email": None,
            "id": 2,
            "middle_name": "Sample text",
            "care_coordinators": [
                {
                    "profiles": {
                        "member": {
                            "dashboard": None,
                            "opted_in_notes_sharing": False,
                            "tel_region": "Sample text",
                            "has_care_plan": True,
                            "care_plan_id": 2,
                            "user_flags": None,
                            "country": None,
                            "can_book_cx": None,
                            "color_hex": "Sample text",
                            "state": None,
                            "subdivision_code": "Sample text",
                            "phone_number": "Sample text",
                            "tel_number": "Sample text",
                            "address": {
                                "country": "Sample text",
                                "state": "Sample text",
                                "zip_code": "Sample text",
                                "street_address": "Sample text",
                                "city": "Sample text",
                            },
                        },
                        "practitioner": {
                            "country_code": "Sample text",
                            "certifications": None,
                            "country": {
                                "summary": None,
                                "ext_info_link": None,
                                "name": None,
                                "abbr": None,
                            },
                            "state": None,
                            "rating": 67.74885480663916,
                            "reference_quote": "Sample text",
                            "certified_states": None,
                            "tel_number": "Sample text",
                            "awards": "Sample text",
                            "tel_region": "Sample text",
                            "specialties": None,
                            "is_cx": None,
                            "subdivision_code": "Sample text",
                            "verticals": None,
                            "years_experience": 2,
                            "can_prescribe_to_member": None,
                            "response_time": 1,
                            "categories": None,
                            "education": "Sample text",
                            "faq_password": None,
                            "work_experience": "Sample text",
                            "vertical_objects": [
                                {
                                    "pluralized_display_name": "Sample text",
                                    "filter_by_state": True,
                                    "description": "Sample text",
                                    "id": 1,
                                    "can_prescribe": True,
                                    "long_description": "Sample text",
                                    "name": "Sample text",
                                }
                            ],
                            "languages": None,
                            "agreements": {"subscription": False},
                            "next_availability": datetime.datetime(
                                2024,
                                2,
                                14,
                                11,
                                59,
                                19,
                                371332,
                                tzinfo=datetime.timezone.utc,
                            ),
                            "cancellation_policy": None,
                            "phone_number": "Sample text",
                            "certified_subdivision_codes": None,
                            "user_id": 1,
                            "care_team_type": None,
                            "messaging_enabled": True,
                            "can_prescribe": None,
                            "address": {
                                "country": "Sample text",
                                "state": "Sample text",
                                "zip_code": "Sample text",
                                "street_address": "Sample text",
                                "city": "Sample text",
                            },
                        },
                    },
                    "image_id": 2,
                    "organization": {
                        "rx_enabled": True,
                        "vertical_group_version": "Sample text",
                        "education_only": True,
                        "id": 2,
                        "bms_enabled": False,
                        "name": "Sample text",
                    },
                    "last_name": "Sample text",
                    "encoded_id": None,
                    "country": {
                        "summary": None,
                        "ext_info_link": None,
                        "name": None,
                        "abbr": None,
                    },
                    "email": None,
                    "role": None,
                    "id": 2,
                    "middle_name": "Sample text",
                    "image_url": None,
                    "username": None,
                    "avatar_url": "Sample text",
                    "subscription_plans": [
                        {
                            "started_at": datetime.datetime(
                                2024,
                                2,
                                14,
                                11,
                                59,
                                19,
                                371369,
                                tzinfo=datetime.timezone.utc,
                            ),
                            "api_id": "Sample text",
                            "cancelled_at": datetime.datetime(
                                2024,
                                2,
                                14,
                                11,
                                59,
                                19,
                                371372,
                                tzinfo=datetime.timezone.utc,
                            ),
                            "plan": {
                                "description": "Sample text",
                                "id": 1,
                                "segment_days": 1,
                                "price_per_segment": None,
                                "minimum_segments": 1,
                                "is_recurring": True,
                                "active": False,
                                "billing_description": "Sample text",
                            },
                            "plan_payer": {
                                "email_address": "Sample text",
                                "email_confirmed": True,
                            },
                            "is_claimed": False,
                            "first_cancellation_date": datetime.datetime(
                                2024,
                                2,
                                14,
                                11,
                                59,
                                19,
                                371386,
                                tzinfo=datetime.timezone.utc,
                            ),
                            "total_segments": 1,
                        }
                    ],
                    "test_group": "Sample text",
                    "esp_id": None,
                    "name": None,
                    "first_name": "Sample text",
                }
            ],
            "username": None,
            "avatar_url": "Sample text",
            "created_at": datetime.datetime(
                2024, 2, 14, 11, 59, 19, 371396, tzinfo=datetime.timezone.utc
            ),
            "subscription_plans": [
                {
                    "started_at": datetime.datetime(
                        2024, 2, 14, 11, 59, 19, 371398, tzinfo=datetime.timezone.utc
                    ),
                    "api_id": "Sample text",
                    "cancelled_at": datetime.datetime(
                        2024, 2, 14, 11, 59, 19, 371401, tzinfo=datetime.timezone.utc
                    ),
                    "plan": {
                        "description": "Sample text",
                        "id": 1,
                        "segment_days": 2,
                        "price_per_segment": None,
                        "minimum_segments": 1,
                        "is_recurring": True,
                        "active": False,
                        "billing_description": "Sample text",
                    },
                    "plan_payer": {
                        "email_address": "Sample text",
                        "email_confirmed": True,
                    },
                    "is_claimed": False,
                    "first_cancellation_date": datetime.datetime(
                        2024, 2, 14, 11, 59, 19, 371416, tzinfo=datetime.timezone.utc
                    ),
                    "total_segments": 1,
                }
            ],
            "esp_id": None,
            "name": None,
            "image_id": 2,
            "organization": {
                "rx_enabled": False,
                "vertical_group_version": "Sample text",
                "education_only": True,
                "id": 2,
                "bms_enabled": False,
                "name": "Sample text",
            },
            "last_name": "Sample text",
            "encoded_id": None,
            "role": None,
            "image_url": None,
            "test_group": "Sample text",
            "first_name": "Sample text",
        }
        v1_schema = UserSchema()
        v3_schema = UserSchemaV3()
        # Since User schema rely on database query for serialize certain field, a mock is needed
        user = DefaultUserFactory.create()
        with patch("storage.connection.db.session.query") as mock_db_query:
            mock_db_query.return_value.filter.return_value.one.return_value = user
            assert v1_schema.dump(data).data == v3_schema.dump(
                data
            ), "Backwards compatibility broken between versions"

    @patch("views.schemas.common.should_enable_can_member_interact")
    def test_practitioner_profile_schema(self, mock_should_enable_can_member_interact):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.base import PractitionerProfileSchemaV3
        from views.schemas.common import PractitionerProfileSchema

        mock_should_enable_can_member_interact.return_value = True
        data = {
            "languages": None,
            "faq_password": None,
            "state": None,
            "next_availability": datetime.datetime(
                2024, 2, 14, 15, 34, 10, 48863, tzinfo=datetime.timezone.utc
            ),
            "certified_states": None,
            "categories": None,
            "phone_number": "Sample text",
            "rating": 35.018671195087194,
            "specialties": None,
            "vertical_objects": [
                {
                    "pluralized_display_name": "Sample text",
                    "id": 2,
                    "name": "Sample text",
                    "can_prescribe": False,
                    "description": "Sample text",
                    "long_description": "Sample text",
                    "filter_by_state": True,
                }
            ],
            "can_prescribe_to_member": None,
            "is_cx": None,
            "care_team_type": None,
            "country": {
                "summary": None,
                "ext_info_link": None,
                "abbr": None,
                "name": None,
            },
            "certifications": None,
            "can_prescribe": None,
            "response_time": 2,
            "verticals": None,
            "education": "Sample text",
            "user_id": 1,
            "cancellation_policy": None,
            "agreements": {"subscription": None},
            "tel_region": "Sample text",
            "awards": "Sample text",
            "subdivision_code": "Sample text",
            "certified_subdivision_codes": None,
            "messaging_enabled": True,
            "years_experience": 2,
            "address": {
                "street_address": None,
                "state": None,
                "zip_code": None,
                "country": None,
                "city": None,
            },
            "country_code": "Sample text",
            "work_experience": "Sample text",
            "tel_number": "Sample text",
            "reference_quote": "Sample text",
        }
        v1_schema = PractitionerProfileSchema()
        v3_schema = PractitionerProfileSchemaV3()
        v3_schema_dump = v3_schema.dump(data)
        if (
            "can_request_availability" in v3_schema_dump.keys()
        ):  # added to v3 post migration, not added to v1
            del v3_schema_dump["can_request_availability"]
        assert (
            v1_schema.dump(data).data == v3_schema_dump
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "languages": None,
            "faq_password": None,
            "state": None,
            "next_availability": None,
            "certified_states": None,
            "categories": None,
            "phone_number": None,
            "rating": None,
            "specialties": None,
            "vertical_objects": None,
            "can_prescribe_to_member": None,
            "is_cx": None,
            "care_team_type": None,
            "country": {
                "summary": None,
                "ext_info_link": None,
                "abbr": None,
                "name": None,
            },
            "certifications": None,
            "can_prescribe": None,
            "response_time": None,
            "verticals": None,
            "education": None,
            "user_id": None,
            "cancellation_policy": None,
            "agreements": {"subscription": None},
            "tel_region": None,
            "awards": None,
            "subdivision_code": None,
            "certified_subdivision_codes": None,
            "messaging_enabled": None,
            "years_experience": None,
            "address": {
                "street_address": None,
                "state": None,
                "zip_code": None,
                "country": None,
                "city": None,
            },
            "country_code": None,
            "work_experience": None,
            "tel_number": None,
            "reference_quote": None,
        }
        v1_schema = PractitionerProfileSchema()
        v3_schema = PractitionerProfileSchemaV3()
        v3_schema_dump = v3_schema.dump(edge_case)
        if (
            "can_request_availability" in v3_schema_dump.keys()
        ):  # added to v3 post migration, not added to v1
            del v3_schema_dump["can_request_availability"]
        assert (
            v1_schema.dump(edge_case).data == v3_schema_dump
        ), "Backwards compatibility broken between versions"

    def test_availability_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.practitioners_availabilities import AvailabilitySchema
        from appointments.schemas.practitioners_availabilities_v3 import (
            AvailabilitySchemaV3,
        )

        data = {
            "start_time": datetime.datetime(
                2024, 3, 7, 13, 42, 3, 664437, tzinfo=datetime.timezone.utc
            ),
            "end_time": datetime.datetime(
                2024, 3, 7, 13, 42, 3, 664447, tzinfo=datetime.timezone.utc
            ),
        }
        v1_schema = AvailabilitySchema()
        v3_schema = AvailabilitySchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"start_time": None, "end_time": None}
        v1_schema = AvailabilitySchema()
        v3_schema = AvailabilitySchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_practitioner_availabilities_data_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.practitioners_availabilities import (
            PractitionerAvailabilitiesDataSchema,
        )
        from appointments.schemas.practitioners_availabilities_v3 import (
            PractitionerAvailabilitiesDataSchemaV3,
        )

        data = {
            "availabilities": [
                {
                    "end_time": datetime.datetime(
                        2024, 3, 7, 13, 42, 30, 144601, tzinfo=datetime.timezone.utc
                    ),
                    "start_time": datetime.datetime(
                        2024, 3, 7, 13, 42, 30, 144612, tzinfo=datetime.timezone.utc
                    ),
                }
            ],
            "duration": 1,
            "practitioner_id": 2,
            "product_price": 64.4734981646622,
            "product_id": 2,
            "total_available_credits": 2,
        }
        v1_schema = PractitionerAvailabilitiesDataSchema()
        v3_schema = PractitionerAvailabilitiesDataSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "availabilities": None,
            "duration": None,
            "practitioner_id": None,
            "product_price": None,
            "product_id": None,
            "total_available_credits": None,
        }
        v1_schema = PractitionerAvailabilitiesDataSchema()
        v3_schema = PractitionerAvailabilitiesDataSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_practitioners_availabilities_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.practitioners_availabilities import (
            PractitionersAvailabilitiesSchema,
        )
        from appointments.schemas.practitioners_availabilities_v3 import (
            PractitionersAvailabilitiesSchemaV3,
        )

        data = {
            "meta": None,
            "pagination": {
                "order_direction": None,
                "offset": None,
                "total": None,
                "limit": None,
            },
            "data": [
                {
                    "product_id": 1,
                    "availabilities": [
                        {
                            "end_time": datetime.datetime(
                                2024,
                                3,
                                7,
                                13,
                                42,
                                40,
                                33908,
                                tzinfo=datetime.timezone.utc,
                            ),
                            "start_time": datetime.datetime(
                                2024,
                                3,
                                7,
                                13,
                                42,
                                40,
                                33918,
                                tzinfo=datetime.timezone.utc,
                            ),
                        }
                    ],
                    "product_price": 20.94640137389539,
                    "total_available_credits": 2,
                    "practitioner_id": 1,
                    "duration": 1,
                }
            ],
        }
        v1_schema = PractitionersAvailabilitiesSchema()
        v3_schema = PractitionersAvailabilitiesSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "meta": None,
            "pagination": {
                "order_direction": None,
                "offset": None,
                "total": None,
                "limit": None,
            },
            "data": None,
        }
        v1_schema = PractitionersAvailabilitiesSchema()
        v3_schema = PractitionersAvailabilitiesSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_practitioners_availabilities_post_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.practitioners_availabilities import (
            PractitionersAvailabilitiesPostSchema,
        )
        from appointments.schemas.practitioners_availabilities_v3 import (
            PractitionersAvailabilitiesPostSchemaV3,
        )

        data = {
            "start_time": datetime.datetime(
                2024, 3, 18, 9, 4, 27, 104786, tzinfo=datetime.timezone.utc
            ),
            "practitioner_ids": None,
            "provider_steerage_sort": False,
            "can_prescribe": False,
            "end_time": datetime.datetime(
                2024, 3, 18, 9, 4, 27, 104803, tzinfo=datetime.timezone.utc
            ),
            "provider_type": "Sample text",
            "offset": 1,
            "order_direction": None,
            "limit": 2,
        }
        v1_schema = PractitionersAvailabilitiesPostSchema()
        v3_schema = PractitionersAvailabilitiesPostSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "start_time": None,
            "practitioner_ids": None,
            "provider_steerage_sort": None,
            "can_prescribe": None,
            "end_time": None,
            "provider_type": None,
            "offset": None,
            "order_direction": None,
            "limit": None,
        }
        v1_schema = PractitionersAvailabilitiesPostSchema()
        v3_schema = PractitionersAvailabilitiesPostSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_v2_vertical_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.base import V2VerticalSchemaV3
        from views.schemas.common import V2VerticalSchema

        data = {
            "long_description": "Sample text",
            "filter_by_state": True,
            "can_prescribe": False,
            "pluralized_display_name": "Sample text",
            "name": "Sample text",
            "description": "Sample text",
            "id": 1,
        }
        v1_schema = V2VerticalSchema()
        v3_schema = V2VerticalSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "long_description": None,
            "filter_by_state": None,
            "can_prescribe": None,
            "pluralized_display_name": None,
            "name": None,
            "description": None,
            "id": None,
        }
        v1_schema = V2VerticalSchema()
        v3_schema = V2VerticalSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_v2_vertical_get_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.base import V2VerticalGetSchemaV3
        from views.schemas.common import V2VerticalGetSchema

        data = {"ids": []}
        v1_schema = V2VerticalGetSchema()
        v3_schema = V2VerticalGetSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"
        assert v1_schema.load(data).data == v3_schema.load(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"ids": None}
        v1_schema = V2VerticalGetSchema()
        v3_schema = V2VerticalGetSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"
        assert v1_schema.load(edge_case).data == v3_schema.load(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_events_get_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.events import EventsGetSchema
        from appointments.schemas.events_v3 import EventsGetSchemaV3

        data = {
            "starts_at": datetime.datetime(
                2024, 2, 23, 11, 31, 59, 91169, tzinfo=datetime.timezone.utc
            ),
            "limit": 1,
            "ends_at": datetime.datetime(
                2024, 2, 23, 11, 31, 59, 91182, tzinfo=datetime.timezone.utc
            ),
            "recurring": False,
            "offset": 2,
            "order_direction": None,
        }
        v1_schema = EventsGetSchema()
        v3_schema = EventsGetSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"
        assert v1_schema.load(
            {
                "starts_at": "2024-02-23 11:31:59",
                "limit": 1,
                "ends_at": "2024-02-23 11:31:59",
                "recurring": False,
                "offset": 2,
                "order_direction": None,
            }
        ).data == v3_schema.load(
            {
                "starts_at": "2024-02-23 11:31:59",
                "limit": 1,
                "ends_at": "2024-02-23 11:31:59",
                "recurring": False,
                "offset": 2,
                "order_direction": None,
            }
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "starts_at": None,
            "limit": None,
            "ends_at": None,
            "recurring": None,
            "offset": None,
            "order_direction": None,
        }
        v1_schema = EventsGetSchema()
        v3_schema = EventsGetSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"
        assert v1_schema.load(edge_case).data == v3_schema.load(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_events_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.events import EventsSchema
        from appointments.schemas.events_v3 import EventsSchemaV3

        data = {
            "meta": {"user_id": None, "starts_at": None, "ends_at": None},
            "data": [
                {
                    "id": 2,
                    "state": "Sample text",
                    "starts_at": datetime.datetime(
                        2024, 2, 23, 12, 59, 50, 296986, tzinfo=datetime.timezone.utc
                    ),
                    "ends_at": datetime.datetime(
                        2024, 2, 23, 12, 59, 50, 296989, tzinfo=datetime.timezone.utc
                    ),
                }
            ],
            "pagination": {
                "offset": None,
                "total": None,
                "limit": None,
                "order_direction": None,
            },
        }
        v1_schema = EventsSchema()
        v3_schema = EventsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "meta": {"user_id": None, "starts_at": None, "ends_at": None},
            "data": None,
            "pagination": {
                "offset": None,
                "total": None,
                "limit": None,
                "order_direction": None,
            },
        }
        v1_schema = EventsSchema()
        v3_schema = EventsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_booking_flow_search_get_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.booking import BookingFlowSearchGetSchema
        from appointments.schemas.booking_v3 import BookingFlowSearchGetSchemaV3

        data = {
            "offset": 2,
            "order_direction": None,
            "limit": 2,
            "query": "Sample text",
            "is_common": True,
        }
        v1_schema = BookingFlowSearchGetSchema()
        v3_schema = BookingFlowSearchGetSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"
        assert v1_schema.load(
            {
                "offset": 2,
                "order_direction": None,
                "limit": 2,
                "query": "Sample text",
                "is_common": True,
            }
        ).data == v3_schema.load(
            {
                "offset": 2,
                "order_direction": None,
                "limit": 2,
                "query": "Sample text",
                "is_common": True,
            }
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "offset": None,
            "order_direction": None,
            "limit": None,
            "query": None,
            "is_common": None,
        }
        v1_schema = BookingFlowSearchGetSchema()
        v3_schema = BookingFlowSearchGetSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"
        assert v1_schema.load(edge_case).data == v3_schema.load(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_booking_flow_search_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.booking import BookingFlowSearchSchema
        from appointments.schemas.booking_v3 import BookingFlowSearchSchemaV3

        data = {
            "pagination": {
                "limit": None,
                "total": None,
                "order_direction": None,
                "offset": None,
            },
            "data": {
                "need_categories": None,
                "needs": None,
                "verticals": None,
                "keywords": None,
                "practitioners": None,
                "specialties": None,
            },
            "meta": None,
        }
        v1_schema = BookingFlowSearchSchema()
        v3_schema = BookingFlowSearchSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "pagination": {
                "limit": None,
                "total": None,
                "order_direction": None,
                "offset": None,
            },
            "data": {
                "need_categories": None,
                "needs": None,
                "verticals": None,
                "keywords": None,
                "practitioners": None,
                "specialties": None,
            },
            "meta": None,
        }
        v1_schema = BookingFlowSearchSchema()
        v3_schema = BookingFlowSearchSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_products_get_args(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.products import ProductsGetArgs
        from views.schemas.products_v3 import ProductsGetArgsV3

        data = {"vertical_name": "Sample text", "practitioner_ids": [123, 456, 789]}
        v1_schema = ProductsGetArgs()
        v3_schema = ProductsGetArgsV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"vertical_name": None, "practitioner_ids": None}
        v1_schema = ProductsGetArgs()
        v3_schema = ProductsGetArgsV3()

        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_products_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.products import ProductsSchema
        from views.schemas.products_v3 import ProductsSchemaV3

        data = {
            "data": [{"id": 1, "practitioner_id": 1, "minutes": 2, "price": None}],
            "pagination": {
                "order_direction": None,
                "total": None,
                "offset": None,
                "limit": None,
            },
            "meta": None,
        }
        v1_schema = ProductsSchema()
        v3_schema = ProductsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "data": None,
            "pagination": {
                "order_direction": None,
                "total": None,
                "offset": None,
                "limit": None,
            },
            "meta": None,
        }
        v1_schema = ProductsSchema()
        v3_schema = ProductsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_image_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.images import ImageSchema
        from views.schemas.images_v3 import ImageSchemaV3

        data = {
            "height": 1,
            "id": 2,
            "filetype": "Sample text",
            "width": 1,
            "url": "Sample text",
        }
        v1_schema = ImageSchema()
        v3_schema = ImageSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "height": None,
            "id": None,
            "filetype": None,
            "width": None,
            "url": None,
        }
        v1_schema = ImageSchema()
        v3_schema = ImageSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_image_get_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.images import ImageGetSchema
        from views.schemas.images_v3 import ImageGetSchemaV3

        data = {"smart": True}
        v1_schema = ImageGetSchema()
        v3_schema = ImageGetSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"smart": None}
        v1_schema = ImageGetSchema()
        v3_schema = ImageGetSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_asset_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.images import AssetSchema
        from views.schemas.images_v3 import AssetSchemaV3

        data = {"url": "Sample text"}
        v1_schema = AssetSchema()
        v3_schema = AssetSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"url": None}
        v1_schema = AssetSchema()
        v3_schema = AssetSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_create_invite_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.enterprise import CreateInviteSchema
        from views.schemas.enterprise_v3 import CreateInviteSchemaV3

        data = {
            "tel_number": "Sample text",
            "id": "Sample text",
            "last_child_birthday": None,
            "phone_number": "Sample text",
            "due_date": None,
            "date_of_birth": None,
            "claimed": True,
            "name": "Sample text",
            "email": "foo@bar.com",
            "tel_region": "Sample text",
        }
        v1_schema = CreateInviteSchema()
        v3_schema = CreateInviteSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "tel_number": None,
            "id": None,
            "last_child_birthday": None,
            "phone_number": None,
            "due_date": None,
            "date_of_birth": None,
            "claimed": None,
            "name": None,
            "email": None,
            "tel_region": None,
        }
        v1_schema = CreateInviteSchema()
        v3_schema = CreateInviteSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_braze_connected_content_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from braze.schemas.content import BrazeConnectedContentSchema
        from braze.schemas.content_v3 import BrazeConnectedContentSchemaV3

        data = {
            "type": "Sample text",
            "esp_id": "Sample text",
            "types": None,
            "token": "Sample text",
        }
        v1_schema = BrazeConnectedContentSchema()
        v3_schema = BrazeConnectedContentSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"type": None, "esp_id": None, "types": None, "token": None}
        v1_schema = BrazeConnectedContentSchema()
        v3_schema = BrazeConnectedContentSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_attachment_schema_1(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.internal import AttachmentSchema
        from views.schemas.internal_v3 import AttachmentSchemaV3

        data = {"token": "Sample text"}
        v1_schema = AttachmentSchema()
        v3_schema = AttachmentSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"token": None}
        v1_schema = AttachmentSchema()
        v3_schema = AttachmentSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_member_profile_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.base import MemberProfileSchemaV3
        from views.schemas.common import MemberProfileSchema

        data = {
            "has_care_plan": True,
            "address": {
                "zip_code": None,
                "street_address": None,
                "country": None,
                "city": None,
                "state": None,
            },
            "phone_number": "Sample text",
            "care_plan_id": 1,
            "opted_in_notes_sharing": False,
            "tel_region": "Sample text",
            "country": None,
            "dashboard": None,
            "tel_number": "Sample text",
            "color_hex": "Sample text",
            "user_flags": None,
            "can_book_cx": None,
            "subdivision_code": "Sample text",
            "state": None,
        }
        v1_schema = MemberProfileSchema()
        v3_schema = MemberProfileSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "has_care_plan": None,
            "address": {
                "zip_code": None,
                "street_address": None,
                "country": None,
                "city": None,
                "state": None,
            },
            "phone_number": None,
            "care_plan_id": None,
            "opted_in_notes_sharing": None,
            "tel_region": None,
            "country": None,
            "dashboard": None,
            "tel_number": None,
            "color_hex": None,
            "user_flags": None,
            "can_book_cx": None,
            "subdivision_code": None,
            "state": None,
        }
        v1_schema = MemberProfileSchema()
        v3_schema = MemberProfileSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_delete_user_request_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from authn.resources.user import (
            DeleteUserRequestSchema,
            DeleteUserRequestSchemaV3,
        )

        data = {"email": "test@test.com", "requested_date": None, "delete_idp": True}
        v1_schema = DeleteUserRequestSchema()
        v3_schema = DeleteUserRequestSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"email": None, "requested_date": None, "delete_idp": None}
        v1_schema = DeleteUserRequestSchema()
        v3_schema = DeleteUserRequestSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions for edge case"

    def test_session_prescription_info_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.appointments import SessionPrescriptionInfoSchema
        from appointments.schemas.appointments_v3 import SessionPrescriptionInfoSchemaV3

        data = {
            "pharmacy_id": "Sample text",
            "pharmacy_info": {
                "City": None,
                "Address2": None,
                "PharmacyId": None,
                "StoreName": None,
                "IsDefault": None,
                "PrimaryPhone": None,
                "ServiceLevel": None,
                "ZipCode": None,
                "Address1": None,
                "State": None,
                "PrimaryFax": None,
                "PrimaryPhoneType": None,
                "Pharmacy": None,
                "IsPreferred": None,
            },
            "enabled": True,
        }
        v1_schema = SessionPrescriptionInfoSchema()
        v3_schema = SessionPrescriptionInfoSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "pharmacy_id": None,
            "pharmacy_info": {
                "City": None,
                "Address2": None,
                "PharmacyId": None,
                "StoreName": None,
                "IsDefault": None,
                "PrimaryPhone": None,
                "ServiceLevel": None,
                "ZipCode": None,
                "Address1": None,
                "State": None,
                "PrimaryFax": None,
                "PrimaryPhoneType": None,
                "Pharmacy": None,
                "IsPreferred": None,
            },
            "enabled": None,
        }
        v1_schema = SessionPrescriptionInfoSchema()
        v3_schema = SessionPrescriptionInfoSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_answer_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.questionnaires import AnswerSchema, AnswerSchemaV3

        data = {
            "soft_deleted_at": datetime.datetime(
                2024, 10, 6, 17, 11, 33, 398282, tzinfo=datetime.timezone.utc
            ),
            "text": "Sample text",
            "oid": "Sample text",
            "id": "Sample text",
            "sort_order": 2,
        }
        v1_schema = AnswerSchema()
        v3_schema = AnswerSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "soft_deleted_at": None,
            "text": None,
            "oid": None,
            "id": None,
            "sort_order": None,
        }
        v1_schema = AnswerSchema()
        v3_schema = AnswerSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_question_set_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.questionnaires import QuestionSetSchema, QuestionSetSchemaV3

        data = {
            "id": "Sample text",
            "soft_deleted_at": datetime.datetime(
                2024, 10, 6, 17, 16, 10, 974697, tzinfo=datetime.timezone.utc
            ),
            "oid": "Sample text",
            "prerequisite_answer_id": "Sample text",
            "questions": None,
            "sort_order": 2,
        }
        v1_schema = QuestionSetSchema()
        v3_schema = QuestionSetSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "id": None,
            "soft_deleted_at": None,
            "oid": None,
            "prerequisite_answer_id": None,
            "questions": None,
            "sort_order": None,
        }
        v1_schema = QuestionSetSchema()
        v3_schema = QuestionSetSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_provider_addendum_answer_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.questionnaires import (
            ProviderAddendumAnswerSchema,
            ProviderAddendumAnswerSchemaV3,
        )

        data = {
            "text": "Sample text",
            "answer_id": "Sample text",
            "date": None,
            "question_id": "Sample text",
        }
        v1_schema = ProviderAddendumAnswerSchema()
        v3_schema = ProviderAddendumAnswerSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"text": None, "answer_id": None, "date": None, "question_id": None}
        v1_schema = ProviderAddendumAnswerSchema()
        v3_schema = ProviderAddendumAnswerSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_session_meta_info_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.common import SessionMetaInfoSchema
        from views.schemas.common_v3 import SessionMetaInfoSchemaV3

        data = {
            "created_at": datetime.datetime(
                2024, 10, 6, 17, 26, 19, 219417, tzinfo=datetime.timezone.utc
            ),
            "notes": "Sample text",
            "draft": True,
            "modified_at": datetime.datetime(
                2024, 10, 6, 17, 26, 19, 219434, tzinfo=datetime.timezone.utc
            ),
        }
        v1_schema = SessionMetaInfoSchema()
        v3_schema = SessionMetaInfoSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "created_at": None,
            "notes": None,
            "draft": None,
            "modified_at": None,
        }
        v1_schema = SessionMetaInfoSchema()
        v3_schema = SessionMetaInfoSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_address_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.common import AddressSchema
        from views.schemas.common_v3 import AddressSchemaV3

        data = {
            "city": "Sample text",
            "zip_code": "Sample text",
            "street_address": "Sample text",
            "country": "Sample text",
            "state": "Sample text",
        }
        v1_schema = AddressSchema()
        v3_schema = AddressSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "city": None,
            "zip_code": None,
            "street_address": None,
            "country": None,
            "state": None,
        }
        v1_schema = AddressSchema()
        v3_schema = AddressSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_agreements_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.common import AgreementsSchema
        from views.schemas.common_v3 import AgreementsSchemaV3

        data = {"subscription": False}
        v1_schema = AgreementsSchema()
        v3_schema = AgreementsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"subscription": None}
        v1_schema = AgreementsSchema()
        v3_schema = AgreementsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_organization_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.common import OrganizationSchema
        from views.schemas.common_v3 import OrganizationSchemaV3

        data = {
            "id": 2,
            "bms_enabled": False,
            "vertical_group_version": "Sample text",
            "rx_enabled": True,
            "name": "Sample text",
            "display_name": "Sample text",
            "education_only": False,
        }
        v1_schema = OrganizationSchema()
        v3_schema = OrganizationSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "id": None,
            "bms_enabled": None,
            "vertical_group_version": None,
            "rx_enabled": None,
            "name": None,
            "display_name": None,
            "education_only": None,
        }
        v1_schema = OrganizationSchema()
        v3_schema = OrganizationSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_video_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.common import VideoSchema
        from views.schemas.common_v3 import VideoSchemaV3

        data = {
            "practitioner_token": "Sample text",
            "member_token": "Sample text",
            "session_id": "Sample text",
        }
        v1_schema = VideoSchema()
        v3_schema = VideoSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "practitioner_token": None,
            "member_token": None,
            "session_id": None,
        }
        v1_schema = VideoSchema()
        v3_schema = VideoSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_dose_spot_pharmacy_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.common import DoseSpotPharmacySchema
        from views.schemas.common_v3 import DoseSpotPharmacySchemaV3

        data = {
            "PharmacyId": "Sample text",
            "State": "Sample text",
            "IsPreferred": False,
            "Pharmacy": "Sample text",
            "Address1": "Sample text",
            "Address2": "Sample text",
            "PrimaryPhoneType": "Sample text",
            "PrimaryFax": "Sample text",
            "ZipCode": "Sample text",
            "IsDefault": True,
            "PrimaryPhone": "Sample text",
            "ServiceLevel": 1,
            "City": "Sample text",
            "StoreName": "Sample text",
        }
        v1_schema = DoseSpotPharmacySchema()
        v3_schema = DoseSpotPharmacySchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "PharmacyId": None,
            "State": None,
            "IsPreferred": None,
            "Pharmacy": None,
            "Address1": None,
            "Address2": None,
            "PrimaryPhoneType": None,
            "PrimaryFax": None,
            "ZipCode": None,
            "IsDefault": None,
            "PrimaryPhone": None,
            "ServiceLevel": None,
            "City": None,
            "StoreName": None,
        }
        v1_schema = DoseSpotPharmacySchema()
        v3_schema = DoseSpotPharmacySchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_questionnaire_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.questionnaires import QuestionnaireSchema, QuestionnaireSchemaV3

        data = {
            "soft_deleted_at": datetime.datetime(
                2024, 10, 8, 15, 38, 34, 118723, tzinfo=datetime.timezone.utc
            ),
            "question_sets": None,
            "sort_order": 1,
            "id": "Sample text",
            "description_text": "Sample text",
            "oid": "Sample text",
            "trigger_answer_ids": None,
            "title_text": "Sample text",
        }
        v1_schema = QuestionnaireSchema()
        v3_schema = QuestionnaireSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "soft_deleted_at": None,
            "question_sets": None,
            "sort_order": None,
            "id": None,
            "description_text": None,
            "oid": None,
            "trigger_answer_ids": None,
            "title_text": None,
        }
        v1_schema = QuestionnaireSchema()
        v3_schema = QuestionnaireSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_question_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.questionnaires import QuestionSchema, QuestionSchemaV3

        data = {
            "oid": "Sample text",
            "required": False,
            "sort_order": 2,
            "label": "Sample text",
            "type": None,
            "answers": None,
            "id": "Sample text",
            "non_db_answer_options_json": None,
            "soft_deleted_at": datetime.datetime(
                2024, 10, 8, 22, 11, 41, 108278, tzinfo=datetime.timezone.utc
            ),
        }
        v1_schema = QuestionSchema()
        v3_schema = QuestionSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "oid": None,
            "required": None,
            "sort_order": None,
            "label": None,
            "type": None,
            "answers": None,
            "id": None,
            "non_db_answer_options_json": None,
            "soft_deleted_at": None,
        }
        v1_schema = QuestionSchema()
        v3_schema = QuestionSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_country_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.schemas.common import CountrySchema
        from views.schemas.common_v3 import CountrySchemaV3

        data = {"name": None, "ext_info_link": None, "abbr": None, "summary": None}
        v1_schema = CountrySchema()
        v3_schema = CountrySchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"name": None, "ext_info_link": None, "abbr": None, "summary": None}
        v1_schema = CountrySchema()
        v3_schema = CountrySchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_minimal_user_profiles_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.appointments import MinimalUserProfilesSchema
        from appointments.schemas.appointments_v3 import MinimalUserProfilesSchemaV3

        data = {
            "practitioner": {
                "years_experience": None,
                "tel_number": None,
                "can_prescribe_to_member": None,
                "tel_region": None,
                "reference_quote": None,
                "rating": None,
                "agreements": {"subscription": None},
                "address": {
                    "street_address": None,
                    "state": None,
                    "zip_code": None,
                    "city": None,
                    "country": None,
                },
                "next_availability": None,
                "faq_password": None,
                "phone_number": None,
                "specialties": None,
                "can_prescribe": None,
                "verticals": None,
                "is_cx": None,
                "care_team_type": None,
                "country_code": None,
                "work_experience": None,
                "response_time": None,
                "can_member_interact": None,
                "user_id": None,
                "messaging_enabled": None,
                "awards": None,
                "certified_states": None,
                "categories": None,
                "cancellation_policy": None,
                "subdivision_code": None,
                "languages": None,
                "certified_subdivision_codes": None,
                "vertical_objects": None,
                "state": None,
                "education": None,
                "certifications": None,
                "country": {
                    "abbr": None,
                    "ext_info_link": None,
                    "name": None,
                    "summary": None,
                },
            }
        }
        v1_schema = MinimalUserProfilesSchema()
        v3_schema = MinimalUserProfilesSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "practitioner": {
                "years_experience": None,
                "tel_number": None,
                "can_prescribe_to_member": None,
                "tel_region": None,
                "reference_quote": None,
                "rating": None,
                "agreements": {"subscription": None},
                "address": {
                    "street_address": None,
                    "state": None,
                    "zip_code": None,
                    "city": None,
                    "country": None,
                },
                "next_availability": None,
                "faq_password": None,
                "phone_number": None,
                "specialties": None,
                "can_prescribe": None,
                "verticals": None,
                "is_cx": None,
                "care_team_type": None,
                "country_code": None,
                "work_experience": None,
                "response_time": None,
                "can_member_interact": None,
                "user_id": None,
                "messaging_enabled": None,
                "awards": None,
                "certified_states": None,
                "categories": None,
                "cancellation_policy": None,
                "subdivision_code": None,
                "languages": None,
                "certified_subdivision_codes": None,
                "vertical_objects": None,
                "state": None,
                "education": None,
                "certifications": None,
                "country": {
                    "abbr": None,
                    "ext_info_link": None,
                    "name": None,
                    "summary": None,
                },
            }
        }
        v1_schema = MinimalUserProfilesSchema()
        v3_schema = MinimalUserProfilesSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_minimal_practitioner_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.appointments import MinimalPractitionerSchema
        from appointments.schemas.appointments_v3 import MinimalPractitionerSchemaV3

        data = {
            "name": None,
            "image_url": None,
            "id": 2,
            "last_name": "Sample text",
            "profiles": {
                "practitioner": {
                    "response_time": None,
                    "care_team_type": None,
                    "country": {
                        "abbr": None,
                        "name": None,
                        "summary": None,
                        "ext_info_link": None,
                    },
                    "next_availability": None,
                    "languages": None,
                    "education": None,
                    "faq_password": None,
                    "work_experience": None,
                    "specialties": None,
                    "can_member_interact": None,
                    "user_id": None,
                    "awards": None,
                    "years_experience": None,
                    "is_cx": None,
                    "tel_region": None,
                    "phone_number": None,
                    "tel_number": None,
                    "can_prescribe": None,
                    "agreements": {"subscription": None},
                    "can_prescribe_to_member": None,
                    "state": None,
                    "cancellation_policy": None,
                    "vertical_objects": None,
                    "rating": None,
                    "certifications": None,
                    "certified_states": None,
                    "verticals": None,
                    "address": {
                        "city": None,
                        "country": None,
                        "zip_code": None,
                        "state": None,
                        "street_address": None,
                    },
                    "categories": None,
                    "reference_quote": None,
                    "messaging_enabled": None,
                    "subdivision_code": None,
                    "certified_subdivision_codes": None,
                    "country_code": None,
                }
            },
            "first_name": "Sample text",
        }
        v1_schema = MinimalPractitionerSchema()
        v3_schema = MinimalPractitionerSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "name": None,
            "image_url": None,
            "id": None,
            "last_name": None,
            "profiles": {
                "practitioner": {
                    "response_time": None,
                    "care_team_type": None,
                    "country": {
                        "abbr": None,
                        "name": None,
                        "summary": None,
                        "ext_info_link": None,
                    },
                    "next_availability": None,
                    "languages": None,
                    "education": None,
                    "faq_password": None,
                    "work_experience": None,
                    "specialties": None,
                    "can_member_interact": None,
                    "user_id": None,
                    "awards": None,
                    "years_experience": None,
                    "is_cx": None,
                    "tel_region": None,
                    "phone_number": None,
                    "tel_number": None,
                    "can_prescribe": None,
                    "agreements": {"subscription": None},
                    "can_prescribe_to_member": None,
                    "state": None,
                    "cancellation_policy": None,
                    "vertical_objects": None,
                    "rating": None,
                    "certifications": None,
                    "certified_states": None,
                    "verticals": None,
                    "address": {
                        "city": None,
                        "country": None,
                        "zip_code": None,
                        "state": None,
                        "street_address": None,
                    },
                    "categories": None,
                    "reference_quote": None,
                    "messaging_enabled": None,
                    "subdivision_code": None,
                    "certified_subdivision_codes": None,
                    "country_code": None,
                }
            },
            "first_name": None,
        }
        v1_schema = MinimalPractitionerSchema()
        v3_schema = MinimalPractitionerSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_minimal_product_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.appointments import MinimalProductSchema
        from appointments.schemas.appointments_v3 import MinimalProductSchemaV3

        data = {
            "practitioner": {
                "profiles": {
                    "practitioner": {
                        "verticals": None,
                        "can_prescribe_to_member": None,
                        "reference_quote": None,
                        "subdivision_code": None,
                        "country": {
                            "ext_info_link": None,
                            "summary": None,
                            "name": None,
                            "abbr": None,
                        },
                        "work_experience": None,
                        "phone_number": None,
                        "years_experience": None,
                        "languages": None,
                        "country_code": None,
                        "certified_states": None,
                        "specialties": None,
                        "certifications": None,
                        "next_availability": None,
                        "is_cx": None,
                        "agreements": {"subscription": None},
                        "awards": None,
                        "response_time": None,
                        "vertical_objects": None,
                        "tel_region": None,
                        "cancellation_policy": None,
                        "faq_password": None,
                        "messaging_enabled": None,
                        "care_team_type": None,
                        "education": None,
                        "tel_number": None,
                        "categories": None,
                        "address": {
                            "zip_code": None,
                            "state": None,
                            "city": None,
                            "street_address": None,
                            "country": None,
                        },
                        "certified_subdivision_codes": None,
                        "can_member_interact": None,
                        "state": None,
                        "user_id": None,
                        "can_prescribe": None,
                        "rating": None,
                    }
                },
                "name": None,
                "image_url": None,
            }
        }
        v1_schema = MinimalProductSchema()
        v3_schema = MinimalProductSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "practitioner": {
                "profiles": {
                    "practitioner": {
                        "verticals": None,
                        "can_prescribe_to_member": None,
                        "reference_quote": None,
                        "subdivision_code": None,
                        "country": {
                            "ext_info_link": None,
                            "summary": None,
                            "name": None,
                            "abbr": None,
                        },
                        "work_experience": None,
                        "phone_number": None,
                        "years_experience": None,
                        "languages": None,
                        "country_code": None,
                        "certified_states": None,
                        "specialties": None,
                        "certifications": None,
                        "next_availability": None,
                        "is_cx": None,
                        "agreements": {"subscription": None},
                        "awards": None,
                        "response_time": None,
                        "vertical_objects": None,
                        "tel_region": None,
                        "cancellation_policy": None,
                        "faq_password": None,
                        "messaging_enabled": None,
                        "care_team_type": None,
                        "education": None,
                        "tel_number": None,
                        "categories": None,
                        "address": {
                            "zip_code": None,
                            "state": None,
                            "city": None,
                            "street_address": None,
                            "country": None,
                        },
                        "certified_subdivision_codes": None,
                        "can_member_interact": None,
                        "state": None,
                        "user_id": None,
                        "can_prescribe": None,
                        "rating": None,
                    }
                },
                "name": None,
                "image_url": None,
            }
        }
        v1_schema = MinimalProductSchema()
        v3_schema = MinimalProductSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_appointments_meta_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.appointments import AppointmentsMetaSchema
        from appointments.schemas.appointments_v3 import AppointmentsMetaSchemaV3

        data = {
            "schedule_event_ids": None,
            "scheduled_end": datetime.datetime(
                2024, 10, 8, 23, 6, 27, 232877, tzinfo=datetime.timezone.utc
            ),
            "scheduled_start": datetime.datetime(
                2024, 10, 8, 23, 6, 27, 232888, tzinfo=datetime.timezone.utc
            ),
        }
        v1_schema = AppointmentsMetaSchema()
        v3_schema = AppointmentsMetaSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "schedule_event_ids": None,
            "scheduled_end": None,
            "scheduled_start": None,
        }
        v1_schema = AppointmentsMetaSchema()
        v3_schema = AppointmentsMetaSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_minimal_appointment_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.appointments import MinimalAppointmentSchema
        from appointments.schemas.appointments_v3 import MinimalAppointmentSchemaV3

        data = {
            "state": "Sample text",
            "product": {
                "practitioner": {
                    "profiles": {
                        "practitioner": {
                            "reference_quote": None,
                            "categories": None,
                            "country": {
                                "summary": None,
                                "ext_info_link": None,
                                "abbr": None,
                                "name": None,
                            },
                            "phone_number": None,
                            "user_id": None,
                            "tel_region": None,
                            "rating": None,
                            "can_prescribe_to_member": None,
                            "faq_password": None,
                            "subdivision_code": None,
                            "state": None,
                            "can_prescribe": None,
                            "languages": None,
                            "years_experience": None,
                            "response_time": None,
                            "is_cx": None,
                            "verticals": None,
                            "care_team_type": None,
                            "certifications": None,
                            "certified_states": None,
                            "specialties": None,
                            "agreements": {"subscription": None},
                            "address": {
                                "state": None,
                                "country": None,
                                "zip_code": None,
                                "street_address": None,
                                "city": None,
                            },
                            "education": None,
                            "next_availability": None,
                            "awards": None,
                            "vertical_objects": None,
                            "certified_subdivision_codes": None,
                            "tel_number": None,
                            "work_experience": None,
                            "can_member_interact": None,
                            "cancellation_policy": None,
                            "messaging_enabled": None,
                            "country_code": None,
                        }
                    },
                    "name": None,
                    "image_url": None,
                }
            },
            "scheduled_end": datetime.datetime(
                2024, 10, 8, 23, 9, 48, 906389, tzinfo=datetime.timezone.utc
            ),
            "appointment_id": None,
            "repeat_patient": False,
            "need": {"description": None, "name": None, "id": None},
            "privacy": None,
            "cancelled_at": datetime.datetime(
                2024, 10, 8, 23, 9, 48, 906399, tzinfo=datetime.timezone.utc
            ),
            "rescheduled_from_previous_appointment_time": None,
            "privilege_type": None,
            "post_session": {
                "created_at": None,
                "draft": None,
                "notes": None,
                "modified_at": None,
            },
            "scheduled_start": datetime.datetime(
                2024, 10, 8, 23, 9, 48, 906412, tzinfo=datetime.timezone.utc
            ),
            "member": {
                "test_group": None,
                "country": {
                    "summary": None,
                    "ext_info_link": None,
                    "abbr": None,
                    "name": None,
                },
                "avatar_url": None,
                "subscription_plans": None,
                "name": None,
                "middle_name": None,
                "last_name": None,
                "organization": {
                    "display_name": None,
                    "education_only": None,
                    "name": None,
                    "rx_enabled": None,
                    "vertical_group_version": None,
                    "bms_enabled": None,
                    "id": None,
                },
                "id": None,
                "esp_id": None,
                "email": None,
                "image_id": None,
                "role": None,
                "username": None,
                "encoded_id": None,
                "first_name": None,
                "image_url": None,
                "created_at": None,
                "profiles": {
                    "member": {
                        "state": None,
                        "color_hex": None,
                        "opted_in_notes_sharing": None,
                        "care_plan_id": None,
                        "user_flags": None,
                        "country": None,
                        "phone_number": None,
                        "tel_region": None,
                        "tel_number": None,
                        "has_care_plan": None,
                        "subdivision_code": None,
                        "can_book_cx": None,
                        "address": {
                            "state": None,
                            "country": None,
                            "zip_code": None,
                            "street_address": None,
                            "city": None,
                        },
                    },
                    "practitioner": {
                        "reference_quote": None,
                        "categories": None,
                        "country": {
                            "summary": None,
                            "ext_info_link": None,
                            "abbr": None,
                            "name": None,
                        },
                        "phone_number": None,
                        "user_id": None,
                        "tel_region": None,
                        "rating": None,
                        "can_prescribe_to_member": None,
                        "faq_password": None,
                        "subdivision_code": None,
                        "state": None,
                        "can_prescribe": None,
                        "languages": None,
                        "years_experience": None,
                        "response_time": None,
                        "is_cx": None,
                        "verticals": None,
                        "care_team_type": None,
                        "certifications": None,
                        "certified_states": None,
                        "specialties": None,
                        "agreements": {"subscription": None},
                        "address": {
                            "state": None,
                            "country": None,
                            "zip_code": None,
                            "street_address": None,
                            "city": None,
                        },
                        "education": None,
                        "next_availability": None,
                        "awards": None,
                        "vertical_objects": None,
                        "certified_subdivision_codes": None,
                        "tel_number": None,
                        "work_experience": None,
                        "can_member_interact": None,
                        "cancellation_policy": None,
                        "messaging_enabled": None,
                        "country_code": None,
                    },
                },
            },
            "pre_session": {
                "created_at": None,
                "draft": None,
                "notes": None,
                "modified_at": None,
            },
            "state_match_type": None,
            "id": None,
        }
        v1_schema = MinimalAppointmentSchema()
        v3_schema = MinimalAppointmentSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "state": None,
            "product": {
                "practitioner": {
                    "profiles": {
                        "practitioner": {
                            "reference_quote": None,
                            "categories": None,
                            "country": {
                                "summary": None,
                                "ext_info_link": None,
                                "abbr": None,
                                "name": None,
                            },
                            "phone_number": None,
                            "user_id": None,
                            "tel_region": None,
                            "rating": None,
                            "can_prescribe_to_member": None,
                            "faq_password": None,
                            "subdivision_code": None,
                            "state": None,
                            "can_prescribe": None,
                            "languages": None,
                            "years_experience": None,
                            "response_time": None,
                            "is_cx": None,
                            "verticals": None,
                            "care_team_type": None,
                            "certifications": None,
                            "certified_states": None,
                            "specialties": None,
                            "agreements": {"subscription": None},
                            "address": {
                                "state": None,
                                "country": None,
                                "zip_code": None,
                                "street_address": None,
                                "city": None,
                            },
                            "education": None,
                            "next_availability": None,
                            "awards": None,
                            "vertical_objects": None,
                            "certified_subdivision_codes": None,
                            "tel_number": None,
                            "work_experience": None,
                            "can_member_interact": None,
                            "cancellation_policy": None,
                            "messaging_enabled": None,
                            "country_code": None,
                        }
                    },
                    "name": None,
                    "image_url": None,
                }
            },
            "scheduled_end": None,
            "appointment_id": None,
            "repeat_patient": None,
            "need": {"description": None, "name": None, "id": None},
            "privacy": None,
            "cancelled_at": None,
            "rescheduled_from_previous_appointment_time": None,
            "privilege_type": None,
            "post_session": {
                "created_at": None,
                "draft": None,
                "notes": None,
                "modified_at": None,
            },
            "scheduled_start": None,
            "member": {
                "test_group": None,
                "country": {
                    "summary": None,
                    "ext_info_link": None,
                    "abbr": None,
                    "name": None,
                },
                "avatar_url": None,
                "subscription_plans": None,
                "name": None,
                "middle_name": None,
                "last_name": None,
                "organization": {
                    "display_name": None,
                    "education_only": None,
                    "name": None,
                    "rx_enabled": None,
                    "vertical_group_version": None,
                    "bms_enabled": None,
                    "id": None,
                },
                "id": None,
                "esp_id": None,
                "email": None,
                "image_id": None,
                "role": None,
                "username": None,
                "encoded_id": None,
                "first_name": None,
                "image_url": None,
                "created_at": None,
                "profiles": {
                    "member": {
                        "state": None,
                        "color_hex": None,
                        "opted_in_notes_sharing": None,
                        "care_plan_id": None,
                        "user_flags": None,
                        "country": None,
                        "phone_number": None,
                        "tel_region": None,
                        "tel_number": None,
                        "has_care_plan": None,
                        "subdivision_code": None,
                        "can_book_cx": None,
                        "address": {
                            "state": None,
                            "country": None,
                            "zip_code": None,
                            "street_address": None,
                            "city": None,
                        },
                    },
                    "practitioner": {
                        "reference_quote": None,
                        "categories": None,
                        "country": {
                            "summary": None,
                            "ext_info_link": None,
                            "abbr": None,
                            "name": None,
                        },
                        "phone_number": None,
                        "user_id": None,
                        "tel_region": None,
                        "rating": None,
                        "can_prescribe_to_member": None,
                        "faq_password": None,
                        "subdivision_code": None,
                        "state": None,
                        "can_prescribe": None,
                        "languages": None,
                        "years_experience": None,
                        "response_time": None,
                        "is_cx": None,
                        "verticals": None,
                        "care_team_type": None,
                        "certifications": None,
                        "certified_states": None,
                        "specialties": None,
                        "agreements": {"subscription": None},
                        "address": {
                            "state": None,
                            "country": None,
                            "zip_code": None,
                            "street_address": None,
                            "city": None,
                        },
                        "education": None,
                        "next_availability": None,
                        "awards": None,
                        "vertical_objects": None,
                        "certified_subdivision_codes": None,
                        "tel_number": None,
                        "work_experience": None,
                        "can_member_interact": None,
                        "cancellation_policy": None,
                        "messaging_enabled": None,
                        "country_code": None,
                    },
                },
            },
            "pre_session": {
                "created_at": None,
                "draft": None,
                "notes": None,
                "modified_at": None,
            },
            "state_match_type": None,
            "id": None,
        }
        v1_schema = MinimalAppointmentSchema()
        v3_schema = MinimalAppointmentSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_appointment_get_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.appointments import AppointmentGetSchema
        from appointments.schemas.appointments_v3 import AppointmentGetSchemaV3

        data = {
            "order_direction": None,
            "purposes": None,
            "practitioner_id": 2,
            "offset": 1,
            "minimal": True,
            "limit": 1,
            "scheduled_start": datetime.datetime(
                2024, 10, 8, 23, 20, 10, 984722, tzinfo=datetime.timezone.utc
            ),
            "exclude_statuses": None,
            "scheduled_end": datetime.datetime(
                2024, 10, 8, 23, 20, 10, 984736, tzinfo=datetime.timezone.utc
            ),
            "scheduled_start_before": datetime.datetime(
                2024, 10, 8, 23, 20, 10, 984739, tzinfo=datetime.timezone.utc
            ),
            "schedule_event_ids": None,
            "member_id": 1,
        }
        v1_schema = AppointmentGetSchema()
        v3_schema = AppointmentGetSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "order_direction": None,
            "purposes": None,
            "practitioner_id": None,
            "offset": None,
            "minimal": None,
            "limit": None,
            "scheduled_start": None,
            "exclude_statuses": None,
            "scheduled_end": None,
            "scheduled_start_before": None,
            "schedule_event_ids": None,
            "member_id": None,
        }
        v1_schema = AppointmentGetSchema()
        v3_schema = AppointmentGetSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_minimal_appointments_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.appointments import MinimalAppointmentsSchema
        from appointments.schemas.appointments_v3 import MinimalAppointmentsSchemaV3

        data = {
            "data": [
                {
                    "post_session": {
                        "created_at": datetime.datetime(
                            2024, 10, 8, 23, 29, 9, 820522, tzinfo=datetime.timezone.utc
                        ),
                        "modified_at": datetime.datetime(
                            2024, 10, 8, 23, 29, 9, 820533, tzinfo=datetime.timezone.utc
                        ),
                        "notes": "Sample text",
                        "draft": False,
                    },
                    "pre_session": {
                        "created_at": datetime.datetime(
                            2024, 10, 8, 23, 29, 9, 820542, tzinfo=datetime.timezone.utc
                        ),
                        "modified_at": datetime.datetime(
                            2024, 10, 8, 23, 29, 9, 820545, tzinfo=datetime.timezone.utc
                        ),
                        "notes": "Sample text",
                        "draft": True,
                    },
                    "scheduled_start": datetime.datetime(
                        2024, 10, 8, 23, 29, 9, 820549, tzinfo=datetime.timezone.utc
                    ),
                    "state": "Sample text",
                    "repeat_patient": True,
                    "scheduled_end": datetime.datetime(
                        2024, 10, 8, 23, 29, 9, 820554, tzinfo=datetime.timezone.utc
                    ),
                    "need": {
                        "id": 2,
                        "description": "Sample text",
                        "name": "Sample text",
                    },
                    "cancelled_at": datetime.datetime(
                        2024, 10, 8, 23, 29, 9, 820561, tzinfo=datetime.timezone.utc
                    ),
                    "state_match_type": None,
                    "id": None,
                    "rescheduled_from_previous_appointment_time": None,
                    "product": {
                        "practitioner": {
                            "profiles": {
                                "practitioner": {
                                    "user_id": 2,
                                    "state": None,
                                    "categories": None,
                                    "subdivision_code": "Sample text",
                                    "response_time": 1,
                                    "specialties": None,
                                    "tel_region": "Sample text",
                                    "can_member_interact": None,
                                    "country": {
                                        "summary": None,
                                        "ext_info_link": None,
                                        "name": None,
                                        "abbr": None,
                                    },
                                    "awards": "Sample text",
                                    "can_prescribe_to_member": None,
                                    "cancellation_policy": None,
                                    "messaging_enabled": False,
                                    "certified_states": None,
                                    "certifications": None,
                                    "languages": None,
                                    "phone_number": "Sample text",
                                    "address": {
                                        "state": "Sample text",
                                        "city": "Sample text",
                                        "street_address": "Sample text",
                                        "zip_code": "Sample text",
                                        "country": "Sample text",
                                    },
                                    "education": "Sample text",
                                    "agreements": {"subscription": False},
                                    "faq_password": None,
                                    "rating": 37.76417290762977,
                                    "reference_quote": "Sample text",
                                    "years_experience": 2,
                                    "tel_number": "Sample text",
                                    "work_experience": "Sample text",
                                    "is_cx": None,
                                    "verticals": None,
                                    "next_availability": datetime.datetime(
                                        2024,
                                        10,
                                        8,
                                        23,
                                        29,
                                        9,
                                        820607,
                                        tzinfo=datetime.timezone.utc,
                                    ),
                                    "care_team_type": None,
                                    "certified_subdivision_codes": None,
                                    "can_prescribe": None,
                                    "country_code": "Sample text",
                                    "vertical_objects": [
                                        {
                                            "long_description": "Sample text",
                                            "description": "Sample text",
                                            "name": "Sample text",
                                            "pluralized_display_name": "Sample text",
                                            "can_prescribe": True,
                                            "filter_by_state": True,
                                            "id": 2,
                                        }
                                    ],
                                }
                            },
                            "name": None,
                            "image_url": None,
                        }
                    },
                    "appointment_id": None,
                    "privacy": None,
                    "privilege_type": None,
                    "member": {
                        "test_group": "Sample text",
                        "role": None,
                        "email": None,
                        "organization": {
                            "name": "Sample text",
                            "bms_enabled": True,
                            "vertical_group_version": "Sample text",
                            "rx_enabled": True,
                            "display_name": "Sample text",
                            "education_only": True,
                            "id": 2,
                        },
                        "name": None,
                        "middle_name": "Sample text",
                        "encoded_id": None,
                        "subscription_plans": [
                            {
                                "plan": {
                                    "active": True,
                                    "price_per_segment": None,
                                    "minimum_segments": 2,
                                    "description": "Sample text",
                                    "billing_description": "Sample text",
                                    "is_recurring": True,
                                    "segment_days": 2,
                                    "id": 1,
                                },
                                "total_segments": 1,
                                "first_cancellation_date": datetime.datetime(
                                    2024,
                                    10,
                                    8,
                                    23,
                                    29,
                                    9,
                                    820653,
                                    tzinfo=datetime.timezone.utc,
                                ),
                                "plan_payer": {
                                    "email_confirmed": True,
                                    "email_address": "Sample text",
                                },
                                "api_id": "Sample text",
                                "is_claimed": True,
                                "started_at": datetime.datetime(
                                    2024,
                                    10,
                                    8,
                                    23,
                                    29,
                                    9,
                                    820660,
                                    tzinfo=datetime.timezone.utc,
                                ),
                                "cancelled_at": datetime.datetime(
                                    2024,
                                    10,
                                    8,
                                    23,
                                    29,
                                    9,
                                    820662,
                                    tzinfo=datetime.timezone.utc,
                                ),
                            }
                        ],
                        "id": 1,
                        "username": None,
                        "country": {
                            "summary": None,
                            "ext_info_link": None,
                            "name": None,
                            "abbr": None,
                        },
                        "last_name": "Sample text",
                        "created_at": datetime.datetime(
                            2024, 10, 8, 23, 29, 9, 820674, tzinfo=datetime.timezone.utc
                        ),
                        "esp_id": None,
                        "profiles": {
                            "practitioner": {
                                "user_id": 1,
                                "state": None,
                                "categories": None,
                                "subdivision_code": "Sample text",
                                "response_time": 2,
                                "specialties": None,
                                "tel_region": "Sample text",
                                "can_member_interact": None,
                                "country": {
                                    "summary": None,
                                    "ext_info_link": None,
                                    "name": None,
                                    "abbr": None,
                                },
                                "awards": "Sample text",
                                "can_prescribe_to_member": None,
                                "cancellation_policy": None,
                                "messaging_enabled": True,
                                "certified_states": None,
                                "certifications": None,
                                "languages": None,
                                "phone_number": "Sample text",
                                "address": {
                                    "state": "Sample text",
                                    "city": "Sample text",
                                    "street_address": "Sample text",
                                    "zip_code": "Sample text",
                                    "country": "Sample text",
                                },
                                "education": "Sample text",
                                "agreements": {"subscription": False},
                                "faq_password": None,
                                "rating": 18.953181664689133,
                                "reference_quote": "Sample text",
                                "years_experience": 1,
                                "tel_number": "Sample text",
                                "work_experience": "Sample text",
                                "is_cx": None,
                                "verticals": None,
                                "next_availability": datetime.datetime(
                                    2024,
                                    10,
                                    8,
                                    23,
                                    29,
                                    9,
                                    820716,
                                    tzinfo=datetime.timezone.utc,
                                ),
                                "care_team_type": None,
                                "certified_subdivision_codes": None,
                                "can_prescribe": None,
                                "country_code": "Sample text",
                                "vertical_objects": [
                                    {
                                        "long_description": "Sample text",
                                        "description": "Sample text",
                                        "name": "Sample text",
                                        "pluralized_display_name": "Sample text",
                                        "can_prescribe": False,
                                        "filter_by_state": True,
                                        "id": 1,
                                    }
                                ],
                            },
                            "member": {
                                "address": {
                                    "state": "Sample text",
                                    "city": "Sample text",
                                    "street_address": "Sample text",
                                    "zip_code": "Sample text",
                                    "country": "Sample text",
                                },
                                "opted_in_notes_sharing": False,
                                "state": None,
                                "subdivision_code": "Sample text",
                                "care_plan_id": 1,
                                "tel_number": "Sample text",
                                "has_care_plan": False,
                                "user_flags": None,
                                "color_hex": "Sample text",
                                "tel_region": "Sample text",
                                "phone_number": "Sample text",
                                "country": None,
                                "can_book_cx": None,
                            },
                        },
                        "avatar_url": "Sample text",
                        "first_name": "Sample text",
                        "image_url": None,
                        "image_id": 2,
                    },
                }
            ],
            "meta": {
                "scheduled_end": None,
                "scheduled_start": None,
                "schedule_event_ids": None,
            },
            "pagination": {
                "total": None,
                "order_direction": None,
                "limit": None,
                "offset": None,
            },
        }
        v1_schema = MinimalAppointmentsSchema()
        v3_schema = MinimalAppointmentsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "data": None,
            "meta": {
                "scheduled_end": None,
                "scheduled_start": None,
                "schedule_event_ids": None,
            },
            "pagination": {
                "total": None,
                "order_direction": None,
                "limit": None,
                "offset": None,
            },
        }
        v1_schema = MinimalAppointmentsSchema()
        v3_schema = MinimalAppointmentsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    @patch(
        "appointments.schemas.appointments_v3.AppointmentSchemaV3._get_member_rating_data"
    )
    @patch(
        "appointments.schemas.appointments_v3.AppointmentSchemaV3.get_post_session_notes"
    )
    @patch("appointments.schemas.appointments.AppointmentSchema.get_post_session_notes")
    @patch(
        "appointments.schemas.appointments.AppointmentSchema._get_member_rating_data"
    )
    def test_appointment_schema(
        self,
        get_member_rating_data_v1,
        get_post_session_notes_v1,
        get_post_session_notes_v3,
        get_member_rating_data_v3,
    ):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.schemas.appointments import AppointmentSchema
        from appointments.schemas.appointments_v3 import AppointmentSchemaV3

        data = {
            "practitioner_started_at": datetime.datetime(
                2024, 10, 9, 16, 28, 46, 220112, tzinfo=datetime.timezone.utc
            ),
            "member_started_at": datetime.datetime(
                2024, 10, 9, 16, 28, 46, 220124, tzinfo=datetime.timezone.utc
            ),
            "rx_enabled": True,
            "phone_call_at": datetime.datetime(
                2024, 10, 9, 16, 28, 46, 220133, tzinfo=datetime.timezone.utc
            ),
            "appointment_type": None,
            "id": None,
            "rescheduled_from_previous_appointment_time": None,
            "schedule_event_id": 2,
            "pre_session": {
                "created_at": None,
                "modified_at": None,
                "draft": None,
                "notes": None,
            },
            "state": "Sample text",
            "member_ended_at": datetime.datetime(
                2024, 10, 9, 16, 28, 46, 220154, tzinfo=datetime.timezone.utc
            ),
            "video": {
                "member_token": None,
                "practitioner_token": None,
                "session_id": None,
            },
            "cancelled_by": None,
            "provider_addenda": {
                "description_text": None,
                "question_sets": None,
                "id": None,
                "sort_order": None,
                "title_text": None,
                "oid": None,
                "soft_deleted_at": None,
                "trigger_answer_ids": None,
            },
            "rx_written_via": "Sample text",
            "repeat_patient": True,
            "need_id": 1,
            "rx_written_at": datetime.datetime(
                2024, 10, 9, 16, 28, 46, 220174, tzinfo=datetime.timezone.utc
            ),
            "practitioner_ended_at": datetime.datetime(
                2024, 10, 9, 16, 28, 46, 220177, tzinfo=datetime.timezone.utc
            ),
            "cancelled_note": "Sample text",
            "prescription_info": {
                "pharmacy_info": {
                    "StoreName": None,
                    "ZipCode": None,
                    "Address2": None,
                    "Pharmacy": None,
                    "PrimaryPhoneType": None,
                    "PharmacyId": None,
                    "PrimaryFax": None,
                    "IsPreferred": None,
                    "City": None,
                    "IsDefault": None,
                    "ServiceLevel": None,
                    "PrimaryPhone": None,
                    "State": None,
                    "Address1": None,
                },
                "enabled": None,
                "pharmacy_id": None,
            },
            "ratings": None,
            "need": {"name": None, "description": None, "id": None},
            "product": {
                "id": None,
                "price": None,
                "vertical_id": None,
                "practitioner": {
                    "role": None,
                    "id": None,
                    "profiles": {
                        "member": {
                            "tel_region": None,
                            "color_hex": None,
                            "can_book_cx": None,
                            "tel_number": None,
                            "has_care_plan": None,
                            "state": None,
                            "phone_number": None,
                            "address": {
                                "city": None,
                                "state": None,
                                "zip_code": None,
                                "street_address": None,
                                "country": None,
                            },
                            "subdivision_code": None,
                            "user_flags": None,
                            "country": None,
                            "opted_in_notes_sharing": None,
                            "care_plan_id": None,
                        },
                        "practitioner": {
                            "verticals": None,
                            "rating": None,
                            "state": None,
                            "faq_password": None,
                            "can_prescribe": None,
                            "phone_number": None,
                            "care_team_type": None,
                            "subdivision_code": None,
                            "awards": None,
                            "work_experience": None,
                            "categories": None,
                            "education": None,
                            "tel_number": None,
                            "years_experience": None,
                            "reference_quote": None,
                            "address": {
                                "city": None,
                                "state": None,
                                "zip_code": None,
                                "street_address": None,
                                "country": None,
                            },
                            "languages": None,
                            "specialties": None,
                            "user_id": None,
                            "certifications": None,
                            "tel_region": None,
                            "messaging_enabled": None,
                            "certified_states": None,
                            "certified_subdivision_codes": None,
                            "country_code": None,
                            "cancellation_policy": None,
                            "next_availability": None,
                            "response_time": None,
                            "can_member_interact": None,
                            "can_prescribe_to_member": None,
                            "vertical_objects": None,
                            "agreements": {"subscription": None},
                            "country": {
                                "name": None,
                                "ext_info_link": None,
                                "summary": None,
                                "abbr": None,
                            },
                            "is_cx": None,
                        },
                    },
                    "care_coordinators": None,
                    "subscription_plans": None,
                    "email": None,
                    "organization": {
                        "rx_enabled": None,
                        "id": None,
                        "name": None,
                        "display_name": None,
                        "education_only": None,
                        "bms_enabled": None,
                        "vertical_group_version": None,
                    },
                    "image_url": None,
                    "test_group": None,
                    "name": None,
                    "esp_id": None,
                    "first_name": None,
                    "last_name": None,
                    "image_id": None,
                    "encoded_id": None,
                    "middle_name": None,
                    "username": None,
                    "country": {
                        "name": None,
                        "ext_info_link": None,
                        "summary": None,
                        "abbr": None,
                    },
                    "avatar_url": None,
                },
                "minutes": None,
            },
            "scheduled_start": datetime.datetime(
                2024, 10, 9, 16, 28, 46, 220486, tzinfo=datetime.timezone.utc
            ),
            "rx_reason": "Sample text",
            "post_session": {
                "created_at": None,
                "modified_at": None,
                "draft": None,
                "notes": None,
            },
            "state_match_type": None,
            "disputed_at": datetime.datetime(
                2024, 10, 9, 16, 28, 46, 220499, tzinfo=datetime.timezone.utc
            ),
            "privilege_type": None,
            "cancellation_policy": None,
            "surveys": {
                "description_text": None,
                "question_sets": None,
                "id": None,
                "sort_order": None,
                "title_text": None,
                "oid": None,
                "soft_deleted_at": None,
                "trigger_answer_ids": None,
            },
            "purpose": "Sample text",
            "member": {
                "role": None,
                "id": None,
                "profiles": {
                    "member": {
                        "tel_region": None,
                        "color_hex": None,
                        "can_book_cx": None,
                        "tel_number": None,
                        "has_care_plan": None,
                        "state": None,
                        "phone_number": None,
                        "address": {
                            "city": None,
                            "state": None,
                            "zip_code": None,
                            "street_address": None,
                            "country": None,
                        },
                        "subdivision_code": None,
                        "user_flags": None,
                        "country": None,
                        "opted_in_notes_sharing": None,
                        "care_plan_id": None,
                    },
                    "practitioner": {
                        "verticals": None,
                        "rating": None,
                        "state": None,
                        "faq_password": None,
                        "can_prescribe": None,
                        "phone_number": None,
                        "care_team_type": None,
                        "subdivision_code": None,
                        "awards": None,
                        "work_experience": None,
                        "categories": None,
                        "education": None,
                        "tel_number": None,
                        "years_experience": None,
                        "reference_quote": None,
                        "address": {
                            "city": None,
                            "state": None,
                            "zip_code": None,
                            "street_address": None,
                            "country": None,
                        },
                        "languages": None,
                        "specialties": None,
                        "user_id": None,
                        "certifications": None,
                        "tel_region": None,
                        "messaging_enabled": None,
                        "certified_states": None,
                        "certified_subdivision_codes": None,
                        "country_code": None,
                        "cancellation_policy": None,
                        "next_availability": None,
                        "response_time": None,
                        "can_member_interact": None,
                        "can_prescribe_to_member": None,
                        "vertical_objects": None,
                        "agreements": {"subscription": None},
                        "country": {
                            "name": None,
                            "ext_info_link": None,
                            "summary": None,
                            "abbr": None,
                        },
                        "is_cx": None,
                    },
                },
                "subscription_plans": None,
                "email": None,
                "organization": {
                    "rx_enabled": None,
                    "id": None,
                    "name": None,
                    "display_name": None,
                    "education_only": None,
                    "bms_enabled": None,
                    "vertical_group_version": None,
                },
                "created_at": None,
                "image_url": None,
                "test_group": None,
                "name": None,
                "esp_id": None,
                "first_name": None,
                "last_name": None,
                "image_id": None,
                "encoded_id": None,
                "middle_name": None,
                "username": None,
                "country": {
                    "name": None,
                    "ext_info_link": None,
                    "summary": None,
                    "abbr": None,
                },
                "avatar_url": None,
            },
            "cancelled_at": datetime.datetime(
                2024, 10, 9, 16, 28, 46, 220647, tzinfo=datetime.timezone.utc
            ),
            "structured_internal_note": {
                "submitted_at": None,
                "appointment_id": None,
                "id": None,
                "recorded_answers": None,
                "questionnaire_id": None,
                "modified_at": None,
                "source_user_id": None,
                "draft": None,
            },
            "member_rating": {
                "description_text": None,
                "question_sets": None,
                "id": None,
                "sort_order": None,
                "title_text": None,
                "oid": None,
                "soft_deleted_at": None,
                "trigger_answer_ids": None,
            },
            "scheduled_end": datetime.datetime(
                2024, 10, 9, 16, 28, 46, 220672, tzinfo=datetime.timezone.utc
            ),
            "privacy": None,
        }
        v1_schema = AppointmentSchema()
        v3_schema = AppointmentSchemaV3()

        user = DefaultUserFactory.create()
        get_post_session_notes_v1.return_value = {
            "draft": None,
            "notes": "",
            "created_at": None,
            "modified_at": None,
        }
        get_member_rating_data_v1.return_value = ([], [])
        get_post_session_notes_v3.return_value = None
        get_member_rating_data_v3.return_value = ([], [])

        with patch("storage.connection.db.session.query") as mock_db_query:
            mock_db_query.return_value.filter.return_value.one.return_value = user
            v3_schema_dump = v3_schema.dump(data)
            del v3_schema_dump["product"]["practitioner"]["profiles"]["practitioner"][
                "can_request_availability"
            ]
            assert (
                v1_schema.dump(data).data == v3_schema_dump
            ), "Backwards compatibility broken between versions"

        edge_case = {
            "practitioner_started_at": None,
            "member_started_at": None,
            "rx_enabled": None,
            "phone_call_at": None,
            "appointment_type": None,
            "id": None,
            "rescheduled_from_previous_appointment_time": None,
            "schedule_event_id": None,
            "pre_session": {
                "created_at": None,
                "modified_at": None,
                "draft": None,
                "notes": None,
            },
            "state": None,
            "member_ended_at": None,
            "video": {
                "member_token": None,
                "practitioner_token": None,
                "session_id": None,
            },
            "cancelled_by": None,
            "provider_addenda": {
                "description_text": None,
                "question_sets": None,
                "id": None,
                "sort_order": None,
                "title_text": None,
                "oid": None,
                "soft_deleted_at": None,
                "trigger_answer_ids": None,
            },
            "rx_written_via": None,
            "repeat_patient": None,
            "need_id": None,
            "rx_written_at": None,
            "practitioner_ended_at": None,
            "cancelled_note": None,
            "prescription_info": {
                "pharmacy_info": {
                    "StoreName": None,
                    "ZipCode": None,
                    "Address2": None,
                    "Pharmacy": None,
                    "PrimaryPhoneType": None,
                    "PharmacyId": None,
                    "PrimaryFax": None,
                    "IsPreferred": None,
                    "City": None,
                    "IsDefault": None,
                    "ServiceLevel": None,
                    "PrimaryPhone": None,
                    "State": None,
                    "Address1": None,
                },
                "enabled": None,
                "pharmacy_id": None,
            },
            "ratings": None,
            "need": {"name": None, "description": None, "id": None},
            "product": {
                "id": None,
                "price": None,
                "vertical_id": None,
                "practitioner": {
                    "role": None,
                    "id": None,
                    "profiles": {
                        "member": {
                            "tel_region": None,
                            "color_hex": None,
                            "can_book_cx": None,
                            "tel_number": None,
                            "has_care_plan": None,
                            "state": None,
                            "phone_number": None,
                            "address": {
                                "city": None,
                                "state": None,
                                "zip_code": None,
                                "street_address": None,
                                "country": None,
                            },
                            "subdivision_code": None,
                            "user_flags": None,
                            "country": None,
                            "opted_in_notes_sharing": None,
                            "care_plan_id": None,
                        },
                        "practitioner": {
                            "verticals": None,
                            "rating": None,
                            "state": None,
                            "faq_password": None,
                            "can_prescribe": None,
                            "phone_number": None,
                            "care_team_type": None,
                            "subdivision_code": None,
                            "awards": None,
                            "work_experience": None,
                            "categories": None,
                            "education": None,
                            "tel_number": None,
                            "years_experience": None,
                            "reference_quote": None,
                            "address": {
                                "city": None,
                                "state": None,
                                "zip_code": None,
                                "street_address": None,
                                "country": None,
                            },
                            "languages": None,
                            "specialties": None,
                            "user_id": None,
                            "certifications": None,
                            "tel_region": None,
                            "messaging_enabled": None,
                            "certified_states": None,
                            "certified_subdivision_codes": None,
                            "country_code": None,
                            "cancellation_policy": None,
                            "next_availability": None,
                            "response_time": None,
                            "can_member_interact": None,
                            "can_prescribe_to_member": None,
                            "vertical_objects": None,
                            "agreements": {"subscription": None},
                            "country": {
                                "name": None,
                                "ext_info_link": None,
                                "summary": None,
                                "abbr": None,
                            },
                            "is_cx": None,
                        },
                    },
                    "care_coordinators": None,
                    "subscription_plans": None,
                    "email": None,
                    "organization": {
                        "rx_enabled": None,
                        "id": None,
                        "name": None,
                        "display_name": None,
                        "education_only": None,
                        "bms_enabled": None,
                        "vertical_group_version": None,
                    },
                    "image_url": None,
                    "test_group": None,
                    "name": None,
                    "esp_id": None,
                    "first_name": None,
                    "last_name": None,
                    "image_id": None,
                    "encoded_id": None,
                    "middle_name": None,
                    "username": None,
                    "country": {
                        "name": None,
                        "ext_info_link": None,
                        "summary": None,
                        "abbr": None,
                    },
                    "avatar_url": None,
                },
                "minutes": None,
            },
            "scheduled_start": None,
            "rx_reason": None,
            "post_session": {
                "created_at": None,
                "modified_at": None,
                "draft": None,
                "notes": None,
            },
            "state_match_type": None,
            "disputed_at": None,
            "privilege_type": None,
            "cancellation_policy": None,
            "surveys": {
                "description_text": None,
                "question_sets": None,
                "id": None,
                "sort_order": None,
                "title_text": None,
                "oid": None,
                "soft_deleted_at": None,
                "trigger_answer_ids": None,
            },
            "purpose": None,
            "member": {
                "role": None,
                "id": None,
                "profiles": {
                    "member": {
                        "tel_region": None,
                        "color_hex": None,
                        "can_book_cx": None,
                        "tel_number": None,
                        "has_care_plan": None,
                        "state": None,
                        "phone_number": None,
                        "address": {
                            "city": None,
                            "state": None,
                            "zip_code": None,
                            "street_address": None,
                            "country": None,
                        },
                        "subdivision_code": None,
                        "user_flags": None,
                        "country": None,
                        "opted_in_notes_sharing": None,
                        "care_plan_id": None,
                    },
                    "practitioner": {
                        "verticals": None,
                        "rating": None,
                        "state": None,
                        "faq_password": None,
                        "can_prescribe": None,
                        "phone_number": None,
                        "care_team_type": None,
                        "subdivision_code": None,
                        "awards": None,
                        "work_experience": None,
                        "categories": None,
                        "education": None,
                        "tel_number": None,
                        "years_experience": None,
                        "reference_quote": None,
                        "address": {
                            "city": None,
                            "state": None,
                            "zip_code": None,
                            "street_address": None,
                            "country": None,
                        },
                        "languages": None,
                        "specialties": None,
                        "user_id": None,
                        "certifications": None,
                        "tel_region": None,
                        "messaging_enabled": None,
                        "certified_states": None,
                        "certified_subdivision_codes": None,
                        "country_code": None,
                        "cancellation_policy": None,
                        "next_availability": None,
                        "response_time": None,
                        "can_member_interact": None,
                        "can_prescribe_to_member": None,
                        "vertical_objects": None,
                        "agreements": {"subscription": None},
                        "country": {
                            "name": None,
                            "ext_info_link": None,
                            "summary": None,
                            "abbr": None,
                        },
                        "is_cx": None,
                    },
                },
                "subscription_plans": None,
                "email": None,
                "organization": {
                    "rx_enabled": None,
                    "id": None,
                    "name": None,
                    "display_name": None,
                    "education_only": None,
                    "bms_enabled": None,
                    "vertical_group_version": None,
                },
                "created_at": None,
                "image_url": None,
                "test_group": None,
                "name": None,
                "esp_id": None,
                "first_name": None,
                "last_name": None,
                "image_id": None,
                "encoded_id": None,
                "middle_name": None,
                "username": None,
                "country": {
                    "name": None,
                    "ext_info_link": None,
                    "summary": None,
                    "abbr": None,
                },
                "avatar_url": None,
            },
            "cancelled_at": None,
            "structured_internal_note": {
                "submitted_at": None,
                "appointment_id": None,
                "id": None,
                "recorded_answers": None,
                "questionnaire_id": None,
                "modified_at": None,
                "source_user_id": None,
                "draft": None,
            },
            "member_rating": {
                "description_text": None,
                "question_sets": None,
                "id": None,
                "sort_order": None,
                "title_text": None,
                "oid": None,
                "soft_deleted_at": None,
                "trigger_answer_ids": None,
            },
            "scheduled_end": None,
            "privacy": None,
        }
        v1_schema = AppointmentSchema()
        v3_schema = AppointmentSchemaV3()
        with patch("storage.connection.db.session.query") as mock_db_query:
            mock_db_query.return_value.filter.return_value.one.return_value = user
            v3_schema_dump = v3_schema.dump(edge_case)
            del v3_schema_dump["product"]["practitioner"]["profiles"]["practitioner"][
                "can_request_availability"
            ]
            assert (
                v1_schema.dump(edge_case).data == v3_schema_dump
            ), "Backwards compatibility broken between versions"

    def test_message_billing_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from messaging.schemas.messaging import MessageBillingSchema
        from messaging.schemas.messaging_v3 import MessageBillingSchemaV3

        data = {
            "card_last4": "Sample text",
            "maven_credit_used": "Sample text",
            "stripe_charge_id": "Sample text",
            "card_brand": "Sample text",
            "available_messages": 2,
            "charged_at": datetime.datetime(
                2024, 9, 24, 20, 36, 50, 38807, tzinfo=datetime.timezone.utc
            ),
        }
        v1_schema = MessageBillingSchema()
        v3_schema = MessageBillingSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "card_last4": None,
            "maven_credit_used": None,
            "stripe_charge_id": None,
            "card_brand": None,
            "available_messages": None,
            "charged_at": None,
        }
        v1_schema = MessageBillingSchema()
        v3_schema = MessageBillingSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_message_billing_get_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from messaging.schemas.messaging import MessageBillingGETSchema
        from messaging.schemas.messaging_v3 import MessageBillingGETSchemaV3

        data = {
            "available_messages": 2,
            "modified_at": datetime.datetime(
                2024, 9, 24, 20, 37, 14, 423070, tzinfo=datetime.timezone.utc
            ),
        }
        v1_schema = MessageBillingGETSchema()
        v3_schema = MessageBillingGETSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"available_messages": None, "modified_at": None}
        v1_schema = MessageBillingGETSchema()
        v3_schema = MessageBillingGETSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_v2_practitioner_notes_args_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.profiles import (
            V2PractitionerNotesArgsSchema,
            V2PractitionerNotesArgsSchemaV3,
        )

        data = {
            "scheduled_end": datetime.datetime(
                2024, 10, 19, 20, 10, 43, 701457, tzinfo=datetime.timezone.utc
            ),
            "completed_appointments": False,
            "my_encounters": True,
            "verticals": None,
            "limit": 2,
            "scheduled_start": datetime.datetime(
                2024, 10, 19, 20, 10, 43, 701481, tzinfo=datetime.timezone.utc
            ),
            "all_appointments": False,
            "offset": 2,
            "order_direction": None,
        }
        v1_schema = V2PractitionerNotesArgsSchema()
        v3_schema = V2PractitionerNotesArgsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "scheduled_end": None,
            "completed_appointments": None,
            "my_encounters": None,
            "verticals": None,
            "limit": None,
            "scheduled_start": None,
            "all_appointments": None,
            "offset": None,
            "order_direction": None,
        }
        v1_schema = V2PractitionerNotesArgsSchema()
        v3_schema = V2PractitionerNotesArgsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_practitioner_notes_args_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.profiles import (
            PractitionerNotesArgsSchema,
            PractitionerNotesArgsSchemaV3,
        )

        data = {
            "limit": 2,
            "all_appointments": True,
            "completed_appointments": False,
            "order_direction": None,
            "scheduled_end": datetime.datetime(
                2024, 10, 19, 20, 13, 22, 15163, tzinfo=datetime.timezone.utc
            ),
            "my_appointments": False,
            "offset": 2,
            "verticals": None,
            "scheduled_start": datetime.datetime(
                2024, 10, 19, 20, 13, 22, 15180, tzinfo=datetime.timezone.utc
            ),
        }
        v1_schema = PractitionerNotesArgsSchema()
        v3_schema = PractitionerNotesArgsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "limit": None,
            "all_appointments": None,
            "completed_appointments": None,
            "order_direction": None,
            "scheduled_end": None,
            "my_appointments": None,
            "offset": None,
            "verticals": None,
            "scheduled_start": None,
        }
        v1_schema = PractitionerNotesArgsSchema()
        v3_schema = PractitionerNotesArgsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_practitioner_notes_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.profiles import PractitionerNotesSchema, PractitionerNotesSchemaV3

        data = {
            "pagination": {
                "order_direction": None,
                "total": None,
                "offset": None,
                "limit": None,
            },
            "meta": None,
            "data": [
                {
                    "cancelled_by": None,
                    "id": None,
                    "scheduled_start": datetime.datetime(
                        2024, 10, 19, 20, 19, 55, 732841, tzinfo=datetime.timezone.utc
                    ),
                    "post_session": {
                        "notes": "Sample text",
                        "created_at": datetime.datetime(
                            2024,
                            10,
                            19,
                            20,
                            19,
                            55,
                            732853,
                            tzinfo=datetime.timezone.utc,
                        ),
                        "draft": True,
                        "modified_at": datetime.datetime(
                            2024,
                            10,
                            19,
                            20,
                            19,
                            55,
                            732859,
                            tzinfo=datetime.timezone.utc,
                        ),
                    },
                    "need": {
                        "name": "Sample text",
                        "id": 1,
                        "description": "Sample text",
                    },
                    "product": {
                        "practitioner": {
                            "first_name": "Sample text",
                            "id": 2,
                            "image_url": None,
                            "name": None,
                            "profiles": {
                                "practitioner": {
                                    "country_code": "Sample text",
                                    "years_experience": 1,
                                    "certifications": None,
                                    "education": "Sample text",
                                    "certified_states": None,
                                    "can_member_interact": None,
                                    "phone_number": "Sample text",
                                    "faq_password": None,
                                    "cancellation_policy": None,
                                    "work_experience": "Sample text",
                                    "country": {
                                        "name": None,
                                        "ext_info_link": None,
                                        "abbr": None,
                                        "summary": None,
                                    },
                                    "rating": 32.37303083468616,
                                    "categories": None,
                                    "tel_number": "Sample text",
                                    "response_time": 1,
                                    "subdivision_code": "Sample text",
                                    "messaging_enabled": True,
                                    "tel_region": "Sample text",
                                    "vertical_objects": [
                                        {
                                            "id": 1,
                                            "name": "Sample text",
                                            "can_prescribe": False,
                                            "description": "Sample text",
                                            "filter_by_state": False,
                                            "pluralized_display_name": "Sample text",
                                            "long_description": "Sample text",
                                        }
                                    ],
                                    "address": {
                                        "street_address": "Sample text",
                                        "zip_code": "Sample text",
                                        "state": "Sample text",
                                        "city": "Sample text",
                                        "country": "Sample text",
                                    },
                                    "certified_subdivision_codes": None,
                                    "is_cx": None,
                                    "care_team_type": None,
                                    "user_id": 2,
                                    "can_prescribe": None,
                                    "state": None,
                                    "specialties": None,
                                    "reference_quote": "Sample text",
                                    "agreements": {"subscription": False},
                                    "awards": "Sample text",
                                    "next_availability": datetime.datetime(
                                        2024,
                                        10,
                                        19,
                                        20,
                                        19,
                                        55,
                                        732926,
                                        tzinfo=datetime.timezone.utc,
                                    ),
                                    "can_prescribe_to_member": None,
                                    "languages": None,
                                    "verticals": None,
                                }
                            },
                            "last_name": "Sample text",
                        }
                    },
                    "structured_internal_note": {
                        "questionnaire_id": "Sample text",
                        "id": "Sample text",
                        "source_user_id": 1,
                        "submitted_at": datetime.datetime(
                            2024,
                            10,
                            19,
                            20,
                            19,
                            55,
                            732938,
                            tzinfo=datetime.timezone.utc,
                        ),
                        "appointment_id": None,
                        "modified_at": datetime.datetime(
                            2024,
                            10,
                            19,
                            20,
                            19,
                            55,
                            732943,
                            tzinfo=datetime.timezone.utc,
                        ),
                        "recorded_answers": None,
                        "draft": True,
                    },
                    "pre_session": {
                        "notes": "Sample text",
                        "created_at": datetime.datetime(
                            2024,
                            10,
                            19,
                            20,
                            19,
                            55,
                            732949,
                            tzinfo=datetime.timezone.utc,
                        ),
                        "draft": False,
                        "modified_at": datetime.datetime(
                            2024,
                            10,
                            19,
                            20,
                            19,
                            55,
                            732954,
                            tzinfo=datetime.timezone.utc,
                        ),
                    },
                    "state": "Sample text",
                    "scheduled_end": datetime.datetime(
                        2024, 10, 19, 20, 19, 55, 732957, tzinfo=datetime.timezone.utc
                    ),
                    "provider_addenda": {
                        "title_text": "Sample text",
                        "soft_deleted_at": datetime.datetime(
                            2024,
                            10,
                            19,
                            20,
                            19,
                            55,
                            732961,
                            tzinfo=datetime.timezone.utc,
                        ),
                        "id": "Sample text",
                        "sort_order": 1,
                        "oid": "Sample text",
                        "trigger_answer_ids": None,
                        "question_sets": None,
                        "description_text": "Sample text",
                    },
                }
            ],
        }
        v1_schema = PractitionerNotesSchema()
        v3_schema = PractitionerNotesSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "pagination": {
                "order_direction": None,
                "total": None,
                "offset": None,
                "limit": None,
            },
            "meta": None,
            "data": None,
        }
        v1_schema = PractitionerNotesSchema()
        v3_schema = PractitionerNotesSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_payment_methods_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.payments import PaymentMethodsSchema, PaymentMethodsSchemaV3

        data = {
            "data": [
                {"id": "Sample text", "brand": "Sample text", "last4": "Sample text"}
            ],
            "meta": None,
            "pagination": {
                "offset": 1,
                "total": 3,
                "limit": 4,
                "order_direction": "desc",
            },
        }
        v1_schema = PaymentMethodsSchema()
        v3_schema = PaymentMethodsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "data": None,
            "meta": None,
            "pagination": {
                "offset": None,
                "total": None,
                "limit": None,
                "order_direction": "desc",
            },
        }
        v1_schema = PaymentMethodsSchema()
        v3_schema = PaymentMethodsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_bank_account_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.payments import BankAccountSchema, BankAccountSchemaV3

        data = {
            "country": "Sample text",
            "bank_name": "Sample text",
            "last4": "Sample text",
        }
        v1_schema = BankAccountSchema()
        v3_schema = BankAccountSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"country": None, "bank_name": None, "last4": None}
        v1_schema = BankAccountSchema()
        v3_schema = BankAccountSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_debit_card_p_o_s_t_request_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet_debit_card import (
            ReimbursementWalletDebitCardPOSTRequestSchema,
            ReimbursementWalletDebitCardPOSTRequestSchemaV3,
        )

        data = {"sms_opt_in": False}
        v1_schema = ReimbursementWalletDebitCardPOSTRequestSchema()
        v3_schema = ReimbursementWalletDebitCardPOSTRequestSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"sms_opt_in": None}
        v1_schema = ReimbursementWalletDebitCardPOSTRequestSchema()
        v3_schema = ReimbursementWalletDebitCardPOSTRequestSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_debit_card_response_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet_debit_card import (
            ReimbursementWalletDebitCardResponseSchema,
            ReimbursementWalletDebitCardResponseSchemaV3,
        )

        data = {
            "data": {
                "id": 123,
                "created_date": datetime.date(year=2024, month=1, day=1),
                "shipped_date": datetime.date(year=2024, month=1, day=1),
                "card_status": "lost",
                "issued_date": datetime.date(year=2024, month=1, day=1),
                "card_proxy_number": "1234",
                "reimbursement_wallet_id": 123,
                "shipping_tracking_number": "1234",
                "card_status_reason_text": "1234",
                "card_last_4_digits": "1234",
                "card_status_reason": "123798",
            }
        }
        v1_schema = ReimbursementWalletDebitCardResponseSchema()
        v3_schema = ReimbursementWalletDebitCardResponseSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "data": {
                "id": None,
                "created_date": None,
                "shipped_date": None,
                "card_status": None,
                "issued_date": None,
                "card_proxy_number": None,
                "reimbursement_wallet_id": None,
                "shipping_tracking_number": None,
                "card_status_reason_text": None,
                "card_last_4_digits": None,
                "card_status_reason": None,
            }
        }
        v1_schema = ReimbursementWalletDebitCardResponseSchema()
        v3_schema = ReimbursementWalletDebitCardResponseSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_request_source_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement import (
            ReimbursementRequestSourceSchema,
            ReimbursementRequestSourceSchemaV3,
        )

        data = {
            "source_id": "Sample text",
            "inline_url": "test",
            "content_type": "test",
            "created_at": datetime.datetime(
                2024, 10, 19, 21, 32, 49, 512878, tzinfo=datetime.timezone.utc
            ),
            "file_name": "test",
            "source_url": "test",
            "type": "Sample text",
        }
        v1_schema = ReimbursementRequestSourceSchema()
        v3_schema = ReimbursementRequestSourceSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "source_id": None,
            "inline_url": None,
            "content_type": None,
            "created_at": None,
            "file_name": None,
            "source_url": None,
            "type": None,
        }
        v1_schema = ReimbursementRequestSourceSchema()
        v3_schema = ReimbursementRequestSourceSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_pharmacy_search_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.prescription import PharmacySearchSchema, PharmacySearchSchemaV3

        data = {"pharmacy_name": "Sample text", "zip_code": "Sample text"}
        v1_schema = PharmacySearchSchema()
        v3_schema = PharmacySearchSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"pharmacy_name": None, "zip_code": None}
        v1_schema = PharmacySearchSchema()
        v3_schema = PharmacySearchSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_member_search_results_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from members.schemas.search import (
            MemberSearchResultsSchema,
            MemberSearchResultsSchemaV3,
        )

        data = {
            "meta": None,
            "data": [
                {
                    "id": 2,
                    "care_coordinators": [
                        {"first_name": "Sample text", "last_name": "Sample text"}
                    ],
                    "email": "Sample text",
                    "is_restricted": False,
                    "organization": {"name": "Sample text", "US_restricted": None},
                    "first_name": "Sample text",
                    "last_name": "Sample text",
                }
            ],
            "pagination": {
                "offset": None,
                "limit": None,
                "order_direction": None,
                "total": None,
            },
        }
        v1_schema = MemberSearchResultsSchema()
        v3_schema = MemberSearchResultsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "meta": None,
            "data": None,
            "pagination": {
                "offset": None,
                "limit": None,
                "order_direction": None,
                "total": None,
            },
        }
        v1_schema = MemberSearchResultsSchema()
        v3_schema = MemberSearchResultsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_appointment_notes_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from appointments.notes.schemas.notes import (
            AppointmentNotesSchema,
            AppointmentNotesSchemaV3,
        )

        data = {
            "structured_internal_note": {
                "appointment_id": None,
                "submitted_at": None,
                "id": None,
                "recorded_answers": None,
                "source_user_id": None,
                "questionnaire_id": None,
                "draft": None,
                "modified_at": None,
            },
            "provider_addenda": {
                "question_sets": None,
                "id": None,
                "title_text": None,
                "trigger_answer_ids": None,
                "soft_deleted_at": None,
                "sort_order": None,
                "oid": None,
                "description_text": None,
            },
            "post_session": {
                "created_at": None,
                "modified_at": None,
                "draft": None,
                "notes": None,
            },
        }
        v1_schema = AppointmentNotesSchema()
        v3_schema = AppointmentNotesSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "structured_internal_note": {
                "appointment_id": None,
                "submitted_at": None,
                "id": None,
                "recorded_answers": None,
                "source_user_id": None,
                "questionnaire_id": None,
                "draft": None,
                "modified_at": None,
            },
            "provider_addenda": {
                "question_sets": None,
                "id": None,
                "title_text": None,
                "trigger_answer_ids": None,
                "soft_deleted_at": None,
                "sort_order": None,
                "oid": None,
                "description_text": None,
            },
            "post_session": {
                "created_at": None,
                "modified_at": None,
                "draft": None,
                "notes": None,
            },
        }
        v1_schema = AppointmentNotesSchema()
        v3_schema = AppointmentNotesSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_refill_transmission_count_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.prescription import (
            RefillTransmissionCountSchema,
            RefillTransmissionCountSchemaV3,
        )

        data = {"transaction_count": 1, "url": "Sample text", "refill_count": 1}
        v1_schema = RefillTransmissionCountSchema()
        v3_schema = RefillTransmissionCountSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"transaction_count": None, "url": None, "refill_count": None}
        v1_schema = RefillTransmissionCountSchema()
        v3_schema = RefillTransmissionCountSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_money_amount_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.currency import MoneyAmountSchema
        from wallet.schemas.currency_v3 import MoneyAmountSchemaV3

        data = {
            "amount": 1,
            "formatted_amount_truncated": "Sample text",
            "formatted_amount": "Sample text",
            "currency_code": "Sample text",
            "raw_amount": "Sample text",
        }
        v1_schema = MoneyAmountSchema()
        v3_schema = MoneyAmountSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "amount": None,
            "formatted_amount_truncated": None,
            "formatted_amount": None,
            "currency_code": None,
            "raw_amount": None,
        }
        v1_schema = MoneyAmountSchema()
        v3_schema = MoneyAmountSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_category_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_category import ReimbursementCategorySchema
        from wallet.schemas.reimbursement_category_v3 import (
            ReimbursementCategorySchemaV3,
        )

        data = {
            "direct_payment_eligible": True,
            "is_fertility_category": True,
            "benefit_type": None,
            "credit_maximum": 2,
            "title": "Sample text",
            "is_unlimited": None,
            "reimbursement_request_category_maximum_amount": {
                "formatted_amount": None,
                "amount": None,
                "formatted_amount_truncated": None,
                "raw_amount": None,
                "currency_code": None,
            },
            "subtitle": "Sample text",
            "reimbursement_request_category_maximum": 2,
            "label": "Sample text",
            "credits_remaining": 2,
            "reimbursement_request_category_id": "Sample text",
        }
        v1_schema = ReimbursementCategorySchema()
        v3_schema = ReimbursementCategorySchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "direct_payment_eligible": None,
            "is_fertility_category": None,
            "benefit_type": None,
            "credit_maximum": None,
            "title": None,
            "is_unlimited": None,
            "reimbursement_request_category_maximum_amount": {
                "formatted_amount": None,
                "amount": None,
                "formatted_amount_truncated": None,
                "raw_amount": None,
                "currency_code": None,
            },
            "subtitle": None,
            "reimbursement_request_category_maximum": None,
            "label": None,
            "credits_remaining": None,
            "reimbursement_request_category_id": None,
        }
        v1_schema = ReimbursementCategorySchema()
        v3_schema = ReimbursementCategorySchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_request_category_container_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_category import (
            ReimbursementRequestCategoryContainerSchema,
        )
        from wallet.schemas.reimbursement_category_v3 import (
            ReimbursementRequestCategoryContainerSchemaV3,
        )

        data = {
            "spent": 2,
            "spent_amount": {
                "currency_code": None,
                "amount": None,
                "formatted_amount_truncated": None,
                "raw_amount": None,
                "formatted_amount": None,
            },
            "remaining_amount": {
                "currency_code": None,
                "amount": None,
                "formatted_amount_truncated": None,
                "raw_amount": None,
                "formatted_amount": None,
            },
            "plan_end": datetime.datetime(
                2024, 12, 2, 3, 8, 48, 68244, tzinfo=datetime.timezone.utc
            ),
            "plan_type": "Sample text",
            "plan_start": datetime.datetime(
                2024, 12, 2, 3, 8, 48, 68254, tzinfo=datetime.timezone.utc
            ),
            "category": {
                "label": None,
                "benefit_type": None,
                "id": None,
                "is_unlimited": None,
                "reimbursement_request_category_maximum_amount": {
                    "currency_code": None,
                    "amount": None,
                    "formatted_amount_truncated": None,
                    "raw_amount": None,
                    "formatted_amount": None,
                },
                "direct_payment_eligible": None,
                "reimbursement_request_category_maximum": None,
                "subtitle": None,
                "credit_maximum": None,
                "credits_remaining": None,
                "is_fertility_category": None,
                "title": None,
            },
        }
        v1_schema = ReimbursementRequestCategoryContainerSchema()
        v3_schema = ReimbursementRequestCategoryContainerSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "spent": None,
            "spent_amount": {
                "currency_code": None,
                "amount": None,
                "formatted_amount_truncated": None,
                "raw_amount": None,
                "formatted_amount": None,
            },
            "remaining_amount": {
                "currency_code": None,
                "amount": None,
                "formatted_amount_truncated": None,
                "raw_amount": None,
                "formatted_amount": None,
            },
            "plan_end": None,
            "plan_type": None,
            "plan_start": None,
            "category": {
                "label": None,
                "benefit_type": None,
                "id": None,
                "reimbursement_request_category_maximum_amount": {
                    "currency_code": None,
                    "amount": None,
                    "formatted_amount_truncated": None,
                    "raw_amount": None,
                    "formatted_amount": None,
                },
                "direct_payment_eligible": None,
                "reimbursement_request_category_maximum": None,
                "subtitle": None,
                "credit_maximum": None,
                "credits_remaining": None,
                "is_fertility_category": None,
                "title": None,
            },
        }
        v1_schema = ReimbursementRequestCategoryContainerSchema()
        v3_schema = ReimbursementRequestCategoryContainerSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_expense_types_form_options_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_category import ExpenseTypesFormOptionsSchema
        from wallet.schemas.reimbursement_category_v3 import (
            ExpenseTypesFormOptionsSchemaV3,
        )

        data = {"name": "Sample text", "label": "Sample text"}
        v1_schema = ExpenseTypesFormOptionsSchema()
        v3_schema = ExpenseTypesFormOptionsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"name": None, "label": None}
        v1_schema = ExpenseTypesFormOptionsSchema()
        v3_schema = ExpenseTypesFormOptionsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_request_expense_types_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_category import (
            ReimbursementRequestExpenseTypesSchema,
        )
        from wallet.schemas.reimbursement_category_v3 import (
            ReimbursementRequestExpenseTypesSchemaV3,
        )

        data = {
            "is_fertility_expense": False,
            "currency_code": "Sample text",
            "label": "Sample text",
            "form_options": [{"name": "Sample text", "label": "Sample text"}],
        }
        v1_schema = ReimbursementRequestExpenseTypesSchema()
        v3_schema = ReimbursementRequestExpenseTypesSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "is_fertility_expense": None,
            "currency_code": None,
            "label": None,
            "form_options": None,
        }
        v1_schema = ReimbursementRequestExpenseTypesSchema()
        v3_schema = ReimbursementRequestExpenseTypesSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_request_cost_share_details_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement import (
            ReimbursementRequestCostShareDetailsSchema,
        )
        from wallet.schemas.reimbursement_v3 import (
            ReimbursementRequestCostShareDetailsSchemaV3,
        )

        data = {
            "original_claim_amount": "Sample text",
            "reimbursement_expected_message": "Sample text",
            "reimbursement_amount": "Sample text",
        }
        v1_schema = ReimbursementRequestCostShareDetailsSchema()
        v3_schema = ReimbursementRequestCostShareDetailsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "original_claim_amount": None,
            "reimbursement_expected_message": None,
            "reimbursement_amount": None,
        }
        v1_schema = ReimbursementRequestCostShareDetailsSchema()
        v3_schema = ReimbursementRequestCostShareDetailsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_request_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement import ReimbursementRequestSchema
        from wallet.schemas.reimbursement_v3 import ReimbursementRequestSchemaV3

        data = {
            "source": {
                "source_url": None,
                "content_type": None,
                "created_at": None,
                "file_name": None,
                "source_id": None,
                "type": None,
                "inline_url": None,
            },
            "state_description": "Sample text",
            "cost_share_details": {
                "original_claim_amount": None,
                "reimbursement_expected_message": None,
                "reimbursement_amount": None,
            },
            "category": {
                "benefit_type": None,
                "label": None,
                "title": None,
                "id": None,
                "subtitle": None,
            },
            "sources": [
                {
                    "source_url": None,
                    "content_type": None,
                    "created_at": datetime.datetime(
                        2024, 12, 2, 3, 15, 51, 973891, tzinfo=datetime.timezone.utc
                    ),
                    "file_name": None,
                    "source_id": "Sample text",
                    "type": "Sample text",
                    "inline_url": None,
                }
            ],
            "service_start_date": datetime.datetime(
                2024, 12, 2, 3, 15, 51, 973898, tzinfo=datetime.timezone.utc
            ),
            "description": "Sample text",
            "label": "Sample text",
            "benefit_amount": {
                "amount": None,
                "formatted_amount_truncated": None,
                "formatted_amount": None,
                "currency_code": None,
                "raw_amount": None,
            },
            "employee_name": "Sample text",
            "reimbursement_type": None,
            "created_at": datetime.datetime(
                2024, 12, 2, 3, 15, 51, 973911, tzinfo=datetime.timezone.utc
            ),
            "id": "Sample text",
            "state": None,
            "person_receiving_service": "Sample text",
            "service_provider": "Sample text",
            "amount": 1,
            "taxation_status": "Sample text",
            "service_end_date": datetime.datetime(
                2024, 12, 2, 3, 15, 51, 973918, tzinfo=datetime.timezone.utc
            ),
        }
        v1_schema = ReimbursementRequestSchema()
        v3_schema = ReimbursementRequestSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "source": {
                "source_url": None,
                "content_type": None,
                "created_at": None,
                "file_name": None,
                "source_id": None,
                "type": None,
                "inline_url": None,
            },
            "state_description": None,
            "cost_share_details": {
                "original_claim_amount": None,
                "reimbursement_expected_message": None,
                "reimbursement_amount": None,
            },
            "category": {
                "benefit_type": None,
                "label": None,
                "title": None,
                "id": None,
                "subtitle": None,
            },
            "sources": None,
            "service_start_date": None,
            "description": None,
            "label": None,
            "benefit_amount": {
                "amount": None,
                "formatted_amount_truncated": None,
                "formatted_amount": None,
                "currency_code": None,
                "raw_amount": None,
            },
            "employee_name": None,
            "reimbursement_type": None,
            "created_at": None,
            "id": None,
            "state": None,
            "person_receiving_service": None,
            "service_provider": None,
            "amount": None,
            "taxation_status": None,
            "service_end_date": None,
        }
        v1_schema = ReimbursementRequestSchema()
        v3_schema = ReimbursementRequestSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_request_summary_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement import ReimbursementRequestSummarySchema
        from wallet.schemas.reimbursement_v3 import ReimbursementRequestSummarySchemaV3

        data = {
            "expense_types": [
                {
                    "is_fertility_expense": True,
                    "label": "Sample text",
                    "currency_code": "Sample text",
                    "form_options": [{"label": "Sample text", "name": "Sample text"}],
                }
            ],
            "category_breakdown": [
                {
                    "spent_amount": {
                        "amount": 1,
                        "formatted_amount": "Sample text",
                        "formatted_amount_truncated": "Sample text",
                        "raw_amount": "Sample text",
                        "currency_code": "Sample text",
                    },
                    "category": {
                        "id": "Sample text",
                        "label": "Sample text",
                        "benefit_type": None,
                        "subtitle": "Sample text",
                        "is_unlimited": None,
                        "reimbursement_request_category_maximum_amount": {
                            "amount": 1,
                            "formatted_amount": "Sample text",
                            "formatted_amount_truncated": "Sample text",
                            "raw_amount": "Sample text",
                            "currency_code": "Sample text",
                        },
                        "title": "Sample text",
                        "credit_maximum": 1,
                        "direct_payment_eligible": True,
                        "is_fertility_category": True,
                        "reimbursement_request_category_maximum": 2,
                        "credits_remaining": 1,
                    },
                    "plan_start": datetime.datetime(
                        2024, 12, 2, 3, 20, 0, 793532, tzinfo=datetime.timezone.utc
                    ),
                    "remaining_amount": {
                        "amount": 1,
                        "formatted_amount": "Sample text",
                        "formatted_amount_truncated": "Sample text",
                        "raw_amount": "Sample text",
                        "currency_code": "Sample text",
                    },
                    "plan_type": "Sample text",
                    "plan_end": datetime.datetime(
                        2024, 12, 2, 3, 20, 0, 793545, tzinfo=datetime.timezone.utc
                    ),
                    "spent": 1,
                }
            ],
            "wallet_shareable": False,
            "reimbursement_request_maximum": 1,
            "reimbursement_spent": 1,
            "currency_code": "Sample text",
        }
        v1_schema = ReimbursementRequestSummarySchema()
        v3_schema = ReimbursementRequestSummarySchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "expense_types": None,
            "category_breakdown": None,
            "wallet_shareable": None,
            "reimbursement_request_maximum": None,
            "reimbursement_spent": None,
            "currency_code": None,
        }
        v1_schema = ReimbursementRequestSummarySchema()
        v3_schema = ReimbursementRequestSummarySchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_request_data_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement import ReimbursementRequestDataSchema
        from wallet.schemas.reimbursement_v3 import ReimbursementRequestDataSchemaV3

        data = {
            "reimbursement_requests": [
                {
                    "service_end_date": datetime.datetime(
                        2024, 12, 2, 3, 21, 26, 241475, tzinfo=datetime.timezone.utc
                    ),
                    "id": "Sample text",
                    "person_receiving_service": "Sample text",
                    "benefit_amount": {
                        "formatted_amount": "Sample text",
                        "amount": 2,
                        "currency_code": "Sample text",
                        "raw_amount": "Sample text",
                        "formatted_amount_truncated": "Sample text",
                    },
                    "state": None,
                    "employee_name": "Sample text",
                    "amount": 1,
                    "created_at": datetime.datetime(
                        2024, 12, 2, 3, 21, 26, 241498, tzinfo=datetime.timezone.utc
                    ),
                    "category": {
                        "label": "Sample text",
                        "id": "Sample text",
                        "benefit_type": None,
                        "subtitle": "Sample text",
                        "title": "Sample text",
                    },
                    "source": {
                        "type": "Sample text",
                        "content_type": None,
                        "file_name": None,
                        "source_url": None,
                        "source_id": "Sample text",
                        "created_at": datetime.datetime(
                            2024, 12, 2, 3, 21, 26, 241510, tzinfo=datetime.timezone.utc
                        ),
                        "inline_url": None,
                    },
                    "reimbursement_type": None,
                    "sources": [
                        {
                            "type": "Sample text",
                            "content_type": None,
                            "file_name": None,
                            "source_url": None,
                            "source_id": "Sample text",
                            "created_at": datetime.datetime(
                                2024,
                                12,
                                2,
                                3,
                                21,
                                26,
                                241521,
                                tzinfo=datetime.timezone.utc,
                            ),
                            "inline_url": None,
                        }
                    ],
                    "taxation_status": "Sample text",
                    "state_description": "Sample text",
                    "service_provider": "Sample text",
                    "label": "Sample text",
                    "service_start_date": datetime.datetime(
                        2024, 12, 2, 3, 21, 26, 241527, tzinfo=datetime.timezone.utc
                    ),
                    "cost_share_details": {
                        "reimbursement_amount": "Sample text",
                        "reimbursement_expected_message": "Sample text",
                        "original_claim_amount": "Sample text",
                    },
                    "description": "Sample text",
                }
            ],
            "summary": {
                "reimbursement_request_maximum": None,
                "category_breakdown": None,
                "expense_types": None,
                "wallet_shareable": None,
                "reimbursement_spent": None,
                "currency_code": None,
            },
        }
        v1_schema = ReimbursementRequestDataSchema()
        v3_schema = ReimbursementRequestDataSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "reimbursement_requests": None,
            "summary": {
                "reimbursement_request_maximum": None,
                "category_breakdown": None,
                "expense_types": None,
                "wallet_shareable": None,
                "reimbursement_spent": None,
                "currency_code": None,
            },
        }
        v1_schema = ReimbursementRequestDataSchema()
        v3_schema = ReimbursementRequestDataSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_request_meta_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement import ReimbursementRequestMetaSchema
        from wallet.schemas.reimbursement_v3 import ReimbursementRequestMetaSchemaV3

        data = {"category": "Sample text", "reimbursement_wallet_id": "Sample text"}
        v1_schema = ReimbursementRequestMetaSchema()
        v3_schema = ReimbursementRequestMetaSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"category": None, "reimbursement_wallet_id": None}
        v1_schema = ReimbursementRequestMetaSchema()
        v3_schema = ReimbursementRequestMetaSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_request_response_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement import ReimbursementRequestResponseSchema
        from wallet.schemas.reimbursement_v3 import ReimbursementRequestResponseSchemaV3

        data = {
            "meta": {"reimbursement_wallet_id": None, "category": None},
            "data": {
                "summary": {
                    "expense_types": None,
                    "category_breakdown": None,
                    "reimbursement_request_maximum": None,
                    "wallet_shareable": None,
                    "reimbursement_spent": None,
                    "currency_code": None,
                },
                "reimbursement_requests": None,
            },
        }
        v1_schema = ReimbursementRequestResponseSchema()
        v3_schema = ReimbursementRequestResponseSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "meta": {"reimbursement_wallet_id": None, "category": None},
            "data": {
                "summary": {
                    "expense_types": None,
                    "category_breakdown": None,
                    "reimbursement_request_maximum": None,
                    "wallet_shareable": None,
                    "reimbursement_spent": None,
                    "currency_code": None,
                },
                "reimbursement_requests": None,
            },
        }
        v1_schema = ReimbursementRequestResponseSchema()
        v3_schema = ReimbursementRequestResponseSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_request_with_category_response_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement import (
            ReimbursementRequestWithCategoryResponseSchema,
        )
        from wallet.schemas.reimbursement_v3 import (
            ReimbursementRequestWithCategoryResponseSchemaV3,
        )

        data = {
            "meta": {"category": None, "reimbursement_wallet_id": None},
            "data": {
                "reimbursement_requests": None,
                "summary": {
                    "reimbursement_request_maximum": None,
                    "expense_types": None,
                    "category_breakdown": None,
                    "currency_code": None,
                    "wallet_shareable": None,
                    "reimbursement_spent": None,
                },
            },
        }
        v1_schema = ReimbursementRequestWithCategoryResponseSchema()
        v3_schema = ReimbursementRequestWithCategoryResponseSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "meta": {"category": None, "reimbursement_wallet_id": None},
            "data": {
                "reimbursement_requests": None,
                "summary": {
                    "reimbursement_request_maximum": None,
                    "expense_types": None,
                    "category_breakdown": None,
                    "currency_code": None,
                    "wallet_shareable": None,
                    "reimbursement_spent": None,
                },
            },
        }
        v1_schema = ReimbursementRequestWithCategoryResponseSchema()
        v3_schema = ReimbursementRequestWithCategoryResponseSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_employee_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import (
            ReimbursementWalletEmployeeSchema,
        )
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementWalletEmployeeSchemaV3,
        )

        data = {"name": None, "last_name": "Sample text", "first_name": "Sample text"}
        v1_schema = ReimbursementWalletEmployeeSchema()
        v3_schema = ReimbursementWalletEmployeeSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"name": None, "last_name": None, "first_name": None}
        v1_schema = ReimbursementWalletEmployeeSchema()
        v3_schema = ReimbursementWalletEmployeeSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_member_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import ReimbursementWalletMemberSchema
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementWalletMemberSchemaV3,
        )

        data = {
            "first_name": "Sample text",
            "last_name": "Sample text",
            "id": 2,
            "name": None,
        }
        v1_schema = ReimbursementWalletMemberSchema()
        v3_schema = ReimbursementWalletMemberSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"first_name": None, "last_name": None, "id": None, "name": None}
        v1_schema = ReimbursementWalletMemberSchema()
        v3_schema = ReimbursementWalletMemberSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_payment_block_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import (
            ReimbursementWalletPaymentBlockSchema,
        )
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementWalletPaymentBlockSchemaV3,
        )

        data = {"show_benefit_amount": True, "variant": "Sample text", "num_errors": 1}
        v1_schema = ReimbursementWalletPaymentBlockSchema()
        v3_schema = ReimbursementWalletPaymentBlockSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"show_benefit_amount": None, "variant": None, "num_errors": None}
        v1_schema = ReimbursementWalletPaymentBlockSchema()
        v3_schema = ReimbursementWalletPaymentBlockSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_estimate_summary_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import (
            ReimbursementWalletEstimateSummarySchema,
        )
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementWalletEstimateSummarySchemaV3,
        )

        data = {
            "estimate_text": "Sample text",
            "estimate_bill_uuid": "Sample text",
            "payment_text": "Sample text",
            "total_member_estimate": "Sample text",
            "total_estimates": 2,
        }
        v1_schema = ReimbursementWalletEstimateSummarySchema()
        v3_schema = ReimbursementWalletEstimateSummarySchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "estimate_text": None,
            "estimate_bill_uuid": None,
            "payment_text": None,
            "total_member_estimate": None,
            "total_estimates": None,
        }
        v1_schema = ReimbursementWalletEstimateSummarySchema()
        v3_schema = ReimbursementWalletEstimateSummarySchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_treatment_block_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import (
            ReimbursementWalletTreatmentBlockSchema,
        )
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementWalletTreatmentBlockSchemaV3,
        )

        data = {
            "variant": "Sample text",
            "clinic_location": "Sample text",
            "clinic": "Sample text",
        }
        v1_schema = ReimbursementWalletTreatmentBlockSchema()
        v3_schema = ReimbursementWalletTreatmentBlockSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"variant": None, "clinic_location": None, "clinic": None}
        v1_schema = ReimbursementWalletTreatmentBlockSchema()
        v3_schema = ReimbursementWalletTreatmentBlockSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_upcoming_payment_summary_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import (
            ReimbursementWalletUpcomingPaymentSummarySchema,
        )
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementWalletUpcomingPaymentSummarySchemaV3,
        )

        data = {
            "total_member_amount": 2,
            "total_benefit_amount": 1,
            "benefit_remaining": 2,
            "procedure_title": "Sample text",
            "member_method": "Sample text",
            "member_method_formatted": None,
        }
        v1_schema = ReimbursementWalletUpcomingPaymentSummarySchema()
        v3_schema = ReimbursementWalletUpcomingPaymentSummarySchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "total_member_amount": None,
            "total_benefit_amount": None,
            "benefit_remaining": None,
            "procedure_title": None,
            "member_method": None,
            "member_method_formatted": None,
        }
        v1_schema = ReimbursementWalletUpcomingPaymentSummarySchema()
        v3_schema = ReimbursementWalletUpcomingPaymentSummarySchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_upcoming_payment_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import (
            ReimbursementWalletUpcomingPaymentSchema,
        )
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementWalletUpcomingPaymentSchemaV3,
        )

        data = {
            "procedure_title": "Sample text",
            "benefit_date": "Sample text",
            "benefit_remaining": 2,
            "error_type": "Sample text",
            "benefit_amount": 1,
            "member_amount": 1,
            "member_method": "Sample text",
            "member_date": "Sample text",
            "procedure_id": 2,
            "bill_uuid": "Sample text",
            "member_method_formatted": None,
        }
        v1_schema = ReimbursementWalletUpcomingPaymentSchema()
        v3_schema = ReimbursementWalletUpcomingPaymentSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "procedure_title": None,
            "benefit_date": None,
            "benefit_remaining": None,
            "error_type": None,
            "benefit_amount": None,
            "member_amount": None,
            "member_method": None,
            "member_date": None,
            "procedure_id": None,
            "bill_uuid": None,
            "member_method_formatted": None,
        }
        v1_schema = ReimbursementWalletUpcomingPaymentSchema()
        v3_schema = ReimbursementWalletUpcomingPaymentSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_upcoming_payments_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import (
            ReimbursementWalletUpcomingPaymentsSchema,
        )
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementWalletUpcomingPaymentsSchemaV3,
        )

        data = {
            "summary": {
                "member_method": None,
                "benefit_remaining": None,
                "total_benefit_amount": None,
                "procedure_title": None,
                "member_method_formatted": None,
                "total_member_amount": None,
            },
            "payments": [
                {
                    "benefit_date": "Sample text",
                    "member_method": "Sample text",
                    "benefit_remaining": 1,
                    "member_date": "Sample text",
                    "procedure_id": 1,
                    "procedure_title": "Sample text",
                    "member_method_formatted": None,
                    "bill_uuid": "Sample text",
                    "error_type": "Sample text",
                    "member_amount": 1,
                    "benefit_amount": 2,
                }
            ],
        }
        v1_schema = ReimbursementWalletUpcomingPaymentsSchema()
        v3_schema = ReimbursementWalletUpcomingPaymentsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "summary": {
                "member_method": None,
                "benefit_remaining": None,
                "total_benefit_amount": None,
                "procedure_title": None,
                "member_method_formatted": None,
                "total_member_amount": None,
            },
            "payments": None,
        }
        v1_schema = ReimbursementWalletUpcomingPaymentsSchema()
        v3_schema = ReimbursementWalletUpcomingPaymentsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_reimbursement_request_block_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import (
            ReimbursementWalletReimbursementRequestBlockSchema,
        )
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementWalletReimbursementRequestBlockSchemaV3,
        )

        data = {
            "reimbursement_text": "Sample text",
            "total": 1,
            "reimbursement_request_uuid": "Sample text",
            "has_cost_breakdown_available": True,
            "expected_reimbursement_amount": "Sample text",
            "original_claim_amount": "Sample text",
            "details_text": "Sample text",
            "original_claim_text": "Sample text",
            "title": "Sample text",
        }
        v1_schema = ReimbursementWalletReimbursementRequestBlockSchema()
        v3_schema = ReimbursementWalletReimbursementRequestBlockSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "reimbursement_text": None,
            "total": None,
            "reimbursement_request_uuid": None,
            "has_cost_breakdown_available": None,
            "expected_reimbursement_amount": None,
            "original_claim_amount": None,
            "details_text": None,
            "original_claim_text": None,
            "title": None,
        }
        v1_schema = ReimbursementWalletReimbursementRequestBlockSchema()
        v3_schema = ReimbursementWalletReimbursementRequestBlockSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_pharmacy_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import (
            ReimbursementWalletPharmacySchema,
        )
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementWalletPharmacySchemaV3,
        )

        data = {"name": "Sample text", "url": "Sample text"}
        v1_schema = ReimbursementWalletPharmacySchema()
        v3_schema = ReimbursementWalletPharmacySchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"name": None, "url": None}
        v1_schema = ReimbursementWalletPharmacySchema()
        v3_schema = ReimbursementWalletPharmacySchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_benefit_resource_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import BenefitResourceSchema
        from wallet.schemas.reimbursement_wallet_v3 import BenefitResourceSchemaV3

        data = {"title": "Sample text", "url": "Sample text"}
        v1_schema = BenefitResourceSchema()
        v3_schema = BenefitResourceSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"title": None, "url": None}
        v1_schema = BenefitResourceSchema()
        v3_schema = BenefitResourceSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_organization_settings_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import (
            ReimbursementOrganizationSettingsSchema,
        )
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementOrganizationSettingsSchemaV3,
        )

        data = {
            "benefit_faq_resource": {"url": None, "title": None},
            "survey_url": "Sample text",
            "allowed_reimbursement_categories": {
                "subtitle": None,
                "label": None,
                "reimbursement_request_category_maximum_amount": {
                    "currency_code": None,
                    "formatted_amount_truncated": None,
                    "amount": None,
                    "raw_amount": None,
                    "formatted_amount": None,
                },
                "benefit_type": None,
                "direct_payment_eligible": None,
                "reimbursement_request_category_maximum": None,
                "is_fertility_category": None,
                "credits_remaining": None,
                "id": None,
                "title": None,
                "credit_maximum": None,
            },
            "direct_payment_enabled": True,
            "debit_card_enabled": True,
            "is_active": False,
            "reimbursement_request_maximum": 1,
            "organization_id": 1,
            "id": "Sample text",
            "benefit_overview_resource": {"url": None, "title": None},
        }
        v1_schema = ReimbursementOrganizationSettingsSchema()
        v3_schema = ReimbursementOrganizationSettingsSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "benefit_faq_resource": {"url": None, "title": None},
            "survey_url": None,
            "allowed_reimbursement_categories": {
                "subtitle": None,
                "label": None,
                "reimbursement_request_category_maximum_amount": {
                    "currency_code": None,
                    "formatted_amount_truncated": None,
                    "amount": None,
                    "raw_amount": None,
                    "formatted_amount": None,
                },
                "benefit_type": None,
                "direct_payment_eligible": None,
                "reimbursement_request_category_maximum": None,
                "is_fertility_category": None,
                "credits_remaining": None,
                "id": None,
                "title": None,
                "credit_maximum": None,
            },
            "direct_payment_enabled": None,
            "debit_card_enabled": None,
            "is_active": None,
            "reimbursement_request_maximum": None,
            "organization_id": None,
            "id": None,
            "benefit_overview_resource": {"url": None, "title": None},
        }
        v1_schema = ReimbursementOrganizationSettingsSchema()
        v3_schema = ReimbursementOrganizationSettingsSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import ReimbursementWalletSchema
        from wallet.schemas.reimbursement_wallet_v3 import ReimbursementWalletSchemaV3

        data = {
            "id": "Sample text",
            "estimate_block": {
                "total_member_estimate": None,
                "estimate_bill_uuid": None,
                "payment_text": None,
                "total_estimates": None,
                "estimate_text": None,
            },
            "payment_block": {
                "show_benefit_amount": None,
                "variant": None,
                "num_errors": None,
            },
            "treatment_block": {
                "variant": None,
                "clinic": None,
                "clinic_location": None,
            },
            "channel_id": 1,
            "reimbursement_wallet_debit_card": {
                "issued_date": None,
                "shipping_tracking_number": None,
                "shipped_date": None,
                "card_proxy_number": None,
                "id": None,
                "card_status_reason": None,
                "card_last_4_digits": None,
                "created_date": None,
                "card_status": None,
                "reimbursement_wallet_id": None,
                "card_status_reason_text": None,
            },
            "hdhp_status": "Sample text",
            "currency_code": "Sample text",
            "benefit_id": None,
            "reimbursement_method": "Sample text",
            "upcoming_payments": {
                "summary": {
                    "procedure_title": None,
                    "total_benefit_amount": None,
                    "member_method_formatted": None,
                    "total_member_amount": None,
                    "member_method": None,
                    "benefit_remaining": None,
                },
                "payments": None,
            },
            "payments_customer_id": "Sample text",
            "household": [
                {
                    "name": None,
                    "last_name": "Sample text",
                    "first_name": "Sample text",
                    "id": 1,
                }
            ],
            "pharmacy": {"name": None, "url": None},
            "dependents": [
                {
                    "name": None,
                    "last_name": "Sample text",
                    "first_name": "Sample text",
                    "id": 1,
                }
            ],
            "zendesk_ticket_id": 2,
            "reimbursement_organization_settings": {
                "debit_card_enabled": None,
                "benefit_faq_resource": {"url": None, "title": None},
                "benefit_overview_resource": {"url": None, "title": None},
                "id": None,
                "reimbursement_request_maximum": None,
                "survey_url": None,
                "is_active": None,
                "direct_payment_enabled": None,
                "allowed_reimbursement_categories": {
                    "subtitle": None,
                    "credit_maximum": None,
                    "benefit_type": None,
                    "title": None,
                    "reimbursement_request_category_maximum_amount": {
                        "formatted_amount": None,
                        "currency_code": None,
                        "raw_amount": None,
                        "formatted_amount_truncated": None,
                        "amount": None,
                    },
                    "id": None,
                    "credits_remaining": None,
                    "is_fertility_category": None,
                    "label": None,
                    "reimbursement_request_category_maximum": None,
                    "direct_payment_eligible": None,
                },
                "organization_id": None,
            },
            "state": None,
            "debit_card_eligible": True,
            "reimbursement_request_block": {
                "total": None,
                "title": None,
                "details_text": None,
                "expected_reimbursement_amount": None,
                "reimbursement_text": None,
                "has_cost_breakdown_available": None,
                "reimbursement_request_uuid": None,
                "original_claim_text": None,
                "original_claim_amount": None,
            },
            "employee": {"name": None, "last_name": None, "first_name": None},
            "debit_banner": "Sample text",
            "members": [
                {
                    "name": None,
                    "last_name": "Sample text",
                    "first_name": "Sample text",
                    "id": 2,
                }
            ],
        }
        v1_schema = ReimbursementWalletSchema()
        v3_schema = ReimbursementWalletSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "id": None,
            "estimate_block": {
                "total_member_estimate": None,
                "estimate_bill_uuid": None,
                "payment_text": None,
                "total_estimates": None,
                "estimate_text": None,
            },
            "payment_block": {
                "show_benefit_amount": None,
                "variant": None,
                "num_errors": None,
            },
            "treatment_block": {
                "variant": None,
                "clinic": None,
                "clinic_location": None,
            },
            "channel_id": None,
            "reimbursement_wallet_debit_card": {
                "issued_date": None,
                "shipping_tracking_number": None,
                "shipped_date": None,
                "card_proxy_number": None,
                "id": None,
                "card_status_reason": None,
                "card_last_4_digits": None,
                "created_date": None,
                "card_status": None,
                "reimbursement_wallet_id": None,
                "card_status_reason_text": None,
            },
            "hdhp_status": None,
            "currency_code": None,
            "benefit_id": None,
            "reimbursement_method": None,
            "upcoming_payments": {
                "summary": {
                    "procedure_title": None,
                    "total_benefit_amount": None,
                    "member_method_formatted": None,
                    "total_member_amount": None,
                    "member_method": None,
                    "benefit_remaining": None,
                },
                "payments": None,
            },
            "payments_customer_id": None,
            "household": None,
            "pharmacy": {"name": None, "url": None},
            "dependents": None,
            "zendesk_ticket_id": None,
            "reimbursement_organization_settings": {
                "debit_card_enabled": None,
                "benefit_faq_resource": {"url": None, "title": None},
                "benefit_overview_resource": {"url": None, "title": None},
                "id": None,
                "reimbursement_request_maximum": None,
                "survey_url": None,
                "is_active": None,
                "direct_payment_enabled": None,
                "allowed_reimbursement_categories": {
                    "subtitle": None,
                    "credit_maximum": None,
                    "benefit_type": None,
                    "title": None,
                    "reimbursement_request_category_maximum_amount": {
                        "formatted_amount": None,
                        "currency_code": None,
                        "raw_amount": None,
                        "formatted_amount_truncated": None,
                        "amount": None,
                    },
                    "id": None,
                    "credits_remaining": None,
                    "is_fertility_category": None,
                    "label": None,
                    "reimbursement_request_category_maximum": None,
                    "direct_payment_eligible": None,
                },
                "organization_id": None,
            },
            "state": None,
            "debit_card_eligible": None,
            "reimbursement_request_block": {
                "total": None,
                "title": None,
                "details_text": None,
                "expected_reimbursement_amount": None,
                "reimbursement_text": None,
                "has_cost_breakdown_available": None,
                "reimbursement_request_uuid": None,
                "original_claim_text": None,
                "original_claim_amount": None,
            },
            "employee": {"name": None, "last_name": None, "first_name": None},
            "debit_banner": None,
            "members": None,
        }
        v1_schema = ReimbursementWalletSchema()
        v3_schema = ReimbursementWalletSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_reimbursement_wallet_response_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from wallet.schemas.reimbursement_wallet import (
            ReimbursementWalletResponseSchema,
        )
        from wallet.schemas.reimbursement_wallet_v3 import (
            ReimbursementWalletResponseSchemaV3,
        )

        data = {
            "data": {
                "payment_block": {
                    "show_benefit_amount": None,
                    "num_errors": None,
                    "variant": None,
                },
                "employee": {"name": None, "last_name": None, "first_name": None},
                "debit_card_eligible": None,
                "dependents": None,
                "estimate_block": {
                    "total_estimates": None,
                    "payment_text": None,
                    "estimate_text": None,
                    "total_member_estimate": None,
                    "estimate_bill_uuid": None,
                },
                "upcoming_payments": {
                    "summary": {
                        "procedure_title": None,
                        "total_member_amount": None,
                        "total_benefit_amount": None,
                        "benefit_remaining": None,
                        "member_method": None,
                        "member_method_formatted": None,
                    },
                    "payments": None,
                },
                "channel_id": None,
                "reimbursement_method": None,
                "members": None,
                "reimbursement_organization_settings": {
                    "is_active": None,
                    "reimbursement_request_maximum": None,
                    "id": None,
                    "benefit_faq_resource": {"title": None, "url": None},
                    "debit_card_enabled": None,
                    "benefit_overview_resource": {"title": None, "url": None},
                    "survey_url": None,
                    "allowed_reimbursement_categories": {
                        "title": None,
                        "credit_maximum": None,
                        "id": None,
                        "benefit_type": None,
                        "subtitle": None,
                        "reimbursement_request_category_maximum_amount": {
                            "currency_code": None,
                            "formatted_amount_truncated": None,
                            "formatted_amount": None,
                            "amount": None,
                            "raw_amount": None,
                        },
                        "direct_payment_eligible": None,
                        "reimbursement_request_category_maximum": None,
                        "credits_remaining": None,
                        "label": None,
                        "is_fertility_category": None,
                    },
                    "organization_id": None,
                    "direct_payment_enabled": None,
                },
                "state": None,
                "id": None,
                "reimbursement_request_block": {
                    "title": None,
                    "reimbursement_request_uuid": None,
                    "total": None,
                    "has_cost_breakdown_available": None,
                    "original_claim_text": None,
                    "reimbursement_text": None,
                    "original_claim_amount": None,
                    "details_text": None,
                    "expected_reimbursement_amount": None,
                },
                "hdhp_status": None,
                "treatment_block": {
                    "clinic": None,
                    "clinic_location": None,
                    "variant": None,
                },
                "payments_customer_id": None,
                "debit_banner": None,
                "benefit_id": None,
                "currency_code": None,
                "zendesk_ticket_id": None,
                "pharmacy": {"name": None, "url": None},
                "reimbursement_wallet_debit_card": {
                    "created_date": None,
                    "card_status_reason_text": None,
                    "id": None,
                    "card_status_reason": None,
                    "card_status": None,
                    "reimbursement_wallet_id": None,
                    "card_proxy_number": None,
                    "issued_date": None,
                    "shipped_date": None,
                    "shipping_tracking_number": None,
                    "card_last_4_digits": None,
                },
                "household": None,
            }
        }
        v1_schema = ReimbursementWalletResponseSchema()
        v3_schema = ReimbursementWalletResponseSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "data": {
                "payment_block": {
                    "show_benefit_amount": None,
                    "num_errors": None,
                    "variant": None,
                },
                "employee": {"name": None, "last_name": None, "first_name": None},
                "debit_card_eligible": None,
                "dependents": None,
                "estimate_block": {
                    "total_estimates": None,
                    "payment_text": None,
                    "estimate_text": None,
                    "total_member_estimate": None,
                    "estimate_bill_uuid": None,
                },
                "upcoming_payments": {
                    "summary": {
                        "procedure_title": None,
                        "total_member_amount": None,
                        "total_benefit_amount": None,
                        "benefit_remaining": None,
                        "member_method": None,
                        "member_method_formatted": None,
                    },
                    "payments": None,
                },
                "channel_id": None,
                "reimbursement_method": None,
                "members": None,
                "reimbursement_organization_settings": {
                    "is_active": None,
                    "reimbursement_request_maximum": None,
                    "id": None,
                    "benefit_faq_resource": {"title": None, "url": None},
                    "debit_card_enabled": None,
                    "benefit_overview_resource": {"title": None, "url": None},
                    "survey_url": None,
                    "allowed_reimbursement_categories": {
                        "title": None,
                        "credit_maximum": None,
                        "id": None,
                        "benefit_type": None,
                        "subtitle": None,
                        "reimbursement_request_category_maximum_amount": {
                            "currency_code": None,
                            "formatted_amount_truncated": None,
                            "formatted_amount": None,
                            "amount": None,
                            "raw_amount": None,
                        },
                        "direct_payment_eligible": None,
                        "reimbursement_request_category_maximum": None,
                        "credits_remaining": None,
                        "label": None,
                        "is_fertility_category": None,
                    },
                    "organization_id": None,
                    "direct_payment_enabled": None,
                },
                "state": None,
                "id": None,
                "reimbursement_request_block": {
                    "title": None,
                    "reimbursement_request_uuid": None,
                    "total": None,
                    "has_cost_breakdown_available": None,
                    "original_claim_text": None,
                    "reimbursement_text": None,
                    "original_claim_amount": None,
                    "details_text": None,
                    "expected_reimbursement_amount": None,
                },
                "hdhp_status": None,
                "treatment_block": {
                    "clinic": None,
                    "clinic_location": None,
                    "variant": None,
                },
                "payments_customer_id": None,
                "debit_banner": None,
                "benefit_id": None,
                "currency_code": None,
                "zendesk_ticket_id": None,
                "pharmacy": {"name": None, "url": None},
                "reimbursement_wallet_debit_card": {
                    "created_date": None,
                    "card_status_reason_text": None,
                    "id": None,
                    "card_status_reason": None,
                    "card_status": None,
                    "reimbursement_wallet_id": None,
                    "card_proxy_number": None,
                    "issued_date": None,
                    "shipped_date": None,
                    "shipping_tracking_number": None,
                    "card_last_4_digits": None,
                },
                "household": None,
            }
        }
        v1_schema = ReimbursementWalletResponseSchema()
        v3_schema = ReimbursementWalletResponseSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_s_m_s_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from messaging.schemas.sms import SMSSchema, SMSSchemaV3

        data = {
            "tel_number": "6501231234",
            "template": "default",
            "phone_number": "6501231234",
            "tel_region": "1",
        }
        v1_schema = SMSSchema()
        v3_schema = SMSSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "tel_number": None,
            "template": None,
            "phone_number": None,
            "tel_region": None,
        }
        v1_schema = SMSSchema()
        v3_schema = SMSSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_message_p_o_s_t_args(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from messaging.schemas.messaging import MessagePOSTArgs
        from messaging.schemas.messaging_v3 import MessagePOSTArgsV3

        data = {"source": None, "attachments": None, "body": "Sample text"}
        v1_schema = MessagePOSTArgs()
        v3_schema = MessagePOSTArgsV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"source": None, "attachments": None, "body": None}
        v1_schema = MessagePOSTArgs()
        v3_schema = MessagePOSTArgsV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_channel_participants_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from messaging.schemas.messaging import ChannelParticipantsSchema
        from messaging.schemas.messaging_v3 import ChannelParticipantsSchemaV3

        data = {
            "data": [
                {
                    "is_initiator": False,
                    "is_anonymous": False,
                    "user": {
                        "encoded_id": None,
                        "role": None,
                        "country": {
                            "abbr": None,
                            "summary": None,
                            "name": None,
                            "ext_info_link": None,
                        },
                        "username": None,
                        "image_url": None,
                        "image_id": 2,
                        "avatar_url": "Sample text",
                        "profiles": {
                            "practitioner": {
                                "country": {
                                    "abbr": None,
                                    "summary": None,
                                    "name": None,
                                    "ext_info_link": None,
                                },
                                "years_experience": 2,
                                "cancellation_policy": None,
                                "tel_region": "Sample text",
                                "education": "Sample text",
                                "phone_number": "Sample text",
                                "awards": "Sample text",
                                "can_prescribe": None,
                                "certifications": None,
                                "state": None,
                                "response_time": 2,
                                "specialties": None,
                                "rating": 77.56857112703082,
                                "address": {
                                    "zip_code": "Sample text",
                                    "state": "Sample text",
                                    "country": "Sample text",
                                    "city": "Sample text",
                                    "street_address": "Sample text",
                                },
                                "vertical_objects": [
                                    {
                                        "long_description": "Sample text",
                                        "id": 1,
                                        "description": "Sample text",
                                        "filter_by_state": False,
                                        "pluralized_display_name": "Sample text",
                                        "can_prescribe": False,
                                        "name": "Sample text",
                                    }
                                ],
                                "messaging_enabled": False,
                                "care_team_type": None,
                                "reference_quote": "Sample text",
                                "work_experience": "Sample text",
                                "certified_states": None,
                                "verticals": None,
                                "certified_subdivision_codes": None,
                                "can_member_interact": None,
                                "country_code": "Sample text",
                                "languages": None,
                                "subdivision_code": "Sample text",
                                "agreements": {"subscription": False},
                                "is_cx": None,
                                "faq_password": None,
                                "tel_number": "Sample text",
                                "next_availability": datetime.datetime(
                                    2024,
                                    12,
                                    2,
                                    1,
                                    1,
                                    48,
                                    93295,
                                    tzinfo=datetime.timezone.utc,
                                ),
                                "user_id": 1,
                                "categories": None,
                                "can_prescribe_to_member": None,
                            },
                            "member": {
                                "subdivision_code": "Sample text",
                                "country": None,
                                "state": None,
                                "has_care_plan": False,
                                "phone_number": "Sample text",
                                "user_flags": None,
                                "tel_region": "Sample text",
                                "color_hex": "Sample text",
                                "can_book_cx": None,
                                "care_plan_id": 1,
                                "tel_number": "Sample text",
                                "address": {
                                    "zip_code": "Sample text",
                                    "state": "Sample text",
                                    "country": "Sample text",
                                    "city": "Sample text",
                                    "street_address": "Sample text",
                                },
                                "opted_in_notes_sharing": True,
                            },
                        },
                        "subscription_plans": None,
                        "first_name": "Sample text",
                        "organization": {
                            "id": 2,
                            "rx_enabled": True,
                            "vertical_group_version": "Sample text",
                            "name": "Sample text",
                            "education_only": False,
                            "benefits_url": "Sample text",
                            "display_name": "Sample text",
                            "bms_enabled": False,
                        },
                        "last_name": "Sample text",
                        "care_coordinators": [
                            {
                                "encoded_id": None,
                                "role": None,
                                "country": {
                                    "abbr": None,
                                    "summary": None,
                                    "name": None,
                                    "ext_info_link": None,
                                },
                                "username": None,
                                "image_url": None,
                                "image_id": 2,
                                "avatar_url": "Sample text",
                                "profiles": {
                                    "practitioner": {
                                        "country": {
                                            "abbr": None,
                                            "summary": None,
                                            "name": None,
                                            "ext_info_link": None,
                                        },
                                        "years_experience": 1,
                                        "cancellation_policy": None,
                                        "tel_region": "Sample text",
                                        "education": "Sample text",
                                        "phone_number": "Sample text",
                                        "awards": "Sample text",
                                        "can_prescribe": None,
                                        "certifications": None,
                                        "state": None,
                                        "response_time": 1,
                                        "specialties": None,
                                        "rating": 97.83849434524292,
                                        "address": {
                                            "zip_code": "Sample text",
                                            "state": "Sample text",
                                            "country": "Sample text",
                                            "city": "Sample text",
                                            "street_address": "Sample text",
                                        },
                                        "vertical_objects": [
                                            {
                                                "long_description": "Sample text",
                                                "id": 2,
                                                "description": "Sample text",
                                                "filter_by_state": False,
                                                "pluralized_display_name": "Sample text",
                                                "can_prescribe": False,
                                                "name": "Sample text",
                                            }
                                        ],
                                        "messaging_enabled": True,
                                        "care_team_type": None,
                                        "reference_quote": "Sample text",
                                        "work_experience": "Sample text",
                                        "certified_states": None,
                                        "verticals": None,
                                        "certified_subdivision_codes": None,
                                        "can_member_interact": None,
                                        "country_code": "Sample text",
                                        "languages": None,
                                        "subdivision_code": "Sample text",
                                        "agreements": {"subscription": False},
                                        "is_cx": None,
                                        "faq_password": None,
                                        "tel_number": "Sample text",
                                        "next_availability": datetime.datetime(
                                            2024,
                                            12,
                                            2,
                                            1,
                                            1,
                                            48,
                                            93392,
                                            tzinfo=datetime.timezone.utc,
                                        ),
                                        "user_id": 2,
                                        "categories": None,
                                        "can_prescribe_to_member": None,
                                    },
                                    "member": {
                                        "subdivision_code": "Sample text",
                                        "country": None,
                                        "state": None,
                                        "has_care_plan": True,
                                        "phone_number": "Sample text",
                                        "user_flags": None,
                                        "tel_region": "Sample text",
                                        "color_hex": "Sample text",
                                        "can_book_cx": None,
                                        "care_plan_id": 1,
                                        "tel_number": "Sample text",
                                        "address": {
                                            "zip_code": "Sample text",
                                            "state": "Sample text",
                                            "country": "Sample text",
                                            "city": "Sample text",
                                            "street_address": "Sample text",
                                        },
                                        "opted_in_notes_sharing": False,
                                    },
                                },
                                "subscription_plans": None,
                                "first_name": "Sample text",
                                "organization": {
                                    "id": 2,
                                    "rx_enabled": False,
                                    "vertical_group_version": "Sample text",
                                    "name": "Sample text",
                                    "education_only": False,
                                    "benefits_url": "Sample text",
                                    "display_name": "Sample text",
                                    "bms_enabled": False,
                                },
                                "last_name": "Sample text",
                                "email": None,
                                "id": 1,
                                "middle_name": "Sample text",
                                "esp_id": None,
                                "name": None,
                                "test_group": "Sample text",
                            }
                        ],
                        "email": None,
                        "id": 1,
                        "middle_name": "Sample text",
                        "esp_id": None,
                        "name": None,
                        "test_group": "Sample text",
                    },
                    "max_chars": 1,
                }
            ]
        }
        v1_schema = ChannelParticipantsSchema()
        v3_schema = ChannelParticipantsSchemaV3()

        user = DefaultUserFactory.create()
        with patch("storage.connection.db.session.query") as mock_db_query:
            mock_db_query.return_value.filter.return_value.one.return_value = user
            assert v1_schema.dump(data).data == v3_schema.dump(
                data
            ), "Backwards compatibility broken between versions"

        edge_case = {"data": None}
        v1_schema = ChannelParticipantsSchema()
        v3_schema = ChannelParticipantsSchemaV3()

        with patch("storage.connection.db.session.query") as mock_db_query:
            mock_db_query.return_value.filter.return_value.one.return_value = user
            assert v1_schema.dump(edge_case).data == v3_schema.dump(
                edge_case
            ), "Backwards compatibility broken between versions"

    def test_participant_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from messaging.schemas.messaging import ParticipantSchema
        from messaging.schemas.messaging_v3 import ParticipantSchemaV3

        data = {
            "user": {
                "role": None,
                "test_group": None,
                "username": None,
                "image_id": None,
                "care_coordinators": None,
                "name": None,
                "id": None,
                "encoded_id": None,
                "first_name": None,
                "subscription_plans": None,
                "image_url": None,
                "country": {
                    "name": None,
                    "summary": None,
                    "abbr": None,
                    "ext_info_link": None,
                },
                "last_name": None,
                "email": None,
                "organization": {
                    "vertical_group_version": None,
                    "education_only": None,
                    "benefits_url": None,
                    "bms_enabled": None,
                    "rx_enabled": None,
                    "display_name": None,
                    "name": None,
                    "id": None,
                },
                "middle_name": None,
                "profiles": {
                    "practitioner": {
                        "cancellation_policy": None,
                        "certifications": None,
                        "certified_states": None,
                        "address": {
                            "street_address": None,
                            "country": None,
                            "zip_code": None,
                            "state": None,
                            "city": None,
                        },
                        "categories": None,
                        "is_cx": None,
                        "rating": None,
                        "next_availability": None,
                        "vertical_objects": None,
                        "specialties": None,
                        "user_id": None,
                        "tel_number": None,
                        "tel_region": None,
                        "country": {
                            "name": None,
                            "summary": None,
                            "abbr": None,
                            "ext_info_link": None,
                        },
                        "years_experience": None,
                        "verticals": None,
                        "can_prescribe_to_member": None,
                        "languages": None,
                        "care_team_type": None,
                        "certified_subdivision_codes": None,
                        "subdivision_code": None,
                        "state": None,
                        "education": None,
                        "awards": None,
                        "faq_password": None,
                        "messaging_enabled": None,
                        "can_prescribe": None,
                        "can_member_interact": None,
                        "work_experience": None,
                        "reference_quote": None,
                        "response_time": None,
                        "agreements": {"subscription": None},
                        "phone_number": None,
                        "country_code": None,
                    },
                    "member": {
                        "tel_number": None,
                        "can_book_cx": None,
                        "opted_in_notes_sharing": None,
                        "color_hex": None,
                        "tel_region": None,
                        "country": None,
                        "has_care_plan": None,
                        "state": None,
                        "subdivision_code": None,
                        "user_flags": None,
                        "address": {
                            "street_address": None,
                            "country": None,
                            "zip_code": None,
                            "state": None,
                            "city": None,
                        },
                        "care_plan_id": None,
                        "phone_number": None,
                    },
                },
                "avatar_url": None,
                "esp_id": None,
            },
            "max_chars": 2,
            "is_anonymous": False,
            "is_initiator": False,
        }
        v1_schema = ParticipantSchema()
        v3_schema = ParticipantSchemaV3()

        user = DefaultUserFactory.create()
        with patch("storage.connection.db.session.query") as mock_db_query:
            mock_db_query.return_value.filter.return_value.one.return_value = user
            assert v1_schema.dump(data).data == v3_schema.dump(
                data
            ), "Backwards compatibility broken between versions"

        edge_case = {
            "user": {
                "role": None,
                "test_group": None,
                "username": None,
                "image_id": None,
                "care_coordinators": None,
                "name": None,
                "id": None,
                "encoded_id": None,
                "first_name": None,
                "subscription_plans": None,
                "image_url": None,
                "country": {
                    "name": None,
                    "summary": None,
                    "abbr": None,
                    "ext_info_link": None,
                },
                "last_name": None,
                "email": None,
                "organization": {
                    "vertical_group_version": None,
                    "education_only": None,
                    "benefits_url": None,
                    "bms_enabled": None,
                    "rx_enabled": None,
                    "display_name": None,
                    "name": None,
                    "id": None,
                },
                "middle_name": None,
                "profiles": {
                    "practitioner": {
                        "cancellation_policy": None,
                        "certifications": None,
                        "certified_states": None,
                        "address": {
                            "street_address": None,
                            "country": None,
                            "zip_code": None,
                            "state": None,
                            "city": None,
                        },
                        "categories": None,
                        "is_cx": None,
                        "rating": None,
                        "next_availability": None,
                        "vertical_objects": None,
                        "specialties": None,
                        "user_id": None,
                        "tel_number": None,
                        "tel_region": None,
                        "country": {
                            "name": None,
                            "summary": None,
                            "abbr": None,
                            "ext_info_link": None,
                        },
                        "years_experience": None,
                        "verticals": None,
                        "can_prescribe_to_member": None,
                        "languages": None,
                        "care_team_type": None,
                        "certified_subdivision_codes": None,
                        "subdivision_code": None,
                        "state": None,
                        "education": None,
                        "awards": None,
                        "faq_password": None,
                        "messaging_enabled": None,
                        "can_prescribe": None,
                        "can_member_interact": None,
                        "work_experience": None,
                        "reference_quote": None,
                        "response_time": None,
                        "agreements": {"subscription": None},
                        "phone_number": None,
                        "country_code": None,
                    },
                    "member": {
                        "tel_number": None,
                        "can_book_cx": None,
                        "opted_in_notes_sharing": None,
                        "color_hex": None,
                        "tel_region": None,
                        "country": None,
                        "has_care_plan": None,
                        "state": None,
                        "subdivision_code": None,
                        "user_flags": None,
                        "address": {
                            "street_address": None,
                            "country": None,
                            "zip_code": None,
                            "state": None,
                            "city": None,
                        },
                        "care_plan_id": None,
                        "phone_number": None,
                    },
                },
                "avatar_url": None,
                "esp_id": None,
            },
            "max_chars": None,
            "is_anonymous": None,
            "is_initiator": None,
        }
        v1_schema = ParticipantSchema()
        v3_schema = ParticipantSchemaV3()

        with patch("storage.connection.db.session.query") as mock_db_query:
            mock_db_query.return_value.filter.return_value.one.return_value = user
            assert v1_schema.dump(edge_case).data == v3_schema.dump(
                edge_case
            ), "Backwards compatibility broken between versions"

    def test_stripe_d_o_b_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.payments import StripeDOBSchema, StripeDOBSchemaV3

        data = {"day": "Sample text", "year": "Sample text", "month": "Sample text"}
        v1_schema = StripeDOBSchema()
        v3_schema = StripeDOBSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"day": None, "year": None, "month": None}
        v1_schema = StripeDOBSchema()
        v3_schema = StripeDOBSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_stripe_address_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.payments import StripeAddressSchema, StripeAddressSchemaV3

        data = {
            "postal_code": "Sample text",
            "line1": "Sample text",
            "state": "Sample text",
            "city": "Sample text",
        }
        v1_schema = StripeAddressSchema()
        v3_schema = StripeAddressSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"postal_code": None, "line1": None, "state": None, "city": None}
        v1_schema = StripeAddressSchema()
        v3_schema = StripeAddressSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_stripe_document_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.payments import StripeDocumentSchema, StripeDocumentSchemaV3

        data = {
            "details_code": "Sample text",
            "front": "Sample text",
            "details": "Sample text",
            "back": "Sample text",
        }
        v1_schema = StripeDocumentSchema()
        v3_schema = StripeDocumentSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"details_code": None, "front": None, "details": None, "back": None}
        v1_schema = StripeDocumentSchema()
        v3_schema = StripeDocumentSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_stripe_verification_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.payments import StripeVerificationSchema, StripeVerificationSchemaV3

        data = {
            "additional_document": {
                "details_code": None,
                "front": None,
                "back": None,
                "details": None,
            },
            "document": {
                "details_code": None,
                "front": None,
                "back": None,
                "details": None,
            },
        }
        v1_schema = StripeVerificationSchema()
        v3_schema = StripeVerificationSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "additional_document": {
                "details_code": None,
                "front": None,
                "back": None,
                "details": None,
            },
            "document": {
                "details_code": None,
                "front": None,
                "back": None,
                "details": None,
            },
        }
        v1_schema = StripeVerificationSchema()
        v3_schema = StripeVerificationSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_legal_entity_individual_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.payments import (
            LegalEntityIndividualSchema,
            LegalEntityIndividualSchemaV3,
        )

        data = {
            "address": {
                "postal_code": None,
                "city": None,
                "line1": None,
                "state": None,
            },
            "ssn_last_4_provided": True,
            "verification": {
                "document": {
                    "details": None,
                    "back": None,
                    "front": None,
                    "details_code": None,
                },
                "additional_document": {
                    "details": None,
                    "back": None,
                    "front": None,
                    "details_code": None,
                },
            },
            "last_name": "Sample text",
            "type": "Sample text",
            "id_number": "Sample text",
            "dob": {"year": None, "month": None, "day": None},
            "first_name": "Sample text",
            "ssn_last_4": "Sample text",
            "id_number_provided": True,
        }
        v1_schema = LegalEntityIndividualSchema()
        v3_schema = LegalEntityIndividualSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "address": {
                "postal_code": None,
                "city": None,
                "line1": None,
                "state": None,
            },
            "ssn_last_4_provided": None,
            "verification": {
                "document": {
                    "details": None,
                    "back": None,
                    "front": None,
                    "details_code": None,
                },
                "additional_document": {
                    "details": None,
                    "back": None,
                    "front": None,
                    "details_code": None,
                },
            },
            "last_name": None,
            "type": None,
            "id_number": None,
            "dob": {"year": None, "month": None, "day": None},
            "first_name": None,
            "ssn_last_4": None,
            "id_number_provided": None,
        }
        v1_schema = LegalEntityIndividualSchema()
        v3_schema = LegalEntityIndividualSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_legal_entity_company_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.payments import LegalEntityCompanySchema, LegalEntityCompanySchemaV3

        data = {
            "verification": {
                "document": {
                    "front": None,
                    "details_code": None,
                    "details": None,
                    "back": None,
                }
            },
            "type": "Sample text",
            "tax_id_provided": True,
            "name": "Sample text",
            "tax_id": "Sample text",
            "address": {
                "state": None,
                "postal_code": None,
                "city": None,
                "line1": None,
            },
        }
        v1_schema = LegalEntityCompanySchema()
        v3_schema = LegalEntityCompanySchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "verification": {
                "document": {
                    "front": None,
                    "details_code": None,
                    "details": None,
                    "back": None,
                }
            },
            "type": None,
            "tax_id_provided": None,
            "name": None,
            "tax_id": None,
            "address": {
                "state": None,
                "postal_code": None,
                "city": None,
                "line1": None,
            },
        }
        v1_schema = LegalEntityCompanySchema()
        v3_schema = LegalEntityCompanySchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_terms_of_service_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.payments import TermsOfServiceSchema, TermsOfServiceSchemaV3

        data = {"ip": "Sample text", "date": 2, "user_agent": "Sample text"}
        v1_schema = TermsOfServiceSchema()
        v3_schema = TermsOfServiceSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {"ip": None, "date": None, "user_agent": None}
        v1_schema = TermsOfServiceSchema()
        v3_schema = TermsOfServiceSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_connect_account_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from views.payments import ConnectAccountSchema, ConnectAccountSchemaV3

        data = {
            "tos_acceptance": {"date": None, "ip": None, "user_agent": None},
            "company": {
                "name": None,
                "tax_id_provided": None,
                "verification": {
                    "document": {
                        "details_code": None,
                        "back": None,
                        "details": None,
                        "front": None,
                    }
                },
                "address": {
                    "state": None,
                    "line1": None,
                    "city": None,
                    "postal_code": None,
                },
            },
            "payouts_enabled": True,
            "individual": {
                "id_number": None,
                "last_name": None,
                "id_number_provided": None,
                "dob": {"day": None, "month": None, "year": None},
                "ssn_last_4_provided": None,
                "ssn_last_4": None,
                "first_name": None,
                "verification": {
                    "additional_document": {
                        "details_code": None,
                        "back": None,
                        "details": None,
                        "front": None,
                    },
                    "document": {
                        "details_code": None,
                        "back": None,
                        "details": None,
                        "front": None,
                    },
                },
                "address": {
                    "state": None,
                    "line1": None,
                    "city": None,
                    "postal_code": None,
                },
            },
            "external_accounts": {
                "data": [
                    {
                        "country": "Sample text",
                        "last4": "Sample text",
                        "bank_name": "Sample text",
                    }
                ]
            },
        }
        v1_schema = ConnectAccountSchema()
        v3_schema = ConnectAccountSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "tos_acceptance": {"date": None, "ip": None, "user_agent": None},
            "company": {
                "name": None,
                "tax_id_provided": None,
                "verification": {
                    "document": {
                        "details_code": None,
                        "back": None,
                        "details": None,
                        "front": None,
                    }
                },
                "address": {
                    "state": None,
                    "line1": None,
                    "city": None,
                    "postal_code": None,
                },
            },
            "payouts_enabled": None,
            "individual": {
                "id_number": None,
                "last_name": None,
                "id_number_provided": None,
                "dob": {"day": None, "month": None, "year": None},
                "ssn_last_4_provided": None,
                "ssn_last_4": None,
                "first_name": None,
                "verification": {
                    "additional_document": {
                        "details_code": None,
                        "back": None,
                        "details": None,
                        "front": None,
                    },
                    "document": {
                        "details_code": None,
                        "back": None,
                        "details": None,
                        "front": None,
                    },
                },
                "address": {
                    "state": None,
                    "line1": None,
                    "city": None,
                    "postal_code": None,
                },
            },
            "external_accounts": {"data": None},
        }
        v1_schema = ConnectAccountSchema()
        v3_schema = ConnectAccountSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"

    def test_attachment_schema(self):
        """
        Auto generated method by scripts/ma_coverage_tool

        Please make necessary updates, i.e. database query mock used by schema, to make it pass
        """
        from messaging.schemas.messaging import AttachmentSchema
        from messaging.schemas.messaging_v3 import AttachmentSchemaV3

        data = {
            "content_type": "Sample text",
            "content_length": 2,
            "thumbnail": None,
            "file_name": "Sample text",
            "id": None,
        }
        v1_schema = AttachmentSchema()
        v3_schema = AttachmentSchemaV3()
        assert v1_schema.dump(data).data == v3_schema.dump(
            data
        ), "Backwards compatibility broken between versions"

        edge_case = {
            "content_type": None,
            "content_length": None,
            "thumbnail": None,
            "file_name": None,
            "id": None,
        }
        v1_schema = AttachmentSchema()
        v3_schema = AttachmentSchemaV3()
        assert v1_schema.dump(edge_case).data == v3_schema.dump(
            edge_case
        ), "Backwards compatibility broken between versions"
