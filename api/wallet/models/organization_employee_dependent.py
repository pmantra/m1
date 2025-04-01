import secrets

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import TimeLoggedModelBase
from storage.connection import db


class OrganizationEmployeeDependent(TimeLoggedModelBase):
    __tablename__ = "organization_employee_dependent"

    id = Column(Integer, primary_key=True)
    alegeus_dependent_id = Column(String(30))
    first_name = Column(String(40))
    last_name = Column(String(40))
    middle_name = Column(String(40))
    reimbursement_wallet_id = Column(
        ForeignKey("reimbursement_wallet.id", ondelete="CASCADE"), nullable=True
    )
    reimbursement_wallet = relationship("ReimbursementWallet")

    def create_alegeus_dependent_id(self) -> None:
        self.alegeus_dependent_id = secrets.token_hex(15)
        db.session.commit()

    def __repr__(self) -> str:
        return f"<Wallet Authorized User: {self.id}>"
