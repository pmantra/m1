from __future__ import annotations

import abc
import dataclasses
import functools
from typing import Any, List, Literal, Mapping, overload

import inflection
import sqlalchemy.orm

from storage import connection
from storage.repository import abstract

__all__ = ("BaseRepository",)


class BaseRepository(abstract.AbstractRepository[abstract.InstanceT]):
    model: type[abstract.InstanceT]
    table: sqlalchemy.Table
    metadata: sqlalchemy.MetaData = connection.db.metadata

    def __init_subclass__(cls, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        cls.table = cls.make_table()

    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        is_in_uow: bool = False,
    ):
        if is_in_uow and session is None:
            # if is_in_uow, a session must be passed in
            raise ValueError("Session must be provided when is_in_uow flag is True")
        self.scoped = session or connection.db.session
        # our usage of repository pattern has messed up so requiring callers to explicitly declare uow pattern
        self._is_in_uow = is_in_uow
        self._session = None
        self.from_obj = self.make_from_obj()

    @property
    def is_in_uow(self) -> bool:
        return self._is_in_uow

    @property
    def session(self) -> sqlalchemy.orm.Session | sqlalchemy.orm.scoping.ScopedSession:
        if self._is_in_uow:
            return self.scoped

        if self._session is None or not self._session.is_active:
            self._session = self.scoped()
        return self._session

    def get(self, *, id: int) -> abstract.InstanceT | None:
        where = self.table.c.id == id
        result = self.execute_select(where=where, from_obj=self.from_obj)  # type: ignore[arg-type] # Argument "from_obj" to "execute_select" of "BaseRepository" has incompatible type "Optional[Selectable]"; expected "Selectable"
        row = result.first()
        return self.deserialize(row=row)

    def create(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, *, instance: abstract.InstanceT, fetch: Literal[True, False] = True
    ):
        values = self.instance_to_values(instance=instance)
        insert = self.table.insert(values=values)
        result = self.session.execute(insert)
        if not self._is_in_uow:
            self.session.commit()
        # MySQL doesn't support RETURNING, so we use this...
        #  https://docs.sqlalchemy.org/en/13/core/connections.html#sqlalchemy.engine.ResultProxy.inserted_primary_key
        pk: int = result.inserted_primary_key[0]
        return self.affected_or_instance(affected=1, id=pk, fetch=fetch)

    def update(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, *, instance: abstract.InstanceT, fetch: Literal[True, False] = True
    ):
        values = self.instance_to_values(instance=instance)
        update = self.table.update(
            whereclause=self.table.c.id == instance.id, values=values
        )
        result = self.session.execute(update)
        if not self._is_in_uow:
            self.session.commit()
        affected: int = result.rowcount
        return self.affected_or_instance(affected=affected, id=instance.id, fetch=fetch)

    def delete(self, *, id: int) -> int:
        delete = self.table.delete(whereclause=self.table.c.id == id)
        result = self.session.execute(delete)
        if not self._is_in_uow:
            self.session.commit()
        affected: int = result.rowcount
        return affected

    def all(self) -> list[abstract.InstanceT]:
        result = self.execute_select()
        entries = result.fetchall()
        return [self.deserialize(row=row) for row in entries]

    def execute_select(
        self,
        *,
        where: sqlalchemy.sql.ClauseElement = None,  # type: ignore[assignment] # Incompatible default for argument "where" (default has type "None", argument has type "ClauseElement")
        from_obj: sqlalchemy.sql.Selectable = None,  # type: ignore[assignment] # Incompatible default for argument "from_obj" (default has type "None", argument has type "Selectable")
    ) -> sqlalchemy.engine.ResultProxy:
        columns = self.select_columns()
        select = sqlalchemy.select(
            columns=columns, whereclause=where, from_obj=from_obj
        )
        result = self.session.execute(select)
        return result

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_from_obj(cls) -> sqlalchemy.sql.Selectable | None:
        return None

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sqlalchemy.Table:
        table_name = cls.table_name()
        table_columns = cls.table_columns()
        identity_columns = cls.identity_columns()
        return sqlalchemy.Table(
            table_name,
            cls.metadata,
            *table_columns,
            *identity_columns,
            info=dict(bind_key="default"),
        )

    @classmethod
    def identity_columns(cls) -> tuple[sqlalchemy.Column, ...]:
        return (
            sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
            sqlalchemy.Column(
                "created_at",
                sqlalchemy.TIMESTAMP,
                nullable=False,
                server_default=sqlalchemy.FetchedValue(),
            ),
            sqlalchemy.Column(
                "modified_at",
                sqlalchemy.TIMESTAMP,
                nullable=False,
                server_default=sqlalchemy.FetchedValue(),
                server_onupdate=sqlalchemy.FetchedValue(for_update=True),
            ),
        )

    @classmethod
    def table_name(cls) -> str:
        return inflection.underscore(cls.model.__name__)

    @classmethod
    def instance_to_values(cls, instance: abstract.InstanceT) -> dict[str, Any]:
        return cls.filter_fetched_values(**dataclasses.asdict(instance))  # type: ignore[call-overload] # No overload variant of "asdict" matches argument type "abstract.InstanceT"

    @classmethod
    def filter_fetched_values(cls, **values: Any) -> dict[str, Any]:
        out = {}
        for name, value in values.items():
            column: sqlalchemy.Column | None = cls.table.columns.get(name)
            # Input parameter may not be a column.
            if column is None:
                out[name] = value
                continue
            # Filter columns with a server default.
            if isinstance(column.server_default, sqlalchemy.FetchedValue):
                continue
            # Filter columns with a server_onupdate.
            if isinstance(column.server_onupdate, sqlalchemy.FetchedValue):
                continue
            # Pass-through, add the input.
            out[name] = value

        return out

    @staticmethod
    @abc.abstractmethod
    def table_columns() -> tuple[sqlalchemy.Column, ...]:
        ...

    @classmethod
    def select_columns(
        cls,
    ) -> tuple[sqlalchemy.sql.ColumnElement, ...] | tuple[sqlalchemy.Table]:
        return (cls.table,)

    @classmethod
    def deserialize(cls, row: Mapping[str, Any] | None) -> abstract.InstanceT | None:
        if row is None:
            return  # type: ignore[return-value] # Return value expected
        return cls.model(**row)

    @classmethod
    def deserialize_list(
        cls, rows: List[Mapping[str, Any]] | None
    ) -> List[abstract.InstanceT]:
        if rows is None:
            return []
        return [cls.model(**row) for row in rows]

    @overload
    def affected_or_instance(
        self, affected: int, id: int, fetch: Literal[False]
    ) -> int:
        ...

    @overload
    def affected_or_instance(
        self, affected: int, id: int, fetch: Literal[True]
    ) -> abstract.InstanceT | None:
        ...

    def affected_or_instance(self, *, affected: int, id: int, fetch: bool):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # If we don't want the new user object, just return the affected rowcount.
        if fetch is False:
            return affected
        # Don't wast a db round-trip if there were no affected rows.
        if affected == 0:
            return
        # Get the user object we just updated.
        return self.get(id=id)
