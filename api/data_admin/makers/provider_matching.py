from flask import flash
from marshmallow_v1 import fields

from data_admin.maker_base import _MakerBase
from models.profiles import PractitionerProfile, PractitionerSubdivision
from models.tracks import TrackName
from models.verticals_and_specialties import Vertical
from provider_matching.models.practitioner_track_vgc import PractitionerTrackVGC
from provider_matching.models.vgc import VGC
from storage.connection import db
from utils.log import logger
from utils.migrations.populate_practitioner_track_vgc import (
    _get_one_associated_vertical,
)
from views.schemas.common import MavenSchema

log = logger(__name__)


class PractitionerTrackVGCSchema(MavenSchema):
    track_name = fields.Enum(choices=[t.value for t in TrackName])
    vgc = fields.Enum(choices=[*VGC])
    certified_subdivision_codes = fields.String()


class PractitionerTrackVGCMaker(_MakerBase):
    spec_class = PractitionerTrackVGCSchema(strict=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "PractitionerTrackVGCSchema", base class "_MakerBase" defined the type as "None")

    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"

        if spec_data.get("track_name") not in [*TrackName]:
            flash(f"Track Not Found {spec.get('track_name')}", "error")
            return

        if spec_data.get("vgc") not in [*VGC]:
            flash(f"VGC Not Found {spec.get('vgc')}", "error")
            return

        vertical = _get_one_associated_vertical(VGC(spec_data.get("vgc")))

        prac_profile = (
            PractitionerProfile.query.join(PractitionerProfile.verticals)
            .filter(Vertical.id == vertical.id)
            .join(PractitionerProfile.certified_practitioner_subdivisions)
            .filter(
                PractitionerSubdivision.subdivision_code
                == spec_data.get("certified_subdivision_codes")
            )
            .one_or_none()
        )

        # Just log verticals with no practitioners for now
        if not prac_profile:
            track_name = spec_data.get("track_name")
            certified_subdivision_codes = spec_data.get("certified_subdivision_codes")
            log.warning(
                "PractitionerProfile Not Found: "
                f"(Vertical: {vertical.name}, "
                f"Track: {track_name}, "
                f"State: {certified_subdivision_codes}"
            )
            # Return someting that will pass the empty check
            # Otherwise the final flash doesn't show
            return True

        else:
            ptv = PractitionerTrackVGC(
                practitioner_id=prac_profile.user_id,
                track=spec_data.get("track_name"),
                vgc=spec_data.get("vgc"),
            )
            db.session.add(ptv)
            return ptv
