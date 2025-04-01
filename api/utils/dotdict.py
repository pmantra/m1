from __future__ import annotations

from typing import Any


class DotDict(dict):
    """
    dot.notation access to dictionary attributes
    Example:
    dd = DotDict({"foo": {"bar": "baz"}})
    dd.foo.bar == "baz"
    """

    __getattr__ = dict.get
    # we are explicitly overriding to create the desired behavior so ignore
    # the assignment type error
    __delattr__ = dict.__delitem__  # type: ignore[assignment]

    def __init__(self, __dict: dict | None = None):
        if __dict is None:
            __dict = {}

        super().__init__(__dict)
        for k, v in __dict.items():
            self.__setattr__(k, v)

    def __setattr__(self, __name: str, __value: Any) -> None:
        if isinstance(__value, dict):
            __value = DotDict(__value)
        return super().__setitem__(__name, __value)
