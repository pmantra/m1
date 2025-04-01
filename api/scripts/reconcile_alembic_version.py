import argparse
import json
import os
import pathlib
from time import sleep

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from kubernetes import (  # type: ignore[attr-defined] # Module "kubernetes" has no attribute "client" #type: ignore[attr-defined] # Module "kubernetes" has no attribute "config"
    client,
    config,
)

from utils.log import logger

TRIGGER_JOB_NAME = "trigger-mono-alembic-reconcile"
CRON_JOB_NAME = "mono-alembic-reconcile-template"
NAMESPACE = "mono"
RECONCILE_ENV_VAR_NAME = "ALEMBIC_RECONCILE_TARGET"
MAX_DOWNGRADES = 5

log = logger(__name__)


def reconcile_alembic_version() -> None:

    # fetch incoming revisions from environment (created by trigger)
    log.info("Fetching incoming alembic history")
    incoming_alembic_revisions = os.environ[RECONCILE_ENV_VAR_NAME].split()

    # fetch revisions using local versions directory
    local_alembic_revisions = _get_alembic_history()

    # try and find matching revision
    for _downgrade_count, revision in enumerate(local_alembic_revisions):
        if revision in incoming_alembic_revisions:
            log.info("Found shared revision history.", revision=revision)
            break
        log.info("Local revision eligible for downgrade.", revision=revision)
    else:
        # theoretical edge-case where we find no shared revision history
        log.warning(
            "No shared revision history found. Reconcile requires downgrading to base."
        )
        revision = "base"

    if _downgrade_count > MAX_DOWNGRADES:
        raise ValueError(
            f"Manual DB reconcile required: max downgrades ({MAX_DOWNGRADES}) has been exceeded: {_downgrade_count}"
        )

    if _downgrade_count > 0:
        log.info(
            "Downgrading DB.",
            revision=revision,
            downgrade_count=_downgrade_count,
        )
        _alembic_downgrade(revision)


def trigger_reconcile() -> None:

    # kubernetes setup
    config.load_incluster_config()
    batch_v1 = client.BatchV1Api()

    # get alembic history
    alembic_revisions = _get_alembic_history()
    alembic_revision_str = " ".join(alembic_revisions)

    # fetch job spec from existing k8s cronjob
    job_spec = _get_reconcile_job_template(batch_v1)

    # patch job spec
    _patch_job_spec(job_spec, alembic_revision_str)

    # create new k8s job with spec we patched
    _create_k8s_job(batch_v1, job_spec)

    # wait and pass through result
    status = _get_job_status(batch_v1)
    if status.failed is not None:
        log.info("Trigger job failed", job_name=TRIGGER_JOB_NAME)
        exit(1)

    log.info("Trigger job succeeded", job_name=TRIGGER_JOB_NAME)


def _get_alembic_history() -> list:
    # get alembic history
    log.info("Getting alembic history")
    DIR = pathlib.Path(__file__).resolve()
    alembic_ini_file = DIR.parent.parent / "alembic.ini"
    default_cfg = Config(alembic_ini_file)
    script = ScriptDirectory.from_config(default_cfg)
    return [rev.revision for rev in script.walk_revisions()]


def _alembic_downgrade(downgrade_arg: str) -> None:
    # alembic downgrade
    DIR = pathlib.Path(__file__).resolve()
    alembic_ini_file = DIR.parent.parent / "alembic.ini"
    default_cfg = Config(alembic_ini_file)
    command.downgrade(default_cfg, downgrade_arg)


def _get_reconcile_job_template(batch_v1: client.BatchV1Api) -> dict:
    # fetch our job template from existing cronjob
    log.info("Fetching k8s job template")
    ret = batch_v1.list_namespaced_cron_job(
        namespace=NAMESPACE, pretty=True, _preload_content=False
    )
    cron_job_list = json.loads(ret.data)
    job_spec = None
    for cron_job in cron_job_list["items"]:
        if CRON_JOB_NAME == cron_job["metadata"]["name"]:
            job_spec = cron_job["spec"]["jobTemplate"]["spec"]
            return job_spec

    # this will be the case on the first migration. warn and exit
    log.warning("Unable to find existing cronjob spec")
    exit(0)


def _patch_job_spec(job_spec: dict, alembic_revisions: str) -> None:
    # patch job spec
    log.info("Patching job spec")
    job_spec["suspend"] = False
    job_spec["template"]["spec"]["containers"][0]["env"].append(
        {"name": RECONCILE_ENV_VAR_NAME, "value": alembic_revisions}
    )


def _create_k8s_job(batch_v1: client.BatchV1Api, job_spec: dict) -> None:
    # create new job
    log.info("Creating new k8s job to trigger reconcile")
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.models.V1ObjectMeta(name=TRIGGER_JOB_NAME),
        spec=job_spec,
    )
    batch_v1.create_namespaced_job(NAMESPACE, job)


def _get_job_status(
    batch_v1: client.BatchV1Api,
) -> client.models.v1_job_status.V1JobStatus:
    job_completed = False
    while not job_completed:
        log.info("Waiting for k8s job to finish...")
        api_response = batch_v1.read_namespaced_job_status(
            name=TRIGGER_JOB_NAME, namespace=NAMESPACE
        )
        if (
            api_response.status.succeeded is not None
            or api_response.status.failed is not None
        ):
            job_completed = True
        sleep(2)
    return api_response.status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reconcile alembic version between db revision and source revision",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("command", choices=["trigger", "reconcile"])

    args = parser.parse_args()
    argconfig = vars(args)

    if argconfig["command"] == "trigger":
        trigger_reconcile()
    else:
        reconcile_alembic_version()
