from __future__ import annotations

import datetime
import inspect
import os
import time
import unittest
from typing import Any, Callable

import dateutil.parser
import time_machine


def setutc():
    os.environ["TZ"] = "UTC"
    time.tzset()


class freeze_time(time_machine.travel):
    def __init__(self, time_to_freeze: str | datetime.date, *, tick: bool = False):
        dt = (
            dateutil.parser.parse(time_to_freeze)
            if isinstance(time_to_freeze, str)
            else time_to_freeze
        )
        if not isinstance(dt, datetime.datetime):
            dt = datetime.datetime(
                dt.year, dt.month, dt.day, tzinfo=datetime.timezone.utc
            )
        # Assume UTC for naive time
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        super().__init__(dt, tick=tick)

    def __call__(self, wrapped: Callable) -> Callable:
        if inspect.isclass(wrapped) and not issubclass(wrapped, unittest.TestCase):
            for name, member in inspect.getmembers(wrapped, is_wrappable):
                try:
                    setattr(wrapped, name, self.__call__(member))
                except (AttributeError, TypeError):
                    # Sometimes we can't set this for built-in types and custom callables
                    continue
            return wrapped
        return super().__call__(wrapped=wrapped)


def is_wrappable(obj: Any) -> bool:
    if not inspect.ismethod(obj):
        return False
    if obj.__name__.startswith("_"):
        return False
    if isinstance(obj, staticmethod):
        return False
    return True
