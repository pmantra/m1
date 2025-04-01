import http
import json
import os
import urllib
from datetime import datetime, timedelta, timezone
from unittest import mock
from urllib.parse import quote

import pytest
from sqlalchemy import insert

from appointments.models.needs_and_categories import need_need_category
from appointments.services.v2.member_appointment import MemberAppointmentService
from l10n.config import CUSTOM_LOCALE_HEADER
from messaging.resources.deflection import HEADER_KEY_ZENDESKSC_API_KEY
from pytests import factories
from storage.connection import db
from views.search import SearchResult


@pytest.fixture(autouse=True)
def zendesksc_api_key():
    secret_key = "some_key"
    with mock.patch.dict(
        os.environ,
        values={
            "ZENDESKSC_API_SECRET_KEY_PRIMARY": secret_key,
        },
    ):
        yield secret_key


@pytest.fixture
def appointment(enterprise_user):
    member_schedule = factories.ScheduleFactory.create(user=enterprise_user)
    provider = factories.PractitionerUserFactory.create()
    return factories.AppointmentFactory.create_with_practitioner(
        scheduled_start=datetime.now(tz=timezone.utc) + timedelta(days=1),
        member_schedule=member_schedule,
        practitioner=provider,
    )


@pytest.mark.parametrize(
    "path",
    [
        "/member_context",
    ],
)
def test_deflection_api_key_authorization_no_key(
    client,
    path,
):

    res = client.get(
        f"/api/v1/_/vendor/zendesksc/deflection{path}",
    )
    assert res.status_code == http.HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(
    "path",
    [
        "/member_context",
    ],
)
def test_deflection_api_key_authorization_invalid_key(
    client,
    path,
):

    res = client.get(
        f"/api/v1/_/vendor/zendesksc/deflection{path}",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: "invalid_value"},
    )
    assert res.status_code == http.HTTPStatus.FORBIDDEN


def test_deflection_user_context_not_found(
    zendesksc_api_key,
    client,
):

    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/member_context?member_id=999999",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    assert res.status_code == http.HTTPStatus.NOT_FOUND


def test_deflection_member_context_no_member_profile(
    zendesksc_api_key,
    client,
    default_user,
):
    member = default_user
    res = client.get(
        f"/api/v1/_/vendor/zendesksc/deflection/member_context?member_id={member.id}",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    assert res.status_code == http.HTTPStatus.BAD_REQUEST


@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_deflection_member_context_doula_only_member(
    _,
    zendesksc_api_key,
    client,
    create_doula_only_member,
):
    member = create_doula_only_member
    res = client.get(
        f"/api/v1/_/vendor/zendesksc/deflection/member_context?member_id={member.id}",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    assert res.status_code == http.HTTPStatus.OK
    data = res.json

    assert data["member_id"] == member.id
    assert data["is_doula_only_member"] is True
    assert data["active_track_ids"] == [member.active_tracks[0].id]
    assert data["active_track_names"] == [member.active_tracks[0].name]
    assert data["member_state"] == member.member_profile.state.abbreviation


def test_deflection_track_categories__missing_member(
    client,
    zendesksc_api_key,
):
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/track_categories",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    assert res.status_code == http.HTTPStatus.BAD_REQUEST
    assert "member_id is required" in res.text


def test_deflection_track_categories__member_not_found(
    client,
    zendesksc_api_key,
):
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/track_categories?member_id=000",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    assert res.status_code == http.HTTPStatus.NOT_FOUND
    assert "user not found" in res.text


def test_deflection_track_categories__missing_api_key(
    client,
    enterprise_user,
):
    member = enterprise_user
    res = client.get(
        f"/api/v1/_/vendor/zendesksc/deflection/track_categories?member_id={member.id}",
    )

    assert res.status_code == http.HTTPStatus.UNAUTHORIZED


def test_deflection_track_categories(
    client,
    enterprise_user,
    zendesksc_api_key,
):
    member = enterprise_user
    res = client.get(
        f"/api/v1/_/vendor/zendesksc/deflection/track_categories?member_id={member.id}",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    assert res.status_code == http.HTTPStatus.OK
    data = res.json

    assert data["member_id"] == member.id
    assert data["need_categories"] is not None


def test_deflection_category_needs__missing_category(
    client,
    zendesksc_api_key,
):
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/category_needs",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    assert res.status_code == http.HTTPStatus.BAD_REQUEST
    assert "category_name is required" in res.text


def test_deflection_category_needs__category_not_found(
    client,
    zendesksc_api_key,
):
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/category_needs?category_name=test",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    assert res.status_code == http.HTTPStatus.NOT_FOUND
    assert "category not found" in res.text


def test_deflection_category_needs(
    client,
    factories,
    zendesksc_api_key,
):
    category = factories.NeedCategoryFactory.create()
    need = factories.NeedFactory.create()
    stmt = insert(need_need_category).values(category_id=category.id, need_id=need.id)
    db.session.execute(stmt)
    db.session.commit()

    res = client.get(
        f"/api/v1/_/vendor/zendesksc/deflection/category_needs?category_name={quote(category.name)}",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    data = res.json
    assert data["needs"] != []


def test_deflection_upcoming_appointments(
    zendesksc_api_key,
    client,
    appointment,
):
    member = appointment.member_schedule.user
    res = client.get(
        f"/api/v1/_/vendor/zendesksc/deflection/upcoming_appointments?member_id={member.id}",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    assert res.status_code == http.HTTPStatus.OK

    data = res.json

    appointments = data["appointments"]
    assert len(appointments) == 1
    assert appointments[0]["id"] == appointment.id


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"member_id": 123},
        {"appointment_id": 456},
    ],
)
def test_deflection_cancel_appointment_invalid_request(
    zendesksc_api_key,
    client,
    appointment,
    body,
):
    res = client.post(
        "/api/v1/_/vendor/zendesksc/deflection/cancel_appointment",
        data=json.dumps(body),
        headers={
            HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key,
            "Content-type": "application/json",
        },
    )

    assert res.status_code == http.HTTPStatus.BAD_REQUEST
    data = res.json
    assert data["errors"] is not None


def test_deflection_cancel_appointment(
    zendesksc_api_key,
    client,
    appointment,
):
    member = appointment.member_schedule.user
    body = {
        "member_id": member.id,
        "appointment_id": appointment.id,
    }

    res = client.post(
        "/api/v1/_/vendor/zendesksc/deflection/cancel_appointment",
        data=json.dumps(body),
        headers={
            HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key,
            "Content-type": "application/json",
        },
    )
    assert res.status_code == http.HTTPStatus.OK

    cancelled_appointment = MemberAppointmentService().get_member_appointment_by_id(
        user=member,
        appointment_id=appointment.id,
        skip_check_permissions=True,
    )

    assert cancelled_appointment.cancelled_at is not None


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"member_id": 123},
        {"query": "omg"},
    ],
)
def test_deflection_resource_search_invalid_request(
    zendesksc_api_key,
    client,
    params,
):

    encoded_params = urllib.parse.urlencode(params)
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/resource_search?" + encoded_params,
        headers={
            HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key,
        },
    )

    assert res.status_code == http.HTTPStatus.BAD_REQUEST
    data = res.json
    assert data["errors"] is not None


@mock.patch(
    "messaging.resources.deflection.perform_search", return_value=SearchResult()
)
def test_deflection_resource_search(
    mock_perform_search,
    zendesksc_api_key,
    client,
    default_user,
):
    given_search_query = "some query"
    params = {
        "member_id": default_user.id,
        "query": given_search_query,
    }

    encoded_params = urllib.parse.urlencode(params)
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/resource_search?" + encoded_params,
        headers={
            HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key,
        },
    )
    assert res.status_code == http.HTTPStatus.OK
    mock_perform_search.assert_called_once_with(
        "resources",
        given_search_query,
        default_user.current_member_track,
    )


def test_deflection_provider_search__missing_member(
    client,
    zendesksc_api_key,
):
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/provider_search",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    assert res.status_code == http.HTTPStatus.BAD_REQUEST
    assert "member_id is required" in res.text


def test_deflection_provider_search__missing_parameters(
    client,
    zendesksc_api_key,
    enterprise_user,
):
    member = enterprise_user
    res = client.get(
        f"/api/v1/_/vendor/zendesksc/deflection/provider_search?member_id={member.id}",
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )
    # we expect an empty list of providers when no parameters are provided
    assert res.status_code == http.HTTPStatus.OK
    assert res.json["providers"] == []


def test_deflection_provider_search__need_category_not_found(
    client,
    zendesksc_api_key,
    enterprise_user,
):
    member = enterprise_user
    encoded_params = urllib.parse.urlencode(
        {
            "member_id": member.id,
            "need_category": "test",
        }
    )
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/provider_search?" + encoded_params,
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    # we dont expect any providers to be returned when the category is not found
    # which leaves us with no search criteria
    assert res.status_code == http.HTTPStatus.OK
    assert res.json["providers"] == []


@mock.patch("providers.service.provider.ProviderService.search")
def test_deflection_provider_search__need_category(
    mock_provider_search, client, factories, zendesksc_api_key, enterprise_user
):
    member = enterprise_user

    provider = factories.PractitionerUserFactory.create()
    mock_provider_search.return_value = [[provider], 1]

    category = factories.NeedCategoryFactory.create()
    need = factories.NeedFactory.create()
    stmt = insert(need_need_category).values(category_id=category.id, need_id=need.id)
    db.session.execute(stmt)
    db.session.commit()

    encoded_params = urllib.parse.urlencode(
        {
            "member_id": member.id,
            "need_category": category.name,
        }
    )
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/provider_search?" + encoded_params,
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    mock_provider_search.assert_called_with(
        current_user=member,
        verticals=None,
        vertical_ids=None,
        needs=None,
        need_ids=[need.id],
        limit=7,
        offset=0,
    )
    assert res.status_code == http.HTTPStatus.OK
    res_data = json.loads(res.data)
    assert res_data["providers"][0]["id"] == provider.id
    assert (
        f"app/book-practitioner/{provider.id}"
        in res_data["providers"][0]["booking_url"]
    )


def test_deflection_provider_search__vertical_name(
    client, factories, zendesksc_api_key, enterprise_user
):
    member = enterprise_user
    provider = factories.PractitionerUserFactory.create()
    vertical = provider.practitioner_profile.verticals[0]

    encoded_params = urllib.parse.urlencode(
        {
            "member_id": member.id,
            "vertical": vertical.name,
        }
    )
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/provider_search?" + encoded_params,
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    assert res.status_code == http.HTTPStatus.OK
    res_data = json.loads(res.data)
    assert res_data["providers"] is not None

    returned_provider_ids = [provider["id"] for provider in res_data["providers"]]
    assert provider.id in returned_provider_ids
    assert "app/book-practitioner/" in res_data["providers"][0]["booking_url"]


@mock.patch("providers.service.provider.ProviderService.search")
def test_deflection_provider_search__need_category_and_vertical(
    mock_provider_search, client, factories, zendesksc_api_key, enterprise_user
):
    member = enterprise_user

    provider = factories.PractitionerUserFactory.create()
    vertical = provider.practitioner_profile.verticals[0]
    mock_provider_search.return_value = [[provider], 1]

    category = factories.NeedCategoryFactory.create()
    need = factories.NeedFactory.create()
    stmt = insert(need_need_category).values(category_id=category.id, need_id=need.id)
    db.session.execute(stmt)

    category_2 = factories.NeedCategoryFactory.create()
    need_2 = factories.NeedFactory.create()
    stmt_2 = insert(need_need_category).values(
        category_id=category_2.id,
        need_id=need_2.id,
    )
    db.session.execute(stmt_2)

    db.session.commit()

    encoded_params = urllib.parse.urlencode(
        {
            "member_id": member.id,
            "need_category": category.name,
            "need_category_id": category_2.id,
            "vertical": vertical.name,
        }
    )
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/provider_search?" + encoded_params,
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    mock_provider_search.assert_called_with(
        current_user=member,
        verticals=[vertical.name],
        vertical_ids=None,
        needs=None,
        need_ids=[
            need_2.id,
            need.id,
        ],
        limit=7,
        offset=0,
    )
    assert res.status_code == http.HTTPStatus.OK
    res_data = json.loads(res.data)
    assert res_data["providers"] is not None

    returned_provider_ids = [provider["id"] for provider in res_data["providers"]]
    assert provider.id in returned_provider_ids
    assert "app/book-practitioner/" in res_data["providers"][0]["booking_url"]


@mock.patch("providers.service.provider.ProviderService.search")
def test_deflection_provider_search__need(
    mock_provider_search, client, factories, zendesksc_api_key, enterprise_user
):
    member = enterprise_user

    provider = factories.PractitionerUserFactory.create()
    mock_provider_search.return_value = [[provider], 1]
    need = factories.NeedFactory.create()

    encoded_params = urllib.parse.urlencode(
        {
            "member_id": member.id,
            "need": need.name,
        }
    )
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/provider_search?" + encoded_params,
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )

    mock_provider_search.assert_called_with(
        current_user=member,
        verticals=None,
        vertical_ids=None,
        needs=[need.name],
        need_ids=None,
        limit=7,
        offset=0,
    )
    assert res.status_code == http.HTTPStatus.OK
    res_data = json.loads(res.data)
    assert res_data["providers"][0]["id"] == provider.id
    assert (
        f"app/book-practitioner/{provider.id}"
        in res_data["providers"][0]["booking_url"]
    )


@mock.patch("providers.service.provider.ProviderService.search")
def test_deflection_provider_search__omit_provider_id(
    mock_provider_search, client, factories, zendesksc_api_key, enterprise_user
):
    member = enterprise_user

    provider = factories.PractitionerUserFactory.create()
    vertical = provider.practitioner_profile.verticals[0]
    mock_provider_search.return_value = [[provider], 1]

    encoded_params = urllib.parse.urlencode(
        {
            "member_id": member.id,
            "vertical": vertical.name,
        }
    )
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/provider_search?" + encoded_params,
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )
    assert res.status_code == http.HTTPStatus.OK
    res_data = json.loads(res.data)
    assert res_data["providers"][0]["id"] == provider.id

    # filter out the provider we previously saw in the response
    encoded_params = urllib.parse.urlencode(
        {
            "member_id": member.id,
            "vertical": vertical.name,
            "omit_provider_id": provider.id,
        }
    )
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/provider_search?" + encoded_params,
        headers={HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key},
    )
    assert res.status_code == http.HTTPStatus.OK
    res_data = json.loads(res.data)
    assert res_data["providers"] == []


@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
@mock.patch(
    "appointments.resources.provider_profile.feature_flags.bool_variation",
    return_value=True,
)
@mock.patch("l10n.db_strings.translate.TranslateDBFields.get_translated_vertical")
def test_deflection_provider_search__with_locale(
    translate_mock,
    feature_flag,
    locale,
    client,
    factories,
    zendesksc_api_key,
    enterprise_user,
    release_mono_api_localization_on,
):
    localized_vertical = "test_translate"
    translate_mock.return_value = localized_vertical
    member = enterprise_user
    provider = factories.PractitionerUserFactory.create()
    vertical = provider.practitioner_profile.verticals[0]
    translate_mock.reset_mock()
    encoded_params = urllib.parse.urlencode(
        {
            "member_id": member.id,
            "vertical": vertical.name,
        }
    )
    res = client.get(
        "/api/v1/_/vendor/zendesksc/deflection/provider_search?" + encoded_params,
        headers={
            HEADER_KEY_ZENDESKSC_API_KEY: zendesksc_api_key,
            CUSTOM_LOCALE_HEADER: locale,
        },
    )

    assert translate_mock.called
    assert res.status_code == http.HTTPStatus.OK
    res_data = json.loads(res.data)
    assert res_data["providers"] is not None

    returned_provider_ids = [provider["id"] for provider in res_data["providers"]]
    assert provider.id in returned_provider_ids
    assert res_data["providers"][0]["vertical"] == localized_vertical
