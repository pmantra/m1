# -*- coding: utf-8 -*-
import pytest

from marshmallow_v1 import fields

from tests.base import ALL_FIELDS


class TestFieldAliases:
    def test_enum_is_select(self):
        assert fields.Enum is fields.Select

    def test_int_is_integer(self):
        assert fields.Int is fields.Integer

    def test_str_is_string(self):
        assert fields.Str is fields.String

    def test_bool_is_boolean(self):
        assert fields.Bool is fields.Boolean


class TestField:
    def test_repr(self):
        default = u"œ∑´"
        field = fields.Field(default=default, attribute=None)
        assert repr(field) == (
            u"<fields.Field(default={0!r}, attribute=None, "
            "error=None, validate=None, required=False)>".format(default)
        )
        int_field = fields.Integer(validate=lambda x: True)
        assert "<fields.Integer" in repr(int_field)

    def test_error_raised_if_uncallable_validator_passed(self):
        with pytest.raises(ValueError):
            fields.Field(validate="notcallable")


class TestMetadata:

    FIELDS_TO_TEST = [
        field
        for field in ALL_FIELDS
        if field not in [fields.Enum, fields.FormattedString]
    ]

    @pytest.mark.parametrize("FieldClass", FIELDS_TO_TEST)
    def test_extra_metadata_may_be_added_to_field(self, FieldClass):  # noqa
        field = FieldClass(description="Just a normal field.")
        assert field.metadata["description"] == "Just a normal field."
        field = FieldClass(
            required=True,
            default=None,
            validate=lambda v: True,
            description="foo",
            widget="select",
        )
        assert field.metadata == {"description": "foo", "widget": "select"}

    def test_metadata_may_be_added_to_formatted_string_field(self):
        field = fields.FormattedString("hello {name}", description="a greeting")
        assert field.metadata == {"description": "a greeting"}

    def test_metadata_may_be_added_to_enum_field(self):
        field = fields.Enum(["red", "blue"], description="A color")
        assert field.metadata == {"description": "A color"}
