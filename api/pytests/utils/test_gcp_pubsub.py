import os
from unittest import mock

from common import stats
from utils import gcp_pubsub
from utils import log as utils_log

log = utils_log.logger(__name__)

TEST_PUBLISHER_TOPIC = os.getenv(
    "TEST_PUBLISHER_TOPIC", "projects/local-dev/topics/test-publisher-topic"
)


class TestPublisher:
    """Class used to simulate a publisher to allow the testing of the callback
    handler.
    """

    inc = 0
    TEST_TOPIC_SUCCESS = "test_topic_success"
    TEST_TOPIC_FAIL = "test_topic_fail"

    @classmethod
    def topic_path(cls, *args):
        return "/".join(str(a) for a in args if a)

    def publish(self, topic, data, ordering_key="", **attrs) -> str:
        self.inc += 1
        if data is self.TEST_TOPIC_FAIL:
            raise Exception("Failed test")
        else:
            return f"<local-{self.inc}>"


def test_publisher_error_handler_success():
    """Tests the behavior of the callback handler if the publish request is
    successful. The expectation is that the success will be written to Datadog
    via the stats module.
    """
    # Given
    topic = TEST_PUBLISHER_TOPIC
    publisher = TestPublisher()
    metric_name = "pytests.utils.test_gcp_pubsub.test_publisher_callback_success"

    # When
    with mock.patch("common.stats.increment") as stats_increment_mock:
        with gcp_pubsub.publisher_error_handler(
            metric_name=metric_name,
            pod_name=stats.PodNames.TEST_POD,
            topic=topic,
            tags=["type:demo"],
        ):
            publisher.publish(topic, data=TestPublisher.TEST_TOPIC_SUCCESS)

    # Then
    stats_increment_mock.assert_called_with(
        metric_name=metric_name,
        pod_name=stats.PodNames.TEST_POD,
        tags=[
            f"topic:{topic}",
            "success:true",
            "type:demo",
        ],
    )


def test_publisher_error_handler_fail():
    """Tests the behavior of the callback handler if the publish request fails.
    The expectation is that the failure will be written to Datadog via mmlib's
    stats module.
    """
    # Given
    topic = TEST_PUBLISHER_TOPIC
    publisher = TestPublisher()
    metric_name = "pytests.utils.test_gcp_pubsub.test_publisher_callback_fail"

    # When
    with mock.patch("common.stats.increment") as stats_increment_mock:
        with gcp_pubsub.publisher_error_handler(
            metric_name=metric_name,
            pod_name=stats.PodNames.TEST_POD,
            topic=topic,
            tags=["type:demo"],
        ):
            publisher.publish(topic, data=TestPublisher.TEST_TOPIC_FAIL)

    # Then
    stats_increment_mock.assert_called_with(
        metric_name=metric_name,
        pod_name=stats.PodNames.TEST_POD,
        tags=[
            f"topic:{topic}",
            "success:false",
            "type:demo",
        ],
    )
