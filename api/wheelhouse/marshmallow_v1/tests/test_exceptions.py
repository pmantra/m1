# -*- coding: utf-8 -*-

from marshmallow_v1.exceptions import (
    ValidationError,
    MarshallingError,
    UnmarshallingError,
)
from marshmallow_v1 import fields


class TestValidationError:
    def test_stores_message_in_list(self):
        err = ValidationError("foo")
        assert err.messages == ["foo"]

    def test_can_pass_list_of_messages(self):
        err = ValidationError(["foo", "bar"])
        assert err.messages == ["foo", "bar"]

    def test_stores_dictionaries(self):
        messages = {"user": {"email": ["email is invalid"]}}
        err = ValidationError(messages)
        assert err.messages == messages

    def test_can_store_field_name(self):
        err = ValidationError("invalid email", field="email")
        assert err.field == "email"

    def test_str(self):
        err = ValidationError("invalid email")
        assert str(err) == "invalid email"

        err2 = ValidationError("invalid email", "email")
        assert str(err2) == "invalid email"


class TestMarshallingError:
    def test_can_store_field_and_field_name(self):
        field_name = "foo"
        field = fields.Str()
        err = MarshallingError(
            "something went wrong", field=field, field_name=field_name
        )
        assert err.field == field
        assert err.field_name == field_name


class TestUnmarshallingError:
    def test_can_store_field_and_field_name(self):
        field_name = "foo"
        field = fields.Str()
        err = UnmarshallingError(
            "something went wrong", field=field, field_name=field_name
        )
        assert err.field == field
        assert err.field_name == field_name
