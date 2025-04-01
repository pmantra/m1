import datetime
import os
from unittest import mock

import pytest

import configuration
from direct_payment.clinic.pytests.factories import FertilityClinicUserProfileFactory
from models.tracks import TrackName
from pytests.factories import DefaultUserFactory
from pytests.freezegun import freeze_time
from utils.braze_events import (
    FERTILITY_USER_RESET_PASSWORD_EXP_IN_SECONDS,
    NEW_FERTILITY_USER_PASSWORD_SET_EXP_IN_SECONDS,
    bms_travel_end_date,
    existing_fertility_user_password_reset,
    new_user_password_set,
    password_reset,
    reimbursement_request_created_new,
    reimbursement_request_updated_new_to_pending,
    track_auto_renewal,
    track_renewal,
)
from utils.rotatable_token import BRAZE_CONNECTED_EVENT_TOKEN
from wallet.models.constants import (
    MemberType,
    ReimbursementRequestState,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.pytests.factories import (
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)


@pytest.fixture
def patch_braze_request():
    with mock.patch("braze.client.BrazeClient._make_request") as br:
        yield br


@pytest.fixture
def patch_braze_connected_event_token(primary="foo"):
    with mock.patch.object(BRAZE_CONNECTED_EVENT_TOKEN, "primary", primary) as token:
        yield token


@pytest.fixture
def patch_braze_fertility_api_key():
    with mock.patch.dict(
        os.environ, {"BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY": "test"}
    ) as key:
        yield key


def test_bms_travel_end_date(default_user, patch_braze_request):
    travel_end_date = datetime.date(2025, 6, 20)

    bms_travel_end_date(default_user, travel_end_date)

    patch_braze_request.assert_called_once()

    travel_end_date_property = patch_braze_request.call_args[1]["data"]["events"][0][
        "properties"
    ]["travel_end_date"]
    assert travel_end_date_property == "2025-06-20T00:00:00"


def test_track_renewal(default_user, patch_braze_request):
    start_date = datetime.date(2025, 6, 20)

    track_renewal(
        user=default_user,
        track=TrackName.ADOPTION,
        start_date=start_date,
    )

    patch_braze_request.assert_called_once()

    start_date_property = patch_braze_request.call_args[1]["data"]["events"][0][
        "properties"
    ]["start_date"]
    assert start_date_property == "2025-06-20T00:00:00"

    track_property = patch_braze_request.call_args[1]["data"]["events"][0][
        "properties"
    ]["track"]
    assert track_property == TrackName.ADOPTION


def test_track_auto_renewal(default_user, patch_braze_request):
    start_date = datetime.date(2025, 6, 20)

    track_auto_renewal(
        user=default_user,
        track=TrackName.ADOPTION,
        start_date=start_date,
    )

    patch_braze_request.assert_called_once()

    start_date_property = patch_braze_request.call_args[1]["data"]["events"][0][
        "properties"
    ]["start_date"]
    assert start_date_property == "2025-06-20T00:00:00"

    track_property = patch_braze_request.call_args[1]["data"]["events"][0][
        "properties"
    ]["track"]
    assert track_property == TrackName.ADOPTION


def test_password_reset_non_fertility_clinic_user(
    client,
    api_helpers,
    default_user,
    patch_braze_request,
    patch_braze_connected_event_token,
):
    # Act
    password_reset(default_user)
    connected_event_token = patch_braze_request.call_args[1]["data"]["events"][0][
        "properties"
    ]["connected_event_token"].value
    res = client.get(
        f"/api/v1/vendor/braze/connected_event_properties/{connected_event_token}",
        headers=api_helpers.json_headers(user=default_user),
    )
    json = api_helpers.load_json(res)

    # Assert
    res.status_code = 200
    assert len(patch_braze_request.call_args) == 2
    config = configuration.get_api_config()
    assert config.common.base_url in json["password_reset_url"]


@pytest.mark.parametrize(
    ["type_of_event", "password_reset_route", "delay_in_hours"],
    [
        ("existing_fertility_user_password_reset", "reset_password", 6),
        ("existing_fertility_user_password_reset", "reset_password", 9),
        ("new_user_password_set", "activate-account", 20),
        ("new_user_password_set", "activate-account", 170),
    ],
    ids=[
        "password_reset_fertility_clinic_user",
        "password_reset_fertility_clinic_user_expired_token",
        "new_user_password_set_fertility_clinic_user",
        "new_user_password_set_fertility_clinic_user_expired_token",
    ],
)
@mock.patch("braze.client.constants.BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY", "test")
@mock.patch("utils.braze_events.FERTILITY_CLINIC_PORTAL_BASE_URL", "fertility")
@mock.patch("braze.client.BrazeClient", autospec=True)
def test_password_reset_fertility_clinic_user(
    patch_braze_client,
    client,
    api_helpers,
    default_user,
    patch_braze_request,
    patch_braze_connected_event_token,
    type_of_event,
    password_reset_route,
    delay_in_hours,
):
    # Arrange
    FertilityClinicUserProfileFactory.create(user_id=default_user.id)

    # Act
    max_permitted_delay = None
    if type_of_event == "existing_fertility_user_password_reset":
        max_permitted_delay = FERTILITY_USER_RESET_PASSWORD_EXP_IN_SECONDS / 3600
        existing_fertility_user_password_reset(default_user)
    elif type_of_event == "new_user_password_set":
        max_permitted_delay = NEW_FERTILITY_USER_PASSWORD_SET_EXP_IN_SECONDS / 3600
        new_user_password_set(default_user)
    connected_event_token = (
        patch_braze_client.method_calls[0][2]["events"][0]
        .properties["connected_event_token"]
        .value
    )

    with freeze_time(
        datetime.datetime.now() + datetime.timedelta(hours=delay_in_hours)
    ):
        res = client.get(
            f"/api/v1/vendor/braze/connected_event_properties/{connected_event_token}",
            headers=api_helpers.json_headers(user=default_user),
        )
        json = api_helpers.load_json(res)

    # Assert
    if delay_in_hours < max_permitted_delay:
        assert res.status_code == 200
        patch_braze_client.assert_called_once_with(api_key="test")
        assert "fertility" in json["password_reset_url"]
        assert password_reset_route in json["password_reset_url"]
    else:
        assert res.status_code == 401


@pytest.mark.parametrize(
    ["prev_state", "new_state", "has_been_created", "has_multiple_wallet_users"],
    [
        (None, ReimbursementRequestState.NEW.value, False, False),
        (None, ReimbursementRequestState.NEW.value, False, True),
        (
            ReimbursementRequestState.NEW.value,
            ReimbursementRequestState.PENDING.value,
            True,
            False,
        ),
        (
            ReimbursementRequestState.NEW.value,
            ReimbursementRequestState.PENDING.value,
            True,
            True,
        ),
    ],
    ids=[
        "reimbursement_request_created_new_single_wallet_user",
        "reimbursement_request_created_new_multi_wallet_users",
        "reimbursement_request_updated_new_to_pending_single_wallet_user",
        "reimbursement_request_updated_new_to_pending_multi_wallet_users",
    ],
)
def test_reimbursement_request_created_and_updated(
    enterprise_user,
    patch_braze_request,
    prev_state,
    new_state,
    has_been_created,
    has_multiple_wallet_users,
):
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
    )
    if has_multiple_wallet_users:
        active_user = DefaultUserFactory.create()
        ReimbursementWalletUsersFactory.create(
            user_id=active_user.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.DEPENDENT,
        )
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    _ = ReimbursementRequestFactory.create(
        wallet=wallet,
        category=category,
        amount=100000,
        state=ReimbursementRequestState.NEW,
    )

    maven_gold = MemberType.MAVEN_GOLD

    if not has_been_created:
        reimbursement_request_created_new(wallet, maven_gold)
    else:
        reimbursement_request_updated_new_to_pending(wallet, maven_gold)
    if has_multiple_wallet_users:
        assert patch_braze_request.call_count == 2
    else:
        patch_braze_request.assert_called_once()

    braze_req_properties: dict = patch_braze_request.call_args[1]["data"]["events"][0][
        "properties"
    ]

    assert braze_req_properties == {
        "member_type": "MAVEN_GOLD",
        "prev_state": prev_state,
        "new_state": new_state,
    }
