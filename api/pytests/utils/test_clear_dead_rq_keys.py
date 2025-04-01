from unittest.mock import Mock, patch

import pytest

from utils.clear_dead_rq_keys import RQKeyInvalidator


@pytest.fixture
def rq_invalidator():
    data = {
        "a": {"ended_at": "2020-01-01T12:00:00Z", "status": "failed"},
        "b": {"ended_at": "2020-01-01T12:00:00Z", "status": "not failed"},
    }

    def mock_scan(cursor, pattern, count):
        return (0, ["a", "b"])

    def mock_hmget(key, attr):
        return data[key][attr]

    def mock_delete(key):
        return 1

    def mock_type(key):
        return "hash"

    with patch("redis.Redis") as mock_redis:
        mock_redis.scan.side_effect = mock_scan
        mock_redis.type.side_effect = mock_type
        mock_redis.hmget.side_effect = mock_hmget
        mock_redis.delete.side_effect = mock_delete

        pipeline_mock = Mock()
        mock_redis.pipeline.return_value.__enter__.return_value = pipeline_mock
        pipeline_mock.execute.side_effect = [
            ["hash", "hash"],
            [
                [data["a"]["ended_at"], data["a"]["status"]],
                [data["b"]["ended_at"], data["b"]["status"]],
            ],
        ]

        yield RQKeyInvalidator(redis=mock_redis)


class TestRQInvalidator:
    def test_percentage_deleteable(self, rq_invalidator):
        assert rq_invalidator.percent_deleteable() == 50.0

    def test_percent_deleteable_no_keys(self, rq_invalidator):
        def scan_keys(cursor, pattern, count):
            return (0, [])

        rq_invalidator.redis.scan.side_effect = scan_keys
        assert rq_invalidator.percent_deleteable() == 0.0

    def test_percent_deleteable_key_not_hash(self, rq_invalidator):
        pipeline_mock = Mock()
        rq_invalidator.redis.pipeline.return_value.__enter__.return_value = (
            pipeline_mock
        )
        pipeline_mock.execute.side_effect = [["set", "set"], []]
        assert rq_invalidator.percent_deleteable() == 0.0

    def test_delete_keys(self, rq_invalidator):
        rq_invalidator.process_deletion()
        rq_invalidator.redis.delete.assert_called_with("a")
