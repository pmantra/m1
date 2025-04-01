from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship, validates
from wtforms import validators

from models import base
from models.tracks.track import validate_name
from provider_matching.models.vgc import validate_vgc


class PractitionerTrackVGC(base.TimeLoggedModelBase):

    __tablename__ = "practitioner_track_vgc"

    constraints = (UniqueConstraint("practitioner_id", "track", "vgc"),)

    id = Column(Integer, primary_key=True)

    practitioner_id = Column(
        Integer, ForeignKey("practitioner_profile.user_id"), nullable=False
    )
    practitioner = relationship("PractitionerProfile")
    track = Column(String(120), nullable=False)
    vgc = Column(String(120), nullable=False)

    def __repr__(self) -> str:
        return (
            "<PractitionerTrackVGC: "
            f"Practitioner ID {self.practitioner_id}, "
            f"Track {self.track}, "
            f"VGC: {self.vgc}>"
        )

    @validates("practitioner")
    def validate_practitioner(self, key, practitioner):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if practitioner.active:
            return practitioner
        raise validators.ValidationError("Error: Can not add an inactive practitioner.")

    @validates("track")
    def validate_track_exists(self, key, track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        validate_name(self, key, track)
        return track

    @validates("vgc")
    def validate_vgc_exists(self, key, vgc):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        validate_vgc(self, key, vgc)
        return vgc
