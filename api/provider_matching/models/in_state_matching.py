from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship, validates

from geography.repository import SubdivisionRepository
from models.base import ModelBase


class VerticalInStateMatchState(ModelBase):
    __tablename__ = "vertical_in_state_match_state"

    constraints = (UniqueConstraint("vertical_id", "state_id", "subdivision_code"),)

    vertical = relationship("Vertical")
    vertical_id = Column(
        Integer,
        ForeignKey("vertical.id"),
        primary_key=True,
    )
    state = relationship("State")
    state_id = Column(
        Integer,
        ForeignKey("state.id"),
        primary_key=True,
    )

    subdivision_code = Column(String(6), nullable=True)

    def __repr__(self) -> str:
        return (
            "<VerticalInStateMatchState: "
            f"Vertical {self.vertical.name}, "
            f"State {self.state.abbreviation}>"
        )


class VerticalInStateMatching(ModelBase):
    __tablename__ = "vertical_in_state_matching"
    constraints = (UniqueConstraint("vertical_id", "subdivision_code"),)

    id = Column(Integer, primary_key=True)
    vertical_id = Column(
        Integer,
        ForeignKey("vertical.id"),
        nullable=False,
    )
    vertical = relationship("Vertical", back_populates="in_state_matching")

    subdivision_code = Column(String(6), nullable=False)

    def __repr__(self) -> str:
        return (
            "<VerticalInStateMatching: "
            f"Vertical {self.vertical.name}, "
            f"Subdivision Code {self.subdivision_code}>"
        )

    @validates("subdivision_code")
    def validate_subdivision_code(self, key, subdivision_code: str):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        subdivision_repo = SubdivisionRepository()
        subdivision = subdivision_repo.get(subdivision_code=subdivision_code)

        # We want to keep "US-ZZ" as a valid subdivision code, even if it's not technically valid.
        # This is in line with how we currently handle international members.
        if not subdivision and subdivision_code != "US-ZZ":
            raise ValueError(
                f"Error: '{subdivision_code}' is not a valid subdivision code"
            )
        return subdivision_code
