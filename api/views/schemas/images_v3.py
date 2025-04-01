from views.schemas.base import (
    BooleanWithDefault,
    IntegerWithDefaultV3,
    MavenSchemaV3,
    StringWithDefaultV3,
)


class ImageSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0)
    height = IntegerWithDefaultV3(dump_default=0)
    width = IntegerWithDefaultV3(dump_default=0)
    filetype = StringWithDefaultV3(dump_default="", load_default="")
    url = StringWithDefaultV3(dump_default="", load_default="")


class AssetSchemaV3(MavenSchemaV3):
    url = StringWithDefaultV3(dump_default="", load_default="")


class ImageGetSchemaV3(MavenSchemaV3):
    smart = BooleanWithDefault(load_default=True, dump_default=True)
