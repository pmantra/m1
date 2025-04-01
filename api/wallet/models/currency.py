import dataclasses
from decimal import Decimal


@dataclasses.dataclass(frozen=True)
class Money:
    amount: Decimal
    currency_code: str
