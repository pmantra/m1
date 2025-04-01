import datetime
import json
import uuid
from typing import Any, Callable, Dict, Optional

import snowflake
from dateutil.parser import parse
from sqlalchemy import BigInteger, Column, DateTime, String, inspect
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Mapper
from sqlalchemy.types import VARBINARY

from storage.connection import db
from utils.data import JSONEncodedObj
from utils.json import SafeJSONEncoder
from utils.log import logger

log = logger(__name__)


class ModelBase(db.Model):  # type: ignore[name-defined] # Name "db.Model" is not defined
    __abstract__ = True
    __bind_key__ = "default"
    __restricted_columns__ = frozenset([])
    __calculated_columns__ = frozenset([])

    constraints: tuple = ()

    @declared_attr
    def __table_args__(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        _defaults = {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        }
        return cls.constraints + (_defaults,)

    @property
    def export_schema(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        data = {}
        col: Column
        for col in self.__table__.columns:
            if col.name in self.__restricted_columns__:
                continue
            value = getattr(self, col.name)
            if isinstance(col.type, JSONEncodedObj):
                value = json.dumps(value, cls=SafeJSONEncoder)
            data[col.name] = value

        for col in self.__calculated_columns__:
            if hasattr(self, col):  # type: ignore[arg-type] # Argument 2 to "hasattr" has incompatible type "Column[Any]"; expected "str"
                value = getattr(self, col)  # type: ignore[call-overload] # No overload variant of "getattr" matches argument types "ModelBase", "Column[Any]"
                if callable(value):
                    value = value()
                data[col] = value  # type: ignore[index] # Invalid index type "Column[Any]" for "Dict[str, Any]"; expected type "str"
            else:
                raise ValueError(f"Invalid calculated column: {col}")
        data["exported_at"] = datetime.datetime.now()
        return data

    # useful if you need to use an ORM object in a core SQL query
    def to_dict(self) -> Dict[str, Any]:
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
            if getattr(self, column.name) is not None
        }


class ModifiedAtModelBase(ModelBase):
    __abstract__ = True

    modified_at = Column(
        DateTime,
        default=lambda: datetime.datetime.utcnow(),
        onupdate=lambda: datetime.datetime.utcnow(),
        doc="When this record was last modified.",
    )


class TimeLoggedModelBase(ModifiedAtModelBase):
    __abstract__ = True

    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.utcnow(),
        doc="When this record was created.",
    )


class TimeLoggedExternalUuidModelBase(TimeLoggedModelBase):
    __abstract__ = True

    id = Column(BigInteger, primary_key=True)
    uuid = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))


def default_snowflake_created_at(context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Create default ID if context doesn't exist
    snowflake_id = (
        context.get_current_parameters()["id"] if context else snowflake.generate()
    )
    return snowflake.to_datetime(snowflake_id)


def default_snowflake_id(context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not context:
        return snowflake.generate()

    parameters = context.get_current_parameters()
    if "created_at" in parameters and isinstance(
        parameters["created_at"], datetime.datetime
    ):
        return snowflake.from_datetime(parameters["created_at"])
    else:
        return snowflake.generate()


class TimeLoggedSnowflakeModelBase(ModifiedAtModelBase):
    __abstract__ = True

    id = Column(
        BigInteger, primary_key=True, autoincrement=False, default=default_snowflake_id
    )

    # https://docs.sqlalchemy.org/en/14/core/defaults.html#context-sensitive-default-functions
    created_at = Column(DateTime, default=default_snowflake_created_at)

    def __init__(self, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if "id" not in kwargs or kwargs["id"] is None:
            kwargs["id"] = snowflake.generate()
            kwargs["created_at"] = snowflake.to_datetime(kwargs["id"])
        super().__init__(**kwargs)

    @property
    def export_schema(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        data = super().export_schema
        data["created_at"] = self.created_at
        return data


class PolymorphicAwareMixin:
    _empty = object()

    def __new__(cls, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        mapper: Mapper = inspect(cls)
        if mapper.polymorphic_map and mapper.polymorphic_on is not None:
            tag = mapper.polymorphic_on.name
            value = kwargs.pop(tag, cls._empty)
            if (
                value is not cls._empty
                and value in mapper.polymorphic_map
                and value != mapper.polymorphic_identity
            ):
                cls = mapper.polymorphic_map[value].class_
        return super().__new__(cls)


class CaseSensitiveStringType(VARBINARY):
    """Custom String type that supports case sensitive look up.
    It uses MySQL binary types behind the scene for storage but
    it's charset and collation neutral.
    @SEE http://docs.sqlalchemy.org/en/rel_0_9/core/custom_types.html#replacing-the-bind-result-processing-of-existing-types
    @TODO: implement all abstract methods?
    """

    def result_processor(self, dialect, coltype):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        def process(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            if value is not None:
                return value.decode("utf-8")
            else:
                return None

        return process

    def bind_processor(self, dialect):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # DBAPIBinary = dialect.dbapi.Binary

        def process(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            if value is not None:
                # return DBAPIBinary(value)
                return value.encode("utf-8")
            else:
                return None

        return process


class JSONProperty:
    """
    To be used on models storing named data in 'json' columns. Subclasses
    handle various data types.
    """

    converter: Callable[[Any], Any]

    def __init__(self, name: str, *, nullable: bool = True, default: Any = None):
        self.name: str = name
        self.nullable: bool = nullable
        self.default = default

    def __get__(self, obj, type=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if obj is not None:
            value = obj.json.get(self.name) if obj.json else None
            if self.default and value is None:
                value = self.default
            return self.convert_outgoing(value)

    def __set__(self, obj, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not obj.json:
            obj.json = {}
        if value is None and self.nullable:
            obj.json.pop(self.name, None)
        else:
            obj.json[self.name] = self.convert_incoming(value)

        # This method is defined on the JSONAlchemy object when running the API "normally"
        # but not on the regular 'dict' that gets passed by flask-admin (in our Admin tool).
        if hasattr(obj.json, "changed"):
            obj.json.changed()

    def convert_outgoing(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None and self.nullable:
            return value
        return self.converter(value)

    def convert_incoming(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None and self.nullable:
            return value
        return self.converter(value)


class StringJSONProperty(JSONProperty):
    @staticmethod
    def converter(value) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return str(value)


class IntJSONProperty(JSONProperty):
    def converter(self, value) -> Optional[int]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        try:
            return int(value)
        except ValueError:
            return self.default


class DateJSONProperty(JSONProperty):
    def convert_outgoing(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            if value:
                return parse(value).date()
        except ValueError:
            return self.default

    def convert_incoming(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None and self.nullable:
            return value
        if not isinstance(value, datetime.date):
            raise ValueError("Value should be datetime.date object")
        return value.strftime("%Y-%m-%d")


class BoolJSONProperty(JSONProperty):
    @staticmethod
    def converter(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return bool(value)


class ObjectJSONProperty(JSONProperty):
    @staticmethod
    def converter(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return dict(value)
