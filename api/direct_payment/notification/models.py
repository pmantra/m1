from __future__ import annotations

import dataclasses
import enum
from traceback import format_exc

from ddtrace import tracer
from requests import Response

from direct_payment.notification.errors import (
    NotificationEventPayloadCreationError,
    NotificationPayloadCreationError,
)


class UserIdType(enum.Enum):
    PAYOR_ID = "PAYOR_ID"
    WALLET_ID = "WALLET_ID"
    USER_ID = "USER_ID"


class UserType(enum.Enum):
    MEMBER = "MEMBER"
    EMPLOYER = "EMPLOYER"
    CLINIC = "CLINIC"


class EventSourceSystem(enum.Enum):
    WALLET = "WALLET"
    BILLING = "BILLING"
    PAYMENTS_GATEWAY = "PAYMENTS_GATEWAY"
    CLINIC_PORTAL = "CLINIC_PORTAL"


class NotificationStatus(enum.Enum):
    BRAZE_SUCCESS = "BRAZE_SUCCESS"
    BRAZE_FAILURE = "BRAZE_FAILURE"
    ERROR = "ERROR"


class EventName(enum.Enum):
    MMB_UPCOMING_PAYMENT_REMINDER = "mmb_upcoming_payment_reminder"
    MMB_PAYMENT_CONFIRMED = "mmb_payment_confirmed"
    MMB_REFUND_CONFIRMATION = "mmb_refund_confirmation"
    MMB_PAYMENT_PROCESSING_ERROR = "mmb_payment_processing_error"
    MMB_PAYMENT_ADJUSTED_ADDL_CHARGE = "mmb_payment_adjusted_addl_charge"
    MMB_PAYMENT_ADJUSTED_REFUND = "mmb_payment_adjusted_refund"
    MMB_WALLET_QUALIFIED = "mmb_wallet_qualified"
    MMB_PAYMENT_METHOD_ADDED = "mmb_payment_method_added"
    MMB_PAYMENT_METHOD_REMOVED = "mmb_payment_method_removed"
    MMB_PAYMENT_METHOD_REQUIRED = "mmb_payment_method_required"
    MMB_BILLING_ESTIMATE = "mmb_billing_estimate"
    MMB_CLINIC_PORTAL_MISSING_INFO = "mmb_clinic_portal_missing_info"


@dataclasses.dataclass(frozen=True)
class MmbUpcomingPaymentReminderEventProperties:
    __slots__ = (
        "benefit_id",
        "payment_amount",
        "payment_date",
        "payment_method_last4",
        "payment_method_type",
        "clinic_name",
        "clinic_location",
    )
    benefit_id: str
    payment_amount: str
    payment_date: str
    payment_method_last4: str
    payment_method_type: str
    clinic_name: str
    clinic_location: str


@dataclasses.dataclass(frozen=True)
class MmbBillingEstimateEventProperties:
    __slots__ = (
        "bill_uuid",
        "benefit_id",
        "total_cost",
        "member_responsibility",
        "maven_benefit",
        "credits_used",
        "procedure_name",
        "clinic_name",
        "clinic_location",
    )
    bill_uuid: str
    benefit_id: str
    total_cost: str
    member_responsibility: str
    maven_benefit: str
    credits_used: str
    procedure_name: str
    clinic_name: str
    clinic_location: str


@dataclasses.dataclass(frozen=True)
class MmbPaymentConfirmedEventProperties:
    __slots__ = (
        "benefit_id",
        "payment_amount",
        "payment_date",
        "payment_details_link",
        "payment_method_last4",
        "payment_method_type",
    )

    benefit_id: str
    payment_amount: str
    payment_date: str
    payment_details_link: str
    payment_method_last4: str
    payment_method_type: str


@dataclasses.dataclass(frozen=True)
class MmbRefundConfirmationEventProperties:
    __slots__ = (
        "payment_details_link",
        "payment_method_last4",
        "payment_method_type",
        "refund_amount",
        "refund_date",
    )
    payment_details_link: str
    payment_method_last4: str
    payment_method_type: str
    refund_amount: str
    refund_date: str


@dataclasses.dataclass(frozen=True)
class MmbPaymentProcessingErrorEventProperties:
    __slots__ = (
        "payment_amount",
        "payment_date",
        "payment_method_last4",
        "payment_method_type",
    )
    payment_amount: str
    payment_date: str
    payment_method_last4: str
    payment_method_type: str


@dataclasses.dataclass(frozen=True)
class MmbPaymentAdjustedAddlChargeEventProperties:
    __slots__ = (
        "additional_charge_amount",
        "benefit_id",
        "original_payment_amount",
        "payment_amount",
        "payment_date",
        "payment_method_last4",
        "payment_method_type",
    )
    additional_charge_amount: str
    benefit_id: str
    original_payment_amount: str
    payment_amount: str
    payment_date: str
    payment_method_last4: str
    payment_method_type: str


@dataclasses.dataclass(frozen=True)
class MmbPaymentAdjustedRefundEventProperties:
    __slots__ = (
        "benefit_id",
        "original_payment_amount",
        "payment_amount",
        "refund_date",
        "payment_method_last4",
        "payment_method_type",
        "refund_amount",
    )
    benefit_id: str
    original_payment_amount: str
    payment_amount: str
    refund_date: str
    payment_method_last4: str
    payment_method_type: str
    refund_amount: str


@dataclasses.dataclass(frozen=True)
class MmbWalletQualifiedEventProperties:
    __slots__ = ("program_overview_link",)
    program_overview_link: str


@dataclasses.dataclass(frozen=True)
class MmbPaymentMethodAddedEventProperties:
    __slots__ = (
        "payment_method_last4",
        "payment_method_type",
        "program_overview_link",
        "card_funding",
    )
    payment_method_last4: str
    payment_method_type: str
    program_overview_link: str
    card_funding: str


@dataclasses.dataclass(frozen=True)
class MmbPaymentMethodRemovedEventProperties:
    __slots__ = ("benefit_id", "payment_method_last4", "payment_method_type")

    benefit_id: str
    payment_method_last4: str
    payment_method_type: str


@dataclasses.dataclass(frozen=True)
class MmbPaymentMethodRequiredEventProperties:
    __slots__ = ("benefit_id",)

    benefit_id: str


@dataclasses.dataclass(frozen=True)
class MmbClinicPortalMissingInfoEventProperties:
    __slots__ = (
        "benefit_id",
        "missing_health_plan_information",
        "missing_payment_information",
    )

    benefit_id: str
    missing_health_plan_information: bool
    missing_payment_information: bool


@dataclasses.dataclass(frozen=True)
class NotificationEventPayload:
    event_name: EventName
    # fmt: off
    # Black tries to put the following all on one line
    event_properties: MmbUpcomingPaymentReminderEventProperties | MmbPaymentConfirmedEventProperties\
        | MmbRefundConfirmationEventProperties | MmbPaymentAdjustedAddlChargeEventProperties\
        | MmbPaymentAdjustedRefundEventProperties | MmbWalletQualifiedEventProperties \
        | MmbPaymentMethodAddedEventProperties | MmbPaymentMethodRemovedEventProperties \
        | MmbPaymentMethodRequiredEventProperties | MmbBillingEstimateEventProperties \
        | MmbClinicPortalMissingInfoEventProperties
    # fmt: on

    EVENT_NAME_PROPERTIES_MAPPING = {
        EventName.MMB_UPCOMING_PAYMENT_REMINDER: MmbUpcomingPaymentReminderEventProperties,
        EventName.MMB_PAYMENT_CONFIRMED: MmbPaymentConfirmedEventProperties,
        EventName.MMB_REFUND_CONFIRMATION: MmbRefundConfirmationEventProperties,
        EventName.MMB_PAYMENT_PROCESSING_ERROR: MmbPaymentProcessingErrorEventProperties,
        EventName.MMB_PAYMENT_ADJUSTED_ADDL_CHARGE: MmbPaymentAdjustedAddlChargeEventProperties,
        EventName.MMB_PAYMENT_ADJUSTED_REFUND: MmbPaymentAdjustedRefundEventProperties,
        EventName.MMB_WALLET_QUALIFIED: MmbWalletQualifiedEventProperties,
        EventName.MMB_PAYMENT_METHOD_ADDED: MmbPaymentMethodAddedEventProperties,
        EventName.MMB_PAYMENT_METHOD_REMOVED: MmbPaymentMethodRemovedEventProperties,
        EventName.MMB_PAYMENT_METHOD_REQUIRED: MmbPaymentMethodRequiredEventProperties,
        EventName.MMB_BILLING_ESTIMATE: MmbBillingEstimateEventProperties,
        EventName.MMB_CLINIC_PORTAL_MISSING_INFO: MmbClinicPortalMissingInfoEventProperties,
    }

    @staticmethod
    def create_from_dict(input_dict: dict) -> NotificationEventPayload:
        try:
            event_name = EventName(input_dict["event_name"])
            property_class = NotificationEventPayload.EVENT_NAME_PROPERTIES_MAPPING[
                event_name
            ]
            event_properties_dict = input_dict["event_properties"]
            # check that the keys exactly match
            assert (
                property_class.__annotations__.keys() == event_properties_dict.keys()
            ), (
                f"The input dict keys: {set(input_dict.keys())} do not exactly match the dataclass fields: "
                f"{set(NotificationEventPayload.__annotations__.keys())}."
            )

            # we do not allow Nones
            nones = {k for k, v in event_properties_dict.items() if v is None}
            assert (
                not nones
            ), f"keys: {''.join(nones)} in event properties have None values"

            event_properties = property_class(**event_properties_dict)
            return NotificationEventPayload(
                event_name=event_name, event_properties=event_properties
            )
        except Exception:
            raise NotificationEventPayloadCreationError(
                [f"NotificationEventPayload creation failed. reason:  {format_exc()}"]
            )

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class NotificationPayload:
    __slots__ = (
        "user_id",
        "user_id_type",
        "user_type",
        "event_source_system",
        "notification_event_payload",
    )
    user_id: str
    user_id_type: UserIdType
    user_type: UserType | None
    event_source_system: EventSourceSystem
    notification_event_payload: NotificationEventPayload

    @staticmethod
    @tracer.wrap()
    def create_from_dict(input_dict: dict) -> NotificationPayload:
        try:
            assert NotificationPayload.__annotations__.keys() == input_dict.keys(), (
                f"The input dict keys: {set(input_dict.keys())} do not exactly match the dataclass fields: "
                f"{set(NotificationPayload.__annotations__.keys())}."
            )

            return NotificationPayload(
                user_id=input_dict["user_id"],
                user_id_type=UserIdType(input_dict["user_id_type"]),
                user_type=UserType(input_dict["user_type"])
                if input_dict["user_type"]
                else None,
                event_source_system=EventSourceSystem(
                    input_dict["event_source_system"]
                ),
                notification_event_payload=(
                    NotificationEventPayload.create_from_dict(
                        input_dict["notification_event_payload"]
                    )
                ),
            )
        except Exception:
            raise NotificationPayloadCreationError(
                [f"NotificationEvent creation failed. reason:  {format_exc()}"]
            )


@dataclasses.dataclass(frozen=True)
class NotificationStatusObject:
    __slots__ = ("notification_status", "braze_response", "message")
    notification_status: NotificationStatus
    braze_response: Response | None
    message: str | None
