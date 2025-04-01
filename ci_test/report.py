import json
import re
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from glob import iglob
from io import BytesIO
from typing import Any, NoReturn, cast
from zipfile import ZipFile

import requests
from dateutil.parser import isoparse
from junitparser import JUnitXml
from lxml import etree

from ci_test import datadog, testmondata
from ci_test.gitlab import fetch, fetch_json
from ci_test.log import err
from ci_test.settings import (
    MISSING_COVERAGE_LABEL,
    TRIGGER_JOB_NAME,
    TestScope,
    api_url,
    commit_branch,
    commit_sha,
    default_branch,
    gitlab_user_login,
    gl_headers,
    mr_event_type,
    mr_id,
    pipeline_id,
    pipeline_url,
    project_dir,
    project_id,
    source_dir,
)

TJobs = dict[TestScope, list[dict[str, Any]]]
coverage_rcfile = str(source_dir / ".coveragerc")
coverage_data_file = str(project_dir / ".coverage")
coverage_xml = str(project_dir / "coverage.xml")
job_pattern = re.compile(
    r"pytest-({}) \d+\/\d+".format("|".join(s.value.lower() for s in TestScope))
)


def main() -> None:
    jobs = _fetch_test_jobs()
    _fetch_artifacts(jobs)

    # Consider pipeline_scope FULL if any jobs are FULL
    pipeline_scope = TestScope.FULL if TestScope.FULL in jobs else TestScope.IMPACTED

    _combine_coverage()
    _report_coverage_xml()
    if pipeline_scope == TestScope.FULL:
        _report_coverage_total()
        _combine_test_durations()
        _combine_testmondata()
    report = _report_junit_xml()

    _report_end(pipeline_scope, jobs, report)


def _fetch_test_jobs() -> TJobs:
    jobs = defaultdict(list)
    p_id, p_url = _pick_pipeline_with_test_results()
    err(f"Searching for test jobs from the following pipeline: {p_url}")
    for job in fetch_json(f"pipelines/{p_id}/jobs?per_page=100"):
        match = job_pattern.search(job["name"])
        if match is not None:
            job_scope = TestScope(match.group(1).upper())
            jobs[job_scope].append(cast(dict[str, Any], job))
    if not jobs:
        raise ValueError("No test jobs were found.")
    for s, jj in jobs.items():
        err(f"Found {len(jj)} test jobs with scope {s.value}")
    return jobs


def _pick_pipeline_with_test_results() -> tuple[int, str]:
    if commit_branch == default_branch:
        # Promote test results from the merge train associated with this commit
        return _pick_newest_merge_train()
    # Promote test results from the current pipeline
    return _pick_child_test_pipeline(pipeline_id)


def _pick_newest_merge_train() -> tuple[int, str]:
    newest_train = None
    for mr in fetch_json(f"repository/commits/{commit_sha}/merge_requests"):
        mr_iid = mr["iid"]
        train_pipeline = fetch_json(f"merge_trains/merge_requests/{mr_iid}")["pipeline"]
        if newest_train is None:
            newest_train = train_pipeline
        else:
            newest_train = max(newest_train, train_pipeline, key=lambda p: p["id"])
    if newest_train is None:
        raise ValueError(
            "Unable to determine merge train associated with this commit; test results are unknown."
        )

    newest_train_id = cast(int, newest_train["id"])
    return _pick_child_test_pipeline(newest_train_id)


def _pick_child_test_pipeline(parent_pipeline_id: int) -> tuple[int, str]:
    bridge_jobs = fetch_json(f"pipelines/{parent_pipeline_id}/bridges")
    bridge = next(j for j in bridge_jobs if j["name"] == TRIGGER_JOB_NAME)
    pipeline = bridge["downstream_pipeline"]
    return (
        cast(int, pipeline["id"]),
        cast(str, pipeline["web_url"]),
    )


def _fetch_artifacts(jobs: TJobs) -> None:
    job_ids = [cast(int, j["id"]) for jj in jobs.values() for j in jj]

    # Fetch and extract job artifacts in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(_fetch_job_artifacts, job_ids))


def _fetch_job_artifacts(job_id: int) -> None:
    res = fetch(f"jobs/{job_id}/artifacts")
    zip = ZipFile(BytesIO(res.content))
    zip.extractall(project_dir)


def _combine_coverage() -> None:
    in_files = list(iglob(str(project_dir / ".coverage-*")))
    err(f"Merging coverage {', '.join(in_files)} into {coverage_data_file}")

    subprocess.run(
        [
            "coverage",
            "combine",
            "--keep",
            f"--rcfile={coverage_rcfile}",
            f"--data-file={coverage_data_file}",
        ]
        + in_files,
        cwd=source_dir,
        check=True,
    )


def _report_coverage_xml() -> None:
    err(f"Reporting coverage from {coverage_data_file} to {coverage_xml}")

    subprocess.run(
        [
            "coverage",
            "xml",
            f"--rcfile={coverage_rcfile}",
            f"--data-file={coverage_data_file}",
            "-o",
            coverage_xml,
            "--skip-empty",
        ],
        cwd=source_dir,
        check=True,
    )


def _report_coverage_total() -> None:
    # TODO: emit coverage total as a standard pipeline metric (i.e. !reference [.upload-coverage-to-datadog])
    with open(coverage_xml, "r") as f:
        report = etree.parse(f)
        line_rate = report.xpath("/coverage/@line-rate")[0]
    total_coverage = 100 * float(line_rate)
    print(f"TOTAL_COVERAGE:{total_coverage}")  # noqa


def _combine_test_durations() -> None:
    in_files = list(iglob(str(project_dir / ".test_durations*")))
    out_file = str(project_dir / ".test_durations")
    err(f"Merging test durations {', '.join(in_files)} into {out_file}")

    durations = dict()
    for durations_path in in_files:
        with open(durations_path, "r") as f:
            durations.update(json.load(f))
    with open(out_file, "w") as f:
        json.dump(durations, f)


def _combine_testmondata() -> None:
    in_files = [
        f
        for f in iglob(str(project_dir / ".testmondata-*"))
        if not (f.endswith("-shm") or f.endswith("-wal"))
    ]
    out_file = str(project_dir / ".testmondata")
    env = "default"
    err(f"Merging testmondata env:{env} of {', '.join(in_files)} into {out_file}")

    testmondata.merge(
        input_datafiles=in_files,
        output_datafile=out_file,
        environment_name=env,
        rootdir=str(source_dir),
    )


def _report_junit_xml() -> JUnitXml:
    in_files = list(iglob(str(project_dir / "report-*.xml")))
    out_file = str(project_dir / "report.xml")
    err(f"Merging junit reports {', '.join(in_files)} into {out_file}")

    result = JUnitXml()
    for path in in_files:
        result += JUnitXml.fromfile(path)

    result.update_statistics()
    result.write(out_file)
    return result


def _report_end(pipeline_scope: TestScope, jobs: TJobs, report: JUnitXml) -> NoReturn:
    suite_failed_n = report.failures + report.errors
    suite_failed = bool(suite_failed_n)
    test_report_url = f"{pipeline_url}/test_report"

    # Report max latency across jobs by scope
    for scope, scope_jobs in jobs.items():
        scope_latencies = (
            (cast(float, job["duration"]), job["finished_at"]) for job in scope_jobs
        )
        duration, finished_at = max(scope_latencies, key=lambda l: l[0])
        timestamp = isoparse(finished_at)
        datadog.gauge_latency(duration, timestamp, scope, suite_failed)

    if mr_event_type is not None:
        datadog.get().tag(
            "pipeline", **{"gitlab.merge_request_event_type": mr_event_type}
        )

    if mr_event_type == "merge_train" and pipeline_scope == TestScope.FULL:
        datadog.count_merge_trains(suite_failed)
        if suite_failed:
            datadog.get().tag("pipeline", tia_missing_coverage="true")
            note = (
                f":steam_locomotive: @{gitlab_user_login} please address additional [test failures]({test_report_url}) caught by the merge train pipeline. "
                f'Your MR has been labeled ~"{MISSING_COVERAGE_LABEL}" so that subsequent MR pipelines provide full coverage.\n\n'
                "_[Click here](https://app.datadoghq.com/dashboard/8as-a5a-cdd/monolith-ci-tests?fromUser=false&tile_focus=2976857255361460) to learn more about about Test Impact Analysis (TIA)_"
            )
            requests.post(
                f"{api_url}/projects/{project_id}/merge_requests/{mr_id}/notes",
                headers=gl_headers,
                json={"body": note},
            ).raise_for_status()
            requests.put(
                f"{api_url}/projects/{project_id}/merge_requests/{mr_id}",
                headers=gl_headers,
                json={"add_labels": MISSING_COVERAGE_LABEL},
            ).raise_for_status()

    if suite_failed:
        ansi_red = "\033[91m"
        ansi_reset = "\033[0m"
        suffix = "s" if suite_failed_n > 1 else ""
        cta1 = f"Please address {suite_failed_n} test failure{suffix} detected in this pipeline:"
        cta2 = "If you believe this is a transient issue, please create a new pipeline from your MR."
        border = "=" * max(len(cta1), len(cta2))
        err(f"{ansi_red}{border}{ansi_reset}")
        err(f"{ansi_red}{cta1}{ansi_reset}")
        err(f"{ansi_red}{test_report_url}{ansi_reset}")
        err(cta2)
        err(f"{ansi_red}{border}{ansi_reset}")
        sys.exit(100)
    sys.exit(0)
