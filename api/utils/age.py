from datetime import datetime

from dateutil.relativedelta import relativedelta


def calculate_age(dob: datetime) -> int:
    return calculate_years_between_dates(dob, datetime.now())


def calculate_years_between_dates(start: datetime, end: datetime) -> int:
    return relativedelta(end, start).years
