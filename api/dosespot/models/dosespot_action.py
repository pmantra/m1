from sqlalchemy import Column, Integer, String, Text

from models.base import TimeLoggedModelBase
from utils.data import JSONAlchemy


class DoseSpotAction(TimeLoggedModelBase):
    __tablename__ = "dosespot_action"
    __bind_key__ = "audit"

    id = Column(Integer, primary_key=True)

    type = Column(String(30))
    user_id = Column(Integer, nullable=False)
    ds_xml = Column(Text, nullable=True)
    data = Column(JSONAlchemy(Text), default={})

    def __repr__(self) -> str:
        return f"<DoseSpotAction {self.type} [User {self.user_id}]>"

    __str__ = __repr__
