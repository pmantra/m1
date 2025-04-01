import datetime
import json
from collections import namedtuple
from http import HTTPStatus
from typing import List
from unittest import mock
from unittest.mock import patch

import pytest

from appointments.models.appointment import (
    _MEMBER_TOKEN,
    _PRACTITIONER_TOKEN,
    _SESSION_ID,
    Appointment,
)
from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.schedule_event import ScheduleEvent
from appointments.pytests.factories import PaymentAccountingEntryFactory
from appointments.pytests.mock_search_api_response import search_api_response_8_hits_obj
from appointments.repository.schedules import (
    ScheduleEventRepository,
    ScheduleRecurringBlockRepository,
)
from appointments.services.common import round_to_nearest_minutes
from appointments.services.recurring_schedule import (
    RecurringScheduleAvailabilityService,
)
from appointments.utils.flask_redis_ext import FlaskRedis
from authn.models.user import User
from common.services.stripe import StripeCustomerClient
from models.products import Product
from payments.models.practitioner_contract import ContractType
from payments.pytests.factories import PractitionerContractFactory
from pytests import freezegun
from pytests.factories import (
    AppointmentFactory,
    CreditFactory,
    EnterpriseUserFactory,
    PractitionerUserFactory,
    ProductFactory,
    VerticalFactory,
)
from pytests.stripe_fixtures import captured_charge, one_card_list, uncaptured_payment
from utils.cache import redis_client

AppointmentSetupValues = namedtuple(
    "AppointmentSetupValues", ["member", "product", "data", "practitioner"]
)
PATCH_RESCHEDULE_APPOINTMENT_SETUP_VALUES = namedtuple(
    "patch_reschedule_appointment_setup_values",
    ["member", "product", "reschedule_appointment_request", "appointment"],
)

now = datetime.datetime.utcnow()


@pytest.fixture
def app_with_redis(app):
    FlaskRedis(app)
    return app


@pytest.fixture
def client(app_with_redis):
    with app_with_redis.test_client() as client:
        yield client


@pytest.fixture
def vertical_ca():
    return VerticalFactory.create_cx_vertical()


@pytest.fixture
def vertical_wellness_coach_cannot_prescribe(factories):
    vertical = factories.VerticalFactory.create(
        name="Wellness Coach",
        pluralized_display_name="Wellness Coaches",
        can_prescribe=False,
        filter_by_state=False,
    )

    return vertical


@pytest.fixture
def vertical_wellness_coach_can_prescribe(factories):
    vertical = factories.VerticalFactory.create(
        name="Wellness Coach",
        pluralized_display_name="Wellness Coaches",
        can_prescribe=True,
        filter_by_state=False,
    )

    return vertical


@pytest.fixture
def member_with_add_appointment(factories, states):
    """Returns a member with the add_appointment permission"""
    c = factories.CapabilityFactory.create(object_type="appointment", method="post")
    r = factories.RoleFactory.create(name="member", capabilities=[c])

    member = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user=member,
        role=r,
        phone_number="+12125551515",
        dosespot={},
        state=states["NY"],
    )
    return member


@pytest.fixture
def doula_only_member_with_add_appointment_permission(
    factories, create_doula_only_member, states
):
    """Returns a doula only member with the add_appointment permission"""
    c = factories.CapabilityFactory.create(object_type="appointment", method="post")
    r = factories.RoleFactory.create(name="member", capabilities=[c])

    member = create_doula_only_member

    factories.MemberProfileFactory.create(
        user=member,
        role=r,
        phone_number="+12125551515",
        dosespot={},
        state=states["NY"],
    )
    return member


@pytest.fixture
def member_with_reschedule_appointment(factories):
    """Returns a member for the rescheduling the appointment"""
    r = factories.RoleFactory.create(name="member")

    member = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user=member, role=r, phone_number="+12125551515", dosespot={}
    )
    return member


@pytest.fixture
def practitioner_user(vertical_ca):
    def make_practitioner_user(
        verticals=[vertical_ca],  # noqa  B006
    ):
        pu = PractitionerUserFactory.create(
            practitioner_profile__verticals=verticals,
            practitioner_profile__country_code="US",
        )
        return pu

    return make_practitioner_user


@pytest.fixture
def wellness_coach_user(vertical_wellness_coach_cannot_prescribe):
    def make_wellness_coach_user(
        verticals=[vertical_wellness_coach_cannot_prescribe],  # noqa  B008
    ):
        wcu = PractitionerUserFactory.create(
            practitioner_profile__verticals=verticals,
        )
        return wcu

    return make_wellness_coach_user


@pytest.fixture
def valid_appointment():
    def make_valid_appointment(
        created_at=datetime.datetime.utcnow(),  # noqa  B008
        product=ProductFactory.create(),  # noqa  B008
        scheduled_start=datetime.datetime.utcnow(),  # noqa  B008
        member_started_at=None,
        practitioner_started_at=None,
        is_enterprise_factory=True,
        member_ended_at=None,
        practitioner_ended_at=None,
        cancelled_at=None,
        disputed_at=None,
    ):
        a = AppointmentFactory.create(
            created_at=created_at,
            product=product,
            scheduled_start=scheduled_start,
            member_started_at=member_started_at,
            practitioner_started_at=practitioner_started_at,
            is_enterprise_factory=is_enterprise_factory,
            member_ended_at=member_ended_at,
            practitioner_ended_at=practitioner_ended_at,
            cancelled_at=cancelled_at,
            disputed_at=disputed_at,
        )
        return a

    return make_valid_appointment


@pytest.fixture
def appointment_with_video_info(factories):
    appt = factories.AppointmentFactory.create()
    appt.video = {
        _SESSION_ID: "1",
        _MEMBER_TOKEN: "1",
        _PRACTITIONER_TOKEN: "1",
    }
    return appt


@pytest.fixture
def valid_appointment_with_user(factories):
    def make_valid_appointment_with_user(
        practitioner,
        scheduled_start=datetime.datetime.utcnow(),  # noqa  B008
        # TODO:  Do not perform function calls in argument defaults.  The call is performed only once at function definition time. All calls to your function will reuse the result of that definition-time function call.  If this is intended, assign the function call to a module-level variable and use that variable as a default value.
        scheduled_end=None,
        purpose=None,
        member_schedule=None,
    ):
        a = factories.AppointmentFactory.create_with_practitioner(
            member_schedule=member_schedule,
            purpose=purpose,
            practitioner=practitioner,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
        )
        return a

    return make_valid_appointment_with_user


@pytest.fixture
def appointment_payment():
    def make_payment(appointment):
        p = PaymentAccountingEntryFactory.create(appointment_id=appointment.id)
        return p

    return make_payment


@pytest.fixture()
def states(create_state):
    return {
        "NY": create_state(name="New York", abbreviation="NY"),
        "NJ": create_state(name="New Jersey", abbreviation="NJ"),
        "CA": create_state(name="California", abbreviation="CA"),
    }


@pytest.fixture()
def create_marketplace_user(factories, states):
    def _create_marketplace_user(state=states["NY"], **kwargs):
        member = factories.MemberFactory.create(
            member_profile__state=state,
            **kwargs,
        )

        return member

    return _create_marketplace_user


@pytest.fixture(scope="function")
def marketplace_user(create_marketplace_user):
    return create_marketplace_user()


@pytest.fixture(scope="function")
def marketplace_user_NJ(create_marketplace_user, states):
    return create_marketplace_user(
        state=states["NJ"],
    )


@pytest.fixture
def enterprise_user(factories):
    return factories.EnterpriseUserFactory.create()


@pytest.fixture
def enterprise_user_with_tracks_and_categories(factories):
    def _create_enterprise_user_with_tracks_and_categories(track_names: List[str]):
        member = factories.EnterpriseUserFactory.create(tracks=[])
        tracks = []
        need_categories = []
        for track_name in track_names:
            tracks.append(
                factories.MemberTrackFactory.create(name=track_name, user=member)
            )

            nc = factories.NeedCategoryFactory.create()
            need_categories.append(nc)
            factories.NeedCategoryTrackFactory.create(
                track_name=track_name,
                need_category_id=nc.id,
            )
        return member, tracks, need_categories

    return _create_enterprise_user_with_tracks_and_categories


@pytest.fixture(scope="function")
def create_practitioner(factories, states):
    def _create_practitioner(state=states["NY"], **kwargs):
        return factories.PractitionerUserFactory.create(
            practitioner_profile__state=state,
            practitioner_profile__certified_states=[state],
            **kwargs,
        )

    return _create_practitioner


@pytest.fixture
def practitioner_with_product_prices(factories):
    def make_with_products_prices(prices: List[int]):
        practitioner_user = factories.PractitionerUserFactory.create()

        products = [factories.ProductFactory.create(price=p) for p in prices]
        practitioner_user.products = products

        return practitioner_user

    return make_with_products_prices


@pytest.fixture
def practitioner_profile_with_product_prices(practitioner_with_product_prices):
    def make_with_products_prices(prices: List[int]):
        practitioner_user = practitioner_with_product_prices(prices)
        return practitioner_user.practitioner_profile

    return make_with_products_prices


@pytest.fixture()
def practitioner_with_availability(factories, create_practitioner):
    vertical = factories.VerticalFactory.create(products=None)

    products = [
        factories.ProductFactory(
            practitioner=None,
            vertical=vertical,
            minutes=30,
        ),
        factories.ProductFactory(practitioner=None, vertical=vertical, minutes=60),
    ]

    now = datetime.datetime.utcnow()
    practitioner = create_practitioner(
        practitioner_profile__next_availability=now + datetime.timedelta(minutes=3),
        practitioner_profile__verticals=[vertical],
        products=products,
    )

    schedule = factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=(now + datetime.timedelta(minutes=30)),
        ends_at=(now + datetime.timedelta(hours=2)),
    )

    return practitioner, schedule


@pytest.fixture
def valid_questionnaire_with_oid(factories):
    def make_valid_questionnaire_with_oid(oid):
        return factories.QuestionnaireFactory.create(oid=oid)

    return make_valid_questionnaire_with_oid


@pytest.fixture
def valid_questionnaire_with_verticals(factories):
    def make_valid_questionnaire_with_verticals(verticals):
        return factories.QuestionnaireFactory.create(verticals=verticals)

    return make_valid_questionnaire_with_verticals


@pytest.fixture
def new_credit():
    def make_new_credit(
        amount=0,
        user=EnterpriseUserFactory.create(),  # noqa  B008
        # TODO:  Do not perform function calls in argument defaults.  The call is performed only once at function definition time. All calls to your function will reuse the result of that definition-time function call.  If this is intended, assign the function call to a module-level variable and use that variable as a default value.
    ):
        return CreditFactory.create(
            amount=amount,
            user=user,
        )

    return make_new_credit


@pytest.fixture
def basic_appointment(valid_appointment):
    return valid_appointment(is_enterprise_factory=False)


@pytest.fixture
def enterprise_appointment(valid_appointment):
    return valid_appointment(is_enterprise_factory=True)


@pytest.fixture
def cancellable_appointment(factories):
    # Create the cancellable appointment
    appointment = factories.AppointmentFactory.create_with_cancellable_state()
    appointment.cancellation_policy = factories.CancellationPolicyFactory.create()
    appointment.product.price = 1
    return appointment


@pytest.fixture
def non_refundable_cancellable_appointment(factories, datetime_now):
    cancellation_policy = factories.CancellationPolicyFactory.create(refund_48_hours=30)
    return factories.AppointmentFactory.create(
        cancellation_policy=cancellation_policy,
        scheduled_start=datetime_now + datetime.timedelta(hours=50),
        created_at=datetime_now - datetime.timedelta(minutes=15),
    )


@pytest.fixture
def cancelled_appointment(factories):
    return AppointmentFactory.create(
        created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(hours=50),
        cancelled_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=10),
    )


@pytest.fixture
def scheduled_appointment(factories):
    return factories.AppointmentFactory.create(
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    )


@pytest.fixture
def scheduled_appointment_with_member_note(factories):
    return factories.AppointmentFactory.create(
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        client_notes="Original Note",
    )


@pytest.fixture
def started_appointment(factories):
    return factories.AppointmentFactory.create_with_completeable_state()


@pytest.fixture
def ended_appointment(factories):
    return factories.AppointmentFactory.create_with_state_payment_pending()


@pytest.fixture
def incomplete_appointment(factories):
    return factories.AppointmentFactory.create_with_state_incomplete()


@pytest.fixture
def anonymous_appointment(factories):
    return factories.AppointmentFactory.create_anonymous()


@pytest.fixture
def add_appointment_post_session_note(factories):
    """Adds a draft post session note to an appointment"""

    def add_appointment_post_session_note_func(**kwargs):
        appointment = kwargs.get("appointment")
        return factories.AppointmentMetaDataFactory.create(
            draft=True,
            appointment_id=appointment.id,
            **kwargs,
        )

    return add_appointment_post_session_note_func


@pytest.fixture
def add_non_draft_appointment_post_session_note(factories):
    """Adds a non-draft post session note to an appointment"""

    def add_appointment_post_session_note_not_draft_func(**kwargs):
        appointment = kwargs.get("appointment")
        return factories.AppointmentMetaDataFactory.create(
            draft=False,
            appointment_id=appointment.id,
            **kwargs,
        )

    return add_appointment_post_session_note_not_draft_func


@pytest.fixture
def get_post_session_dict_in_response():
    def get_post_session_dict_in_response_func(appointment_meta_data=None):
        if appointment_meta_data:
            return {
                "notes": appointment_meta_data.content,
                "created_at": appointment_meta_data.created_at.isoformat(),
                "modified_at": appointment_meta_data.modified_at.isoformat(),
                "draft": appointment_meta_data.draft,
            }
        return {
            "modified_at": None,
            "created_at": None,
            "draft": None,
            "notes": "",
        }

    return get_post_session_dict_in_response_func


@pytest.fixture
def appointment_with_pharmacy(valid_appointment_with_user, practitioner_user):
    ca = practitioner_user()
    dp = ca.practitioner_profile.dosespot
    dp["clinic_key"] = 1
    dp["clinic_id"] = 1
    dp["user_id"] = 1

    a = valid_appointment_with_user(
        practitioner=ca,
        purpose="birth_needs_assessment",
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
    )
    mp = a.member.member_profile
    mp.set_patient_info(patient_id=a.member.id, practitioner_id=a.practitioner.id)
    return ca, a


@pytest.fixture
def enable_appointment_rx(factories, valid_pharmacy):
    def enable_appointment_rx_func(appointment):
        """Enabled rx on an appointment"""
        # Set settings necessary for practitioner to can_prescribe
        practitioner_profile = appointment.practitioner.profile
        practitioner_profile.dosespot = {
            "clinic_key": "secret_key",
            "user_id": 1,
            "clinic_id": 1,
        }

        # Set settings necessary for member enabled_for_prescription
        appointment.member.health_profile.json["birthday"] = "1982-01-13T00:00:00"
        member_profile = appointment.member.profile
        member_profile.user.first_name = "Billy Bo Bob"
        member_profile.user.last_name = "Brain"
        member_profile.state = practitioner_profile.certified_states[0]
        member_profile.add_or_update_address(
            {
                "street_address": "123 Foo Bar Road",
                "zip_code": 11234,
                "city": "Foo Bar",
                "state": member_profile.state.abbreviation,
                "country": "US",
            }
        )
        member_profile.phone_number = "1-212-555-5555"

        # Set pharmacy info
        member_profile.dosespot = {
            "global_pharmacy": {"pharmacy_id": 1, "pharmacy_info": valid_pharmacy}
        }

        # Enable RX for organization if applicable
        if appointment.member.organization:
            appointment.member.organization.rx_enabled = True

    return enable_appointment_rx_func


@pytest.fixture
def datetime_now():
    return datetime.datetime.utcnow().replace(microsecond=0)


@pytest.fixture
def datetime_now_iso_format(datetime_now):
    return datetime_now.isoformat()


@pytest.fixture
def frozen_now(datetime_now_iso_format):
    with freezegun.freeze_time(datetime_now_iso_format) as f:
        yield f


@pytest.fixture
def datetime_one_hour_earlier(datetime_now):
    return datetime_now - datetime.timedelta(hours=1)


@pytest.fixture
def datetime_one_hour_earlier_iso_format(datetime_one_hour_earlier):
    return datetime_one_hour_earlier.isoformat()


@pytest.fixture
def frozen_one_hour_earlier(datetime_one_hour_earlier_iso_format):
    with freezegun.freeze_time(datetime_one_hour_earlier_iso_format) as f:
        yield f


@pytest.fixture
def datetime_one_hour_later(datetime_now):
    return datetime_now + datetime.timedelta(hours=1)


@pytest.fixture
def datetime_one_hour_later_iso_format(datetime_one_hour_later):
    return datetime_one_hour_later.isoformat()


@pytest.fixture
def frozen_one_hour_later(datetime_one_hour_later_iso_format):
    with freezegun.freeze_time(datetime_one_hour_later_iso_format) as f:
        yield f


@pytest.fixture
def simple_post_session_data():
    return {"post_session": {"notes": "test123", "draft": True}}


@pytest.fixture
def simple_post_session_data_with_provider_and_member():
    return {"post_session": {"notes": "test123", "draft": True}, " ": ""}


@pytest.fixture
def cancellation_data(datetime_now_iso_format):
    return {"cancelled_at": datetime_now_iso_format}


@pytest.fixture
def get_minimal_appointments_from_endpoint(client, api_helpers):
    """Gets minimal appointments schema from the endpoint."""

    def get_minimal_appointments_from_endpoint_func(user):
        return client.get(
            "/api/v1/appointments?minimal=true",
            headers=api_helpers.json_headers(user=user),
            data=json.dumps({}),
        )

    return get_minimal_appointments_from_endpoint_func


@pytest.fixture
def get_appointment_from_endpoint(client, api_helpers):
    """Gets appointment information from the endpoint"""

    def get_appointment_from_endpoint_func(api_id, user):
        return client.get(
            f"/api/v1/appointments/{api_id}",
            headers=api_helpers.json_headers(user=user),
        )

    return get_appointment_from_endpoint_func


@pytest.fixture
def get_appointment_from_endpoint_using_appointment(get_appointment_from_endpoint):
    """Gets appointment information from the endpoint"""

    def get_appointment_from_endpoint_using_appointment_func(appointment):
        return get_appointment_from_endpoint(
            api_id=appointment.api_id,
            user=appointment.practitioner,
        )

    return get_appointment_from_endpoint_using_appointment_func


@pytest.fixture
def get_appointment_from_endpoint_using_appointment_user_member(
    get_appointment_from_endpoint,
):
    """Gets appointment information from the endpoint"""

    def get_appointment_from_endpoint_using_appointment_func(appointment):
        return get_appointment_from_endpoint(
            api_id=appointment.api_id,
            user=appointment.member,
        )

    return get_appointment_from_endpoint_using_appointment_func


@pytest.fixture
def put_appointment_on_endpoint(client, api_helpers):
    def put_appointment_on_endpoint_func(api_id, user, data_json_string):
        return client.put(
            f"/api/v1/appointments/{api_id}",
            headers=api_helpers.json_headers(user=user),
            data=data_json_string,
        )

    return put_appointment_on_endpoint_func


@pytest.fixture
def put_appointment_on_endpoint_using_appointment(put_appointment_on_endpoint):
    def put_appointment_on_endpoint_using_appointment_func(
        appointment, data_json_string, appointment_user
    ):
        return put_appointment_on_endpoint(
            api_id=appointment.api_id,
            user=appointment_user,
            data_json_string=data_json_string,
        )

    return put_appointment_on_endpoint_using_appointment_func


@pytest.fixture
def put_appointment_post_session_on_endpoint(
    put_appointment_on_endpoint_using_appointment,
):
    """PUTs a post session note on an appointment via the endpoint"""

    def put_appointment_post_session_on_endpoint_func(
        appointment,
        post_session_note,
        is_draft,
    ):
        # Create the data structure for the post session note
        post_session_data = {
            "id": appointment.api_id,
            "post_session": {
                "notes": post_session_note,
                "draft": is_draft,
            },
        }

        # PUT the post session note on the appointment
        return put_appointment_on_endpoint_using_appointment(
            appointment=appointment,
            data_json_string=json.dumps(post_session_data),
            appointment_user=appointment.practitioner,
        )

    return put_appointment_post_session_on_endpoint_func


@pytest.fixture
def patch_appointment_on_endpoint(client, api_helpers):
    def patch_appointment_on_endpoint_func(api_id, user, data_json_string):
        return client.patch(
            f"/api/v1/appointments/{api_id}",
            headers=api_helpers.json_headers(user=user),
            data=data_json_string,
        )

    return patch_appointment_on_endpoint_func


@pytest.fixture
def patch_appointment_on_endpoint_using_appointment(patch_appointment_on_endpoint):
    def patch_appointment_on_endpoint_using_appointment_func(
        appointment, data_json_string, appointment_user
    ):
        return patch_appointment_on_endpoint(
            api_id=appointment.api_id,
            user=appointment_user,
            data_json_string=data_json_string,
        )

    return patch_appointment_on_endpoint_using_appointment_func


@pytest.fixture
def patch_reschedule_appointment_on_endpoint(client, api_helpers):
    def patch_reschedule_appointment_on_endpoint_func(api_id, user, data_json_string):
        return client.patch(
            f"/api/v1/appointments/{api_id}/reschedule",
            headers=api_helpers.json_headers(user=user),
            data=data_json_string,
        )

    return patch_reschedule_appointment_on_endpoint_func


def _is_subset(subset, superset):
    if isinstance(subset, dict):
        return all(
            key in superset and _is_subset(val, superset[key])
            for key, val in subset.items()
        )

    if isinstance(subset, (list, set)):
        return all(
            any(_is_subset(subitem, superitem) for superitem in superset)
            for subitem in subset
        )

    # assume that subset is a plain value if none of the above match
    return subset == superset


@pytest.fixture
def assert_successful_http_update():
    def assert_successful_http_update_func(update_result, expected_data):
        assert update_result.status_code == HTTPStatus.OK
        # Assert the expected data is in the result
        assert _is_subset(expected_data, update_result.json)

    return assert_successful_http_update_func


@pytest.fixture
def assert_successful_http_appointment_cancellation(db):
    def assert_successful_http_appointment_cancellation_func(
        cancellation_result, appointment, expected_user, expected_note=None
    ):
        # Assert the cancellation succeeded
        assert cancellation_result.status_code == HTTPStatus.OK

        # Remove the appointment from the db cache to prevent lazy loading.
        db.session.expire(appointment)

        # Get a fresh copy of the appointment
        appt = Appointment.query.get(appointment.id)
        # Assert that the appointment was cancelled
        assert appt.state == APPOINTMENT_STATES.cancelled
        # Assert that the appointment was cancelled by the member
        assert appt.cancelled_by is expected_user
        # Assert note is set
        if expected_note:
            assert appt.cancelled_note == expected_note

    return assert_successful_http_appointment_cancellation_func


@pytest.fixture
def assert_cancellation_survey():
    def assert_cancellation_survey(cancellation_response, has_cancellation_survey):
        if has_cancellation_survey:
            assert cancellation_response.json.get("surveys") is not None
            cancellation_survey = cancellation_response.json.get("surveys").get(
                "cancellation_survey"
            )
            assert cancellation_survey is not None
            # Test DB doesn't have questionnaires data, so we could only check if
            # the key exists in the "cancellation_survey" dictionary
            # TODO: use factory to create cancellation survey data
            assert "questionnaires" in cancellation_survey.keys()
            assert "recorded_answers" in cancellation_survey.keys()
        else:
            assert cancellation_response.json.get("surveys") == {}

    return assert_cancellation_survey


@pytest.fixture
def setup_post_appointment_test(
    factories,
    practitioner_user,
    member_with_add_appointment,
):
    """Setup function for post appointment tests"""

    def setup_post_appointment_test_func():
        practitioner = practitioner_user()
        schedule_start = now.replace(microsecond=0)

        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=schedule_start,
            ends_at=now + datetime.timedelta(minutes=500),
        )

        product = practitioner.products[0]

        member = member_with_add_appointment
        factories.ScheduleFactory.create(user=member)

        start = schedule_start + datetime.timedelta(minutes=20)
        data = {"product_id": product.id, "scheduled_start": start.isoformat()}
        return AppointmentSetupValues(
            member=member, product=product, data=data, practitioner=practitioner
        )

    return setup_post_appointment_test_func


@pytest.fixture
def setup_post_appointment_state_check(
    factories,
    setup_post_appointment_test,
    create_state,
):
    """Setup function for post appointment state check tests"""

    def setup_post_appointment_state_check_func():
        appointment_setup_values = setup_post_appointment_test()

        member = appointment_setup_values.member
        product = appointment_setup_values.product
        practitioner = appointment_setup_values.practitioner
        data = appointment_setup_values.data

        vertical = factories.VerticalFactory(name="Allergist", filter_by_state=True)
        state = create_state(name="New Jersey", abbreviation="NJ")

        profile = practitioner.practitioner_profile
        profile.verticals = [vertical]
        profile.certified_states = [state]

        return AppointmentSetupValues(
            member=member, product=product, data=data, practitioner=practitioner
        )

    return setup_post_appointment_state_check_func


@pytest.fixture
def setup_patch_reschedule_appointment_test(
    factories, datetime_now, member_with_reschedule_appointment
):
    """Setup function for patch reschedule appointment tests"""

    def setup_patch_reschedule_appointment_test_func(
        original_scheduled_start, new_scheduled_start_time, is_enterprise=True
    ):
        # Create a member user with the authentication permission
        member = member_with_reschedule_appointment
        member_schedule = factories.ScheduleFactory.create(user=member)
        product = ProductFactory.create()
        factories.ScheduleEventFactory.create(
            schedule=product.practitioner.schedule,
            starts_at=original_scheduled_start,
            ends_at=now + datetime.timedelta(hours=1),
        )
        factories.ScheduleEventFactory.create(
            schedule=product.practitioner.schedule,
            starts_at=new_scheduled_start_time,
            ends_at=now + datetime.timedelta(hours=1),
        )
        appointment = AppointmentFactory.create(
            created_at=datetime_now,
            product=product,
            scheduled_start=original_scheduled_start,
            member_started_at=None,
            practitioner_started_at=None,
            is_enterprise_factory=is_enterprise,
            member_ended_at=None,
            practitioner_ended_at=None,
            member_schedule=member_schedule,
        )
        reschedule_appointment_request = {
            "scheduled_start": new_scheduled_start_time,
            "product_id": appointment.product_id,
        }

        return PATCH_RESCHEDULE_APPOINTMENT_SETUP_VALUES(
            member=member,
            product=product,
            reschedule_appointment_request=reschedule_appointment_request,
            appointment=appointment,
        )

    return setup_patch_reschedule_appointment_test_func


@pytest.fixture
def schedule_recurring_block_events(factories):
    def _create_schedule_recurring_blocks_events(practitioner, starts_at):
        recurring_block = factories.ScheduleRecurringBlockFactory.create(
            schedule=practitioner.schedule,
            starts_at=round_to_nearest_minutes(starts_at),
            ends_at=round_to_nearest_minutes(starts_at) + datetime.timedelta(hours=2),
            until=round_to_nearest_minutes(starts_at) + datetime.timedelta(weeks=1),
        )
        factories.ScheduleRecurringBlockWeekdayIndexFactory.create(
            schedule_recurring_block=recurring_block,
        )
        factories.ScheduleRecurringBlockWeekdayIndexFactory.create(
            schedule_recurring_block=recurring_block,
            week_days_index=3,
        )
        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=round_to_nearest_minutes(starts_at),
            ends_at=round_to_nearest_minutes(starts_at) + datetime.timedelta(hours=2),
            schedule_recurring_block_id=recurring_block.id,
        )
        return recurring_block

    return _create_schedule_recurring_blocks_events


@pytest.fixture
def create_schedule_event(factories):
    def _create_schedule_event(practitioner, start_time, num_availabilities):
        # round the start time to the nearest 10 minutes like the front end does
        start_time = round_to_nearest_minutes(start_time)
        end_time = start_time + datetime.timedelta(
            minutes=practitioner.products[0].minutes * num_availabilities
        )
        return factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=start_time,
            ends_at=end_time,
        )

    def make_create_schedule_event(
        practitioner,
        start_time=datetime.datetime.now(),  # noqa  B008
        num_availabilities=3,
    ):
        return _create_schedule_event(practitioner, start_time, num_availabilities)

    return make_create_schedule_event


@pytest.fixture
def add_schedule_event(factories):
    def _add_schedule_event(
        practitioner: User,
        starts_at: datetime.datetime,
        num_slots: int,
        product: Product = None,
    ) -> ScheduleEvent:
        if not product:
            product = practitioner.default_product

        # Add booking buffer, with a few extra minutes to avoid any edge cases around timing.
        starts_at += datetime.timedelta(minutes=practitioner.profile.booking_buffer)

        # Round the starting time according to rounding_minutes
        starts_at += datetime.timedelta(minutes=practitioner.profile.rounding_minutes)
        starts_at -= (
            datetime.timedelta(
                minutes=(starts_at.minute % practitioner.profile.rounding_minutes)
            )
            + datetime.timedelta(seconds=starts_at.second)
            + datetime.timedelta(microseconds=starts_at.microsecond)
        )

        available_duration = num_slots * product.minutes
        if product.minutes % practitioner.profile.rounding_minutes != 0:
            additional = practitioner.profile.rounding_minutes - (
                product.minutes % practitioner.profile.rounding_minutes
            )
            available_duration += (num_slots - 1) * additional

        return factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=starts_at,
            ends_at=starts_at + datetime.timedelta(minutes=available_duration),
        )

    return _add_schedule_event


@pytest.fixture(autouse=True, scope="function")
def flush_redis():
    # dont allow cached values to persist between tests
    redis_client().flushall()
    yield


@pytest.fixture
def mock_schedule_recurring_block_repo():
    with mock.patch(
        "appointments.repository.schedules.ScheduleRecurringBlockRepository",
    ) as m:
        yield m


@pytest.fixture
def mock_schedule_event_repo():
    with mock.patch(
        "appointments.repository.schedules.ScheduleEventRepository",
    ) as m:
        yield m


@pytest.fixture
def recurring_schedule_service(
    mock_schedule_recurring_block_repo,
    mock_schedule_event_repo,
):
    return RecurringScheduleAvailabilityService(
        schedule_recurring_block_repo=mock_schedule_recurring_block_repo,
        schedule_event_repo=mock_schedule_event_repo,
    )


@pytest.fixture
def schedule_repo(session) -> ScheduleRecurringBlockRepository:
    return ScheduleRecurringBlockRepository(session=session)


@pytest.fixture
def schedule_event_repo(session) -> ScheduleEventRepository:
    return ScheduleEventRepository(session=session)


@pytest.fixture
def schedule(factories):
    return factories.ScheduleFactory.create()


@pytest.fixture
def search_api_8_hits():
    return search_api_response_8_hits_obj


@pytest.fixture
def practitioner_and_contract(factories, practitioner_user):
    contract = PractitionerContractFactory.create(
        practitioner=practitioner_user().practitioner_profile,
        contract_type=ContractType.FIXED_HOURLY,
    )
    return practitioner_user(), contract


@pytest.fixture
def patch_authorize_payment():
    with patch.object(
        StripeCustomerClient, "capture_charge", return_value=captured_charge
    ), patch.object(
        StripeCustomerClient, "create_charge", return_value=uncaptured_payment
    ), patch.object(
        StripeCustomerClient, "list_cards", return_value=one_card_list
    ):
        yield


@pytest.fixture
def patch_refund_payment():
    with patch.object(
        StripeCustomerClient, "refund_charge", return_value=captured_charge
    ):
        yield
