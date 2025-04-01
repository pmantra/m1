from sqlalchemy import Column, Integer, String

from utils.data import PHONE_NUMBER_LENGTH

from .base import TimeLoggedModelBase


class BlockedPhoneNumber(TimeLoggedModelBase):
    __tablename__ = "blocked_phone_number"

    id = Column(Integer, primary_key=True)
    digits = Column(String(PHONE_NUMBER_LENGTH), nullable=False, unique=True)
    error_code = Column(String(10))

    def __repr__(self) -> str:
        return (
            f"<BlockedPhoneNumber[{self.id}] {self.digits} active: {self.error_code}>"
        )

    __str__ = __repr__
