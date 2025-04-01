from typing import Optional

import croniter  # type: ignore[import-untyped]

from utils.log import logger

log = logger(__name__)

MONTH_NAME = {
    "1": "January",
    "2": "February",
    "3": "March",
    "4": "April",
    "5": "May",
    "6": "June",
    "7": "July",
    "8": "August",
    "9": "September",
    "10": "October",
    "11": "November",
    "12": "December",
}

DAYS_OF_WEEK = {
    "0": "Sunday",
    "1": "Monday",
    "2": "Tuesday",
    "3": "Wednesday",
    "4": "Thursday",
    "5": "Friday",
    "6": "Saturday",
}


def validate_cron_expression(cron_expression: str) -> None:
    croniter.croniter(cron_expression)


def generate_user_friendly_report_cadence(
    organization_id: int, report_cadence_in_cron_format: Optional[str]
) -> Optional[str]:
    if report_cadence_in_cron_format is None:
        return None

    try:
        # croniter will raise ValueError if expression is invalid
        validate_cron_expression(report_cadence_in_cron_format)
    except ValueError:
        log.error(
            "The cron expression of the invoice cadence is invalid",
            organization_id=organization_id,
            invoice_cadence=report_cadence_in_cron_format,
        )
        return None

    parts = report_cadence_in_cron_format.split()

    # Extract the parts we're interested in (ignoring minute and hour)
    day = parts[2]
    month = parts[3]
    day_of_week = parts[4]

    # Translate the month and day of week
    day_str = "every day" if day == "*" else f"on day {day}"
    month_str = "every month" if month == "*" else MONTH_NAME.get(month, "")

    day_of_week_str = ""
    if day_of_week != "*":
        if day_str == "every day":
            day_str = ""
        if month_str == "every month":
            month_str = ""
        day_of_week_str = f'every {DAYS_OF_WEEK.get(day_of_week, "")}'

    components = [day_str, month_str, day_of_week_str]
    return ", ".join([s for s in components if s])
