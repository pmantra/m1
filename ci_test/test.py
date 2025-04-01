"""This module runs our pytest suite in sequential targets executed across N parallel CI jobs."""
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import MutableMapping
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime
from itertools import count
from os.path import isfile
from pathlib import Path
from pprint import pformat
from tempfile import TemporaryDirectory
from timeit import default_timer as timer
from typing import NoReturn, Optional, cast

from coverage import Coverage
from dateutil.parser import isoparse
from junitparser import JUnitXml, TestCase

from ci_test import datadog
from ci_test.artifacts import fetch_artifact
from ci_test.log import err, log
from ci_test.settings import (
    FLAKY_MAX_RUNS,
    MAX_RETRYABLE_FAILED_RATIO,
    TestScope,
    job_id,
    job_started_at,
    node_index,
    node_total,
    pipeline_created_at,
    project_dir,
    source_dir,
    test_scope,
)
from ci_test.testmondata import normalize_environment

TSecond = float
TDurations = MutableMapping[str, TSecond]
TLastFailed = MutableMapping[str, bool]

combined_durations_path = project_dir / f".test_durations-{job_id}"
combined_testmon_datafile = str(project_dir / f".testmondata-{job_id}")
os.environ["TESTMON_DATAFILE"] = combined_testmon_datafile


class TestData:
    directory: Path
    lastfailed: TLastFailed
    durations: TDurations

    def __init__(self, stack: ExitStack):
        temp = TemporaryDirectory()
        stack.enter_context(temp)
        self.directory = Path(temp.name)
        self.lastfailed = dict()
        shutil.copy(combined_durations_path, self.durations_path)

    @property
    def junitxml(self) -> str:
        return str(self.directory / "report.xml")

    @property
    def durations_path(self) -> str:
        return str(self.directory / ".test_durations")

    @property
    def coverage_file(self) -> str:
        return str(self.directory / ".coverage")

    def load(self) -> None:
        self.load_report()
        self.load_lastfailed()
        self.load_durations()

    def load_report(self) -> None:
        self.report = JUnitXml.fromfile(self.junitxml)

    def load_lastfailed(self) -> None:
        if self.report.failures + self.report.errors:
            with open(
                str(source_dir / ".pytest_cache/v/cache/lastfailed")
            ) as lastfailed_file:
                lastfailed_json = json.load(lastfailed_file)
                self.lastfailed = cast(TLastFailed, lastfailed_json)

    def load_durations(self) -> None:
        with open(self.durations_path) as durations_file:
            durations_json = json.load(durations_file)
            self.durations = cast(TDurations, durations_json)


@dataclass
class TestResult:
    report: JUnitXml = field(default_factory=JUnitXml)
    lastfailed: TLastFailed = field(default_factory=dict)
    durations: TDurations = field(default_factory=dict)
    coverage: Coverage = field(default_factory=Coverage)
    data: list[TestData] = field(default_factory=list)

    @property
    def junitxml(self) -> str:
        return str(project_dir / f"report-{job_id}.xml")

    @property
    def durations_path(self) -> str:
        return str(combined_durations_path)

    @property
    def coverage_file(self) -> str:
        return str(project_dir / f".coverage-{job_id}")

    def update(self, data: TestData) -> None:
        self.data.append(data)

    def combine(self) -> None:
        for d in self.data:
            for suite in d.report:
                # Repair junitxml reports corrupted by pytest-flaky
                # See https://github.com/box/flaky/issues/182
                seen = set()
                retry_duplicates = []
                for case in reversed(list(suite)):
                    if case.name in seen:
                        retry_duplicates.append(case)
                    else:
                        seen.add(case.name)
                for duplicate in retry_duplicates:
                    suite._elem.remove(duplicate._elem)
            d.report.update_statistics()
            self.report += d.report
            self.lastfailed.update(d.lastfailed)
            self.durations.update(d.durations)
        self.report.update_statistics()

    def dump(self) -> None:
        self.report.write(self.junitxml)

        with open(
            str(source_dir / ".pytest_cache/v/cache/lastfailed"), "w"
        ) as lastfailed_file:
            json.dump(self.lastfailed, lastfailed_file)

        with open(self.durations_path, "w") as durations_file:
            json.dump(self.durations, durations_file)

        combine_result = subprocess.run(
            [
                "coverage",
                "combine",
                f"--rcfile={source_dir / '.coveragerc'}",
                f"--data-file={self.coverage_file}",
            ]
            + [d.coverage_file for d in self.data],
            cwd=source_dir,
        )
        combine_result.check_returncode()


@dataclass
class TestReference:
    path: str
    reference: str
    class_name: Optional[str]
    func_name: str

    @classmethod
    def from_case(cls, case: TestCase) -> "TestReference":
        path = case.classname.replace(".", "/") + ".py"
        # Decode bin_xml_escape formatting to unicode, see:
        # https://github.com/pytest-dev/pytest/blob/93dd34e76d9c687d1c249fe8cf94bdf46813f783/src/_pytest/junitxml.py#L42-L66
        case_name = re.sub(
            "#x([0-9A-F]+)",
            lambda m: bytes(f"\\U{m.group(1):0>8}", "ascii").decode("unicode-escape"),
            case.name,
        )
        class_name: Optional[str] = None
        func_name = case_name.split("[")[0]
        if isfile(path):
            # case is a module-level function
            reference = f"{path}::{case_name}"
        else:
            # case is a class-level method
            class_parts = case.classname.split(".")
            path = "/".join(class_parts[:-1]) + ".py"
            class_name = class_parts[-1]
            reference = f"{path}::{class_name}::{case_name}"
        return cls(
            path=path,
            reference=reference,
            class_name=class_name,
            func_name=func_name,
        )


def main() -> None:
    _fetch_artifacts()
    _report_test_start()
    initial_result = _test_initial()
    retry_result = _retry_failed(initial_result)
    _report_test_end(initial_result, retry_result)


def _fetch_artifacts() -> None:
    fetch_artifact(".test_durations", str(combined_durations_path))
    if test_scope == TestScope.IMPACTED:
        # TODO: handle missing .testmondata artifact? default behavior will be to run all tests
        fetch_artifact(".testmondata", combined_testmon_datafile)
        normalize_environment(combined_testmon_datafile)


def _report_test_start() -> None:
    pipeline_created = isoparse(pipeline_created_at).replace(tzinfo=None)
    job_started = isoparse(job_started_at).replace(tzinfo=None)
    now = datetime.utcnow()

    startup_duration = (now - job_started).total_seconds()
    queue_e2e_duration = (job_started - pipeline_created).total_seconds()
    datadog.get().measure(
        "job",
        queue_e2e_duration=queue_e2e_duration,
        startup_duration_seconds=startup_duration,
    )
    datadog.get().tag(
        "job",
        test_scope=test_scope.value,
    )


def _test_initial() -> TestResult:
    start = timer()
    result = TestResult()
    with ExitStack() as stack:
        data = TestData(stack)
        if test_scope == TestScope.FULL:
            test_args = [
                "--testmon",
                "--testmon-noselect",
                f"--group={node_index}",
                f"--splits={node_total}",
                "--splitting-algorithm=least_duration",
                "--clean-durations",
                "--store-durations",
                f"--durations-path={data.durations_path}",
            ]
        elif test_scope == TestScope.IMPACTED:
            test_args = [
                "--testmon",
                "--testmon-nocollect",
                f"--group={node_index}",
                f"--splits={node_total}",
                f"--durations-path={data.durations_path}",
            ]
        else:
            raise NotImplementedError(
                f"Unexpected test scope provided: '{test_scope.value}'"
            )
        _pytest(data, *test_args)
        data.load()
        result.update(data)
        result.combine()
        result.dump()
    end = timer()

    r = result.report
    datadog.get().measure(
        "job",
        initial_e2e_seconds=end - start,
        initial_duration_seconds=r.time,
        initial_passed=r.tests - r.skipped - r.failures - r.errors,
        initial_skipped=r.skipped,
        initial_failed=r.failures + r.errors,
    )
    return result


_no_retry_measures = dict(
    retry_e2e_seconds=0,
    retry_iterations=0,
    retry_passed=0,
    retry_failed=0,
)


def _retry_failed(initial: TestResult) -> Optional[TestResult]:
    initial_failed = len(initial.lastfailed)
    if initial_failed == 0:
        err("All tests passed initial run; Skipping retry...")
        datadog.get().measure("job", **_no_retry_measures)
        return None

    max_retryable_tests = int(MAX_RETRYABLE_FAILED_RATIO * initial.report.tests)
    if initial_failed > max_retryable_tests:
        err(
            f"{initial_failed} of {initial.report.tests} tests failed initial run, exceeding max retryable tests {max_retryable_tests}; Skipping retry..."
        )
        datadog.get().measure("job", **_no_retry_measures)
        return None

    retry_collection_targets = list(
        set(ref.split("::")[0] for ref in initial.lastfailed)
    )

    start = timer()
    result = TestResult()
    prev_lastfailed = initial.lastfailed
    with ExitStack() as stack:
        for _retry_count in count(1):
            data = TestData(stack)
            _pytest(
                data,
                "--show-capture=no",
                "--last-failed",
                "--force-flaky",
                f"--max-runs={FLAKY_MAX_RUNS}",
                *retry_collection_targets,
            )
            data.load()
            result.update(data)
            if data.lastfailed == prev_lastfailed:
                err("All tests failed again; exiting in failure...")
                break
            prev_lastfailed = data.lastfailed
            if not data.lastfailed:
                err("All tests passed on retry...")
                break
            err("Some failed tests passed; retrying remaining failed tests again...")
        result.combine()
    end = timer()

    r = result.report
    retry_passed = r.tests - r.skipped - r.failures - r.errors
    datadog.get().measure(
        "job",
        retry_e2e_seconds=end - start,
        retry_iterations=_retry_count,
        retry_passed=retry_passed,  # a.k.a. flaky tests
        retry_failed=initial_failed - retry_passed,
    )
    return result


def _report_test_end(initial: TestResult, retry: Optional[TestResult]) -> NoReturn:
    # Establish tests that passed on retry
    flaky_refs = set()
    if retry is not None:
        for suite in retry.report:
            for case in suite:
                if case.is_passed:
                    ref = TestReference.from_case(case).reference
                    flaky_refs.add(ref)

    preconditions = []
    for suite in initial.report:
        for case in suite:
            ref = TestReference.from_case(case).reference

            if case.is_passed:
                log(
                    "INFO",
                    "TEST PASSED",
                    test_result="PASS",
                    test_case=ref,
                    test_duration=case.time,
                    test_scope=test_scope.value,
                )
                preconditions.append(ref)
                continue

            if case.is_skipped:
                log(
                    "INFO",
                    "TEST SKIPPED",
                    test_result="SKIP",
                    test_case=ref,
                    test_scope=test_scope.value,
                )
                continue

            # Establish negative test result (failure or error)
            negative_results = case.result
            if len(negative_results) != 1:
                raise NotImplementedError(
                    f"Unexpected result could not be reported on case '{case}':\n{pformat(negative_results)}"
                )
            negative_result = negative_results[0]
            failure = negative_result.text

            # Test failed all attempts -> FAIL
            if ref not in flaky_refs:
                log(
                    "ERROR",
                    "TEST FAILED",
                    test_result="FAIL",
                    test_case=ref,
                    test_duration=case.time,
                    test_failure=failure,
                    test_scope=test_scope.value,
                )
                continue

            # Test passed after initial failure -> FLAKE
            log(
                "WARNING",
                "TEST FLAKED",
                test_result="FLAKE",
                test_case=ref,
                test_duration=case.time,
                test_failure=failure,
                n_preconditions=len(preconditions),
                test_scope=test_scope.value,
            )
            # Report flaky test as passing while retaining initial failure text
            case.remove(negative_result)
            case.system_out = f"Flaky test passed after initial failure:\n\n{failure}"
    initial.report.update_statistics()
    initial.report.write(initial.junitxml)

    if retry is None:
        suite_failed = initial.lastfailed
    else:
        suite_failed = retry.data[-1].lastfailed

    sys.exit(100 if suite_failed else 0)


def _pytest(data: TestData, *vargs: str) -> None:
    os.environ["COVERAGE_FILE"] = data.coverage_file
    subprocess.run(
        [
            "pytest",
            f"--cov={source_dir}",
            "--cov-report=",
            f"--cov-config={source_dir / '.coveragerc'}",
            "-vv",
            "--dist=no",
            "-p no:warnings",
            f"--junitxml={data.junitxml}",
        ]
        + list(vargs),
        cwd=source_dir,
    )
