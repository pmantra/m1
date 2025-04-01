# via https://gist.github.com/dbarnett/1730610
import contextlib
import json

import ddtrace
import phonenumbers
import sqlalchemy
import sqlalchemy.dialects.mysql as sa_mysql
from marshmallow_v1 import ValidationError
from sqlalchemy import String
from sqlalchemy.ext.mutable import Mutable
from structlog.stdlib import BoundLogger

from utils.log import logger as get_logger

# Make sure to keep default_schema.sql up to date when changing this constant.
PHONE_NUMBER_LENGTH = 50


logger: BoundLogger = get_logger(__name__)


class JSONEncodedObj(sqlalchemy.types.TypeDecorator):
    """Represents an immutable structure as a json-encoded string."""

    impl = String

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            return value
        try:
            return json.loads(value)
        except (ValueError, TypeError, json.decoder.JSONDecodeError) as err:
            logger.exception("Failed to decode JSON value.", exception=err)
            return None


class TinyIntEnum(sqlalchemy.types.TypeDecorator):
    """
    Represent a Python IntEnum that is stored as an Integer type
    Best for high-cardinality,

    Future: make the impl dynamic based on kwargs so the user can specify alternatively-sized integers as needed
    without having to duplicate the logic.
    """

    impl = sa_mysql.TINYINT

    def __init__(self, enum_class, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(*args, **kwargs)
        self.enum_class = enum_class

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return value.value

    def process_result_value(self, value, dialect):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self.enum_class(value)


class MutationObj(Mutable):
    @classmethod
    def coerce(cls, key, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(value, dict) and not isinstance(value, MutationDict):
            return MutationDict.coerce(key, value)
        if isinstance(value, list) and not isinstance(value, MutationList):
            return MutationList.coerce(key, value)
        return value

    @classmethod
    def _listen_on_attribute(cls, attribute, coerce, parent_cls):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        key = attribute.key
        if parent_cls is not attribute.class_:
            return

        # rely on "propagate" here
        parent_cls = attribute.class_

        def load(state, *args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            val = state.dict.get(key, None)
            if coerce:
                val = cls.coerce(key, val)
                state.dict[key] = val
            if isinstance(val, cls):
                val._parents[state.obj()] = key  # type: ignore[attr-defined] # "MutationObj" has no attribute "_parents"

        def set(target, value, oldvalue, initiator):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            if not isinstance(value, cls):
                value = cls.coerce(key, value)
            if isinstance(value, cls):
                value._parents[target.obj()] = key  # type: ignore[attr-defined] # "MutationObj" has no attribute "_parents"
            if isinstance(oldvalue, cls):
                oldvalue._parents.pop(target.obj(), None)  # type: ignore[attr-defined] # "MutationObj" has no attribute "_parents"
            return value

        def pickle(state, state_dict):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            val = state.dict.get(key, None)
            if isinstance(val, cls):
                if "ext.mutable.values" not in state_dict:
                    state_dict["ext.mutable.values"] = []
                state_dict["ext.mutable.values"].append(val)

        def unpickle(state, state_dict):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            if "ext.mutable.values" in state_dict:
                for val in state_dict["ext.mutable.values"]:
                    val._parents[state.obj()] = key

        sqlalchemy.event.listen(parent_cls, "load", load, raw=True, propagate=True)
        sqlalchemy.event.listen(parent_cls, "refresh", load, raw=True, propagate=True)
        sqlalchemy.event.listen(
            attribute, "set", set, raw=True, retval=True, propagate=True
        )
        sqlalchemy.event.listen(parent_cls, "pickle", pickle, raw=True, propagate=True)
        sqlalchemy.event.listen(
            parent_cls, "unpickle", unpickle, raw=True, propagate=True
        )


class MutationDict(MutationObj, dict):
    @classmethod
    def coerce(cls, key, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Convert plain dictionary to MutationDict"""
        self = MutationDict((k, MutationObj.coerce(key, v)) for (k, v) in value.items())
        self._key = key  # type: ignore[attr-defined] # "MutationDict" has no attribute "_key"
        return self

    def __setitem__(self, key, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        dict.__setitem__(self, key, MutationObj.coerce(self._key, value))  # type: ignore[attr-defined] # "MutationDict" has no attribute "_key"
        self.changed()

    def __delitem__(self, key):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        dict.__delitem__(self, key)
        self.changed()


class MutationList(MutationObj, list):
    @classmethod
    def coerce(cls, key, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Convert plain list to MutationList"""
        self = MutationList((MutationObj.coerce(key, v) for v in value))
        self._key = key  # type: ignore[attr-defined] # "MutationList" has no attribute "_key"
        return self

    def __setitem__(self, idx, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        list.__setitem__(self, idx, MutationObj.coerce(self._key, value))  # type: ignore[attr-defined] # "MutationList" has no attribute "_key"
        self.changed()

    def __setslice__(self, start, stop, values):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        list.__setslice__(  # type: ignore[attr-defined] # "Type[List[Any]]" has no attribute "__setslice__"
            self, start, stop, (MutationObj.coerce(self._key, v) for v in values)  # type: ignore[attr-defined] # "MutationList" has no attribute "_key"
        )
        self.changed()

    def __delitem__(self, idx):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        list.__delitem__(self, idx)
        self.changed()

    def __delslice__(self, start, stop):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        list.__delslice__(self, start, stop)  # type: ignore[attr-defined] # "Type[List[Any]]" has no attribute "__delslice__"
        self.changed()

    def append(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        list.append(self, MutationObj.coerce(self._key, value))  # type: ignore[attr-defined] # "MutationList" has no attribute "_key"
        self.changed()

    def insert(self, idx, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        list.insert(self, idx, MutationObj.coerce(self._key, value))  # type: ignore[attr-defined] # "MutationList" has no attribute "_key"
        self.changed()

    def extend(self, values):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        list.extend(self, (MutationObj.coerce(self._key, v) for v in values))  # type: ignore[attr-defined] # "MutationList" has no attribute "_key"
        self.changed()

    def pop(self, *args, **kw):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        value = list.pop(self, *args, **kw)
        self.changed()
        return value

    def remove(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        list.remove(self, value)
        self.changed()


def JSONAlchemy(sqltype):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """A type to encode/decode JSON on the fly

    sqltype is the string type for the underlying DB column.

    You can use it like:
    Column(JSONAlchemy(Text(600)))
    """

    class _JSONEncodedObj(JSONEncodedObj):
        impl = sqltype

    return MutationObj.as_mutable(_JSONEncodedObj)


# ---- Shared utility functions -----


@ddtrace.tracer.wrap()
def normalize_phone_number(number, region, number_length=PHONE_NUMBER_LENGTH):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        phone_number = _parse_phone_number(number, region)
    except phonenumbers.NumberParseException as e:
        raise ValidationError(e)

    normalized = phonenumbers.format_number(
        phone_number, phonenumbers.PhoneNumberFormat.RFC3966
    )

    # Can we store this phone number in the database?
    if len(normalized) > number_length:
        raise ValidationError(
            "Normalized phone number ({}) too long {} > {}".format(
                normalized, len(normalized), number_length
            )
        )

    # We want to make sure that the normalized number alone can be used to recreate all of the information provided by
    # the original number and region, including information not represented by E164 such as extensions.
    normalized_parsed = phonenumbers.parse(normalized, None)
    if phone_number != normalized_parsed:
        raise ValidationError(
            "Original region ({}) and number ({}) were parsed ({}), but normalized number ({}) was parsed as ({}).".format(
                region, number, phone_number, normalized, normalized_parsed
            )
        )

    return normalized, phone_number


def _parse_phone_number(number, region):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Try parsing the number under the given region, potentially None.
    with contextlib.suppress(phonenumbers.NumberParseException):
        n = phonenumbers.parse(number, region)
        if phonenumbers.is_valid_number(n):
            return n
    logger.warning("Couldn't parse phone number with given region.", region=region)

    # Try parsing the number as a US number.
    with contextlib.suppress(phonenumbers.NumberParseException):
        if region is None:
            n = phonenumbers.parse(number, "US")
            if phonenumbers.is_valid_number(n):
                return n
    logger.warning("Failed to parse phone number with US region.")

    # Try parsing the number as international by prepending a +.
    with contextlib.suppress(phonenumbers.NumberParseException):
        n = phonenumbers.parse("+" + number, None)
        if phonenumbers.is_valid_number(n):
            logger.debug("Parsed as international phone number.")
            return n

    logger.warning("Failed to parse phone number as international.")
    # None of our parsing strategies worked, and the last strategy yielded an invalid number.
    raise ValidationError(f"Phone number ({number}) and region ({region}) not valid.")


def normalize_phone_number_old(num, include_extension):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if num is None:
        return ""
    ret = str(num.national_number)
    if include_extension and num.extension:
        ret += "x"
        ret += num.extension
    return ret


def calculate_bmi(height, weight):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return 703 * weight / height**2
