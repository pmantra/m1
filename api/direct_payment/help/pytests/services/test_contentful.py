from unittest import mock

from direct_payment.help.services import contentful

EXPECTED_CLIENT_TIMEOUT_SECONDS_USER_FACING = 2
EXPECTED_CLIENT_TIMEOUT_SECONDS_NON_USER_FACING = 5


@mock.patch("direct_payment.help.services.contentful.contentful")
@mock.patch("direct_payment.help.services.contentful.CONTENT_PREVIEW_TOKEN")
def test_initiate_preview_client(preview_token_mock, contentful_mock):
    contentful.MMBContentfulClient(preview=True, user_facing=False)
    contentful_mock.Client.assert_called_with(
        mock.ANY,
        preview_token_mock,
        api_url="preview.contentful.com",
        environment=mock.ANY,
        reuse_entries=mock.ANY,
        timeout_s=EXPECTED_CLIENT_TIMEOUT_SECONDS_NON_USER_FACING,
    )


@mock.patch("direct_payment.help.services.contentful.contentful")
@mock.patch("direct_payment.help.services.contentful.CONTENT_DELIVERY_TOKEN")
def test_initiate_delivery_client(delivery_token_mock, contentful_mock):
    contentful.MMBContentfulClient(preview=False, user_facing=False)
    contentful_mock.Client.assert_called_with(
        mock.ANY,
        delivery_token_mock,
        environment=mock.ANY,
        reuse_entries=mock.ANY,
        timeout_s=EXPECTED_CLIENT_TIMEOUT_SECONDS_NON_USER_FACING,
    )


@mock.patch("direct_payment.help.services.contentful.contentful")
@mock.patch("direct_payment.help.services.contentful.CONTENT_DELIVERY_TOKEN")
def test_initiate_user_facing_client(delivery_token_mock, contentful_mock):
    contentful.MMBContentfulClient(preview=False, user_facing=True)
    contentful_mock.Client.assert_called_with(
        mock.ANY,
        delivery_token_mock,
        environment=mock.ANY,
        reuse_entries=mock.ANY,
        timeout_s=EXPECTED_CLIENT_TIMEOUT_SECONDS_USER_FACING,
    )


@mock.patch("direct_payment.help.services.contentful.contentful")
@mock.patch("direct_payment.help.services.contentful.CONTENT_DELIVERY_TOKEN")
def test_initiate_non_user_facing_client(delivery_token_mock, contentful_mock):
    contentful.MMBContentfulClient(preview=False, user_facing=False)
    contentful_mock.Client.assert_called_with(
        mock.ANY,
        delivery_token_mock,
        environment=mock.ANY,
        reuse_entries=mock.ANY,
        timeout_s=EXPECTED_CLIENT_TIMEOUT_SECONDS_NON_USER_FACING,
    )
