from types import MappingProxyType

from messaging.resources.braze import BrazeBulkMessageResource
from messaging.resources.deflection import (
    DeflectionCancelAppointmentsResource,
    DeflectionCategoryNeedsResource,
    DeflectionMemberContextResource,
    DeflectionProviderSearchResource,
    DeflectionResourcesSearch,
    DeflectionTrackCategoriesResource,
    DeflectionUpcomingAppointmentsResource,
)
from messaging.resources.messaging import (
    ChannelMessagesResource,
    ChannelParticipantsResource,
    ChannelsResource,
    ChannelStatusResource,
    ChannelsUnreadMessagesResource,
    MessageAcknowledgementResource,
    MessageBillingResource,
    MessageNotificationsConsentResource,
    MessageProductsResource,
    MessageResource,
)
from messaging.resources.sms import InternalSMSResource, SMSResource
from messaging.resources.twilio import TwilioStatusWebhookResource
from messaging.resources.zendesk import (
    AuthenticationViaZenDeskResource,
    MessageViaZenDeskResource,
)

_urls = MappingProxyType(
    {
        "/v1/_/vendor/zendesksc/deflection/cancel_appointment": DeflectionCancelAppointmentsResource,
        "/v1/_/vendor/zendesksc/deflection/category_needs": DeflectionCategoryNeedsResource,
        "/v1/_/vendor/zendesksc/deflection/member_context": DeflectionMemberContextResource,
        "/v1/_/vendor/zendesksc/deflection/provider_search": DeflectionProviderSearchResource,
        "/v1/_/vendor/zendesksc/deflection/resource_search": DeflectionResourcesSearch,
        "/v1/_/vendor/zendesksc/deflection/track_categories": DeflectionTrackCategoriesResource,
        "/v1/_/vendor/zendesksc/deflection/upcoming_appointments": DeflectionUpcomingAppointmentsResource,
        "/v1/channels/unread": ChannelsUnreadMessagesResource,
        "/v1/channel/<int:channel_id>/messages": ChannelMessagesResource,
        "/v1/channel/<int:channel_id>/participants": ChannelParticipantsResource,
        "/v1/channel/<int:channel_id>/status": ChannelStatusResource,
        "/v1/channels": ChannelsResource,
        "/v1/message/<int:message_id>": MessageResource,
        "/v1/message/<int:message_id>/acknowledgement": MessageAcknowledgementResource,
        "/v1/message/billing": MessageBillingResource,
        "/v1/message/products": MessageProductsResource,
        "/v1/message/notifications_consent": MessageNotificationsConsentResource,
        "/v1/unauthenticated/sms": SMSResource,
        "/v1/vendor/braze/bulk_messaging": BrazeBulkMessageResource,
        "/v1/vendor/twilio/message_status": TwilioStatusWebhookResource,
        "/v1/vendor/zendesk/message": MessageViaZenDeskResource,
        "/v1/zendesk/authentication": AuthenticationViaZenDeskResource,
        # Internal routes contain dash prefix
        "/v1/-/sms": InternalSMSResource,
    }
)


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for url_path, view in _urls.items():
        api.add_resource(view, url_path)
    return api


def _fetch_url_mappings():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for url_path, view in _urls.items():
        yield url_path, view, {},


def get_routes():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    yield from _fetch_url_mappings()


def get_blueprints():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    ...
