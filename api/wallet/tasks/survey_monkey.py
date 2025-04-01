import datetime

from common import stats
from tasks.queues import job
from utils.log import logger
from utils.survey_monkey import update_webhook_survey_ids

log = logger(__name__)

metric_name = "api.wallet.tasks.survey_monkey_add_survey_to_webhook"


@job
def add_survey_ids_to_webhook():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    This updates the survey ids within the SurveyMonkey webhook.
    """

    job_start_time = datetime.datetime.utcnow()

    log.info(
        "survey_monkey_webhook: Starting job to add survey ids to survey monkey webhook."
    )

    success = update_webhook_survey_ids()

    time_to_complete_job = datetime.datetime.utcnow() - job_start_time

    log.info(
        "survey_monkey_webhook: Completing job to add survey ids to survey monkey webhook."
    )

    stats.histogram(
        metric_name,
        pod_name=stats.PodNames.PAYMENTS_POD,
        metric_value=time_to_complete_job.total_seconds(),
    )

    tags = [f"success:{success}"]
    stats.increment(
        metric_name=metric_name,
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=tags,
    )
