from dateutil.parser import parse

from utils.age import calculate_years_between_dates


def test_calculate_years_between_dates():
    start = parse("02/29/1984")
    end = parse("03/01/2021")
    years = calculate_years_between_dates(start, end)
    assert years == 37
