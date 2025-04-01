"""A python wrapper around the datadog-ci CLI."""
import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pprint import pformat
from tempfile import NamedTemporaryFile
from typing import Literal, Optional

import requests

from ci_test.log import err
from ci_test.settings import TestScope, dd_headers

_PATH = (
    "latest/download"
    if (_V := os.getenv("DD_CI_CLI_VERSION")) is None
    else f"download/{_V}"
)
_ASSET = os.getenv(
    "DD_CI_CLI_ARCH", f"datadog-ci_{platform.system().lower()}-{platform.machine()}"
)
_DOWNLOAD_URL = f"https://github.com/DataDog/datadog-ci/releases/{_PATH}/{_ASSET}"
_USAGE_PATTERN = re.compile(
    r"datadog-ci (measure|metric).*(--measures|--metrics)", re.MULTILINE
)
Level = Literal["pipeline", "job"]


class _MetricType(Enum):
    UNSPECIFIED = 0
    COUNT = 1
    RATE = 2
    GAUGE = 3


@dataclass
class DatadogCI:
    path: str
    measure_command: str = field(init=False)
    measure_argname: str = field(init=False)

    def __post_init__(self) -> None:
        result = subprocess.run([self.path, "-h"], capture_output=True, text=True)
        match = _USAGE_PATTERN.search(result.stdout)
        if match is None:
            raise NotImplementedError(
                f"Could not parse measures command from help:\n{result.stdout}"
            )
        self.measure_command = match.group(1)
        self.measure_argname = match.group(2)

    def measure(self, level: Level, **measures: float) -> None:
        """Add numeric tags to CI Visibility pipeline or job spans.

        Args:
            level: If pipeline is selected then the measures will be added to
              the pipeline trace span. If job is selected it will be added to
              the span for the currently running job.
            measures: The key-value pairs to be added to the pipeline or job span.
        """
        err(f"submitting datadog CI measures:\n{pformat(measures)}")
        subprocess.run(
            [self.path, self.measure_command, f"--level={level}"]
            + [f"{self.measure_argname}={k}:{v}" for k, v in measures.items()]
        )

    def tag(self, level: Level, **tags: str) -> None:
        """Add custom tags to a CI Visibility pipeline trace or job span in Datadog.

        Args:
            level: If pipeline is selected then the tags will be added to the
              pipeline trace span. If job is selected it will be added to the
              span for the currently running job.
            tags: The key-value tag pairs to be added to the pipeline or job span.
        """
        err(f"submitting datadog CI tags:\n{pformat(tags)}")
        subprocess.run(
            [self.path, "tag", f"--level={level}"]
            + [f"--tags={k}:{v}" for k, v in tags.items()]
        )


_singleton: Optional[DatadogCI] = None


def get() -> DatadogCI:
    """get() lazily initializes the DatadogCI singleton.

    datadog-ci will be used directly if it is available on the system path, or
    be downloaded from the project's GitHub releases as specified by
    `$DD_CI_CLI_VERSION` and `$DD_CI_CLI_ARCH` (defaulting to latest).

    Returns:
        A wrapper object around the datadog-ci CLI with two methods: measure & tag

        dd = datadog_ci.get()
        dd.measure("job", my_job_counter=123)
        dd.measure("pipeline", my_pipeline_timer=4.56, and_also=789)
        dd.tag("job", some_job_tag="foo")
        dd.tag("pipeline", some_pipeline_tag="bar")
    """
    global _singleton
    if _singleton is not None:
        return _singleton
    try:
        # datadog-ci is already available on the path
        return (_singleton := DatadogCI(path="datadog-ci"))
    except FileNotFoundError:
        # datadog-ci will be downloaded to a temp file
        res = requests.get(_DOWNLOAD_URL, allow_redirects=True)
        with NamedTemporaryFile(delete=False) as tmp:
            with open(tmp.name, "wb") as f:
                f.write(res.content)
            os.chmod(tmp.name, 0o777)
        return (_singleton := DatadogCI(path=tmp.name))


def gauge_latency(
    duration: float, timestamp: datetime, test_scope: TestScope, suite_failed: bool
) -> None:
    _series(
        "mvn.ci_test.latency",
        _MetricType.GAUGE,
        timestamp,
        duration,
        [f"test_scope:{test_scope.value}", _pass_fail_tag(suite_failed)],
    )


def count_merge_trains(suite_failed: bool) -> None:
    _series(
        "mvn.ci_test.merge_trains",
        _MetricType.COUNT,
        datetime.now(timezone.utc),
        1,
        [_pass_fail_tag(suite_failed)],
    )


def _pass_fail_tag(suite_failed: bool) -> str:
    return f"suite_passed:{'false' if suite_failed else 'true'}"


def _series(
    metric: str, type: _MetricType, timestamp: datetime, value: float, tags: list[str]
) -> None:
    series = {
        "metric": metric,
        "type": type.value,
        "points": [
            {
                "timestamp": int(timestamp.timestamp()),
                "value": value,
            }
        ],
        "tags": tags,
    }
    err(f"submitting datadog custom metric:\n{pformat(series)}")
    res = requests.post(
        "https://api.datadoghq.com/api/v2/series",
        headers=dd_headers,
        json={"series": [series]},
    )
    try:
        res.raise_for_status()
    except Exception as e:
        err(f"error encountered submitting metrics: {e}\n{res.text}")
