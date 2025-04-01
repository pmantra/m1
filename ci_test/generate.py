import json
import os
import time
from math import ceil
from statistics import mean
from string import Template
from tempfile import NamedTemporaryFile
from typing import Optional

from testmon.testmon_core import TestmonData

from ci_test import datadog
from ci_test.artifacts import closest_ancestor_report_job, fetch_artifact
from ci_test.log import err
from ci_test.settings import (
    ARTIFACT_JOB_ID_ENV,
    DURATION,
    PIPELINE_CREATED_AT_ENV,
    ci_pipeline_created_at,
    commit_sha,
    gar_image_root,
    project_dir,
    source_dir,
)
from ci_test.testmondata import normalize_environment

FULL_PARALLEL = 30
TEST_TEMPLATE = Template(
    """
.test-full-changes: &test-full-changes
- "api/schemas/dump/*.sql"
- "**/*.po"
- "**/*.edi"

stages:
  - test

.pytest:
  stage: test
  image: $dev_image
  variables:
    FF_USE_NEW_BASH_EVAL_STRATEGY: true
    CI_TEST_SOURCE_DIR: $CI_PROJECT_DIR/api
    $pipeline_created_at_env: $pipeline_created_at
    $artifact_job_id_env: $artifact_job_id
    RANDOMLY_SEED: $randomly_seed
    SECURITY_SIGNING_TOKEN_PRIMARY: 88fd485112a2167c32af78c03cd12190106f755a2559a78da728622c4dda4a4a
    LOG_LEVEL: INFO
    MYSQL_ROOT_PASSWORD: root
    MYSQL_DATABASE: maven
    DEFAULT_DB_URL: 'mysql+pymysql://root:root@mysql-test:3306/maven?charset=utf8mb4'
    REDIS_URL: 'redis://redis-test:6379/0'
    REDIS_API_KEYS_HOST: 'redis-test'
    DISABLE_TRACING: "yes"  # N.B. - this value must be quoted or gitlab will barf
    DEV_LOGGING: "yes"
    MFA_JWT_SECRET: "test" # used by some api tests, don't want to hard-code a fallback value
    RATE_LIMIT_MULTIPLIER: "1000"
    PARENTING_JWT_SECRET: "test" # used by some api tests, don't want to hard-code a fallback value
    FF_NETWORK_PER_BUILD: "true"
    DD_TRACE_ENABLED: "false"
    DD_DOGSTATSD_DISABLE: "true"
    NODE_NAME: "gitlab-saas"
    DATA_ADMIN_ALLOWED: "YES"
    PYTHONDONTWRITEBYTECODE: "1"  # https://stackoverflow.com/a/65135170
    APPOINTMENTS_REDIS_PORT: 6379
    APPOINTMENTS_REDIS_HOST: redis-test
    APPOINTMENTS_REDIS_DB: 11
    DB_FIXTURE_STRATEGY: reset
  services:
    - name: mysql:5.7
      alias: mysql-test
      command:
      - "mysqld"
      - "--character-set-server"
      - "utf8mb4"
      - "--collation-server"
      - "utf8mb4_unicode_ci"
      - "--group-concat-max-len"
      - "655360"
      - "--sql_mode"
      - "NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION"
    - name: redis:5.0
      alias: redis-test
  allow_failure:
    exit_codes: 100
  script:
    # Wait for the database to be ready
    - db ready
    # Run tests...
    - python -m ci_test test
  artifacts:
    when: always
    paths:
    - "report-*.xml"
    - ".coverage-*"
    - ".test_durations-*"
    - ".testmondata-${CI_JOB_ID}"

pytest-full:
  extends: .pytest
  parallel: $full_parallel
  variables:
    CI_TEST_SCOPE: FULL
  rules:
    # Hotfix branches
    - if: $CI_COMMIT_BRANCH =~ $HOTFIX_BRANCH_REGEX
      when: on_success
    # Merge Trains
    - if: $CI_MERGE_REQUEST_EVENT_TYPE == "merge_train"
      when: on_success
    # MRs (labeled tia::disabled)
    - if: $CI_MERGE_REQUEST_LABELS =~ /tia::disabled/
      when: on_success
    # MRs, QA1, QA2 (with test-full-changes)
    - if: $CI_MERGE_REQUEST_EVENT_TYPE == "merged_result" || $CI_MERGE_REQUEST_EVENT_TYPE == "detached" || $CI_COMMIT_BRANCH == "qa1" || $CI_COMMIT_BRANCH == "qa2"
      when: on_success
      changes:
        *test-full-changes
    # Else
    - when: never

pytest-impacted:
  extends: .pytest
  parallel: $impacted_parallel
  variables:
    CI_TEST_SCOPE: IMPACTED
  rules:
    # Hotfix branches
    - if: $CI_COMMIT_BRANCH =~ $HOTFIX_BRANCH_REGEX
      when: never
    # MRs, QA1, QA2 (with test-full-changes)
    - if: $CI_MERGE_REQUEST_EVENT_TYPE == "merged_result" || $CI_MERGE_REQUEST_EVENT_TYPE == "detached" || $CI_COMMIT_BRANCH == "qa1" || $CI_COMMIT_BRANCH == "qa2"
      when: never
      changes:
        *test-full-changes
    # MRs
    - if: ($CI_MERGE_REQUEST_EVENT_TYPE == "merged_result" || $CI_MERGE_REQUEST_EVENT_TYPE == "detached") && $CI_MERGE_REQUEST_LABELS !~ /tia::disabled/
      when: on_success
    # QA1, QA2
    - if: $CI_COMMIT_BRANCH == "qa1" || $CI_COMMIT_BRANCH == "qa2"
      when: on_success
    # Else
    - when: never
"""
)


def main() -> None:
    mapping = {
        "dev_image": f"{gar_image_root}/monolith-dev:{commit_sha}",
        "artifact_job_id": (artifact_job_id := closest_ancestor_report_job()) or "",
        "artifact_job_id_env": ARTIFACT_JOB_ID_ENV,
        "full_parallel": FULL_PARALLEL,
        "impacted_parallel": _impacted_parallel(artifact_job_id),
        "pipeline_created_at_env": PIPELINE_CREATED_AT_ENV,
        "pipeline_created_at": ci_pipeline_created_at,
        "randomly_seed": int(time.time()),
    }
    mapping = {k: json.dumps(v) for k, v in mapping.items()}
    test_pipeline = TEST_TEMPLATE.safe_substitute(mapping)
    err(test_pipeline)

    with open(str(project_dir / ".gitlab-ci.test.yml"), "w") as f:
        f.write(test_pipeline)


def _impacted_parallel(artifact_job_id: Optional[str]) -> int:
    if artifact_job_id is None:
        return FULL_PARALLEL
    impacted_n, impacted_duration = _impacted_duration(artifact_job_id)

    # Target Latency: The target latency of impacted test pipelines (in seconds)
    # Actual Latency: https://app.datadoghq.com/dashboard/vvm-gkh-gxq/ci-test-platform?tile_focus=5176168549793718
    target_latency = 5 * 60

    # Approx Startup Overhead: A fixed approximation of how long it takes test jobs to start running tests (in seconds)
    # Actual Startup Overhead: https://app.datadoghq.com/dashboard/vvm-gkh-gxq/ci-test-platform?tile_focus=6574002437539796
    approx_startup_overhead = 70

    # Approx Collection + Fixture Overhead: A fixed approximation of how much time test jobs spend on collection and fixtures (in seconds)
    # Actual Collection + Fixture Overhead: https://app.datadoghq.com/dashboard/vvm-gkh-gxq/ci-test-platform?tile_focus=5124278831679903
    approx_collection_overhead = 175

    available_per_job = target_latency - (
        approx_startup_overhead + approx_collection_overhead
    )
    parallel = ceil(impacted_duration / available_per_job)
    safe_parallel = _impacted_safe_parallel(parallel)
    err(
        f"Scheduling impacted tests (n: {impacted_n}; duration: {impacted_duration:{DURATION}}s) across {safe_parallel} job(s)"
    )
    datadog.get().measure(
        "pipeline",
        generate_impacted_n=impacted_n,
        generate_impacted_duration_seconds=impacted_duration,
        generate_impacted_parallel=parallel,
        generate_impacted_safe_parallel=safe_parallel,
    )
    return safe_parallel


def _impacted_duration(artifact_job_id: str) -> tuple[int, float]:
    # Determine impacted tests
    with NamedTemporaryFile() as fp:
        fetch_artifact(".testmondata", fp.name, artifact_job_id)
        normalize_environment(fp.name)
        os.environ["TESTMON_DATAFILE"] = fp.name
        testmon_data = TestmonData(rootdir=source_dir)
        testmon_data.determine_stable()
        impacted_tests = testmon_data.unstable_test_names
        impacted_n = len(impacted_tests)

    # Fetch durations
    with NamedTemporaryFile() as fp:
        fetch_artifact(".test_durations", fp.name, artifact_job_id)
        durations = json.load(fp)

    # Pick impacted parallel scale
    avg = mean(durations.values())
    unknown_n = 0

    def duration_for(test_case: str) -> float:
        if (t := durations.get(test_case)) is not None:
            return t
        nonlocal unknown_n
        unknown_n += 1
        return avg

    impacted_duration = sum(duration_for(t) for t in impacted_tests)
    if unknown_n:
        err(
            f"falling back to average {int(avg * 1000)}ms for {unknown_n} tests with unknown duration"
        )
    return impacted_n, impacted_duration


def _impacted_safe_parallel(parallel: int) -> int:
    if parallel < 1:
        err(
            f"Impacted parallel estimated as {parallel}; raising to 1 to ensure estimation errors don't prevent test coverage."
        )
        return 1
    if parallel > FULL_PARALLEL:
        err(
            f"Impacted parallel estimated as {parallel}; lowering to {FULL_PARALLEL} to prevent unintended cost."
        )
        return FULL_PARALLEL
    return parallel
