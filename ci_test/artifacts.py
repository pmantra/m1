import os
from typing import Optional

from ci_test.gitlab import fetch, fetch_json
from ci_test.log import err
from ci_test.settings import (
    ARTIFACT_JOB_ID_ENV,
    commit_sha,
    default_branch,
    merge_request_base_sha,
)

ARTIFACT_JOB_NAMES = ("combine-pytest", "test-report")
MAX_COMMIT_ANCESTOR_LOOKBACK = 10


def closest_ancestor_report_job() -> Optional[str]:
    if (merge_base := merge_request_base_sha) is None:
        merge_base = fetch_json(
            f"repository/merge_base?refs[]={commit_sha}&refs[]={default_branch}"
        )["id"]
    base_commits = fetch_json(
        f"repository/commits?ref_name={merge_base}&first_parent=true&per_page{MAX_COMMIT_ANCESTOR_LOOKBACK}"
    )
    for base_commit in base_commits:
        base_commit_id = base_commit["id"]
        pipelines = fetch_json(f"pipelines?sha={base_commit_id}&ref={default_branch}")
        for p in pipelines:
            p_id = p["id"]
            jobs = fetch_json(f"pipelines/{p_id}/jobs?scope=success&per_page=100")
            combine_job = next(
                (j for j in jobs if j["name"] in ARTIFACT_JOB_NAMES), None
            )
            if combine_job is not None:
                err(
                    f"== Combine artifacts will be fetched from the following job: {combine_job['web_url']}"
                )
                return str(combine_job["id"])
    err("== Combine job not found; falling back to default behavior.")
    return None


def fetch_artifact(
    artifact: str, filepath: str, artifact_job_id: Optional[str] = None
) -> None:
    if artifact_job_id is None:
        artifact_job_id = os.getenv(ARTIFACT_JOB_ID_ENV)
    if not artifact_job_id:
        err(
            f"== Combine job for fetching '{artifact}' not found; falling back to default behavior."
        )
        return

    res = fetch(f"jobs/{artifact_job_id}/artifacts/{artifact}")
    with open(filepath, "wb") as f:
        f.write(res.content)
