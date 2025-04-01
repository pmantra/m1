import pytest
from redis.exceptions import ConnectionError, TimeoutError

from authz.services.block_list import BlockList, BlockListDenied


class TestBlockList:
    @staticmethod
    def test_validate_access(mock_redis, mock_user_service):
        # Given
        user_id = 123
        attribute = "credit_card"
        check_values = "zyx123"
        mock_redis.sismember.return_value = 1

        # When/Then
        with pytest.raises(BlockListDenied):
            BlockList().validate_access(
                user_id=user_id, attribute=attribute, check_values=check_values
            )

        assert mock_user_service.update_user.call_args[1] == {
            "is_active": False,
            "user_id": user_id,
        }

    @staticmethod
    def test_validate_access_connection_timeout(mock_redis, mock_user_service):
        # Given
        user_id = 123
        attribute = "credit_card"
        check_values = "zyx123"
        mock_redis.sismember.side_effect = TimeoutError("Timeout")

        # When
        BlockList().validate_access(
            user_id=user_id, attribute=attribute, check_values=check_values
        )

    @staticmethod
    def test_validate_access_connection_error(mock_redis, mock_user_service):
        # Given
        user_id = 123
        attribute = "credit_card"
        check_values = "zyx123"
        mock_redis.sismember.side_effect = ConnectionError(
            "Error 111 connecting to redis:6379. Connection refused."
        )

        # When
        BlockList().validate_access(
            user_id=user_id, attribute=attribute, check_values=check_values
        )

    @staticmethod
    def test_validate_access_connection_refused_error(mock_redis, mock_user_service):
        # Given
        user_id = 123
        attribute = "credit_card"
        check_values = "zyx123"
        mock_redis.sismember.side_effect = ConnectionRefusedError(
            "[Errno 111] Connection refused"
        )

        # When
        BlockList().validate_access(
            user_id=user_id, attribute=attribute, check_values=check_values
        )

    @staticmethod
    def test_validate_access_random_exception_enforced(mock_redis, mock_user_service):
        # Given
        user_id = 123
        attribute = "credit_card"
        check_values = "zyx123"
        mock_redis.sismember.side_effect = Exception("dummy exception")

        # When
        with pytest.raises(Exception, match="dummy exception"):
            BlockList().validate_access(
                user_id=user_id, attribute=attribute, check_values=check_values
            )

    @staticmethod
    def test_validate_access_random_exception_skipped(mock_redis, mock_user_service):
        # Given
        user_id = 123
        attribute = "credit_card"
        check_values = "zyx123"
        mock_redis.sismember.side_effect = Exception("dummy exception")

        # When
        BlockList(skip_if_unavailable=True).validate_access(
            user_id=user_id, attribute=attribute, check_values=check_values
        )

    @staticmethod
    def test_validate_access_multiple_values(mock_redis, mock_user_service):
        # Given
        user_id = 123
        attribute = "phone_number"
        check_values = ["zyx123", "abcd1234"]
        mock_redis.sismember.return_value = 1

        # When/Then
        with pytest.raises(BlockListDenied):
            BlockList().validate_access(
                user_id=user_id, attribute=attribute, check_values=check_values
            )

        assert mock_user_service.update_user.call_args[1] == {
            "is_active": False,
            "user_id": user_id,
        }

    @staticmethod
    def test_validate_attributes(mock_redis, mock_user_service):
        # Given
        user_id = 123
        attribute = "SOME_INVALID_ATTRIBUTE"
        check_values = "foo"

        # When/Then
        with pytest.raises(AttributeError):
            BlockList().validate_access(
                user_id=user_id, attribute=attribute, check_values=check_values
            )

    @staticmethod
    def test_block_attribute(mock_redis):
        # Given
        attribute = "phone_number"
        value = "foo"

        # When
        BlockList().block_attribute(attribute=attribute, value=value)

        # Then
        assert mock_redis.sadd.call_args.args == (
            f"user_blocked_attributes.{attribute}",
            value,
        )

    @staticmethod
    def test_unblock_attribute(mock_redis):
        # Given
        attribute = "phone_number"
        value = "foo"

        # When
        BlockList().unblock_attribute(attribute=attribute, value=value)

        # Then
        assert mock_redis.srem.call_args.args == (
            f"user_blocked_attributes.{attribute}",
            value,
        )
