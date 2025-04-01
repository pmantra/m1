from views.schemas.common_v3 import (
    IntegerWithDefaultV3,
    MavenSchemaV3,
    StringWithDefaultV3,
)


class MoneyAmountSchemaV3(MavenSchemaV3):
    currency_code = StringWithDefaultV3(default="")
    amount = IntegerWithDefaultV3(default=0)
    formatted_amount = StringWithDefaultV3(default="")
    formatted_amount_truncated = StringWithDefaultV3(default="")
    raw_amount = StringWithDefaultV3(default="")
