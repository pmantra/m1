from unittest import mock

import pytest
import requests

from direct_payment.notification.errors import NotificationServiceError
from direct_payment.notification.models import (
    EventName,
    EventSourceSystem,
    NotificationPayload,
    NotificationStatus,
    NotificationStatusObject,
    UserIdType,
    UserType,
)
from direct_payment.notification.notification_service import NotificationService


@pytest.fixture
def mock_response():
    def fn(response_code):
        res = None
        if response_code is not None:
            res = requests.Response()
            res.status_code = 200
        return res

    return fn


class TestNotificationService:
    @pytest.mark.parametrize(
        argvalues=(
            (
                {
                    "user_id_type": UserIdType.WALLET_ID.value,
                    "user_type": UserType.MEMBER.value,
                    "event_source_system": EventSourceSystem.WALLET.value,
                    "notification_event_payload": {
                        "event_name": EventName.MMB_WALLET_QUALIFIED,
                        "event_properties": {"program_overview_link": "a"},
                    },
                },
                200,
                NotificationStatus.BRAZE_SUCCESS,
            ),
            (
                {
                    "user_id_type": UserIdType.PAYOR_ID.value,
                    "user_type": UserType.MEMBER.value,
                    "event_source_system": EventSourceSystem.BILLING.value,
                    "notification_event_payload": {
                        "event_name": EventName.MMB_UPCOMING_PAYMENT_REMINDER,
                        "event_properties": {
                            "benefit_id": "123",
                            "payment_amount": "10000",
                            "payment_date": "11/25/2023",
                            "payment_method_last4": "1234",
                            "payment_method_type": "card",
                            "clinic_name": "",
                            "clinic_location": "",
                        },
                    },
                },
                None,
                NotificationStatus.BRAZE_FAILURE,
            ),
        ),
        argnames="input_payload_dict, response_code, expected_status",
    )
    def test_send_notification_from_payload(
        self,
        notified_user,
        notified_user_wallet,
        mock_response,
        input_payload_dict,
        response_code,
        expected_status,
    ):
        wallet = notified_user_wallet(notified_user)
        input_payload_dict["user_id"] = str(
            wallet.id
        )  # same value for bills and wallets
        payload = NotificationPayload.create_from_dict(input_payload_dict)
        service = NotificationService()
        with mock.patch("braze.client.BrazeClient._make_request") as br:
            mocked_response = mock_response(response_code)
            br.return_value = mocked_response
            res = service.send_notification_event_from_payload(payload)
        expected = {
            notified_user.esp_id: NotificationStatusObject(
                expected_status, mocked_response, None
            )
        }
        assert res == expected

    @pytest.mark.parametrize(
        argvalues=([0, UserType.EMPLOYER.value], [1, UserType.MEMBER.value]),
        argnames="offset, user_type",
        ids=[
            "1. Employer type not currently supported",
            "2. User not found",
        ],
    )
    def test_send_notification_from_payload_failure(
        self, notified_user, notified_user_wallet, offset, user_type
    ):
        wallet = notified_user_wallet(notified_user)
        input_payload_dict = {
            "user_id": str(wallet.id + offset),
            "user_id_type": UserIdType.WALLET_ID.value,
            "user_type": user_type,
            "event_source_system": EventSourceSystem.WALLET.value,
            "notification_event_payload": {
                "event_name": EventName.MMB_WALLET_QUALIFIED,
                "event_properties": {"program_overview_link": "a"},
            },
        }

        payload = NotificationPayload.create_from_dict(input_payload_dict)
        with pytest.raises(NotificationServiceError):
            _ = NotificationService().send_notification_event_from_payload(payload)

    @pytest.mark.parametrize(
        argvalues=(
            (
                UserIdType.WALLET_ID,
                UserType.MEMBER,
                EventSourceSystem.WALLET,
                EventName.MMB_WALLET_QUALIFIED,
                {"program_overview_link": "a"},
                200,
                NotificationStatus.BRAZE_SUCCESS,
            ),
            (
                UserIdType.PAYOR_ID,
                UserType.MEMBER,
                EventSourceSystem.BILLING,
                EventName.MMB_UPCOMING_PAYMENT_REMINDER,
                {
                    "benefit_id": "123",
                    "payment_amount": "10000",
                    "payment_date": "11/25/2023",
                    "payment_method_last4": "1234",
                    "payment_method_type": "card",
                    "clinic_name": "",
                    "clinic_location": "",
                },
                200,
                NotificationStatus.BRAZE_SUCCESS,
            ),
            (
                UserIdType.WALLET_ID,
                UserType.MEMBER,
                EventSourceSystem.WALLET,
                EventName.MMB_WALLET_QUALIFIED,
                {"program_overview_link": "a"},
                None,
                NotificationStatus.BRAZE_FAILURE,
            ),
            (
                UserIdType.PAYOR_ID,
                UserType.MEMBER,
                EventSourceSystem.BILLING,
                EventName.MMB_UPCOMING_PAYMENT_REMINDER,
                {
                    "benefit_id": "123",
                    "payment_amount": "10000",
                    "payment_date": "11/25/2023",
                    "payment_method_last4": "1234",
                    "payment_method_type": "card",
                    "clinic_name": "",
                    "clinic_location": "",
                },
                None,
                NotificationStatus.BRAZE_FAILURE,
            ),
        ),
        argnames="user_id_type, user_type, event_source_system, event_name,event_properties, response_code, "
        "expected_status",
        ids=[
            "1. Wallet event success.",
            "2. Billing Event success.",
            "3. Wallet event failure.",
            "4. Billing Event failure.",
        ],
    )
    def test_send_notification(
        self,
        notified_user,
        notified_user_wallet,
        mock_response,
        user_id_type,
        user_type,
        event_source_system,
        event_name,
        event_properties,
        response_code,
        expected_status,
    ):
        wallet = notified_user_wallet(notified_user)
        with mock.patch("braze.client.BrazeClient._make_request") as br:
            mocked_response = mock_response(response_code)
            br.return_value = mocked_response
            res = NotificationService().send_notification_event(
                user_id=str(wallet.id),
                user_id_type=user_id_type,
                user_type=user_type,
                event_source_system=event_source_system,
                event_name=event_name,
                event_properties=event_properties,
            )

        expected = {
            notified_user.esp_id: NotificationStatusObject(
                expected_status, mocked_response, None
            )
        }
        assert res == expected

    @pytest.mark.parametrize(
        argvalues=(
            [0, UserType.EMPLOYER.value],
            [1, UserType.MEMBER.value],
        ),
        argnames="offset, user_type",
        ids=[
            "1. Employer type not currently supported",
            "2. User not found",
        ],
    )
    def test_send_notification_failure(
        self,
        notified_user,
        notified_user_wallet,
        offset,
        user_type,
    ):
        wallet = notified_user_wallet(notified_user)
        with pytest.raises(NotificationServiceError):
            _ = NotificationService().send_notification_event(
                user_id=(wallet.id + offset),
                user_id_type=UserIdType.WALLET_ID.value,
                user_type=user_type,
                event_source_system=EventSourceSystem.WALLET.value,
                event_name=EventName.MMB_WALLET_QUALIFIED.value,
                event_properties={"program_overview_link": "a"},
            )
