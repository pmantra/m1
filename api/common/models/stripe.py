from sqlalchemy import Column, Integer, String, Text

from models import base
from utils.data import JSONAlchemy


class StripeAction(base.TimeLoggedModelBase):
    __tablename__ = "stripe_action"
    __bind_key__ = "audit"

    id = Column(Integer, primary_key=True)

    type = Column(String(30))
    user_id = Column(Integer, nullable=True)
    stripe_json = Column(JSONAlchemy(Text), nullable=True)
    data = Column(JSONAlchemy(Text))

    def __repr__(self) -> str:
        return f"<StripeAction {self.type} [User {self.user_id}]>"
