#!/usr/bin/env python
import gevent.monkey

gevent.monkey.patch_all()

import argparse
import contextlib
import pathlib
import sys

import coverage
import pytest

DIR = pathlib.Path(__file__).parent.absolute()
SRC = DIR.parent.parent.absolute()
TESTS = DIR / "test_connector.py"


def run(collect_coverage: bool = False):
    suffix = "connector"
    pytest_args = [
        str(TESTS),
        "--disable-warnings",
        "--capture=no",
        "--store-durations",
        "--clean-durations",
        f"--durations-path={str(SRC)}/.test_durations-{suffix}",
        f"--junitxml={str(SRC)}/report-{suffix}.xml",
    ]
    with coverage_context(collect_coverage=collect_coverage, suffix=suffix):
        return pytest.main(pytest_args)


@contextlib.contextmanager
def coverage_context(collect_coverage: bool = False, suffix: str = "connector"):
    if not collect_coverage:
        yield
        return
    cov = coverage.Coverage(
        config_file=str(SRC / ".coveragerc"),
        data_file=f".coverage-{suffix}",
    )
    cov.start()
    try:
        yield
    finally:
        cov.stop()
        cov.save()
        cov.report()
        cov.xml_report()


if __name__ == "__main__":
    sys.path.append(str(SRC))
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--coverage", action="store_true")
    parsed = parser.parse_args()
    run(collect_coverage=parsed.coverage)
