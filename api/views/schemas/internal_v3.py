from __future__ import annotations

from views.schemas.base import MavenSchemaV3, StringWithDefaultV3


class AttachmentSchemaV3(MavenSchemaV3):
    token = StringWithDefaultV3(required=True, dump_default="")
