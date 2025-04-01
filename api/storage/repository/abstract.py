from __future__ import annotations

import abc
from typing import Generic, Literal, Protocol, TypeVar, overload

from sqlalchemy.ext import baked


class Instance(Protocol):
    id: int


InstanceT = TypeVar("InstanceT", bound=Instance)


class AbstractRepository(abc.ABC, Generic[InstanceT]):
    bakery: baked.Bakery

    __slots__ = ("session",)

    def __init_subclass__(cls, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        cls.bakery = baked.bakery()  # type: ignore[call-arg,func-returns-value] # Missing positional argument "initial_fn" in call to "__call__" of "Bakery" #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None) #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None)

    @abc.abstractmethod
    def get(self, *, id: int) -> InstanceT | None:
        ...

    @overload
    def create(self, *, instance: InstanceT, fetch: Literal[False] = False) -> int:
        ...

    @overload
    def create(self, *, instance: InstanceT, fetch: Literal[True] = True) -> InstanceT:
        ...

    @overload
    def create(self, *, instance: InstanceT) -> InstanceT:
        ...

    @abc.abstractmethod
    def create(self, *, instance, fetch=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        ...

    @overload
    def update(self, *, instance: InstanceT, fetch: Literal[False] = False) -> int:
        ...

    @overload
    def update(
        self, *, instance: InstanceT, fetch: Literal[True] = True
    ) -> InstanceT | None:
        ...

    @overload
    def update(self, *, instance: InstanceT) -> InstanceT | None:
        ...

    @abc.abstractmethod
    def update(self, *, instance, fetch=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        ...

    @abc.abstractmethod
    def delete(self, *, id: int) -> int:
        ...
