import os
from enum import Enum
from pathlib import Path
from typing import Optional, cast


class TestScope(Enum):
    FULL = "FULL"
    IMPACTED = "IMPACTED"


def _get_int(name: str, default: Optional[int] = None) -> int:
    val = os.getenv(name, default)
    if val is None:
        raise ValueError(f"Expected env var {name} to be set.")
    return int(val)


ARTIFACT_JOB_ID_ENV = "CI_TEST_ARTIFACT_JOB_ID"
DURATION = ".2f"
FLAKY_MAX_RUNS = 5  # The number of times failed tests will be retried during each iteration of the retry loop
MAX_RETRYABLE_FAILED_RATIO = (
    0.2  # The highest ratio of test failure for which the retry loop will be performed
)
MISSING_COVERAGE_LABEL = (
    "tia::disabled"  # The label used to trigger full test runs on MR pipelines
)
PIPELINE_CREATED_AT_ENV = "CI_TEST_PIPELINE_CREATED_AT"
TRIGGER_JOB_NAME = "tests"  # NOTE: matches the trigger job defined in the app pipeline
api_url = os.getenv("CI_API_V4_URL", "https://gitlab.com/api/v4")
ci_pipeline_created_at = os.getenv("CI_PIPELINE_CREATED_AT")
commit_branch = os.getenv("CI_COMMIT_BRANCH")
commit_sha = os.getenv("CI_COMMIT_SHA")
default_branch = os.getenv("CI_DEFAULT_BRANCH")
dd_headers = {"DD-API-KEY": os.getenv("DD_API_KEY")}
gar_image_root = os.getenv("GAR_IMAGE_ROOT")
gitlab_user_login = os.getenv("GITLAB_USER_LOGIN")
gl_headers = {"PRIVATE-TOKEN": os.getenv("GITLAB_TOKEN")}
job_id = os.getenv("CI_JOB_ID", "job-id")
job_started_at = os.getenv("CI_JOB_STARTED_AT", "2022-01-31T16:47:55Z")
merge_request_base_sha = os.getenv("CI_MERGE_REQUEST_TARGET_BRANCH_SHA") or os.getenv(
    "CI_MERGE_REQUEST_DIFF_BASE_SHA"
)
mr_event_type = os.getenv("CI_MERGE_REQUEST_EVENT_TYPE")
mr_id = os.getenv("CI_MERGE_REQUEST_IID")
node_index = _get_int("CI_NODE_INDEX", 1)
node_total = _get_int("CI_NODE_TOTAL", 1)
pipeline_created_at = cast(str, os.getenv(PIPELINE_CREATED_AT_ENV))
pipeline_id = _get_int("CI_PIPELINE_ID")
pipeline_url = os.getenv("CI_PIPELINE_URL")
project_dir = Path(os.getenv("CI_PROJECT_DIR", os.getcwd()))
project_id = os.getenv("CI_PROJECT_ID", "48434451")
source_dir = Path(os.getenv("CI_TEST_SOURCE_DIR", project_dir))
test_scope = TestScope(os.getenv("CI_TEST_SCOPE", "FULL"))
