import pytest

from direct_payment.notification.errors import NotificationPayloadCreationError
from direct_payment.notification.models import (
    EventName,
    EventSourceSystem,
    MmbPaymentMethodAddedEventProperties,
    MmbWalletQualifiedEventProperties,
    NotificationEventPayload,
    NotificationPayload,
    UserIdType,
    UserType,
)


class TestModel:
    @pytest.mark.parametrize(
        argnames="input_dict, exp_user_type, exp_notification_event_payload",
        argvalues=(
            (
                {
                    "user_id": "ABC",
                    "user_id_type": "PAYOR_ID",
                    "user_type": "MEMBER",
                    "event_source_system": "WALLET",
                    "notification_event_payload": {
                        "event_name": "mmb_wallet_qualified",
                        "event_properties": {"program_overview_link": "www"},
                    },
                },
                UserType.MEMBER,
                NotificationEventPayload(
                    event_name=EventName("mmb_wallet_qualified"),
                    event_properties=MmbWalletQualifiedEventProperties(
                        **{"program_overview_link": "www"}
                    ),
                ),
            ),
            (
                {
                    "user_id": "ABC",
                    "user_id_type": "PAYOR_ID",
                    "user_type": None,
                    "event_source_system": "WALLET",
                    "notification_event_payload": {
                        "event_name": "mmb_payment_method_added",
                        "event_properties": {
                            "payment_method_last4": "1234",
                            "payment_method_type": "card",
                            "program_overview_link": "www",
                            "card_funding": "",
                        },
                    },
                },
                None,
                NotificationEventPayload(
                    event_name=EventName("mmb_payment_method_added"),
                    event_properties=MmbPaymentMethodAddedEventProperties(
                        **{
                            "payment_method_last4": "1234",
                            "payment_method_type": "card",
                            "program_overview_link": "www",
                            "card_funding": "",
                        }
                    ),
                ),
            ),
        ),
        ids=[
            "1. User type member in payload, single item in event properties.",
            "2. User type absent in payload, multiple items in event properties.",
        ],
    )
    def test_notification_event_creation(
        self, input_dict, exp_user_type, exp_notification_event_payload
    ):
        res = NotificationPayload.create_from_dict(input_dict)
        assert res.user_id == input_dict["user_id"]
        assert res.user_id_type == UserIdType(input_dict["user_id_type"])
        assert res.user_type == exp_user_type
        assert res.event_source_system == EventSourceSystem(
            input_dict["event_source_system"]
        )
        assert res.notification_event_payload == exp_notification_event_payload

    @pytest.mark.parametrize(
        ids=[
            "1. wrong key in notification_event dict",
            "2. missing key in notification_event dict",
            "3. Invalid user type enum in notification_event dict",
            "4. Invalid event_name enum in notification_event_payload",
            "5. Invalid event_properties in notification_event_payload",
        ],
        argnames="input_dict",
        argvalues=(
            {
                "wrong_key": "ABC",
                "user_id_type": "PAYOR_ID",
                "user_type": "MEMBER",
                "event_source_system": "WALLET",
                "notification_event_payload": {
                    "event_name": "mmb_wallet_qualified",
                    "event_properties": {"program_overview_link": "www"},
                },
            },
            {
                "user_id_type": "PAYOR_ID",
                "user_type": "MEMBER",
                "event_source_system": "WALLET",
                "notification_event_payload": {
                    "event_name": "mmb_wallet_qualified",
                    "event_properties": {"program_overview_link": "www"},
                },
            },
            {
                "user_id": "1234",
                "user_id_type": "PAYOR_ID",
                "user_type": "THIS_IS_WRONG",
                "event_source_system": "WALLET",
                "notification_event_payload": {
                    "event_name": "mmb_wallet_qualified",
                    "event_properties": {"program_overview_link": "www"},
                },
            },
            {
                "user_id": "1234",
                "user_id_type": "PAYOR_ID",
                "user_type": "MEMBER",
                "event_source_system": "WALLET",
                "notification_event_payload": {
                    "event_name": "this_is_wrong",
                    "event_properties": {"program_overview_link": "www"},
                },
            },
            {
                "user_id": "1234",
                "user_id_type": "PAYOR_ID",
                "user_type": "MEMBER",
                "event_source_system": "WALLET",
                "notification_event_payload": {
                    "event_name": "mmb_wallet_qualified",
                    "event_properties": {"this_is_wrong": "www"},
                },
            },
        ),
    )
    def test_notification_event_creation_errors(self, input_dict):
        with pytest.raises(NotificationPayloadCreationError):
            _ = NotificationPayload.create_from_dict(input_dict)
