from views.schemas.common import BooleanField, MavenSchema


class PractitionerReplacementSchema(MavenSchema):
    remove_only_quiz_type = BooleanField(
        required=True,
    )
