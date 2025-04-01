from __future__ import annotations

from marshmallow import fields, pre_load

from views.schemas.base import (
    CSVIntegerFieldV3,
    DecimalWithDefault,
    IntegerWithDefaultV3,
    MavenSchemaV3,
    NestedWithDefaultV3,
    PaginableOutputSchemaV3,
    StringWithDefaultV3,
)


class ProductsGetArgsV3(MavenSchemaV3):
    @pre_load
    def normalize_none(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for k, v in data.items():
            # This is for backwards compatibility of a required field. Interestingly,
            # the required behavior is already broken due to our customize field implementation
            # i.e.
            #     data = {'vertical_name': None, 'practitioner_ids': None}
            #     from views.products import ProductsGetArgs
            #     schema = ProductGetArgs()
            #     schema.load(data)
            # essentially, there won't be validation error for `practitioner_ids` at all
            if "practitioner_ids" in data and data["practitioner_ids"] is None:
                data["practitioner_ids"] = []
            if v is None and not self.fields[k].allow_none:  # type: ignore[has-type] # Cannot determine type of "allow_none"
                data[k] = self.fields[k].load_default  # type: ignore[attr-defined] # "Field" has no attribute "load_default"

            return data

    practitioner_ids = CSVIntegerFieldV3(required=True)
    vertical_name = StringWithDefaultV3(dump_default="", load_default="")


class ProductSimpleSchemaV3(MavenSchemaV3):
    id = fields.Integer()
    minutes = fields.Integer()
    price = DecimalWithDefault(as_string=True, dump_default=0)
    practitioner_id = IntegerWithDefaultV3(attribute="user_id", dump_default=0)


class ProductsSchemaV3(PaginableOutputSchemaV3):
    data = NestedWithDefaultV3(ProductSimpleSchemaV3, many=True, dump_default=[])  # type: ignore[assignment] # Incompatible types in assignment (expression has type "NestedWithDefaultV3", base class "PaginableOutputSchemaV3" defined the type as "RawWithDefaultV3")
