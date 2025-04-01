from unittest import mock

from eligibility.e9y import grpc_service


def test_get_service_stub_without_channel():
    with mock.patch("eligibility.e9y.grpc_service.channel") as mock_create_channel:
        # create channel if channel is not passed in
        stub = grpc_service._get_service_stub("mock_method1")
        assert stub is not None
        mock_create_channel.assert_called_once()


def test_get_service_stub_with_channel():
    channel = grpc_service.channel()
    with mock.patch("eligibility.e9y.grpc_service.channel") as mock_create_channel:
        # create channel if channel is not passed in
        stub = grpc_service._get_service_stub("mock_method1", grpc_connection=channel)
        assert stub is not None
        mock_create_channel.assert_not_called()
