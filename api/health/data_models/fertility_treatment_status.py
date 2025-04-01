from sqlalchemy import Column, ForeignKey, Integer, String

from models import base


class FertilityTreatmentStatus(base.TimeLoggedModelBase):
    __tablename__ = "fertility_treatment_status"

    def __repr__(self) -> str:
        return f"<FertilityTreatmentStatus [{self.user_id}]: Status: {self.fertility_treatment_status}>"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    fertility_treatment_status = Column(String(200), nullable=False)
