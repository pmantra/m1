from traceback import FrameSummary, StackSummary
from unittest import mock

from common import stats
from utils.log_model_usage import extract_referer, log_model_usage


class TestLogUsageMetric:
    def test_log_usage_metric(self, mock_trace, mock_stats_incr):
        # Given
        stack = StackSummary.from_list([])
        mock_trace.return_value = stack
        expected_call = mock.call(
            metric_name="mono_sqlalchemy_model_access",
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=[
                "model_name:User",
                "referer_file:Unknown referer",
            ],
            sample_rate=0.1,
        )

        # When
        log_model_usage("User", pod_name=stats.PodNames.CORE_SERVICES)

        # Then
        assert mock_stats_incr.call_args == expected_call

    def test_log_usage_metric_with_exclusions(self, mock_trace, mock_stats_incr):
        # Given
        excluded = ["/api/foo/bar.py"]
        stack = StackSummary.from_list(
            [
                FrameSummary("/api/foo/bar.py", 9, "one_or_none"),
                FrameSummary("/usr/sqlalchemy/orm/query.py", 9, "one_or_none"),
            ]
        )
        mock_trace.return_value = stack

        # When
        log_model_usage(
            "User", exclude_files=excluded, pod_name=stats.PodNames.CORE_SERVICES
        )

        # Then
        assert mock_stats_incr.called is False


class TestExtractingReferer:
    def test_extracting_referer(self):
        # Given
        stack = StackSummary.from_list(
            [
                FrameSummary("/usr/local/bin/gunicorn", 8, "<module>"),
                FrameSummary(
                    "/usr/local/lib/python3.8/site-packages/gunicorn/app/wsgiapp.py",
                    67,
                    "run",
                ),
                FrameSummary(
                    "/usr/local/lib/python3.8/site-packages/flask/app.py",
                    2464,
                    "__call__",
                ),
                FrameSummary(
                    "/api/common/services/ratelimiting.py", 47, "ratelimit_wrapper"
                ),
                FrameSummary("/api/authn/resources/user.py", 662, "post"),
                FrameSummary("/usr/local/lib/python3.8/some-package/foo.py", 3, "bar"),
                FrameSummary(
                    "/usr/local/lib/python3.8/site-packages/sqlalchemy/orm/query.py",
                    3459,
                    "one_or_none",
                ),
                FrameSummary(
                    "/usr/local/lib/python3.8/site-packages/sqlalchemy/event/attr.py",
                    322,
                    "__call__",
                ),
                FrameSummary("/api/authn/models/user.py", 932, "receive_load"),
            ]
        )
        expected_file = "/api/authn/resources/user.py"

        # When
        actual_file = extract_referer(stack)

        # Then
        assert actual_file == expected_file

    def test_extracting_from_empty_stack(self):
        # Given
        stack = StackSummary.from_list([])
        # When
        actual_file = extract_referer(stack)
        # Then
        assert actual_file == "Unknown referer"

    def test_extracting_from_stack_without_sqlalchemy(self):
        # Given
        stack = StackSummary.from_list(
            [
                FrameSummary("/api/authn/resources/user.py", 662, "post"),
            ]
        )
        # When
        actual_file = extract_referer(stack)
        # Then
        assert actual_file == "Unknown referer"

    def test_extracting_from_stack_without_file_preceding_sqlalchemy(self):
        # Given
        stack = StackSummary.from_list(
            [
                FrameSummary(
                    "/usr/local/lib/python3.8/site-packages/sqlalchemy/orm/query.py",
                    3459,
                    "one_or_none",
                ),
            ]
        )
        # When
        actual_file = extract_referer(stack)
        # Then
        assert actual_file == "Unknown referer"
