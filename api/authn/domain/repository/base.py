from __future__ import annotations

import functools

import sqlalchemy

from authn.models import user
from storage.repository import abstract, base

__all__ = ("BaseUserRepository",)


class BaseUserRepository(base.BaseRepository[abstract.InstanceT]):
    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sqlalchemy.Table:
        return user.User.__table__

    @classmethod
    @functools.lru_cache(maxsize=1)
    def table_name(cls) -> str:
        return user.User.__tablename__

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def table_columns() -> tuple[sqlalchemy.Column, ...]:
        return ()
