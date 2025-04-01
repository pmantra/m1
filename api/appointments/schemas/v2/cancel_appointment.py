from __future__ import annotations  # needed for python 3.9 type annotations

from marshmallow import fields as marshmallow_fields

from views.schemas.base import MavenSchemaV3


class ProviderCancelAppointmentRequestSchema(MavenSchemaV3):
    cancelled_note = marshmallow_fields.String(
        required=False, allow_none=True, load_default=None
    )
