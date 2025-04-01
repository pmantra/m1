import enum
from datetime import datetime, timedelta
from typing import List, Optional

from modules.logger import logger as log


class Schedule(str, enum.Enum):
    FOUR_TIMES_DAILY = "four times daily"
    TWICE_DAILY = "twice daily"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"


def _is_within_window(
    current_time: datetime, target_time: datetime, window_minutes: int = 20
) -> bool:
    """
    Check if current_time is within window_minutes of target_time.
    Only allows times equal to or after target_time.

    Args:
        current_time: The time to check
        target_time: The base time to compare against
        window_minutes: The number of minutes after target_time to allow (default 20)

    Returns:
        bool: True if current_time is within the window, False otherwise
    """
    window = timedelta(minutes=window_minutes)
    return target_time <= current_time <= target_time + window


def _get_today_schedule_times(
    task_schedule: str, base_hours: list[int], reference_date: Optional[datetime] = None
) -> list[datetime]:
    """Get the scheduled times for today based on the schedule type"""
    current_time = reference_date if reference_date is not None else datetime.utcnow()
    today = current_time.replace(hour=0, minute=0, second=0, microsecond=0)

    if task_schedule == Schedule.FOUR_TIMES_DAILY.value:
        # Use all available hours, even if fewer than 4
        return [today.replace(hour=hour) for hour in base_hours]
    elif task_schedule == Schedule.TWICE_DAILY.value:
        if len(base_hours) >= 2:
            # Use first and last hours for twice daily
            return [
                today.replace(hour=base_hours[0]),
                today.replace(hour=base_hours[-1]),
            ]
        else:
            # If only one hour available, use it
            return [today.replace(hour=base_hours[0])]
    elif task_schedule == Schedule.DAILY.value:
        # Use the last hour for daily schedules
        return [today.replace(hour=base_hours[-1])]
    elif task_schedule == Schedule.WEEKLY.value:
        # Run only on Mondays at the last hour
        if current_time.weekday() == 0:  # Monday is 0
            return [today.replace(hour=base_hours[-1])]
    elif task_schedule == Schedule.BIWEEKLY.value:
        # Run on days 1,15,29 at the last hour
        if current_time.day in [1, 15, 29]:
            return [today.replace(hour=base_hours[-1])]
    return []


def task_scheduled_to_run(
    task_schedule: str, dag_schedule: str, current_time: Optional[datetime] = None
) -> bool:
    """
    Determines if a task is scheduled to run based on the provided task schedule type
    and a cron-based DAG schedule.

    Considers a time window around the scheduled time to account for slight timing variations.

    Args:
        task_schedule: The type of schedule for the task (e.g., "four times daily", "twice daily", "daily")
        dag_schedule: The cron expression that defines when the DAG runs (e.g., "0 18 * * *" or "0 0,18 * * *")
        current_time: Optional datetime to use for testing, defaults to utcnow()

    Returns:
        bool: True if the task is scheduled to run at the current time
    """
    try:
        # Parse hours from cron schedule (e.g., "0 18 * * *" -> [18] or "0 0,18 * * *" -> [0, 18])
        hours = [int(h) for h in dag_schedule.split()[1].split(",")]
    except (IndexError, ValueError):
        log.error(f"Invalid cron expression: {dag_schedule}")
        return False

    current_time = current_time if current_time is not None else datetime.utcnow()
    schedule_times = _get_today_schedule_times(
        task_schedule, hours, reference_date=current_time
    )

    log.info(
        f"Evaluating schedule - Task schedule: {task_schedule}, "
        f"Base DAG schedule: {dag_schedule}, "
        f"Schedule times: {schedule_times}, "
        f"Current time (UTC): {current_time}"
    )

    # Check if we're within window of any scheduled time
    for schedule_time in schedule_times:
        if _is_within_window(current_time, schedule_time):
            return True

    # Also check tomorrow's first schedule (for times near midnight)
    tomorrow = current_time + timedelta(days=1)
    tomorrow_schedule = _get_today_schedule_times(
        task_schedule, hours, reference_date=tomorrow
    )

    # For daily schedules, check if we're within window of tomorrow's scheduled time
    if task_schedule == Schedule.DAILY.value:
        if tomorrow_schedule:
            if _is_within_window(current_time, tomorrow_schedule[0]):
                return True
    elif task_schedule in [Schedule.FOUR_TIMES_DAILY.value, Schedule.TWICE_DAILY.value]:
        # For four times daily and twice daily schedules, check tomorrow's first scheduled time
        if tomorrow_schedule and _is_within_window(current_time, tomorrow_schedule[0]):
            return True

    return False


def should_run_task(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    task_instance,
    payer: str,
    schedule: str,
    job_type: str,
    default_payers: List[str],
    **kwargs,
) -> bool:
    """
    Determines if a task should run based on the payer's schedule and configuration.

    Args:
        task_instance: The Airflow task instance
        payer: The payer to check
        schedule: The schedule type for the payer
        job_type: The type of job being run (e.g., "file_generation", "data_sourcing")
        default_payers: List of default payers to use if Launch Darkly config is empty
        **kwargs: Additional keyword arguments from the Airflow context

    Returns:
        bool: True if the task should run, False otherwise
    """
    # check launch darkly config
    ld_config = task_instance.xcom_pull(task_ids="get_launchdarkly_config")
    enabled_payers = ld_config.get("enabled_payers", default_payers)
    log.info(f"List of enabled payers for this job: {enabled_payers}")
    if payer not in enabled_payers:
        log.info(
            f"Payer {payer} not enabled in Launch Darkly for job {job_type}. Skipping downstream task."
        )
        return False
    payers_list = kwargs["dag_run"].conf.get("payers", [])

    # check if task is on schedule or being manually run off schedule
    if not task_scheduled_to_run(
        schedule, kwargs["dag"].schedule_interval
    ) and not kwargs["dag_run"].conf.get("run_off_schedule"):
        log.info(
            f"Task not currently scheduled to run, and is not set to run off schedule. Payer {payer} has schedule {schedule}. Skipping downstream task for job {job_type}."
        )
        return False

    # check if payer should be run based on payer dag params (default is none, so run all payers in this case)
    if not payers_list:
        log.info(
            f"No params were passed into DAG. Running tasks for all payers enabled in Launch Darkly. Running downstream task for payer {payer} job {job_type}."
        )
        return True
    # if payer params are passed in, skip payer tasks that are not in the payers list
    if payer and payer not in payers_list:
        log.info(
            f"Payer {payer} not in payers_list {payers_list} for job {job_type}. Skipping downstream task."
        )
        return False

    log.info(
        f"Payer {payer} in payers_list {payers_list} and task is scheduled to run {schedule}. Running downstream task for payer {payer} job {job_type}."
    )
    return True
