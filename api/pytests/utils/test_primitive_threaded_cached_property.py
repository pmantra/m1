from datetime import date, datetime
from unittest import mock

import pytest

from pytests.factories import MemberFactory
from utils.primitive_threaded_cached_property import (
    is_primitive,
    primitive_threaded_cached_property,
)


def test_primitive_threaded_cached_property_simple():

    today_date: date = date.today()
    today_datetime: datetime = datetime.utcnow()

    class foo:
        def __init__(self) -> None:
            self.func_calls = 0

        @primitive_threaded_cached_property
        def int_func(self) -> int:
            self.func_calls += 1
            return 1

        @primitive_threaded_cached_property
        def str_func(self) -> str:
            self.func_calls += 1
            return ""

        @primitive_threaded_cached_property
        def float_func(self) -> float:
            self.func_calls += 1
            return 0.0

        @primitive_threaded_cached_property
        def bool_func(self) -> bool:
            self.func_calls += 1
            return True

        @primitive_threaded_cached_property
        def none_func(self) -> None:
            self.func_calls += 1
            return None

        @primitive_threaded_cached_property
        def date_func(self) -> date:
            self.func_calls += 1
            return today_date

        @primitive_threaded_cached_property
        def datetime_func(self) -> datetime:
            self.func_calls += 1
            return today_datetime

    bar = foo()
    assert bar.int_func == 1
    assert bar.func_calls == 1
    assert bar.int_func == 1
    assert bar.func_calls == 1

    assert bar.str_func == ""
    assert bar.func_calls == 2
    assert bar.str_func == ""
    assert bar.func_calls == 2

    assert bar.float_func == 0.0
    assert bar.func_calls == 3
    assert bar.float_func == 0.0
    assert bar.func_calls == 3

    assert bar.bool_func is True
    assert bar.func_calls == 4
    assert bar.bool_func is True
    assert bar.func_calls == 4

    assert bar.none_func is None
    assert bar.func_calls == 5
    assert bar.none_func is None
    assert bar.func_calls == 5

    assert bar.date_func == today_date
    assert bar.func_calls == 6
    assert bar.date_func == today_date
    assert bar.func_calls == 6

    assert bar.datetime_func == today_datetime
    assert bar.func_calls == 7
    assert bar.datetime_func == today_datetime
    assert bar.func_calls == 7


@mock.patch(
    "utils.primitive_threaded_cached_property.should_raise_on_non_primitive",
    return_value=True,
)
def test_primitive_threaded_cached_property_dict(
    mock_should_raise_on_non_primitive,
):
    member = MemberFactory.create()

    class foo:
        @primitive_threaded_cached_property
        def list_func(self) -> list:
            return []

        @primitive_threaded_cached_property
        def orm_func(self):
            return member

    bar = foo()

    with pytest.raises(ValueError):
        bar.list_func

    with pytest.raises(ValueError):
        bar.orm_func


@mock.patch(
    "utils.primitive_threaded_cached_property.should_raise_on_non_primitive",
    return_value=False,
)
def test_primitive_threaded_cached_property_dict_flag_off(
    mock_should_raise_on_non_primitive,
):
    member = MemberFactory.create()

    class foo:
        @primitive_threaded_cached_property
        def list_func(self) -> list:
            return []

        @primitive_threaded_cached_property
        def orm_func(self):
            return member

    bar = foo()
    assert bar.list_func == []
    assert bar.orm_func == member


def test_is_primitive_dict():

    empty_dict = {}
    primitive_dict = {
        1: 1,
        "foo": "bar",
        "date": date.today(),
        "bool": True,
    }
    nested_primitive_dict = {
        "primitive_dict": primitive_dict,
    }
    invalid_dict = {
        "key": MemberFactory.create(),
    }

    assert is_primitive(empty_dict) is True
    assert is_primitive(primitive_dict) is True
    assert is_primitive(nested_primitive_dict) is True

    assert is_primitive(invalid_dict) is False
