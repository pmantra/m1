import json
from unittest.mock import Mock, patch

from factory.alchemy import SQLAlchemyModelFactory

from conftest import BaseMeta
from models.marketing import IosNonDeeplinkUrl


class IosNonDeeplinkUrlFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = IosNonDeeplinkUrl


@patch("models.marketing.log")
@patch("models.marketing.redis_client")
class TestGetIosNonDeeplinkUrls:
    def test_error_initializing_no_data(self, redis_client, log, client):
        err = Exception("ahhh")
        redis_client.side_effect = err

        res = client.get("/api/v1/_/ios_non_deeplink_urls")
        log.error.assert_called_with(
            "Error fetching cached ios non-deeplink urls from Redis",
            error=err,
        )
        assert res.status_code == 200
        assert json.loads(res.data) == []

    def test_error_initializing_yes_data(self, redis_client, log, client):
        err = Exception("ahhh")
        redis_client.side_effect = err

        IosNonDeeplinkUrlFactory.create(url="reset_password")
        IosNonDeeplinkUrlFactory.create(url="google.com")

        res = client.get("/api/v1/_/ios_non_deeplink_urls")
        log.error.assert_called_with(
            "Error fetching cached ios non-deeplink urls from Redis",
            error=err,
        )
        assert res.status_code == 200
        assert set(json.loads(res.data)) == {"reset_password", "google.com"}

    def test_error_fetching_no_data(self, redis_client, log, client):
        err = Exception("ahhh")
        redis_mock = Mock()
        redis_mock.smembers.side_effect = err
        redis_client.return_value = redis_mock

        res = client.get("/api/v1/_/ios_non_deeplink_urls")
        log.error.assert_called_with(
            "Error fetching cached ios non-deeplink urls from Redis",
            error=err,
        )
        assert res.status_code == 200
        assert json.loads(res.data) == []

    def test_error_fetching_yes_data(self, redis_client, log, client):
        err = Exception("ahhh")
        redis_mock = Mock()
        redis_mock.smembers.side_effect = err
        redis_client.return_value = redis_mock

        IosNonDeeplinkUrlFactory.create(url="reset_password")
        IosNonDeeplinkUrlFactory.create(url="google.com")

        res = client.get("/api/v1/_/ios_non_deeplink_urls")
        log.error.assert_called_with(
            "Error fetching cached ios non-deeplink urls from Redis",
            error=err,
        )
        assert res.status_code == 200
        assert set(json.loads(res.data)) == {"reset_password", "google.com"}

    def test_cache_empty_no_data(self, redis_client, log, client):
        redis_mock = Mock()
        redis_mock.smembers.return_value = set()
        redis_client.return_value = redis_mock

        res = client.get("/api/v1/_/ios_non_deeplink_urls")
        log.error.assert_not_called()
        redis_mock.sadd.assert_not_called()
        assert res.status_code == 200
        assert json.loads(res.data) == []

    def test_cache_empty_yes_data_write_error(self, redis_client, log, client):
        redis_mock = Mock()
        redis_mock.smembers.return_value = set()
        err = Exception("ahhh")
        redis_mock.sadd.side_effect = err
        redis_client.return_value = redis_mock

        IosNonDeeplinkUrlFactory.create(url="reset_password")
        IosNonDeeplinkUrlFactory.create(url="google.com")

        res = client.get("/api/v1/_/ios_non_deeplink_urls")
        log.error.assert_called_with(
            "Error storing ios non-deeplink urls in Redis",
            error=err,
        )
        redis_mock.sadd.assert_called_with(
            IosNonDeeplinkUrl.CACHE_KEY, "reset_password", "google.com"
        )
        assert res.status_code == 200
        assert set(json.loads(res.data)) == {"reset_password", "google.com"}

    def test_cache_empty_yes_data_write_success(self, redis_client, log, client):
        redis_mock = Mock()
        redis_mock.smembers.return_value = set()
        redis_client.return_value = redis_mock

        IosNonDeeplinkUrlFactory.create(url="reset_password")
        IosNonDeeplinkUrlFactory.create(url="google.com")

        res = client.get("/api/v1/_/ios_non_deeplink_urls")
        log.error.assert_not_called()
        redis_mock.sadd.assert_called_with(
            IosNonDeeplinkUrl.CACHE_KEY, "reset_password", "google.com"
        )
        redis_mock.expire.assert_called()
        assert set(json.loads(res.data)) == {"reset_password", "google.com"}

    def test_cache_not_empty(self, redis_client, log, client):
        redis_mock = Mock()
        redis_mock.smembers.return_value = {b"reset_password", b"google.com"}
        redis_client.return_value = redis_mock

        res = client.get("/api/v1/_/ios_non_deeplink_urls")
        redis_mock.sadd.assert_not_called()
        redis_mock.expire.assert_not_called()
        assert set(json.loads(res.data)) == {"reset_password", "google.com"}
