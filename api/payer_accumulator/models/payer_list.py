from sqlalchemy import BigInteger, Column, Enum, String

from models.base import TimeLoggedModelBase
from payer_accumulator.common import PayerName


class Payer(TimeLoggedModelBase):
    __tablename__ = "payer_list"

    id = Column(BigInteger, primary_key=True)
    payer_name = Column(Enum(PayerName), nullable=False)
    payer_code = Column(String(255), nullable=True)

    def __repr__(self) -> str:
        return self.payer_name.value  # type: ignore[attr-defined] # "str" has no attribute "value"
